# PREREG_VR1 — variance-ratio pre-registration (paired vs unpaired replication)

*Registered 2026-07-07, during BUILD_S2 slice 0, BEFORE any keyed A-vs-C comparison result
was viewed in the build session. Committed ahead of the 0c-2 I-2 witness by design: the
registration must precede sight of any keyed comparison. RUN POST-THAW ONLY (after the
BUILD_S2 §1 0e thaw minute reopens the comparison lane).*

## Design

- **Scenario:** IRON BRIDGE preset (`src/faer_dev/config/defaults/iron_bridge.yaml`).
- **Doctrine pair:** one pair, config A (all-default `SimulationToggles`) vs config C
  (`enable_extracted_routing=True, enable_graph_routing=True,
  enable_capability_routing=True`) — the standing A-vs-C contrast of RNG_DIAGNOSTIC.md
  and S2_PREBUILD_ANSWERS.md Q0.
- **Arms:**
  - **Paired:** n replications where both doctrines share replication roots — identical
    `(master_seed, replication_index)` root entropy per replication, keyed mode.
  - **Unpaired:** n replications per doctrine with disjoint roots (non-overlapping
    replication indices or distinct master seeds), keyed mode.
  - Same n in both arms; n chosen at run time and recorded before analysis (minimum
    n = 20, the F0.2 `sweep` default).
- **Metrics (per the 5a reporting standard — numerator/denominator, exact fractions,
  ITT variant alongside any conditional form):**
  1. Golden-hour attainment, ITT form.
  2. Mortality (DECEASED dispositions / arrivals).
- **Estimand:** the A−C difference per metric; the quantity compared across arms is the
  variance of that difference across replications.

## Hypothesis (registered)

Var(paired difference) is SUBSTANTIALLY lower than Var(unpaired difference) — the
variance-reduction ratio Var_unpaired / Var_paired materially exceeds 1 for both metrics.
Direction is registered; no threshold is tuned after seeing data — "substantial" is
pre-declared as ratio ≥ 2 for at least one registered metric, with both ratios reported
regardless of outcome.

## Analysis plan

- Ratio of sample variances of the per-replication A−C differences (paired) vs the
  difference of independent arm means (unpaired), same n.
- Report both metrics, exact fractions, and the violation census via the F0.2 harness —
  no ad-hoc evidence tables (standing 5a rule, docs/MVP/CURRENT.md).
- No exclusions: every replication that completes is analysed; a replication that fails
  to run is reported as such, not resampled.

## Run conditions

- Keyed mode (`rng_mode="keyed"`), post-0e default, AFTER the thaw minute (I-2 green at
  default) — never before.
- Capability-ON interim rule applies (GM-3): analysis configs set
  `enable_capability_routing` (with `enable_extracted_routing`) in the C arm as above.

## Registry lesson (recorded with this registration)

> A fixed seed buys reproducibility, not comparability — seed=42 reproduces a
> contaminated comparison perfectly; comparability is a designed property.

---

## AMENDMENT (2026-07-07, gate-directed, declared BEFORE any VR-1 result was viewed)

**Secondary contrast — the RESOURCE pair**, same design discipline as the registered
routing pair:

- **Arms:** IRON BRIDGE baseline vs IRON BRIDGE with **+4 beds at R1-ALPHA** (8 → 12),
  applied as a dict edit via `apply_scenario_overrides({"facilities.R1-ALPHA.beds": 12})`.
  R1-ALPHA is the first R1-role facility in preset insertion order; named here to remove
  the ambiguity before results exist.
- **Toggles:** BOTH arms run capability-ON (`enable_extracted_routing`,
  `enable_graph_routing`, `enable_capability_routing`) per GM-3 — the contrast is
  beds-only, doctrine held fixed.
- **Scheme:** same n = 20, same paired (shared `(master_seed=42, replication_index i)`
  roots, reps 0–19 both arms) / unpaired (baseline reps 0–19, variant reps 100–119,
  disjoint roots) structure, same metrics, same reporting rules as the routing pair.
- **Rationale on record:** the resource pair is the PoC comparison shape and the
  sharpest arbiter of the transit-keying provisional (vehicle-mission streams are
  keyed per-mode, not per-casualty; a bed change perturbs dispatch interleaving without
  touching routing policy).
- **Reporting:** BOTH golden-hour operationalisations for BOTH contrasts —
  (i) ITT: first TREATMENT_START within 60 min of ARRIVAL, denominator = all arrivals;
  (ii) the view-based variant matching `analytics/views.py` GoldenHourView as
  implemented (DISPOSITION within 60 min of ARRIVAL) — plus mortality. Exact fractions
  throughout; no post-hoc selection between variants.
