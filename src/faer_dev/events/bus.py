"""Thin synchronous pub/sub EventBus for FAER-M.

Decouples event producers (engine, BT observer) from consumers
(EventStore, future Phase 5/6 subscribers).

Synchronous: subscribers execute immediately during SimPy step.
This preserves deterministic replay (same seed = identical event sequence).
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Callable, Dict, List

from faer_dev.events.models import SimEvent

EventSubscriber = Callable[[SimEvent], None]
logger = logging.getLogger(__name__)


class EventBus:
    """Synchronous pub/sub bus.

    Phase 4: single subscriber (EventStore).
    Phase 5+: additional subscribers (ConsumableManager, FacilityAgent, etc).
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[EventSubscriber]] = {}
        self._wildcard_subscribers: List[EventSubscriber] = []
        self._pending_events: deque[SimEvent] = deque()
        self._is_publishing = False

    def subscribe(self, event_type: str, callback: EventSubscriber) -> None:
        """Subscribe to events of a specific type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def subscribe_all(self, callback: EventSubscriber) -> None:
        """Subscribe to ALL event types (wildcard)."""
        self._wildcard_subscribers.append(callback)

    def publish(self, event: SimEvent) -> None:
        """Publish event to all matching subscribers. Synchronous.

        Re-entrant publishes are queued and processed after the current
        event's subscriber pass completes, preserving deterministic order.
        """
        self._pending_events.append(event)
        if self._is_publishing:
            return

        self._is_publishing = True
        try:
            while self._pending_events:
                current = self._pending_events.popleft()
                wildcard = list(self._wildcard_subscribers)
                typed = list(self._subscribers.get(current.event_type, []))

                for cb in wildcard:
                    try:
                        cb(current)
                    except Exception:
                        logger.error(
                            "EventBus wildcard subscriber failed on %s",
                            current.event_type,
                            exc_info=True,
                        )

                for cb in typed:
                    try:
                        cb(current)
                    except Exception:
                        logger.error(
                            "EventBus subscriber failed for %s",
                            current.event_type,
                            exc_info=True,
                        )
        finally:
            self._is_publishing = False

    def clear(self) -> None:
        """Remove all subscribers."""
        self._subscribers.clear()
        self._wildcard_subscribers.clear()

    @property
    def subscriber_count(self) -> int:
        """Total number of subscriber registrations."""
        typed = sum(len(v) for v in self._subscribers.values())
        return typed + len(self._wildcard_subscribers)
