"""Append-only, indexed event store for FAER-M.

In-memory (list-backed). Implements EventStoreProtocol for future
replacement with SQLite or other backend.
"""

from __future__ import annotations

from collections import defaultdict
from typing import List, Optional, Protocol, Set, Tuple, runtime_checkable

from faer_dev.events.models import SimEvent


@runtime_checkable
class EventStoreProtocol(Protocol):
    """Protocol for event store backends.

    Phase 4: in-memory. Phase 5: SQLiteStore implements same protocol.
    """

    def append(self, event: SimEvent) -> None: ...
    def query(self, **kwargs: object) -> List[SimEvent]: ...
    @property
    def count(self) -> int: ...
    def export_xes(self, filepath: str) -> None: ...


class EventStore:
    """Append-only, indexed event store.

    Indexes:
    - by time (sorted list)
    - by casualty_id (dict of lists)
    - by facility_id (dict of lists)
    - by event_type (dict of lists)
    """

    def __init__(self) -> None:
        self._events: List[SimEvent] = []
        self._by_casualty: dict[str, List[SimEvent]] = defaultdict(list)
        self._by_facility: dict[str, List[SimEvent]] = defaultdict(list)
        self._by_type: dict[str, List[SimEvent]] = defaultdict(list)

    def append(self, event: SimEvent) -> None:
        """Append event and update indexes."""
        self._events.append(event)
        if event.casualty_id:
            self._by_casualty[event.casualty_id].append(event)
        if event.facility_id:
            self._by_facility[event.facility_id].append(event)
        self._by_type[event.event_type].append(event)

    @property
    def count(self) -> int:
        """Total number of events in the store."""
        return len(self._events)

    @property
    def event_types(self) -> Set[str]:
        """Set of distinct event types in the store."""
        return set(self._by_type.keys())

    def query(
        self,
        *,
        time_range: Optional[Tuple[float, float]] = None,
        casualty_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> List[SimEvent]:
        """Query with AND logic across filters."""
        results = self._events

        if casualty_id:
            results = self._by_casualty.get(casualty_id, [])
        if facility_id:
            fac_ids = {id(e) for e in self._by_facility.get(facility_id, [])}
            results = [e for e in results if id(e) in fac_ids]
        if event_type:
            type_ids = {id(e) for e in self._by_type.get(event_type, [])}
            results = [e for e in results if id(e) in type_ids]
        if time_range:
            t1, t2 = time_range
            results = [e for e in results if t1 <= e.sim_time <= t2]

        return sorted(results, key=lambda e: e.sim_time)

    def patient_journey(self, casualty_id: str) -> List[SimEvent]:
        """All events for a patient, ordered by time."""
        return sorted(
            self._by_casualty.get(casualty_id, []),
            key=lambda e: e.sim_time,
        )

    def facility_events(self, facility_id: str) -> List[SimEvent]:
        """All events at a facility, ordered by time."""
        return sorted(
            self._by_facility.get(facility_id, []),
            key=lambda e: e.sim_time,
        )

    def events_of_type(self, event_type: str) -> List[SimEvent]:
        """All events of a type, ordered by time."""
        return sorted(
            self._by_type.get(event_type, []),
            key=lambda e: e.sim_time,
        )

    def clear(self) -> None:
        """Remove all events and reset indexes."""
        self._events.clear()
        self._by_casualty.clear()
        self._by_facility.clear()
        self._by_type.clear()

    def export_xes(self, filepath: str) -> None:
        """Export to XES format for PM4Py."""
        from faer_dev.events.xes_exporter import XESExporter
        XESExporter().export(self, filepath)
