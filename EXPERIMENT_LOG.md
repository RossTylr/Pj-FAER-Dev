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

*Subsequent entries added as NB34-39 are completed.*
*Format: date, hypothesis, method, result, artifacts.*
