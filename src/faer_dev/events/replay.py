"""Replay engine — reconstruct simulation state at any time T.

Processes events from an EventStore to build a snapshot of the simulation
state at a given point in time. Used for debugging, analysis, and timeline
visualisation.

Phase 4 Iter 3. No SimPy dependency — purely event-driven reconstruction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from faer_dev.events.models import SimEvent
from faer_dev.events.store import EventStore


@dataclass
class PatientSnapshot:
    """Snapshot of a single patient's state at time T."""

    casualty_id: str
    triage: str = ""
    state: str = ""
    current_facility: str = ""
    in_transit: bool = False
    in_pfc: bool = False
    events_seen: int = 0


@dataclass
class FacilitySnapshot:
    """Snapshot of a facility's state at time T."""

    facility_id: str
    current_patients: Set[str] = field(default_factory=set)
    total_arrivals: int = 0
    total_departures: int = 0

    @property
    def occupancy(self) -> int:
        return len(self.current_patients)


@dataclass
class SimulationStateSnapshot:
    """Complete simulation state reconstructed at time T.

    Contains all patient states, facility states, and system-level flags.
    """

    target_time: float
    patients: Dict[str, PatientSnapshot] = field(default_factory=dict)
    facilities: Dict[str, FacilitySnapshot] = field(default_factory=dict)
    mascal_active: bool = False
    total_events_processed: int = 0

    @property
    def patient_count(self) -> int:
        return len(self.patients)

    @property
    def active_patients(self) -> List[PatientSnapshot]:
        return [p for p in self.patients.values() if p.state not in ("COMPLETED", "DISPOSITION")]

    @property
    def facility_ids(self) -> Set[str]:
        return set(self.facilities.keys())


