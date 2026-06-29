# MAAFI RED TEAM — FAER-MIL Codebase Interrogation (layer-aware)

**Agent role:** Red Team — challenge "done" claims, run actual tests, stress-test foundations.
**Run date:** 2026-06-17
**Environment:** Python 3.14.4, pytest (99 tests), `.venv` active, `src/` layout.
**Method:** Live execution. Every verdict below was produced by *running code*, not reading it.
Break-experiments were reverted via `git checkout` and the suite confirmed green afterward.

> **Headline (read first):** The test suite proves **execution, not correctness.** Forcing every
> casualty to triage **T3** — a catastrophic clinical corruption — **passes all 99 tests** (R17, Break C).
> The suite's safety comes almost entirely from *differential* `legacy==extracted` checks; any defect on a
> single-implementation path with no oracle (triage, severity, deterioration model, capability) is invisible.
> Combined with the known facts that routing ignores capability (R16a: 86/114 surgical patients treated at
> non-surgical facilities) and DCS never emits, **most intrinsic "done" claims mean "runs", not "computes
> correctly."** A surface MVP built on this foundation would create false confidence.

---

## GATE RESULTS (R1, R5) — both PASS

| Gate | Verdict | Evidence |
|------|---------|----------|
| **R1 Determinism** | ✅ **PASS** (with caveat) | `coin` seed=42 run twice → legacy event log **byte-identical** (md5 `2536fedbab97` both), typed store identical after excluding non-deterministic fields, `completed=28` both. Suite runs twice → `99 passed` both. |
| **R5 Strangler** | ✅ **PASS** | All 4 toggles (`enable_extracted_routing/metrics`, `enable_typed_emitter`, `enable_graph_routing`) → OFF vs ON at seed 42 produce **identical legacy log + identical store + identical completed count**. Confirmed live. |

