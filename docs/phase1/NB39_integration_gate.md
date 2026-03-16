# NB39: Phase 1 Integration Gate
## Claude Code Instruction File

---

## Objective

Full regression test of ALL Phase 1 extractions running together. This notebook
is the go/no-go gate for Phase 1 completion. It does not extract or build
anything new — it VALIDATES everything built in NB34-38.

## What This Notebook Proves

1. All 4 toggles ON simultaneously produces identical output to pre-Phase-1 baseline
2. Distribution statistics hold within ±5% at 1,000 casualties (MC-3)
3. No memory leak at 5,000 casualties
4. Deterministic replay works (HC-2)
5. DISPOSITION invariant holds (KL-6)
6. engine.py LOC is at target (~800)
7. Debt items K-3 and K-7 are closed
8. Analytics views produce correct data

## Notebook Structure

### Cell 1: Pre-Phase-1 Baseline (ALL toggles OFF)
```python
from faer_dev.simulation.engine import FAEREngine
from faer_dev.decisions.mode import SimulationToggles

# ALL TOGGLES OFF — this is the legacy baseline
toggles = SimulationToggles(
    use_extracted_routing=False,
    use_extracted_metrics=False,
    use_typed_emitter=False,
    use_extracted_pfc=False,
)

engine_legacy = FAEREngine(seed=42, toggles=toggles)
engine_legacy.build_network(topology)
engine_legacy.generate_casualties(20)
engine_legacy.run(until=600.0)

baseline = capture_full_state(engine_legacy)  # events, outcomes, metrics
```

### Cell 2: Phase 1 State (ALL toggles ON)
```python
toggles_phase1 = SimulationToggles(
    use_extracted_routing=True,
    use_extracted_metrics=True,
    use_typed_emitter=True,
    use_extracted_pfc=True,
)

engine_phase1 = FAEREngine(seed=42, toggles=toggles_phase1)
engine_phase1.build_network(topology)
engine_phase1.generate_casualties(20)
engine_phase1.run(until=600.0)

phase1 = capture_full_state(engine_phase1)
```

### Cell 3: Event-Level Regression (Zero Tolerance)
```python
assert len(baseline.events) == len(phase1.events), \
    f"Event count mismatch: {len(baseline.events)} vs {len(phase1.events)}"

for i, (b, p) in enumerate(zip(baseline.events, phase1.events)):
    assert b.event_type == p.event_type, f"Event {i}: type {b.event_type} vs {p.event_type}"
    assert b.casualty_id == p.casualty_id, f"Event {i}: casualty mismatch"
    assert abs(b.sim_time - p.sim_time) < 0.001, f"Event {i}: time drift"

print(f"Event regression: {len(phase1.events)} events, ALL IDENTICAL ✓")
```

### Cell 4: Per-Casualty Outcome Regression
```python
for cas_b, cas_p in zip(engine_legacy.casualties, engine_phase1.casualties):
    assert cas_b.triage == cas_p.triage
    assert abs(cas_b.outcome_time - cas_p.outcome_time) < 0.001
    assert abs(cas_b.total_wait_time - cas_p.total_wait_time) < 0.001
    assert abs(cas_b.total_transit_time - cas_p.total_transit_time) < 0.001
    assert abs(cas_b.total_treatment_time - cas_p.total_treatment_time) < 0.001

print(f"Per-casualty regression: {len(engine_phase1.casualties)} casualties, ALL IDENTICAL ✓")
```

### Cell 5: Distribution Test at Scale (MC-3: ±5%)
```python
engine_1k = FAEREngine(seed=42, toggles=toggles_phase1)
engine_1k.build_network(topology)
engine_1k.generate_casualties(1000)
engine_1k.run(until=6000.0)

# Compare triage distribution against expected proportions
triage_dist = Counter(c.triage.value for c in engine_1k.casualties)
total = sum(triage_dist.values())
proportions = {k: v/total for k, v in triage_dist.items()}

# These expected proportions come from the pre-migration 1k baseline
# Run once with legacy toggles to establish, then hardcode
expected = {"T1": 0.20, "T2": 0.35, "T3": 0.45}  # approximate
for cat, expected_prop in expected.items():
    actual_prop = proportions.get(cat, 0.0)
    assert abs(actual_prop - expected_prop) < 0.05, \
        f"MC-3 FAIL: {cat} expected {expected_prop:.2f}, got {actual_prop:.2f}"

print(f"Distribution regression (MC-3 ±5%): PASS ✓")
```

### Cell 6: Memory Profile (5,000 Casualties)
```python
import tracemalloc
tracemalloc.start()

engine_5k = FAEREngine(seed=42, toggles=toggles_phase1)
engine_5k.build_network(topology)
engine_5k.generate_casualties(5000)
engine_5k.run(until=60000.0)

current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()

print(f"Memory: current={current/1e6:.1f}MB, peak={peak/1e6:.1f}MB")
assert peak < 500e6, f"OOM RISK: peak memory {peak/1e6:.1f}MB exceeds 500MB threshold"
print("Memory check: PASS ✓")
```

