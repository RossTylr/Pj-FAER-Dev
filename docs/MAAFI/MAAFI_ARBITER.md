# MAAFI ARBITER — Final Adjudication (FAER-MIL, layer-aware)

**Agent:** Arbiter (conflict resolution + tiered verdict)
**Date:** 2026-06-17
**Inputs:** [MAAFI_FORWARD.md](MAAFI_FORWARD.md), [MAAFI_BACKWARD.md](MAAFI_BACKWARD.md), [MAAFI_CROSS.md](MAAFI_CROSS.md), [MAAFI_REDTEAM.md](MAAFI_REDTEAM.md)
**Final tiers + acceptance verdict:** [MAAFI_VERDICT.md](MAAFI_VERDICT.md)

## Scoring rubric (5-axis, split-value)

| Axis | Weight | Applies to |
|------|--------|-----------|
| Mechanistic fidelity | 0.25 | INTRINSIC only (SURFACE scores 0) |
| Analytical utility | 0.15 | SURFACE only (INTRINSIC scores 0) |
| Parsimony | 0.20 | both |
| Robustness | 0.20 | both |
| Readiness | 0.20 | both |

The split value axis gives intrinsic features a built-in 10-point edge (0.25 vs 0.15).
**HARD RULE enforced throughout:** no SURFACE feature may sit in a higher tier than the
INTRINSIC feature it depends on (Cross C13 + C14 maps). Verified in A8.

**The decisive cross-cutting fact (R17):** the suite tests *execution and differential
equivalence*, not *correctness*. Forcing triage→always-T3 passed 99/99. Therefore
"Readiness" and "Robustness" for every single-implementation intrinsic mechanism are
capped low until correctness oracles exist — this is why the foundation layer (A11)
outranks all feature work.

---

## A1. FORWARD vs RED TEAM CONFLICTS

For each feature where Forward implied easy/done and Red Team found it untested or
unimplemented, adjudicated against source. Verdict ∈ {CONFIRMED | HARDER THAN CLAIMED |
NOT ACTUALLY DONE}.

