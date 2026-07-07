# BUILD_S2 — Step 2: keyed-draw RNG architecture (slice 0) + config machinery (slice 1)
### Instruction file for Claude Code — FINAL v1, grounded in docs/MVP/S2_PREBUILD_ANSWERS.md (Q0–Q9, normative for all census facts). Authority: docs/MAAFI_VERDICT.md ▸ RNG ratification (5 Jul) as amended below ▸ this file.
### RULE-3 DECLARATION: slice 0 is intrinsic-zone RNG surgery — behaviour-bearing estimate ≈120–160 intrinsic LOC across engine.py, factories, arrivals, transport, well above the ~30 tripwire. The human authorisation firing this file IS the mandatory Rule-3 gate. Precedence clause applies.

**Baseline:** HEAD = the S2_PREBUILD_ANSWERS docs commit on top of 4b28bad (record SHA at step 0) · 134 green · comparison lane FROZEN.
**Q0 verdict driving scope: BOTH** — attribute contamination (severity differs 26/30; divergence begins at CAS-0003, one casualty before timing k=3) and timing divergence. 0c is REPAIR of identity invariance.

**Design of record (ratified 5 Jul, amended on Q-evidence — amendments marked ◆):**
- Unit of synchronisation is the DRAW. Identity axis key `(casualty_uid, purpose, occurrence)`; system axis `(stream, occurrence)`. `.spawn()` FORBIDDEN on the identity axis (order-dependence).
- Philox canonical; SeedSequence entropy-tuple fallback. Entropy layout: identity → `(identity_root, replication_index, 1, uid_int, purpose, occurrence)`; system → `(master_seed, replication_index, 0, stream_id, occurrence)`. `uid_int` = the factory counter n (arrival-order-stable post-fix, Q4).
- **Seed semantics (◆ patient_seed made precise):** `master_seed` (default 42) = system root and identity fallback · `replication_index` (new param, default 0) enters BOTH axes · `patient_seed` (ensemble.py:151, currently inert) = identity-root override. Invariant: vary patient_seed at fixed master → identical arrival schedule, different people; vary replication_index → fresh paired world on both axes.
- Eager where index-knowable at creation → drawn at spawn, frozen to roster; lazy elsewhere (mathematically the pre-drawn table materialised on demand). **◆ Arrays key per LOGICAL DRAW-EVENT** — whole array from one keyed generator (secondary-region sets, MASCAL offsets) — preserving exact distributional identity; never per-element decomposition of joint draws.
- **◆ Vehicle-return keying decided: casualty-leg** `(casualty_uid, VEHICLE_RETURN, leg n)` — a vehicle-mission stream would couple to dispatch interleaving and reimport desync; unrealised draws in an arm leak only doctrine-genuine congestion signal.
- **◆ SELLKE RESCOPED TO STEP 4.** Q3: deterioration is deterministic as-built (zero draws, engine.py:700-860; ladder engine.py:324-362). Introducing Sellke is a MODELLING change belonging to the Step-4 PFC adjudication (now three candidates: inline ladder · pfc.py linear · Sellke). S2 does NOT touch deterioration; it pre-draws `frailty_threshold` (uniform(0,1), purpose FRAILTY) into the roster — reserved, unused, identity-stable for the day Sellke is chosen. O3 (direction-only) remains the watchdog.
- Purpose codes: closed enum `RNGPurpose` — identity: TRIAGE, MECHANISM, PRIMARY_REGION, SECONDARY_COUNT, SECONDARY_REGIONS, SEVERITY, VITALS(field∈{GCS,HR,BP,RR,SPO2}), FRAILTY, TREATMENT(episode n), TRANSIT(leg n), VEHICLE_RETURN(leg n); system: ARRIVAL_GAP(n), MASCAL_GAP(n), MASCAL_SIZE(n), MASCAL_OFFSETS(event n). The three treatment sites (engine.py:1096/1140/1192) are ONE purpose.
- **◆ Fallback hazard killed:** in keyed mode the `rng or default_rng()` constructor fallbacks (Q1 census) RAISE; a lint invariant forbids unseeded generator construction in src/ permanently (covers triage.py:42-43).
- Dual-mode strangler: `rng_mode: shared | keyed`, default shared through 0d; keyed becomes DEFAULT at 0e with the one sanctioned O1 regen (sole committed baseline, Q7). Shared retained for archaeology.
- Perf: ~9 ms/run, 286 scalar draws (Q5/Q6 measured; the earlier 44 ms figure was stale). Cache per (uid, purpose) inside the keyed API chokepoint; draw-count instrumentation is a dict increment there (Q9).
- Thaw criterion: keyed mode, A-vs-C → ARRIVAL events byte-identical AND roster hash config-invariant (I-2). Minuted at gate.

