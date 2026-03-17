# Phase 3: PFC Hold Loop Delegation via `yield from`

## Status: Phase 3 — Triggered when engine.py ~650 LOC blocks progress

## Background

### What exists now

`pfc.py` was extracted in Phase 1 (EX-4 sync) with two pure functions:

- `evaluate_hold(hold_duration, downstream_available, ...)` → `HoldEvaluation`
  dataclass with a `PFCAction` enum (CONTINUE_HOLD, ESCALATE_TO_PFC, RELEASE,
  HOLD_TIMEOUT)
- `compute_deterioration(current_severity, hold_duration)` → float severity

Both are tested (13 tests in `test_pfc.py`) and proven in NB38.

### What's not wired

`engine.py` never checks `enable_extracted_pfc`. The hold/PFC loop
(engine.py lines 696-828) runs entirely inline. The toggle field exists in
`SimulationToggles` but has no effect.

This was intentional: the hold loop interleaves sync decisions with SimPy
yields (Y3), CCP processing, PFC ceiling enforcement, and re-triage. Inserting
a toggle-gated call to `evaluate_hold()` mid-loop would cover ~30% of the logic
while adding conditional complexity to the densest block in the engine. The ROI
was too low for Phase 1.

### Why Phase 3 is the right time

Phase 3's purpose is `yield from` delegation — extracting generator sub-loops
from engine.py into standalone generator functions. The hold/PFC loop is the
primary candidate (EX-6 in BUILD_INSTRUCTIONS.md). When this happens, the
entire block moves out of engine.py into `hold_pfc.py`, and that module
naturally imports `pfc.py` for its sync decisions.

## The Problem

The hold/PFC loop in engine.py (lines 696-828) is ~130 LOC of nested
conditionals interleaved with yields. It handles:

1. **Capacity polling** — check if downstream facility has space (sync)
2. **Hold start** — emit HOLD_START event on first iteration (sync)
3. **Hold timeout** — if held too long, dispose patient (sync decision + state change)
4. **PFC escalation** — if held > 60 min, transition to PFC status (sync decision)
5. **CCP processing** — if CCP available, admit patient, request medic, apply
   interventions (async — yields Y3a medic request, Y3b intervention timeout)
6. **PFC ceiling** — if PFC duration exceeds triage-specific max hours, fire
   ceiling event (sync)
7. **Re-triage** — on deterioration, promote triage category (sync decision)
8. **Retry yield** — `yield self.env.timeout(retry_interval)` (Y3 proper)
9. **Post-loop cleanup** — finalize PFC, finalize patient if timed out

Steps 1-4 and 6-7 are sync decisions. Steps 5 and 8 are SimPy yields. Step 9
is cleanup. The sync decisions are what `pfc.py` should own. The yields must
remain in a generator function (engine.py or a `yield from` delegate).

## Architecture

```
engine.py (Phase 3)
│
│   # Where the hold loop currently lives (~130 LOC)
│   # Replaced with:
│   yield from hold_pfc.hold_loop(env, patient, facility, network, ...)
│
└── hold_pfc.py (new — generator function, owns Y3)
    │
    ├── pfc.evaluate_hold(...)           # sync decision (existing)
    │   → PFCAction.CONTINUE_HOLD
    │   → PFCAction.ESCALATE_TO_PFC
    │   → PFCAction.RELEASE
    │   → PFCAction.HOLD_TIMEOUT
    │
    ├── pfc.compute_deterioration(...)   # sync model (existing)
    │   → updated severity float
    │
    ├── _check_pfc_ceiling(...)          # sync, moved from engine.py
    │   → whether to fire ceiling event + re-triage
    │
    ├── _process_ccp(env, patient, ccp)  # generator, yields medic/intervention
    │   → yield medic_req | env.timeout(5)
    │   → yield env.timeout(intervention_time)
    │
    └── yield env.timeout(retry_interval)  # Y3 — the retry yield
```

### Key boundaries

- `hold_pfc.py` IS allowed to import SimPy (it contains yields)
- `pfc.py` remains SimPy-free (HC-6) — sync decisions only
- engine.py calls `yield from hold_pfc.hold_loop(...)` — single delegation point
- The `yield from` passes SimPy's generator protocol through cleanly (NB44
  must prove exception safety before this ships)

## What pfc.py Already Provides

| Function | Used by hold_pfc.py for | Currently tested |
|---|---|---|
| `evaluate_hold()` | Steps 1-4: capacity, timeout, PFC escalation | 13 tests |
| `compute_deterioration()` | Step 7: severity update during re-triage | 2 tests |
| `PFCAction` enum | Control flow in hold loop | Used in all tests |
| `HoldEvaluation` dataclass | Structured decision output | Used in all tests |

### What needs to be added to pfc.py

| Function | Purpose | LOC estimate |
|---|---|---|
| `check_pfc_ceiling(pfc_hours, max_hours, already_fired)` | Step 6: ceiling check, returns bool | ~10 |
| `retriage_for_deterioration(current_triage, severity)` | Step 7: triage promotion logic | ~15 |

These are currently inline in engine.py. They're pure sync decisions that
belong in pfc.py but were never extracted because the hold loop itself wasn't
being moved.

### What hold_pfc.py contains (new file)

| Function | Purpose | LOC estimate |
|---|---|---|
| `hold_loop(env, patient, facility, ...)` | Generator: the full hold/PFC/CCP loop | ~80 |
| `_process_ccp(env, patient, ccp, ...)` | Generator: CCP medic request + interventions | ~25 |

Total new code: ~130 LOC (moving, not adding — engine.py shrinks by the same amount).

## Toggle Strategy

Replace the current dead `enable_extracted_pfc` toggle with:

