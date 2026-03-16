"""PolyhybridEngine — orchestrates SimPy, NetworkX, and py-trees.

Central coordination of patient flow through the treatment chain.
"""

from __future__ import annotations

import logging
import time as _time
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
import simpy

from faer_dev.core.enums import OperationalContext, PatientState, Role, TriageCategory
from faer_dev.core.schemas import Casualty, Facility
from faer_dev.network.topology import TreatmentNetwork
from faer_dev.simulation.arrivals import (
    ArrivalConfig,
    ArrivalProcess,
    ArrivalRecord,
    MASCALEvent,
    get_arrival_config,
)
from faer_dev.decisions.mode import SimulationToggles
from faer_dev.routing import (
    triage_decisions as _extracted_triage_decisions,
    get_next_destination as _extracted_get_next_destination,
)
from faer_dev.events.bus import EventBus
from faer_dev.events.store import EventStore
from faer_dev.events.run_logger import RunLogger
from faer_dev.simulation.casualty_factory import create_factory
from faer_dev.simulation.departments import FacilityInternalGraph, build_r1, build_r2, build_r3
from faer_dev.simulation.mascal import MASCALDetector
from faer_dev.simulation.queues import FacilityQueue
from faer_dev.simulation.transport import (
    TransportConfig,
    TransportPool,
    get_transport_config,
    resolve_transport_mode,
)

logger = logging.getLogger(__name__)

# Known event types for structured logging (string-typed, not enum,
# allowing VOP platform types like "CHINOOK_MERT" without extension)
KNOWN_EVENT_TYPES = [
    "ARRIVAL", "TRIAGE", "TRANSIT_START", "TRANSIT_END",
    "FACILITY_ARRIVAL", "TREATMENT_START", "TREATMENT_END",
    "DISPOSITION", "MASCAL_ACTIVATE", "MASCAL_DEACTIVATE",
    "HOLD_START", "HOLD_RETRY", "HOLD_TIMEOUT",
    "PFC_START", "PFC_END", "PFC_CEILING_EXCEEDED",
    "R1_DEPT", "R2_DEPT", "DCS",
    "ATMIST_HANDOVER", "NINE_LINER",
]

# Treatment times by facility role (mean minutes)
DEFAULT_TREATMENT_TIMES: Dict[Role, Dict[str, int]] = {
    Role.R1: {
        "T1_SURGICAL": 20, "T1_MEDICAL": 20,
        "T2": 30, "T3": 15, "T4": 10,
    },
    Role.R2: {
        "T1_SURGICAL": 90, "T1_MEDICAL": 60,
        "T2": 45, "T3": 20, "T4": 15,
    },
    Role.R3: {
        "T1_SURGICAL": 180, "T1_MEDICAL": 120,
        "T2": 60, "T3": 30, "T4": 20,
    },
}

# Role progression order for determining next destination
ROLE_ORDER = [Role.POI, Role.R1, Role.R2, Role.R3, Role.R4]


def _triage_decisions(patient: Casualty) -> Dict[str, Any]:
    """Evaluate triage and return clinical decisions.

    Simplified decision logic extracted from notebook TriageDecisionMaker.
    Will be replaced by py-trees behavior tree in Phase 3.
    """
    decisions: Dict[str, Any] = {
        "recommended_triage": patient.triage,
        "bypass_role1": False,
        "requires_dcs": False,
        "priority": 5,
    }

    if patient.triage == TriageCategory.T1_SURGICAL:
        decisions["priority"] = 1
        decisions["bypass_role1"] = True
        decisions["requires_dcs"] = True
    elif patient.triage == TriageCategory.T1_MEDICAL:
        decisions["priority"] = 1
        decisions["bypass_role1"] = True
    elif patient.triage == TriageCategory.T2:
        decisions["priority"] = 2
    elif patient.triage == TriageCategory.T3:
        decisions["priority"] = 3
    elif patient.triage == TriageCategory.T4:
        decisions["priority"] = 5

    return decisions


def _get_next_destination(
    patient: Casualty,
    current_facility: Facility,
    network: TreatmentNetwork,
    decisions: Dict[str, Any],
) -> Optional[str]:
    """Determine the next facility in the treatment chain.

    Returns None when the patient journey is complete (RTD or end of chain).
    """
    current_idx = ROLE_ORDER.index(current_facility.role)

    # T3 can RTD from R1 or R2
    if patient.triage == TriageCategory.T3 and current_facility.role in (
        Role.R1,
        Role.R2,
    ):
        return None

    # T4 stays at current location
    if patient.triage == TriageCategory.T4:
        return None

    # Walk up the chain looking for the next facility
    for next_idx in range(current_idx + 1, len(ROLE_ORDER)):
        next_role = ROLE_ORDER[next_idx]

        # Skip R1 if bypass indicated
        if next_role == Role.R1 and decisions["bypass_role1"]:
            continue

        for fac_id, fac in network.facilities.items():
            if fac.role != next_role:
                continue
            if network.graph.has_edge(current_facility.id, fac_id):
                return fac_id

    return None