---

## 0. Scope fence
IN: slices 0c-1/0c-2/0c-3, 0d, 0e · slice 1 · tails §3. (0a/0b complete — the interrogation session; answers file is normative.)
OUT: deterioration/Sellke mechanics (Step 4) · pfc.py adjudication (Step 4) · Step-3 multi-POI (per-POI sub-RNG dissolves into the key tuple; id_prefix is the collision seam — rider noted) · consumer wiring #4/#42/#53 · POLYBIUS itself (roster parquet = interface artefact; schema is 0c-2's to define, nothing external constrains it — Q8) · legacy walk · MVP_ACCEPTANCE.md.

## 1. Slice 0 — commits 0c-1 → 0c-2 → 0c-3 → 0d → 0e, red-then-green throughout

**0c-1 KEYED CORE + PLUMBING (no draw site converted):** `rng_mode` toggle on SimulationToggles · `RNGPurpose` enum + KeyedRNG module (entropy layout above; Philox; per-(uid,purpose) cache; per-purpose draw counters) · `replication_index` threaded through the three-site surface ensemble.py:190-192 → builder.py:144/158 → engine.py:142 (Q5) · `patient_seed` wired live per the semantics table · shared mode byte-untouched: 134 green, O1 identical. Commit.

**0c-2 EAGER + ROSTER:** convert identity-at-spawn draws (triage, mechanism, regions, severity, vitals — Q2 EAGER rows) to keyed; add FRAILTY reserved draw · roster assembly at the ARRIVAL emission point (engine.py:681-688 — identity + derived fields, the full Q0 row + frailty + key-schema version stamp) · parquet writer behind `emit_roster` flag ⟨HUMAN RULING pending on dependency: recommend pyarrow as optional-extra; writer raises helpfully if absent; in-memory roster + hash always available regardless⟩ · keyed-mode red witnessed first: I-2 attribute clause fails BEFORE this commit (arrivals still shared), roster-hash clause passes AFTER it under explicit rng_mode="keyed". Commit.

**0c-3 LAZY + SYSTEM-AXIS:** arrivals/MASCAL to system-axis keys · treatment (one purpose, three sites), transit legs, vehicle returns to casualty-keyed lazy · occurrence counters per Q2 proposals (per-casualty ordinals; MASCAL event/member indices) · fallbacks-raise in keyed mode. I-2 goes fully green in keyed mode. Commit.

**0d INVARIANTS + POISON (keyed mode exercised explicitly; default still shared):**
- I-1 keyed determinism: double run, digests equal.
- I-2 IDENTITY INVARIANCE (the point): keyed, A vs C → ARRIVAL byte-identical · roster hash identical · per-casualty field equality. (Red history across 0c-2/0c-3 documented in docstrings.)
- I-3 draw-count census in digest: widen `log_digest(events, draw_counts=None)` (canonical.py:33-42; merged into the hashed blob — no synthetic events); harness threads counts; keyed A-vs-C per-purpose counts equal on shared casualties, divergences attributable.
- I-4 POISON (R17 pattern, scoped): test-only hook mis-keys ONE purpose → I-2 FAILS; hook removed → green.
- I-5 shared-mode regression: 134 green, O1 byte-identical.
- I-6 LINT: static scan — no unseeded `default_rng()`/module-level `np.random.*`/`random.*` draws in src/; keyed-mode fallback-raise covered by unit test.
- I-7 SEED SEMANTICS: patient_seed varied at fixed master → arrival sim_times identical, rosters differ; replication_index varied → both differ; ensemble reps decorrelated.
Commit.

