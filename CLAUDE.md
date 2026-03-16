# CLAUDE.md — Claude Code Instructions for Pj-FAER-Dev

## What This Repo Is

FAER-Dev is the development branch for refactoring the FAER poly-hybrid
simulation engine (SimPy DES + BehaviorTrees + NetworkX). It implements
the "Tidy, Decouple, Then Plug" architecture validated by a multi-LLM
Design Space Exploration.

## Hard Rules (Never Violate)

1. **All 5 SimPy yield points stay in engine.py** (Phase 1-2). Only Phase 3
   delegates via `yield from`, and only after NB44 proves exception safety.

2. **Every extraction is toggle-gated** behind `SimulationToggles`. Old path
   preserved. Fixed-seed comparison before merging.

3. **50-100 LOC per iteration.** If a change touches >100 lines, split it.

4. **DISPOSITION count == ARRIVAL count.** Check after every engine change.

5. **No SimPy imports** in routing.py, metrics.py, emitter.py, pfc.py,
   analytics/, or any plugin module. SimPy lives ONLY in simulation/.

6. **Notebook proves it first.** NB34-38 validate before production code.

## Architecture Constraints (from DSE)

- HC-1: SimPy generator model (yield-based, no async/await)
- HC-2: Deterministic replay (same seed = same output)
- HC-5: Blackboard isolation (BT↔engine only via SimBlackboard)
- HC-6: Layer separation (BT: zero SimPy imports, Sim: zero Streamlit)
- HC-8: Incremental migration only (strangler pattern)
- MC-3: ±5% distribution calibration on 1,000+ casualties
- MC-4: SimulationToggles gate every extraction step

## Current Phase: Phase 1 (Tidy + Decouple)

Phase 1 extractions in order:
1. EX-1 → routing.py (NB34)
2. EX-2 → metrics.py (NB35)
3. EX-3 → emitter.py + K-3 delete (NB36)
4. Pattern E → analytics/ (NB37)
5. EX-4 sync → pfc.py (NB38)
6. Integration gate (NB39)

## Key Files

| File | Purpose |
|------|---------|
| `docs/phase1/BUILD_INSTRUCTIONS.md` | Master Phase 1 instructions |
| `docs/phase1/NB34_routing_extraction.md` | EX-1 detailed spec |
| `docs/phase1/NB35_metrics_extraction.md` | EX-2 detailed spec |
| `docs/phase1/NB36_typed_emitter.md` | EX-3 detailed spec |
| `docs/phase1/NB37_analytics_decoupling.md` | Pattern E spec |
| `docs/phase1/NB38_pfc_sync_extraction.md` | EX-4 sync spec |
| `docs/phase1/NB39_integration_gate.md` | Phase 1 go/no-go gate |

## Coding Style

- Python 3.10+, type hints on all public functions
- Frozen dataclasses for decision objects (`@dataclass(frozen=True)`)
- Protocols for interfaces (`typing.Protocol`)
- Enums for decision outcomes
- No global state. No module-level RNG. No dict iteration order dependence.
- `ruff` for linting (line-length=100)

## Testing Pattern

```python
# 1. Run with toggle OFF (baseline)
engine_old = FAEREngine(seed=42, toggles=SimulationToggles(use_extracted_X=False))
engine_old.run()

# 2. Run with toggle ON (extraction)
engine_new = FAEREngine(seed=42, toggles=SimulationToggles(use_extracted_X=True))
engine_new.run()

# 3. Assert identical
assert events_match(engine_old.log.events, engine_new.log.events)
assert outcomes_match(engine_old.casualties, engine_new.casualties)
```
