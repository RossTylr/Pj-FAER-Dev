"""AnalyticsEngine — cold-path event subscriber (Pattern E).

Subscribes to EventBus. Never touches SimPy. Never reads engine state.
Materialises views that the dashboard reads via get_view().

Zero SimPy imports. All analytics computed from the typed event stream.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class MaterialisedView(Protocol):
    """Base protocol for analytics views."""

    def update(self, event: Any) -> None: ...

    def snapshot(self) -> Dict[str, Any]: ...

    def reset(self) -> None: ...


class AnalyticsEngine:
    """Cold-path analytics. Subscribes to EventBus. Zero SimPy contact.

    RULES:
    - _on_event() is called synchronously during emit (between yields)
    - View.update() must be O(1) amortised — counter increments, not scans
    - If a view is slow, it will add latency to the hot path
    - For Monte Carlo: call reset_all() between replications
    """

    def __init__(self, event_bus: Any) -> None:
        self._views: Dict[str, MaterialisedView] = {}
        event_bus.subscribe_all(self._on_event)

    def register_view(self, name: str, view: MaterialisedView) -> None:
        """Register a materialised view by name."""
        self._views[name] = view

    def _on_event(self, event: Any) -> None:
        """Dispatch event to all registered views."""
        for view in self._views.values():
            try:
                view.update(event)
            except Exception:
                logger.error(
                    "AnalyticsEngine view failed on %s",
                    getattr(event, "event_type", "?"),
                    exc_info=True,
                )

    def get_view(self, name: str) -> Dict[str, Any]:
        """Return snapshot of a named view."""
        return self._views[name].snapshot()

    def reset_all(self) -> None:
        """Reset all views between Monte Carlo replications."""
        for view in self._views.values():
            view.reset()
