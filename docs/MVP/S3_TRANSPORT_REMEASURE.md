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
