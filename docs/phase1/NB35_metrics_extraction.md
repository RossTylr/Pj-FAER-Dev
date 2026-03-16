# NB35: EX-2 Metrics Extraction Proof
## Claude Code Instruction File

---

## Objective

Extract `get_metrics()` (~62 LOC) from `engine.py` into a standalone
`metrics.py` module. This is a read-only aggregation function over the
EventStore that has zero interaction with SimPy yields.

## What You're Extracting

From `engine.py`, identify and extract:

1. **`get_metrics()` or `_compute_metrics()`** — aggregates simulation results
   from the EventStore/event log. Computes triage distribution, mean wait/transit/
   treatment times, facility utilisation, outcome counts.

2. **Any helper aggregation functions** called exclusively by metrics computation
   (e.g., `_compute_facility_utilisation()`, `_compute_survivability_summary()`).

## What You're NOT Extracting

- Event publication logic (that's EX-3, NB36)
- Per-casualty state tracking (stays in engine)
- Anything with `yield`, `env`, `resource`, or `simpy` references

## Target Module: `src/faer_dev/metrics.py`

```python
"""Metrics pure aggregation extracted from engine.py (EX-2).

Reads EventStore. Returns frozen dataclass. Zero side effects.
Zero SimPy dependency. Zero engine state access.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List
from collections import Counter


@dataclass(frozen=True)
class SimulationMetrics:
    """Immutable simulation result summary.

    Computed from EventStore after engine.run() completes.
    Dashboard and notebooks read this, never engine internals.
    """
    total_casualties: int
    triage_distribution: Dict[str, int]
    outcome_distribution: Dict[str, int]
    mean_wait_time: float
    mean_transit_time: float
    mean_treatment_time: float
    median_time_to_disposition: float
    facility_utilisation: Dict[str, float]
    survivability_by_triage: Dict[str, float]
    contested_denial_count: int


def compute_metrics(event_store) -> SimulationMetrics:
    """Compute simulation metrics from the event store.

    Pure aggregation. Reads events, computes stats, returns frozen result.
    This function has NO access to engine state, SimPy resources, or
    mutable simulation objects.

    Args:
        event_store: EventStore with .events property returning List[SimEvent]

    Returns:
        SimulationMetrics frozen dataclass
    """
    events = event_store.events

    # Triage distribution from TRIAGED events
    triage_events = [e for e in events if e.event_type == "TRIAGED"]
    triage_dist = dict(Counter(e.detail for e in triage_events))

    # Outcome distribution from DISCHARGED/DIED events
    outcome_events = [e for e in events if e.event_type in ("DISCHARGED", "DIED")]
    outcome_dist = dict(Counter(e.event_type for e in outcome_events))

    # Time metrics from per-casualty event pairs
    # ... (implementation extracted from engine.py)

    # Contested denials
    denials = [e for e in events if e.event_type == "ROUTE_DENIED"]

    return SimulationMetrics(
        total_casualties=len(triage_events),
        triage_distribution=triage_dist,
        outcome_distribution=outcome_dist,
        mean_wait_time=0.0,      # computed from event pairs
        mean_transit_time=0.0,   # computed from event pairs
        mean_treatment_time=0.0, # computed from event pairs
        median_time_to_disposition=0.0,
        facility_utilisation={},  # computed from facility events
        survivability_by_triage={},
        contested_denial_count=len(denials),
    )
```

## Toggle Integration

Add to `SimulationToggles`:
```python
use_extracted_metrics: bool = False  # EX-2: metrics.compute_metrics()
```

In engine, replace `get_metrics()` call path:
```python
def get_metrics(self):
    if self.toggles.use_extracted_metrics:
        from faer_dev.metrics import compute_metrics
        return compute_metrics(self.event_store)
    else:
        return self._legacy_compute_metrics()
```

## Notebook Structure (NB35)

### Cell 1: Baseline
```python
engine = FAEREngine(seed=42)
engine.build_network(topology)
engine.generate_casualties(20)
engine.run(until=600.0)
baseline_metrics = engine.get_metrics()  # legacy path
```

### Cell 2: Define metrics.py inline

### Cell 3: Compare
```python
from faer_dev.metrics import compute_metrics
new_metrics = compute_metrics(engine.event_store)

assert baseline_metrics.total_casualties == new_metrics.total_casualties
assert baseline_metrics.triage_distribution == new_metrics.triage_distribution
assert abs(baseline_metrics.mean_wait_time - new_metrics.mean_wait_time) < 0.01
# ... all fields compared
print("METRICS REGRESSION: PASS ✓")
```

### Cell 4: Prove SimPy independence
```python
# metrics.py must work with a mock EventStore — no SimPy needed
from unittest.mock import Mock
mock_store = Mock()
mock_store.events = [
    SimEvent(sim_time=0.0, event_type="TRIAGED", casualty_id="CAS-001", detail="T1"),
    SimEvent(sim_time=10.0, event_type="DISCHARGED", casualty_id="CAS-001"),
]
result = compute_metrics(mock_store)
assert result.total_casualties == 1
assert result.triage_distribution == {"T1": 1}
print("SimPy-free unit test: PASS ✓")
```

## Success Criteria

- [ ] All metric values match baseline within float tolerance
- [ ] metrics.py has zero SimPy imports
- [ ] compute_metrics() works with mock EventStore
- [ ] Toggle switches cleanly between old and new path

## Estimated Effort

- Extraction: ~62 LOC from engine.py
- New module: ~100 LOC (metrics.py with dataclass + function)
- Toggle wiring: ~10 LOC
- Notebook: ~100 LOC test scaffold
- **Total: ~180 LOC across 2 iterations (day 3)**
