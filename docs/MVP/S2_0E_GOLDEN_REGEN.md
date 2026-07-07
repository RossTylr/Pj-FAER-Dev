# S2 0e — sanctioned golden regeneration (gate-review artefact)

*2026-07-07 · the FIRST golden regeneration since F0 · produced by exactly ONE
`pytest tests/test_oracles.py::test_o1_golden_trace --regen-golden` run at the 0e default
flip. The full byte diff is in this commit (Rule 7: reviewed in the commit, never silent).*

## Why the golden changes

`rng_mode` default flipped `shared → keyed`. The keyed universe draws every stochastic
value from `(entity, purpose, occurrence)` Philox streams, so the realisation at
coin/seed 42 differs from the shared-stream realisation by construction. This is the one
sanctioned re-bless; the shared universe remains byte-frozen behind the toggle and is
policed by the pinned literal in `tests/test_rng_keyed.py::test_i5_shared_mode_byte_frozen`.

## Review summary (O1 protocol: coin, seed 42, 480 min, max 50, undrained)

| | old (shared) | new (keyed) |
|---|---|---|
| digest | `9164bd97…e41d` | `d6546fbf…7479` |
| ARRIVAL | 13 | 16 |
| DISPOSITION | 9 | 14 |
| FACILITY_ARRIVAL | 15 | 16 |
| TRANSIT_START / END | 18 / 15 | 17 / 16 |
| TREATMENT_START / END | 15 / 14 | 16 / 15 |
| first arrival | CAS-0001 @ 96.168 | CAS-0001 @ 27.950 |
| last arrival | CAS-0013 @ 430.962 | CAS-0016 @ 452.812 |

Diff shape: full-universe replacement (610 insertions, 463 deletions over the 1073-line
file) — expected for a re-keyed draw architecture; ids stay sequential (CAS-0001…);
conservation holds (Rule 4 suites green); no structural/schema change to any event.

## Suite disposition at the flip (the Q7 census, settled empirically)

- **RE-BASELINE (complete list):**
  1. `tests/golden/coin_s42.json` — regenerated (this artefact). O1 green post-regen.
  2. `hold_promotion_run` recipe (`tests/test_capability_retriage.py`) — cohort
     60 → 120; the keyed realisation drained the shared-era backlog before any hold
     reached the 15 h PFC ceiling; deeper backlog restores starvation (62 promotions at
     seed 42). Assertions untouched.
- **PROPERTY-SAFE — all passed UNMODIFIED at the keyed default:** O2 (±0.15 band),
  O3 (direction), O4 (hold-gate sequence), O5 (congestion shift), O6 (tie-break
  determinism), Rule-4 conservation ×2 forms, T-5-1/2/4/6/7 safety and characterisation
  suites, T-5-5a/b assertions, all toggle-equivalence and double-run determinism suites,
  seed-difference, I-1–I-7 (including the I-5 shared byte-freeze pin, unchanged).

**141 passed** at the keyed default.
