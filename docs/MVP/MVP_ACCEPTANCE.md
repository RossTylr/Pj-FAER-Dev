# FAER-MIL — MVP Acceptance Criteria
### Behavioural assertions per feature — drives the PRD build loop

---

## How to use this

Each MVP feature has 1–3 **acceptance criteria**: machine-checkable assertions
about what the engine **computes**, not whether it runs. A feature is not
"done" until its criteria pass on a **real run** (not a stub) at seed=42.

This is the antidote to the stub-passes-tests failure mode (proved in
HEPHAESTUS): a feature that runs cleanly but computes wrong behaviour.
Each assertion reads the event log or ensemble output and checks a
behavioural property that would FAIL if the mechanism were broken.

**Prerequisite:** run interrogation A11 first. If the verdict is
CORRECTNESS BLIND or HARNESS GAP, build the acceptance-test fixture
before writing these as live tests.

**Convention:** all criteria assume a helper `run(scenario, seed=42)`
returning an event log, and `ensemble(scenario, n, seed=42)` returning
per-replication aggregate metrics. Adjust names to match the harness
the interrogation finds.

---

## Tier 0 — Activate (verify, don't build)

### #19 Injury-first casualty generation — INTRINSIC
**Property:** triage category is derived FROM the sampled injury, not
assigned independently.

```
AC-19.1  Run a scenario. For every casualty, assert that triage_category
         is consistent with injury severity: a casualty with an
         immediately life-threatening injury profile is never triaged T3
         or T4. (Sample → triage direction holds, not reverse.)

AC-19.2  Over 100 reps, the triage distribution is non-degenerate:
         all of T1, T2, T3 appear (the generator isn't collapsing to
         one category).
```

### #46 Route denial — INTRINSIC
**Property:** contested routes deny transport at the configured probability.

```
AC-46.1  Set route denial probability to 0.0. Run. Assert ZERO
         ROUTE_DENIED events.

AC-46.2  Set route denial probability to 1.0 on a specific edge. Run.
         Assert every transport attempt on that edge produces a
         ROUTE_DENIED event (no casualty traverses it).

AC-46.3  Set denial to 0.3 over 100 reps. Assert observed denial rate
         on contested edges is 0.3 ± 0.05.
```

---

## Tier 1 — MVP wire (build to these criteria, in order)

### 1st — #5 Facility capability flags — INTRINSIC
**Property:** routing respects facility capability requirements. A
casualty needing a capability is never sent to a facility lacking it.

```
AC-5.1   THE KILLER ASSERTION. Configure one facility with
         has_surgery=False. Run a scenario with surgical casualties.
         Assert: NO event where a casualty with requires_dcs=True
         is treated at the has_surgery=False facility.
         (If this fails, routing ignores capability — the feature is
         not wired, regardless of test execution status.)

AC-5.2   Configure all facilities has_surgery=True. Run. Surgical
         casualties ARE treated (no casualty stuck unrouteable when
         capability exists). Confirms the flag gates, doesn't block.

AC-5.3   Determinism: AC-5.1 produces byte-identical canonical log
         (F0.1) across two runs at seed=42.
```
**Wire-order note:** #5 must land before #45 sweep. A sensitivity sweep
over capability-blind routing measures a broken mechanism.

### 2nd — #1+#8 Multi-POI + unit positioning — INTRINSIC (bundle)
**Property:** casualties spawn at multiple POIs in configured proportions,
and each POI feeds its nearest R1.

```
AC-1.1   Configure two POIs with arrival weights 0.7 / 0.3. Run 100 reps.
         Assert spawn proportion is 0.7 / 0.3 ± 0.05.

AC-1.2   Configure POI-NORTH nearest to R1-ALPHA and POI-SOUTH nearest
         to R1-BRAVO. Assert casualties from POI-NORTH predominantly
         route to R1-ALPHA (nearest-facility logic holds).

AC-1.3   INVARIANT: with two concurrent POI arrival processes, total
         DISPOSITION count still equals total ARRIVAL count.

AC-1.4   Determinism: two-POI scenario reproduces byte-identical at
         seed=42 (concurrent processes don't break determinism).
```

### 3rd — #10 Threat zones — INTRINSIC
**Property:** route denial is geographic — high-threat routes deny more
than low-threat routes.

```
AC-10.1  Configure one high-threat edge (denial weight high) and one
         low-threat edge (denial weight low) between the same role
         levels. Run 100 reps. Assert denial rate on the high-threat
         edge is measurably greater than on the low-threat edge.

AC-10.2  Set all threat zones to zero. Assert denial rate reduces to
         the baseline route-denial probability (threat adds to, doesn't
         replace, base denial).
```

