# DSE Document Index
## Multi-LLM Design Space Exploration Outputs

These documents record the full architectural exploration that produced
the "Tidy, Decouple, Then Plug" recommendation for the FAER engine.

## Input Documents

| Document | Purpose |
|----------|---------|
| `faer_dse_context_index.md` | Compressed fact table: KF, HC, CP, IC, EX, MC, KL, K, EP, PR IDs |
| `faer_dse_pseudocode_reference.md` | Baseline call sequence + 5 architectural patterns (A-E) |
| `faer_lessons_learned_for_dse.md` | 8 months of hard-won context from FAER-MIL development |

## Analysis Outputs (Claude)

| Document | Stage | Contents |
|----------|-------|----------|
| `stage2a_architecture_proposals.md` | 2a | 6 approaches with interfaces, engine splits, migration sequences |
| `stage2b_red_team.md` | 2b | Self-attacks and cross-attacks on all 6 approaches |
| `stage2c_score_synthesise.md` | 2c | Weighted scorecard, hybrid recommendation, migration plan |

## Synthesis Outputs

| Document | Stage | Contents |
|----------|-------|----------|
| `pass3_cross_llm_synthesis.md` | Pass 3 | Cross-LLM comparison (Claude, Gemini, ChatGPT), Pareto front, final recommendation |
| `faer_dse_lessons_and_findings.md` | Post-DSE | 32 lessons across 5 categories (process, architecture, technical, meta, open questions) |
| `faer_dse_notebook_plan.md` | Post-DSE | 12 notebook specs with phase gates and dependency graph |

## Key Decision

**Architecture:** Tidy, Decouple, Then Plug (Pattern A+E → Pattern B → Pattern D)
**Phase 1:** EX-1/2/3 + analytics decoupling (12 iterations, ~6 days)
**Decision:** GO. All 7 exit criteria met. 3/3 LLMs converge on Phase 1.
