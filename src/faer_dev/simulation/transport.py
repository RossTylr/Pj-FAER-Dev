"""Transport resource pools.

Models helicopters, ambulances, and fixed-wing aircraft as shared
SimPy Resources with capacity limits. When demand exceeds capacity,
patients queue for transport.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Generator, Optional

import numpy as np
import simpy

from faer_dev.core.enums import OperationalContext, TransportMode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class TransportConfig:
    """Transport resource configuration."""

    helicopters: int = 2
    ambulances: int = 6
    aircraft: int = 1

    rotary_time_mean: float = 60.0
    rotary_time_std: float = 15.0
    ground_time_mean: float = 90.0
    ground_time_std: float = 30.0
    fixed_wing_time_mean: float = 240.0
    fixed_wing_time_std: float = 60.0

    rotary_patient_capacity: int = 2
    ground_patient_capacity: int = 1
    fixed_wing_patient_capacity: int = 6

    # Turnaround: load + unload + refuel/crew time (minutes per mission)
    rotary_turnaround: float = 30.0   # land, load, unload, refuel
    ground_turnaround: float = 10.0   # load/unload at each end
    fixed_wing_turnaround: float = 45.0  # taxi, load, unload, refuel

    # Batching parameters
    batch_wait_minutes: float = 10.0   # Max wait for batch to fill
    batch_enabled: bool = True         # Toggle batching on/off

    def get_patient_capacity(self, mode: TransportMode) -> int:
        """Get patient capacity per vehicle for mode."""
        return {
            TransportMode.ROTARY: self.rotary_patient_capacity,
            TransportMode.GROUND: self.ground_patient_capacity,
            TransportMode.FIXED_WING: self.fixed_wing_patient_capacity,
        }.get(mode, 1)

    def get_turnaround(self, mode: TransportMode) -> float:
        """Get ground turnaround time for mode (minutes)."""
        return {
            TransportMode.ROTARY: self.rotary_turnaround,
            TransportMode.GROUND: self.ground_turnaround,
            TransportMode.FIXED_WING: self.fixed_wing_turnaround,
        }.get(mode, 10.0)

    def get_capacity(self, mode: TransportMode) -> int:
        """Get vehicle count for mode."""
        return {
            TransportMode.ROTARY: self.helicopters,
            TransportMode.GROUND: self.ambulances,
            TransportMode.FIXED_WING: self.aircraft,
        }.get(mode, 0)

    def get_round_trip_params(self, mode: TransportMode) -> tuple[float, float]:
        """Get (mean, std) for round-trip time."""
        return {
            TransportMode.ROTARY: (self.rotary_time_mean, self.rotary_time_std),
            TransportMode.GROUND: (self.ground_time_mean, self.ground_time_std),
            TransportMode.FIXED_WING: (self.fixed_wing_time_mean, self.fixed_wing_time_std),
        }.get(mode, (60.0, 15.0))


TRANSPORT_CONFIGS: dict[OperationalContext, TransportConfig] = {
    OperationalContext.COIN: TransportConfig(
        helicopters=2, ambulances=6, aircraft=1,
        rotary_time_mean=45.0, ground_time_mean=60.0,
    ),
    OperationalContext.LSCO: TransportConfig(
        helicopters=4, ambulances=8, aircraft=2,
        rotary_time_mean=60.0, ground_time_mean=90.0,
    ),
    OperationalContext.HADR: TransportConfig(
        helicopters=6, ambulances=12, aircraft=2,
        rotary_time_mean=45.0, ground_time_mean=60.0,
    ),
    OperationalContext.SPECOPS: TransportConfig(
        helicopters=1, ambulances=2, aircraft=1,
        rotary_time_mean=90.0, ground_time_mean=120.0,
    ),
}

# Case-insensitive string -> TransportMode mapping
TRANSPORT_MODE_MAP: dict[str, TransportMode] = {
    "ground": TransportMode.GROUND,
    "rotary": TransportMode.ROTARY,
    "helo": TransportMode.ROTARY,
    "helicopter": TransportMode.ROTARY,
    "fixed_wing": TransportMode.FIXED_WING,
    "aircraft": TransportMode.FIXED_WING,
}


def get_transport_config(context: OperationalContext) -> TransportConfig:
    """Get transport configuration for context. PEACEKEEPING falls back to COIN."""
    return TRANSPORT_CONFIGS.get(
        context, TRANSPORT_CONFIGS[OperationalContext.COIN]
    )


def resolve_transport_mode(transport_str: str) -> TransportMode:
    """Map a transport string to TransportMode enum (case-insensitive)."""
    return TRANSPORT_MODE_MAP.get(transport_str.lower(), TransportMode.GROUND)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@dataclass
class TransportModeMetrics:
    """Metrics for a single transport mode."""

    requests: int = 0
    completions: int = 0
    total_wait_time: float = 0.0
    total_trip_time: float = 0.0
    max_queue_depth: int = 0
    queue_samples: list[tuple[float, int]] = field(default_factory=list)

    @property
    def mean_wait_time(self) -> float:
        return self.total_wait_time / self.requests if self.requests > 0 else 0.0

    @property
    def mean_trip_time(self) -> float:
        return self.total_trip_time / self.completions if self.completions > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "requests": self.requests,
            "completions": self.completions,
            "mean_wait_time": self.mean_wait_time,
            "mean_trip_time": self.mean_trip_time,
            "max_queue_depth": self.max_queue_depth,
        }


@dataclass
class TransportMetrics:
    """Aggregate metrics for all transport modes."""

    rotary: TransportModeMetrics = field(default_factory=TransportModeMetrics)
    ground: TransportModeMetrics = field(default_factory=TransportModeMetrics)
    fixed_wing: TransportModeMetrics = field(default_factory=TransportModeMetrics)

    def get_mode_metrics(self, mode: TransportMode) -> TransportModeMetrics:
        return {
            TransportMode.ROTARY: self.rotary,
            TransportMode.GROUND: self.ground,
            TransportMode.FIXED_WING: self.fixed_wing,
        }[mode]

    def to_dict(self) -> dict:
        return {
            "rotary": self.rotary.to_dict(),
            "ground": self.ground.to_dict(),
            "fixed_wing": self.fixed_wing.to_dict(),
        }


# ---------------------------------------------------------------------------
# Transport Pool
# ---------------------------------------------------------------------------

class TransportPool:
    """Shared transport resources across the network.

    Manages helicopters, ambulances, and aircraft as SimPy Resources.
    Tracks queue depths, wait times, and utilization.
    """

    def __init__(
        self,
        env: simpy.Environment,
        config: TransportConfig,
        rng: Optional[np.random.Generator] = None,
    ) -> None:
        self.env = env
        self.config = config
        self.rng = rng or np.random.default_rng()

        self._configured_capacity: dict[TransportMode, int] = {
            TransportMode.ROTARY: config.helicopters,
            TransportMode.GROUND: config.ambulances,
            TransportMode.FIXED_WING: config.aircraft,
        }
        self._resources: dict[TransportMode, simpy.PriorityResource] = {
            # SimPy resources must have capacity > 0. For configured zero modes
            # we keep an internal placeholder resource and gate usage via has_capacity().
            TransportMode.ROTARY: simpy.PriorityResource(
                env, capacity=max(1, config.helicopters),
            ),
            TransportMode.GROUND: simpy.PriorityResource(
                env, capacity=max(1, config.ambulances),
            ),
            TransportMode.FIXED_WING: simpy.PriorityResource(
                env, capacity=max(1, config.aircraft),
            ),
        }

        self.metrics = TransportMetrics()

        # Batch coordinators (only for modes with capacity > 1)
        self._batchers: dict[TransportMode, Optional[BatchCoordinator]] = {}
        if config.batch_enabled:
            for mode in TransportMode:
                if not self.has_capacity(mode):
                    self._batchers[mode] = None
                    continue
                cap = config.get_patient_capacity(mode)
                if cap > 1:
                    self._batchers[mode] = BatchCoordinator(
                        env=env,
                        resource=self._resources[mode],
                        capacity=cap,
                        batch_wait=config.batch_wait_minutes,
                        trip_time_fn=lambda m=mode: self.sample_trip_time(m),
                    )
                else:
                    self._batchers[mode] = None
        else:
            for mode in TransportMode:
                self._batchers[mode] = None

        if any(cap > 0 for cap in self._configured_capacity.values()):
            env.process(self._monitor_queues())

    def get_resource(self, mode: TransportMode) -> simpy.PriorityResource:
        """Get SimPy resource for transport mode."""
        return self._resources[mode]

    def has_capacity(self, mode: TransportMode) -> bool:
        """True when transport mode has at least one configured vehicle."""
        return self._configured_capacity.get(mode, 0) > 0

    def get_batcher(self, mode: TransportMode) -> Optional["BatchCoordinator"]:
        """Get batch coordinator for mode, or None if no batching."""
        return self._batchers.get(mode)

    def uses_batching(self, mode: TransportMode) -> bool:
        """Check if mode uses batching."""
        return self._batchers.get(mode) is not None

    def record_request(self, mode: TransportMode) -> float:
        """Record transport request. Returns request time."""
        metrics = self.metrics.get_mode_metrics(mode)
        metrics.requests += 1
        current_queue = self.get_queue_depth(mode)
        metrics.max_queue_depth = max(metrics.max_queue_depth, current_queue)
        return self.env.now

    def record_pickup(self, mode: TransportMode, request_time: float) -> None:
        """Record transport pickup (patient got a vehicle)."""
        wait_time = self.env.now - request_time
        metrics = self.metrics.get_mode_metrics(mode)
        metrics.total_wait_time += wait_time

    def record_completion(self, mode: TransportMode, trip_time: float) -> None:
        """Record transport completion."""
        metrics = self.metrics.get_mode_metrics(mode)
        metrics.completions += 1
        metrics.total_trip_time += trip_time

    def sample_trip_time(self, mode: TransportMode) -> float:
        """Sample round-trip time for transport mode (minimum 10 min)."""
        mean, std = self.config.get_round_trip_params(mode)
        trip_time = self.rng.normal(mean, std)
        return max(10.0, trip_time)

    def get_queue_depth(self, mode: TransportMode) -> int:
        """Get current queue depth for transport mode."""
        if not self.has_capacity(mode):
            return 0
        return len(self._resources[mode].queue)

    def get_utilization(self, mode: TransportMode) -> float:
        """Get current utilization (0-1) for transport mode."""
        if not self.has_capacity(mode):
            return 0.0
        resource = self._resources[mode]
        if resource.capacity == 0:
            return 0.0
        return resource.count / resource.capacity

    def get_available(self, mode: TransportMode) -> int:
        """Get number of available vehicles."""
        if not self.has_capacity(mode):
            return 0
        resource = self._resources[mode]
        return resource.capacity - resource.count

    def _monitor_queues(self, interval: float = 5.0) -> Generator:
        """Monitor queue depths for metrics/visualization."""
        while True:
            yield self.env.timeout(interval)
            for mode in TransportMode:
                metrics = self.metrics.get_mode_metrics(mode)
                depth = self.get_queue_depth(mode)
                metrics.queue_samples.append((self.env.now, depth))

    def get_status(self) -> dict:
        """Get current status of all transport modes."""
        return {
            mode.name.lower(): {
                "capacity": self._configured_capacity.get(mode, 0),
                "in_use": self._resources[mode].count,
                "available": self.get_available(mode),
                "queue_depth": self.get_queue_depth(mode),
                "utilization": self.get_utilization(mode),
            }
            for mode in TransportMode
        }


# ---------------------------------------------------------------------------
# Batch Coordinator
# ---------------------------------------------------------------------------

@dataclass
class BatchSlot:
    """A pending patient waiting for a batch to depart."""

    patient_id: str
    priority: int
    ready_event: simpy.Event
    trip_time: float = 0.0


class BatchCoordinator:
    """Coordinates patient batching for multi-capacity vehicles.

    Collects patients waiting for the same transport mode and dispatches
    them together when the batch is full or a timeout expires.
    T1 patients (priority <= 200) trigger immediate dispatch.
    """

    def __init__(
        self,
        env: simpy.Environment,
        resource: simpy.PriorityResource,
        capacity: int,
        batch_wait: float,
        trip_time_fn: callable,
    ):
        self.env = env
        self.resource = resource
        self.capacity = capacity
        self.batch_wait = batch_wait
        self.trip_time_fn = trip_time_fn

        self._pending: list[BatchSlot] = []
        self._batch_timer_active = False

    def request_transport(self, patient_id: str, priority: int) -> simpy.Event:
        """Request transport for a patient. Returns event that fires on departure.

        The event's value is the trip_time shared by all batch members.
        """
        ready_event = self.env.event()
        slot = BatchSlot(
            patient_id=patient_id,
            priority=priority,
            ready_event=ready_event,
        )
        self._pending.append(slot)

        # T1 patients trigger immediate dispatch
        if priority <= 200:
            self.env.process(self._dispatch_batch())
            return ready_event

        # Start batch timer if not already running
        if not self._batch_timer_active:
            self.env.process(self._batch_timer())

        # If batch is full, dispatch immediately
        if len(self._pending) >= self.capacity:
            self.env.process(self._dispatch_batch())

        return ready_event

    def _batch_timer(self) -> Generator:
        """Timer that dispatches partial batch after wait period."""
        self._batch_timer_active = True
        yield self.env.timeout(self.batch_wait)
        self._batch_timer_active = False

        if self._pending:
            self.env.process(self._dispatch_batch())

    def _dispatch_batch(self) -> Generator:
        """Dispatch a batch: claim one vehicle, send up to capacity patients."""
        if not self._pending:
            return

        # Take up to capacity patients, sorted by priority (best first)
        self._pending.sort(key=lambda s: s.priority)
        batch = self._pending[:self.capacity]
        self._pending = self._pending[self.capacity:]

        # Claim one vehicle using best priority in batch
        best_priority = batch[0].priority

        with self.resource.request(priority=best_priority) as req:
            yield req

            # Vehicle acquired — sample trip time once for entire batch
            trip_time = self.trip_time_fn()

            # Notify all patients in batch
            for slot in batch:
                slot.trip_time = trip_time
                if not slot.ready_event.triggered:
                    slot.ready_event.succeed(value=trip_time)

            # Vehicle occupied for round-trip
            yield self.env.timeout(trip_time)

        # If more patients pending, start next batch
        if self._pending and not self._batch_timer_active:
            self.env.process(self._batch_timer())

    @property
    def pending_count(self) -> int:
        """Number of patients waiting for a batch."""
        return len(self._pending)


def transport_patient(
    env: simpy.Environment,
    pool: TransportPool,
    mode: TransportMode,
    priority: int = 500,
) -> Generator:
    """Transport a patient using the pool.

    Standalone SimPy generator for transporting a patient.
    Yields SimPy events; returns (wait_time, trip_time) tuple.

    Args:
        priority: Triage priority (lower = more urgent). Use casualty.priority_value.
    """
    request_time = pool.record_request(mode)

    resource = pool.get_resource(mode)
    with resource.request(priority=priority) as req:
        yield req

        wait_time = env.now - request_time
        pool.record_pickup(mode, request_time)

        trip_time = pool.sample_trip_time(mode)
        yield env.timeout(trip_time)

        pool.record_completion(mode, trip_time)

    return (wait_time, trip_time)
