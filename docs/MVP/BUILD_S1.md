# BUILD_S1 — MVP Step 1: capability routing (strangler-side, toggle+guard) · blackboard writer (HELD)
### Instruction file for Claude Code. Authority chain: docs/MAAFI_VERDICT.md ▸ this file. Scope is S1 only.
### v3.1 — refined against verbatim AC-5.1–5.3 (MVP_ACCEPTANCE.md:61-84) and Hard Rules 1–8 (CLAUDE.md:18-66). Changes from v2: filter moves to the strangler side only (Rule 2 letter: "Legacy path preserved"); R11-family config guard added; AC-5.2 liveness assertion added; AC-5.3 canonical-log defect flagged; FQ2 pre-flight deleted (answered out-of-band); writer-AC authoring precondition recorded for S1.1.

**Baseline:** main @ `679ecc0` · 114 tests green (oracles O1–O6; O1 = golden trace)
**Discipline:** F0 pattern — red-then-green · one commit per slice · suite green throughout · zero golden diff expected and asserted · seed=42 · British English · HALT at phase gate.
**Fixture style (Q9):** inline dicts or `copy.deepcopy(get_preset_raw("coin"))` — no YAML under tests/.

---

## 0. Scope fence

IN: chore commit · S1.2a filter+toggle+guard · S1.2b re-triage fix + characterisations · FQ1/3/4 read-only tail.
OUT — hard fence: S1.1 writer build (HELD, §6); any edit to MVP_ACCEPTANCE.md (human-owned; two amendments pending, §3); `scenario_overrides`/ensemble.py:190; `triage_distribution` (F9, Step 2); multi-POI; PFC model decision; dynamic occupancy→weight feedback; CROSSOVER_PROBES; **engine.py:84-121 legacy walk — do not modify** (Rule 2: legacy preserved; it stays capability-blind until retirement).
KNOWN ADJACENT DEFECTS — log, do not fix: `has_lab` never parsed (builder.py:201-203); `or_tables`/`icu_beds`/`ventilators` silently dropped (builder.py:195-204); `Facility.current_occupancy` never written (schemas.py:169); `None`-route → success-shaped STRATEVAC (engine.py:690-704 — T-5-6, gate item).

## 1. Order decision

S1.2a → S1.2b → FQ1/3/4 → HALT. S1.1 does not build this session (§6 preconditions).

## 2. Chore commit (standalone, first)

`.gitignore` += `run_log.jsonl`; `git rm --cached run_log.jsonl` if tracked. Commit: `chore: gitignore run_log.jsonl`.

## 3. S1.2a — capability filter on the strangler side, toggle + guard

**Acceptance criteria, verbatim (MVP_ACCEPTANCE.md:61-84).** Property: "routing respects facility capability requirements. A casualty needing a capability is never sent to a facility lacking it."
- AC-5.1: "THE KILLER ASSERTION. Configure one facility with has_surgery=False. Run a scenario with surgical casualties. Assert: NO event where a casualty with needs_surgery=True is treated at the has_surgery=False facility."
- AC-5.2: "Configure all facilities has_surgery=True. Run. Surgical casualties ARE treated (no casualty stuck unrouteable when capability exists). Confirms the flag gates, doesn't block."
- AC-5.3: "Determinism: AC-5.1 produces byte-identical event log across two runs at seed=42."
- Wire-order note: "#5 must land before #45 sweep."

**AC document defects — HUMAN AMENDMENTS, do not edit in this session:** AMEND-1: `needs_surgery` does not exist in code; the as-built flag is `requires_dcs` (schemas.py:114; routing.py:47-50; engine.py:657). AMEND-2: "byte-identical event log" is unsatisfiable on raw logs (event_id uuid4 + wall_time — the R1 caveat); must read "byte-identical **canonical** log (F0.1)". Tests below implement the amended letter.

**Ground truth (Q1–Q4):** three routing implementations — legacy walk engine.py:84-121 (live at baseline; NOT touched), extracted walk routing.py:138-149, graph routing.py:127-136 via `_find_highest_reachable` (routing.py:88-96). 12 equivalence tests pin them pairwise at capability-OFF. Flag pair: casualty `requires_dcs` ↔ facility `has_surgery` (schemas.py:162; parsed builder.py:201-203).

