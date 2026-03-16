"""Metrics pure aggregation extracted from engine.py (EX-2).

Computes simulation summary from engine data structures.
Zero SimPy dependency. Zero side effects. All inputs passed explicitly.

Extracted from:
  - engine.py::get_metrics() (lines 1286-1347)

Hard Constraints preserved:
  - HC-1: No SimPy imports
  - HC-2: Same inputs → identical output as legacy get_metrics()
  - HC-5: Pure function, testable without engine
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

import numpy as np


# ---------------------------------------------------------------------------
# Protocols — what metrics.py expects from callers
# ---------------------------------------------------------------------------

class QueueProtocol(Protocol):
    """Minimal interface for facility queue metrics."""

    patients_treated: int
    wait_times: List[float]

    @property
    def utilization(self) -> float: ...


class TransportPoolProtocol(Protocol):
    """Minimal interface for transport pool metrics."""

    @property
    def metrics(self) -> Any: ...


class MASCALDetectorProtocol(Protocol):
    """Minimal interface for MASCAL detector metrics."""

    activation_count: int
    active: bool


# ---------------------------------------------------------------------------
# Pure aggregation function — exact replica of engine.get_metrics()
# ---------------------------------------------------------------------------

def compute_metrics(
    events: List[Dict[str, Any]],
    completed_patients: List[Any],
    active_patients: Dict[str, Any],
    queues: Dict[str, QueueProtocol],
    transport_pool: TransportPoolProtocol,
    mascal_detector: MASCALDetectorProtocol,
    mascal_events: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """Compute simulation metrics from engine data.

    Pure aggregation. Reads data, computes stats, returns dict.
    Exact replica of engine.py::get_metrics() — same keys, same values.

    This function has NO access to SimPy env, resources, or generators.
    All required data is passed in explicitly.
    """
    if mascal_events is None:
        mascal_events = []

    total_arrivals = sum(1 for e in events if e["type"] == "ARRIVAL")

    metrics: Dict[str, Any] = {
        "total_arrivals": total_arrivals,
        "completed": len(completed_patients),
        "in_system": len(active_patients),
        "facilities": {},
        "outcomes": {},
    }

    # Transport stats
    metrics["transport"] = transport_pool.metrics.to_dict()

    # MASCAL stats
    if mascal_events:
        metrics["mascal"] = {
            "events": len(mascal_events),
            "total_casualties": sum(m.size for m in mascal_events),
        }
    metrics["mascal_detector"] = {
        "activations": mascal_detector.activation_count,
        "currently_active": mascal_detector.active,
    }

    # Facility stats
    for fac_id, queue in queues.items():
        metrics["facilities"][fac_id] = {
            "treated": queue.patients_treated,
            "avg_wait": (
                float(np.mean(queue.wait_times))
                if queue.wait_times
                else 0.0
            ),
            "max_wait": (
                float(max(queue.wait_times))
                if queue.wait_times
                else 0.0
            ),
            "final_utilization": queue.utilization,
        }

    # Outcome distribution
    for patient in completed_patients:
        outcome = str(patient.metadata.get("final_outcome", "UNKNOWN"))
        metrics["outcomes"].setdefault(outcome, 0)
        metrics["outcomes"][outcome] += 1

    # Golden Hour metrics
    gh_data = [
        p.metadata["golden_hour_minutes"]
        for p in completed_patients
        if "golden_hour_minutes" in p.metadata
    ]
    if gh_data:
        metrics["golden_hour"] = {
            "mean_minutes": float(np.mean(gh_data)),
            "median_minutes": float(np.median(gh_data)),
            "pct_within_60": sum(1 for g in gh_data if g <= 60.0) / len(gh_data),
            "total_tracked": len(gh_data),
        }

    return metrics
