"""MASCAL detection via sliding-window arrival rate monitoring.

Standalone detector — no engine coupling. The engine feeds arrivals
via ``record_arrival()``; BT reads via ``is_mascal()`` / ``current_rate()``.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MASCALDetector:
    """Sliding-window MASCAL event detector.

    Monitors arrival rate and triggers MASCAL when the count within
    ``window_minutes`` exceeds ``threshold``.

    Args:
        window_minutes: Sliding window size (default 15 min).
        threshold: Number of arrivals in window to trigger MASCAL.
        cooldown_minutes: Minimum time after deactivation before
            re-triggering (default 30 min).
    """

    def __init__(
        self,
        window_minutes: float = 15.0,
        threshold: int = 20,
        cooldown_minutes: float = 30.0,
    ):
        self.window_minutes = window_minutes
        self.threshold = threshold
        self.cooldown_minutes = cooldown_minutes
        self._arrival_times: list[float] = []
        self._active = False
        self._last_deactivation: float = -999.0
        self._activations: int = 0

    def record_arrival(self, time: float) -> None:
        """Record an arrival timestamp."""
        self._arrival_times.append(time)

    def _count_recent(self, now: float) -> int:
        """Count arrivals within the sliding window."""
        cutoff = now - self.window_minutes
        return sum(1 for t in self._arrival_times if t >= cutoff)

    def current_rate(self, now: float) -> float:
        """Current arrival rate (per hour) within the window."""
        count = self._count_recent(now)
        hours = self.window_minutes / 60.0
        return count / hours if hours > 0 else 0.0

    def is_mascal(self, now: float) -> bool:
        """Check if MASCAL is currently active."""
        count = self._count_recent(now)

        if count >= self.threshold:
            if not self._active:
                # Check cooldown
                if (now - self._last_deactivation) >= self.cooldown_minutes:
                    self._active = True
                    self._activations += 1
                    logger.info(
                        "MASCAL ACTIVATED at t=%.1f (%d arrivals in %.0f min)",
                        now, count, self.window_minutes,
                    )
        else:
            if self._active:
                self._active = False
                self._last_deactivation = now
                logger.info("MASCAL DEACTIVATED at t=%.1f", now)

        return self._active

    @property
    def active(self) -> bool:
        """Current MASCAL state (without updating)."""
        return self._active

    @property
    def activation_count(self) -> int:
        """Number of times MASCAL has been activated."""
        return self._activations

    @property
    def total_arrivals(self) -> int:
        return len(self._arrival_times)