**0e FLIP + RE-BLESS + THAW:** default `rng_mode=keyed` · ONE sanctioned `pytest --regen-golden` (tests/conftest.py:24-39), diff artefact committed for gate review — the sole re-baseline (Q7) · recipe-vacuity check on the riders (hold_promotion_run `assert promotions`, O3/O4/O5 non-vacuity, T-5-6/7 scenarios): if any tuned scenario goes vacuous, RE-TUNE THE RECIPE, never the assertion, one-line justification each · O2 band, T-5-* properties, conservation, all toggle-arm equality suites must pass UNMODIFIED — a failure there is a KEYING DEFECT, stop and report · THAW: I-2 re-run at default, minuted → comparison lane REOPENS. Commit.

## 2. Slice 1 — config machinery (light half, one commit + rulings)
`scenario_overrides` on EnsembleBuilder → `sweep()` internals onto it (F0.2 signature survives) · scenario version stamp · guard family: role-presence · capability-ON analysis rule (GM-3) · empty-facilities ⟨HUMAN: valid-empty vs raise⟩ · `triage_distribution` wire-or-delete ⟨HUMAN; O2 polices⟩.

## 3. Tails
Mixed-caseload killer variant · CURRENT/checker reconciliation · route-divergent equivalence fixture (proof rides keyed streams) · Rule-8 addendum text for CLAUDE.md: "identical code paths AND per-entity keyed streams AND tested invariants" ⟨paste or explicit delegation⟩ · PREREG_VR1.md (IRON BRIDGE, paired vs unpaired reps, golden-hour ITT + mortality per 5a standard) — committed BEFORE any keyed comparison result is viewed, run post-thaw · Registry lesson: "a fixed seed buys reproducibility, not comparability."

## 4. Re-baseline matrix (Q7, normative)
RE-BASELINE: O1 only (tests/golden/coin_s42.json — sole committed baseline). RECIPE-SENSITIVE (re-tune scenario, never assertion): hold_promotion_run, O3/O4/O5 non-vacuity, T-5-6/7. PROPERTY-SAFE (unmodified): O2 band · O3 direction · T-5-5a/b · conservation · capability safety/liveness · all double-run determinism · seed-difference · every toggle-arm equality suite (post-flip failure = keying defect signal).

## 5. Phase gate — Definition of Done (STOP for human confirmation)
□ 0c-1 shared untouched, 134 green · □ 0c-2/0c-3 keyed reds witnessed then green · □ 0d I-1–I-7 green, poison red witnessed · □ 0e golden diff reviewed; property-safe list unmodified; recipe re-tunes justified · □ THAW minuted (I-2 at default) · □ Slice 1 + two human rulings recorded · □ PREREG_VR1 committed pre-viewing · □ Rule-4 ×3 configs · □ Intrinsic LOC actual vs 120–160 declaration · □ Rule-8 addendum ratified or explicitly deferred · □ parquet dependency ruling recorded
HALT. Step 3 and Step-4 adjudication remain unauthorised.

## 6. Kickoff prompt (verbatim, for CC in Cursor)
NOT plan mode. Verify HEAD = answers-commit atop 4b28bad, record SHA; tree clean; pytest 134 green; read docs/MVP/BUILD_S2.md + S2_PREBUILD_ANSWERS.md in full (answers normative for census facts) → 0c-1 commit → 0c-2 commit (I-2 red witnessed pre-commit under rng_mode="keyed") → 0c-3 commit (I-2 fully green keyed) → 0d commit (I-1–I-7; poison red witnessed) → 0e commit (default flip; ONE --regen-golden with diff artefact; property-safe suites unmodified or STOP; recipe re-tunes one-line justified; thaw I-2 minuted) → slice-1 commit (+ record the two human rulings; if not yet given, STOP at that point and report) → tails commits (PREREG_VR1 BEFORE viewing any keyed comparison) → HALT at §5 gate, DoD filled. Rules: seed=42 · British English · inline-dict fixtures · .spawn() forbidden on identity axis · arrays keyed per logical draw-event · deterioration untouched · shared mode never edited after 0c-1 · MVP_ACCEPTANCE.md never edited · intrinsic LOC drifting materially beyond 160 = STOP · Write tool + ls · nothing outside §0.
