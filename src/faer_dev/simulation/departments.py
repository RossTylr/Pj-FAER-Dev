"""Facility internal department graph.

Models departments within a treatment facility (DCR, FST, ITU, WARD, ED).
Each department has its own bed count and SimPy PriorityResource.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import simpy


@dataclass
class Department:
    """Single department within a facility."""

    name: str
    beds: int
    resource: Optional[simpy.PriorityResource] = field(
        default=None, repr=False
    )

    @property
    def queue_depth(self) -> int:
        if self.resource is None:
            return 0
        return len(self.resource.queue)

    @property
    def utilisation(self) -> float:
        if self.resource is None or self.resource.capacity == 0:
            return 0.0
        return self.resource.count / self.resource.capacity

    @property
    def beds_available(self) -> int:
        if self.resource is None:
            return self.beds
        return max(0, self.resource.capacity - self.resource.count)


class FacilityInternalGraph:
    """Departments within a single treatment facility.

    Args:
        facility_id: Parent facility identifier.
        env: SimPy environment for resource creation.
        metadata: Optional dict for VOP geospatial data
            (e.g. ``{"lat": ..., "lon": ..., "mgrs": ...}``).
    """

    def __init__(
        self,
        facility_id: str,
        env: simpy.Environment,
        metadata: Optional[dict[str, Any]] = None,
        is_partitioned: bool = True,
        shared_capacity: Optional[int] = None,
    ):
        self.facility_id = facility_id
        self.env = env
        self.departments: dict[str, Department] = {}
        self.metadata = metadata or {}
        self.is_partitioned = is_partitioned
        self.shared_capacity = shared_capacity

    def add_department(
        self,
        name: str,
        beds: int,
        create_resource: bool = True,
    ) -> Department:
        """Add a department with its own PriorityResource."""
        resource = None
        if create_resource:
            resource = simpy.PriorityResource(self.env, capacity=beds)
        dept = Department(name=name, beds=beds, resource=resource)
        self.departments[name] = dept
        return dept

    def get_department(self, name: str) -> Optional[Department]:
        return self.departments.get(name)

    @property
    def total_beds(self) -> int:
        if not self.is_partitioned and self.shared_capacity is not None:
            return self.shared_capacity
        return sum(d.beds for d in self.departments.values())

    @property
    def department_names(self) -> list[str]:
        return list(self.departments.keys())

    def get_queue_depths(self) -> dict[str, int]:
        """Return {dept_key: queue_depth} for blackboard integration."""
        return {
            f"{self.facility_id}.{name}": dept.queue_depth
            for name, dept in self.departments.items()
        }

    def get_capacities(self) -> dict[str, int]:
        """Return {dept_key: capacity} for blackboard integration."""
        return {
            f"{self.facility_id}.{name}": dept.beds
            for name, dept in self.departments.items()
        }

    def get_utilisation(self) -> float:
        """Overall facility utilisation (0.0-1.0)."""
        total_cap = self.total_beds
        if total_cap == 0:
            return 0.0
        total_used = sum(
            d.resource.count for d in self.departments.values()
            if d.resource is not None
        )
        return total_used / total_cap


# ── Builders ───────────────────────────────────────────────────


def build_r1(
    env: simpy.Environment,
    facility_id: str,
    config: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
    total_beds: Optional[int] = None,
) -> FacilityInternalGraph:
    """Build standard R1 internal graph: DCR + WARD.

    Args:
        config: Optional bed count overrides, e.g.
            ``{"DCR": 3, "WARD": 4}``.
        metadata: VOP geospatial data passed through to graph.
    """
    return _build_by_regime(
        env=env,
        facility_id=facility_id,
        defaults=[("DCR", 2), ("WARD", 4)],
        config=config,
        metadata=metadata,
        total_beds=total_beds,
    )


def build_r2(
    env: simpy.Environment,
    facility_id: str,
    config: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
    total_beds: Optional[int] = None,
) -> FacilityInternalGraph:
    """Build standard R2 internal graph: ED + FST + ITU + WARD.

    Args:
        config: Optional bed count overrides.
        metadata: VOP geospatial data passed through to graph.
    """
    return _build_by_regime(
        env=env,
        facility_id=facility_id,
        defaults=[("ED", 4), ("FST", 2), ("ITU", 2), ("WARD", 8)],
        config=config,
        metadata=metadata,
        total_beds=total_beds,
    )


def build_r3(
    env: simpy.Environment,
    facility_id: str,
    config: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
    total_beds: Optional[int] = None,
) -> FacilityInternalGraph:
    """Build standard R3 internal graph: ED + FST + ITU + HDU + WARD."""
    return _build_by_regime(
        env=env,
        facility_id=facility_id,
        defaults=[("ED", 6), ("FST", 4), ("ITU", 4), ("HDU", 4), ("WARD", 20)],
        config=config,
        metadata=metadata,
        total_beds=total_beds,
    )


def _allocate_partitioned_beds(
    weighted_defaults: list[tuple[str, int]],
    total_beds: int,
) -> dict[str, int]:
    """Allocate beds proportionally with exact-sum enforcement.

    Guarantees:
    - at least one bed per department
    - sum(allocated) == total_beds
    """
    names = [name for name, _ in weighted_defaults]
    weights = {name: max(1, beds) for name, beds in weighted_defaults}

    # Minimum guarantee: one bed per department.
    allocated = {name: 1 for name in names}
    remaining = max(0, total_beds - len(names))
    if remaining == 0:
        return allocated

    total_weight = sum(weights.values())
    if total_weight <= 0:
        # Defensive fallback if weights are malformed.
        max_name = names[-1]
    else:
        max_name = max(weights, key=lambda key: weights[key])

    # Allocate proportionally to all but the largest-weight department.
    # The largest-weight department absorbs remainder to enforce exact sum.
    for name in names:
        if name == max_name:
            continue
        share = int(remaining * (weights[name] / total_weight))
        allocated[name] += share

    allocated[max_name] = total_beds - sum(
        beds for name, beds in allocated.items() if name != max_name
    )
    return allocated


def _build_by_regime(
    env: simpy.Environment,
    facility_id: str,
    defaults: list[tuple[str, int]],
    config: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
    total_beds: Optional[int] = None,
) -> FacilityInternalGraph:
    """Build facility graph using regime A/B/C capacity contract."""
    cfg = config or {}
    configured_defaults = [(name, int(cfg.get(name, beds))) for name, beds in defaults]
    department_count = len(configured_defaults)

    # Backward compatibility path: preserve historical defaults exactly.
    if total_beds is None:
        graph = FacilityInternalGraph(
            facility_id, env, metadata=metadata, is_partitioned=True
        )
        for name, beds in configured_defaults:
            graph.add_department(name, beds, create_resource=True)
        return graph

    # Regime C: no treatment capacity.
    if total_beds <= 0:
        graph = FacilityInternalGraph(
            facility_id,
            env,
            metadata=metadata,
            is_partitioned=False,
            shared_capacity=0,
        )
        for name, _ in configured_defaults:
            graph.add_department(name, 0, create_resource=False)
        return graph

    # Regime B: logical department routing with facility-level shared capacity.
    if total_beds < department_count:
        graph = FacilityInternalGraph(
            facility_id,
            env,
            metadata=metadata,
            is_partitioned=False,
            shared_capacity=total_beds,
        )
        for name, _ in configured_defaults:
            graph.add_department(name, 0, create_resource=False)
        return graph

    # Regime A: partitioned department capacity constrained by facility beds.
    allocations = _allocate_partitioned_beds(configured_defaults, total_beds)
    graph = FacilityInternalGraph(
        facility_id, env, metadata=metadata, is_partitioned=True
    )
    for name, _ in configured_defaults:
        graph.add_department(name, allocations[name], create_resource=True)
    return graph
