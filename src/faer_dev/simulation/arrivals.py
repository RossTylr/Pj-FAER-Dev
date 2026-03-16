"""Poisson and MASCAL arrival processes.

Replaces the original ArrivalGenerator with a process-based approach:
- ArrivalProcess generates arrival events using SimPy
- ArrivalConfig holds context-specific rates
- MASCALEvent/ArrivalRecord are lightweight data records
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Generator, Optional

import numpy as np
import simpy

from faer_dev.core.enums import OperationalContext

logger = logging.getLogger(__name__)


@dataclass
class ArrivalConfig:
    """Configuration for the arrival process."""

    base_rate_per_hour: float = 2.0

    mascal_enabled: bool = True
    mascal_rate_per_hour: float = 0.1
    mascal_size_mean: float = 15.0
    mascal_size_std: float = 5.0
    mascal_size_min: int = 5
    mascal_size_max: int = 30
    mascal_duration_minutes: float = 20.0

    @property
    def base_rate_per_minute(self) -> float:
        return self.base_rate_per_hour / 60.0

    @property
    def mascal_rate_per_minute(self) -> float:
        return self.mascal_rate_per_hour / 60.0


# Context-specific arrival configurations
ARRIVAL_CONFIGS: dict[OperationalContext, ArrivalConfig] = {
    OperationalContext.COIN: ArrivalConfig(
        base_rate_per_hour=1.5,
        mascal_rate_per_hour=0.05,
        mascal_size_mean=10,
        mascal_size_std=3,
    ),
    OperationalContext.LSCO: ArrivalConfig(
        base_rate_per_hour=8.0,
        mascal_rate_per_hour=0.2,
        mascal_size_mean=20,
        mascal_size_std=5,
    ),
    OperationalContext.HADR: ArrivalConfig(
        base_rate_per_hour=15.0,
        mascal_rate_per_hour=0.1,
        mascal_size_mean=25,
        mascal_size_std=8,
    ),
    OperationalContext.SPECOPS: ArrivalConfig(
        base_rate_per_hour=0.5,
        mascal_rate_per_hour=0.02,
        mascal_size_mean=8,
        mascal_size_std=2,
    ),
}


@dataclass
class MASCALEvent:
    """Record of a MASCAL event."""

    time: float
    size: int
    duration: float


@dataclass
class ArrivalRecord:
    """Record of a single arrival."""

    time: float
    is_mascal: bool
    mascal_id: Optional[int] = None


class ArrivalProcess:
    """Combined Poisson + MASCAL arrival generator.

    Uses Neyman-Scott cluster process:
    1. Base arrivals follow Poisson process
    2. MASCAL parent events follow separate Poisson process
    3. Each MASCAL generates a cluster of children
    """

    def __init__(
        self,
        env: simpy.Environment,
        config: ArrivalConfig,
        rng: Optional[np.random.Generator] = None,
        on_arrival: Optional[Callable[[ArrivalRecord], None]] = None,
        on_mascal: Optional[Callable[[MASCALEvent], None]] = None,
    ) -> None:
        self.env = env
        self.config = config
        self.rng = rng or np.random.default_rng()
        self.on_arrival = on_arrival
        self.on_mascal = on_mascal

        self.arrivals: list[ArrivalRecord] = []
        self.mascal_events: list[MASCALEvent] = []
        self._mascal_counter = 0
        self._max_arrivals: Optional[int] = None
        self._started = False

    @property
    def count(self) -> int:
        """Total arrivals generated so far."""
        return len(self.arrivals)

    def start(self, max_arrivals: Optional[int] = None) -> None:
        """Start arrival processes.

        max_arrivals is a lifetime cap for this ArrivalProcess instance.
        """
        if self._started:
            return
        self._started = True
        self._max_arrivals = max_arrivals
        self.env.process(self._base_arrival_process())
        if self.config.mascal_enabled:
            self.env.process(self._mascal_event_process())

    def _base_arrival_process(self) -> Generator:
        """Generate base Poisson arrivals."""
        if self.config.base_rate_per_minute <= 0:
            return

        while self._can_emit():
            inter_arrival = self.rng.exponential(
                1.0 / self.config.base_rate_per_minute
            )
            yield self.env.timeout(inter_arrival)

            if not self._can_emit():
                break

            record = ArrivalRecord(time=self.env.now, is_mascal=False)
            self._emit_arrival(record)

    def _mascal_event_process(self) -> Generator:
        """Generate MASCAL events and their cluster casualties."""
        if self.config.mascal_rate_per_minute <= 0:
            return

        while self._can_emit():
            inter_mascal = self.rng.exponential(
                1.0 / self.config.mascal_rate_per_minute
            )
            yield self.env.timeout(inter_mascal)

            if not self._can_emit():
                break

            mascal = self._generate_mascal_event()
            self.mascal_events.append(mascal)

            if self.on_mascal:
                self.on_mascal(mascal)

            self.env.process(self._mascal_cluster_process(mascal))

    def _generate_mascal_event(self) -> MASCALEvent:
        """Generate a single MASCAL event."""
        size = int(
            self.rng.normal(
                self.config.mascal_size_mean, self.config.mascal_size_std
            )
        )
        size = max(
            self.config.mascal_size_min,
            min(self.config.mascal_size_max, size),
        )
        self._mascal_counter += 1
        return MASCALEvent(
            time=self.env.now,
            size=size,
            duration=self.config.mascal_duration_minutes,
        )

    def _mascal_cluster_process(self, mascal: MASCALEvent) -> Generator:
        """Generate casualties for a MASCAL cluster."""
        mascal_id = self._mascal_counter

        offsets = self.rng.uniform(0, mascal.duration, size=mascal.size)
        offsets.sort()

        current_offset = 0.0
        for offset in offsets:
            if not self._can_emit():
                break
            wait = offset - current_offset
            if wait > 0:
                yield self.env.timeout(wait)
            current_offset = offset

            if not self._can_emit():
                break
            record = ArrivalRecord(
                time=self.env.now, is_mascal=True, mascal_id=mascal_id
            )
            if not self._emit_arrival(record):
                break

    def _can_emit(self) -> bool:
        """Return True when the configured max arrival cap is not reached."""
        return self._max_arrivals is None or self.count < self._max_arrivals

    def _emit_arrival(self, record: ArrivalRecord) -> bool:
        """Record arrival and trigger callback."""
        if not self._can_emit():
            return False
        self.arrivals.append(record)
        if self.on_arrival:
            self.on_arrival(record)
        return True


def get_arrival_config(context: OperationalContext) -> ArrivalConfig:
    """Get arrival configuration for context. PEACEKEEPING falls back to COIN."""
    return ARRIVAL_CONFIGS.get(
        context, ARRIVAL_CONFIGS[OperationalContext.COIN]
    )
