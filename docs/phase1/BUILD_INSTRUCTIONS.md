# Phase 1 Build Instructions: Tidy + Decouple
## Master Instruction File for Claude Code Sessions

---

## Context

You are refactoring the FAER poly-hybrid simulation engine (SimPy DES + BehaviorTrees + NetworkX).
The current `engine.py` is 1,309 LOC containing a 327 LOC SimPy generator with 5 yield points.
Phase 1 extracts ~273 LOC of pure logic WITHOUT moving any yield points.

## Hard Rules (Violate NONE of These)

1. **All 5 yield points stay in engine.py.** Y1 (resource acquire), Y2 (treatment timeout), Y3 (PFC retry), Y4 (vehicle acquire), Y5 (travel timeout). No yield moves to another module.
2. **Every extraction is toggle-gated.** Add a flag to `SimulationToggles`. Old path preserved. New path activated by flag. Both paths must produce identical output on the same seed.
3. **Fixed-seed regression after every change.** Run with seed=42. Compare event log, triage distribution, per-casualty outcomes. Zero tolerance for Y1-Y5 changes. ±5% tolerance on distribution stats for 1,000+ casualty runs.
4. **50-100 LOC per iteration.** If a change touches more than 100 lines, split it.
5. **Notebook proves it first.** Each extraction has a proof notebook (NB34-38) that validates BEFORE the production code is touched.
6. **DISPOSITION == ARRIVAL count.** Non-negotiable invariant. Check after every change.

## Extraction Order (Do NOT reorder)

| Step | Notebook | Target | LOC | Risk | Yields Moved? |
|------|----------|--------|-----|------|---------------|
| 1 | NB34 | EX-1: Routing pure functions | ~70 | LOW | No |
| 2 | NB35 | EX-2: Metrics aggregation | ~62 | LOW | No |
| 3 | NB36 | EX-3: Typed EventEmitter + K-3 delete | ~73 (+28 deleted) | MEDIUM | No |
| 4 | NB37 | Pattern E: AnalyticsEngine | ~150 new | LOW-MED | No |
| 5 | NB38 | EX-4 sync: PFC decision function | ~60 | MEDIUM | No |
| 6 | NB39 | Integration gate | ~150 test | LOW | No |

## Files Created by Phase 1

| File | Source | Contents |
|------|--------|----------|
| `src/faer_dev/routing.py` | EX-1 from engine.py | `get_next_destination()`, `RoutingDecision` dataclass |
| `src/faer_dev/metrics.py` | EX-2 from engine.py | `compute_metrics()`, `SimulationMetrics` frozen dataclass |
| `src/faer_dev/emitter.py` | EX-3 from engine.py | `EventEmitter` Protocol, `TypedEmitter` implementation |
| `src/faer_dev/pfc.py` | EX-4 sync from engine.py | `evaluate_pfc()`, `PFCAction` enum, `PFCState` dataclass |
| `src/faer_dev/analytics/engine.py` | New (Pattern E) | `AnalyticsEngine` class, EventBus subscriber |
| `src/faer_dev/analytics/views.py` | New (Pattern E) | `GoldenHourView`, `FacilityLoadView`, `SurvivabilityView` |

## Phase 1 Exit Criteria

- [ ] engine.py ≤ 850 LOC (target ~800)
- [ ] K-3 closed (legacy `_triage_decisions()` deleted)
- [ ] K-7 closed (typed emitter publishes real event fields)
- [ ] NB32 acceptance test passes with all toggles ON
- [ ] 1,000-casualty run within ±5% distribution match
- [ ] 5,000-casualty run completes without OOM
- [ ] Deterministic replay: two runs with seed=42 produce identical output
- [ ] DISPOSITION count == ARRIVAL count on every test run
- [ ] Dashboard reads `AnalyticsEngine.get_view()`, not engine state

## Build Sequence Detail

See individual instruction files:
- `docs/phase1/NB34_routing_extraction.md`
- `docs/phase1/NB35_metrics_extraction.md`
- `docs/phase1/NB36_typed_emitter.md`
- `docs/phase1/NB37_analytics_decoupling.md`
- `docs/phase1/NB38_pfc_sync_extraction.md`
- `docs/phase1/NB39_integration_gate.md`