**Design:**
- **Toggle:** `enable_capability_routing: bool = False` on `SimulationToggles` (mode.py, alongside :53/:58). Rule 2 letter supports declaring a toggle ahead of full wiring; Rule 8 synergy: capability-aware vs capability-blind routing becomes a config axis through identical code paths — CRN-attributable if ever compared.
- **Guard (mandatory, R11 family):** `enable_capability_routing=True` with `enable_extracted_routing=False` raises a config error at engine construction. Without it we recreate the R11 silent-toggle trap: a capability toggle that is inert on the default path. Legacy + capability is an *invalid combination by design*.
- **Predicate (one, shared):** `_meets_capability(patient, facility) -> bool` in routing.py: `return facility.has_surgery or not patient.requires_dcs`. Extensible; S1 wires surgery only.
- **Two application sites — candidate-set exclusion, never weighting** (R1-ALPHA lesson, Q3: weights silently dominate soft flags): (1) extracted walk acceptance, routing.py:140-148; (2) graph `_find_highest_reachable` inner loop, routing.py:92-96, before `get_route`/Dijkstra runs. Legacy walk: untouched, capability-blind, retired with the strangler.
- **Plumbing:** `use_capability_routing: bool = False` param on `get_next_destination`, mirroring `use_graph_routing`; engine passes `toggles.enable_capability_routing` at engine.py:680-684 (~2 LOC intrinsic-zone touch — Rule 3 accounting below).

**Red-then-green:**
- **T-5-1 KILLER (↔AC-5.1 as amended), parametrised ×2.** Inline fixture: POI → R2-A (non-surgical, light edge weight) + R2-B (`has_surgery: true`, heavier weight), direct edges; 100% T1_SURGICAL; capability ON. Params: (extracted walk: extracted ON, graph OFF) / (graph: BOTH routing toggles ON — R11). Fixture note: R2-A must PRECEDE R2-B in facility insertion order — walk first-match (routing.py:147) and the graph candidate loop (routing.py:92-96) both select by insertion order among same-role candidates, so R2-A-first is what makes the unfiltered red state manifest on both params. Assertion on the event stream, clinical truth not mechanism: for every TREATMENT_START where the casualty's triage *at that moment* is T1_SURGICAL, the treating facility has `has_surgery=True`. This is a treatment-site predicate — it matches AC-5.1's letter exactly. Red today on both params. Docstring records: legacy walk is capability-blind by design; R16a remains open at defaults until legacy retirement (gate minute).
- **T-5-2 CONTROL + LIVENESS (↔AC-5.2):** (a) digest control — killer fixture with R2-A also surgical: toggle ON vs OFF canonical digests byte-identical (filter vacuous when all qualify); (b) AC-5.2 letter — same all-surgical config, toggle ON: every T1_SURGICAL casualty has ≥1 TREATMENT_START and none is disposed via the None-route path (the flag gates, doesn't block); (c) coin preset, extracted ON in BOTH arms, capability ON vs OFF — digests expected identical (coin's T1s already reach surgical facilities, Q6; holding extracted fixed isolates the capability toggle from strangler equivalence); if not identical, stop and report.
- **T-5-3 DETERMINISM (↔AC-5.3 as amended):** killer config, double run, canonical digests equal (R1 gate re-applied).
- **T-5-4 NON-DOMINANCE (R1-ALPHA non-inheritance):** graph param on the killer fixture — weight-preferred R2-A is excluded; casualty routes to R2-B despite the worse weight; no weight advantage re-admits a non-capable candidate.
- **T-5-G GUARD:** capability ON + extracted OFF → config error raised at construction.
- **T-5-0 ZERO GOLDEN DIFF:** full suite green, O1 byte-identical. Any O1 diff = stop and report; regeneration NOT sanctioned in S1 (stricter than Rule 7).

Budget ≈80–100 LOC incl. tests (intrinsic-zone share ≈2 LOC). Commit: `feat(S1.2a): toggle-gated capability filter on extracted+graph paths, with config guard`.

## 4. S1.2b — re-triage staleness fix + characterisations

