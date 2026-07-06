# EXPERIMENT_LOG.md — Pj-FAER-Dev
## Append-only record of all extraction experiments and validation results

---

### Entry 0: DSE Architecture Decision (2026-03-16)

**Decision:** "Tidy, Decouple, Then Plug" — Pattern A+E Phase 1, Pattern B Phase 2, Pattern D Phase 3.
**Method:** Multi-LLM Design Space Exploration (Claude, Gemini, ChatGPT). 30 approaches generated, 6 shortlisted, red-teamed, scored, synthesised.
**Result:** 3/3 LLMs converge on Phase 1 (EX-1/2/3 + analytics). 7/7 exit criteria met. GO.
**Artifacts:** `docs/dse/` (9 documents)

---

### Entry 1: S1.2b T-5-5 tripwire — recompute alone cannot fix committed-hold staleness (2026-07-05)

**Hypothesis:** recomputing `requires_dcs` at the PFC-ceiling promotion site (engine.py:807-815) turns the T-5-5 stale-flag test green.
**Method:** red-then-green per BUILD_S1 §4. Red built from a probe-tuned O4-derived recipe (R2-NS beds=1, enable_ccp for the 15 h data-driven T2 ceiling, severity 0.70, treatment modifier 2.0, hold timeout 45 h; seed=42): 45 promotions, 21 T1_SURGICAL treatments at the non-surgical facility. Recompute applied; test re-run; live probe on a violating casualty.
**Result:** TRIPWIRE FIRED — 21 violations unchanged pre/post fix. Verified live: the flag recomputes correctly and a fresh routing call from the hold location selects the surgical facility, but the hold destination is committed at engine.py:680-688 before the hold gate and never re-evaluated (engine.py:720-848). **Gate ruling (b)+(c):** recompute lands as flag-truth fix (commit `bddd05e`); gap pinned by characterisation `test_promotion_does_not_reroute_committed_hold` (inverts at Step 3); re-route decision routed to Step 3 as the re-plan-on-Clock-1 family alongside T-5-7's spatial twin; EX-6 possible vehicle, not plan of record.
**Artifacts:** `tests/test_capability_retriage.py` · `docs/MVP/BUILD_S1.md` §4 OUTCOME block · gate ruling minutes GM-1–5 (chat, 2026-07-05)

**Addendum (2026-07-05, AMEND-1/2 session):** AC-1.4 (MVP_ACCEPTANCE.md:101) carries the same byte-identical raw-log defect as pre-amendment AC-5.3; deferred to Step-3 AC authoring — a mechanical swap may be insufficient since multi-POI determinism language may need per-POI sub-RNG caveats.

---

### Entry 2: S1 phase-gate minutes GM-1–5 ratified (2026-07-05)

**Decision:** the five gate minutes tabled at the S1 halt are RATIFIED (human invocation flag, S1.1 pre-author session).
**Method:** gate adjudication over the S1 evidence — T-5-6 starvation characterisation, O7 absence audit, R16a-at-defaults minute, legacy-path status, and the T-5-5 tripwire outcome.
**Result:**
- **GM-1 STRATEVAC starvation:** confirmed success-shaped silent disposition (T-5-6). Resolution owned by Step 5a — the disposition-metric decision (compliant/censored/failed, plus warm-up respect) is made there; no engine change before it. Accepted for Steps 2–4: toggle default-off, no current scenario starves.
- **GM-2 O7 absence:** ruled F0 debt, SCHEDULED — not descoped. Erlang/Little is the cheap external-theory anchor for the PoC's queue-dependent claims. Build after Step 2 using `scenario_overrides` for the single-node collapse; gate for Step 5.
- **GM-3 R16a at defaults:** persists on the legacy path by design (Rule 2 letter). Interim rule: every analysis or doctrine-comparison scenario sets capability ON (+extracted); enforced by the Step-2 guard/version-stamp family. Closes at retirement.
- **GM-4 legacy retirement:** named milestone, window after the Step-3 gate and before Step-5 pre-flight (Step-5 comparisons run a single code path — Rule 8 purity). Scope: extracted default-on, legacy walk deletion, capability-default decision (flipping it closes R16a). Own mini instruction file.
- **GM-5 violation census (from the tripwire):** the T-5-1 predicate graduates to a standing reported metric — any capability-ON ensemble reports the violation census — and a promotion census joins the Step-5 pre-flight probes alongside warm-up. Until Step 3 lands the re-route, this keeps the stale-hop gap from silently contaminating the PoC sentence (bed-constrained MASCAL is precisely the regime that produces long holds and promotions).
**Artifacts:** `docs/MVP/BUILD_S1.md` §4 OUTCOME + §8 gate · `tests/test_capability_retriage.py` (T-5-5b/T-5-6/T-5-7) · gate ruling message (chat, 2026-07-05)

---

