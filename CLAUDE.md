# CLAUDE.md — Claude Code Instructions for Pj-FAER-Dev

> **Load gate — before writing any code:** read `docs/MVP/CURRENT.md` for the active
> phase and current step, and confirm the relevant `docs/phase<N>/NB<xx>_*.md` spec **or**
> `notebooks/phase<N>/NB<xx>_*.ipynb` notebook for that step is loaded. If not loaded,
> stop and load it. Run `python scripts/check_claude_md.py`; it must pass before building.

## What This Repo Is

FAER-Dev is the development branch for refactoring the FAER poly-hybrid simulation engine
(SimPy DES + BehaviorTrees + NetworkX). It implements the "Tidy, Decouple, Then Plug"
architecture validated by a multi-LLM Design Space Exploration (DSE). Coding style, the
testing pattern, the HC-*/MC-* constraints and verification standards live in `AGENTS.md`.

> **Authority (ratified, F0):** `docs/MAAFI/MAAFI_VERDICT.md` governs tier and build
> order; it supersedes all earlier feature plans.

## Hard Rules (Never Violate)

1. **SimPy yields live only in the engine layer (B3, ratified).** All `yield` / `yield from`
   stay inside `src/faer_dev/simulation/`; the decoupled modules (routing, metrics, emitter,
   pfc, analytics, plugins) contain none. Within the layer, yields may live in extracted
   generator modules (arrivals, transport, ccp) provided they are exception-safe and covered
   by the strangler/oracle suite; `engine.py` remains the sole *orchestrator* of patient
   journeys. (The earlier "all 5 yield points stay in engine.py" form was aspirational, not
   load-bearing — determinism holds with 10 distributed yields.) `yield from` delegation to a
   sub-generator must release any acquired SimPy resource on exception — the safety property
   proven in `notebooks/phase2/NB44_yield_from_safety.ipynb`.

2. **Every path-replacing extraction is toggle-gated** behind `SimulationToggles`. Legacy path
   preserved; fixed-seed equivalence checked before merging. Additive decouplings (e.g. the
   analytics EventBus subscriber) have no legacy path to gate, and a toggle may be declared
   ahead of its engine wiring. *(Canonical home of the toggle-gate rule — DSE MC-4.)*

3. **LOC tripwire — risk-tiered, not a ceiling.** Measure `max(added, removed, touched)`,
   not net. Exclude notebook, fixture, generated and vendored lines.
   - **Intrinsic change** — `engine.py`, the SimPy yield points, the blackboard, or anything
     under `src/faer_dev/simulation/`: ~30 LOC, **mandatory human gate**.
   - **Surface change** — routing/metrics/emitter/pfc/analytics plumbing, types, config: ~150 LOC.
   - **Precedence:** disposition parity (Rule 4) and toggle-equivalence (Rule 2) OUTRANK this
     tripwire. When a true vertical slice will not fit — e.g. EX-3 emitter extraction + K-3
     delete as one atomic, replay-equivalent change — take the gate; never break parity or
     toggle-equivalence to hit a line count.

4. **Casualties are conserved.** Every arrival is eventually disposed or still in-system at the
   run cutoff: `arrivals == dispositions + in_system`. The bare `arrivals == dispositions` is the
   special case of a fully drained system (`in_system == 0`). Check after every engine change.

5. **Layer import isolation (both directions).** No SimPy imports in routing.py, metrics.py,
   emitter.py, pfc.py, analytics/, or any plugin module; and no Streamlit imports anywhere
   under `src/faer_dev/simulation/`. SimPy lives ONLY under `src/faer_dev/simulation/`.
   *(Canonical home of the import-boundary rule — DSE HC-6.)*

6. **Notebook proves it first.** Every extraction has a proof spec **or** notebook under
   `docs/phase<N>/` / `notebooks/phase<N>/` that validates before the production code is touched.

7. **Golden-trace regeneration policy (F0.3 O1).** `tests/golden/*.json` may only be
   regenerated via `pytest --regen-golden`, and the resulting diff must be reviewed in the
   commit — never regenerated silently to make red go green.

8. **Doctrine-as-config (standing, for #29 and all future policy comparisons).** Any compared
   doctrines/policies must run through IDENTICAL code paths, differing only in configuration —
   never a code branch per doctrine. Branching breaks CRN: different paths draw different
   random numbers, and the measured difference stops being attributable to the policy.
   Nothing violates this today; this rule keeps it that way.
   *Addendum (ratified at the S2 gate, 2026-07-07):* a valid comparison requires
   "identical code paths AND per-entity keyed streams AND tested invariants" — the keyed
   RNG architecture (BUILD_S2 slice 0) and invariants I-1–I-7 (`tests/test_rng_keyed.py`)
   are load-bearing parts of this rule, not optional extras.

## Standing Constraints (verified, for Phase 2)

- **Event bus (C6):** the bus logs-but-swallows subscriber exceptions
  (`src/faer_dev/events/bus.py:62-80` — non-fatal, subscriber stays attached), and fires
  AFTER the routing decision — sufficient for consumable tracking (#35-37), insufficient for
  stockout feedback (#39) without a blackboard write-back loop. Two wildcard subscribers
  already exist (`event_store.append`, `AnalyticsEngine`); a throwing `ConsumableManager`
  degrades quietly, so subscribers must be exception-safe by design.

## Current Position

Active phase and current step are recorded in **`docs/MVP/CURRENT.md`** (single source of truth);
the full ordered sequence per phase lives in that file's linked `BUILD_INSTRUCTIONS.md`.

## Key Files

| File | Purpose |
|------|---------|
| `docs/MVP/CURRENT.md` | Canonical phase state: active phase + current step + deferred register (sole phase-state file since the S2 reconciliation) |
| `docs/MAAFI/MAAFI_VERDICT.md` | MAAFI verdict — governs tier and build order (authority) |
| `AGENTS.md` | Coding style, testing pattern, HC-*/MC-* constraints, verification |
| `docs/dse/faer_dse_context_index.md` | DSE source of truth for HC-*/MC-* constraints |
| `scripts/check_claude_md.py` | Session-start probe — must pass before building |
