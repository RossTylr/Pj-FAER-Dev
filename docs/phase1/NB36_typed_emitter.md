# NB36: EX-3 Typed EventEmitter + K-3/K-7 Closure
## Claude Code Instruction File

---

## Objective

Replace the legacy `_log_event(dict)` pattern with a typed `EventEmitter`
Protocol that publishes frozen `SimEvent` dataclasses with ALL fields populated.
Also delete the legacy `_triage_decisions()` dead code (K-3). This is the
highest-impact Phase 1 extraction because it closes two debt items and unblocks
analytics decoupling (NB37).

## Why This Matters

K-7 is the blocker: the current engine publishes events using legacy dicts,
which means typed `SimEvent` fields get default/empty values. Any analytics
code that reads typed fields reads zeros. PR-9 explicitly warns: "Analytics
on typed fields without verifying emit sites will read zeros." This extraction
fixes every emit site to publish typed, populated, frozen events.

## What You're Extracting

1. **`_log_event()` call sites** — every place in engine.py that publishes
   an event. Replace with calls to a typed `EventEmitter` protocol.

2. **K-3: `_triage_decisions()`** — top-level function that is dead code when
   BT is enabled. DELETE it entirely.

## Target Module: `src/faer_dev/emitter.py`

```python
"""Typed event emission protocol (EX-3).

Replaces legacy _log_event(dict) with typed, frozen SimEvent publication.
Closes K-7 (typed fields empty in production).
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class EventEmitter(Protocol):
    """Protocol for typed event emission.

    Every emit method creates a frozen SimEvent with ALL fields populated.
    The engine calls these methods; the implementation publishes to EventBus.

    RULES:
    - Every method receives raw values, not SimPy objects
    - sim_time is passed explicitly (from env.now at call site)
    - casualty is passed for ID and state extraction
    - No SimPy imports in this module
    """

    def emit_arrival(self, casualty, facility_id: str, sim_time: float) -> None: ...
    def emit_triage(self, casualty, facility_id: str, sim_time: float) -> None: ...
    def emit_treatment_start(self, casualty, facility_id: str,
                              department: str, sim_time: float) -> None: ...
    def emit_treatment_complete(self, casualty, facility_id: str,
                                 department: str, sim_time: float) -> None: ...
    def emit_hold_start(self, casualty, facility_id: str, sim_time: float) -> None: ...
    def emit_hold_retry(self, casualty, facility_id: str, sim_time: float) -> None: ...
    def emit_pfc_start(self, casualty, facility_id: str, sim_time: float) -> None: ...
    def emit_transit_start(self, casualty, from_id: str,
                            to_id: str, sim_time: float) -> None: ...
    def emit_transit_end(self, casualty, facility_id: str, sim_time: float) -> None: ...
    def emit_route_denied(self, casualty, facility_id: str,
                           destination: str, sim_time: float) -> None: ...
    def emit_disposition(self, casualty, facility_id: str, sim_time: float) -> None: ...


class TypedEmitter:
    """Concrete EventEmitter publishing frozen SimEvent dataclasses.

    Every method constructs a fully-populated SimEvent and publishes
    it to the EventLog/EventBus.
    """

    def __init__(self, event_log):
        """Args: event_log — EventLog instance with .publish(SimEvent) method."""
        self._log = event_log

    def emit_arrival(self, casualty, facility_id: str, sim_time: float) -> None:
        from faer_dev.events.models import SimEvent
        self._log.publish(SimEvent(
            sim_time=sim_time,
            event_type="ARRIVAL",
            casualty_id=casualty.id,
            facility_id=facility_id,
            detail=f"triage={casualty.triage.value}" if hasattr(casualty.triage, 'value') else "",
        ))

    def emit_triage(self, casualty, facility_id: str, sim_time: float) -> None:
        from faer_dev.events.models import SimEvent
        self._log.publish(SimEvent(
            sim_time=sim_time,
            event_type="TRIAGED",
            casualty_id=casualty.id,
            facility_id=facility_id,
            detail=casualty.triage.value if hasattr(casualty.triage, 'value') else str(casualty.triage),
        ))

    # ... remaining methods follow same pattern ...

    def emit_disposition(self, casualty, facility_id: str, sim_time: float) -> None:
        from faer_dev.events.models import SimEvent
        self._log.publish(SimEvent(
            sim_time=sim_time,
            event_type="DISCHARGED",
            casualty_id=casualty.id,
            facility_id=facility_id,
            detail=casualty.state.value if hasattr(casualty.state, 'value') else str(casualty.state),
        ))
```

