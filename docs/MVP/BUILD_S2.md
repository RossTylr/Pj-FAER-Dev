# BUILD_S2 — Step 2: keyed-draw RNG architecture (slice 0) + config machinery (slice 1)
### AS-BUILT RECORD (finalised 2026-07-07; replaces the FINAL v1 instruction file, preserved verbatim at `e9dd941`). Authority chain: docs/MAAFI/MAAFI_VERDICT.md ▸ RNG design ratification (5 Jul gate) ▸ FINAL v1 (`e9dd941`) ▸ this record. Witnesses and minutes: docs/MVP/S2_BUILD_LEDGER.md.

**Baseline:** `4b28bad` · 134 green · comparison lane FROZEN (RNG_DIAGNOSTIC.md: stream
contamination, k=3). **Final state:** 153 green · keyed default · **comparison lane
REOPENED** (thaw minuted) · first paired evidence produced (VR1_RESULTS.md).

## Design as built

- Unit of synchronisation is the DRAW: identity-axis draws keyed
  `(casualty_uid, purpose, occurrence)`, system-axis `(stream, occurrence)`.
  Per-draw keying, not casualty-level decks.
- **Philox counter-based keying** (`src/faer_dev/core/rng.py`): 256-bit counter encodes
  `(0, occurrence, purpose_index, blake2b-64(entity))`; 128-bit key from
  `SeedSequence(entropy=(master_seed, replication_index))`. **`.spawn()` forbidden on
  the identity axis** — counter blocks are position-free.
- Root entropy carries the replication index (`ensemble → builder → engine`).
  `patient_seed` is live in keyed mode: it pins the SINGLE keyed root across ensembles
  (paired arms across different `base_seed`s — invariant I-7); shared mode keeps the
  legacy `base_seed + i` untouched.
- **Eager** at creation: TRIAGE, MECHANISM, PRIMARY_REGION, SECONDARY_COUNT,
  SECONDARY_REGIONS (one array draw-event), SEVERITY, POLYTRAUMA (inverted path),
  FRAILTY_THRESHOLD (reserved, unused — deterioration untouched at S2; Sellke rescoped
  to the Step-4 PFC adjudication per FINAL v1 ◆). **Lazy:** TREATMENT (one purpose,
  three engine sites; episode n), VEHICLE_RETURN (casualty leg n — per FINAL v1 ◆),
  VITALS (per ATMIST handover n). **System axis:** ARRIVALS(n), MASCAL_GAP/SIZE(event
  n), MASCAL_OFFSETS (one keyed array draw per event — arrays per logical draw-event ◆).
- Roster behind `enable_roster`, rows at creation; digest reuses the F0.1 canonical
  dump; parquet writer = **optional extra** (ruling): `pip install faer-dev[roster]`.
- Purpose codes: closed enum `RNGPurpose`; ad-hoc keys rejected at the draw API.
- Dual-mode strangler `rng_mode: shared | keyed`; **keyed is the DEFAULT since 0e**
  (one sanctioned O1 regen, artefact `docs/MVP/S2_0E_GOLDEN_REGEN.md`); shared retained
  for archaeology, byte-frozen, policed by the pinned I-5 digest + wire-discrimination
  check.

### Census corrections (ledger, 0c entries)

- **VITALS is LAZY** — draws per ATMIST handover (`core/atmist.py` → `vitals.py`),
  occurrence = handover n.
- **TRANSIT is a per-mode vehicle-mission stream** (`transit:<mode>`, mission n): the
  only production trip-time consumer is the BatchCoordinator, whose missions may serve
  several patients. Gate: provisionally accepted; **VR-1 arbitrated — see OUTCOME.**

### DEVIATIONS from FINAL v1 (`e9dd941`) — on the record, none silent

The build sessions executed the §6 kickoff prompt; FINAL v1's ◆ refinements were never
loaded into the build session (the file was authored between sessions and sat untracked).
Deltas, each with disposition:

| # | FINAL v1 specified | As built | Disposition |
|---|---|---|---|
| D1 | Entropy layout: SeedSequence-style tuples, `uid_int` = factory counter n | Philox counter block, entity = blake2b-64 of uid string | Equivalent keying properties (position-free, order-invariant); string-hash also covers system streams uniformly. ACCEPT-AS-BUILT proposed |
| D2 | **Dual-root seed semantics**: `patient_seed` = identity-root override, separate from system root — "vary patient_seed at fixed master → identical arrival schedule, different people" | Single root; `patient_seed` pins the WHOLE root in ensemble keyed mode (varying it changes arrivals too) | **SUBSTANTIVE — not implemented.** The "same schedule, different people" axis-separation invariant does not exist as built. Register row added; needs a gate ruling (implement at Step-3 entry vs accept single-root) |
| D3 | FRAILTY drawn uniform(0,1) | Exp(1) (standard Sellke threshold form) | Both inert/reserved; monotone-equivalent. ACCEPT-AS-BUILT proposed; Step-4 adjudication picks the final form |
| D4 | Keyed mode RAISES on `rng or default_rng()` constructor fallbacks + standing lint invariant (I-6 LINT: no unseeded construction in src/) | Not implemented; I-6 slot used for the route-divergent equivalence fixture instead; latent fallbacks remain dormant-but-present (Q1 census) | **OPEN.** Lint-as-test is zero-src-lines and cheap; fallback-raise touches intrinsic-zone constructors. Register row added — candidate first item of the next session |
| D5 | VITALS keyed per field (GCS/HR/BP/RR/SPO2) | One VITALS draw-event per handover yielding the 5 values | Same invariance class (array-per-logical-draw-event rule ◆). ACCEPT-AS-BUILT proposed |
| D6 | Roster assembled at the ARRIVAL emission (identity + derived decision fields + key-schema version stamp) | Roster at `create()` — identity fields + frailty only; no derived fields; no key-schema version | **PARTIAL.** I-2's roster clause polices the as-built rows; derived fields are deterministic (draw-free routing) so invariance is not weakened. Register row: enrich roster (derived fields + key-schema version) when POLYBIUS schema is defined |
| D7 | I-3 via widened `log_digest(events, draw_counts=None)`, explicitly "no synthetic events" | Additive `log_digest_with_draws()` folding counts as a synthetic terminal row | Functionally equivalent detector; signature of `log_digest` untouched (smaller blast radius). ACCEPT-AS-BUILT proposed |

