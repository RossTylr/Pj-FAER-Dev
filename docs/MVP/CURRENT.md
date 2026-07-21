# CURRENT — FAER-MIL canonical state

<!-- ACTIVE_PHASE: phase2 -->
<!-- CURRENT_STEP: phase2/NB40_graph_routing -->
<!-- The HTML markers above are the check_claude_md.py parity-drift anchors (moved here
     from the deleted docs/CURRENT.md at the S2 close-out reconciliation). They track the
     PHASE-2 NB extraction frontier, which is unchanged by the MVP build; MVP state is
     the prose below. -->

*Single source of phase truth (RAIE v3). **Rev 4**, 21 Jul 2026 — Session R register
reconciliation: round-B findings (Q11–Q19) recorded, closures marked, S3 dispositions
set. Replaces Rev 3.1 (S2-D deviation closure).*

**HEAD:** Session R docs chain atop the round-B answers (`debf01f`) — instruction file
`docs/MVP/BUILD_S3.md`, doctrine authority `docs/MVP/ROUTING_SEMANTICS_NOTE.md` (signed
21 Jul 2026), session record `docs/MVP/S3_BUILD_LEDGER.md`. 163 tests green,
0 deselected.
**Phase:** MVP build. F0 complete (O7 = scheduled debt, GM-2). S1.1 complete. **Step 2
COMPLETE** (slice 0 keyed-draw architecture + slice 1 config machinery + tails), gate-
ratified 2026-07-07 with deviations D2/D4/D6 disclosed. **S2-D COMPLETE**: D2 dual-root
BUILT (I-7 proper form, three clauses) · D4 lint + unconditional raise BUILT · D6
deferred to the POLYBIUS lane · D1/D3/D5/D7 accepted as-built (D3 minuted: Exp(1) is
the canonical Sellke frailty — as-built improves the spec).
**Step 3 status: SESSION R CLOSED, α UNAUTHORISED.** The doctrine ruling that was the
last human-gated item on the critical path is signed: **D-A nodes-may-be-passed · D-B
divert-on-state-change (bounded to leg boundaries and hold-retry) · D-C mixed, and
deterioration CONFERS bypass**. Mechanisms auto-selected: **M2 + M3, both flags
recompute**. Sessions α and β each require their own human gate word.
**Evidence status:** **COMPARISON LANE OPEN** (thaw minuted at 0e; scoped wording is
normative: *casualty identity and arrival streams are provably config-invariant;
journey-draw pairing is per-purpose* — I-2 certifies identity + arrival invariance, not
full-trajectory pairing). First quotable paired evidence: `docs/MVP/VR1_RESULTS.md`
(routing-pair golden-hour ITT variance ratio 776; view/mortality paired perfectly;
resource perturbation inert at tested parameters).
**Standing reporting rule (5a):** any quoted metric carries numerator/denominator, exact
fractions, and an ITT variant alongside any conditional form; probe runs go through the
F0.2 harness with the violation census attached.
**Next authorisation decision:** BUILD_S3 session α (gate word 1) — hygiene · M3
boundary recompute · multi-POI. Pre-build answers in `docs/MVP/S3_PREBUILD_ANSWERS.md`
(Q1–Q10) and `docs/MVP/S3_FOLLOWUP_ANSWERS.md` (Q11–Q19).
**Sequence (locked):** S1.1 ✓ → Step 2 ✓ → Step 3 (R ✓ → α → β) → Step 4 (PFC, own
track) → 4b legacy retirement (GM-4) → Step 5a metric probes → Step 5 PoC.

## DEFERRED REGISTER — every paused item, with intent

