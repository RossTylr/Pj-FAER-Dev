"""Temporal query API for FAER-M event store.

Provides time-windowed queries, patient journey analysis, MASCAL period
detection, and aggregate statistics. Built on top of EventStore indexes.

Phase 4 Iter 3.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from faer_dev.events.models import SimEvent
from faer_dev.events.store import EventStore


class TemporalQuery:
    """Query interface for temporal analysis of simulation events.

    Wraps an EventStore and provides higher-level analytical queries
    beyond the basic CRUD operations on the store itself.

    Usage::

        query = TemporalQuery(engine.event_store)
        journey = query.patient_journey("CAS-001")
        mascal_periods = query.mascal_periods()
        agg = query.aggregate_by_type("ARRIVAL", 0.0, 120.0)
    """

    def __init__(self, store: EventStore) -> None:
        self._store = store

    @property
    def store(self) -> EventStore:
        return self._store

    def patient_journey(self, casualty_id: str) -> List[SimEvent]:
        """All events for a patient, ordered by time."""
        return self._store.patient_journey(casualty_id)

    def patient_journey_between(
        self, casualty_id: str, t1: float, t2: float
    ) -> List[SimEvent]:
        """Patient events within a time window."""
        return self._store.query(casualty_id=casualty_id, time_range=(t1, t2))

    def facility_events_between(
        self, facility_id: str, t1: float, t2: float
    ) -> List[SimEvent]:
        """Facility events within a time window."""
        return self._store.query(facility_id=facility_id, time_range=(t1, t2))

    def events_of_type_between(
        self, event_type: str, t1: float, t2: float
    ) -> List[SimEvent]:
        """Events of a specific type within a time window."""
        return self._store.query(event_type=event_type, time_range=(t1, t2))

    def events_between(self, t1: float, t2: float) -> List[SimEvent]:
        """All events within a time window."""
        return self._store.query(time_range=(t1, t2))

    def mascal_periods(self) -> List[Tuple[float, Optional[float]]]:
        """Detect MASCAL active periods from events.

        Returns list of (start_time, end_time) tuples.
        end_time is None if MASCAL is still active at end of simulation.
        """
        activations = self._store.events_of_type("MASCAL_ACTIVATE")
        deactivations = self._store.events_of_type("MASCAL_DEACTIVATE")

        periods: List[Tuple[float, Optional[float]]] = []
        deact_idx = 0

        for act in activations:
            # Find the next deactivation after this activation
            end_time: Optional[float] = None
            while deact_idx < len(deactivations):
                if deactivations[deact_idx].sim_time >= act.sim_time:
                    end_time = deactivations[deact_idx].sim_time
                    deact_idx += 1
                    break
                deact_idx += 1
            periods.append((act.sim_time, end_time))

        return periods

    def aggregate_by_type(
        self, event_type: str, t1: float, t2: float
    ) -> Dict[str, Any]:
        """Count and basic stats for events of a type within window.

        PRD section 7.4: aggregate_by_type(type, window).

        Returns:
            dict with count, first, last, rate_per_hour
        """
        events = self.events_of_type_between(event_type, t1, t2)
        if not events:
            return {"count": 0, "first": None, "last": None, "rate_per_hour": 0.0}

        window_hours = (t2 - t1) / 60.0
        return {
            "count": len(events),
            "first": events[0].sim_time,
            "last": events[-1].sim_time,
            "rate_per_hour": len(events) / window_hours if window_hours > 0 else 0.0,
        }

    def patient_ids(self) -> List[str]:
        """All unique patient IDs in the store."""
        return sorted(self._store._by_casualty.keys())

    def facility_ids(self) -> List[str]:
        """All unique facility IDs in the store."""
        return sorted(self._store._by_facility.keys())

    def time_range(self) -> Tuple[float, float]:
        """Time range of all events in the store.

        Returns (min_time, max_time). Returns (0.0, 0.0) if empty.
        """
        if not self._store._events:
            return (0.0, 0.0)
        times = [e.sim_time for e in self._store._events]
        return (min(times), max(times))
