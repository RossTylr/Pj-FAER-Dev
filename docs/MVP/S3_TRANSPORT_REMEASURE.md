# S3 TRANSPORT RE-MEASURE — pre-registration

*BUILD_S3 session β, slice 4. **This file is committed BEFORE any ratio is
computed or viewed.** Results are appended in a later commit; the git order is the
witness, exactly as `PREREG_VR1` → `VR1_RESULTS` established at S2.*

---

## 1. Why this re-measure exists

The deferred register carries a **provisional**: *"Transit keying = per-mode mission
stream — arbitrated SUFFICIENT at VR-1 (variance ratio 776, leak 3/200 in 1/20 reps).
REVISIT iff a transit-dependent estimand shows weak pairing."*

That arbitration was made on a **non-re-routing, single-POI topology**. Round B found
the trigger condition met on **two independent grounds**:

1. **M3 re-routing** (Q17, mechanism M3(b)) — a divert reorders vehicle requests.
2. **Multi-POI batch coupling** (Q19.2) — `BatchCoordinator` pools by mode across the
   whole network with no origin dimension, so two POIs' casualties batch *together*
   and batch membership becomes cross-POI coupled.

Both mechanisms landed in session α. The provisional therefore cannot be carried
forward unexamined; this re-measure is its re-arbitration.

## 2. What is being compared

`enable_origin_transport` re-scopes the TRANSIT mission stream from `transit:<MODE>`
to `transit:<MODE>:<origin>`, and gives the batcher an origin dimension so a batch
never spans two departure points. The question is whether that scoping materially
improves CRN pairing for transit-dependent estimands.

**Two stages, pre-declared, because the flags are separable and the attribution
matters:**

| Stage | `enable_origin_transport` | `enable_batched_turnaround` | Isolates |
|---|---|---|---|
| **1** | ON | OFF | The provisional's actual subject — keying + batch composition, with vehicle physics unchanged |
| **2** | ON | ON | The full change, including the unified downtime model |

Stage 1 is the one the ruling turns on. Stage 2 is reported so the physical change is
not smuggled into the keying verdict.

Each stage is compared against a **baseline arm with both flags OFF**.

## 3. Contrasts

Both are run at every stage.

- **Contrast A — the routing pair.** The VR-1 contrast: two arms differing only in a
  routing configuration, on a single-POI topology. Retained so the new numbers are
  commensurable with the ratio 776 already on record.
- **Contrast B — a divert-exercising two-POI scenario.** The case that did not exist
  when the provisional was arbitrated: two POIs, two R1s, a shared batched rotary
  leg, and a bottleneck that forces holds and therefore M3 diverts.

## 4. Metrics

Per replication, per arm:

- `transit_total` — summed transit time across all casualties (the directly
  transit-dependent estimand);
- `golden_hour_rate` — ITT form: casualties stamped compliant ÷ **all** arrivals, per
  the standing 5a rule, with numerator and denominator both reported;
- `disposition_mix` — share of each outcome string.

## 5. The statistic

For each metric and each contrast, over `n = 40` replications:

- **paired variance** `var_p` = variance of the per-replication difference
  `x_A(i) − x_B(i)`, both arms sharing replication index `i` (common random numbers);
- **unpaired variance** `var_u` = variance of `x_A(i) − x_B(j)` with `j` a fixed
  derangement of `i`, so the arms are decorrelated but the marginal distributions are
  identical;
- **variance ratio** `VR = var_u / var_p`.

High `VR` means pairing is doing work. `VR ≈ 1` means the arms are effectively
independent and the comparison has lost CRN's benefit.

Degenerate case, declared in advance: if `var_p == 0` exactly (byte-identical arms,
as the VR-1 resource perturbation turned out to be), `VR` is reported as **infinite
and the contrast is marked INERT** — an inert contrast is evidence about the fixture,
not about the keying, and must not be quoted as a pairing success.

## 6. Decision rule — declared before the numbers are seen

Let `VR_off` be the variance ratio with both flags OFF (the status quo) and `VR_on`
the ratio at stage 1.

- **REPLACE the provisional** (origin-scoped keying becomes the standard) if, on
  contrast B for `transit_total`, `VR_off < 10` **and** `VR_on ≥ 10 × VR_off`. That is:
  the unscoped stream shows genuinely weak pairing on a divert-exercising topology,
  and scoping fixes it by an order of magnitude.
- **RETAIN the provisional as sufficient** if `VR_off ≥ 100` on both contrasts — the
  unscoped stream is already pairing well and the scoping is optional hygiene.
- **INCONCLUSIVE, escalate to the human** in every other case, including any case
  where contrast B is INERT.

The default-flip of `enable_origin_transport` rides the GM-4 legacy bundle regardless
of this ruling; what is being decided here is whether the *register provisional* is
discharged, replaced, or carried.

## 7. Standing constraints

- Seed 42 throughout; replication index is the pairing key.
- Both arms of every contrast run through **identical code paths**, differing only in
  configuration (Hard Rule 8).
- Arms are compared only at equal POI count — `require_comparable_arms` is invoked in
  the harness and will raise rather than let a key-schema mismatch through.