| # | Feature | Layer | Forward | Red Team | **ARBITER VERDICT** | Basis |
|---|---------|-------|---------|----------|---------------------|-------|
| **pfc.py wiring** (#21/#31–33) | INTRINSIC | ranked #1, "lowest marginal cost — just flip the toggle" | tested module ≠ running module; inline path 0 integration tests | **HARDER THAN CLAIMED** | `enable_extracted_pfc` is checked nowhere (B10); inline `_retriage_for_deterioration` uses 0.20× ladder, `pfc.py` uses linear 0.01 (B2/C4). Not a toggle flip — a **model-reconciliation decision**. Forward's #1 "freebie" is a trap. |
| **#5** capability routing | INTRINSIC | "greenfield wiring on an existing seam, not blocked" | unimplemented; 86/114 surgical patients treated at non-surgical facilities (R16a) | **NOT ACTUALLY DONE** (but cheapest real lever) | Seam genuinely exists (`network.facilities[fac_id]` in hand at `routing.py:88-96`/`144-148`, C1). Flags already parsed (C14). One routing reader; no builder change. Forward right on cost, Red Team right on status. |
| **#28** DCS decision | INTRINSIC | `build_dcs_tree` exported | tree never ticked, `DCS` event never emitted, `requires_dcs` written-never-read | **NOT ACTUALLY DONE** | Phantom closed loop (C4, B6, B7). Two parallel DCS notions that never meet: rule-based `requires_dcs` (live, biases dept only) vs BT `decision_dcs` (phantom). "Done" is unobservable and unverifiable. |
| **#30** MASCAL triage shift | INTRINSIC | live | live but no assertion on the shift | **CONFIRMED (live) — but CORRECTNESS BLIND** | `MASCALTriageShift` runs every casualty (`casualty_factory.py:51,74`, B6 LIVE). No oracle asserts the shift is correct (R2 MED, R17). Wired ≠ verified. |
| **6 feature toggles** (`factory_mode`, `decision_mode`, `enable_department_routing`, `enable_vitals`, `enable_atmist`, `enable_ccp`) | INTRINSIC (5) + 1 dead | exist | zero ON-path tests; `decision_mode` read nowhere; `ccp.py` 0 tests | **HARDER THAN CLAIMED** (`decision_mode`: NOT ACTUALLY DONE — dead) | B4/B10/R2. ON paths exist but every regression runs default-OFF. `enable_ccp` ON drives the only PFC medic-resource yield (`ccp.py:44`) on an entirely untested module. |
| **graph routing** (Phase 1.5) | INTRINSIC | "done" | works **only when paired** with `enable_extracted_routing`; inert alone (R11) | **HARDER THAN CLAIMED** | Silent-toggle trap: `enable_graph_routing` alone falls through to legacy role-walk (starves 2nd R1, 223/0). Load-balancing real but branching-topology behaviour has no test (R12). Needs a config guard. |
| **#40** survivability | SURFACE | "done" | UI helper only, not in engine | **CONFIRMED (as surface)** | `compute_survivability_at_T` lives in `demo_app/` (B6). The "done" claim is a UI artefact, correctly surface. |
| **#43** process mining | SURFACE | needs pm4py | stdlib only, import-orphan | **CONFIRMED runnable, NOT wired** (Forward factual error) | `mining.py` imports only stdlib+internal (C1/B8). Runnable today; nothing imports it. Forward's pm4py claim is **false**. |

**A1 net:** every intrinsic "done" claim collapses to "runs" or "exists unwired." The only
genuinely CONFIRMED-and-correct items are the three differential extractions
(EX-1/2/3) and the decoupled analytics views — none of which is a clinical mechanism.

---

## A2. SYNERGY BUNDLE MERGE RISK

| Bundle | Layers | Shared file? | Dev mode | Risk + note |
|--------|--------|--------------|----------|-------------|
| **#1 + #8** multi-POI + unit positioning | I × I | `arrivals.py` + `engine.py` arrival handler; #8 also needs a **new `units` config block** (C14) | **Sequential** — #1 first (thread `origin` through `ArrivalRecord`), #8 layers source→POI weighting on top | #8 cannot be configured at all today (no `units` block). #1 carries the determinism hazard (shared `_rng`, C5) — needs per-POI `rng.spawn`. Don't merge; #1 lands, #8 follows. |
| **#12 + #13** vehicle types + litter capacity | I × I | `topology.py` (DiGraph) + `transport.py` | **Sequential, both blocked on C3** | Both require **DiGraph→MultiDiGraph** first (C3) — a foundational data-structure change touching every `topology.py` accessor. #14 multi-modal **also** blocks here. Treat the MultiDiGraph promotion as a shared prerequisite, then #12/#13/#14 are siblings. |
| **#20 + #23** vitals + re-triage | I × I | `vitals.py` (gated OFF) + inline `_retriage_for_deterioration` (`engine.py:310-348`) | **Sequential after the PFC model decision** | #23 currently consumes #21 via return-value + in-place `severity_score` mutation, NOT the blackboard, and NOT `pfc.py` (C4). Reconcile the 0.20 vs 0.01 model before either is trustworthy. |
| **#2 + #3 + #4** departments triple | I × I × I | `departments.py` + `engine.py` `_treat_in_department` (`973-980`) | **Parallel-ish, one shared prerequisite** | Mechanism is **already built and toggle-gated OFF** — three capacity regimes pre-exist (C7). Real work is the **engine→blackboard writer** (C2, shared with #53/#58) + ON-path tests (B4: 0 today), not yield restructuring. Wire the writer once; the triple lights up together. |
| **#44 + #45** ensemble + sweep | S × S | `ensemble.py` | **Sequential, #45 wraps #44** | Low mechanism risk. Both gated behind the `scenario_overrides` threading point (`ensemble.py:190`, C9) AND behind the intrinsics they vary (#5/#1/#10) — sweeping `has_surgery` measures nothing until #5 lands. |

**Bundles that genuinely parallelise:** #5 (routing) ∥ the blackboard writer (departments)
∥ the foundation oracles — disjoint files, no shared state. **Bundles that serialise on a
hidden prerequisite:** #12/#13/#14 (MultiDiGraph), #2/#3/#4 (blackboard writer),
#20/#23 (PFC model decision).

---

## A3. BACKWARD EXPENDABILITY vs FORWARD DEPENDENCY (cross-layer)

| Backward flagged expendable | Layer | Does any Tier 0/1/2 feature depend on it? | Verdict |
|-----------------------------|-------|-------------------------------------------|---------|
| `mining.py` (#43) | SURFACE | No Tier 0/1/2 dependency | **Safe to defer** (Tier 4). Runnable but no MVP feature needs it. |
| `delay.py` | SURFACE | No | **Safe to defer/delete** (Tier 4). |
| `xes_exporter.py` | SURFACE | #62 MNEMOSYNE (Tier 4) only | **Safe to defer** — its only consumer is itself Tier 4. |
| `build_department_routing_tree` (#27) | SURFACE→ gates #4 BT path | #4 departments (Tier 3) reads the dept BT | **Keep, don't delete** — it is the consumer the C2 writer feeds. Phantom now, prerequisite later. |
| `GoldenHourView` (#41) / `FacilityLoadView` (#42) | SURFACE | They ARE Tier 0 activations (tested, decoupled) | **Keep — these are assets, not cruft.** |
| Phantom events `QUEUE_ENTERED` / `HOLD_RELEASED` / `BT_DECISION` | SURFACE | #53 Engine Room benefits from `BT_DECISION`; `HOLD_RELEASED` aids PFC stream #34 | **Keep declarations, add emit sites later** — cheap, no harm. |
| `mascal_event_id`, `origin_position` schema fields | SURFACE | None | **Safe to ignore** (audit/geo tags). |
| `compute_deterioration` (#21, `pfc.py`) | INTRINSIC | #23 re-triage, #33 PFC ceiling, #62 export | **DO NOT DELETE** — it is the reconciliation target, not dead weight. The inline model is the one to retire *after* reconciliation, not `pfc.py`. |

**Cross-layer catch:** the only "expendable" items a future Tier-1/2/3 feature depends on
are `pfc.py` (gates #23/#33), `build_department_routing_tree` (gates #4 BT consumer), and
the phantom event declarations (gate #34/#53 observability). All are **dormant
prerequisites, not removable cruft.** The three events/ analytics orphans
(`mining`/`delay`/`xes_exporter`) are the only truly free-to-park items.

---

## A4. STRANGLER / ARCHITECTURE HEALTH — where new intrinsic work goes

**Composition (B11):** `engine.py` = 1,378 lines. ~33% active intrinsic, ~29% infra,
~18% whitespace/comments, **~7% toggle-gated legacy fallbacks** (routing+metrics, safe to
drop once toggles pinned ON), **~6% always-on inline PFC legacy** (~80 LOC, `310-348`,
`355-407`, `706-847`) — the concrete debt: intrinsic, untested at the toggle level, and
running a deterioration model that **diverges** from extracted `pfc.py`.

**The 5-yield invariant is already VIOLATED (B3, corrects Forward):** 10 SimPy yields live
outside `engine.py` — arrivals (3), transport (6), ccp (1) — including resource-request
`yield req` patterns (`transport.py:429/471`, `ccp.py:44`) that CLAUDE.md Rule 1 says NB44
must prove exception-safe before any Phase-3 `yield from` delegation.

**ARBITER POSITION:** The "all 5 yields in engine.py" rule is **already an unmet
aspiration, not a live invariant.** Given that:

1. **New intrinsic work goes in extracted modules, NOT engine.py** — the codebase has
   already chosen the strangler/extracted-module pattern (arrivals, transport, ccp,
   routing, metrics, pfc all live outside engine.py). Adding #5's capability filter to
   `routing.py` (extracted) and the blackboard writer as an engine→module callback
   *continues* the established direction. Piling more into `engine.py` would deepen the
   ~6% inline-legacy debt.
2. **The ~80 LOC inline-PFC block is the one exception that must be retired in place** —
   it is the only always-on intrinsic duplication, and it must be reconciled with `pfc.py`
   (not extended) before `enable_extracted_pfc` becomes real.
3. **Reconcile B3 before Phase 3.** The yield-centralisation question is a CLAUDE.md
   contradiction that should be resolved explicitly (amend the rule to "yields may live in
   extracted SimPy generators, proven exception-safe per NB44") rather than silently
   carried. This is a documentation/decision task, Tier 1 foundation-adjacent.

Migration health is otherwise **good**: layer boundaries are clean (B5, zero violations)
and the three extractions are seed-matched regression-tested (R5).

---

## A5. COMPLETION MOMENTUM RANKING (top 15)

`momentum = (lines_written / lines_needed) × has_CORRECTNESS_test`. Per R17,
`has_test` now means **has a correctness oracle**; differential-only coverage counts as
**partial (0.5)**, execution-only counts as **0**. This collapses most "done" claims.

| Rank | # | Feature | Layer | written/needed | Correctness test | Momentum | Note |
|------|---|---------|-------|----------------|------------------|----------|------|
| 1 | EX-1 | routing extraction | I | ~1.0 | partial (differential, R17 Break A caught) | **~0.50** | Highest real momentum; the inline oracle still cross-checks it. |
| 2 | EX-2 | metrics extraction | I | ~1.0 | partial (differential) | ~0.50 | Seed-matched (R5). |
| 3 | EX-3 | typed emitter | S→I (behaves S) | ~1.0 | partial (differential) | ~0.50 | Changes representation, not outcomes (R13). |
| 4 | Phase 1.5 | graph routing | I | ~0.9 | partial (linear chains only; branching untested R12) | ~0.45 | Real but trap-gated (R11). |
| 5 | #41 | golden-hour view | S | ~1.0 | yes (unit+integration, decoupled) | ~0.30* | *Surface cap — analytical utility only. |
| 6 | #42 | facility-load view | S | ~1.0 | yes | ~0.30* | Decoupled, tested. |
| 7 | #30 | MASCAL triage shift | I | ~0.9 | none (R17) | **~0.0** | LIVE but no oracle — high written, zero verified. |
| 8 | #21/#31-33 | inline PFC/hold | I | ~0.8 (inline) + extracted `pfc.py` | none on the *running* path (R4) | **~0.0** | Tested code isn't running code. |
| 9 | #16 | return-to-base vehicle | I | ~0.8 | none | ~0.0 | Live in transport.py, unasserted. |
| 10 | #19 | injury-first generation | I | ~0.7 | none (factory_mode ON untested) | ~0.0 | |
| 11 | #5 | capability routing | I | **~0.15** (seam + parsed flags only) | none | ~0.0 | Cheapest to *finish*, but barely written. |
| 12 | #2-4 | departments | I | ~0.7 (mechanism built, gated OFF) | none (B4: 0 ON-path) | ~0.0 | Built, unwired to blackboard, untested. |
| 13 | #20 | vitals trajectory | I | ~0.6 (vitals.py gated) | none | ~0.0 | |
| 14 | #44 | ensemble CI | S | ~0.8 (no override hook) | partial (used in test_analytics) | ~0.15* | Needs `scenario_overrides`. |
| 15 | #28 | BT DCS | I | ~0.5 (tree built, unwired) | none | ~0.0 | Phantom (C4). |

**A5 read:** once `has_test` means *correctness*, the momentum field is brutally flat —
only the four differential-tested extractions and the two decoupled views carry nonzero
momentum, and **none of them is a clinical mechanism.** This is the quantitative form of
the CORRECTNESS BLIND verdict: there is no intrinsic feature with both code AND a
correctness anchor. The MVP must *manufacture* that anchor (oracles) before momentum means
anything.

---

## A6. MVP GROUND TRUTH

Updated 10-feature MVP (claimed LOC from the pre-interrogation verdict; actual LOC = real
remaining work to make it *correct*, not just present).

| # | Name | Layer | Claimed LOC | Actual LOC | Risk | Verdict |
|---|------|-------|-------------|------------|------|---------|
| **F0** | **Foundation: correctness oracles + canonical serialiser + run-to-completion fixture** | enabling (intrinsic-correctness infra) | 0 (not in original MVP) | ~120–180 | **CRITICAL — new** | **MUST PRECEDE ALL.** Did not exist in the prior MVP; R17 makes it mandatory. |
| 5 | Capability-aware routing | INTRINSIC | ~40 | ~40–60 + oracle | MED | Cheapest real lever; one routing reader (C1). Gates R16a + #44/45/50/56/62. |
| 1 | Multi-POI arrivals | INTRINSIC | ~60 | ~80–120 (origin thread + per-POI sub-RNG + **both-toggle guard**) | HIGH | Determinism hazard (C5); silent collapse to one R1 without both toggles (R11). |
| 30 | MASCAL triage shift | INTRINSIC | ~0 (done) | ~20 (trigger wiring + oracle) | MED | Live but unverified; per-POI surge needs #1. |
| 10 | Threat zones | INTRINSIC | ~50 | ~80 (stop dropping `threat_level` + new `threat_zones` block + engine reader) | HIGH | Config silently drops `threat_level` today (C14, R15). |
| 50 | YAML-driven scenarios + `scenario_overrides` | SURFACE (config, gates intrinsic) | ~30 | ~30 + schema_version | MED | One threading point (C9); but no schema version, silent field-drop (R8). |
| 44 | Ensemble CI | SURFACE | ~0 (done) | ~10 (wire `scenario_overrides`) | LOW | Exists; inert without #5/#1/#10. |
| 45 | Sensitivity sweep | SURFACE | ~40 | ~40 | LOW | Wraps #44; meaningless until intrinsics live. |
| 41 | Golden-hour compliance | SURFACE | ~0 (done) | ~0 | LOW | Tested, decoupled. Needs ≥1 stable metric population (R16b: only ~8 tracked/run today). |
| 42 | Facility utilisation over time | SURFACE | ~0 (done) | ~0 + C2 writer | MED | View done; live occupancy needs the blackboard writer (C11). |

**Is the MVP intrinsic-dominant?** Counting features: 5 intrinsic (#5,#1,#30,#10, + the
foundation's intrinsic-correctness purpose) vs 5 surface (#50,#44,#45,#41,#42). **By
feature count it is balanced; by build effort and risk it is intrinsic-dominant** — every
surface feature is inert until its intrinsic dependency lands (C13), and the single largest
new line-item is the intrinsic-correctness foundation.

**Does it now require a foundation layer it didn't before?** **YES — decisively.** The
prior MVP assumed the harness could express behavioural acceptance tests. R16/R17 prove it
cannot. The MVP gained a mandatory **F0 foundation** (oracles + canonical serialiser +
run-to-completion fixture) that is a prerequisite for *trusting* any of the other nine.

---

## A7. CRITICAL PATH WITH LAYER ORDERING

Build sequence respecting intrinsic-before-dependent-surface (C13) and the prerequisites
surfaced by Cross/Red Team:

```
STEP 0 — FOUNDATION (intrinsic-correctness infra; blocks everything)   [parallelisable internally]
  0a. Canonical event serialiser — drop event_id (uuid4) + wall_time (datetime.now)   ← R1 caveat
  0b. Golden-trace fixture + distribution assertions (NOT legacy==extracted)          ← R17
  0c. run_to_completion() + sweep() fixtures (~40–60 LOC)                              ← F13
  0d. Resolve the B3 yield-invariant contradiction in CLAUDE.md (decision, not code)
       ── 0a/0b/0c parallelise; 0d is independent ──

STEP 1 — CHEAPEST HIGH-LEVERAGE INTRINSICS                              [the two parallelise]
  1a. #5 capability-aware routing — one reader in routing.py (flags already parsed)    ← C1, R16a
  1b. engine→blackboard facility writer — one per-tick callback (unblocks #4/#42/#53/#58) ← C2
       ── 1a ∥ 1b: disjoint files, no shared state ──

STEP 2 — CONFIG ENABLEMENT
  2.  scenario_overrides param on EnsembleBuilder + read threat_level/or_tables/icu_beds
       + add schema_version                                                            ← C9, C14, R8

STEP 3 — ARRIVAL MECHANISM
  3.  #1 multi-POI — ArrivalRecord.origin + per-POI sub-RNG (rng.spawn) + BOTH-TOGGLE GUARD ← C5, R11
       (then #30 per-POI MASCAL surge layers on; #8 positioning needs new units block, later)

STEP 4 — PARKED MODEL DECISION (own step, NOT a toggle flip)
  4.  PFC model reconciliation: choose 0.20× ladder vs linear 0.01, write the oracle,
       THEN wire enable_extracted_pfc                                                  ← B2, C4, A1

STEP 5 — SURFACE ACTIVATION (only now meaningful)
  5.  #44 ensemble CI, #45 sweep, #41 golden-hour, #42 utilisation, #53 Engine Room
```

**Answers to the A7 verification questions:**
- **Does #5 land before #1+#8?** Independent files (routing vs arrivals) — they
  **parallelise**, but #5 is sequenced first because it is cheaper and unblocks the R16a
  acceptance gate that proves the foundation works.
- **Does #10 require #5's routing.py changes?** No shared code, but #10 needs its own
  builder fix (`threat_level` is dropped, C14) + engine reader. Independent of #5.
- **Can #1+#8 and #10 parallelise?** #1 and #10 touch different files (arrivals vs
  builder/topology) → yes. #8 blocks on #1 (needs origin threading) → sequential within
  that pair.
- **Does #30 need #1?** Only for **per-POI** surge. The global MASCAL shift is already live
  (#30 is wired); multi-POI just makes surge spatially differentiated.
- **Does #45 call #44?** Yes — #45 wraps #44 in a loop over `scenario_overrides`; build
  beside, not before.

**What parallelises:** {0a,0b,0c} ∥ {0d}; then {1a #5} ∥ {1b blackboard writer}; then #1
∥ #10. **What strictly serialises:** foundation → everything; PFC reconciliation (Step 4)
is its own gated decision and must not be folded into Step 1.

---

## A8. CROSS-LAYER DEPENDENCY AUDIT

Using C13/C14: does any SURFACE feature land in a higher tier than an INTRINSIC feature it
depends on? Checked every surface feature against the final tiers (A10):

| Surface | Tier | Depends on intrinsic | Intrinsic tier | Violation? |
|---------|------|----------------------|----------------|------------|
| #41 golden-hour | 0 | (treatment/transit live — no dormant dep) | live | ✅ none |
| #42 facility util | 2 | #2-3 (departments) | 3 | ✅ none (surface ≥ tier of dep is the *forbidden* direction; #42 sits **below** its dep's full wiring, populated via replay until C2 lands) — **see note** |
| #44 ensemble CI | 2 | #5, #1, #10 | 1 | ✅ none |
| #45 sweep | 2 | #5, #1, #10, #44 | 1/2 | ✅ none |
| #50 YAML scenarios | 1 | #5, #10, #12 | 1 / 3 | ⚠️ **resolved** — see below |
| #53 Engine Room | 3 | #2,#3,#4 | 3 | ✅ none |
| #62 MNEMOSYNE | 4 | #5,#10,#20,#28,#31-33 | 1–4 | ✅ none |
| #34 PFC stream | 3 | #31,#32,#33 | 3 | ✅ none |
| #43 mining | 4 | all intrinsic event types | mixed | ✅ none |

**Two adjudications made to keep the rule clean:**

1. **#50 YAML scenarios — kept in Tier 1, scoped narrowly.** #50 in the *general* sense
   depends on #12 vehicles (Tier 3) and full threat config (#10). To avoid a violation,
   Tier-1 #50 is **scoped to the `scenario_overrides` + schema_version + read-already-
   present-fields slice only** (the part that gates #5/#1 sweeps). The *vehicle/threat-block*
   portion of #50 is demoted to Tier 3 alongside #12/#10's deeper config. This split
   preserves the ordering rule: the Tier-1 slice depends only on Tier-0/1 intrinsics.

2. **#42 facility utilisation — kept in Tier 2 with a replay caveat.** Its event-derived
   form works today (via `ReplayEngine`); its *live blackboard* form needs the C2 writer
   (Tier 3 territory). Tier-2 #42 is scoped to the replay-derived view; the live-occupancy
   bar follows the writer. No feature sits above its dependency.

**Result: zero unresolved violations after the two scoping splits.**

---

## A9. LAYER BALANCE PER TIER

Intrinsic:surface ratio per tier (foundation oracles count as **enabling
intrinsic-correctness infra** → intrinsic side).

| Tier | Intrinsic | Surface | Ratio | Health |
|------|-----------|---------|-------|--------|
| **Tier 0** (activate) | 3 (EX-1/2/3 extractions, graph-routing-paired) | 2 (#41, #42 views) | 3:2 | ✅ healthy — activations, low risk both sides |
| **Tier 1** (MVP wire) | **5** (F0 oracles[intrinsic-infra], #5, #1, #30, blackboard writer) | 1 (#50 narrow slice) | **5:1** | ✅ **intrinsic-dominant — correct** |
| **Tier 2** (showcase polish) | 1 (#10 threat) | 4 (#44, #45, #42, #53-event-derived) | 1:4 | ✅ acceptable — Tier 2 is where polish surfaces land, gated on Tier-1 intrinsics |
| **Tier 3** (Phase 2 bundles) | 8 (#2,#3,#4,#12,#13,#14,#23,#28,#31-33 cluster) | 2 (#34, #53-live) | ~4:1 | ✅ intrinsic-heavy bundles |
| **Tier 4** (parked) | ~9 (#6,#11,#15,#17,#35-39,#46-49,#55,#58,#59) | ~9 (#43,#54,#56,#57,#60,#61,#62,#63,#64,#7,#51,#52) | ~1:1 | ✅ deferred — surface analytics + far-future intrinsics |

**Flag check:** Tier 1 is **5:1 intrinsic-dominant** (the single surface item is the
narrowly-scoped config slice that *gates* intrinsic sweeps) — passes the "Tier 1 must be
intrinsic-dominant" rule. No tier is improperly surface-heavy: Tier 2's surface tilt is by
design (polish layer), and every Tier-2 surface item is gated on a Tier-0/1 intrinsic.

---

*Arbiter working complete (A1–A9). Final tiers (A10) and acceptance verdict (A11) in
[MAAFI_VERDICT.md](MAAFI_VERDICT.md).*
