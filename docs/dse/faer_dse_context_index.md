# FAER Engine DSE — Context Index
## Feed this + Pseudocode Reference to ALL stages.
## Source docs (NB30, NB32, Lessons) loaded in Stage 2a only.
## All stages reference facts by ID (KF-3, HC-5, CP-2, etc.)

---

## KERNEL FACTS (from NB30 + NB32)

| ID | Fact | Source |
|----|------|--------|
| KF-1 | Total kernel: 4,508 LOC, 16 files, 4 layers | NB30 §5.1 |
| KF-2 | TRUE irreducible kernel: 11 files (5 orchestration files are architecture-dependent) | Lessons §13 |
| KF-3 | engine.py: 1,309 LOC = 30% of kernel | NB30 §2.1, Lessons §6 |
| KF-4 | engine.py hot path: 69% (per-casualty), cold path: 29%, legacy: 2% | Lessons §6 |
| KF-5 | _patient_journey(): 327 LOC generator, hold/PFC loop: 140 LOC nested conditionals | Lessons §6 |
| KF-6 | 624 LOC (48%) extractable without touching SimPy yields | Lessons §6 |
| KF-7 | NB32 kernel primitive runs in ~255 LOC | NB32 summary |
| KF-8 | Engine purity: ENGINE_CORE is 42% of total repo LOC | NB30 §1.2 |

## HARD CONSTRAINTS

| ID | Constraint |
|----|-----------|
| HC-1 | SimPy generator model (yield-based, no async/await) |
| HC-2 | Deterministic replay given same (config, seed) |
| HC-3 | Temporal causality (no future state observation) |
| HC-4 | Event immutability (frozen dataclasses after publish) |
| HC-5 | Blackboard isolation (BT ↔ engine ONLY via blackboard) |
| HC-6 | Separation of concerns (BT: zero SimPy imports) |
| HC-7 | Solo-developer velocity (50-100 LOC iterations) |
| HC-8 | Incremental migration only (strangler pattern) |
| HC-9 | Single process (no microservices, no IPC) |
| HC-10 | Python-first (Cython/Rust FFI for hot paths only) |

## COUPLING DATA (from NB32 + Lessons §12)

| ID | Interface | Ops/Casualty | Mutable | Decouple Cost |
|----|-----------|-------------|---------|---------------|
| CP-1 | Blackboard | ~16 r/w | Yes | LOW |
| CP-2 | EventBus | 8-15 publishes | No | LOWEST |
| CP-3 | SimPy Resources | ~4-8 requests | Yes (shared) | HIGHEST |
| CP-4 | Topology (NetworkX) | 2-4 reads, ~1 write | Read-heavy | LOW |

## INTERFACE CONTRACTS (from NB30 §5.3)

| ID | Contract | Key Types |
|----|----------|-----------|
| IC-1 | Casualty → system | Casualty(Pydantic): id, mist, triage, state, facilities_visited, times |
| IC-2 | Engine → Blackboard | set_mist_context(): severity, region, mechanism, polytrauma, surgical, gcs, hr, context |
| IC-3 | Blackboard → BT | decision_triage, decision_department, decision_dcs |
| IC-4 | Engine → EventBus | SimEvent(frozen): sim_time, event_type, casualty_id, facility_id, detail |
| IC-5 | Engine → Network | get_next_facility(), get_travel_time(), is_route_denied(), update_edge_weight() |

## DEBT MAP (from NB30 §4.4 + Lessons §14)

| ID | Debt Item | Level | Severity |
|----|-----------|-------|----------|
| K-1 | engine.py monolith (1,309 LOC) | KERNEL | HIGH |
| K-2 | Dual casualty factory modes coexist | KERNEL | MEDIUM |
| K-3 | Legacy _triage_decisions() dead code | KERNEL | LOW |
| K-4 | transport.py hardcoded TRANSPORT_CONFIGS | KERNEL | MEDIUM |
| K-5 | Single-edge graph topology | KERNEL | MEDIUM |
| K-6 | Transport teleportation (vehicle freed at TRANSIT_START) | KERNEL | HIGH |
| K-7 | Typed event fields empty in production (legacy dict emits) | KERNEL | HIGH |
| K-8 | run() absolute vs relative time semantics | KERNEL | MEDIUM |

## EXTENSION POINTS (from NB30 §5.4 + NB32)

| ID | Extension | Current State | Required For |
|----|-----------|--------------|-------------|
| EP-1 | FAER variant family | OperationalContext enum + YAML | FAER-Hosp, FAER-HADR |
| EP-2 | Contested transport | denial_prob on edges | Ukraine/Delta scenarios |
| EP-3 | Prolonged field care | CCP + basic deterioration | Extended hold modelling |
| EP-4 | Batch/Monte Carlo | EnsembleBuilder | Confidence intervals |
| EP-5 | Alternative BT | SimBlackboard as interface | ML triage, custom logic |
| EP-6 | Multi-edge transport | Single edge per pair currently | Multi-modal selection |
| EP-7 | Phase 5 consumables | Not yet implemented | Blood products, O2, surgical |

## VALIDATED EXTRACTION ORDER (from NB32/Lessons §6)

| Step | Target | LOC | Risk | SimPy Yields? |
|------|--------|-----|------|---------------|
| EX-1 | Pure functions (_get_next_destination, ATMIST) | ~70 | LOW | No |
| EX-2 | get_metrics() | ~62 | LOW | No |
| EX-3 | EventEmitter protocol | ~73 | MEDIUM | No |
| EX-4 | PFC state machine | ~111 | MEDIUM | Yes (CCP path) |
| EX-5 | Treatment orchestration | ~155 | MEDIUM | Yes (generators) |
| EX-6 | Hold/PFC loop from _patient_journey | ~140 | HIGH | Yes (nested) |

