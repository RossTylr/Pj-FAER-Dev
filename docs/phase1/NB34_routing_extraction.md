# NB34: EX-1 Routing Extraction Proof
## Claude Code Instruction File

---

## Objective

Extract `_get_next_destination()` and related ATMIST generation logic (~70 LOC)
from `engine.py` into a standalone `routing.py` module. Prove extraction is
behaviourally identical via fixed-seed comparison.

## What You're Extracting

From `engine.py`, identify and extract:

1. **`_get_next_destination(casualty, current_facility)`** — pure function that
   queries the TreatmentNetwork to find the next facility in the evacuation chain.
   Uses `network.get_next_facility()`, bypass logic, and role-based routing.

2. **ATMIST report generation** — if present inline in the journey, extract the
   report formatting. This is pure string/data formatting with zero SimPy dependency.

3. **Any helper functions** called exclusively by the above (e.g., `_should_bypass_r1()`,
   facility capacity checks used for routing decisions).

## What You're NOT Extracting

- Anything with `yield` in it
- Anything that calls `env.timeout()` or `resource.request()`
- The BT tick calls (those stay in engine.py)
- Transport execution logic (Y4, Y5)

## Target Module: `src/faer_dev/routing.py`

```python
"""Routing pure functions extracted from engine.py (EX-1).

All functions are synchronous, side-effect-free, and SimPy-independent.
They take immutable inputs and return frozen decision objects.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np


@dataclass(frozen=True)
class RoutingDecision:
    """Immutable routing decision returned by get_next_destination().

    The engine reads these fields and translates them into SimPy yields.
    This dataclass NEVER contains SimPy objects.
    """
    next_facility: Optional[str]   # None = end of chain (disposition)
    travel_time: float             # minutes, from network edge weight
    is_denied: bool                # contested route denial (EP-2)
    denial_wait: float             # if denied, suggested retry wait


def get_next_destination(
    casualty,                      # Casualty (Pydantic model)
    current_facility: str,
    network,                       # TreatmentNetworkProtocol
    rng: np.random.Generator,
) -> RoutingDecision:
    """Determine next facility in evacuation chain.

    Pure function. No SimPy. No yields. No side effects.
    Handles:
    - Forward chain traversal via network.get_next_facility()
    - Bypass R1 for critical cases (casualty.bypass_role1)
    - Contested route denial check (EP-2)
    - Travel time lookup with triage-priority modifier

    Args:
        casualty: The patient being routed
        current_facility: Current location ID
        network: Treatment chain topology
        rng: Random generator for contested route checks

    Returns:
        RoutingDecision with next destination or None if chain complete
    """
    next_fac = network.get_next_facility(current_facility)

    if next_fac is None:
        return RoutingDecision(
            next_facility=None, travel_time=0.0,
            is_denied=False, denial_wait=0.0,
        )

    # Contested route check (EP-2)
    is_denied = network.is_route_denied(current_facility, next_fac, rng)
    denial_wait = float(rng.exponential(15)) if is_denied else 0.0

    # Travel time with triage priority modifier
    travel_time = network.get_travel_time(current_facility, next_fac)

    return RoutingDecision(
        next_facility=next_fac,
        travel_time=travel_time,
        is_denied=is_denied,
        denial_wait=denial_wait,
    )
```

## Toggle Integration

Add to `SimulationToggles`:
```python
@dataclass
class SimulationToggles:
    # ... existing fields ...
    use_extracted_routing: bool = False  # EX-1: routing.get_next_destination()
```

In `engine.py._patient_journey()`, replace inline routing with:
```python
if self.toggles.use_extracted_routing:
    from faer_dev.routing import get_next_destination
    decision = get_next_destination(casualty, current_facility, self.network, self.rng)
    next_fac = decision.next_facility
    travel_time = decision.travel_time
    is_denied = decision.is_denied
else:
    # ... existing inline code (PRESERVED) ...
```

## Notebook Structure (NB34)

### Cell 1: Setup + Baseline Capture
```python
# Load current engine (NO toggles)
engine = FAEREngine(seed=42)
engine.build_network(topology)  # NB32 3-node contested chain
engine.generate_casualties(20)
engine.run(until=600.0)

# Capture baseline
baseline_events = [e for e in engine.log.events]
baseline_triage = Counter(c.triage.value for c in engine.casualties)
baseline_outcomes = {c.id: (c.triage.value, c.outcome_time, c.total_transit_time)
                     for c in engine.casualties}
```

### Cell 2: Define routing.py (inline for notebook proof)
```python
# Full routing module defined inline (copy of target src/faer_dev/routing.py)
```

### Cell 3: Extraction Wiring
```python
# Monkey-patch engine to use extracted routing
# OR: set toggles.use_extracted_routing = True
```

### Cell 4: Re-run + Comparison
```python
engine2 = FAEREngine(seed=42)
engine2.toggles.use_extracted_routing = True
engine2.build_network(topology)
engine2.generate_casualties(20)
engine2.run(until=600.0)

# REGRESSION: identical output
for e1, e2 in zip(baseline_events, engine2.log.events):
    assert e1.event_type == e2.event_type
    assert e1.casualty_id == e2.casualty_id
    assert abs(e1.sim_time - e2.sim_time) < 0.001

new_triage = Counter(c.triage.value for c in engine2.casualties)
assert baseline_triage == new_triage
print("REGRESSION: PASS ✓")
```

### Cell 5: Contested Route Verification
```python
# Verify route denial events are identical
baseline_denials = [e for e in baseline_events if e.event_type == "ROUTE_DENIED"]
new_denials = [e for e in engine2.log.events if e.event_type == "ROUTE_DENIED"]
assert len(baseline_denials) == len(new_denials)
print(f"Contested route denials: {len(new_denials)} (identical)")
```

### Cell 6: DISPOSITION Invariant
```python
arrivals = len([e for e in engine2.log.events if e.event_type in ("CREATED", "ARRIVAL")])
dispositions = len([e for e in engine2.log.events if e.event_type == "DISCHARGED"])
assert arrivals == dispositions == 20
print(f"DISPOSITION invariant: {arrivals} == {dispositions} ✓")
```

### Cell 7: Unit Tests (routing.py standalone)
```python
# Test get_next_destination without SimPy
from unittest.mock import Mock

mock_network = Mock()
mock_network.get_next_facility.return_value = "R1"
mock_network.is_route_denied.return_value = False
mock_network.get_travel_time.return_value = 30.0

rng = np.random.default_rng(42)
mock_casualty = Mock()

decision = get_next_destination(mock_casualty, "POI", mock_network, rng)
assert decision.next_facility == "R1"
assert decision.travel_time == 30.0
assert decision.is_denied == False
print("Unit tests: PASS ✓")
```

## Success Criteria

- [ ] Event log diff: 0 events different
- [ ] Per-casualty outcome diff: 0 casualties different
- [ ] Contested route denial count identical
- [ ] DISPOSITION == ARRIVAL == 20
- [ ] Unit tests pass without SimPy fixtures
- [ ] routing.py has zero SimPy imports

## Estimated Effort

- Extraction: ~70 LOC from engine.py
- New module: ~70 LOC (routing.py) + ~50 LOC (dataclass, imports)
- Toggle wiring: ~15 LOC in engine.py
- Notebook: ~130 LOC test scaffold
- **Total: ~265 LOC across 3 iterations (days 1-2)**