**Ground truth (Q4 caveat):** PFC-ceiling re-triage promotes triage to T1_SURGICAL mid-journey (engine.py:807-810) WITHOUT recomputing `requires_dcs` (set once, engine.py:655-657). The filter would read a stale lie for promoted casualties.
- **T-5-5 (red):** the O4 hold recipe (beds=1, hold-timeout override, T2 that hits PFC ceiling and promotes) applied to an INLINE fixture whose held facility is NON-surgical with a surgical alternative reachable — a coin deepcopy cannot produce the red state, since coin's downstream facilities are all surgical; capability + extracted ON. Under the T-5-1 predicate the promoted casualty treated non-surgically → red. **Green:** recompute `requires_dcs` at the promotion site (engine.py:807-810 region, same rule as routing.py:47-50; ~2 LOC intrinsic). Golden unaffected (no PFC/HOLD events in the trace — Q9 census). Tripwire: if HOLD_RETRY re-admits to the same facility without re-routing, recompute alone may not turn this green — STOP and report for a fix-scope decision; do not expand the fix unilaterally.
- **T-5-6 CHARACTERISATION — capability starvation:** no surgical facility reachable; capability + extracted ON; T1_SURGICAL. Assert current behaviour: None → journey-complete → STRATEVAC (engine.py:690-704), no failure signal. Docstring: "success-shaped silent disposition; gate discussion item; Step-5 golden-hour metric contamination risk."
- **T-5-7 CHARACTERISATION — per-hop treatment, graph mode. STEP-3 ENTRY CRITERION, not optional polish:** chain fixture POI→R1→R2(surgical); both routing toggles + capability ON; T1_SURGICAL. Document treatment at non-capable intermediates (Q3/Q5: every FACILITY_ARRIVAL treats). AC-5.1's letter is a treatment-site property, so this gap is a known nonconformance in multi-hop graph topologies — tolerable in S1 (graph is default-off and single-hop fixtures conform) but MUST be resolved before Step 5's #45 sweep (wire-order note), i.e. during Step 3 multi-POI. Mechanism sketch for Step 3: capability as hard edge-constraint à la `bypass_role1` infinite weights (topology.py:63-68 pattern), or transit-without-treatment semantics — decision then, not now.

Budget ≈40–70 LOC incl. tests. Commit: `fix(S1.2b): recompute requires_dcs on PFC re-triage + capability characterisation tests`.

**S1.2b OUTCOME (recorded 2026-07-05).** The T-5-5 tripwire FIRED: with the
recompute applied, the promoted casualty was still treated at the
non-surgical destination (21 violations at seed=42, unchanged pre/post fix).
Root cause verified live, not inferred: the hold destination is chosen at
engine.py:680-688 BEFORE the hold gate; the hold loop (engine.py:720-848)
re-checks that destination's fullness only and never re-evaluates it — the
truthful flag has no routing decision left to influence (probe: a fresh
routing call from R1-HOLD post-promotion selects R2-S). **Gate ruling:
(b)+(c) hybrid.** The recompute lands as a flag-truth fix (bounds damage to
one stale hop; every event payload truthful); T-5-5 splits into
`test_requires_dcs_recomputed_on_promotion` (flag-level, green) and
`test_promotion_does_not_reroute_committed_hold` (characterisation,
violations > 0, inverts at Step 3); the re-route decision is routed to
Step 3 as the re-plan-on-Clock-1 family alongside T-5-7's spatial twin —
one routing-semantics decision (re-plan triggers + waypoint meaning). EX-6
noted as possible implementation vehicle, not plan of record. Landed as
commit `bddd05e`; suite 127 green, O1 zero-diff, Rule-4 conserved.

## 5. Hard Rules compliance map (CLAUDE.md:18-66, verbatim sighted)

