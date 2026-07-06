# BUILD_S1_1 — blackboard facility writer, contract-first
### Instruction file for Claude Code. Authority chain: docs/MAAFI_VERDICT.md ▸ this file. Scope is S1.1 only.
### Grounded in: S1_FOLLOWUP_ANSWERS.md (FQ1/FQ3/FQ4) · S1_PREBUILD_ANSWERS.md Q7/Q8 · AC-W.1–W.5 (MVP_ACCEPTANCE.md @ 000c287) · DPs 1–3 accepted at gate.
### RULE-3 DECLARATION: intrinsic-zone estimate 35–45 LOC (writer module under simulation/ + engine call-sites + blackboard sentinel) EXCEEDS the ~30 tripwire. The human authorisation that fired this file IS the mandatory Rule-3 gate; Rule-3 precedence clause applies (never split below a coherent slice to hit a line count).
### v1.1 — adds §8 comparison-lane riders from the external evidence review (5 Jul). Build design UNCHANGED: the writer consumes no RNG, so the arrival anomaly cannot touch AC-W.1–W.5.

**Baseline:** HEAD `dbc6119` · 127 tests green · chain dbc6119→000c287→e4e8835→53683cc→bddd05e→98597de→11284f2
**Discipline:** red-then-green · one commit per slice · zero golden diff expected and asserted · seed=42 · British English · HALT at gate.

---

## 0. Scope fence