class PolyhybridEngine:
    """Orchestrates SimPy, NetworkX, and triage decisions.

    This is the core integration class that coordinates all components
    of the FAER-M simulation.
    """

    def __init__(
        self,
        context: OperationalContext = OperationalContext.COIN,
        arrival_config: Optional[ArrivalConfig] = None,
        transport_config: Optional[TransportConfig] = None,
        seed: Optional[int] = None,
        # Legacy dict config support for builder.py
        config: Optional[Dict[str, Any]] = None,
        toggles: Optional[SimulationToggles] = None,
    ) -> None:
        self.context = context
        self._rng = np.random.default_rng(seed)
        self.toggles = toggles or SimulationToggles()

        # SimPy environment
        self.env = simpy.Environment()

        # Components
        self.network = TreatmentNetwork()

        # Resolve arrival config
        if arrival_config is not None:
            self._arrival_config = arrival_config
        elif config is not None:
            rate = config.get("arrival_rate", 2.0)
            self._arrival_config = ArrivalConfig(
                base_rate_per_hour=rate, mascal_enabled=False
            )
        else:
            self._arrival_config = get_arrival_config(context)

        # Casualty factory (mode controlled by toggles, default "legacy")
        if self.toggles.factory_mode == "inverted":
            from faer_dev.data.injury_loader import InjuryDataLoader
            from faer_dev.simulation.injury_sampler import DataDrivenInjurySampler
            from faer_dev.decisions.blackboard import SimBlackboard
            from faer_dev.decisions.trees import build_triage_tree

            self._injury_loader = InjuryDataLoader()
            self._injury_sampler = DataDrivenInjurySampler(
                context.name, self._injury_loader, self._rng,
            )
            self._triage_bt = build_triage_tree()
            self._blackboard = SimBlackboard(name="engine")

            self.casualty_factory = create_factory(
                mode="inverted",
                context=context,
                rng=self._rng,
                injury_sampler=self._injury_sampler,
                triage_bt=self._triage_bt,
                blackboard=self._blackboard,
            )
        else:
            self.casualty_factory = create_factory(
                mode=self.toggles.factory_mode,
                context=context,
                rng=self._rng,
            )

        # Transport pool
        self._transport_config = transport_config or get_transport_config(context)
        self.transport_pool = TransportPool(
            env=self.env, config=self._transport_config, rng=self._rng
        )

        # Arrival process (created at run time when POI is known)
        self.arrival_process: Optional[ArrivalProcess] = None
        self._mascal_events: List[MASCALEvent] = []
        self._poi_id: Optional[str] = None
        self._arrivals_started = False

        # Facility queues (created when facilities are added)
        self.queues: Dict[str, FacilityQueue] = {}

        # Department graphs (Phase 3 — coexists with queues)
        self.department_graphs: Dict[str, FacilityInternalGraph] = {}

        # MASCAL detector (Phase 3 — sliding window rate monitor)
        self.mascal_detector = MASCALDetector(
            window_minutes=15.0, threshold=20
        )

        # Patient tracking
        self.patients: Dict[str, Casualty] = {}
        self.completed_patients: List[Casualty] = []

        # Event log (legacy dict path)
        self.events: List[Dict[str, Any]] = []

        # Phase 4: typed event store + bus
        self.event_bus = EventBus()
        self.event_store = EventStore()
        self.event_bus.subscribe_all(self.event_store.append)
        self._run_logger = RunLogger()

        # Persist config for run logging / state saving
        self.config = config

        # Treatment times
        self.treatment_times = DEFAULT_TREATMENT_TIMES

        # CCP (Phase 4 Iter 4 — behind enable_ccp toggle)
        self._ccp = None
        self._injury_loader_for_pfc = None
        if self.toggles.enable_ccp:
            from faer_dev.simulation.ccp import CasualtyCollectionPoint, CCPConfig
            from faer_dev.data.injury_loader import InjuryDataLoader
            self._ccp = CasualtyCollectionPoint(self.env, CCPConfig())
            self._injury_loader_for_pfc = InjuryDataLoader()

        # Phase 3 optional subsystems (lazy init, behind toggles)
        self._vitals_gen = None
        self._atmist_formatter = None
        self._nine_liner_gen = None
        if self.toggles.enable_vitals or self.toggles.enable_atmist:
            self._init_clinical_subsystems()

    def add_facility(self, facility: Facility) -> None:
        """Add a facility to the network and create its queue."""
        self.network.add_facility(facility)
        if facility.role != Role.POI and facility.beds > 0:
            self.queues[facility.id] = FacilityQueue(self.env, facility)

            # Build department graph if toggle enabled
            if self.toggles.enable_department_routing:
                builder = {Role.R1: build_r1, Role.R2: build_r2, Role.R3: build_r3}
                build_fn = builder.get(facility.role)
                if build_fn:
                    self.department_graphs[facility.id] = build_fn(
                        self.env, facility.id, total_beds=facility.beds
                    )
        elif facility.role != Role.POI:
            logger.warning(
                "Facility %s has zero beds; skipping treatment queue creation.",
                facility.id,
            )

    def add_route(
        self,
        from_id: str,
        to_id: str,
        time_minutes: float,
        transport: str = "ground",
    ) -> None:
        """Add a transport route between facilities."""
        self.network.add_route(from_id, to_id, time_minutes, transport)

    def _init_clinical_subsystems(self) -> None:
        """Lazily initialize vitals/ATMIST subsystems."""
        from faer_dev.core.atmist import ATMISTFormatter, NineLinerGenerator
        from faer_dev.core.vitals import VitalsGenerator
        from faer_dev.data.injury_loader import InjuryDataLoader

        loader = InjuryDataLoader()
        self._vitals_gen = VitalsGenerator(loader, self._rng)
        self._atmist_formatter = ATMISTFormatter(loader, self._vitals_gen)
        self._nine_liner_gen = NineLinerGenerator()

    # Triage priority ranking (higher = more urgent). Used for
    # promote-only re-triage: new triage accepted only if rank > current.
    _TRIAGE_RANK: Dict[str, int] = {
        "T4": 0, "T3": 1, "T2": 2, "T1_MEDICAL": 3, "T1_SURGICAL": 4,
    }

    @staticmethod
    def _patient_triage_str(patient: Casualty) -> str:
        """Get triage category as string for PFC ceiling lookup."""
        if isinstance(patient.triage, Enum):
            return patient.triage.name
        return str(patient.triage)

    def _retriage_for_deterioration(
        self, patient: Casualty,
    ) -> Optional[TriageCategory]:
        """Re-evaluate triage on PFC ceiling breach (PRD v7.0 §7.4).

        Applies deterioration to severity (patient has exceeded max PFC
        hours), then re-evaluates using BT thresholds. Only promotes
        (returns a higher-priority category) — never demotes.
        Returns None if no promotion warranted.
        """
        current_str = self._patient_triage_str(patient)
        current_rank = self._TRIAGE_RANK.get(current_str, -1)

        # Apply deterioration — patient has been in PFC for max hours
        base_deterioration = 0.20
        if self._injury_loader_for_pfc:
            cmt = bool(patient.metadata.get("cmt_available", False))
            mult = self._injury_loader_for_pfc.get_pfc_deterioration_multiplier(cmt)
        else:
            mult = 0.6  # conservative without loader
        patient.severity_score = min(
            patient.severity_score + base_deterioration * mult, 0.99,
        )

        # Severity-based escalation ladder for PFC ceiling breach.
        sev = patient.severity_score
        if sev > 0.65:
            candidate = TriageCategory.T1_SURGICAL
        elif sev > 0.50:
            candidate = TriageCategory.T1_MEDICAL
        elif sev > 0.35:
            candidate = TriageCategory.T2
        else:
            return None  # T3 or lower — no promotion

        candidate_rank = self._TRIAGE_RANK.get(candidate.name, -1)
        if candidate_rank > current_rank:
            return candidate
        return None

    @staticmethod
    def _is_pfc_active(patient: Casualty) -> bool:
        """True when patient has an open PFC episode."""
        return bool(patient.metadata.get("pfc_active", False))

    def _mark_pfc_started(
        self,
        patient: Casualty,
        facility_id: Optional[str],
        hold_duration_at_trigger: float,
        cmt_available: bool,
    ) -> None:
        """Mark PFC active, persist key metadata, and emit one start event."""
        patient.metadata["pfc_active"] = True
        patient.metadata["pfc_started_at"] = self.env.now
        patient.metadata["cmt_available"] = cmt_available
        self._log_event("PFC_START", patient, facility_id, {
            "hold_duration_at_trigger": hold_duration_at_trigger,
            "cmt_available": cmt_available,
        })

    def _finalize_pfc_if_active(
        self,
        patient: Casualty,
        facility_id: Optional[str],
        reason: Optional[str] = None,
    ) -> None:
        """Close an active PFC episode and release CCP resources."""
        if self._is_pfc_active(patient):
            started_at_raw = patient.metadata.get("pfc_started_at", self.env.now)
            try:
                started_at = float(started_at_raw)
            except (TypeError, ValueError):
                started_at = self.env.now
            details: Dict[str, Any] = {
                "pfc_duration_min": max(0.0, self.env.now - started_at),
            }
            if reason:
                details["reason"] = reason
            self._log_event("PFC_END", patient, facility_id, details)
            patient.metadata["pfc_active"] = False
            patient.metadata.pop("pfc_started_at", None)

        # Discharge is idempotent and acts as a safety net for AT_CCP stragglers.
        if self._ccp is not None:
            self._ccp.discharge(patient)

    def _finalize_active_pfc_patients(self) -> None:
        """Close active PFC episodes when run() ends before journeys do."""
        for patient in list(self.patients.values()):
            if self._is_pfc_active(patient):
                self._finalize_pfc_if_active(
                    patient,
                    patient.current_facility,
                    reason="simulation_end",
                )
            elif self._ccp is not None and patient.state == PatientState.AT_CCP:
                self._ccp.discharge(patient)

    def _casualty_to_dict(self, patient: Casualty) -> Dict[str, Any]:
        """Convert Casualty to dict for ATMIST/NineLiner formatters."""
        triage_name = (
            patient.triage.name
            if isinstance(patient.triage, Enum)
            else str(patient.triage)
        )
        mechanism_name = (
            patient.mechanism.name
            if isinstance(patient.mechanism, Enum)
            else str(patient.mechanism)
        )
        region_name = (
            patient.primary_region.name
            if isinstance(patient.primary_region, Enum)
            else str(patient.primary_region)
        )
        secondary = [
            r.name if isinstance(r, Enum) else str(r)
            for r in (patient.secondary_regions or [])
        ]
        return {
            "id": patient.id,
            "triage": triage_name,
            "mechanism": mechanism_name,
            "primary_region": region_name,
            "secondary_regions": secondary,
            "severity_score": patient.severity_score,
            "is_polytrauma": len(secondary) > 0,
            "arrival_time": patient.arrival_time,
        }

    def _generate_atmist(
        self, patient: Casualty, from_facility: str, to_facility: str
    ) -> None:
        """Generate ATMIST handover report if toggle is enabled."""
        if not self.toggles.enable_atmist or not self._atmist_formatter:
            return
        cas_dict = self._casualty_to_dict(patient)
        # ATMISTFormatter.generate expects events list and handover_number
        existing = patient.metadata.get("atmist_reports", [])
        handover_num = len(existing) + 1
        report = self._atmist_formatter.generate(
            casualty=cas_dict,
            events=[],  # no per-patient event log needed at this stage
            handover_time=self.env.now,
            from_facility=from_facility,
            to_facility=to_facility,
            handover_number=handover_num,
        )
        patient.metadata.setdefault("atmist_reports", []).append(
            report.to_handover_string()
        )
        self._log_event("ATMIST_HANDOVER", patient, from_facility, {
            "handover_number": report.handover_number,
            "from_facility": from_facility,
            "to_facility": to_facility,
        })

    def _generate_nine_liner(
        self, patient: Casualty, from_facility: str, to_facility: str
    ) -> None:
        """Generate 9-liner MEDEVAC request if toggle is enabled."""
        if not self.toggles.enable_atmist or not self._nine_liner_gen:
            return
        cas_dict = self._casualty_to_dict(patient)
        liner = self._nine_liner_gen.generate(
            cas_dict, from_facility, to_facility
        )
        patient.metadata.setdefault("nine_liners", []).append(
            liner.to_string()
        )
        self._log_event("NINE_LINER", patient, from_facility, {
            "from_facility": from_facility,
            "to_facility": to_facility,
        })

    def _log_event(
        self,
        event_type: str,
        patient: Casualty,
        facility: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit event to both legacy dict list and typed EventBus.

        Legacy path: IDENTICAL dict format to Phase 3 — same keys, same values.
        Bus path: typed SimEvent routed through EventBus to EventStore.
        """
        triage_val = (
            patient.triage.name
            if isinstance(patient.triage, Enum)
            else patient.triage
        )
        state_val = (
            patient.state.name
            if isinstance(patient.state, Enum)
            else patient.state
        )
        # === LEGACY PATH (always — backward compat) ===
        self.events.append({
            "time": self.env.now,
            "type": event_type,
            "patient_id": patient.id,
            "triage": triage_val,
            "state": state_val,
            "facility": facility,
            "details": details or {},
        })
        # === BUS PATH (if enabled) ===
        if self.toggles.enable_event_store:
            from faer_dev.events.models import create_event
            typed_event = create_event(
                event_type,
                sim_time=self.env.now,
                casualty_id=patient.id,
                facility_id=facility,
                source="engine",
                triage=triage_val,
                **(details or {}),
            )
            self.event_bus.publish(typed_event)

    def _log_event_raw(
        self,
        event_type: str,
        time: float,
        details: Dict[str, Any],
    ) -> None:
        """Emit system event (no patient) to legacy list and typed EventBus."""
        # === LEGACY PATH (always) ===
        self.events.append({
            "time": time,
            "type": event_type,
            "patient_id": None,
            "triage": None,
            "state": None,
            "facility": None,
            "details": details,
        })
        # === BUS PATH (if enabled) ===
        if self.toggles.enable_event_store:
            from faer_dev.events.models import create_event
            typed_event = create_event(
                event_type,
                sim_time=time,
                source="engine",
                **details,
            )
            self.event_bus.publish(typed_event)

    def _handle_arrival(self, record: ArrivalRecord) -> None:
        """Handle an arrival event — create casualty and start journey."""
        # Feed MASCALDetector for rate-based detection
        self.mascal_detector.record_arrival(record.time)
        was_active = self.mascal_detector.active
        is_now = self.mascal_detector.is_mascal(record.time)
        if is_now and not was_active:
            self._log_event_raw("MASCAL_ACTIVATE", record.time, {
                "arrival_rate": self.mascal_detector.current_rate(record.time),
                "threshold": float(self.mascal_detector.threshold),
                "activation_count": self.mascal_detector.activation_count,
            })
        elif not is_now and was_active:
            self._log_event_raw("MASCAL_DEACTIVATE", record.time, {})

        patient = self.casualty_factory.create(record)
        # Find the POI facility to start the journey
        poi_id = self._poi_id
        if poi_id:
            self.env.process(self._patient_journey(patient, poi_id))

    def _handle_mascal(self, mascal: MASCALEvent) -> None:
        """Record a MASCAL event."""
        self._mascal_events.append(mascal)
        logger.info(
            "MASCAL event at t=%.1f: %d casualties over %.0f min",
            mascal.time,
            mascal.size,
            mascal.duration,
        )

    def _finalize_patient(
        self,
        patient: Casualty,
        facility_id: str,
        outcome: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        """Emit disposition event and move patient to completed list."""
        resolved_outcome = outcome
        if not resolved_outcome:
            if isinstance(patient.state, Enum):
                resolved_outcome = patient.state.name
            else:
                resolved_outcome = str(patient.state)

        details: Dict[str, Any] = {
            "outcome": resolved_outcome,
            "total_time": max(0.0, self.env.now - patient.created_at),
        }
        if reason:
            details["reason"] = reason

        patient.metadata["final_outcome"] = str(resolved_outcome)
        self._log_event("DISPOSITION", patient, facility_id, details)
        self.completed_patients.append(patient)
        self.patients.pop(patient.id, None)

    def _patient_journey(
        self, patient: Casualty, start_facility_id: str
    ):  # type: ignore[return]  # SimPy generator
        """SimPy process: patient's journey through the treatment chain."""
        current_id = start_facility_id
        self.patients[patient.id] = patient

        # Initial triage decisions (toggle-gated extraction)
        if self.toggles.enable_extracted_routing:
            decisions = _extracted_triage_decisions(patient)
        else:
            decisions = _triage_decisions(patient)
        patient.bypass_role1 = decisions["bypass_role1"]
        patient.requires_dcs = decisions["requires_dcs"]

        mechanism = (
            patient.mechanism.name
            if isinstance(patient.mechanism, Enum)
            else str(patient.mechanism or "")
        )
        recommended_triage = decisions["recommended_triage"]
        if isinstance(recommended_triage, Enum):
            recommended_triage = recommended_triage.name
        self._log_event("ARRIVAL", patient, current_id, {
            "injury_mechanism": mechanism,
            "severity": patient.severity_score,
            "recommended_triage": str(recommended_triage),
            "bypass_role1": decisions["bypass_role1"],
            "requires_dcs": decisions["requires_dcs"],
            "priority": decisions["priority"],
        })

        while True:
            current_facility = self.network.facilities[current_id]

            # Determine next destination (toggle-gated extraction)
            if self.toggles.enable_extracted_routing:
                next_id = _extracted_get_next_destination(
                    patient, current_facility, self.network, decisions
                )
            else:
                next_id = _get_next_destination(
                    patient, current_facility, self.network, decisions
                )

            if next_id is None:
                # Journey complete — assign disposition
                if patient.triage == TriageCategory.T4:
                    patient.state = PatientState.DECEASED
                elif patient.triage == TriageCategory.T3:
                    patient.state = PatientState.RTD
                else:
                    patient.state = PatientState.STRATEVAC

                self._finalize_patient(
                    patient,
                    current_id,
                    outcome=patient.state.name,
                )
                break

            # Hold-at-R1: if downstream queue is full, wait and retry
            if (
                current_facility.role == Role.R1
                and next_id in self.queues
            ):
                downstream_q = self.queues[next_id]
                downstream_dept_graph = None
                if self.toggles.enable_department_routing:
                    downstream_dept_graph = self.department_graphs.get(next_id)
                hold_start = self.env.now
                hold_timeout = getattr(self, "_hold_timeout_override", 480.0)
                retry_interval = 15.0  # retry every 15 min
                pfc_threshold = 60.0  # PFC after 60 min hold

                while True:
                    is_full = downstream_q.count >= downstream_q.capacity
                    if (
                        downstream_dept_graph is not None
                        and downstream_dept_graph.is_partitioned
                    ):
                        target_dept = self._resolve_target_department(
                            patient, next_id, downstream_dept_graph, decisions
                        )
                        dept = downstream_dept_graph.get_department(target_dept)
                        if dept and dept.resource is not None:
                            is_full = dept.resource.count >= dept.resource.capacity

                    if not is_full:
                        break

                    held_so_far = self.env.now - hold_start
                    if held_so_far == 0:
                        self._log_event("HOLD_START", patient, current_id, {
                            "downstream_facility": next_id,
                            "constrained_resource": "beds",
                        })

                    if held_so_far >= hold_timeout:
                        self._log_event("HOLD_TIMEOUT", patient, current_id, {
                            "hold_duration_min": held_so_far,
                        })
                        patient.state = PatientState.AWAITING_EVACUATION
                        patient.metadata["hold_timeout"] = True
                        break

                    # PFC trigger: hold > 60 min
                    if (
                        held_so_far >= pfc_threshold
                        and not self._is_pfc_active(patient)
                    ):
                        patient.state = PatientState.IN_PFC
                        cmt_available = self._ccp is not None and not self._ccp.at_capacity

                        # CCP processing (Phase 4 Iter 4)
                        if self._ccp is not None and cmt_available:
                            self._ccp.admit(patient)
                            medic_req = self._ccp.medics.request()
                            result = yield medic_req | self.env.timeout(5)
                            if medic_req in result:
                                cmt_available = True
                                if self._injury_loader_for_pfc:
                                    records = self._ccp.apply_interventions(
                                        patient, self._injury_loader_for_pfc,
                                    )
                                    total_time = sum(r["time_min"] for r in records)
                                    yield self.env.timeout(total_time)
                                self._ccp.medics.release(medic_req)
                            else:
                                cmt_available = False
                                medic_req.cancel()

                        self._mark_pfc_started(
                            patient,
                            current_id,
                            held_so_far,
                            cmt_available,
                        )

                    # PFC ceiling enforcement (PRD v7.0 §7.4)
                    if self._is_pfc_active(patient):
                        started_at_raw = patient.metadata.get(
                            "pfc_started_at", self.env.now,
                        )
                        try:
                            started_at = float(started_at_raw)
                        except (TypeError, ValueError):
                            started_at = self.env.now
                        pfc_hours = max(0.0, (self.env.now - started_at) / 60.0)
                        triage_str = self._patient_triage_str(patient)
                        if self._injury_loader_for_pfc:
                            max_hours = self._injury_loader_for_pfc.get_max_pfc_hours(triage_str)
                        else:
                            max_hours = 24.0
                        if pfc_hours >= max_hours and not patient.metadata.get("pfc_ceiling_fired"):
                            patient.metadata["pfc_ceiling_fired"] = True
                            self._log_event("PFC_CEILING_EXCEEDED", patient, current_id, {
                                "pfc_duration_hours": pfc_hours,
                                "max_hours": max_hours,
                                "triage_at_ceiling": triage_str,
                            })
                            # Re-triage: promote only, never demote (CP4 gate #7)
                            new_triage = self._retriage_for_deterioration(patient)
                            if new_triage is not None:
                                old_triage_str = triage_str
                                patient.triage = new_triage
                                # Recompute target treatment department using
                                # the updated triage before next hold check.
                                patient.metadata.pop("target_department", None)
                                patient.metadata.pop(
                                    "target_department_facility", None,
                                )
                                self._log_event("TRIAGE", patient, current_id, {
                                    "old_triage": old_triage_str,
                                    "new_triage": new_triage.name,
                                    "reason": "deterioration_retriage",
                                })

                    yield self.env.timeout(retry_interval)
                    self._log_event("HOLD_RETRY", patient, current_id, {
                        "hold_duration_min": self.env.now - hold_start,
                    })

                # If timed out, dispose and break
                if patient.state == PatientState.AWAITING_EVACUATION:
                    self._finalize_pfc_if_active(
                        patient, current_id, reason="hold_timeout",
                    )
                    self._finalize_patient(
                        patient,
                        current_id,
                        outcome="HOLD_TIMEOUT",
                        reason="downstream_capacity_timeout",
                    )
                    break

                # End PFC if it was active
                self._finalize_pfc_if_active(
                    patient, current_id, reason="hold_released",
                )

                patient.metadata["hold_minutes"] = self.env.now - hold_start

            # Transit to next facility (via transport pool)
            patient.state = PatientState.IN_TRANSIT
            patient.destination_facility = next_id

            edge = self.network.get_edge(current_id, next_id)
            transport_str = edge.get("transport", "ground")
            mode = resolve_transport_mode(transport_str)
            self._log_event(
                "TRANSIT_START", patient, current_id,
                {
                    "origin": current_id,
                    "destination": next_id,
                    "transport_mode": mode.name.lower(),
                },
            )

            # ATMIST + 9-Liner at handover point
            self._generate_atmist(patient, current_id, next_id)
            self._generate_nine_liner(patient, current_id, next_id)

            if not self.transport_pool.has_capacity(mode):
                logger.warning(
                    "No %s transport capacity configured for patient %s",
                    mode.name.lower(),
                    patient.id,
                )
                patient.state = PatientState.STRATEVAC
                patient.metadata["routing_failure"] = True
                patient.metadata["transport_unavailable"] = mode.name.lower()
                self._log_event(
                    "TRANSIT_END",
                    patient,
                    current_id,
                    {
                        "transit_time": 0.0,
                        "reason": "transport_unavailable",
                    },
                )
                self._finalize_patient(
                    patient,
                    current_id,
                    outcome="TRANSPORT_UNAVAILABLE",
                    reason=f"{mode.name.lower()}_capacity_zero",
                )
                break

            # Missing-edge fallback: check before requesting transport
            travel_time = self.network.get_travel_time(current_id, next_id)
            if travel_time == float("inf"):
                logger.warning(
                    "No direct route %s -> %s for patient %s",
                    current_id, next_id, patient.id,
                )
                patient.state = PatientState.STRATEVAC
                patient.metadata["routing_failure"] = True
                self._log_event(
                    "TRANSIT_END",
                    patient,
                    current_id,
                    {
                        "transit_time": 0.0,
                        "reason": "no_path_to_next_echelon",
                    },
                )
                self._finalize_patient(
                    patient,
                    current_id,
                    outcome="ROUTING_FAILURE",
                    reason="no_path_to_next_echelon",
                )
                break

            # Transport: batched or direct
            request_time = self.transport_pool.record_request(mode)
            batcher = self.transport_pool.get_batcher(mode)

            if batcher is not None:
                # Batched: coordinator manages vehicle sharing
                ready_event = batcher.request_transport(
                    str(patient.id), patient.priority_value,
                )
                yield ready_event
                self.transport_pool.record_pickup(mode, request_time)
                yield self.env.timeout(travel_time)
                self.transport_pool.record_completion(mode, travel_time)
            else:
                # Unbatched: direct resource request with priority
                resource = self.transport_pool.get_resource(mode)
                req = resource.request(priority=patient.priority_value)
                yield req
                self.transport_pool.record_pickup(mode, request_time)
                yield self.env.timeout(travel_time)
                # Vehicle returns asynchronously
                self.env.process(
                    self._vehicle_return(resource, req, mode, travel_time)
                )

            self._log_event(
                "TRANSIT_END",
                patient,
                next_id,
                {"transit_time": travel_time},
            )
            patient.total_transit_time += travel_time

            # Arrive at facility
            current_id = next_id
            patient.current_facility = current_id
            patient.facilities_visited.append(current_id)
            self._log_event("FACILITY_ARRIVAL", patient, current_id)

            # Golden Hour tracking: record first R2 arrival
            arrived_facility = self.network.facilities[current_id]
            if (
                arrived_facility.role == Role.R2
                and "r2_arrival_time" not in patient.metadata
            ):
                gh_minutes = self.env.now - patient.created_at
                patient.metadata["r2_arrival_time"] = self.env.now
                patient.metadata["golden_hour_minutes"] = gh_minutes
                patient.metadata["golden_hour_met"] = gh_minutes <= 60.0

            # Department routing (Phase 3) or single-queue fallback
            dept_graph = self.department_graphs.get(current_id)
            if dept_graph and self.toggles.enable_department_routing:
                yield from self._treat_in_department(
                    patient, current_id, dept_graph, decisions
                )
            elif current_id in self.queues:
                yield from self._treat_in_queue(
                    patient, current_id, arrived_facility.role
                )

    def _resolve_department(
        self,
        patient: Casualty,
        dept_graph: FacilityInternalGraph,
        decisions: Dict[str, Any],
    ) -> str:
        """Pick department name based on triage and clinical decisions."""
        if decisions.get("requires_dcs") and dept_graph.get_department("FST"):
            return "FST"
        if patient.triage in (TriageCategory.T1_SURGICAL, TriageCategory.T1_MEDICAL):
            if dept_graph.get_department("ITU"):
                return "ITU"
            if dept_graph.get_department("FST"):
                return "FST"
        if dept_graph.get_department("ED"):
            return "ED"
        if dept_graph.get_department("DCR"):
            return "DCR"
        return dept_graph.department_names[0] if dept_graph.department_names else "WARD"

    def _resolve_target_department(
        self,
        patient: Casualty,
        facility_id: str,
        dept_graph: FacilityInternalGraph,
        decisions: Dict[str, Any],
    ) -> str:
        """Resolve and cache target department for a specific facility."""
        cached = patient.metadata.get("target_department")
        cached_facility = patient.metadata.get("target_department_facility")
        if (
            isinstance(cached, str)
            and cached_facility == facility_id
            and dept_graph.get_department(cached) is not None
        ):
            return cached

        resolved = self._resolve_department(patient, dept_graph, decisions)
        patient.metadata["target_department"] = resolved
        patient.metadata["target_department_facility"] = facility_id
        return resolved

    def _treat_in_department(
        self,
        patient: Casualty,
        facility_id: str,
        dept_graph: FacilityInternalGraph,
        decisions: Dict[str, Any],
    ):  # type: ignore[return]  # SimPy generator
        """Route patient to a specific department and treat."""
        dept_name = self._resolve_target_department(
            patient, facility_id, dept_graph, decisions
        )
        dept = dept_graph.get_department(dept_name)
        facility = self.network.facilities[facility_id]

        self._log_event(
            f"{facility.role.name}_DEPT", patient, facility_id,
            {"department": dept_name},
        )

        patient.state = PatientState.WAITING
        patient.metadata["department"] = dept_name
        wait_start = self.env.now

        if (
            dept_graph.is_partitioned
            and dept is not None
            and dept.resource is not None
        ):
            with dept.resource.request(priority=patient.priority_value) as req:
                yield req
                wait_time = self.env.now - wait_start
                patient.total_wait_time += wait_time
                if facility_id in self.queues:
                    self.queues[facility_id].wait_times.append(wait_time)

                patient.state = PatientState.IN_TREATMENT
                patient.treatment_started_at = self.env.now
                self._log_event(
                    "TREATMENT_START", patient, facility_id,
                    {"wait_time": wait_time, "department": dept_name},
                )

                triage_key = (
                    patient.triage.name
                    if isinstance(patient.triage, Enum)
                    else patient.triage
                )
                base_time = self.treatment_times.get(
                    facility.role, {}
                ).get(triage_key, 30)
                treatment_time = self._rng.exponential(base_time)
                treatment_time *= patient.treatment_time_modifier

                yield self.env.timeout(treatment_time)
                patient.total_treatment_time += treatment_time

                # Record on both the facility queue and the department.
                if facility_id in self.queues:
                    self.queues[facility_id].patients_treated += 1
                dept.patients_treated = getattr(dept, "patients_treated", 0) + 1

                self._log_event(
                    "TREATMENT_END", patient, facility_id,
                    {"duration": treatment_time, "department": dept_name},
                )
            return

        # Regime B fallback: use shared facility queue capacity while keeping
        # department selection for protocol tracking/event labeling.
        queue = self.queues.get(facility_id)
        if queue is None:
            return

        with queue.resource.request(priority=queue.get_priority(patient)) as req:
            yield req
            wait_time = self.env.now - wait_start
            patient.total_wait_time += wait_time
            queue.wait_times.append(wait_time)

            patient.state = PatientState.IN_TREATMENT
            patient.treatment_started_at = self.env.now
            self._log_event(
                "TREATMENT_START", patient, facility_id,
                {"wait_time": wait_time, "department": dept_name},
            )

            triage_key = (
                patient.triage.name
                if isinstance(patient.triage, Enum)
                else patient.triage
            )
            base_time = self.treatment_times.get(
                facility.role, {}
            ).get(triage_key, 30)
            treatment_time = self._rng.exponential(base_time)
            treatment_time *= patient.treatment_time_modifier

            yield self.env.timeout(treatment_time)
            patient.total_treatment_time += treatment_time
            queue.patients_treated += 1
            if dept is not None:
                dept.patients_treated = getattr(dept, "patients_treated", 0) + 1

            self._log_event(
                "TREATMENT_END", patient, facility_id,
                {"duration": treatment_time, "department": dept_name},
            )

    def _treat_in_queue(
        self,
        patient: Casualty,
        facility_id: str,
        role: Role,
    ):  # type: ignore[return]  # SimPy generator
        """Treat patient using single facility queue (legacy path)."""
        queue = self.queues[facility_id]
        priority = queue.get_priority(patient)

        patient.state = PatientState.WAITING
        queue.record_queue()
        wait_start = self.env.now

        with queue.resource.request(priority=priority) as req:
            yield req

            wait_time = self.env.now - wait_start
            patient.total_wait_time += wait_time
            queue.wait_times.append(wait_time)

            patient.state = PatientState.IN_TREATMENT
            patient.treatment_started_at = self.env.now
            self._log_event(
                "TREATMENT_START", patient, facility_id,
                {"wait_time": wait_time},
            )

            triage_key = (
                patient.triage.name
                if isinstance(patient.triage, Enum)
                else patient.triage
            )
            base_time = self.treatment_times.get(
                role, {}
            ).get(triage_key, 30)
            treatment_time = self._rng.exponential(base_time)
            treatment_time *= patient.treatment_time_modifier

            yield self.env.timeout(treatment_time)
            patient.total_treatment_time += treatment_time
            queue.patients_treated += 1

            self._log_event(
                "TREATMENT_END", patient, facility_id,
                {"duration": treatment_time},
            )

    def _vehicle_return(
        self,
        resource: simpy.PriorityResource,
        req,
        mode,
        outbound_time: float,
    ):  # type: ignore[return]  # SimPy generator
        """SimPy process: vehicle returns to staging area after patient drop-off.

        Models the full post-delivery cycle:
        1. Unload/handoff at destination (part of turnaround)
        2. Return flight/drive to staging area
        3. Refuel/turnaround at staging (part of turnaround)

        The resource stays held until the vehicle is ready for the next mission.
        """
        turnaround = self.transport_pool.config.get_turnaround(mode)

        # Return trip ≈ outbound time with some variance
        return_time = max(
            10.0, self._rng.normal(outbound_time, outbound_time * 0.2)
        )
        # Total unavailable = return flight + turnaround (load/unload/refuel)
        total_downtime = return_time + turnaround
        yield self.env.timeout(total_downtime)
        resource.release(req)
        self.transport_pool.record_completion(
            mode, outbound_time + total_downtime
        )

    def _arrival_process(
        self, poi_id: str, max_arrivals: Optional[int] = None
    ):  # type: ignore[return]  # SimPy generator
        """SimPy process: generate patient arrivals at POI.

        Uses the new ArrivalProcess with callback-driven casualty creation.
        """
        self._poi_id = poi_id
        self.arrival_process = ArrivalProcess(
            env=self.env,
            config=self._arrival_config,
            rng=self._rng,
            on_arrival=self._handle_arrival,
            on_mascal=self._handle_mascal,
        )
        self.arrival_process.start(max_arrivals=max_arrivals)
        # Yield forever — ArrivalProcess manages its own SimPy processes
        yield self.env.timeout(float("inf"))

    def run(
        self,
        duration: float,
        poi_id: Optional[str] = None,
        max_patients: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run the simulation and return metrics.

        Args:
            duration: Simulation duration in minutes.
            poi_id: Facility ID for the point of injury (arrival source).
            max_patients: Lifetime max number of arrivals for this engine instance.
                The arrival process is started once; further run() calls do not
                reset this cap.

        Returns:
            Dictionary of simulation metrics.
        """
        _run_start = _time.monotonic()

        if poi_id is not None:
            if self._arrivals_started and self._poi_id and poi_id != self._poi_id:
                raise ValueError(
                    f"poi_id changed from {self._poi_id!r} to {poi_id!r} after arrivals started"
                )
            self._poi_id = poi_id

        if self._poi_id is None:
            for fid, facility in self.network.facilities.items():
                if facility.role == Role.POI:
                    self._poi_id = fid
                    break

        if self._poi_id and not self._arrivals_started:
            self.arrival_process = ArrivalProcess(
                env=self.env,
                config=self._arrival_config,
                rng=self._rng,
                on_arrival=self._handle_arrival,
                on_mascal=self._handle_mascal,
            )
            self.arrival_process.start(max_arrivals=max_patients)
            self._arrivals_started = True

        if duration > 0:
            self.env.run(until=self.env.now + duration)
        self._finalize_active_pfc_patients()

        # Best-effort run logging — never crashes the simulation
        try:
            from faer_dev.events.run_logger import RunLogEntry
            _run_duration = _time.monotonic() - _run_start
            entry = RunLogEntry.from_engine_run(self, _run_duration)
            self._run_logger.log_run(entry)
        except Exception:
            pass

        return self.get_metrics()

    def step(self, duration: float) -> Dict[str, Any]:
        """Run the simulation for an incremental duration.

        For use with the dashboard to show live progress.
        """
        self.env.run(until=self.env.now + duration)
        return self.get_metrics()

    def get_metrics(self) -> Dict[str, Any]:
        """Collect and return simulation metrics."""
        total_arrivals = sum(1 for e in self.events if e["type"] == "ARRIVAL")

        metrics: Dict[str, Any] = {
            "total_arrivals": total_arrivals,
            "completed": len(self.completed_patients),
            "in_system": len(self.patients),
            "facilities": {},
            "outcomes": {},
        }

        # Transport stats
        metrics["transport"] = self.transport_pool.metrics.to_dict()

        # MASCAL stats
        if self._mascal_events:
            metrics["mascal"] = {
                "events": len(self._mascal_events),
                "total_casualties": sum(m.size for m in self._mascal_events),
            }
        metrics["mascal_detector"] = {
            "activations": self.mascal_detector.activation_count,
            "currently_active": self.mascal_detector.active,
        }

        for fac_id, queue in self.queues.items():
            metrics["facilities"][fac_id] = {
                "treated": queue.patients_treated,
                "avg_wait": (
                    float(np.mean(queue.wait_times))
                    if queue.wait_times
                    else 0.0
                ),
                "max_wait": (
                    float(max(queue.wait_times))
                    if queue.wait_times
                    else 0.0
                ),
                "final_utilization": queue.utilization,
            }

        for patient in self.completed_patients:
            outcome = str(patient.metadata.get("final_outcome", "UNKNOWN"))
            metrics["outcomes"].setdefault(outcome, 0)
            metrics["outcomes"][outcome] += 1

        # Golden Hour metrics
        gh_data = [
            p.metadata["golden_hour_minutes"]
            for p in self.completed_patients
            if "golden_hour_minutes" in p.metadata
        ]
        if gh_data:
            metrics["golden_hour"] = {
                "mean_minutes": float(np.mean(gh_data)),
                "median_minutes": float(np.median(gh_data)),
                "pct_within_60": sum(1 for g in gh_data if g <= 60.0) / len(gh_data),
                "total_tracked": len(gh_data),
            }

        return metrics
