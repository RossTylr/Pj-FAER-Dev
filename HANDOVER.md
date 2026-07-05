# HANDOVER — F0 complete, Step 1 next

*Written 2026-07-05, end of the F0 build session. Attach this file when opening
the Step 1 chat.*

## Where we are

- **F0 (validity layer) is COMPLETE and gate-confirmed PASS.** The suite is no
  longer correctness-blind: the R17 corruption (force every casualty to T3)
  that passed 99/0 now fails **4/110**, caught by four independent oracles
  (O2 triage-distribution, O1 golden trace, O3 deterioration-direction,
  O4 hold-gate). Zero behaviour change proven: seed-42 outcomes byte-match the
  pre-F0 baseline across three run configurations.
- **Commit chain (all on main):** `3c72c37` lockfile → `3a783f7` F0.1 canonical
  serialiser → `6f2e68f` F0.2 run_to_log + sweep harness → `8fcd419` F0.3 six
  oracles → `37bac56` F0.4 CLAUDE.md ratifications → `51ddcf6` docs/demo_app
  reorganisation (MAAFI docs now under `docs/MAAFI/`, MVP docs under
  `docs/MVP/`).
- **Suite:** 114 green (99 original + 15 F0), deterministic across consecutive
  runs. `scripts/check_claude_md.py` ALL PASS.
- **Authority:** `docs/MAAFI/MAAFI_VERDICT.md` governs tier and build order
  (ratified in CLAUDE.md).

## New infrastructure available to every future step

- `src/faer_dev/events/canonical.py` — `canonical_event` / `canonical_log` /
  `log_digest` (strips `event_id`/`wall_time`, nothing else).
- `tests/harness.py` — `run_to_log(scenario, *, seed, duration_min,
  max_patients, toggles, drain)` returns `(engine, canonical_log)` with the
  drained-conservation guarantee (ARRIVAL == DISPOSITION); `sweep(...)` for
  dict-edit parameter sweeps (interim until the Step-2 `scenario_overrides`
  API on EnsembleBuilder — the fixture signature should survive that swap).
- `tests/golden/coin_s42.json` — golden trace; regenerate ONLY via
  `pytest --regen-golden` with the diff reviewed (CLAUDE.md Hard Rule 7).
- Oracles O1–O6 in `tests/test_oracles.py` + `tests/test_hold_gate_integration.py`.
  Re-assert O6 (simultaneity tie-break) after step 3 (multi-POI) lands.

## Step 1 — what the next session builds

Author `docs/MVP/BUILD_S1.md` first, then execute: **capability routing ∥
blackboard writer**, driven by **AC-5.1–5.3** in `docs/MVP/MVP_ACCEPTANCE.md`
(the killer assertion: no surgical casualty treated at a non-surgical
facility) **plus the writer acceptance criteria and the `mascal_active`
exclusion** (per the gate reviewer's directive). Do not start Step 1 without
its instruction file.

## Discoveries logged this session (Step 2 inputs, not gate issues)

1. **`arrivals.triage_distribution` is config-dead** — the engine samples
   triage from the hard-coded context tables in `core/triage.py`
   (`TRIAGE_DISTRIBUTIONS` / `MASCAL_TRIAGE_SHIFTS`), never from the YAML key.
   Logged on the F9 silent-drop list (`docs/MAAFI/MAAFI_FORWARD.md`, F0
   addendum). O2 doubles as the config-coherence tripwire. **Step 2 decision:
   wire the key or delete it from presets.**
2. **Graph routing starves R1 on the coin topology.** With
   `enable_graph_routing=True`, Dijkstra takes POI→R2 direct (45 min ROTARY)
   over POI→R1→R2 (55 min), so **R1-ALPHA receives zero casualties in a full
   72-h Engine Room run** — every casualty skips Role 1 care and the
   per-patient `bypass_role1` decision is overridden for everyone by edge
   weights. Verified live (demo app) and headless (identical numbers:
   988 events, 115 arrivals, 111 dispositions, 4 in-system). Input for
   Step 1's capability routing design.
3. **The EventBus is a proven injection seam** — O5 keeps a congestion push
   applied via an additive `subscribe_all` subscriber; O3 samples per-event
   severity the same way. Legitimate pattern for Phase 2 consumable tracking.
4. **Engine Room "Golden Hour 114 min" is the mean** — median is 55 min and
   `pct_within_60` ≈ 54%. Consider surfacing the percentage in the UI.

## Session hygiene notes

- `run_log.jsonl` accumulates entries on every engine run (tests included);
  routinely dirty — commit or ignore as preferred.
- `playwright` was pip-installed into `.venv` this session (browser-driving
  the demo app); not added to `pyproject.toml`.
