# S2_BUILD_LEDGER — witnesses, minutes and rulings for BUILD_S2 slice 0

*Running record for the S2 gate. Baseline: answers commit `1773db7` atop `4b28bad`;
PREREG_VR1 committed at `b14eddc` BEFORE any keyed comparison was viewed; 134 green.*

## Rulings received at kickoff (2026-07-07)

| Ruling | Status |
|---|---|
| Roster parquet dependency | **optional-extra** — `pip install faer-dev[roster]` (pyproject `[project.optional-dependencies].roster`) |
| Empty/absent `facilities` semantics | **NOT YET** — slice 1 STOPs and reports |
| `triage_distribution` wire-or-delete | **NOT YET** — slice 1 STOPs and reports |

Standing kickoff rules honoured: deterioration mechanism untouched (frailty threshold is
pre-drawn inert state only) · `.spawn()` forbidden on the identity axis · arrays keyed per
logical draw-event · `MVP_ACCEPTANCE.md` untouched · shared-mode byte-stream frozen from
0c-1, policed by O1 + the equivalence suites at every commit.

## Census corrections discovered while building (answers file stands; noted here)

- VITALS is LAZY, not eager: draws happen per ATMIST handover
  (`core/atmist.py:212` → `vitals.py:47`), occurrence = handover n.
- The only production consumer of `transport.py:291` trip-time normals is the
  BatchCoordinator (`transport.py:241`) — a vehicle-mission draw that may serve several
  patients — plus the standalone `transport_patient` helper (`transport.py:476`, unused by
  the engine). TRANSIT is therefore keyed as a per-mode vehicle-mission stream
  `(stream="transit:<mode>", mission n)`, not per-casualty. VEHICLE_RETURN
  (`engine.py:962→1208`) is 1:1 with a patient delivery and keys per casualty.

## 0c-1 — keyed core + plumbing (`2996aa5`)

`RNGPurpose` closed enum · `KeyedRNGRoot` (Philox; 256-bit counter encodes
`(0, occurrence, purpose, entity-hash)`; root entropy `(master_seed, replication_index)`)
· `rng_mode: shared|keyed` toggle (default shared) · `replication_index` plumbed
`ensemble → builder → engine` · EnsembleBuilder keyed branch gives `patient_seed` its
dual-seed meaning (master of the keyed root; shared-mode `base_seed + i` untouched).
Verified: 134 green, O1 identical, keyed-core semantics smoke (same key reproduces;
entity/purpose/replication decorrelate).

## 0c-2 — eager identity draws + roster (this commit)

Keyed at creation: TRIAGE · MECHANISM · PRIMARY_REGION · SECONDARY_COUNT ·
SECONDARY_REGIONS (one array draw-event) · SEVERITY · POLYTRAUMA (inverted path) ·
FRAILTY_THRESHOLD (Sellke Exp(1), frozen to `metadata["frailty_threshold"]`, mechanism
untouched). Roster behind `enable_roster` (rows at `_handle_arrival`; digest reuses the
F0.1 canonical dump; parquet writer = optional extra).

**I-2 red witness (pre-commit, keyed A vs C, protocol run):**

```
1. ARRIVAL events byte-identical: False (A=38, C=40)
   first divergent ARRIVAL index 5 (CAS-0006): fields ['sim_time']
2. roster hash identical: False (spawn_time + 2 C-only ids)
3. per-casualty attribute equality (38 shared ids): True
I-2 VERDICT: RED — failing: ARRIVAL bytes, roster hash
```

Reading: the Q0 defect (ATTRIBUTE CONTAMINATION) is REPAIRED at 0c-2 — every shared
casualty is now field-identical across doctrines, and the surviving divergence is
`sim_time`-only (the un-keyed system axis), which 0c-3 removes. Keyed-mode arrival
counts differ from shared mode (38/40 vs 31/30) because identity draws no longer consume
the shared stream — expected mid-strangler behaviour; shared mode itself is bit-stable
(134 green at default).

## 0c-3 — lazy + system-axis keyed (this commit)

Keyed: TREATMENT `(casualty_uid, episode n)` at all three engine sites ·
VEHICLE_RETURN `(casualty_uid, leg n)` (uid passed into `_vehicle_return`) · TRANSIT as
per-mode vehicle-mission stream `transit:<mode>` (census correction above) · VITALS at
ATMIST handovers `(casualty_uid, handover n)` · system axis: ARRIVALS `(stream, n)`,
MASCAL_GAP / MASCAL_SIZE / MASCAL_OFFSETS `(stream, event n)`, the offsets array one
keyed draw-event per cluster.

**I-2 green witness (keyed A vs C, protocol run):**

```
1. ARRIVAL events byte-identical: True (A=56, C=56)
2. roster hash identical: True (7e1beff6e110756f… both)
3. per-casualty attribute equality (56 shared ids): True
I-2 VERDICT: GREEN
```

Shared mode: 134 green, byte-stable. The keyed arrival sequence (56 in the 24 h window)
is its own universe — the golden re-bless happens once, at 0e, by design.

## 0d — invariants I-1–I-7 + poison (this commit)

`tests/test_rng_keyed.py` (7 tests) + `log_digest_with_draws` (canonical.py, additive):

