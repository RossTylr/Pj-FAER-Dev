# CURRENT — FAER-MIL canonical state

<!-- ACTIVE_PHASE: phase2 -->
<!-- CURRENT_STEP: phase2/NB40_graph_routing -->
<!-- The HTML markers above are the check_claude_md.py parity-drift anchors (moved here
     from the deleted docs/CURRENT.md at the S2 close-out reconciliation). They track the
     PHASE-2 NB extraction frontier, which is unchanged by the MVP build; MVP state is
     the prose below. -->

*Single source of phase truth (RAIE v3). **Rev 3.1**, 7 Jul 2026 — S2-D deviation
closure atop Rev 3 (S2 close-out). Replaces Rev 2; the stale `docs/CURRENT.md` marker
host is deleted and the checker reads this file.*

**HEAD:** S2-D deviation-closure chain atop the S2 close-out (`ffdd257`) — instruction
file `docs/MVP/BUILD_S2D.md`, as-built record in the feature commit's deviations footer.
163 tests green.
**Phase:** MVP build. F0 complete (O7 = scheduled debt, GM-2). S1.1 complete. **Step 2
COMPLETE** (slice 0 keyed-draw architecture + slice 1 config machinery + tails), gate-
ratified 2026-07-07 with deviations D2/D4/D6 disclosed. **S2-D COMPLETE**: D2 dual-root
BUILT (I-7 proper form, three clauses) · D4 lint + unconditional raise BUILT · D6
deferred to the POLYBIUS lane · D1/D3/D5/D7 accepted as-built (D3 minuted: Exp(1) is
the canonical Sellke frailty — as-built improves the spec).
**Evidence status:** **COMPARISON LANE OPEN** (thaw minuted at 0e; scoped wording is
normative: *casualty identity and arrival streams are provably config-invariant;
journey-draw pairing is per-purpose* — I-2 certifies identity + arrival invariance, not
full-trajectory pairing). First quotable paired evidence: `docs/MVP/VR1_RESULTS.md`
(routing-pair golden-hour ITT variance ratio 776; view/mortality paired perfectly;
resource perturbation inert at tested parameters).
**Standing reporting rule (5a):** any quoted metric carries numerator/denominator, exact
fractions, and an ITT variant alongside any conditional form; probe runs go through the
F0.2 harness with the violation census attached.
**Next authorisation decision:** Step 3 (multi-POI + routing semantics) interrogation —
carries the standing transit question (does re-plan-on-promotion move dispatch order
enough to make the transit provisional bite?). The D2 dual-root ruling is discharged
(S2-D); pre-build answers in `docs/MVP/S3_PREBUILD_ANSWERS.md`.
**Sequence (locked):** S1.1 ✓ → Step 2 ✓ → Step 3 → Step 4 (PFC, own track) → 4b legacy
retirement (GM-4) → Step 5a metric probes → Step 5 PoC.

## DEFERRED REGISTER — every paused item, with intent

| Item | Intent | Trigger / vehicle |
|---|---|---|
| **D6: roster enrichment — DEFERRED TO POLYBIUS LANE** (S2-D gate ruling: register row, not built; derived decision fields + key-schema version stamp; FINAL v1 specified ARRIVAL-emission assembly) | EXTEND — as-built roster is identity-PURE at create() (S2-D removed spawn_time + MASCAL provenance: system-axis facts; provenance columns may be re-added deliberately) | When the POLYBIUS parquet schema is defined |
| **Transit keying = per-mode mission stream** (provisional, VR-1 arbitrated SUFFICIENT: ratio 776, leak 3/200 in 1/20 reps) | REVISIT iff a transit-dependent estimand shows weak pairing | Step-3 routing-semantics interrogation (re-plan-on-promotion dispatch-order question) |
| **VR-1 follow-up: binding resource perturbation** (the +4-bed arm proved inert — byte-exact pairing, dispatch sensitivity unexercised) | DESIGN a binding perturbation for the PoC comparison shape | Step-5 PoC design |
| LOC counting-convention calibration | LESSON — declarations state the convention (raw vs code-only; dual-mode duplication included) up front | Every future Rule-3 declaration |
| Hold re-route on promotion (T-5-5b) + path-purity (T-5-7) | FIX — one routing-semantics decision (re-plan-on-Clock-1 + waypoint meaning) | Step-3 entry criteria; both characterisation tests INVERT to ==0 when landed |
| O7 Erlang/Little oracle | BUILD — F0 debt (GM-2); **now unblocked** (`scenario_overrides` landed) | Before Step 5; single-node collapse via overrides |
| Rule-4 terminal-conservation scoping | RESOLVE — drained-fixture assertion is the terminal form | O7 window |
| STRATEVAC starvation ruling + warm-up probe + violation/promotion census + conditional-metric standard | DECIDE + PROBE before any sweep (GM-1/GM-5) | Step 5a pre-flight |
| Legacy walk retirement | RETIRE — R16a mitigated behind flag, open at defaults | GM-4: post-Step-3 gate, pre-Step-5; own mini instruction file |
| Capability-ON interim rule (GM-3) | **ENFORCED** — `config/guards.py` + `EnsembleBuilder(analysis=True)`; retires with GM-4 | Standing until legacy retirement |
| AC-1.4 byte-identical defect | AMEND with context (per-POI sub-RNG dissolves into the key tuple) | Step-3 AC authoring |
| PFC canonical model — now THREE candidates: inline 0.20× ladder · pfc.py linear · **Sellke on the pre-drawn `frailty_threshold`** (reserved in every keyed roster) | ADJUDICATE — modelling decision; loser + inert `enable_extracted_pfc` retired | Step 4, own track; clinical judgement + literature tier |
| Dept/r1 blackboard dict contracts | DEFINE at the consumer | #4 build (AC-W.3 re-gate fires) |
| #58 weather keys | AUTHOR as own feature | When #58 scheduled |
| FacilityLoadView intermediate overcount (views.py:65-66) | FIX via writer's per-facility dict | #42 build |
| `dept_fst_capacity` not loader-mappable · inverted triage tree defaults (engine.py:173) | FIX when affected trees gain a tick site | #4 build |
| Builder silent drops: or_tables/icu_beds/ventilators/has_lab | FIX before MMSL demand modelling | MMSL lane opening |
| CROSSOVER_PROBES (commitment calendar · CP-SAT · Whittle · certificates · attribution ledger) | PARKED wholesale | EXP-IB-1000 lane |
| maafi-protocol.skill three-way rubric polish | OPTIONAL, 10 min | Whenever |

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
dual-file reconciliation → this revision (docs/CURRENT.md deleted; checker re-pathed) ·
Rule-8 addendum → ratified verbatim in CLAUDE.md · CLAUDE.md pointer updates → done at
close-out · PREREG_VR1 → registered, amended pre-run, RUN (results committed).
