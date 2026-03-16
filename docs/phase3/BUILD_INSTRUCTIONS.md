# Phase 3 Build Instructions: Delegate
## Conditional — Only If Phase 2 Proves Insufficient

---

## Prerequisites

- NB42 (HADR Variant) PASSED
- NB41 (EX-5 Treatment Delegation) PASSED with exception safety proven
- engine.py at ~650 LOC is STILL the bottleneck

## When NOT to Do Phase 3

If engine.py at ~650 LOC with plugins is manageable for the solo developer,
Phase 3 is unnecessary. The hold/PFC loop (140 LOC nested conditionals) stays
where it is. The engine still works. Don't break working code to chase purity.

## The Extraction

### NB43 — EX-6 Hold/PFC Loop

**This is the single highest-risk extraction in the entire kernel.**

The 140 LOC nested conditional block containing Y3 (PFC retry timeout) moves
from engine.py into `hold_pfc.py` as a sub-generator via `yield from`.

Why it's hard:
- Deeply nested conditionals with mutable casualty state
- Y3 sits inside a `while not downstream_available:` loop
- The loop evaluates PFC decisions, mutates casualty state, AND yields
- Exception propagation in nested generators with `with` blocks

Gate: 10,000-casualty fixed-seed comparison. If ANY casualty diverges, DO NOT MERGE.

## Phase 3 Exit Criteria

- [ ] engine.py ≤ 550 LOC (target ~500)
- [ ] 10,000-casualty fixed-seed comparison within ±5%
- [ ] Exception safety proven for Y3 in sub-generator
- [ ] NB32 acceptance test passes
- [ ] Total kernel LOC ≤ 4,508 (current baseline)

## Fallback

If NB43 fails: STOP. engine.py at ~650 LOC with plugins is the final state.
The PFC loop stays in engine.py. The architecture is complete at Phase 2.
This is an acceptable outcome.
