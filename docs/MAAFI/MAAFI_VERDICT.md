# MAAFI VERDICT — FAER-MIL (layer-aware, final)

**Arbiter synthesis of Forward / Backward / Cross / Red Team.**
Working: [MAAFI_ARBITER.md](MAAFI_ARBITER.md) (A1–A9). This file: A11 verdict (top) + A10 tiers.

---

# A11. ACCEPTANCE-TESTING FEASIBILITY VERDICT

## 🔴 VERDICT: CORRECTNESS BLIND

The existing 99-test suite proves **execution and differential equivalence, not
correctness.** This is not an opinion — it was demonstrated by live execution (Red Team
R17): **forcing every casualty to triage T3 — a catastrophic clinical corruption — passed
all 99 tests (99/0).** The suite's protection exists *only* where two independent
implementations cross-check each other (`legacy==extracted` for EX-1/2/3, and
graph-vs-legacy routing). Every **single-implementation** intrinsic mechanism — triage
assignment, severity sampling, the inline deterioration model, capability routing — **has
no oracle, and no test would catch a wrong answer.**

Consequences, verified:
- **(a) Event-log behavioural assertions — NOT writable today.** "No surgical casualty
  treated at a non-surgical facility" cannot be expressed: routing ignores capability
  (R16a — **86/114 surgical patients treated at non-surgical facilities**) and
  `TREATMENT_*` events carry no capability/surgical-need field. The property has nowhere to
  plug in (F13c, R16a).
- **(b) Ensemble-property assertions — NOT expressible today.** `EnsembleBuilder` exposes
  no bed-count/scenario-override parameter (F8, C9, R16b); a bed-sweep needs on-disk YAML
  edits, and even then `golden_hour.total_tracked ≈ 8/run` makes `pct_within_60` noisy and
  non-monotonic.
- **(c) The suite catches a deliberately broken feature only on cross-checked paths
  (R17).** Single-implementation breaks are invisible.

### What MUST be built before ANY MVP feature is trustworthy (prerequisite, ahead of feature work)

1. **Correctness oracles** — golden-trace fixtures + distribution assertions on
   single-implementation mechanisms (triage mix, severity distribution, deterioration
   trajectory). **NOT** `legacy==extracted` checks — those are the blind spot, not the fix.
2. **Canonical event serialiser** — strips `event_id` (uuid4) and `wall_time`
   (datetime.now) so replay/golden-trace hashing does not report spurious non-determinism
   (R1 caveat). Determinism is real on meaningful fields; the raw store is not hashable.
3. **Run-to-completion fixture** — a `run_to_log()` that drains the engine (no in-flight
   casualties at cutoff — the ARRIVAL 31 / DISPOSITION 28 delta is a drain artefact, F12)
   and returns the event log for assertion. ~40–60 LOC with the sweep fixture.
4. **`scenario_overrides` / sweep parameter** on `EnsembleBuilder` (one threading point,
   `ensemble.py:190`, C9) — so bed/capability/arrival sweeps are expressible without
   editing YAML on disk.
5. **Capability + surgical-need fields on `TREATMENT_*` events** — so the R16a acceptance
   property is assertable from the event stream alone.

**Until (1)–(5) exist, every intrinsic "done" claim means "runs," not "computes
correctly," and any surface feature (dashboard, sweep, AAR) built on top creates false
confidence — a beautiful dashboard of wrong numbers.** Close the foundation first; it is
Tier 1, ahead of all feature work.

---

# A10. FINAL TIER ASSIGNMENTS (all 64 features, layer-tagged)

Layer tag: **I** = intrinsic, **S** = surface. Foundation oracles are tagged **I-infra**
(enabling intrinsic-correctness). HARD RULE enforced: no S feature sits above an I feature
it depends on (audited in A8).

## TIER 0 — ACTIVATE (built + verified; flip on / keep on)

