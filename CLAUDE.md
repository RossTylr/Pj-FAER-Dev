# CLAUDE.md — Claude Code Instructions for Pj-FAER-Dev

> **Load gate — before writing any code:** read `docs/CURRENT.md` for the active phase
> and current step, and confirm the relevant `docs/phase<N>/NB<xx>_*.md` spec **or**
> `notebooks/phase<N>/NB<xx>_*.ipynb` notebook for that step is loaded. If not loaded,
> stop and load it. Run `python scripts/check_claude_md.py`; it must pass before building.

## What This Repo Is

FAER-Dev is the development branch for refactoring the FAER poly-hybrid simulation engine
(SimPy DES + BehaviorTrees + NetworkX). It implements the "Tidy, Decouple, Then Plug"
architecture validated by a multi-LLM Design Space Exploration (DSE). Coding style, the
testing pattern, the HC-*/MC-* constraints and verification standards live in `AGENTS.md`.

## Hard Rules (Never Violate)

1. **SimPy yields live only in the engine layer.** All `yield` / `yield from` stay inside
   `src/faer_dev/simulation/`; the decoupled modules (routing, metrics, emitter, pfc, analytics,
   plugins) contain none. `yield from` delegation to a sub-generator is allowed within the layer
   but must release any acquired SimPy resource on exception — the safety property proven in
   `notebooks/phase2/NB44_yield_from_safety.ipynb`.

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

## Current Position

Active phase and current step are recorded in **`docs/CURRENT.md`** (single source of truth);
the full ordered sequence per phase lives in that file's linked `BUILD_INSTRUCTIONS.md`.

## Key Files

| File | Purpose |
|------|---------|
| `docs/CURRENT.md` | Active phase + current step + link to the active sequence |
| `AGENTS.md` | Coding style, testing pattern, HC-*/MC-* constraints, verification |
| `docs/dse/faer_dse_context_index.md` | DSE source of truth for HC-*/MC-* constraints |
| `scripts/check_claude_md.py` | Session-start probe — must pass before building |