R1 yields: S1 adds no yields — compliant. · R2 toggle-gate: not a path-replacing extraction, but its letter ("Legacy path preserved") is honoured literally — legacy walk untouched; toggle declared per the ahead-of-wiring clause; fixed-seed equivalence: 12-test suite untouched at capability-OFF + T-5-2 controls. · R3 LOC tripwire: intrinsic-zone touch ≈4 LOC total (engine.py:680-684 plumb + :807-810 recompute) — under the ~30 trip; routing.py/mode.py are surface tier (≤150). **If implementation drifts the intrinsic-zone touch toward 30 LOC: STOP, human gate.** · R4 conservation: run `arrivals == dispositions + in_system` after each commit; T-5-6's STRATEVAC disposition preserves it. · R5 import isolation: predicate is pure Python in routing.py, no SimPy import — compliant. · R6 notebook-proves-first: S1.2 is not an extraction; this file + S1_PREBUILD_ANSWERS.md serve as the proof spec (location nit — docs/MVP/ vs docs/phase<N>/ — human's call). · R7 golden regen: S1 forbids regen outright — stricter than the rule. · R8 doctrine-as-config: toggle makes capability-aware/blind a pure config axis — compliant and synergistic.

## 6. S1.1 — blackboard facility writer: HELD, three preconditions

Verdict line (MAAFI_VERDICT.md:83, verbatim sighted): tier **I (INTRINSIC)**, ~20–40 LOC, "One per-tick callback (C2). Unblocks #4/#42/#53/#58. Watch the mascal_active two-writer collision (C10)." The verdict itself tiers the writer intrinsic — v1's trace-neutral-sensor premise contradicted the verdict, not merely the code. Rule 3 places the blackboard in the intrinsic zone: the eventual build is a **mandatory human-gated change**.
Known hazards (Q7/Q8): `set_facility_context` (blackboard.py:151-160) writes a global scalar triple including `mascal_active=False` on every call — clobbers the factory's per-casualty value (casualty_factory.py:225; collision C10). Required amendment when building: `mascal_active: bool | None = None`, write only when not None. `CheckFacilityUtilisation` (bt_nodes.py:126-136) may sit in a live tree — populating the key could flip dormant decisions. Wildcard-subscriber design risks last-writer-wins scalar aliasing; the verdict's per-tick-callback shape (engine call-site immediately before the consuming tick) is the likely correct design — FQ1 locates it.
**Preconditions to lift the hold:** (1) FQ1/FQ3/FQ4 answered; (2) writer ACs AUTHORED into MVP_ACCEPTANCE.md — none exist there today (grep-confirmed: no writer/blackboard/mascal_active hits; AC set is 19/46/5/1/10/30/44/45) — drafted from FQ answers + the verdict line, human-ratified; (3) Rule-3 human gate scheduled. Note: verdict says #4/#42/#53/#58; the handover added #39 (stockout write-back) — FQ3 resolves whether #39 belongs to this writer or a separate mechanism.

### S1.1 OUTCOME (2026-07-06) — BUILT, hold lifted per preconditions

All three preconditions were met before build: FQ1/FQ3/FQ4 answered (S1_FOLLOWUP_ANSWERS.md); AC-W.1–W.5 authored into MVP_ACCEPTANCE.md @ `000c287` (human-delegated); Rule-3 human gate given at authorisation of BUILD_S1_1.md v1.1 (instruction file blob `748d492`, committed alongside this block). DPs 1–3 accepted at gate.

