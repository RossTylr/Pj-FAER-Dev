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

---

*Subsequent entries added as NB34-39 are completed.*
*Format: date, hypothesis, method, result, artifacts.*