| Invariant | Content |
|---|---|
| I-1 | keyed double-run: equal digests AND equal per-purpose draw counts |
| I-2 | keyed A vs C: ARRIVAL bytes ≡, roster hash ≡, per-casualty field equality |
| I-3 | draw counts recorded, reproducible, enter the digest, single-purpose drift flips it; eager purposes fire exactly once per casualty |
| I-4 | POISON: mis-keying ONE purpose (global-ordinal occurrence — the exact defect class) makes I-2 fail; `pytest.raises` keeps the red witness permanent |
| I-5 | shared-mode byte freeze: O1-protocol digest pinned as literal `9164bd97…e41d` — must survive 0e untouched |
| I-6 | route-divergent equivalence fixture (R3-iv lesson): arms whose routes genuinely diverge (extracted walk → R2-A only; graph+capability → R2-B for surgical) still satisfy I-2 |
| I-7 | replication enters the root (same rep reproduces, different rep decorrelates); EnsembleBuilder keyed arms sharing `patient_seed` draw identical randomness across different `base_seed`s |

**Poison red witness (pre-commit, purpose=SEVERITY poisoned in both arms):**

```
POISON WITNESS: I-2 RED as required — ARRIVAL events not byte-identical
poisoned purpose=SEVERITY: 51/56 casualties severity-divergent across A/C
```

Suite: **141 passed** (134 + 7). Shared default untouched.

## 0e — default flip + re-bless + THAW (this commit)

`rng_mode` default → **keyed**. ONE sanctioned `--regen-golden`
(artefact: `docs/MVP/S2_0E_GOLDEN_REGEN.md`; full byte diff in this commit).
Suite fallout at the flip was exactly the Q7 prediction: O1 (by design) + the
`hold_promotion_run` tuned recipe (cohort 60 → 120, one-line justification in the
fixture docstring, assertions untouched). Every property-safe test passed UNMODIFIED.
**141 passed** at the keyed default.

**THAW MINUTE (2026-07-07).** I-2 re-run at PLAIN DEFAULT toggles (no explicit
`rng_mode`), protocol run, A vs C:

```
arrivals byte-identical=True (56=56), roster hash identical=True,
per-casualty equality=True
THAW: GREEN — COMPARISON LANE REOPENS
```

The RNG_DIAGNOSTIC.md freeze condition ("no paired A-vs-C claims until dual-stream
separation lands") is discharged: paired A-vs-C comparisons are quotable again in keyed
mode, subject to the PREREG_VR1 discipline for variance claims.

## Rule-3 LOC accounting (intrinsic zone: src/faer_dev/simulation/)

| Commit | Cumulative added / removed vs baseline |
|---|---|
| 0c-1 `2996aa5` | 11 / 0 |
| 0c-2 `cc55fcf` | 107 / 9 |
| 0c-3 `a062487` | **204 / 30** (crossed here) |
| 0d `6b2b4ea` | 204 / 30 (tests only) |
| 0e (this commit) | 204 / 30 — **zero intrinsic lines** (toggle default lives in `decisions/mode.py`; golden and test are excluded classes) |

Raw added **204** (code-only, excluding blank/comment-only lines: **176**) vs the
kickoff's ~160 drift ceiling → **materially beyond → STOP fires**. Per the Rule-3
precedence clause (parity and toggle-equivalence outrank the tripwire; never break them
to hit a line count), the vertical slice was completed and every commit carries its
parity/byte-freeze witnesses; the overage is comment-inclusive strangler `if/else`
duplication at 10 draw sites, kept deliberately so legacy lines stayed byte-verbatim.
**The overage is a gate item for human review — no further intrinsic lines will be
written this session.**

## §5 Definition of Done — status at HALT

| DoD item | Status |
|---|---|
| 0c: shared mode byte-untouched, 134 green | ☑ (134 green at every 0c commit; I-5 pin) |
| 0d: I-1–I-5 green, poison red witnessed | ☑ (I-1–I-7 green; poison red in ledger + permanent via I-4) |
| 0e: golden diff reviewed, re-baseline list justified line-by-line, property-safe unmodified | ☑ (artefact + this ledger; 141 green) |
| THAW minuted: I-2 holds at keyed default | ☑ (minute above) |
| Slice 1 landed; two human rulings recorded | ☐ **STOPPED — rulings NOT YET** (parquet ruling recorded; scenario_overrides/version stamp/guard family not started) |
| Tails: prereg committed BEFORE any keyed comparison viewed | ☑ (`b14eddc`, before 0c-2's first keyed witness) |
| Rule-4 conservation ×3 configs | ☑ at keyed default: conservation suites green (coin); killer + hold-promotion inline configs drain to conservation in their suites |
| Intrinsic LOC actual vs declaration | ⚠ 204 raw / 176 code-only vs ~160 ceiling — **human gate item** |
| Rule-8 addendum ratified or explicitly deferred | ☐ **DEFERRED** — text not authored (human paste or explicit delegation; not reached, STOP at slice-1) |

Remaining tails NOT reached (stop at slice-1 per kickoff): mixed-caseload killer variant ·
CURRENT/checker reconciliation · Rule-8 addendum text. PREREG_VR1 done (pulled forward).
