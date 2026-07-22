"""PolyhybridEngine — orchestrates SimPy, NetworkX, and py-trees.

Central coordination of patient flow through the treatment chain.
"""

from __future__ import annotations

import logging
import time as _time
from dataclasses import replace
from enum import Enum
from functools import partial
from typing import Any, Dict, List, Optional

import numpy as np
import simpy

from faer_dev.core.enums import OperationalContext, PatientState, Role, TriageCategory
from faer_dev.core.rng import KeyedRNGRoot, RNGPurpose
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
    clinical_destination as _clinical_destination,
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



# K-3 CLOSED: Legacy _triage_decisions() deleted.
# All paths now use routing.triage_decisions (EX-1 proven identical).


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
        replication_index: int = 0,
        patient_seed: Optional[int] = None,
        arrival_weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self.context = context
        # AC-1.1: per-POI shares of the theatre arrival rate. None =
        # every POI draws the whole rate (the single-POI case).
        self._arrival_weights = arrival_weights
        self._rng = np.random.default_rng(seed)
        self.toggles = toggles or SimulationToggles()
        # S2 slice 0: keyed-draw root — replication enters the root entropy
        # or ensemble arms correlate. None in shared mode. S2-D D2:
        # patient_seed roots the identity axis (None = byte-exact no-op).
        self._replication_index = replication_index
        if self.toggles.rng_mode == "keyed":
            self._keyed_rng: Optional[KeyedRNGRoot] = KeyedRNGRoot(
                seed, replication_index, patient_seed=patient_seed
            )
        else:
            self._keyed_rng = None

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

        self._factory_context = context
        self.casualty_factory = self._build_factory()

        # S2 0c-2: eager identity roster (flag-gated; rows appended at
        # creation, trace-neutral — consumes no events, emits none)
        self._roster: Optional[List[Dict[str, Any]]] = (
            [] if self.toggles.enable_roster else None
        )

        # S1.1: facility context writer (direct-call, three write-sites).
        # Shares py_trees' process-global storage with the inverted factory
        # by construction — the set_facility_context None-sentinel protects
        # the factory's mascal_active key (AC-W.2).
        if self.toggles.enable_facility_writer:
            from faer_dev.decisions.blackboard import SimBlackboard
            from faer_dev.simulation.facility_writer import FacilityContextWriter

            if not hasattr(self, "_blackboard"):
                self._blackboard = SimBlackboard(name="engine")
            self._facility_writer = FacilityContextWriter(self)
        else:
            self._facility_writer = None

        # Transport pool
        self._transport_config = transport_config or get_transport_config(context)
        self.transport_pool = TransportPool(
            env=self.env, config=self._transport_config, rng=self._rng,
            keyed_rng=self._keyed_rng,
        )

        # Arrival processes, one per POI (created at run time when the POI
        # set is known). BUILD_S3 slice 2: N instances. At N=1 every legacy
        # form is preserved — bare stream keys, CAS-NNNN uids, int mascal ids.
        self.arrival_processes: Dict[str, ArrivalProcess] = {}
        self._poi_factories: Dict[str, Any] = {}
        self._mascal_events: List[MASCALEvent] = []
        self._poi_id: Optional[str] = None
        self._poi_ids: List[str] = []
        self._arrivals_started = False
        # POIs the builder materialised from an edge endpoint, not declared
        # in the scenario's facilities list (see _arrival_poi_ids).
        self._synthesised_poi_ids: set[str] = set()

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

        # EX-3: TypedEmitter (toggle-gated)
        if self.toggles.enable_typed_emitter:
            from faer_dev.emitter import TypedEmitter
            self._typed_emitter = TypedEmitter(self.events, self.event_bus)
        else:
            self._typed_emitter = None

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

    def add_facility(
        self, facility: Facility, *, synthesised: bool = False
    ) -> None:
        """Add a facility to the network and create its queue.

        ``synthesised`` marks a facility the builder materialised from an
        edge endpoint rather than one the scenario declared — see
        ``_arrival_poi_ids``.
        """
        self.network.add_facility(facility)
        if synthesised and facility.role == Role.POI:
            self._synthesised_poi_ids.add(facility.id)
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
            vitals_rng=(
                self._keyed_rng.draw(patient.id, RNGPurpose.VITALS)
                if self._keyed_rng is not None
                else None
            ),
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

        Toggle-gated (EX-3): when enable_typed_emitter is True, delegates
        to TypedEmitter. When False, runs legacy inline code.
        """
        if self._typed_emitter is not None:
            self._typed_emitter.emit(
                event_type, patient, facility, details, self.env.now,
            )
            return

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
        """Emit system event (no patient) to legacy list and typed EventBus.

        Toggle-gated (EX-3): when enable_typed_emitter is True, delegates
        to TypedEmitter.emit_raw(). When False, runs legacy inline code.
        """
        if self._typed_emitter is not None:
            self._typed_emitter.emit_raw(event_type, time, details)
            return

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

    def _handle_arrival(
        self, record: ArrivalRecord, poi_id: Optional[str] = None
    ) -> None:
        """Handle an arrival event — create casualty and start journey.

        ``poi_id`` is closed over per ArrivalProcess, so a casualty starts
        at the POI that generated it rather than at a shared engine scalar
        — the seam that made a second POI silently starve.
        """
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

        factory = self._poi_factories.get(poi_id) or self.casualty_factory
        patient = factory.create(record)
        if self._keyed_rng is not None:
            # Sellke frailty threshold: eager identity draw, frozen to the
            # roster. Exp(1) races the cumulative deterioration hazard when
            # the Sellke swap lands; the deterioration mechanism itself is
            # untouched at S2 (kickoff rule) — the threshold is inert state.
            patient.metadata["frailty_threshold"] = float(
                self._keyed_rng.draw(
                    patient.id, RNGPurpose.FRAILTY_THRESHOLD
                ).exponential(1.0)
            )
        if self._roster is not None:
            from faer_dev.data.roster import roster_row
            self._roster.append(roster_row(patient))
        # Start the journey at the POI this arrival came from
        start_facility = poi_id or self._poi_id
        if start_facility:
            self.env.process(self._patient_journey(patient, start_facility))

    @property
    def roster(self) -> Optional[List[Dict[str, Any]]]:
        """Eager identity roster rows (None unless enable_roster)."""
        return self._roster

    def write_roster(self, path: str) -> None:
        """Write the roster artefact to parquet (requires the roster extra)."""
        if self._roster is None:
            raise ValueError(
                "Roster recording is off — construct with "
                "SimulationToggles(enable_roster=True)."
            )
        from faer_dev.data.roster import write_roster_parquet
        write_roster_parquet(self._roster, path)

    def _handle_mascal(self, mascal: MASCALEvent) -> None:
        """Record a MASCAL event."""
        self._mascal_events.append(mascal)
        logger.info(
            "MASCAL event at t=%.1f: %d casualties over %.0f min",
            mascal.time,
            mascal.size,
            mascal.duration,
        )

    def _update_facility_congestion(self, facility_id: str) -> None:
        """Recompute and push congestion factor for a facility's inbound edges.

        Factor = current_occupancy / bed_capacity (0.0=empty, >1.0=over).
        Only active when enable_graph_routing is ON.
        """
        if not self.toggles.enable_graph_routing:
            return
        queue = self.queues.get(facility_id)
        if queue is None or queue.capacity == 0:
            return
        factor = queue.count / queue.capacity
        self.network.update_congestion(facility_id, factor)

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
        self._update_facility_congestion(facility_id)
        self.completed_patients.append(patient)
        self.patients.pop(patient.id, None)

    def _recompute_decisions(self, patient: Casualty) -> Dict[str, Any]:
        """The per-journey clinical decisions, recomputed from current state.

        M3 (BUILD_S3 slice 1). ``routing.triage_decisions`` is pure over
        ``patient.triage`` — no RNG, no side effects — so recomputing is
        IDEMPOTENT: the result changes only when the casualty itself changed.
        That is what makes a boundary recompute golden-safe.

        It also heals a real split: the PFC-ceiling promotion site updates the
        ``requires_dcs`` FIELD but neither ``bypass_role1`` nor the loop-local
        decisions DICT, so field and dict could disagree mid-journey.
        """
        decisions = _extracted_triage_decisions(patient)
        patient.bypass_role1 = decisions["bypass_role1"]
        patient.requires_dcs = decisions["requires_dcs"]
        return decisions

    def _is_waypoint_hop(
        self, patient: Casualty, current_facility: Facility,
        decisions: Dict[str, Any], next_id: Optional[str],
    ) -> bool:
        """Is the next hop a WAYPOINT rather than the clinical destination?

        M2, per the signed note's D-A ruling: routing yields a clinical
        DESTINATION, and graph-mode intermediate path nodes are transit
        only. Three conditions, all required:

        1. graph routing is on — only then does a plan have intermediates;
        2. the next hop is not the destination the plan is aimed at;
        3. the scenario has declared that facility waypointable.

        Condition 3 is the continuity floor as configuration. Default False
        everywhere, so every scenario that does not opt in behaves exactly
        as it did before this slice — which is why the golden is inert.
        """
        if next_id is None or not (
            self.toggles.enable_extracted_routing
            and self.toggles.enable_graph_routing
        ):
            return False
        if not self.network.facilities[next_id].waypoint_allowed:
            return False
        destination = _clinical_destination(
            patient, current_facility, self.network, decisions,
            use_capability_routing=self.toggles.enable_capability_routing,
        )
        return destination is not None and next_id != destination

    def _stamp_golden_hour(self, patient: Casualty, facility_id: str) -> None:
        """Write the golden-hour stamp, if this treatment is the one that
        earns it.

        RULED at BUILD_S3 (F3): the stamp is ARRIVAL-TIMED but
        TREATMENT-CONDITIONED — it records the R2 arrival time exactly as
        before, but only when treatment actually starts at that R2. Before
        this, arrival alone stamped it, so routing a casualty THROUGH an R2
        with zero care scored full compliance (measured: golden_hour_met
        True with no treatment at all). Called at treatment start, so a
        casualty still mid-treatment at the run cutoff keeps its stamp.
        """
        pending = patient.metadata.pop("_pending_r2_arrival", None)
        if pending is None or "r2_arrival_time" in patient.metadata:
            return
        if self.network.facilities[facility_id].role != Role.R2:
            return
        patient.metadata["r2_arrival_time"] = pending
        gh_minutes = pending - patient.created_at
        patient.metadata["golden_hour_minutes"] = gh_minutes
        patient.metadata["golden_hour_met"] = gh_minutes <= 60.0

    def _next_destination(
        self, patient: Casualty, current_facility: Facility,
        decisions: Dict[str, Any],
    ) -> Optional[str]:
        """The toggle-gated routing call, in one place so M3 re-decides
        through exactly the same path the leg boundary uses."""
        if self.toggles.enable_extracted_routing:
            return _extracted_get_next_destination(
                patient, current_facility, self.network, decisions,
                use_graph_routing=self.toggles.enable_graph_routing,
                use_capability_routing=self.toggles.enable_capability_routing,
            )
        return _get_next_destination(
            patient, current_facility, self.network, decisions
        )

    def _patient_journey(
        self, patient: Casualty, start_facility_id: str
    ):  # type: ignore[return]  # SimPy generator
        """SimPy process: patient's journey through the treatment chain."""
        current_id = start_facility_id
        self.patients[patient.id] = patient

        # Triage decisions (K-3 closed: always uses extracted routing module)
        decisions = self._recompute_decisions(patient)

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

            # M3: re-decide at every leg boundary. Idempotent unless the
            # casualty changed (promotion/demotion) — see _recompute_decisions.
            decisions = self._recompute_decisions(patient)
            next_id = self._next_destination(patient, current_facility, decisions)
            patient.intended_destination = next_id
            arrived_as_waypoint = self._is_waypoint_hop(
                patient, current_facility, decisions, next_id
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
                        # Honest transient state: the casualty has been
                        # treated here and holds nothing — no bed (released
                        # before the hold begins), no vehicle, no slot at the
                        # destination. IN_TREATMENT was stale. PFC and
                        # timeout still override with their own states.
                        patient.state = PatientState.HOLDING
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
                                # Re-triage invalidates the once-per-journey
                                # requires_dcs (same rule as routing.py:47-50)
                                patient.requires_dcs = (
                                    new_triage == TriageCategory.T1_SURGICAL
                                )
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

                    # M3: the retry boundary is a free re-decision point —
                    # a held casualty holds nothing, so diverting relinquishes
                    # nothing. Idempotent unless the casualty changed.
                    decisions = self._recompute_decisions(patient)
                    replanned = self._next_destination(
                        patient, current_facility, decisions
                    )
                    if replanned is not None and replanned != next_id:
                        # A None recompute means "no destination at all";
                        # completing the committed leg is the safer fallback,
                        # so only a positive re-decision diverts.
                        next_id = replanned
                        patient.intended_destination = next_id
                        if next_id not in self.queues:
                            break  # new destination is not queue-gated
                        downstream_q = self.queues[next_id]
                        downstream_dept_graph = (
                            self.department_graphs.get(next_id)
                            if self.toggles.enable_department_routing else None
                        )

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
                    self._vehicle_return(
                        resource, req, mode, travel_time,
                        casualty_uid=patient.id,
                    )
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
            # M2: the flag is passed ONLY when true, so an opt-out scenario
            # emits exactly the payload it emitted before this slice.
            self._log_event(
                "FACILITY_ARRIVAL", patient, current_id,
                {"waypoint": True} if arrived_as_waypoint else None,
            )
            if self._facility_writer is not None:  # S1.1: waiting changed
                self._facility_writer.update(current_id)
            self._update_facility_congestion(current_id)

            # Golden Hour: remember WHEN this R2 was reached; the stamp is
            # written only if treatment actually starts here (see
            # _stamp_golden_hour). A later R2 overwrites the pending time,
            # so a casualty waypointed through R2-A and treated at R2-B
            # records R2-B's arrival — the ruled definition.
            arrived_facility = self.network.facilities[current_id]
            if (
                arrived_facility.role == Role.R2
                and "r2_arrival_time" not in patient.metadata
            ):
                patient.metadata["_pending_r2_arrival"] = self.env.now

            # Department routing (Phase 3) or single-queue fallback.
            # A waypoint is transit, not reception: no treatment, matching
            # the measured beds=0 signature (TRANSIT_END, FACILITY_ARRIVAL,
            # TRANSIT_START; no TREATMENT_*).
            dept_graph = self.department_graphs.get(current_id)
            if arrived_as_waypoint:
                pass
            elif dept_graph and self.toggles.enable_department_routing:
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
                self._stamp_golden_hour(patient, facility_id)
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
                if self._keyed_rng is not None:
                    treatment_time = self._keyed_rng.draw(
                        patient.id, RNGPurpose.TREATMENT
                    ).exponential(base_time)
                else:
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
            self._stamp_golden_hour(patient, facility_id)
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
            if self._keyed_rng is not None:
                treatment_time = self._keyed_rng.draw(
                    patient.id, RNGPurpose.TREATMENT
                ).exponential(base_time)
            else:
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
            self._stamp_golden_hour(patient, facility_id)
            self._log_event(
                "TREATMENT_START", patient, facility_id,
                {"wait_time": wait_time},
            )
            if self._facility_writer is not None:  # S1.1: bed acquired
                self._facility_writer.update(facility_id)

            triage_key = (
                patient.triage.name
                if isinstance(patient.triage, Enum)
                else patient.triage
            )
            base_time = self.treatment_times.get(
                role, {}
            ).get(triage_key, 30)
            if self._keyed_rng is not None:
                treatment_time = self._keyed_rng.draw(
                    patient.id, RNGPurpose.TREATMENT
                ).exponential(base_time)
            else:
                treatment_time = self._rng.exponential(base_time)
            treatment_time *= patient.treatment_time_modifier

            yield self.env.timeout(treatment_time)
            patient.total_treatment_time += treatment_time
            queue.patients_treated += 1

            self._log_event(
                "TREATMENT_END", patient, facility_id,
                {"duration": treatment_time},
            )
        # S1.1: bed released at context exit — occupancy only reflects the
        # release here, outside the with block
        if self._facility_writer is not None:
            self._facility_writer.update(facility_id)

    def _vehicle_return(
        self,
        resource: simpy.PriorityResource,
        req,
        mode,
        outbound_time: float,
        casualty_uid: Optional[str] = None,
    ):  # type: ignore[return]  # SimPy generator
        """SimPy process: vehicle returns to staging area after patient drop-off.

        Models the full post-delivery cycle:
        1. Unload/handoff at destination (part of turnaround)
        2. Return flight/drive to staging area
        3. Refuel/turnaround at staging (part of turnaround)

        The resource stays held until the vehicle is ready for the next mission.
        """
        turnaround = self.transport_pool.config.get_turnaround(mode)

        # Return trip ≈ outbound time with some variance. Keyed: the return
        # is 1:1 with a patient delivery, so it keys per casualty leg.
        if self._keyed_rng is not None and casualty_uid is not None:
            return_time = max(
                10.0,
                self._keyed_rng.draw(
                    casualty_uid, RNGPurpose.VEHICLE_RETURN
                ).normal(outbound_time, outbound_time * 0.2),
            )
        else:
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

    def _build_factory(self, id_prefix: str = ""):
        """Construct a casualty factory in this engine's configured mode.

        Extracted so multi-POI can build one factory per POI with a distinct
        ``id_prefix``. Prefixes are the ONLY thing that makes N factories
        safe: two unprefixed factories would both emit CAS-0001 and collide
        on the identity key, which is blake2b of the uid string.
        """
        if self.toggles.factory_mode == "inverted":
            return create_factory(
                mode="inverted",
                context=self._factory_context,
                rng=self._rng,
                keyed_rng=self._keyed_rng,
                injury_sampler=self._injury_sampler,
                triage_bt=self._triage_bt,
                blackboard=self._blackboard,
                id_prefix=id_prefix,
                source_id=id_prefix or "default",
            )
        return create_factory(
            mode=self.toggles.factory_mode,
            context=self._factory_context,
            rng=self._rng,
            keyed_rng=self._keyed_rng,
            id_prefix=id_prefix,
        )

    @property
    def arrival_process(self) -> Optional[ArrivalProcess]:
        """The first arrival process — the scalar view, kept for callers
        that predate multi-POI. Use ``arrival_processes`` when N matters."""
        return next(iter(self.arrival_processes.values()), None)

    def close_arrival_window(self) -> None:
        """Freeze each arrival lifetime cap at the count already generated.

        The single seam every drain path uses to stop new arrivals without
        advancing time — one loop over N processes, so callers are unchanged
        from the scalar era.
        """
        for process in self.arrival_processes.values():
            process._max_arrivals = process.count

    def _arrival_poi_ids(self) -> List[str]:
        """Every POI that spawns casualties, in network insertion order.

        Declared POIs win outright: a synthesised POI (materialised by the
        builder from an edge endpoint) is only used when the scenario
        declares none — the slice-0 precedence rule, applied to the whole
        set rather than just the first.
        """
        pois = [
            fid for fid, f in self.network.facilities.items()
            if f.role == Role.POI
        ]
        declared = [p for p in pois if p not in self._synthesised_poi_ids]
        synthesised = [p for p in pois if p in self._synthesised_poi_ids]
        if declared and synthesised:
            logger.warning(
                "Scenario declares POI(s) %s and also synthesises %s from "
                "edge sources; arrivals spawn at the declared set.",
                declared, synthesised,
            )
        return declared or synthesised

    def _arrival_config_for(self, poi_id: str) -> ArrivalConfig:
        """This POI's share of the theatre arrival rate.

        Weights are SHARES, not independent rates (AC-1.1): the theatre
        total is preserved, which keeps MASCAL-detector tuning stable. The
        MASCAL rate inherits the same split. No weight = the whole rate,
        which is what every single-POI scenario gets.
        """
        weight = (self._arrival_weights or {}).get(poi_id)
        if weight is None:
            return self._arrival_config
        return replace(
            self._arrival_config,
            base_rate_per_hour=self._arrival_config.base_rate_per_hour * weight,
            mascal_rate_per_hour=(
                self._arrival_config.mascal_rate_per_hour * weight
            ),
        )

    def _start_arrivals(self, max_patients: Optional[int]) -> None:
        """Bind one ArrivalProcess per POI.

        The asymmetry is deliberate and load-bearing. At N=1 the stream
        scope, the factory id_prefix and the MASCAL id prefix are all None,
        so the run is byte-identical to every digest committed to date. At
        N>=2 all three are set: scoped keys because two instances sharing one
        occurrence ladder destroys CRN pairing (Q11.4, measured), and
        prefixed uids because two factories would otherwise both emit
        CAS-0001 and collide on the identity key.

        ``max_patients`` is a per-POI lifetime cap, not a theatre total.
        """
        poi_ids = [self._poi_id] if self._poi_id else self._arrival_poi_ids()
        if not poi_ids:
            return
        self._poi_ids = poi_ids
        self._poi_id = poi_ids[0]
        plural = len(poi_ids) > 1

        for poi in poi_ids:
            if plural:
                self._poi_factories[poi] = self._build_factory(id_prefix=poi)
            self.arrival_processes[poi] = ArrivalProcess(
                env=self.env,
                config=self._arrival_config_for(poi),
                rng=self._rng,
                on_arrival=partial(self._handle_arrival, poi_id=poi),
                on_mascal=self._handle_mascal,
                keyed_rng=self._keyed_rng,
                stream_scope=poi if plural else None,
                mascal_id_prefix=poi if plural else None,
            )
        for poi in poi_ids:
            self.arrival_processes[poi].start(max_arrivals=max_patients)
        self._arrivals_started = True

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
            available = self._arrival_poi_ids()
            if len(available) > 1:
                raise ValueError(
                    "poi_id override is single-POI only; this scenario "
                    f"declares {len(available)} POIs ({available}). A "
                    "multi-POI scenario spawns at every POI by design — "
                    "pinning one would silently starve the rest."
                )
            if self._arrivals_started and self._poi_id and poi_id != self._poi_id:
                raise ValueError(
                    f"poi_id changed from {self._poi_id!r} to {poi_id!r} after arrivals started"
                )
            self._poi_id = poi_id

        if not self._arrivals_started:
            self._start_arrivals(max_patients)

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
        """Collect and return simulation metrics.

        Toggle-gated: when enable_extracted_metrics is True, delegates to
        metrics.compute_metrics() (EX-2). When False, runs legacy inline code.
        """
        if self.toggles.enable_extracted_metrics:
            from faer_dev.metrics import compute_metrics

            return compute_metrics(
                events=self.events,
                completed_patients=self.completed_patients,
                active_patients=self.patients,
                queues=self.queues,
                transport_pool=self.transport_pool,
                mascal_detector=self.mascal_detector,
                mascal_events=self._mascal_events,
            )

        return self._legacy_get_metrics()

    def _legacy_get_metrics(self) -> Dict[str, Any]:
        """Legacy inline metrics computation (preserved for toggle-off path)."""
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