**Built (commit `339b940`):** `enable_facility_writer` toggle (default False, no routing dependency) · `set_facility_context` None-sentinel (the C10 fix flagged above — an omitted `mascal_active` no longer clobbers the factory's per-casualty value) · `src/faer_dev/simulation/facility_writer.py`, direct-call shape per the verdict's C2 per-tick-callback ruling, NOT a bus subscriber · three engine write-sites: FACILITY_ARRIVAL emission (engine.py:963 pre-build numbering), post-bed-acquire, post-bed-release at context exit (TREATMENT_END logs inside the `with`; occupancy only reflects the release at exit — placement matters and is test-cited).

**Contract recorded:** `facility_beds_available[fid]` per-facility dict is the durable consumer contract for #42/#53; the global scalar pair (`facility_utilisation`, `fst_queue_depth`) means "facility most recently written" — per-decision semantics only (#4's shape). Dept/r1 dict keys deliberately NOT written — #4 defines them at its decision moment. #58 weather keys not written (writer-insufficient per verdict).

**Evidence:** T-W-2 sentinel red witnessed (`False is True` clobber) then green · T-W-1 killer: snapshot ≡ event-stream derivation, per-facility and last-written scalars · T-W-3a writer ON≡OFF digest (the standing consumer-goes-live tripwire) · T-W-4 determinism · T-W-5 no-aliasing with colocated reads · combined inverted+writer smoke conserved. Suite 127 → 134, green ×2 post-commit; O1 golden byte-identical, regen not used; Rule-4 conserved on defaults / writer-on / writer+inverted (13/13/7 arrivals=dispositions — writer-on matches defaults exactly; the inverted delta is factory RNG consumption, not the writer).

**Rule-3 record:** intrinsic-zone LOC actual = **36 behaviour-bearing** vs the 35–45 declaration (within); raw added lines = 75, of which 39 are spec-mandated docstrings/comments (the §1 contract-intent documentation). Counting convention stated for the gate: the declaration is read as behaviour-bearing lines; every added line traces to a BUILD_S1_1 §1–§3 requirement.

**Consumer wiring remains UNAUTHORISED:** first consumer (#4) re-gates AC-W.3 at its own build.

## 7. FQ — read-only follow-up (answer into docs/MVP/S1_FOLLOWUP_ANSWERS.md, cite file:line)

FQ2 — ANSWERED out-of-band (verbatim ACs + Hard Rules sighted; recorded in this file §3/§5).
FQ1 — Where does the engine tick BT trees/nodes that read `facility_utilisation` and `mascal_active`? At default toggles, does any live decision path execute `CheckFacilityUtilisation` / `CheckMASCALActive`? What thresholds, set where?
FQ3 — Map features #4, #42, #53, #58 (and the handover's #39) to the blackboard keys/readers each consumes: what needs writing, at what cadence, per-facility or scalar?
FQ4 — The inverted-factory path (casualty_factory.py:222-225): which toggle enables it; at default toggles is `mascal_active` written at baseline; who reads it and when?

## 8. Phase gate — Definition of Done (STOP for human confirmation)

□ T-5-1 killer green on both strangler params · T-5-G guard green
□ T-5-2 a/b/c: digest control identical · AC-5.2 liveness green · coin ON≡OFF identical
□ T-5-3 determinism double-run equal · T-5-4 non-dominance green
□ T-5-5 stale-flag fix green; promotion site recomputes `requires_dcs`
□ T-5-0: full suite green — 114 + new; O1 byte-identical (zero diff); O2–O6 untouched
□ Rule 4 conservation checked after each commit
□ T-5-6/T-5-7 characterisations documented; gate decisions tabled: STRATEVAC starvation · O7 absence (built set is O1–O6) · R16a-open-at-defaults minute · legacy-retirement close-out path
□ FQ1/FQ3/FQ4 answered in docs/MVP/S1_FOLLOWUP_ANSWERS.md via Write tool, ls-confirmed
□ Hygiene: seed=42 · British English · nothing outside §0 fence · AMEND-1 and AMEND-2 to MVP_ACCEPTANCE.md confirmed done by human

HALT. S1.1 build and Step 2 are queued, logged, NOT authorised.

## 9. Kickoff prompt (verbatim, for CC in Cursor)

NOT plan mode. Confirm main @ 679ecc0, clean tree. pytest baseline (expect 114 green) → read docs/MVP/BUILD_S1.md in full → chore commit → S1.2a red-then-green, one commit (killer test parametrised ×2 strangler configs; graph config sets BOTH routing toggles; guard test included) → S1.2b red-then-green, one commit → run full suite; assert O1 byte-identical — any golden diff is stop-and-report, regeneration is not sanctioned → check Rule-4 conservation after each commit → answer FQ1/FQ3/FQ4 read-only into docs/MVP/S1_FOLLOWUP_ANSWERS.md (Write tool + ls confirmation) → HALT at the §8 gate with the DoD checklist filled. Rules: seed=42; suite stays green; British English; inline-dict/deepcopy fixtures only; engine.py:84-121 is untouchable; intrinsic-zone touch drifting toward 30 LOC = STOP for human gate; nothing outside the §0 fence; S1.1 is HELD — do not touch blackboard.py beyond reading; MVP_ACCEPTANCE.md is human-owned — never edit it.

---
*Pending: D1′ (strangler-side + guard) and D2′ (Step-3 entry criterion) sign-offs · AMEND-1/AMEND-2 manual edits · v3 committed to docs/MVP/BUILD_S1.md · gate decisions listed in §8 · writer-AC authoring before S1.1.*