### 4th — #30 MASCAL triage shift — INTRINSIC
**Property:** under mass-casualty surge, triage thresholds shift toward
more T4 expectant.

```
AC-30.1  Run baseline (no MASCAL). Record triage distribution.
         Run with MASCAL burst active. Assert the proportion of T4
         expectant is HIGHER under MASCAL than baseline (same seed,
         same casualty profiles where comparable).

AC-30.2  Assert the MASCAL shift is TRIGGERED by the burst event, not
         always-on: before the burst time, triage uses normal
         thresholds; after, shifted thresholds.

AC-30.3  INVARIANT: MASCAL burst casualties are still conserved
         (DISPOSITION == ARRIVAL including the burst cohort).
```

### 5th — #44 Ensemble CI — SURFACE (activate)
**Property:** N replications produce a mean ± 95% CI, with proper
isolation between replications.

```
AC-44.1  ISOLATION. Run ensemble of 50. Assert replications are NOT
         identical to each other (no global-state leak collapsing them)
         AND the set is reproducible at seed=42 (the SEQUENCE of seeds
         is deterministic).

AC-44.2  Assert the CI narrows as N increases: CI width at N=200 is
         smaller than at N=50 (statistically coherent aggregation).

AC-44.3  Assert each replication gets a fresh SimPy environment
         (no carry-over of resource state from the prior run).
```
**Wire-order note:** activate AFTER #1, #5, #10, #30 — running 100 reps of
an incomplete mechanism gives narrow CIs around wrong answers.

### 6th — #45 Sensitivity sweep — SURFACE
**Property:** sweeping a parameter produces coherent directional results.

```
AC-45.1  MONOTONICITY. Sweep R1 beds [4, 6, 8, 12], 100 reps each.
         Assert mean golden-hour compliance is monotonically
         non-decreasing as beds increase. (More capacity should not
         reduce compliance — if it does, either the mechanism or the
         sweep is broken.)

AC-45.2  Assert the sweep output is structured and diffable: each
         parameter value maps to a labelled result with mean and CI,
         comparable across values (not opaque blobs).

AC-45.3  THE PoC ASSERTION. The sweep produces a quantified, signed
         insight: "adding K beds to R1 changes golden-hour compliance
         by X% under LSCO with 30% route denial." Assert X is non-zero
         and directionally sensible. This is the demo's beat 4.
```
**Wire-order note:** depends on #5 (capability routing) being correct —
AC-45.1 monotonicity only holds if routing actually uses the beds it's
given. Build #5 first.

---

## The build loop (per feature)

For each MVP feature, in wire order:

1. **Write the acceptance criteria as live tests** (from the blocks above)
2. **Confirm they FAIL** before building (red — proves the test has teeth)
3. **Build the feature** as a vertical slice (~20–60 LOC), toggle-gated if
   it's a strangler extraction
4. **Confirm criteria PASS** on a real run at seed=42 (green)
5. **Confirm strangler equivalence** where applicable (toggle OFF == ON)
6. **Confirm the conservation invariant** still holds (DISPOSITION == ARRIVAL)
7. **Commit the slice** with the passing criteria

A feature is done when its criteria pass on a real run — never on a stub.
If a stub passes a criterion, the criterion is too weak; strengthen it
until only the real mechanism satisfies it.

---

## Coverage summary

| Feature | Layer | Criteria | Killer assertion |
|---------|-------|----------|------------------|
| #19 injury-first | I | AC-19.1–2 | Triage derived from injury, not reverse |
| #46 route denial | I | AC-46.1–3 | Denial rate matches configured probability |
| #5 capability flags | I | AC-5.1–3 | Surgical casualty never sent to non-surgical facility |
| #1+#8 multi-POI | I | AC-1.1–4 | Spawn proportions correct + invariant holds |
| #10 threat zones | I | AC-10.1–2 | High-threat denies more than low-threat |
| #30 MASCAL shift | I | AC-30.1–3 | T4 proportion higher under surge, triggered not always-on |
| #44 ensemble CI | S | AC-44.1–3 | Replications isolated + CI narrows with N |
| #45 sweep | S | AC-45.1–3 | Monotonic compliance + signed PoC insight |

Eight features, 21 acceptance criteria. The four intrinsic wire features
(#5, #1+#8, #10, #30) carry the criteria that prove the mechanism is
correct. The two surface features (#44, #45) carry the criteria that
prove the analysis is trustworthy. Together they make beat 4 of the
demo — the PoC sentence — defensible.