```python
@dataclass
class SimulationToggles:
    ...
    enable_delegated_pfc: bool = False  # Phase 3: yield from hold_pfc
```

- **OFF**: engine.py runs the inline hold loop (current behaviour, all
  baselines preserved)
- **ON**: engine.py calls `yield from hold_pfc.hold_loop(...)`, which
  internally calls `pfc.evaluate_hold()` and `pfc.compute_deterioration()`

The old `enable_extracted_pfc` field can be removed once the delegation is
proven equivalent.

## Prerequisites

### NB44: `yield from` Exception Safety Proof

Before any `yield from` delegation ships, NB44 must prove:

1. `GeneratorExit` propagates correctly through `yield from` to the sub-generator
2. SimPy's `env.process()` correctly wraps `yield from` delegates
3. Exception in sub-generator surfaces correctly in engine.py
4. Interrupts (e.g. `process.interrupt()`) propagate through `yield from`

This is a Hard Constraint gate (CLAUDE.md rule #1: "Only Phase 3 delegates via
`yield from`, and only after NB44 proves exception safety").

### Phase 2 Option C (graph routing) is independent

PFC delegation does not depend on Option C. They touch different code paths
(routing vs hold loop). Can be done in parallel or in any order.

## Test Strategy

```python
# Step 1: Prove delegation equivalence on linear topology
engine_off = build(toggles=SimulationToggles(enable_delegated_pfc=False))
engine_on  = build(toggles=SimulationToggles(enable_delegated_pfc=True))
# Must produce identical events, metrics, outcomes
assert events_match(engine_off, engine_on)

# Step 2: Prove PFC triggers correctly
# Use a topology with constrained downstream (beds=1) to force holds
engine = build(topology_with_bottleneck, seed=42)
run(duration=1440)
pfc_events = [e for e in events if e["type"] in ("PFC_START", "PFC_END",
              "PFC_CEILING_EXCEEDED", "HOLD_START", "HOLD_TIMEOUT")]
assert len(pfc_events) > 0  # holds actually triggered

# Step 3: Prove deterioration model runs
# Check that compute_deterioration is called and severity updates
pfc_patients = [e for e in events if e["type"] == "PFC_CEILING_EXCEEDED"]
for p in pfc_patients:
    assert p["details"]["pfc_duration_hours"] > 0

# Step 4: Prove CCP integration (if CCP toggle enabled)
engine = build(toggles=SimulationToggles(enable_delegated_pfc=True, enable_ccp=True))
# Verify CCP events appear alongside PFC events
```

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `yield from` breaks SimPy generator protocol | LOW | HIGH | NB44 gate — do not ship without proof |
| CCP medic yield interacts badly with delegation | MEDIUM | MEDIUM | Test CCP ON + delegation ON together |
| Hold loop timing changes under delegation | LOW | HIGH | Fixed-seed comparison, event-by-event match |
| Re-triage logic diverges during extraction | LOW | MEDIUM | Unit tests for `retriage_for_deterioration()` |
| `GeneratorExit` not propagated on sim interruption | MEDIUM | HIGH | NB44 explicitly tests this scenario |

## LOC Impact on engine.py

| Before | After |
|---|---|
| engine.py: ~1,361 LOC | engine.py: ~1,230 LOC (-130) |
| hold_pfc.py: 0 | hold_pfc.py: ~105 |
| pfc.py: 109 | pfc.py: ~135 (+25 for ceiling/retriage) |

engine.py drops ~130 LOC. Combined with EX-5 (treatment orchestration,
-155 LOC), Phase 3 brings engine.py to ~1,075 LOC. Still above the 850
target — further extraction of department routing and transport logic
would be needed to reach it.

## Sequence

1. **NB44**: `yield from` exception safety proof notebook
2. **Add** `check_pfc_ceiling()` and `retriage_for_deterioration()` to pfc.py (~25 LOC)
3. **Create** `hold_pfc.py` with `hold_loop()` generator (~80 LOC, iteration 1)
4. **Wire** CCP sub-generator in `hold_pfc.py` (~25 LOC, iteration 2)
5. **Add** `enable_delegated_pfc` toggle, wire in engine.py
6. **Prove** toggle OFF == toggle ON (fixed-seed comparison)
7. **Remove** old `enable_extracted_pfc` toggle field
8. **Update** IRON BRIDGE preset with constrained topology to demo PFC in Engine Room

## When to Trigger

This work begins when:

1. **engine.py at ~650 LOC is actively blocking you** — the hold loop is too
   tangled to add EP-7 consumable tracking or multiple deterioration models
2. **MNEMOSYNE data generation** needs richer PFC event streams with
   deterioration curves for the surrogate survival model
3. **Defence stakeholder demo** requests visible PFC/hold mechanics in the
   Engine Room

The trigger is not "we should probably clean this up." It's "I'm trying to do
X and the inline hold loop is the thing preventing it."

## Files Touched

| File | Change |
|---|---|
| `src/faer_dev/pfc.py` | Add `check_pfc_ceiling()`, `retriage_for_deterioration()` |
| `src/faer_dev/simulation/hold_pfc.py` | New: `hold_loop()` generator + CCP sub-gen |
| `src/faer_dev/simulation/engine.py` | Replace inline loop with `yield from hold_pfc.hold_loop(...)` |
| `src/faer_dev/decisions/mode.py` | Add `enable_delegated_pfc`, remove `enable_extracted_pfc` |
| `tests/test_pfc.py` | Add ceiling + retriage unit tests |
| `tests/test_hold_pfc.py` | New: delegation equivalence + PFC trigger tests |
| `notebooks/phase3/NB44_yield_from_safety.ipynb` | Exception safety proof (GATE) |
| `notebooks/phase3/NB45_pfc_delegation.ipynb` | PFC delegation proof |