- No golden regeneration: the re-measure reads runs, it does not re-baseline anything.

---

*Pre-registration ends here. Results are appended below in a later commit.*

---

# RESULTS — executed 22 Jul 2026

*Pre-registration above committed at `9520e1f`, before any ratio existed. Executed from
a scratchpad outside the repo against the public harness; `n = 40`, seed 42,
replication index as the pairing key. Arms differ ONLY in `enable_graph_routing`
(a routing configuration), per contrast definition §3.*

## Contrast A — routing pair (coin, single POI)

`stamp 74609bad…:poi1`

| Stage | reps used | `transit_total` VR | `golden_hour_rate` VR | `strat_share` VR |
|---|---|---|---|---|
| both-OFF (status quo) | 40/40 | 94.07 | 1.241 | INERT |
| stage 1 (origin ON) | 40/40 | 94.07 | 1.088 | INERT |
| stage 2 (both ON) | **38/40** | 68.89 | 1.135 | INERT |

Golden-hour ITT, both flags off: arm A **161/984**, arm B **492/984**. At stage 1:
arm A 157/984, arm B 439/984. At stage 2: arm A 122/881, arm B 234/881.

## Contrast B — divert-exercising two-POI

`stamp 4957e44a…:poi2` · 188–191 HOLD_START events per stage, so the divert machinery
was genuinely exercised.

| Stage | reps used | `transit_total` | `golden_hour_rate` | `strat_share` |
|---|---|---|---|---|
| both-OFF | 40/40 | **INERT** | **INERT** | **INERT** |
| stage 1 | 40/40 | **INERT** | **INERT** | **INERT** |
| stage 2 | 40/40 | **INERT** | **INERT** | **INERT** |

`var_paired == 0` on every metric at every stage: the two arms produced **identical**
results (arm A 38/1120 and arm B 38/1120 golden-hour ITT; 189 holds each).

---

## RULING, by the pre-declared decision rule (§6)

**INCONCLUSIVE — escalate to the human.**

§6 states: *"INCONCLUSIVE, escalate to the human in every other case, including any
case where contrast B is INERT."* Contrast B is INERT on every metric at every stage.
The rule fires exactly as written; the provisional is **neither discharged nor
replaced** by this re-measure.

**Recommendation to the human: RETAIN the provisional and carry it forward**, with the
re-measure to be redesigned. The provisional is not evidenced *sufficient* by this
run — it is simply untested by it.

## Three findings, disclosed in full

**1. Contrast B was a degenerate fixture — my design error, not a property of the
code.** Its topology gives every node exactly ONE onward edge (POI-NORTH → R1-ALPHA →
R2-MAIN → R3-REAR). With no branching there is no routing choice, so
`enable_graph_routing` on and off are the same policy and the arms are identical by
construction. The fixture exercised holds and diverts handsomely (189 of them) but
never exercised the thing the *contrast* was supposed to vary. A valid contrast B
needs a topology where the two routing modes can disagree — two capable R2s at
different weights, as contrast A's coin preset has.

**2. `transit_total` is not a transit-draw-dependent estimand.** Its variance ratio is
identical (94.07, `var_paired` 11966.9 to six figures) with origin scoping ON and OFF,
which is the tell. `patient.total_transit_time` accumulates
`network.get_travel_time()`, which returns `base_time` — deterministic, explicitly not
the congestion-adjusted weight and not a draw. Transit *draws* set vehicle
availability, not patient transit duration. So the metric I pre-declared as "the
directly transit-dependent estimand" is nothing of the kind. A future re-measure
should use a vehicle-side estimand — queue wait for transport, or time-to-pickup.

**3. Batched turnaround has a material throughput cost: 2/40 replications failed to
drain.** Stage 2 (both flags ON) left reps 28 and 38 undrained within the harness's
+24 h allowance (`ARRIVAL=52 DISPOSITION=34` and `ARRIVAL=51 DISPOSITION=47`), on the
graph arm only. Both-OFF and stage 1 drained 40/40. Those two replications are
excluded from the stage-2 statistics, declared here rather than silently dropped —
and the exclusion is itself the finding: unifying the two vehicle-downtime models is
**not** a cosmetic change. Holding a batched vehicle for turnaround measurably reduces
theatre throughput, which is the correct physical behaviour and precisely why the flag
is separate from the keying change. Its default-flip needs a capacity review, not just
a toggle.

**A fourth, minor:** contrast A's `strat_share` is INERT at every stage (`var_paired`
exactly 0). Under §5's declared rule that is evidence about the fixture, not a pairing
success, and it is not quoted as one.

## What this means for the register row

The row reads *"REVISIT iff a transit-dependent estimand shows weak pairing."* This
run did not test a transit-dependent estimand (finding 2) on a discriminating contrast
(finding 1). The trigger conditions found at round B — M3 re-routing and multi-POI
batch coupling — remain met and remain unexamined. The row should be carried forward
with its trigger still live, and the re-measure re-run at Step 5 with a branching
two-POI topology and a vehicle-side estimand.
