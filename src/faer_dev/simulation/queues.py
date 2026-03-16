"""Facility queue management using SimPy.

Extracted from notebooks/06_tribrid_integration.ipynb (cell-10).
Wraps SimPy PriorityResource with metrics collection.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import simpy

from faer_dev.core.enums import TriageCategory
from faer_dev.core.schemas import Casualty, Facility

logger = logging.getLogger(__name__)

# Triage to queue priority mapping (lower = higher priority)
TRIAGE_PRIORITY = {
    TriageCategory.T1_SURGICAL: 1,
    TriageCategory.T1_MEDICAL: 1,
    TriageCategory.T2: 2,
    TriageCategory.T3: 3,
    TriageCategory.T4: 5,
}


class FacilityQueue:
    """SimPy-based queue management for a medical facility.

    Wraps SimPy PriorityResource with metrics collection.
    Priority based on triage category (lower number = higher priority).
    """

    def __init__(self, env: simpy.Environment, facility: Facility) -> None:
        self.env = env
        self.facility = facility
        self.resource = simpy.PriorityResource(env, capacity=facility.beds)

        # Metrics
        self.patients_treated: int = 0
        self.total_wait_time: float = 0.0
        self.wait_times: List[float] = []
        self.queue_history: List[tuple[float, int]] = []

    def get_priority(self, patient: Casualty) -> int:
        """Convert triage category to queue priority."""
        return TRIAGE_PRIORITY.get(patient.triage, 3)

    @property
    def queue_length(self) -> int:
        """Current number of patients waiting."""
        return len(self.resource.queue)

    @property
    def utilization(self) -> float:
        """Current bed utilization (0.0 - 1.0)."""
        if self.resource.capacity == 0:
            return 0.0
        return self.resource.count / self.resource.capacity

    @property
    def count(self) -> int:
        """Number of patients currently occupying treatment capacity."""
        return self.resource.count

    @property
    def capacity(self) -> int:
        """Total treatment capacity for this facility queue."""
        return self.resource.capacity

    def record_queue(self) -> None:
        """Record current queue state for analysis."""
        self.queue_history.append((self.env.now, self.queue_length))


def get_facility_processor(
    facility_id: str,
    queues: Dict[str, FacilityQueue],
    department_graphs: Optional[Dict] = None,
) -> Optional[simpy.PriorityResource]:
    """Return the appropriate SimPy resource for a facility.

    Checks department graphs first (Phase 3 routing), falls back
    to the single FacilityQueue resource (legacy).
    """
    if department_graphs and facility_id in department_graphs:
        graph = department_graphs[facility_id]
        # Return the first department's resource as default
        names = graph.department_names
        if names:
            dept = graph.get_department(names[0])
            if dept and dept.resource:
                return dept.resource
    if facility_id in queues:
        return queues[facility_id].resource
    return None
