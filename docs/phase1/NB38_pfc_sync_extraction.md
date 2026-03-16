# NB38: EX-4 PFC Sync Decision Extraction Proof
## Claude Code Instruction File

---

## Objective

Extract the synchronous decision portion (~60 LOC) of the PFC hold logic from
engine.py into a pure function in `pfc.py`. The yield loop (Y3) stays in engine.py.
Only the DECISION moves — "should we keep holding, escalate, or release?" — not
the EXECUTION — "pause the simulation for RETRY_INTERVAL."

## Key Distinction

```
BEFORE (engine.py, inline):
    while not downstream_available(...):
        # 140 LOC of nested conditionals mixing decision + yield
        if hold_duration > PFC_THRESHOLD:    # ← DECISION (extract this)
            casualty.state = PFC
            emit(PFC_START)
        yield env.timeout(RETRY_INTERVAL)    # ← EXECUTION (keep this)

AFTER (engine.py calls pfc.py):
    while not downstream_available(...):
        action = pfc.evaluate_pfc(casualty, hold_duration, False, PFC_THRESHOLD)
        if action == ESCALATE_PFC:           # engine reads decision
            casualty.state = PFC
            emitter.emit_pfc_start(...)
        yield env.timeout(RETRY_INTERVAL)    # Y3 stays in engine.py
```

## Target Module: `src/faer_dev/pfc.py`

```python
"""PFC sync decision logic extracted from engine.py (EX-4 sync portion).

Pure functions for Prolonged Field Care evaluation. No SimPy. No yields.
The engine calls these between yield points to decide what to do next.
The engine owns the actual yield (Y3 retry timeout).
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class PFCAction(Enum):
    """Decision output from evaluate_pfc(). Engine translates to yields."""
    CONTINUE_HOLD = "CONTINUE_HOLD"     # keep waiting, yield retry timeout
    ESCALATE_PFC = "ESCALATE_PFC"       # escalate to PFC status, then hold
    RELEASE = "RELEASE"                  # downstream available, stop holding


@dataclass
class PFCState:
    """Mutable PFC tracking state for a single casualty's hold episode."""
    hold_start: float = 0.0
    hold_duration: float = 0.0
    is_pfc: bool = False
    deterioration_factor: float = 1.0


def evaluate_pfc(
    casualty,
    hold_duration: float,
    downstream_available: bool,
    pfc_threshold: float,
    deterioration_rate: float = 0.01,
) -> PFCAction:
    """Pure PFC decision function. No SimPy. No yields. No side effects.

    Called by engine.py inside the hold retry loop BETWEEN yield points.
    Returns a PFCAction that the engine translates into:
    - RELEASE: break the hold loop
    - ESCALATE_PFC: set PFC state + emit event + continue holding
    - CONTINUE_HOLD: yield retry timeout + continue

    Args:
        casualty: Patient being held
        hold_duration: Time elapsed since hold started (minutes)
        downstream_available: Whether next facility has capacity
        pfc_threshold: Minutes before escalating to PFC status
        deterioration_rate: Per-minute deterioration (EP-3 extension hook)

    Returns:
        PFCAction enum value
    """
    if downstream_available:
        return PFCAction.RELEASE

    if hold_duration > pfc_threshold and not getattr(casualty, '_is_pfc', False):
        return PFCAction.ESCALATE_PFC

    return PFCAction.CONTINUE_HOLD


def compute_deterioration(
    casualty,
    hold_duration: float,
    base_rate: float = 0.01,
) -> float:
    """Compute severity deterioration during PFC hold.

    EP-3 extension point: configurable deterioration model.
    Currently linear; can be replaced with exponential/logistic.

    Returns:
        New severity score (clamped to [0.0, 1.0])
    """
    current = getattr(casualty, 'severity_score', 0.5)
    if hasattr(casualty, 'mist'):
        current = casualty.mist.severity_score
    return min(1.0, current + hold_duration * base_rate)
```

## Toggle Integration

```python
use_extracted_pfc: bool = False  # EX-4 sync: pfc.evaluate_pfc()
```

## Notebook Structure (NB38)

### Cell 1: Build PFC-triggering scenario
```python
# Modify NB32 topology to constrain R1 capacity to 1
# This forces hold/PFC when multiple casualties compete
topology = [
    {"id": "POI", "role": "POI", "capacity": 50,
     "routes_to": [{"to": "R1", "time": 30.0, "contested": True, "denial_prob": 0.2}]},
    {"id": "R1",  "role": "R1",  "capacity": 1,   # CONSTRAINED — triggers PFC
     "routes_to": [{"to": "R2", "time": 45.0}]},
    {"id": "R2",  "role": "R2",  "capacity": 8},
]
```

### Cell 2: Baseline with PFC events captured
### Cell 3: Define pfc.py inline
### Cell 4: Patch engine to call evaluate_pfc(), re-run
### Cell 5: Regression — PFC event sequence identical
### Cell 6: Unit tests (pure, no SimPy)
```python
# These tests need ZERO simulation infrastructure
assert evaluate_pfc(cas, 10.0, True, 30.0) == PFCAction.RELEASE
assert evaluate_pfc(cas, 10.0, False, 30.0) == PFCAction.CONTINUE_HOLD
assert evaluate_pfc(cas, 45.0, False, 30.0) == PFCAction.ESCALATE_PFC
print("PFC unit tests (no SimPy): PASS ✓")
```

### Cell 7: Deterioration model test
```python
# EP-3 extension point validation
new_sev = compute_deterioration(cas, hold_duration=60.0, base_rate=0.005)
assert 0.0 <= new_sev <= 1.0
```

## Success Criteria

- [ ] PFC event sequence identical to baseline
- [ ] evaluate_pfc() passes unit tests without SimPy
- [ ] Y3 (retry timeout) remains in engine.py
- [ ] pfc.py has zero SimPy imports
- [ ] EP-3 deterioration hook exists and is testable

## Estimated Effort

- Extraction: ~60 LOC sync decision logic
- pfc.py module: ~80 LOC (enums, dataclass, 2 functions)
- PFC-triggering scenario: ~30 LOC topology modification
- Engine wiring: ~20 LOC toggle + call replacement
- Notebook: ~100 LOC
- **Total: ~200 LOC across 2 iterations (day 8)**
