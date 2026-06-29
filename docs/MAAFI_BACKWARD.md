# MAAFI BACKWARD — Codebase Interrogation (FAER-MIL, layer-aware)

**Agent:** Backward (dead code, redundant abstractions, expendable features)
**Date:** 2026-06-17
**Method:** Read-only static analysis + `pytest -q`. Every claim carries a `file:line` citation.
**Layer rule applied:** Removing an INTRINSIC feature cascades (surface features wrapping it become
meaningless). Removing a SURFACE feature never invalidates an intrinsic one.

> **Three Forward claims were tested against source and FAILED — see the
> "Corrections to Forward" box below.** Read it first; it changes the risk model.

---

## ⚠️ Corrections to Forward (verified against source)

| # | Forward said | Reality | Evidence |
|---|--------------|---------|----------|
| C1 | `mining.py` needs `pm4py` (not installed); would ImportError | `mining.py` imports **only stdlib + internal** (`statistics`, `dataclasses`, `typing`, `faer_dev.events.*`). Zero `pm4py`. Imports cleanly. | `src/faer_dev/events/mining.py:13-20` |
| C2 | (Implied) all SimPy yields live in `engine.py` (5-yield invariant) | **10 SimPy yields live OUTSIDE engine.py** — `arrivals.py` (3), `transport.py` (6), `ccp.py` (1). The invariant is violated by current code (or is an unmet Phase-1 target). | `arrivals.py:149,166,210`; `transport.py:319,409,429,441,471,477`; `ccp.py:44` |
| C3 | `delay.py` / `xes_exporter.py` analytics deps suspect | Both import **only stdlib + internal**; no third-party deps anywhere in the events/ analytics trio. | `delay.py:9-15`; `xes_exporter.py:14-21` |

Everything else from Forward is **confirmed** (pfc/mining/delay import-orphan status, dead `enable_extracted_pfc`
toggle, phantom DCS, untested feature toggles, written-but-unread schema fields).

---

## B1. Import Orphans

Confirmed orphans (never imported by any other `src/` module):

| Module | Orphan in src? | Imported by tests? | Layer if wired | Notes |
|--------|----------------|--------------------|----------------|-------|
| `src/faer_dev/pfc.py` | ✅ yes | yes — `tests/test_pfc.py:13` | **INTRINSIC** | Pure decision logic (`evaluate_hold`, `compute_deterioration`). Would gate PFC escalation; currently hardcoded inline. |
| `src/faer_dev/events/mining.py` | ✅ yes | no | **SURFACE** | Process-mining analytics over the event store (bottleneck/variant/throughput). Reporting only. |
| `src/faer_dev/events/delay.py` | ✅ yes | no | **SURFACE** | Delay-propagation / cascade tracing. Post-run analysis only. |
| `src/faer_dev/events/xes_exporter.py` | ✅ yes | no | **SURFACE** | XES export for external process-mining tools. Reporting only. |

**Cascade implication:** `pfc.py` is the only INTRINSIC orphan. Wiring it would change simulation
outcomes (see B2 — it competes with inline logic that uses a *different* deterioration model). The three
events/ orphans are SURFACE: they can be deleted with zero effect on simulation results, or wired purely
for analytics value.

---

## B2. Inline Duplication (all INTRINSIC)

`engine.py` carries inline hold/PFC logic that duplicates the extracted-but-unwired `pfc.py`:

| Inline block in `engine.py` | Lines | Mirrors in `pfc.py` | Status |
|-----------------------------|-------|---------------------|--------|
| Hold + PFC escalation loop | `706-847` | `evaluate_hold()` `pfc.py:41-93` | Decision logic re-implemented inline |
| PFC escalation (severity ≥ threshold) | `751-782` | `evaluate_hold()` → `ESCALATE_TO_PFC` | Duplicate |
| PFC ceiling + retriage | `784-821` | (no extracted equiv. for the action) | Inline-only |
| `_retriage_for_deterioration()` | `310-348` | `compute_deterioration()` `pfc.py:96-109` | **Model MISMATCH** |
| `_mark_pfc_started()` / `_finalize_pfc_if_active()` | `355-395` | (no extracted equiv.) | Inline-only state machine |

