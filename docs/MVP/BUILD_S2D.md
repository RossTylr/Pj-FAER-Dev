# BUILD_S2D — S2 deviation closure (D2 dual-root · D4 lint)
Authority: S2 gate ruling 7 Jul ▸ FINAL v1 ◆ design (preserved e9dd941).
RULE-3: ≤30 intrinsic LOC declared; gate given at authorisation.
D6 (roster full-row schema) DEFERRED to POLYBIUS lane — register row,
not built here. D1/D3/D5/D7 accepted as-built (D3 minuted: Exp(1) is
the canonical Sellke frailty — as-built improves the spec).

## D2 — dual-root seed semantics (red-then-green)
Identity axis roots on patient_seed (fallback: master_seed); system
axis roots on master_seed; replication_index enters BOTH axes.
patient_seed=None MUST be a byte-exact no-op: keyed golden and all
digests unchanged at defaults — assert explicitly. If None cannot be
made a no-op without a regen, STOP and report before any regen.
Tests (I-7 proper form):
- patient_seed varied at fixed master → ARRIVAL sim_times byte-
  identical, roster hashes DIFFER ("same schedule, different people").
- replication_index varied → both differ.
- Clause 3: master_seed varied at fixed patient_seed (e.g. master 1 vs
  999, patient_seed=42) → roster hashes byte-IDENTICAL ("same people"),
  ARRIVAL sim_times DIFFER. This is the proper-form successor to the
  superseded single-root pairing clause at test_rng_keyed.py:301-317.
- I-1–I-5, route-divergent fixture, full suite: green unmodified.

## D4 — fallback lint (zero src lines)
Static test: no unseeded default_rng() / module-level np.random.* /
random.* draws anywhere in src/ (the triage.py:42-43 hazard class).
Keyed-mode constructor fallbacks raise — UNCONDITIONALLY (rng=None
forbidden in all modes; a keyed-only raise would leave the unseeded
expression alive and the lint permanently red). Behaviour-neutral on
all engine paths (engine always passes _rng); I-5 must confirm.

## DoD
□ I-7 all THREE clauses green, red witnessed for D2 □ None-is-no-op
asserted, zero golden diff □ lint green, fallback-raise tested
□ intrinsic LOC ≤30 reported □ register rows: D2/D4 CLOSED, D6
deferred-to-POLYBIUS added □ deviations table vs this file in commit
footer. ONE feature commit (+ this file's docs commit).