## MIGRATION CALIBRATION (from NB31 / Lessons §7)

| ID | Metric | Value |
|----|--------|-------|
| MC-1 | Strangler LOC multiplier | ~3x replaced component |
| MC-2 | Migration duration | 1-2 days per component |
| MC-3 | Distribution calibration | Required (±5% target match) |
| MC-4 | Toggle pattern | SimulationToggles flag, old path preserved |

## KEY LESSONS (compressed from Lessons §1-16)

| ID | Lesson |
|----|--------|
| KL-1 | V1 failed: 5,800 LOC spec, 20% working. Specification outran verification. |
| KL-2 | Injury-first generation is canonical (NB24-26). BT assigns triage from injury, not reverse. |
| KL-3 | BT+SimPy: Approach A (sync tick at decision points) + Approach B (async monitoring). |
| KL-4 | FAER/FAER-M: shared leaf patterns, NOT shared framework. |
| KL-5 | Monte Carlo = casualty generation variance. Patient journey deterministic given population. |
| KL-6 | DISPOSITION event count MUST equal ARRIVAL count. Non-negotiable invariant. |
| KL-7 | Transport teleportation: vehicle must be held through entire travel, not freed at start. |
| KL-8 | run() must support incremental execution (Phase 5 dynamic environments). |
| KL-9 | Three department capacity regimes: A (partitioned), B (logical, facility-level), C (waypoint). |
| KL-10 | RCA fix order follows data flow: build → run → emit → analyse. |
| KL-11 | Working code is an asset. Every re-prompt mutates intent. Strangler toggles preserve working paths while new paths are validated. |

## PRE-REJECTED (from Lessons §16)

| ID | Rejected Approach | Why |
|----|-------------------|-----|
| PR-1 | Async/await | SimPy is cooperative (HC-1) |
| PR-2 | Separate BT/DES processes | CP-3 coupling too tight (HC-9) |
| PR-3 | Database-backed state | 10x latency |
| PR-4 | GraphQL API | Overengineered for single-user |
| PR-5 | Microservices | Solo developer (HC-9) |
| PR-6 | Complete rewrite | Must be incremental (HC-8) |
| PR-7 | FAER/FAER-M framework unification | Shared patterns only (KL-4) |
| PR-8 | Naive monolith split | Must respect yield ownership (KF-5) |
| PR-9 | Analytics on typed fields without verifying emits | Will read zeros (K-7) |
| PR-10 | Absolute-time run() | Must support incremental (KL-8) |

---

## USAGE IN STAGED PROMPTS

### Pass 1: Quick Scan
- **Input:** This index + Pseudocode Reference (no source docs)
- **Mode:** Standard (no extended thinking)
- **Instruction:** "Reference facts by ID (KF-3, HC-5, CP-2, EX-4).
  Reference pseudocode patterns by letter (Pattern A-E).
  Generate approaches as diffs from baseline using index IDs."

### Stage 2a: Architecture Proposals
- **Input:** Source docs (NB30, NB32, Lessons) + this index + Pseudocode Ref
- **Mode:** Extended thinking / ultrathink / o3
- **Instruction:** "You have the source documents, Context Index, and
  Pseudocode Reference. For all subsequent stages, reference facts by
  ID rather than re-reading source material."

### Stage 2b: Red-Teaming
- **Input:** This index + Pseudocode Ref + Stage 2a output (DROP source docs)
- **Mode:** MAXIMUM DEPTH — ultrathink / Deep Think / o3 high effort
- **Instruction:** "Context Index and Pseudocode Reference are your
  references. Source documents are no longer needed. Write acceptance
  test traces AS PSEUDOCODE diffed against the baseline pattern."

### Stage 2c: Scoring & Synthesis
- **Input:** This index + Pseudocode Ref + Stage 2a+2b output
- **Mode:** Extended thinking
- **Instruction:** "Calibrate migration estimates against MC-1 through
  MC-4. Verify your recommendation satisfies all HC constraints."

### Pass 3: Cross-LLM Synthesis
- **Input:** This index + 3 LLM executive summaries
- **Mode:** Research mode (preferred) or extended thinking
- **Instruction:** "Use index IDs when referencing facts. Weight
  findings by comprehension quality."

---

## DSE EXIT CRITERIA

The DSE process has succeeded if the final output contains ALL of:

| # | Criterion | How To Verify |
|---|-----------|---------------|
| EC-1 | Migration Phase 1 ships in ≤2 weeks | Phase 1 scope fits 8-12 iterations × 50-100 LOC |
| EC-2 | All 5 yield points accounted for | Pseudocode trace shows each yield's module owner |
| EC-3 | ≥2 of 3 LLMs converge on top approach | Cross-LLM synthesis §1 (convergence) confirms |
| EC-4 | HC-1 through HC-10 satisfied | Each HC checked against final recommendation |
| EC-5 | Debt items K-1 to K-8 mapped | Red-team §f: resolved vs inherited for winner |
| EC-6 | LOC estimate ≤ current kernel (4,508) | Synthesis includes total LOC projection |
| EC-7 | NB32 acceptance test traced | Function call sequence: casualty → survivability |

If ANY criterion is unmet, the process needs another iteration or
the incrementalist fallback (Pattern D) is the safe choice.