**Critical mismatch:** inline `_retriage_for_deterioration()` uses a **0.20 × multiplier** step model
with a severity-escalation ladder (`engine.py:324-343`), while `pfc.py:compute_deterioration()` uses a
**linear `base_rate=0.01`** model. These are not behaviourally equivalent — wiring `pfc.py` without
reconciling the model would change outcomes. This is the single highest-risk refactor target.

Other extracted modules are **intentional toggle-gated dual paths**, not accidental duplication:

| Module | Inline legacy in engine | Extracted | Gate |
|--------|-------------------------|-----------|------|
| routing | `_get_next_destination()` `84-122` | `routing.get_next_destination()` | `enable_extracted_routing` |
| metrics | `_legacy_get_metrics()` `1317-1378` | `metrics.compute_metrics()` | `enable_extracted_metrics` |
| emitter | `_log_event()` dispatch `486-536` | `TypedEmitter.emit()` | `enable_typed_emitter` |

These three are seed-matched regression-tested (see B4) and are safe to keep or collapse once the toggle is permanently ON.

---

## B3. Yield-Point Audit (5-yield invariant **VIOLATED**)

All SimPy yields in `src/`:

**Outside `engine.py` — 10 yields (violations of the stated invariant):**
- `simulation/arrivals.py:149` `yield self.env.timeout(inter_arrival)`
- `simulation/arrivals.py:166` `yield self.env.timeout(inter_mascal)`
- `simulation/arrivals.py:210` `yield self.env.timeout(wait)`
- `simulation/transport.py:319` `yield self.env.timeout(interval)`
- `simulation/transport.py:409` `yield self.env.timeout(self.batch_wait)`
- `simulation/transport.py:429` `yield req`
- `simulation/transport.py:441` `yield self.env.timeout(trip_time)`
- `simulation/transport.py:471` `yield req`
- `simulation/transport.py:477` `yield env.timeout(trip_time)`
- `simulation/ccp.py:44` `result = yield req | env.timeout(5)`

**Inside `engine.py` — 16 yields** (mixture of the canonical 5 conceptual points + treatment/transport
resource requests + one `yield from` delegation to sub-generators at `974`/`978`).

**Verdict:** The "all 5 SimPy yield points stay in engine.py" hard rule (CLAUDE.md Rule 1) is **not met
by the current tree**. Arrivals, transport, and CCP are independent SimPy generators. Either (a) the rule
is an aspirational Phase-1 target not yet reached, or (b) these three files were extracted prematurely
before the yield-centralisation work. Both `transport.py:429/471` (`yield req`) and `ccp.py:44`
(`yield req | timeout`) are resource-request yields — the exact pattern NB44 was meant to prove
exception-safe before delegation. **This contradicts the Forward framing and should be reconciled with
CLAUDE.md before any Phase-3 `yield from` work.**

---

## B4. Test Depth

| Module | Tests | Type | Toggle OFF↔ON seed-matched? |
|--------|-------|------|------------------------------|
| `routing.py` | 24 + regression | unit + integration-through-engine | ✅ yes (`test_routing.py:166-185`, seeds 42 & 99) |
| `metrics.py` | 7 + regression | unit + integration-through-engine | ✅ yes (`test_metrics.py:117-142`, seeds 42 & 99) |
| `emitter.py` | 11 + regression | unit + integration-through-engine | ✅ yes (`test_emitter.py:138-175`, seeds 42 & 99) |
| `pfc.py` | 13 | **unit-only** (pure functions) | ❌ no — toggle never wired (`test_phase1_integration.py:31`) |
| `ccp.py` | **0** | none | ❌ none |

**The 6 feature toggles with ZERO toggle tests (confirmed):**