## K-3 Deletion

Find `_triage_decisions()` in engine.py. It's ~28 LOC of legacy dead code
that only runs when BT is DISABLED. Since BT is now the canonical triage
path (Lessons §2: injury-first generation), this function is dead code.

```python
# DELETE THIS ENTIRE FUNCTION:
def _triage_decisions(self, casualty):
    """Legacy triage path — dead code when BT enabled."""
    # ... ~28 LOC ...
```

Also delete any `if not self.toggles.bt_enabled: self._triage_decisions(...)` branch.

## Toggle Integration

```python
use_typed_emitter: bool = False  # EX-3: TypedEmitter replaces _log_event()
```

## Notebook Structure (NB36)

### Cell 1: Baseline — show K-7 bug
```python
engine = FAEREngine(seed=42)
engine.build_network(topology)
engine.generate_casualties(20)
engine.run(until=600.0)

# Show that typed fields are empty/default in current events
for event in engine.log.events[:5]:
    print(f"{event.event_type}: detail='{event.detail}'")
    # Expected: detail='' (empty — this is K-7)
```

### Cell 2: Define emitter.py inline

### Cell 3: Wire TypedEmitter + re-run
```python
engine2 = FAEREngine(seed=42)
engine2.emitter = TypedEmitter(engine2.log)
engine2.toggles.use_typed_emitter = True
engine2.build_network(topology)
engine2.generate_casualties(20)
engine2.run(until=600.0)

# Show K-7 is fixed
for event in engine2.log.events[:5]:
    print(f"{event.event_type}: detail='{event.detail}'")
    # Expected: detail='T1' or 'T2' etc. (populated — K-7 CLOSED)
```

### Cell 4: Regression — event counts identical
```python
baseline_types = Counter(e.event_type for e in engine.log.events)
new_types = Counter(e.event_type for e in engine2.log.events)
assert baseline_types == new_types
print("Event count regression: PASS ✓")
```

### Cell 5: DISPOSITION invariant
```python
assert len([e for e in engine2.log.events if e.event_type == "ARRIVAL"]) == \
       len([e for e in engine2.log.events if e.event_type == "DISCHARGED"]) == 20
print("DISPOSITION invariant: PASS ✓")
```

### Cell 6: K-3 deletion verification
```python
import inspect
source = inspect.getsource(engine2.__class__)
assert "_triage_decisions" not in source
print("K-3 (legacy triage dead code): DELETED ✓")
```

### Cell 7: Protocol conformance
```python
assert isinstance(TypedEmitter(engine2.log), EventEmitter)
print("Protocol conformance: PASS ✓")
```

## Success Criteria

- [ ] All event fields populated (K-7 closed)
- [ ] Event counts identical between legacy and typed paths
- [ ] DISPOSITION == ARRIVAL == 20
- [ ] `_triage_decisions()` deleted (K-3 closed)
- [ ] TypedEmitter satisfies EventEmitter Protocol
- [ ] emitter.py has zero SimPy imports

## Estimated Effort

- Emitter protocol: ~40 LOC
- TypedEmitter impl: ~100 LOC (11 emit methods)
- Engine wiring (replace ~15 _log_event calls): ~50 LOC changes
- K-3 deletion: -28 LOC
- Notebook: ~100 LOC
- **Total: ~250 LOC across 3 iterations (days 4-5)**
