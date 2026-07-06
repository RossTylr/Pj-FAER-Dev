"""FacilityContextWriter — engine → blackboard facility-state push (S1.1).

Direct-call shape, NOT an EventBus subscriber: the bus logs-but-swallows
subscriber exceptions (bus.py:62-80) and fires after the routing decision,
so a bus-attached writer could degrade quietly and its ordering would be
undefined. Direct calls from the engine's three write-sites keep the
determinism story trivial.

Contract note (durable, for #42/#53): ``facility_beds_available`` is the
per-facility dict consumers should build against. The global scalar pair
(``facility_utilisation``, ``fst_queue_depth``) means "the facility whose
context was most recently set" — coherent for per-decision consumers
(#4's eventual shape), incoherent as a multi-facility view.
"""

from __future__ import annotations


class FacilityContextWriter:
    """Pushes live facility queue state onto the engine's SimBlackboard.

    Holds an engine reference and reads the live ``FacilityQueue`` counters
    (count/capacity/queue_length) at each ``update`` — no state of its own,
    no RNG consumption, no event emission.
    """

    def __init__(self, engine) -> None:
        self._engine = engine

    def update(self, facility_id: str) -> None:
        """Refresh the blackboard facility keys from one facility's live state."""
        queue = self._engine.queues.get(facility_id)
        if queue is None:
            return
        capacity = queue.capacity
        utilisation = queue.count / capacity if capacity else 0.0
        board = self._engine._blackboard
        board.set_facility_context(
            utilisation=utilisation, fst_queue=queue.queue_length,
        )
        beds = dict(board.get("facility_beds_available"))
        beds[facility_id] = capacity - queue.count
        board.set("facility_beds_available", beds)