IN: `enable_facility_writer` toggle · SimBlackboard construction on that toggle · None-sentinel fix to `set_facility_context` · FacilityContextWriter (facility-level keys only) · three engine call-sites · AC-W.1–W.5 tests.
OUT — hard fence: any consumer wiring or tick site (first consumer = #4, wires at its own build under AC-W.3's re-gate) · `department_queue_depth`/`department_capacity`/`r1_beds_available` writes (no sighted consumer contract; #4 defines them at its decision moment) · #58 weather keys (do not exist; writer-insufficient per verdict) · bt_nodes.py, trees.py · FacilityLoadView fix (ledgered, #42's build) · MVP_ACCEPTANCE.md (human-owned) · Step 2 anything.

## 1. Design (DP-1/2/3 as accepted)

- **Toggle (DP-2):** `enable_facility_writer: bool = False` on SimulationToggles (mode.py). No dependency on routing toggles; no guard needed. When ON, the engine constructs a SimBlackboard outside the inverted branch (today it exists only at engine.py:166-174); when both writer and inverted factory are ON they share py_trees' process-global storage by construction — that is the designed behaviour, not a collision, because AC-W.2's sentinel protects the factory's key.
- **Sentinel (AC-W.2, C10):** `set_facility_context(utilisation: float = 0.0, fst_queue: int = 0, mascal_active: bool | None = None)` — write `mascal_active` only when not None (blackboard.py:151-160). ~3 LOC.
- **Writer (DP-3, verdict C2 shape):** new `src/faer_dev/simulation/facility_writer.py` — a class holding an engine reference, method `update(facility_id)`: reads LIVE state (`queues[fid].count/capacity`, engine.py:613-616 pattern) and writes: `facility_utilisation` ← count/capacity of THAT facility (per-decision scalar semantics); `fst_queue_depth` ← waiting at that facility (arrived-not-yet-treating); `facility_beds_available[fid]` ← capacity − count (per-facility dict — the durable contract for #42/#53; the scalars satisfy AC-W.1's letter, the dict is what consumers should build against, and this file records that intent). Direct calls, NOT a bus subscriber: no exception-swallowing (bus.py:62-80), no ordering question, simpler determinism story.
- **Call-sites (three, ~1 line each behind the toggle):** on FACILITY_ARRIVAL emission (engine.py:957 vicinity — waiting changed); after bed acquire / TREATMENT_START (engine.py:1146-1157 — occupancy changed); after bed release / TREATMENT_END (context-exit, engine.py:1146-1178 — occupancy changed). Cite exact lines in test docstrings.
- **Scalar semantics, stated for the record:** the global scalar pair means "the facility whose context was most recently set" — coherent for per-decision consumers (#4's eventual shape), incoherent as a multi-facility view; that is why the dict exists. AC-W.5 tests the colocated-read property, not global scalar stability.

## 2. Test-isolation requirement (real trap, not ceremony)

py_trees Blackboard storage is PROCESS-GLOBAL and shared across every SimBlackboard instance (Q7, verified) — it therefore leaks across tests. Every test in this slice uses a fixture that clears `py_trees.blackboard.Blackboard.storage` (via the library's clear mechanism) before and after. Without this, green is order-dependent and meaningless.

## 3. Red-then-green (tests in tests/test_facility_writer.py; inline-dict fixtures, no YAML)

- **T-W-2 SENTINEL (↔AC-W.2), red first:** board with factory-style `mascal_active=True`; call `set_facility_context(utilisation=0.5, fst_queue=2)` with no mascal arg → key still True. Red today (current signature writes False). Unit-level; plus a combined-toggles smoke (inverted + writer ON, coin-derived run: green, Rule-4 conserved).
- **T-W-1 KILLER (↔AC-W.1), red:** writer ON, `run_to_log` on a two-facility inline fixture (drain=False); final `snapshot()` values equal event-stream derivation — beds_available[fid] vs capacity − (#TREATMENT_START − #TREATMENT_END) per facility; scalar pair vs the derivation for the LAST-written facility. Positive assertion; "no crash" is not evidence.
- **T-W-3 TRACE NEUTRALITY (↔AC-W.3):** (a) writer ON vs OFF, same scenario/seed — canonical digests byte-identical; (b) defaults untouched — O1 golden byte-identical (T-W-0, suite-level). Basis: zero live readers (FQ1). Docstring: "If (a) ever fails, a consumer went live — STOP and re-gate; this test is the standing tripwire."
- **T-W-4 DETERMINISM (↔AC-W.4):** writer ON, double run, canonical digests equal.
- **T-W-5 NO ALIASING (↔AC-W.5):** two concurrently active facilities; at each write-site invocation a colocated read observes its own facility's scalar value; end-state dict entries independently correct for both facilities. (Implementation note: assert via a thin spy/wrapper on update(), or via dict-correctness + interleaved-write unit calls — CC's choice, cite approach.)

Budget: intrinsic ≈35–45 LOC (declared above) · tests ≈60–80. One commit: `feat(S1.1): facility context writer — toggle-gated, sentinel-safe, per-facility dict contract (AC-W.1–W.5)`.

## 4. Post-commit verification

Full suite green (127 + new, expect ~133) twice consecutively · O1 golden byte-identical, `git status --porcelain tests/golden/` empty, regen not used · Rule-4 conservation on defaults / writer-on / writer+inverted.

## 5. Docs commit

Append "S1.1 OUTCOME" block to BUILD_S1.md §6 (hold lifted per preconditions; DPs 1–3; this file's SHA) · append EXPERIMENT_LOG entry: S1.1 built, AC-W.1–W.5 green, intrinsic LOC actual vs declared estimate · replace docs/CURRENT.md with the refreshed version the human provides (or note if absent).

## 6. Phase gate — Definition of Done (STOP for human confirmation)

□ T-W-1/2/3a/4/5 green, reds witnessed first where specified
□ T-W-0/3b: O1 byte-identical; O2–O6 untouched; suite green ×2
□ Rule-4 conservation, three toggle configs
□ Intrinsic-zone LOC actual reported vs 35–45 declaration (Rule-3 record)
□ Test-isolation fixture present on every test in the file
□ Nothing outside §0 fence; MVP_ACCEPTANCE.md untouched
HALT. #4/#42/#53 consumer wiring and Step 2 remain unauthorised. S1 is COMPLETE at this gate.

## 7. Kickoff prompt (verbatim, for CC in Cursor)

NOT plan mode. Confirm HEAD dbc6119, clean tree, pytest 127 green → read docs/MVP/BUILD_S1_1.md in full → red-then-green per §3 in order T-W-2 → T-W-1 → T-W-3 → T-W-4 → T-W-5, ONE feature commit → §4 verification (suite ×2, golden porcelain, conservation ×3 configs) → §5 docs commit → fill §6 DoD → execute §8 riders (read-only diagnostics; outputs are docs commits only) → HALT with §6 DoD + §8 checklist both filled. A STREAM-CONTAMINATION verdict in R1 freezes the COMPARISON LANE, not this build — report it prominently, revert nothing. Rules: seed=42 · British English · inline-dict fixtures · py_trees storage cleared per test · bus subscriber pattern NOT used — direct call-sites only · no consumer wiring, no dept/r1 dict writes, no #58 keys · blackboard edits limited to the sentinel · intrinsic-zone LOC reported against the 35–45 declaration; drifting materially beyond it = STOP for human gate · MVP_ACCEPTANCE.md never edited · nothing outside §0.

## 8. RIDERS — comparison-lane diagnostics (read-only; run AFTER §6 DoD is filled; docs commits only)

Origin: external review of the A/B/C evidence session. Nothing here touches src/ or tests/; nothing here gates the §6 build outcome.

**R1 — ARRIVAL ANOMALY CLASSIFICATION (gates the comparison lane).** Re-run coin, seed 42, 24h, uncapped: Config A = all defaults · Config C = extracted + graph + capability ON. Diff the canonical ARRIVAL events per casualty (id, sim_time). Classify:
(a) identical spawn sequence, count differs by counting-site → **DEFINITION DRIFT** — cite both count sites file:line;
(b) interarrival sequence diverges from some index k → **STREAM CONTAMINATION** — identify the shared RNG: trace the seed fan-out (who constructs the stream(s); whether routing/transit draws share the arrivals stream), cite file:line, report k;
(c) neither → OTHER, report raw evidence.
Write docs/MVP/RNG_DIAGNOSTIC.md (Write tool + ls), one docs commit. Verdict (b) means: paired A-vs-C claims are unquotable until dual-stream separation lands (register row exists); EXP-IB-1000 design threatened; S1.1 build outcome UNAFFECTED.

**R2 — A≡B AT TRACE LEVEL.** If the committed T-5-2c digest test already compares the same two configs at canonical-trace level, cite it and mark SATISFIED. Else run the canonical byte-diff once and record. Field-level differences between implementations are canonicalisation-scope findings, not correctness failures — report, do not fix.

**R3 — LEDGER (EXPERIMENT_LOG appends, one docs commit).** (i) Instrument validation: killer-topology 20/20-detected vs coin 0/0-clean brackets the T-5-1 violation census — the GM-5 instrument is proven, coin's zeros are retroactively meaningful. (ii) R16a status reworded: "mitigated behind flag, open at defaults; trigger condition = nearer/lighter non-capable candidate; closing action = capability-default decision at legacy retirement (GM-4)." (iii) R1's verdict. (iv) Equivalence-fixture lesson: route-coincident fixtures cannot detect draw-count divergence between paths; add a route-divergent fixture when stream separation lands.

**R4 — explicitly NOT this session:** golden-hour reporting fix (Step 5a owns it; interim standard lives in CURRENT.md) · mixed-caseload killer variant (Step-2 tail) · any RNG fix or stream-separation work.

Checklist: □ RNG_DIAGNOSTIC.md written, ls-confirmed, committed, verdict stated □ R2 satisfied-or-run □ R3 four appends committed □ git status confirms docs-only.