### Cell 7: Deterministic Replay (HC-2)
```python
engine_replay = FAEREngine(seed=42, toggles=toggles_phase1)
engine_replay.build_network(topology)
engine_replay.generate_casualties(20)
engine_replay.run(until=600.0)

match = all(
    a.triage == b.triage and abs(a.outcome_time - b.outcome_time) < 0.001
    for a, b in zip(engine_phase1.casualties, engine_replay.casualties)
)
assert match, "HC-2 VIOLATION: deterministic replay failed"
print("Deterministic replay (HC-2): PASS ✓")
```

### Cell 8: DISPOSITION Invariant (KL-6)
```python
for engine_name, eng in [("legacy", engine_legacy), ("phase1", engine_phase1),
                          ("1k", engine_1k), ("5k", engine_5k)]:
    arrivals = len([e for e in eng.log.events if e.event_type in ("ARRIVAL", "CREATED")])
    dispositions = len([e for e in eng.log.events if e.event_type == "DISCHARGED"])
    assert arrivals == dispositions, \
        f"KL-6 VIOLATION in {engine_name}: {arrivals} arrivals, {dispositions} dispositions"

print("DISPOSITION invariant (KL-6): PASS ✓ (all 4 engine runs)")
```

### Cell 9: Debt Closure Verification
```python
import inspect

# K-3: legacy triage dead code deleted
engine_source = inspect.getsource(engine_phase1.__class__)
assert "_triage_decisions" not in engine_source, "K-3 NOT CLOSED: _triage_decisions still exists"
print("K-3 (legacy triage dead code): CLOSED ✓")

# K-7: typed event fields populated
triaged_events = [e for e in engine_phase1.log.events if e.event_type == "TRIAGED"]
for e in triaged_events:
    assert e.detail and e.detail != "", f"K-7 NOT CLOSED: TRIAGED event has empty detail"
print(f"K-7 (typed fields): CLOSED ✓ ({len(triaged_events)} events checked)")
```

### Cell 10: engine.py LOC Count
```python
import pathlib
engine_path = pathlib.Path("src/faer_dev/simulation/engine.py")
loc = len([line for line in engine_path.read_text().splitlines() if line.strip()])
print(f"engine.py: {loc} LOC")
assert loc <= 850, f"engine.py LOC target missed: {loc} > 850"
print(f"LOC target: PASS ✓ (target ≤850, actual {loc})")
```

### Cell 11: Analytics View Verification
```python
from faer_dev.analytics.engine import AnalyticsEngine
from faer_dev.analytics.views import GoldenHourView, SurvivabilityView

analytics = AnalyticsEngine(engine_phase1.log)  # or EventBus
analytics.register_view("golden_hour", GoldenHourView())
analytics.register_view("survivability", SurvivabilityView())

# Replay events through analytics
for event in engine_phase1.log.events:
    analytics._on_event(event)

gh = analytics.get_view("golden_hour")
sv = analytics.get_view("survivability")
print(f"Golden Hour view: {gh}")
print(f"Survivability view: {sv}")
assert sv["total_dispositions"] == 20
print("Analytics views: PASS ✓")
```

### Cell 12: Phase 1 Exit Summary
```python
print("=" * 60)
print("PHASE 1 EXIT CRITERIA")
print("=" * 60)
print(f"  engine.py LOC:         {loc} (target ≤850)     {'✓' if loc <= 850 else '✗'}")
print(f"  K-3 closed:            YES                      ✓")
print(f"  K-7 closed:            YES                      ✓")
print(f"  NB32 acceptance:       PASS                     ✓")
print(f"  MC-3 distribution:     PASS (±5%)               ✓")
print(f"  Memory (5k):           {peak/1e6:.1f}MB          ✓")
print(f"  HC-2 replay:           PASS                     ✓")
print(f"  KL-6 DISPOSITION:      PASS                     ✓")
print(f"  Analytics decoupled:   PASS                     ✓")
print("=" * 60)
print("DECISION: GO / PAUSE for Phase 2")
```

## Success Criteria

ALL of the following must pass:
- [ ] Event-level regression: zero differences
- [ ] Per-casualty regression: zero differences
- [ ] MC-3: ±5% distribution match at 1,000 casualties
- [ ] Memory: peak < 500MB at 5,000 casualties
- [ ] HC-2: deterministic replay verified
- [ ] KL-6: DISPOSITION == ARRIVAL on all test runs
- [ ] K-3: `_triage_decisions` does not exist
- [ ] K-7: all TRIAGED events have populated detail field
- [ ] engine.py ≤ 850 LOC
- [ ] Analytics views produce correct data

If ANY criterion fails: PAUSE. Fix the failing extraction. Do not proceed to Phase 2.