**R1 caveat (a real Red-Team trap):** a *naive* byte-diff of the typed event store **fails every time** —
`SimEvent.event_id` is a `uuid.uuid4()` and `wall_time` is `datetime.now()` ([events/models.py:42-44](../src/faer_dev/events/models.py#L42)).
I confirmed the first 3 `event_id`s differ across two identical-seed runs. Determinism holds **only** on
the simulation-meaningful fields. **Any acceptance harness that hashes the raw event store for replay
equality will report spurious non-determinism.** Recommend a canonical serializer that drops `event_id`/`wall_time`.

**R5 caveat:** `enable_graph_routing` being "identical OFF vs ON" is **not** evidence that graph routing
preserves outcomes — it is evidence that **`enable_graph_routing` is inert by itself** (see R11). It only
takes effect when `enable_extracted_routing` is *also* True ([engine.py:680-684](../src/faer_dev/simulation/engine.py#L680)).

---

## R2. CLAIM–TEST MATRIX

"Test" = a test that exercises the feature's live path. Intrinsic-without-correctness-test = **HIGH** risk.

| # | Feature | Layer | Claimed | Test (file:class) | Verdict |
|---|---------|-------|---------|-------------------|---------|
| 5 | Capability-aware routing | INTRINSIC | implied | **none** | 🔴 **HIGH** — unimplemented (R16a: 86/114 violations). No test because nothing to test. |
| 21/31–33 | PFC deterioration / hold / ceiling | INTRINSIC | done | `test_pfc.py` (13) — **tests the UNWIRED `pfc.py`** | 🔴 **HIGH** — inline engine logic that actually runs has **0** integration tests (R4). Tests validate dead code. |
| 28 | DCS decision | INTRINSIC | done | **none** | 🔴 **HIGH** — `build_dcs_tree` never invoked; `DCS` event never emitted; `requires_dcs` written-never-read. Unverifiable. |
| 30 | MASCAL triage shift | INTRINSIC | done | implicit via `casualty_factory` | 🟡 MED — live but no assertion on the shift itself. |
| EX-1 routing | routing.py extraction | INTRINSIC | done | `test_routing.py::TestRegressionEquivalence` (seed 42/99) | 🟢 differential-tested (but see R17 Break B). |
| EX-2 metrics | metrics.py extraction | INTRINSIC | done | `test_metrics.py::TestMetricsRegressionEquivalence` | 🟢 differential-tested. |
| EX-3 emitter | typed emitter | SURFACE→INTRINSIC | done | `test_emitter.py::TestEmitterRegressionEquivalence` | 🟢 differential-tested. |
| Phase 1.5 | graph routing (Dijkstra) | INTRINSIC | done | `test_routing.py::TestGraphRouting` (6) + `Regression` (3) | 🟡 MED — equivalence only on **linear** chains; **no test of load-balancing on a branching topology** (R11/R12). |
| 40 | survivability | SURFACE | done | — (UI helper only, `demo_app/`) | 🟢 not engine. |
| 41/42 | GoldenHour / FacilityLoad views | SURFACE | done | `test_analytics.py` (unit+integration) | 🟢 tested, decoupled. |
| 43 | process mining | SURFACE | — | **none** (import-orphan) | ⚪ dead. |
| factory_mode, decision_mode, enable_department_routing, enable_vitals, enable_atmist, enable_ccp | 6 feature toggles | INTRINSIC (5) | varies | **none** (ON paths) | 🔴 **HIGH** — every regression test runs default-OFF; ON paths fully unverified. `ccp.py` has 0 tests. |

**Net:** the *only* features with correctness anchors are the differential extractions (EX-1/2/3) and the
analytics views. Every genuinely intrinsic clinical feature (#5, PFC, #28, the 6 feature toggles) is either
untested, or tested only as unwired/pure code that the engine never runs.

---

## R3. PERFORMANCE BASELINE — ✅ not a concern

| Measurement | Result |
|---|---|
| One `coin` run (1440 min, cap 200) | **44 ms**, 258 events |
| 100 replications via `EnsembleBuilder` | **0.94 s** (9 ms/rep) |
| Extrapolated AC-45.1 sweep (100 reps × 4 bed values) | **~3.8 s** |

**Verdict: FINE** (target <5 min; actual seconds). Performance is *not* a bottleneck for the sweep MVP —
the bottleneck is the **missing sweep parameterisation** (R16b), not runtime.

## R6. STRESS CEILING — ✅ bounded

500 casualties, 2880 min, `iron_bridge`: **0.27 s, 3911 events, 500 completed (fully drained), peak 5.5 MB.**
No break point reached; memory bounded and small. The engine scales far beyond MVP needs.

## R9. REPLICATION ISOLATION — ✅ clean

Each `EnsembleBuilder` replication calls `build_engine_from_preset` → **fresh `env` and fresh `_rng`**
(verified distinct objects). Two 5-rep ensembles at base_seed=42 gave **identical** per-rep `completed`
values `[17,20,18,15,18]`; reps differ by seed (no frozen/leaked state). `patient_seed` being inert
(CRN unimplemented) does **not** harm isolation — each rep is independent; it only means common-random-numbers
variance reduction is unavailable.

## R10. IMPORT OVERHEAD — ✅ no tax

Cold `import faer_dev` = **76 ms**; `import …config.builder` = **184 ms**. **streamlit/plotly are NOT
imported at package or builder import** (they live behind `demo_app/`). No per-rep import tax on sweeps.

---

## R4. HOLD GATE INTEGRATION TEST — ⚠️ logic correct, **zero existing coverage**

**Finding:** There is **no integration test** for the full hold sequence. `_hold_timeout_override`
([engine.py:716](../src/faer_dev/simulation/engine.py#L716)) is a test seam that **no test sets**, and the
`evaluate_hold` unit tests in `test_pfc.py` exercise the **unwired `pfc.py`**, not the inline engine gate
([engine.py:706-847](../src/faer_dev/simulation/engine.py#L706)) that actually runs.

**I wrote a minimal one** (`/tmp/rt_holdgate.py`): bottleneck R2 (beds=1), `_hold_timeout_override=75`,
T2 arrivals. One patient (CAS-0024) traversed the **exact** sequence:

```
t= 99.1 HOLD_START
t=114.1/129.1/144.1/159.1/174.1 HOLD_RETRY (every 15.0 min)
t=159.1 PFC_START          (+60.0 from hold start — exactly pfc_threshold)
t=174.1 HOLD_TIMEOUT       (+75.0 — exactly the override)
```

16 patients held, 14 reached PFC, 14 timed out. **The inline logic is correct and verifiable — it is
simply untested.** Recommend promoting `/tmp/rt_holdgate.py` into `tests/`. Note `PFC_CEILING_EXCEEDED`
did **not** fire (default ceiling 24 h ≫ 75 min hold) — consistent with F12: ceiling is only conditionally
observable.

---

## R7. TECH DEBT (engine.py + src/)

- **engine.py:** zero `TODO/FIXME/HACK/XXX`. Five `# type: ignore[return]` — all on SimPy-generator
  signatures ([engine.py:649,1030,1137,1186,1212](../src/faer_dev/simulation/engine.py#L649)), legitimate.
- **src/ total:** 7 `type: ignore`/marker hits (5 in engine + 2 elsewhere), **no** TODO/FIXME/HACK.

Tech-debt-by-comment is essentially nil. The debt in this repo is **structural** (unwired pfc, divergent
deterioration model, untested feature toggles), not annotated — which is *more* dangerous because it is invisible to grep.

---

## R8. CONFIG VALIDATION + VERSIONING

Fed `build_engine_from_dict` malformed configs (live build path). Results:

| Case | Result | Note |
|---|---|---|
| (a) facility missing `coordinates` | **SILENT-ACCEPT** | defaults to `(0,0)` — geo silently wrong |
| (b) edge → nonexistent facility | **CRASH** `ConfigurationError` | ✅ the one real cross-block guard |
| (c) negative bed count | **CRASH** `ValidationError` | ✅ Pydantic `ge=0` catches it — **contradicts the "silent-accept" expectation** |
| (d) unknown key `weather: cloudy` | **SILENT-ACCEPT** | ignored, no warning |
| (e) missing `facilities` section | **CRASH** `ConfigurationError` | but **wrong reason** ("edge references unknown dest") — misleading error |
| (f) facility lacks `has_surgery` | **SILENT-ACCEPT** | defaults `False` — old files silently lose new features (F9 confirmed) |
| (x) missing `edges` section | **SILENT-ACCEPT** | builds isolated facilities, runs with no routing |
| (y) facility missing `role` | **CRASH** raw `KeyError: 'role'` | **unguarded** — not a `ConfigurationError` |
| (z) facility `or_tables: 2` | **SILENT-ACCEPT but DROPPED** | see R15 |

**Schema version:** ❌ **none** in any of the 5 presets (`coin/lsco/hadr/specops/iron_bridge`) — confirmed
by loading each. No `schema_version`/`version`/`config_version` key. No migration path.

**Refinement vs Forward F9:** negative numeric capacity **is** caught (Pydantic `ge=0`), and a missing
`role` raises a **raw `KeyError`** rather than a clean `ConfigurationError`. So validation is *partial and
inconsistent*: Pydantic guards numeric bounds, the builder guards edge integrity, but everything else
(unknown keys, missing sections, missing string fields, capability fields) is silent-default or raw-crash.

## R15. CONFIG BLOCK COUPLING

- **The one real guard holds:** edge → existing facility builds; edge → `GHOST` raises `ConfigurationError`
  ([builder.py:174-184](../src/faer_dev/config/builder.py#L181)).
- **Silently dropped (builder never reads them):** `or_tables=99 → Facility.or_tables=0`,
  `icu_beds=50 → 0`, edge `threat_level=HIGH →` not stored on edge (edge keeps only `base_time/weight/transport`).
- **Unvalidated cross-block references:** there is no check that a surgical scenario has any
  `has_surgery=True` facility, no check that `transport` modes on edges match any vehicle pool, no check
  that triage_distribution sums to 1.0. Only edge→facility id integrity is enforced.

---

## R11. GRAPH ROUTING CORRECTNESS — works, but **gated behind a second toggle** + legacy starves parallel nodes

`iron_bridge` has two R1 nodes (R1-ALPHA, R1-BRAVO), both reachable from POI-FRONT.

| Config | R1-ALPHA | R1-BRAVO | Finding |
|---|---|---|---|
| **graph ON** (both toggles), beds 8/8 | 124 | 94 | ✅ **both load-balanced** |
| legacy (graph OFF), 8/8 | 223 | **0** | 🔴 first-match **starves the 2nd R1 entirely** |
| graph ON, ALPHA=2 / BRAVO=20 | 30 | 187 | ✅ Dijkstra **shifts to capacity** via congestion |
| graph ON, ALPHA=20 / BRAVO=2 | 214 | 4 | ✅ **flips symmetrically** |
| legacy, any bed split | 236 / 0 | | 🔴 ignores beds completely |

**Critical toggle-coupling finding:** my first R11 run set **only** `enable_graph_routing=True` and got
BRAVO=0 with **zero `get_route` calls** — because the engine only routes via graph when
`enable_extracted_routing` is **also** True ([engine.py:680-684](../src/faer_dev/simulation/engine.py#L680)).
`enable_graph_routing` **alone is inert** and silently falls through to legacy role-walk. This is a real
trap: an operator enabling "graph routing" without also enabling "extracted routing" gets legacy behaviour
with no error.

**Congestion observability (Forward F5 caveat) — VERIFIED observable:** `update_congestion` mutates inbound
edge `weight = base × (1+occupancy/beds)`; `get_travel_time` returns `base_time` (transit duration
unaffected). With both toggles on, congestion **does** shift routing choice (factor reaches 1.0 on the
2-bed node, weight 15→30, Dijkstra reroutes). With one toggle, it has **no** behavioural effect.

## R12. PHASE 1.5 REGRESSION — ✅ clean

All 9 `test_phase1_integration.py` tests pass alongside graph routing (part of the green 99). **9**
graph-routing-specific tests exist (`TestGraphRouting` 6 + `TestGraphRoutingRegression` 3) out of 24 in
`test_routing.py`. **Coverage gap:** the graph regression tests assert equivalence only on **linear**
chains (where Dijkstra ≡ role-walk by construction). The branching-topology behaviour I demonstrated in
R11 (load-balancing two R1s) has **no test** — the single most interesting property of graph routing is unguarded.

---

## R13. LAYER MISCLASSIFICATION — adjudication

| Feature | Forward/Backward label | Red Team adjudication |
|---|---|---|
| `enable_typed_emitter` | SURFACE→INTRINSIC seam | **SURFACE.** Verified: OFF vs ON gives byte-identical *simulation* outcomes (R5). It changes event *representation*, not the simulation. Correctly a seam, behaves as surface today. |
| #7 unit definitions | SURFACE (Forward) | **Agree SURFACE** — no engine path consumes them. |
| Facility capability fields | INTRINSIC-dormant | **Confirmed INTRINSIC-but-inert.** R16a proves they change nothing today (86/114 violations) — they are *labels* now, *intrinsic* only once routing reads them (#5). The label/intrinsic distinction is exactly the #5 gap. |
| `enable_graph_routing` | INTRINSIC | **INTRINSIC when paired**, **inert alone** (R11). Its layer is conditional on `enable_extracted_routing`. |
| PFC (`pfc.py`) | INTRINSIC | **INTRINSIC but disconnected** — the *labelled* intrinsic module (`pfc.py`) is not the one that runs; the running one (inline) is untested. The "intrinsic" claim attaches to dead code. |

**No misclassification found that flips a surface feature into a hidden engine-output change.** The
recurring pattern is the opposite: features *labelled* intrinsic are inert/disconnected, so they behave as
surface (or as nothing) until wired.

## R14. CONFIG OVERLAY COMBINATORICS — N/A today, sized for later

Confirmed: **no overlay/composition system.** 5 monolithic presets, 0 compositions → combinatorics N/A.
**If #51/#52 introduce composition**, the test surface would be roughly
**presets × topologies × threat-levels**. With today's assets (5 presets, ~2 distinct topology shapes
[linear coin/lsco/specops, branching iron_bridge], and a notional 3 threat levels) that is **~30 combinations**
before any seed replication — each of which, given R17, would need a *correctness* oracle, not just an
execution check, to be meaningful. Composition multiplies an already-unverified base.

---

## R16. BEHAVIOURAL ASSERTION CAPABILITY

**(a) "No surgical casualty treated at a `has_surgery=False` facility" — NOT enforceable, NOT event-writable.**
Built a scenario (non-surgical R1+R2, surgical R3), 100% T1_SURGICAL arrivals, **both** routing toggles on:
- `TREATMENT_START` events carry **empty metadata** — no `has_surgery`, no surgical-need flag. The property
  **cannot be written from the event stream alone.**
- Joining via `engine.network`: **86 of 114** surgical treatments occurred at **non-surgical** facilities.
  The property is **violated** — routing does not consult capability, even in graph mode.

  *What's missing:* (1) routing must read `has_surgery` (#5); (2) `TREATMENT_*` events must carry a
  capability field and a surgical-need field for a pure event-stream assertion. Both are feature work.

**(b) "Golden-hour compliance rises with R1 beds" — NOT expressible via the harness.**
`EnsembleBuilder(__init__/run)` exposes **no** bed-count / scenario-override parameter (verified by
signature inspection). The property is only computable via a **manual `build_engine_from_dict` dict-edit
sweep** (workaround shown). Even then it is statistically meaningless today: `golden_hour.total_tracked ≈ 8`
per run, and varying R1 beds 1→2→4→12 produced **non-monotonic, noisy** `pct_within_60` (`0.3 / 0.6 / 0.6 / 0.6`
at seed 42, swinging across seeds) — because the COIN bottleneck isn't R1 beds and capability routing is absent.

  *What's missing:* a `run(scenario_overrides=…)` / sweep parameter on `EnsembleBuilder`, plus enough tracked
  patients per run for the metric to be stable.

---

## R17. STUB-PASSES-TESTS — the HEPHAESTUS check ⭐ **most important MVP-risk finding**

I deliberately broke "done" intrinsic logic and ran the **full suite** (reverted via `git checkout` after each;
suite confirmed green post-revert).

| Break | What was corrupted | Suite result | Interpretation |
|---|---|---|---|
| **A** | **Extracted** `routing.get_next_destination` ignores role (returns first facility) | **20 failed** / 79 passed | Caught — because the *inline* path is an uncorrupted oracle for the `legacy==extracted` checks. |
| **B** | **Both** inline + extracted routing corrupted **identically** | **7 failed** / 92 passed | Mostly invisible. The 7 catches came **only** from (i) the still-uncorrupted **graph-routing** oracle and (ii) one absolute assertion `test_t1_surgical_bypasses_r1`. Corrupt all three identically and even these pass. |
| **C** | **Triage sampling always returns T3** (single implementation, no oracle) | 🔴 **99 passed / 0 failed** | **Completely invisible.** Every casualty mis-triaged, zero tests notice. |

**Conclusion:** the suite tests **EXECUTION and DIFFERENTIAL EQUIVALENCE**, not **CORRECTNESS**. Its
protection is real *only* where two independent implementations exist to cross-check (the EX-1/2/3
extractions and graph-vs-legacy). For any **single-implementation** mechanism — triage assignment, severity
sampling, the inline deterioration model, capability routing — **there is no oracle and no test would catch a
wrong answer.**

This was **predicted** from the static findings and **verified**: routing already ignores capability (R16a),
DCS never emits, the running deterioration model diverges from the tested one (Backward B2), and the 6 feature
toggles have no ON-path tests. R17 Break C is the proof that these are not isolated gaps but a **systemic
property** of the test strategy.

---

## RED TEAM SYNTHESIS — what is actually safe to build on

**GREEN (verified solid):**
- Determinism (R1), replication isolation (R9), performance & memory (R3/R6/R10).
- The 3 differential extractions (routing/metrics/emitter) — genuinely seed-matched (R5).
- Graph routing congestion load-balancing **when both toggles are on** (R11).
- Layer boundaries (Backward B5, no violations) and the hold-gate *logic* (R4 — correct, just untested).

**RED (false-confidence risks — fix before any surface MVP):**
1. **Test suite proves execution, not correctness (R17).** Add absolute behavioural oracles (golden
   event-trace fixtures, distribution assertions) — not just `legacy==extracted`. *Highest priority.*
2. **Capability routing absent (R16a, #5).** 86/114 surgical patients treated at non-surgical facilities.
   Every capability sweep is meaningless until routing reads `has_surgery`.
3. **PFC: the tested module is not the running module (R4, B2).** Inline engine deterioration (0.20×
   ladder) diverges from tested `pfc.py` (linear 0.01); inline path has 0 integration tests.
4. **DCS unverifiable (#28).** Tree never invoked, event never emitted, `requires_dcs` never read.
5. **6 feature toggles have no ON-path tests;** `enable_graph_routing` is silently inert without
   `enable_extracted_routing` (R11); `ccp.py` has 0 tests.
6. **Acceptance harness gaps (R16b):** no scenario-override/bed-sweep param on `EnsembleBuilder`, no
   capability/surgical fields on `TREATMENT_*` events, no run-to-completion fixture. The canonical MVP
   acceptance tests (capability enforcement, bed-count sweep) are **not writable today.**
7. **Config layer (R8/R15):** no schema version, silent field-drop (`or_tables/icu_beds/threat_level`),
   inconsistent validation (Pydantic guards numbers, raw `KeyError` on missing `role`).

**A surface feature (#43 mining, #44/#45 ensemble/sweep, #53 Engine Room) built now would sit on an
unverified intrinsic core.** Close R17 (correctness oracles) and #5 (capability routing) first; they gate
every meaningful acceptance test below them.

---
*Red Team complete. 17/17 answered, all via live execution. Break-experiments reverted; `git status` clean; `99 passed` confirmed post-revert.*