| # | Feature | Layer | Evidence |
|---|---------|-------|----------|
| EX-1 | Extracted routing (`enable_extracted_routing`) | I | Seed-matched OFF↔ON, R5 PASS; R17 Break A caught. Pin ON. |
| EX-2 | Extracted metrics (`enable_extracted_metrics`) | I | Seed-matched (R5). Pin ON. |
| EX-3 | Typed emitter (`enable_typed_emitter`) | S→behaves-S | Byte-identical sim outcomes OFF↔ON (R13). Pin ON. |
| 1.5 | Graph routing (`enable_graph_routing`) | I | Load-balancing verified (R11) **— activate WITH a both-toggle config guard**, else inert/legacy-starve (223/0). |
| 41 | Golden-hour compliance view | S | Tested, decoupled analytics (B6, R2 🟢). |
| 42 | Facility-utilisation view (replay-derived) | S | Tested, decoupled (B6); event/replay-derived form works today (C11). |

## TIER 1 — MVP WIRE (intrinsic-dominant; the foundation + cheapest high-leverage intrinsics)

**Ratio 5 I : 1 S — intrinsic-dominant ✅**

| # | Feature | Layer | Actual LOC | Risk | Evidence / requirement |
|---|---------|-------|-----------|------|------------------------|
| **F0** | **Correctness oracles + canonical serialiser + run-to-completion fixture** | **I-infra** | ~120–180 | CRITICAL | A11. Prerequisite for trusting everything below. |
| 5 | Capability-aware routing | I | ~40–60 | MED | One reader in `routing.py`; flags already parsed (C1, C14). Gates R16a + #44/45/50/56/62. **Cheapest real lever.** |
| — | engine→blackboard facility writer | I | ~20–40 | MED | One per-tick callback (C2). Unblocks #4/#42/#53/#58. Watch the `mascal_active` two-writer collision (C10). |
| 1 | Multi-POI arrivals | I | ~80–120 | HIGH | `ArrivalRecord.origin` + per-POI sub-RNG (`rng.spawn`, C5) + **both-toggle guard** (R11). Determinism is the real blocker. |
| 30 | MASCAL triage shift (verify + per-POI wiring) | I | ~20 | MED | Live (B6) but no oracle (R17). Needs a correctness assertion + per-POI surge (needs #1). |
| 50 | YAML `scenario_overrides` + `schema_version` (narrow slice) | S | ~30 | MED | One threading point (C9). Scoped to the sweep-enabling slice only (A8); vehicle/threat config → Tier 3. |

## TIER 2 — SHOWCASE POLISH (mixed; gated on Tier-1 intrinsics)

| # | Feature | Layer | Evidence |
|---|---------|-------|----------|
| 10 | Threat zones | I | Builder drops `threat_level` today (C14, R15); needs `threat_zones` block + engine reader. Gates #44/45/50/56/62. |
| 44 | Ensemble CI | S | Exists; inert until #5/#1/#10 (C13). Wire `scenario_overrides`. |
| 45 | Sensitivity sweep | S | Wraps #44; meaningful only over live intrinsics (R16b). Perf is fine (~3.8s, R3). |
| 53 | Engine Room / X-Ray (event-derived panels) | S | Timeline/triage/facility-via-replay work today (C11). |
| 25 | Surgical vs non-surgical pathway | I | Becomes meaningful once #5 routing reads `has_surgery`. |

## TIER 3 — PHASE 2 BUNDLES (intrinsic-heavy; gated on a shared prerequisite each)

| Bundle | # | Layer | Shared prerequisite |
|--------|---|-------|---------------------|
| **Departments** | 2, 3, 4 | I | Mechanism built/gated OFF (C7); needs the C2 blackboard writer + ON-path tests (B4: 0 today). |
| **PFC reconciliation** | 21, 23, 31, 32, 33 | I | **Model decision** (0.20× ladder vs linear 0.01, B2/C4) BEFORE wiring `enable_extracted_pfc`. Not a toggle flip. |
| **DCS** | 28 | I | Tick `build_dcs_tree` + populate 3 write-never-read keys + emit phantom `DCS` event (C4, B7). |
| **Multi-modal transport** | 12, 13, 14 | I | **DiGraph→MultiDiGraph** (C3) — foundational, touches every `topology.py` accessor. |
| **Patient model** | 18, 20, 22, 24, 26, 27 | I | vitals/ATMIST/BT trees gated OFF, untested ON paths (B4); #27 dept BT is the C2 writer's consumer. |
| PFC event stream | 34 | S | Gated on #31-33 (C13). |
| Engine Room (live blackboard inspector + occupancy) | 53-live | S | Gated on C2 writer (C11). |
| 8, 9 | Unit positioning / engagement | I | Need new `units` config block (C14); #8 blocks on #1. |
| 16, 19, 29 | Return-cycle / injury-first / alt decision systems | I | Live-but-unverified or `decision_mode` dead (B10). |

## TIER 4 — PARKED (with reason)

| # | Feature | Layer | Reason parked |
|---|---------|-------|---------------|
| 6 | Mobile facilities | I | Topology mutation mid-run; no path today. |
| 11 | Dynamic threat changes | I | Needs #10 first + time-varying edge weights. |
| 15 | Physical transport constraint | I | **Deadlock triad** with batching + hold-at-R1 (C8) — model carefully, not MVP. |
| 17 | MERT teams | I | Transport-mechanism extension; post-MultiDiGraph. |
| 35, 36, 37, 38, 39 | Consumables (blood/kit/oxygen/resupply/stockout) | I | **`consumable.py` does not exist** (F1); needs new module + `consumables` config block + bus subscriber + write-back loop for #39 feedback (C6). |
| 46, 47, 48, 49 | Route denial / destruction / comms / counter-MEDEVAC | I | Contested mechanisms; need #10/#11 foundation first. |
| 55 | LLM-backed decision agents | I | `anthropic` dep clean (F10) but no agent scaffold; far-future. |
| 58 | Weather / environment | I | Needs C2 writer + `_WEATHER_KEYS` + consumer (C2). |
| 59 | Medic fatigue / cognitive degradation | I | No mechanism; far-future. |
| 7 | Unit definitions | S | Narrative labels only (R13 confirms surface). |
| 43 | Process mining / XES | S | Runnable but import-orphan (C1/B8); no MVP consumer. |
| 51, 52 | Operational presets / HADR variant | S | No overlay system (R14); variants are no-ops unless intrinsics differ (C13). |
| 54 | Auto-AAR / Report Agent | S | Reads EventStore post-run (C6) but reports over phantom DCS/PFC = gaps-as-facts (C13). |
| 56 | OPORD-to-config | S | Generates config for features the engine can't read = dead text (C14). |
| 57 | Agent memory across runs | S | Needs #55 (no agent, no memory). |
| 60 | Shadow agent / comparator | S | Needs ≥2 live decision systems; `decision_mode` dead (B10). |
| 61 | Statistics upgrade | S | Needs #44 producing real variance first. |
| 62 | MNEMOSYNE export | S | 6 of 9 survival fields dormant/phantom (C12); gated on #5/#10/#20/#28/#31-33. |
| 63 | Supply-chain cascade | S | Gated on #35-39 (don't exist). |
| 64 | Lessons-learned KG | S | Builds on #54; inherits its gaps. |
| 40 | Survivability curves | S | UI-only helper, not engine (B6); needs #20/#21/#22 wired. |

---

## One-line bottom line

**Do not build a single MVP surface feature until the F0 foundation (oracles + canonical
serialiser + run-to-completion fixture) and #5 capability routing exist** — the suite is
CORRECTNESS BLIND (R17), and everything downstream of an unverified mechanism inherits its
blindness. The cheapest path to a *trustworthy* MVP is: foundation → #5 ∥ blackboard
writer → scenario_overrides → multi-POI (guarded) → activate surface. The pfc.py "freebie"
is a model-reconciliation decision (Tier 3), not a toggle flip.

---
*Arbiter complete. 11/11 answered. Tiers cover all 64 features; HARD RULE audited in A8.*