## Slice log (all commits atop `4b28bad`)

| Commit | Content |
|---|---|
| `1773db7` | S2_PREBUILD_ANSWERS.md (Q0–Q9; Q0 verdict **BOTH**) |
| `b14eddc` | PREREG_VR1 registered (before any keyed comparison viewed) |
| `2996aa5` | 0c-1 keyed core + plumbing (shared untouched; 134 green; O1 identical) |
| `cc55fcf` | 0c-2 eager draws + frailty + roster (**I-2 red witnessed**: attributes already invariant — the two Q0 defects proved separable live) |
| `a062487` | 0c-3 lazy + system-axis (**I-2 GREEN keyed**) |
| `6b2b4ea` | 0d invariants I-1–I-7 + poison (red witnessed: one mis-keyed purpose diverges 51/56 casualties) |
| `62da8c9` | 0e default flip + ONE sanctioned golden regen + **THAW minuted** |
| `00b20ff` | slice 1: guards (empty-facilities RAISE · role-presence · GM-3) · version stamp · `triage_distribution` WIRED · `scenario_overrides` API · I-5 re-pinned with the Amendment-1 discriminating check |
| `436a0dc` | PREREG amendment (resource pair) — predates the VR-1 run by git order |
| `c745763` | tails: T-5-8 mixed-caseload over-filtering control · Rule-8 addendum ratified |
| `8229299` | VR-1 results |
| `e9dd941` | FINAL v1 instruction file preserved as-received |

**Sanctioned surface seam (precedent by record, gate recording note):** the
`triage_distribution` wire is a builder-side POST-CONSTRUCTION ATTRIBUTE ASSIGNMENT
from `config/` onto `engine.casualty_factory.triage_shift` — hasattr-guarded, zero
intrinsic-zone lines, inverted/BT path unaffected by design, MASCAL-side distribution
context-registered. Config-derived engine annotations (`scenario_stamp`) use the same
seam.

## Re-baseline matrix (settled empirically at 0e/slice 1)

- **RE-BASELINE (complete):** O1 golden (once, artefact committed) ·
  `hold_promotion_run` recipe (cohort 60→120, assertions untouched) · I-5 pin
  (slice 1, WIRE ruling; `test_i5_wire_discrimination` proves the delta is
  config-value-only — override back to context defaults reproduces the pre-wire pin
  `9164bd97…` byte-for-byte).
- **PROPERTY-SAFE — all passed unmodified:** O2 ±0.15 (now policing the WIRED
  distribution) · O3 direction · O4 · O5 · O6 · Rule-4 conservation · T-5-1/2/3/4/6/7 ·
  T-5-5a/b · every toggle-equivalence and double-run suite · seed-difference.
  **The Q7 census predicted this blast radius exactly.**

## §5 Definition of Done — final

☑ 0c-1 shared untouched, 134 green · ☑ 0c-2/0c-3 keyed reds witnessed then green ·
☑ 0d I-1–I-7 green, poison red witnessed · ☑ 0e golden diff reviewed; property-safe
unmodified; recipe re-tune justified · ☑ THAW minuted (I-2 at plain defaults) ·
☑ slice 1 + both rulings recorded (RAISE · WIRE) · ☑ PREREG committed pre-viewing;
amendment pre-run · ☑ Rule-4 ×3 configs · ☑ intrinsic LOC 204 raw / 176 code-only vs
120–160 declaration — **accepted at gate** (precedence clause; calibration lesson
ledgered) · ☑ Rule-8 addendum ratified · ☑ parquet ruling recorded (optional-extra) ·
⚠ D2/D4/D6 deviations open on the register (this record is their disclosure).

## OUTCOME (gate rulings folded in, 2026-07-07)

- **Thaw language (SCOPED):** *casualty identity and arrival streams are provably
  config-invariant; journey-draw pairing is per-purpose.* I-2 certifies identity +
  arrival invariance, not full-trajectory pairing.
- **Transit provisional — arbitrated by VR-1:** golden-hour ITT (the transit-heavy
  metric) paired to within 3/200 in one rep of twenty; variance ratio **776** vs
  unpaired. Mission-stream keying as built is empirically sufficient for paired
  comparison at this scale. Standing question rides to Step 3: does
  re-plan-on-promotion move dispatch order enough to make the provisional bite?
- **VR-1 headline (first quotable paired evidence):** registered hypothesis satisfied
  overwhelmingly — ratio 776 on golden-hour ITT; view-variant and mortality paired
  PERFECTLY (all 20 diffs zero); the resource perturbation proved inert at these
  parameters (byte-exact pairing under an inert config delta; binding perturbation
  deferred to PoC design). Secondary observation for 5a: doctrine sensitivity lives in
  treatment timing; mortality as-built is identity-carried.
- **Registry lesson (standing):** a fixed seed buys reproducibility, not comparability
  — comparability is a designed property.

HALT. Step 3 (multi-POI + routing semantics) and Step-4 PFC adjudication remain
UNAUTHORISED; the per-POI sub-RNG dissolves into the key tuple — Step 3 inherits this
architecture and builds none of it.
