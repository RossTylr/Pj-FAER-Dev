# VR1_RESULTS — variance-ratio experiment (run as registered)

*2026-07-07 · run per `PREREG_VR1.md` (registered at `b14eddc`, BEFORE any keyed
comparison was viewed) and its gate-directed amendment (resource pair, committed at
`436a0dc`, BEFORE this run — the git log is the witness). Keyed default, IRON BRIDGE,
seed 42, drained F0.2 runs (1440 min, `max_patients=200`; every run drained to
conservation, n = 200 arrivals in all 100 runs; surgical-at-non-capable violations = 0
in every arm). Script: session scratchpad `vr1_run.py` (+ `vr1_per_rep.json`).*

**This is the first quotable paired A-vs-C evidence the programme has produced** — the
comparison lane reopened at the S2 0e thaw; every number below is doctrine-attributable
under the keyed-draw architecture (identity + arrival invariance certified; journey-draw
pairing per-purpose).

## Design (as registered — no post-hoc changes)

- **Routing pair:** A = all-default toggles vs C = extracted+graph+capability.
- **Resource pair (amendment):** capability-ON baseline vs +4 beds at R1-ALPHA (8→12),
  capability-ON both arms, beds-only contrast. Baseline arm ≡ routing C arm by
  construction (identical scenario + toggles); executed once, shared.
- **Paired:** both arms on shared roots `(42, i)`, reps 0–19. **Unpaired:** first arm
  reps 0–19, second arm reps 100–119 (disjoint roots). n = 20 per arm.
- **Metrics (exact fractions, denominator = all 200 arrivals, ITT):**
  golden-hour ITT (first TREATMENT_START ≤ 60 min of ARRIVAL) · view-based variant
  (DISPOSITION ≤ 60 min, matching `GoldenHourView` as implemented) · mortality
  (DECEASED / arrivals). Both golden-hour operationalisations reported for both
  contrasts; no selection.

## Headline ratios — Var(unpaired estimator) / Var(paired per-rep differences)

| Contrast | Metric | Var paired | Var unpaired | **Ratio** |
|---|---|---|---|---|
| Routing (A vs C) | golden-hour ITT | 1.125×10⁻⁵ | 8.726×10⁻³ | **776** |
| Routing (A vs C) | golden-hour view | 0 (all 20 diffs = 0) | 6.596×10⁻³ | **∞ (perfect pairing)** |
| Routing (A vs C) | mortality | 0 (all 20 diffs = 0) | 6.565×10⁻⁴ | **∞ (perfect pairing)** |
| Resource (+4 R1-ALPHA beds) | golden-hour ITT | 0 | 1.093×10⁻² | **∞ (perturbation inert — see note)** |
| Resource (+4 R1-ALPHA beds) | golden-hour view | 0 | 7.122×10⁻³ | **∞ (inert)** |
| Resource (+4 R1-ALPHA beds) | mortality | 0 | 3.836×10⁻⁴ | **∞ (inert)** |

**Registered hypothesis (ratio ≥ 2 on ≥ 1 metric): satisfied overwhelmingly.**
Paired mean A−C difference, golden-hour ITT: −0.00075 (A marginally below C).

## The paired differences, exactly

- **Routing / golden-hour ITT:** 19 of 20 paired reps have IDENTICAL numerators; the
  entire paired variance is one rep — rep 19: A = 60/200, C = 63/200 (Δ = 3/200).
  A-arm numerators across reps 0–19 (over 200):
  59, 57, 60, 90, 37, 64, 58, 43, 55, 64, 54, 66, 46, 54, 47, 68, 43, 62, 60, 60 —
  C-arm identical except rep 19 (63).
- **Routing / view variant and mortality:** A and C numerators identical in all 20
  paired reps (view: 93, 97, 85, 116, 103, 108, 96, 98, 101, 114, 101, 90, 92, 95,
  116, 95, 87, 82, 117, 115; mortality: 17, 16, 20, 23, 24, 25, 17, 17, 24, 21, 20,
  25, 20, 13, 24, 16, 13, 17, 28, 16 — each over 200).
- **Resource pair:** baseline and +4-bed arms produced IDENTICAL fractions in every
  paired rep on every metric.

## What the golden-hour ratio says about the transit-keying provisional

The provisional's question: does per-mode vehicle-mission keying (TRANSIT), rather than
per-casualty-leg keying, cost meaningful pairing on transit-dependent estimands?

**Answer from the sharpest available number: no.** Golden-hour ITT — the transit-heavy
metric — pairs to within 3/200 in one rep out of twenty and exactly in the rest, a
776× variance reduction over unpaired arms. Dispatch-interleaving differences between
doctrine arms did shift some vehicle-mission draws (that is the one nonzero rep), but
the leakage is bounded at ~1.5×10⁻² absolute in a single rep. Mission-stream keying as
built is EMPIRICALLY SUFFICIENT for paired comparison at this scenario scale.

**Resource-pair caveat, on the record:** the +4-bed perturbation proved INERT at these
parameters — R1-ALPHA's 8 beds never bind in IRON BRIDGE at n=200, so both arms produced
byte-identical trajectories and the pairing certificate is trivial (it demonstrates the
keyed architecture's exactness under an inert config change — itself a meaningful
property: config deltas that do nothing measure as EXACTLY nothing — but it does not
exercise dispatch-interleaving sensitivity). A binding resource perturbation is the
natural follow-up when the PoC comparison is designed; registered here as an
observation, not run (no scope drift).

**Secondary observation (for Step-5a's metric standard):** mortality and the
disposition-based golden-hour variant were IDENTICAL across doctrine arms in every
paired rep — as-built, mortality is carried almost entirely by identity-axis attributes
(T4 assignment), not by routing doctrine, at this scenario scale. Doctrine sensitivity
lives in the treatment-timing metric, exactly where the two-clock framework predicts.
