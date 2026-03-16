# Pj-FAER-Dev

**Forecast Accident and Emergency Resources — Development Branch**

Poly-hybrid simulation engine refactoring: SimPy DES + BehaviorTrees + NetworkX.
Implements the "Tidy, Decouple, Then Plug" architecture from a multi-LLM Design Space Exploration.

---

## Quick Start

```bash
git clone https://github.com/RossTylr/Pj-FAER-Dev.git
cd Pj-FAER-Dev
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
streamlit run demo_app/app.py       # demo app
jupyter lab notebooks/              # proof notebooks
```

## Architecture

**Phase 1** (this branch): Pattern A+E — extract pure functions, decouple analytics
**Phase 2** (conditional): Pattern B — sync-only plugin protocols for variant families
**Phase 3** (if needed): Pattern D — yield delegation via `yield from`

### Yield Ownership (the non-negotiable spine)

| Yield | Operation | Phase 1-2 Owner | Phase 3 Owner |
|-------|-----------|-----------------|---------------|
| Y1 | resource.request() — treatment | engine.py | treatment.py |
| Y2 | env.timeout() — treatment duration | engine.py | treatment.py |
| Y3 | env.timeout() — PFC retry | engine.py | hold_pfc.py |
| Y4 | vehicle.request() — transport | engine.py | engine.py |
| Y5 | env.timeout() — travel time | engine.py | engine.py |

## Repo Structure

```
Pj-FAER-Dev/
├── README.md
├── CLAUDE.md                    # Claude Code instructions
├── pyproject.toml
├── docs/
│   ├── dse/                     # DSE outputs (9 documents)
│   ├── phase1/                  # Build instructions per extraction
│   ├── phase2/                  # Conditional phase instructions
│   └── phase3/                  # High-risk extraction instructions
├── notebooks/
│   ├── phase0/NB33_*.ipynb      # Architecture decision record
│   ├── phase1/NB34-39_*.ipynb   # Phase 1 proof notebooks
│   ├── phase2/NB40-44_*.ipynb   # Phase 2 proof notebooks
│   ├── phase3/NB43_*.ipynb      # Phase 3 proof notebook
│   └── demo/NB_DEMO_*.ipynb     # LSCO showcase
├── src/faer_dev/                # Engine source
│   ├── core/                    # Type foundation (PRESERVED)
│   ├── decisions/               # BT layer (PRESERVED)
│   ├── network/                 # Graph layer (PRESERVED)
│   ├── simulation/              # DES layer (REFACTORING TARGET)
│   ├── events/                  # Event layer (PRESERVED + EX-3)
│   ├── analytics/               # NEW — Pattern E
│   ├── plugins/                 # PHASE 2 — sync-only protocols
│   ├── routing.py               # NEW — EX-1
│   ├── metrics.py               # NEW — EX-2
│   ├── emitter.py               # NEW — EX-3
│   └── pfc.py                   # NEW — EX-4 sync
├── demo_app/                    # Streamlit demo (6 pages incl. Engine Room)
└── tests/                       # pytest scaffolds per extraction
```

## Notebooks

| NB | Phase | Purpose | Gate? |
|----|-------|---------|-------|
| NB33 | 0 | Architecture Decision Record | — |
| NB34 | 1 | EX-1 Routing Extraction | — |
| NB35 | 1 | EX-2 Metrics Extraction | — |
| NB36 | 1 | EX-3 Typed Emitter + K-7 Closure | — |
| NB37 | 1 | Pattern E Analytics Decoupling | — |
| NB38 | 1 | EX-4 PFC Sync Decision | — |
| NB39 | 1 | **Phase 1 Integration Gate** | GO/PAUSE |
| NB-DEMO | — | LSCO Scenario Showcase | — |
| Engine Room | 1 cap | Phase 1 Capstone: Architecture X-Ray | — |
| NB44 | 2 | yield from Exception Safety | — |
| NB40 | 2 | Plugin Protocol Design | — |
| NB41 | 2 | EX-5 Treatment Yield Delegation | — |
| NB42 | 2 | **HADR Variant Proof** | GO/PAUSE |
| NB43 | 3 | **EX-6 Hold/PFC Extraction** | DONE/STOP |

## Development Workflow

1. Read the instruction file in `docs/phase1/`
2. Prove in notebook (NB34-38)
3. Extract to `src/faer_dev/`
4. Toggle-gate behind `SimulationToggles`
5. Fixed-seed regression (old path vs new path)
6. ±5% distribution match on 1,000 casualties
7. Merge

## DSE Reference

Full multi-LLM Design Space Exploration outputs in `docs/dse/`:
- Context Index + Pseudocode Reference (input documents)
- Stage 2a Architecture Proposals (6 approaches, full interfaces)
- Stage 2b Red-Team Analysis (self-attack + cross-attack)
- Stage 2c Scoring + Synthesis (weighted scorecard + hybrid recommendation)
- Pass 3 Cross-LLM Synthesis (convergence map + final recommendation)
- Lessons & Findings Registry (32 entries across 5 categories)

## Links

- **FAER-MIL (production):** [github.com/RossTylr](https://github.com/RossTylr)
- **Pj-MNEMOSYNE:** Surrogate survival model
- **Pj-STOCHASM:** Monte Carlo methods lab