| Item | Intent | Trigger / vehicle |
|---|---|---|
| **D6: roster enrichment — DEFERRED TO POLYBIUS LANE** (S2-D gate ruling: register row, not built; derived decision fields + key-schema version stamp; FINAL v1 specified ARRIVAL-emission assembly) | EXTEND — as-built roster is identity-PURE at create() (S2-D removed spawn_time + MASCAL provenance: system-axis facts; provenance columns may be re-added deliberately) | When the POLYBIUS parquet schema is defined |
| **Transit keying = per-mode mission stream** (provisional, VR-1 arbitrated SUFFICIENT: ratio 776, leak 3/200 in 1/20 reps). **TRIGGER MET on two grounds** (M3 re-routing, Q17; multi-POI batch coupling, Q19.2). Resolution candidate: batcher gains origin dimension + mission stream re-scoped per (mode, origin) | REVISIT — decide+build at S3; re-measure VR-1-style post-build | **BUILD_S3 slice 4**, behind `enable_origin_transport`; two-stage re-measure → `S3_TRANSPORT_REMEASURE.md` |
| **VR-1 follow-up: binding resource perturbation** (the +4-bed arm proved inert — byte-exact pairing, dispatch sensitivity unexercised) | DESIGN a binding perturbation for the PoC comparison shape | Step-5 PoC design |
| LOC counting-convention calibration | LESSON — declarations state the convention (raw vs code-only; dual-mode duplication included) up front. **Applied at S3**: RAW, max(added,removed) incl. comments, dual-mode counted | Every future Rule-3 declaration |
| Hold re-route on promotion (T-5-5b) + path-purity (T-5-7) | FIX — one routing-semantics decision, now RULED (D-A + D-B/D-C → M2 + M3) | **BUILD_S3**: T-5-5b inverts at slice 1; T-5-7 stays green as the defaults pin and its waypoint twin T-5-7w carries the inversion at slice 3 |
| **AC-1.4 byte-identical defect — ENLARGED** | AMEND: per-POI sub-RNGs are unnecessary (the POI namespace dissolves into the key tuple, Q12.3); system-axis stream scoping is **MANDATORY** (Q11.4, measured); the AC as written tests determinism, not pairing — the amendment must add the pairing clause | **BUILD_S3 slice 5**, S3-AMEND-2 |
| **AC-1.2 nearest-facility GHOST** — the mechanism does not exist: coordinates are stored (`schemas.py:159`, `topology.py:38`) but no code computes a distance from them; routing is first-match over ROLE_ORDER or Dijkstra over travel time (Q18.3) | AMEND — choose the reading: edges-encode-nearness (iron_bridge precedent) vs build coordinate geometry. **Ruled: edges-encode-nearness**; geometry deferred to its own row below | **BUILD_S3 slice 5**, S3-AMEND-1 |
| **Coordinate geometry** (a coordinate-derived edge weight or distance function) | BUILD or DROP — deliberately, once a scenario needs geometry rather than encoded travel times | Own feature; NOT S3 |
| **S3 KEYING DESIGN-OF-RECORD** (ruled, HUMAN VETO open): asymmetric namespacing on both axes — N=1 scenarios keep legacy forms (`"arrivals"`, `CAS-NNNN`) preserving every committed digest (Q11.4 verified byte-identical); N≥2 get per-POI streams + `id_prefix` factories (collision-safe, POI-stable identity). Zero-golden-regen posture: any O1 diff during S3 = STOP, never regen | RECORD — the asymmetry is a deliberate trade, and it makes the key schema non-compositional, which raises the value of D6's key-schema version stamp | **BUILD_S3 slice 2**; guarded by `require_comparable_arms` (below) |
| **Cross-POI-count arm comparison** — an N=1 arm and an N≥2 arm differ in KEY SCHEMA, so any paired comparison across that boundary is silently invalid (the Hard-Rule-8 failure mode) | GUARD — `scenario_stamp` gains `poi_count`; `require_comparable_arms(a, b)` in `config/guards.py` raises `ValueError` on mismatch | **BUILD_S3 slice 2**; invoked in AC-1.4's arrange step |
| **S3 SLICE-0 HYGIENE BUNDLE** — dead `_arrival_process` (`engine.py:1321-1339`, zero callers) · synthesised-POI insertion-order trap (`builder.py:269-271` inserts before declared facilities; `engine.py:1369-1372` takes the first, so an undeclared POI-prefixed edge source STEALS the arrival source — measured digest change) · harness `_max_arrivals` multi-process close (`tests/harness.py:73-75`, plus `test_capability_routing.py:98` and `:273`) | FIX — behaviour-zero hygiene | **BUILD_S3 slice 0** |
| **GOLDEN-HOUR INTEGRITY BUNDLE** — the stamp ignores treatment (`engine.py:1040-1049`; measured `golden_hour_met=True` with zero care through a beds=0 R2) · `mining.py:259` substring twin has the same false positive and is additionally fooled by any facility id merely containing "R2" | FIX — a doctrine ruling must not weaponise a metrics bug, so this is IN SCOPE at S3 given D-A→M2. Definition RULED: stamp = first R2 arrival AT WHICH treatment occurs | **BUILD_S3 slice 3** (else 5a hardening) |
| **TRANSPORT PHYSICS BUNDLE** — the batched path applies NO turnaround (`transport.py:444-457`) while the unbatched path runs the full model (`engine.py:1281-1319`): two different vehicle-downtime models · the vehicle pool has NO geography, so a vehicle delivering POI-A→R1-A is instantly available to POI-B (perfectly-mobile assumption, minuted) | EXAMINE at S3 — multi-POI exercises both paths far harder. Turnaround unification lands behind `enable_batched_turnaround`; the geography assumption stays minuted, not built | **BUILD_S3 slice 4** |
| **HELD-CASUALTY STATE** — a held casualty holds NO bed, NO vehicle and NO destination-side slot (Q13.2); its state is a stale `IN_TREATMENT` (Q13.1); the intended destination is a loop-local only, not persisted on the entity | FIX — `PatientState.HOLDING` (already declared in the enum) set during holds + `intended_destination` persisted. RULE: `intended_destination` is engine-internal — in no event payload and no roster row | **BUILD_S3 slice 1** (rides M3, the mechanism that touches the hold loop) |
| **MASCAL LANE (#30)** — the detector is hardcoded, global and NOT config-mappable (`engine.py:246-248`; no builder mapping, no YAML key; sums every POI's arrivals, so N POIs trip the 20-in-15-min threshold N× sooner) · there are **TWO unconnected MASCAL notions**: the generator's `is_mascal` flag (which actually shifts triage) and the detector's state (which drives only MASCAL_ACTIVATE/DEACTIVATE and the metrics block) | BUILD — AC-30's "triggered not always-on" assertion must say WHICH notion it means. S3 design-of-record: per-POI generators with per-POI rates configurable; **detector fix deferred to #30** | #30 build; the S3 AC-1.1 fixture works around it with `mascal_enabled=False` |
| **Demotion unreachable** — `_retriage_for_deterioration` is promote-only by CP4 gate #7 (`engine.py:879`), which is in tension with the RATIFIED D-B ruling that triage change in **either direction** is a trigger. The M3 recompute mechanically supports withdrawal of bypass; no code path reaches it | RESOLVE — doctrine-vs-implementation gap, not merely a scoping note | CP4 re-gate, or the first authorised demotion mechanism |
| **Platform care-levels** (the §0101.3 continuity floor as doctrine states it) — the signed note rules the floor **platform-capability-relative**; S3's `waypoint_allowed` config proxy enforces it **per-facility**. Ruled axis ≠ built axis | REFINE — the gap IS the substance of the standing HUMAN VETO on M2 scoping | Post-S3; own feature |
| **Doctrine-note verbatim lifts pending** — `ROUTING_SEMANTICS_NOTE.md` carries paragraph refs plus key phrases, not full lifted paragraphs (source PDFs cannot be lifted in-session) | ENRICH — refs stand as authoritative pointers meanwhile; FM 4-02 edition/paragraph still to be verified at lift | When the human supplies the lifts |
| **STALE-PATH CHECKER RULE** — four instances now caught by hand (floor fiction · AGENTS.md · `docs/CURRENT.md` · the G3 `analytics/ensemble.py` citation). **Plus one LIVE**: `scripts/check_claude_md.py:134-136` emits error text naming the deleted `docs/CURRENT.md`, i.e. a failing checker run instructs the reader to edit a file removed at S2 | BUILD — a checker rule for the class; fix the live string in passing | Next hygiene session (outside Session R's docs-only fence) |
| **FACTORY UNIFICATION** — the legacy and inverted casualty factories have no retirement clock; `id_prefix`/`source_id` seams exist on both and are unused | UNIFY or retire one | #4 authorisation |
| O7 Erlang/Little oracle | BUILD — F0 debt (GM-2); **now unblocked** (`scenario_overrides` landed) | Before Step 5; single-node collapse via overrides |
| Rule-4 terminal-conservation scoping | RESOLVE — drained-fixture assertion is the terminal form | O7 window |
| STRATEVAC starvation ruling + warm-up probe + violation/promotion census + conditional-metric standard. **Added at round B:** `GoldenHourView` (ARRIVAL→DISPOSITION) and `metrics["golden_hour"]` (creation→R2 arrival) measure DIFFERENT things (Q14.3(2)) — one definition must win; a bed-constrained scenario is EXISTENTIAL (VR-1 Δ=0) | DECIDE + PROBE before any sweep (GM-1/GM-5) | Step 5a pre-flight |
| Legacy walk retirement | RETIRE — R16a mitigated behind flag, open at defaults | GM-4: post-Step-3 gate, pre-Step-5; own mini instruction file |
| **Origin-transport + batched-turnaround default-flips** (`enable_origin_transport`, `enable_batched_turnaround` — both land default False at S3) | FLIP — joins the legacy-bundle default-flip set | GM-4 |
| **AC-1.4 / AC-1.2 / AC-1.1 amendments** | APPLY — S3-AMEND-1/2/3, the ONLY sanctioned `MVP_ACCEPTANCE.md` edits. Note: S1's amendments were applied INLINE without labels, so no AMEND-1/2 blocks exist; labelled blocks begin at S3-AMEND-1 | **BUILD_S3 slice 5** |
| PFC canonical model — now THREE candidates: inline 0.20× ladder · pfc.py linear · **Sellke on the pre-drawn `frailty_threshold`** (reserved in every keyed roster) | ADJUDICATE — modelling decision; loser + inert `enable_extracted_pfc` retired | Step 4, own track; clinical judgement + literature tier |
| Dept/r1 blackboard dict contracts | DEFINE at the consumer | #4 build (AC-W.3 re-gate fires) |
| #58 weather keys | AUTHOR as own feature | When #58 scheduled |
| **FacilityLoadView intermediate overcount** (`views.py:65-66`) — increments on FACILITY_ARRIVAL, decrements only on DISPOSITION. **Waypoints (M2) make it STRUCTURAL rather than incidental** (Q14.3): a waypoint hop is a permanent +1 | FIX via writer's per-facility dict. S3 mitigates by making the view waypoint-aware; the underlying overcount stays #42 | #42 build (S3 slice 3 skips waypoint-flagged arrivals) |
| `dept_fst_capacity` not loader-mappable · inverted triage tree defaults (engine.py:173) | FIX when affected trees gain a tick site | #4 build |
| **Builder silent drops:** or_tables/icu_beds/ventilators/has_lab (`builder.py:278-287`). A per-POI weight key joins the SAME parse site (Q18.2) | FIX before MMSL demand modelling | MMSL lane opening (S3 adds `arrivals.per_poi` alongside) |
| CROSSOVER_PROBES (commitment calendar · CP-SAT · Whittle · certificates · attribution ledger) | PARKED wholesale | EXP-IB-1000 lane |
| maafi-protocol.skill three-way rubric polish | OPTIONAL, 10 min | Whenever |
| **Docker pull-forward** (UV-6: uv was its prerequisite and is now landed — the image becomes `uv sync --frozen --no-dev` over `uv.lock`, ~10 lines) | BUILD — the lockfile is the input that makes the Dockerfile trivial | Whenever scheduled; own mini instruction file |
| **Constraint-set retirement** (`[tool.uv] constraint-dependencies` is the 139-pin freeze, held temporarily so the first resolve could not move a version) | DROP + upgrade deliberately, gated by the same test+golden verification | A later, separately-authorised upgrade commit — never incidental |
| **ruff debt: 230 findings, unenforced** (identical at py310 and py312; ruff is not in the 163 and there is no CI, so nothing runs them) | DECIDE — adopt-and-fix, ratchet, or drop ruff; a linter nothing runs is a claim, not a control | Whenever; natural companion to a CI lane |

## CLOSED at Session R (Rev 4, 21 Jul 2026 — `a6e3dfe`)

- **Capability-ON interim rule (GM-3)** → **CLOSED, HOMED**: enforced by
  `config/guards.py` + `EnsembleBuilder(analysis=True)`. The mechanism has a home and a
  retirement vehicle (GM-4); it no longer needs a register row to survive.
- **Mixed-caseload killer variant** → **CLOSED**: landed as T-5-8 in the S2 tails
  (`test_capability_routing.py:258`), where it serves as the over-filtering control.
- **Empty/absent `facilities` semantics** → **CLOSED, RULED**: RAISE, implemented in
  `config/guards.py` (`require_role_presence`).
- **CLAUDE.md current-state note** → **CLOSED, SUPERSEDED**: the CURRENT.md machinery
  plus `scripts/check_claude_md.py`'s parity-drift markers now carry phase state; a
  prose note in CLAUDE.md would be a second source of truth.
- **The routing-semantics doctrine ruling itself** → **CLOSED, SIGNED**
  (`docs/MVP/ROUTING_SEMANTICS_NOTE.md`, 21 Jul 2026 / RT). This was the last item on
  the programme's critical path requiring a human ruling.

## CLOSED at S2-D (deviation closure, 7 Jul 2026 — BUILD_S2D.md)

**D2 `patient_seed` dual-root** → **BUILT**: identity axis roots on
`(patient_seed, replication_index)`, system axis on `(master_seed, replication_index)`;
`patient_seed=None` aliases the system key object (byte-exact no-op by construction,
zero golden diff). I-7 proper form: three clauses red-then-green + ensemble pairing +
None-no-op corollary. Identity roster purified in passing (spawn_time + MASCAL
provenance were system-axis facts inside the identity artefact — event log carries
both; MASCAL-conditioned identity is generative-model design, documented at I-7
clause 3). · **D4 unseeded-fallback lint + raise** → **BUILT**: AST lint over src/
(`tests/test_rng_lint.py`) green after the 6-site census (triage.py:43, injury.py:163,
arrivals.py:114, casualty_factory.py:50/:212, transport.py:206) converted to
UNCONDITIONAL `ValueError` on `rng=None` (BUILD_S2D.md as amended); I-5 confirms
byte-neutrality. · **D1/D3/D5/D7** → accepted as-built at the gate (D3 minute: Exp(1)
canonical Sellke frailty).

## CLOSED at S2 (moved out of the register, closure on record)

RNG dual-stream separation → **superseded by the keyed-draw architecture** (S2 slice 0)
· arrival-anomaly classification → RNG_DIAGNOSTIC verdict (b), repaired at 0c-3 ·
route-divergent equivalence fixture → I-6 · mixed-caseload killer variant → T-5-8 ·
empty-facilities semantics → **RAISE** (guards.py) · `triage_distribution` → **WIRED**
(builder seam; O2 polices; I-5 re-pinned with discriminating check) · CURRENT.md
dual-file reconciliation → Rev 3 (docs/CURRENT.md deleted; checker re-pathed) ·
Rule-8 addendum → ratified verbatim in CLAUDE.md · CLAUDE.md pointer updates → done at
close-out · PREREG_VR1 → registered, amended pre-run, RUN (results committed).