| Toggle | Read in engine | ON-path coverage |
|--------|----------------|------------------|
| `factory_mode` | `engine.py:163,186` | none |
| `decision_mode` | **nowhere** (defined `mode.py:46`, never read) | none |
| `enable_department_routing` | `engine.py:263,713,973` | none |
| `enable_vitals` | `engine.py:253` | none |
| `enable_atmist` | `engine.py:445,472` | none |
| `enable_ccp` | `engine.py:243` | none |

Their ON code paths exist but are never exercised — every regression suite runs the default-OFF config.
`enable_ccp` ON-path drives the entirely-untested `ccp.py` and the only PFC medic-resource yield
(`ccp.py:44`). Highest test-debt cluster in the repo.

---

## B5. Boundary Violations (HC-5 / HC-6) — **NONE**

Clean across the board:
- `import simpy` / `from simpy` in `decisions/` → none
- `import networkx` in `decisions/` → none
- `import py_trees` in `simulation/` or `network/` → none
- `import streamlit` in `simulation/` → none

Layer separation is the healthiest part of the codebase. ✅

---

## B6. Call-Site Verification

| Symbol | Defined | Called in live code? | Tested? | Layer | Verdict |
|--------|---------|----------------------|---------|-------|---------|
| `build_department_routing_tree` (#27) | `decisions/trees.py:160` | ❌ no (exported `decisions/__init__.py:74`, never invoked) | ❌ | SURFACE | **PHANTOM** |
| `build_dcs_tree` (#28) | `decisions/trees.py:221` | ❌ no (exported `__init__.py:75`, never invoked) | ❌ | SURFACE | **PHANTOM** — and DCS event never emitted (B7), so "done" is unverifiable |
| `MASCALTriageShift` (#30) | `core/triage.py:71` | ✅ `casualty_factory.py:51,74` (every casualty) | implicit | INTRINSIC | **LIVE** |
| `compute_survivability` (#40) | **not in src/** (only `compute_survivability_at_T` in `demo_app/components/survivability_curve.py:20`) | n/a | n/a | SURFACE | **NOT IN ENGINE** — #40 "done" claim refers to UI helper, not simulation |
| `GoldenHourView` (#41) | `analytics/views.py:83` | ❌ tests only (`test_analytics.py:194`) | ✅ unit + integration | SURFACE | View, decoupled — analytics-only |
| `FacilityLoadView` (#42) | `analytics/views.py:44` | ❌ tests only (`test_analytics.py:193`) | ✅ unit + integration | SURFACE | View, decoupled — analytics-only |
| `compute_deterioration` (#21, pfc) | `pfc.py:96` | ❌ engine uses inline `_retriage_for_deterioration()` instead | ✅ `test_pfc.py:124` | INTRINSIC | **UNUSED** — overridden by inline model (see B2) |

**High-risk:** the two INTRINSIC entries (`build_dcs_tree`, `compute_deterioration`) are "done"-without-being-wired. Both
are claimed complete but neither affects a running simulation. SURFACE phantoms (`build_department_routing_tree`,
the views) are low-risk to delete or wire later.

---

## B7. Phantom Event Types

Declared-but-never-emitted (4 total):

| Event | Declared | Emitted? | Note |
|-------|----------|----------|------|
| **DCS** | `engine.py:55` (KNOWN_EVENT_TYPES) + `models.py` registry | ❌ never | Confirms Forward. `build_dcs_tree` (#28) sets DCS state that is never logged → #28 completion **unverifiable from the event stream**. |
| **QUEUE_ENTERED** | `models.py:302` | ❌ never | No `_log_event("QUEUE_ENTERED")` anywhere |
| **HOLD_RELEASED** | `models.py:303` | ❌ never | `engine.py:842` finalizes with `reason="hold_released"` but emits no event |
| **BT_DECISION** | `models.py:305` | ❌ never | BTObserver exists in `decisions/` but is not wired to the engine |

All other ~18 declared types are emitted live (ARRIVAL, TRIAGE, TRANSIT_*, TREATMENT_*, DISPOSITION,
MASCAL_*, HOLD_START/RETRY/TIMEOUT, PFC_START/END/CEILING_EXCEEDED, R1/R2_DEPT, ATMIST_HANDOVER, NINE_LINER).

---

## B8. Orphaned Analytics Deps

| File | Third-party imports | Declared in pyproject? | Import status |
|------|---------------------|------------------------|---------------|
| `events/mining.py` | **none** (stdlib + internal only) | n/a | ✅ imports cleanly |
| `events/xes_exporter.py` | **none** (`xml.etree`, `datetime` stdlib) | n/a | ✅ imports cleanly |
| `events/delay.py` | **none** (stdlib + internal only) | n/a | ✅ imports cleanly |

`pyproject.toml:10-19` deps: simpy, numpy, networkx, pydantic, py-trees, pyyaml, streamlit, plotly.
**`pm4py` is NOT a dependency of any file** — Forward's claim that `mining.py` needs `pm4py` is **false**
(see C1). These three orphans are pure-Python and runnable today; their only problem is that nothing
imports them.

---

## B9. Test Health

```
99 passed in 0.41s
```
**Confirmed: 99 passed / 0 failed / 0 skipped / 0 xfail / 0 xpass.**

---

## B10. Dead-Toggle Scan

`SimulationToggles` @ `decisions/mode.py:37-59`.

| Toggle | Read where | Status | Layer |
|--------|-----------|--------|-------|
| `enable_extracted_pfc` (`mode.py:56`) | **nowhere in src/** (grep empty) | **DEAD** — gates nothing; `pfc.py` unimported | INTRINSIC (if ever wired) |
| `decision_mode` (`mode.py:46`) | **nowhere in engine** | **DEAD/structural** — defined, never branched on | — |
| `enable_event_store` (`mode.py:50`, default **True**) | `engine.py:525,564` | **Always-ON** — never set False in any config/test | SURFACE (gates analytics publish only) |

`enable_extracted_pfc` is the canonical dead toggle (matches Forward). `enable_event_store` is read but
its OFF path is never tested — disabling it would break analytics but not simulation outcomes (SURFACE),
so it is low-risk but represents an untested branch.

---

## B11. engine.py Anatomy

**Total: 1,378 lines.**

| Region | Lines | ~LOC | Kind |
|--------|-------|------|------|
| Imports / constants | 1-77 | ~77 | infra |
| `_get_next_destination()` (legacy routing fallback) | 84-122 | ~39 | toggle-gated dual path |
| `__init__` | 131-254 | ~124 | infra |
| facility/route/subsystem setup | 256-308 | ~50 | infra |
| **`_retriage_for_deterioration()` (inline PFC legacy)** | 310-348 | ~39 | **inline legacy (INTRINSIC)** |
| **PFC state machine** (`_mark_pfc_started`, `_finalize_pfc_if_active`) | 355-407 | ~50 | **inline legacy (INTRINSIC)** |
| ATMIST / 9-liner / event logging | 409-572 | ~160 | infra + dispatch |
| arrival / mascal / congestion / finalize | 574-645 | ~70 | intrinsic |
| **`_patient_journey()` main generator** | 647-980 | ~334 | **core intrinsic** |
| ↳ **inline hold + PFC block** (within journey) | 706-847 | ~142 | **inline legacy (INTRINSIC)** |
| department resolve + treatment | 982-1178 | ~196 | core intrinsic |
| vehicle return / arrival process | 1180-1227 | ~47 | intrinsic (partly deprecated) |
| `run()` / `step()` / `get_metrics()` | 1229-1315 | ~85 | infra |
| **`_legacy_get_metrics()` (inline metrics fallback)** | 1317-1378 | ~62 | toggle-gated dual path |

**Composition estimate:**
- Active intrinsic simulation logic: **~33%**
- Inline legacy (PFC/hold/retriage duplication, always-on): **~6%** (~80 LOC) ← B2 refactor target
- Toggle-gated legacy fallbacks (routing + metrics): **~7%** (~100 LOC, safe to drop when toggles pinned ON)
- Infrastructure (init, logging, ATMIST, helpers): **~29%**
- Whitespace/comments: **~18%**

The ~80 LOC of always-on inline PFC legacy (`310-348`, `355-407`, `706-847`) is the concrete debt:
it is INTRINSIC, untested at the toggle level, and uses a deterioration model that diverges from the
extracted `pfc.py`.

---

## B12. Unused Schema Fields

`core/schemas.py`.

### Casualty (`schemas.py:70-143`)
| Field | Written? | Read? | Layer | Note |
|-------|----------|-------|-------|------|
| `requires_blood` (115) | no | no | INTRINSIC | would gate transfusion routing |
| `requires_dcs` | yes `engine.py:213` | **no** | INTRINSIC | written, never gates routing — pairs with phantom DCS (B7) |
| `is_mascal_casualty` (89) | yes `casualty_factory.py:93` | no | INTRINSIC | could drive triage shift / segregation |
| `mascal_event_id` (90) | yes `casualty_factory.py:94` | no | SURFACE | audit tag only |
| `treatment_history` (122) | no (default `[]`) | no | INTRINSIC | would inform re-routing |
| `sex` (124) | no | no | INTRINSIC | clinical decision input (ATMIST) |
| `origin_position` (125) | no | no | SURFACE | geo tracking only |

### Facility (`schemas.py:145-179`) — **all 7 capability/capacity fields unread**
| Field | Read? | Layer |
|-------|-------|-------|
| `or_tables` (154) | ❌ | INTRINSIC — surgical capacity gating |
| `icu_beds` (155) | ❌ | INTRINSIC — ICU capacity |
| `ventilators` (156) | ❌ | INTRINSIC — ventilator availability |
| `has_surgery` (162) | ❌ | INTRINSIC — gates T1_SURGICAL routing |
| `has_blood` (163) | ❌ | INTRINSIC — blood availability |
| `has_imaging` (164) | ❌ | INTRINSIC — imaging pathway gating |
| `has_lab` (165) | ❌ | INTRINSIC — lab pathway gating |

**Confirms Forward.** The entire Facility capability model is declared but never consulted by the
network builder or routing logic — every facility is effectively treated as fully capable. These are
**INTRINSIC dormant features**, not dead code: reading them would materially change routing and
treatment. They represent unbuilt capability, not removable cruft.

---

## Priority Synthesis (layer-aware)

**INTRINSIC debt — wiring/removal changes simulation outcomes (handle with seed-matched gates):**
1. Inline PFC/hold legacy (~80 LOC, `engine.py:310-348,355-407,706-847`) duplicates `pfc.py` with a
   **divergent deterioration model**. Reconcile model before wiring `enable_extracted_pfc` (B2, B6, B10, B11).
2. `pfc.py` + `enable_extracted_pfc` are extracted/tested but **completely unwired** (B1, B10).
3. **5-yield invariant violated** — 10 SimPy yields outside `engine.py` in arrivals/transport/ccp,
   including resource-request yields (`yield req`) that need NB44 exception-safety proof (B3).
4. Facility capability fields (7) + Casualty clinical fields are **dormant intrinsic features** never
   read by routing (B12). Unbuilt capability, not cruft.
5. `build_dcs_tree` (#28) + DCS event + `requires_dcs` form a fully-declared, never-emitted intrinsic
   path — "done" is unverifiable (B6, B7, B12).
6. `ccp.py`: **0 tests**, but `enable_ccp` ON-path drives a live SimPy yield (B4).

**SURFACE expendables — safe to delete or defer with zero outcome impact:**
- `mining.py`, `delay.py`, `xes_exporter.py` — import orphans, pure-Python, analytics-only (B1, B8).
- `build_department_routing_tree`, `GoldenHourView`, `FacilityLoadView` — phantom/test-only views (B6).
- Phantom events QUEUE_ENTERED / HOLD_RELEASED / BT_DECISION (B7).
- `mascal_event_id`, `origin_position` schema fields (B12).

**Healthiest:** layer boundaries (B5, zero violations) and the toggle-gated routing/metrics/emitter
extractions (B4, seed-matched regression-tested).