class ReplayEngine:
    """Reconstruct simulation state at any time T from event store.

    Usage::

        store = engine.event_store  # after simulation run
        replay = ReplayEngine(store)
        snapshot = replay.replay_to(120.0)  # state at t=120 minutes
        print(snapshot.patient_count, snapshot.mascal_active)
    """

    def __init__(self, store: EventStore) -> None:
        self._store = store

    def replay_to(self, target_time: float) -> SimulationStateSnapshot:
        """Reconstruct state at target_time by replaying events up to that point.

        Events with sim_time <= target_time are applied in order.
        """
        snapshot = SimulationStateSnapshot(target_time=target_time)

        events = self._store.query(time_range=(0.0, target_time))
        for event in events:
            self._apply_event(snapshot, event)

        return snapshot

    def _get_patient(self, snapshot: SimulationStateSnapshot, casualty_id: str) -> PatientSnapshot:
        """Get or create patient snapshot."""
        if casualty_id not in snapshot.patients:
            snapshot.patients[casualty_id] = PatientSnapshot(casualty_id=casualty_id)
        return snapshot.patients[casualty_id]

    def _get_facility(self, snapshot: SimulationStateSnapshot, facility_id: str) -> FacilitySnapshot:
        """Get or create facility snapshot."""
        if facility_id not in snapshot.facilities:
            snapshot.facilities[facility_id] = FacilitySnapshot(facility_id=facility_id)
        return snapshot.facilities[facility_id]

    def _apply_event(self, snapshot: SimulationStateSnapshot, event: SimEvent) -> None:
        """Apply a single event to the snapshot. Dispatch by event_type."""
        snapshot.total_events_processed += 1
        etype = event.event_type

        if etype == "ARRIVAL":
            self._apply_arrival(snapshot, event)
        elif etype == "TRIAGE":
            self._apply_triage(snapshot, event)
        elif etype == "TRANSIT_START":
            self._apply_transit_start(snapshot, event)
        elif etype == "TRANSIT_END":
            self._apply_transit_end(snapshot, event)
        elif etype == "FACILITY_ARRIVAL":
            self._apply_facility_arrival(snapshot, event)
        elif etype == "TREATMENT_START":
            self._apply_treatment_start(snapshot, event)
        elif etype == "TREATMENT_END":
            self._apply_treatment_end(snapshot, event)
        elif etype == "DISPOSITION":
            self._apply_disposition(snapshot, event)
        elif etype == "HOLD_START":
            self._apply_hold_start(snapshot, event)
        elif etype == "PFC_START":
            self._apply_pfc_start(snapshot, event)
        elif etype == "PFC_END":
            self._apply_pfc_end(snapshot, event)
        elif etype == "MASCAL_ACTIVATE":
            snapshot.mascal_active = True
        elif etype == "MASCAL_DEACTIVATE":
            snapshot.mascal_active = False
        elif etype.endswith("_DEPT"):
            self._apply_dept(snapshot, event)
        # Other event types (HOLD_RETRY, HOLD_TIMEOUT, DCS, ATMIST, etc.)
        # don't change patient/facility state — just increment counter
        if event.casualty_id:
            p = self._get_patient(snapshot, event.casualty_id)
            p.events_seen += 1

    def _apply_arrival(self, snapshot: SimulationStateSnapshot, event: SimEvent) -> None:
        if not event.casualty_id:
            return
        p = self._get_patient(snapshot, event.casualty_id)
        p.state = "ARRIVED"
        p.triage = getattr(event, "triage", "") or ""
        if event.facility_id:
            p.current_facility = event.facility_id
            fac = self._get_facility(snapshot, event.facility_id)
            fac.current_patients.add(event.casualty_id)
            fac.total_arrivals += 1

    def _apply_triage(self, snapshot: SimulationStateSnapshot, event: SimEvent) -> None:
        if not event.casualty_id:
            return
        p = self._get_patient(snapshot, event.casualty_id)
        new_triage = getattr(event, "new_triage", "")
        if new_triage:
            p.triage = new_triage

    def _apply_transit_start(self, snapshot: SimulationStateSnapshot, event: SimEvent) -> None:
        if not event.casualty_id:
            return
        p = self._get_patient(snapshot, event.casualty_id)
        p.in_transit = True
        p.state = "IN_TRANSIT"
        # Remove from current facility
        if p.current_facility:
            fac = self._get_facility(snapshot, p.current_facility)
            fac.current_patients.discard(event.casualty_id)
            fac.total_departures += 1
            p.current_facility = ""

    def _apply_transit_end(self, snapshot: SimulationStateSnapshot, event: SimEvent) -> None:
        if not event.casualty_id:
            return
        p = self._get_patient(snapshot, event.casualty_id)
        p.in_transit = False

    def _apply_facility_arrival(self, snapshot: SimulationStateSnapshot, event: SimEvent) -> None:
        if not event.casualty_id:
            return
        p = self._get_patient(snapshot, event.casualty_id)
        p.in_transit = False
        if event.facility_id:
            p.current_facility = event.facility_id
            fac = self._get_facility(snapshot, event.facility_id)
            fac.current_patients.add(event.casualty_id)
            fac.total_arrivals += 1

    def _apply_treatment_start(self, snapshot: SimulationStateSnapshot, event: SimEvent) -> None:
        if not event.casualty_id:
            return
        p = self._get_patient(snapshot, event.casualty_id)
        p.state = "IN_TREATMENT"

    def _apply_treatment_end(self, snapshot: SimulationStateSnapshot, event: SimEvent) -> None:
        if not event.casualty_id:
            return
        p = self._get_patient(snapshot, event.casualty_id)
        p.state = "TREATED"

    def _apply_disposition(self, snapshot: SimulationStateSnapshot, event: SimEvent) -> None:
        if not event.casualty_id:
            return
        p = self._get_patient(snapshot, event.casualty_id)
        p.state = "COMPLETED"
        # Remove from facility
        if p.current_facility:
            fac = self._get_facility(snapshot, p.current_facility)
            fac.current_patients.discard(event.casualty_id)
            fac.total_departures += 1

    def _apply_hold_start(self, snapshot: SimulationStateSnapshot, event: SimEvent) -> None:
        if not event.casualty_id:
            return
        p = self._get_patient(snapshot, event.casualty_id)
        p.state = "ON_HOLD"

    def _apply_pfc_start(self, snapshot: SimulationStateSnapshot, event: SimEvent) -> None:
        if not event.casualty_id:
            return
        p = self._get_patient(snapshot, event.casualty_id)
        p.in_pfc = True
        p.state = "IN_PFC"

    def _apply_pfc_end(self, snapshot: SimulationStateSnapshot, event: SimEvent) -> None:
        if not event.casualty_id:
            return
        p = self._get_patient(snapshot, event.casualty_id)
        p.in_pfc = False

    def _apply_dept(self, snapshot: SimulationStateSnapshot, event: SimEvent) -> None:
        if not event.casualty_id:
            return
        p = self._get_patient(snapshot, event.casualty_id)
        if event.facility_id:
            p.current_facility = event.facility_id