### Entry 3: S1.1 facility context writer built — AC-W.1–W.5 green (2026-07-06)

**Hypothesis:** the writer can land contract-first (no consumer) with zero trace impact: writer ON ≡ writer OFF at canonical-digest level, O1 golden untouched, determinism preserved.
**Method:** red-then-green per BUILD_S1_1.md v1.1 §3, order T-W-2 → T-W-1 → T-W-3a → T-W-4 → T-W-5. T-W-2 red witnessed (current `set_facility_context` clobbers factory `mascal_active=True` → False; the C10 collision live in the test output) before the None-sentinel amendment. T-W-1 red witnessed (toggle declared, engine unwired → no `_blackboard`) before the writer/wiring. One feature commit; §4 verification after.
**Result:** ALL GREEN. Suite 127 → 134 (×2 consecutive); O1 golden byte-identical, `--regen-golden` not used, `git status --porcelain tests/golden/` empty; Rule-4 conserved on defaults / writer-on / writer+inverted (arrivals=dispositions 13/13/7; writer-on ≡ defaults exactly — the inverted delta is factory RNG consumption, independent corroboration of writer trace-neutrality alongside T-W-3a). **Rule-3 record:** intrinsic LOC actual 36 behaviour-bearing vs 35–45 declared (within); 75 raw added incl. 39 spec-mandated docstring/comment lines — convention stated in the OUTCOME block for the gate to accept or re-rule. T-W-3a stands as the permanent tripwire: if it ever fails, a consumer went live — STOP and re-gate.
**Artifacts:** commit `339b940` · `src/faer_dev/simulation/facility_writer.py` · `tests/test_facility_writer.py` · `docs/MVP/BUILD_S1.md` §6 S1.1 OUTCOME block · `docs/MVP/BUILD_S1_1.md` v1.1 (blob `748d492`)

---

### Entry 4: S1.1 §8 comparison-lane riders — ledger appends (2026-07-06)

Four items per BUILD_S1_1.md v1.1 §8 R3, wordings (i), (ii) and (iv) verbatim from §8; (iii) is R1's verdict with its evidence.

**(i) Instrument validation:** killer-topology 20/20-detected vs coin 0/0-clean brackets the T-5-1 violation census — the GM-5 instrument is proven, coin's zeros are retroactively meaningful.

**(ii) R16a status reworded:** "mitigated behind flag, open at defaults; trigger condition = nearer/lighter non-capable candidate; closing action = capability-default decision at legacy retirement (GM-4)."

**(iii) R1 verdict — (b) STREAM CONTAMINATION, k=3.** Blind-first diff (raw comparison recorded before any mechanism narrative): Config A defaults vs Config C extracted+graph+capability, coin/seed 42/24 h/uncapped → 31 vs 30 ARRIVALs, identical (id, sim_time) prefix 3, interarrival divergence from CAS-0004. Mechanism traced after the verdict: routing is draw-free (routing.py, zero rng references) — the pre-verdict "graph routing draws extra numbers" hypothesis is wrong in its literal form; the culprit is draw INTERLEAVING on the single shared generator (engine.py:142) serving arrivals (arrivals.py:146), treatment exponentials (engine.py:1096/1140/1192), transport trip normals (transport.py:291) and vehicle-return normals (engine.py:1228). First full-log divergence: CAS-0001 routed POI-1→R1-ALPHA (A) vs POI-1→R2-MAIN (C) — the designed policy difference — after which journey draws reorder against arrival draws. COMPARISON LANE FROZEN; dual-stream separation is the IMMEDIATE Step-2 priority per the register row; EXP-IB-1000 design threatened; S1.1 build unaffected. Full report: `docs/MVP/RNG_DIAGNOSTIC.md`.

**R2 record (satisfied-by-run):** neither committed test covers A≡B at canonical-trace level (T-5-2c holds extracted ON in both arms, tests/test_capability_routing.py:176-191; TestRegressionEquivalence compares A-vs-B but at metrics level only, tests/test_routing.py:163-197). The one-off canonical byte-diff was run: A (defaults) vs B (extracted ON), coin/seed 42/24 h/uncapped — **digests byte-identical** (`0e920ed821a1…`, 258 events each). No field-level canonicalisation findings. Corollary for (iii): contamination enters at the graph-routing step (B→C), not the extraction step (A→B).

**(iv) Equivalence-fixture lesson:** route-coincident fixtures cannot detect draw-count divergence between paths; add a route-divergent fixture when stream separation lands.

**Artifacts:** `docs/MVP/RNG_DIAGNOSTIC.md` (commit `88020e8`) · scratchpad scripts `r1_arrival_diff.py` / `r1_first_divergence.py` / `r2_ab_bytediff.py` (session transcript) · BUILD_S1_1.md v1.1 §8.

---

*Subsequent entries added as NB34-39 are completed.*
*Format: date, hypothesis, method, result, artifacts.*
