# FAER-M Development Lessons & Architectural Decisions
## Companion Document for LLM-DSE Input

**Source:** Distilled from 8+ months of development (Phases 1–4.6), RAIE
framework iterations, RCA-driven hardening, and NB32 kernel analysis.

**Purpose:** Give DSE agents the hard-won context that doesn't appear in code.
Without this, they'll repeat mistakes we've already made.

---

## 1. The V1 Failure Mode (Don't Repeat This)

**What happened:** V1 produced 5,800 lines of specification with ~20% verified
working. Development was horizontal (complete layers) not vertical (thin slices).
The engine was fully spec'd before the dashboard existed. Result: beautiful domain
models that didn't connect into a runnable system.

**Root cause:** Specification outran verification. Test counts were vanity metrics
("handoff theater"). Expert review without implementation feedback created false
confidence.

**The fix that worked (V2):** Dashboard-first, simulation-behind. Every iteration
(50-100 LOC net new) must pass an E2E smoke test before the next begins. Never
let specification outrun verified execution by more than one iteration.

**DSE implication:** Any proposed architecture must be implementable in 50-100
LOC increments with continuous verification. Architectures requiring a "big bang"
cutover or long parallel development paths are rejected on principle.

---

## 2. The Triage Inversion (Hardest Architectural Decision So Far)

**Problem:** V1/Phase 2 generated casualties by sampling triage first, then
generating injuries conditioned on that triage. This is backwards — it's like a
paramedic deciding the triage category before examining the patient.

**Fix (NB24-NB26, now in production):** Invert the flow:
```
OLD: sample_triage(context) → sample_injury(triage) → Casualty
NEW: sample_injury(context) → tick_triage_bt(injury) → Casualty
```

**Why it was hard:** The BT-assigned triage distribution had to match Phase 2
target distributions within ±5%. Required calibrating severity Beta distribution
parameters (α, β) per operational context. NB24 proved this with 10,000-case
cross-validation per context.

**DSE implication:** The injury-first flow is now canonical. Any architecture
must support: generate patient data → decision system assigns triage → simulation
routes based on that decision. The decision system reads blackboard, not raw
patient state.

---

## 3. BT + SimPy Integration (The Hardest Technical Problem)

**Problem:** py_trees is tick-based (synchronous). SimPy is yield-based
(generators). These don't naturally compose.

**Solution (NB15, validated):** Two approaches, both used:
- **Approach A (patient decisions):** BT is a synchronous function called at
  patient decision points within a SimPy generator. `bb.set_context() → bt.tick()
  → bb.get_decision()`. No yield in the BT path.
- **Approach B (system monitoring):** Background SimPy process that periodically
  ticks monitoring BTs (MASCAL detection). Yields `env.timeout(check_interval)`.

**DSE implication:** The blackboard is the mandatory coupling interface. Any
architecture that bypasses the blackboard (BT reads SimPy resources directly,
BT yields SimPy events) violates HC-5 and will break. NB16 stress-tested
concurrent blackboard access under SimPy's cooperative multitasking.

---

## 4. FAER vs FAER-M: Shared Lineage, Not Shared Code

**Key insight:** FAER (NHS single-site) is a queuing network within a single
node. FAER-M is a directed graph where edges (transport) matter as much as
nodes (facilities). The shared lineage is conceptual, not code-level.

**What transfers (leaf-level patterns):**
- Priority queue with triage ordering
- Resource depletion tracking (burn rate, time-to-stockout)
- Alert system (threshold triggers, tiered severity)
- "Seize resource, hold for service time, release" SimPy pattern

**What does NOT transfer:**
- FAER's single-site topology assumptions
- FAER's ED sub-pool model (Resus/Majors/Minors)
- Any architecture assuming intra-facility routing is primary

**DSE implication:** Don't propose architectures that try to unify FAER and
FAER-M at the framework level. The shared patterns are implementation details,
not architectural boundaries. The FAER family divergence is managed through
configuration (YAML context selection), not code branching.

---

## 5. Monte Carlo: Casualty Generation IS the Stochastic Layer

**Insight:** The patient journey is deterministic given a casualty population.
The Monte Carlo layer is the casualty generation (Poisson arrivals, Beta
severity, mechanism sampling, MASCAL burst timing). Run N replications with
different seeds → N different populations → same BT logic → variance.

**Consequence:** The engine must be fully re-instantiable with (config, seed)
and zero global state. This is HC-2 (deterministic replay) in practice.

**Treatment time stochasticity** (e.g., `rng.normal(90, 30)` for OR duration)
is a second variance source within each replication. These RNG streams COULD
be separated (one for arrivals, one for operations) for common random numbers
analysis (Pj-STOCHASM technique), but that's a Phase 5 refinement.

**DSE implication:** Any architecture must support `engine = Engine(seed=N);
engine.run()` with identical results for identical seeds. No singletons, no
module-level RNG, no dict iteration order dependence.

---

## 6. The engine.py Monolith (Quantified by NB32)

**Facts:** engine.py is 1,309 LOC. NB32 broke it into 19 responsibility blocks:
- **69% HOT PATH** (per-casualty): `_patient_journey` (327 LOC), treatment
  (155 LOC), PFC lifecycle (111 LOC), event logging (73 LOC), department
  resolution (42 LOC)
- **29% COLD PATH** (setup/teardown): `__init__` (117 LOC), `run()/step()`
  (66 LOC), `get_metrics()` (62 LOC)
- **2% LEGACY**: `_triage_decisions()` (28 LOC dead code when BT enabled)

**48% (624 LOC) is extractable without touching SimPy yield points.**

**The hard constraint:** `_patient_journey()` is a 327-LOC SimPy generator. The
hold/PFC loop alone is 140 LOC of nested conditionals. You cannot yield across
module boundaries without careful design — the generator must own its yields.

**Validated extraction order (from NB32, risk-rated):**
1. Pure functions: `_get_next_destination()`, ATMIST generation (LOW risk)
2. Pure aggregation: `get_metrics()` (LOW risk)
3. Event emission: extract as EventEmitter protocol (MEDIUM risk)
4. PFC lifecycle: self-contained state machine (MEDIUM risk, CCP path has yields)
5. Treatment orchestration: `_treat_in_department/queue` (MEDIUM risk, generators)
6. Hold/PFC loop from `_patient_journey` (HIGH risk, nested SimPy generator)

**DSE implication:** Proposals to split the monolith must address WHERE the
yields live. The 624 LOC of extractable pure logic is the safe starting point.
The 327-LOC patient journey generator is the hard problem.

---

## 7. The NB31 MIST Migration (Proof of Pattern)

**What happened:** NB31 replaced `DataDrivenInjurySampler` (86 LOC) with
`MISTSampler` (~250 LOC) + MIST YAML schema (13K chars). The blackboard
contract (`set_patient_context()` / `to_blackboard_dict()`) was preserved.

**What worked:** The strangler pattern. Old sampler still works. New sampler
drops in behind the same interface. Factory selector gains `mode="mist"` option.
Backward compatible throughout.

**What was harder than expected:** Getting the M → I → S → T conditional
sampling chain to produce distributions that matched the existing engine's
triage proportions. The severity → vitals mapping required empirical tuning.

**Migration cost:** 86 LOC replaced by ~250 LOC + schema. Net increase, but
the new sampler captures pre-triage vitals and CMT interventions that the old
one couldn't model at all. LOC went up, capability went up more.

**DSE implication:** Real strangler migrations in this codebase cost ~3x the
LOC of the thing they replace, take 1-2 days, and require distribution
calibration. Use this as baseline for migration cost estimates.

---

## 8. Development Methodology Constraints

**Non-negotiable workflow:**
- 50-100 LOC per iteration, verified demo at each step
- Notebook-first validation (prove in NB, then extract to production)
- E2E smoke test must pass after every iteration
- Domain cheat sheet (2-3 pages max) over full PRD for each phase

**AI-assisted development model:**
- Claude Code / Cursor for implementation
- Human (Ross) provides domain governance and architectural decisions
- AI is skilled implementer, not autonomous architect
- Instruction files (.md) drive Claude Code sessions

**DSE implication:** Any proposed architecture must be compatible with this
workflow. "Rewrite from scratch in 2 weeks" is not feasible. "Extract and
replace component X in 3 iterations of 80 LOC each" is feasible.

---

## 9. Transport Is Physically Impossible (The Hardest Correctness Bug)

**Problem:** SimPy Resource is freed at TRANSIT_START, then travel happens
asynchronously. A single helicopter can "carry" 5 patients simultaneously to
different destinations. This is not an edge case — it's a fundamental modelling
error in the core transport loop.

**Why it's hard:** The `with transport_pool.request() as req:` block must
INCLUDE the travel yield. Moving the yield inside the `with` block changes
results dramatically — throughput drops from fantasy numbers to physically
realistic ones. A single helicopter serving 10 patients/hour drops to 2-3
(must fly there and back).

**The fix pattern:** Strangler behind `SimulationToggles.physical_transport`
toggle. New path holds vehicle through entire travel. Old path preserved for
backward compatibility. Run both on fixed seeds, compare, then flip default.

**DSE implication:** If your architecture depends on realistic transport
bottlenecks (resupply vs CASEVAC tradeoffs, vehicle availability), verify
`physical_transport=True`. The legacy path produces physically impossible
numbers that make transport analysis meaningless.

---

## 10. run() Semantics and Incremental Execution

**Problem:** `run(duration=60)` called `env.run(until=60)` (absolute time).
A second call `run(duration=60)` failed because SimPy was already past time 60.
Each call spawned a NEW arrival process. Metric counts drifted across calls.

**Why it mattered:** The ensemble pattern (`build() → run(60) → run(60) →
run(60)`) was silently broken. Same seed produced same result because time
reset instead of advancing.

**The fix:** Track arrival process startup, use `env.run(until=env.now +
duration)` for relative advancement. Invariant test enforces one-shot ==
split-run equivalence on deterministic seeds.

**DSE implication:** The engine must support incremental execution for Phase 5
stochastic capacity (weather/threat changes mid-run). If `run()` can't advance
incrementally, the entire dynamic environment model breaks. Any proposed
architecture must pass: `engine.run(60); engine.run(60)` == `engine.run(120)`.

---

## 11. Event Contract Is Non-Negotiable (Invariant-Driven Development)

**The invariant:**
```python
assert len(store.events_of_type("DISPOSITION")) == len(store.events_of_type("ARRIVAL"))
```

Every patient exit path (normal completion, routing failure, KIA, PFC ceiling,
hold-then-release) MUST emit a terminal DISPOSITION event. Phase 4.5 found that
routing failures broke without emitting DISPOSITION or TRANSIT_END, causing
event counts to not match arrival counts, replay state to become inconsistent,
and outcome metrics to be incomplete.

**If a patient was in transit, TRANSIT_END must precede DISPOSITION.** No
exceptions.

**DSE implication:** If you add a new patient exit path, you MUST emit
DISPOSITION. The invariant test suite enforces this. Run it before committing
any engine changes. Any architecture that restructures patient flow must
preserve this invariant.

---

## 12. Coupling Analysis (What You Can and Can't Decouple)

**NB32 measured per-casualty coupling volume on the hot path:**

| Interface | Ops/Casualty | Mutable? | Decoupling Cost |
|-----------|-------------|----------|-----------------|
| Blackboard | ~16 read/writes | Yes | LOW — shared-memory works; message-passing adds serialisation per BT tick |
| EventBus | 8-15 publishes | No (immutable) | LOWEST — already decoupled. Any architecture works. Cleanest coupling point. |
| SimPy Resources (transport + queues) | ~4-8 requests | Yes (shared mutable) | HIGHEST — wrapping behind a protocol adds latency to every yield point |
| Topology (NetworkX) | 2-4 reads, ~1 write | Read-heavy | LOW — safe to extract behind a protocol |

**DSE implication:** SimPy Resource state is the architectural bottleneck. The
blackboard can tolerate message-passing overhead. The EventBus is already
decoupled. But transport and queue resources CANNOT be moved to separate
processes without fundamentally changing SimPy's cooperative scheduling model.
This is why "microservices" and "separate processes for BT and DES" are
pre-rejected.

---

## 13. Kernel Isolation Proof (11 Files, Not 16)

**NB32 proved** a primitive simulation (1 casualty → 1 triage → 1 route → 1
outcome) runs with only 11 of 16 KERNEL files:
- Types: enums, schemas, exceptions
- Decisions: blackboard, trees, bt_nodes, mode
- Network: topology
- Events: models, bus, store

**The remaining 5 files** (engine.py, arrivals.py, casualty_factory.py,
transport.py, queues.py) are orchestration infrastructure — the primitive can
run without them by inlining their logic.

**DSE implication:** The TRUE irreducible kernel is 11 files. The 5
orchestration files are architecture-dependent — any redesign reimplements
them. Don't try to preserve orchestration code; focus on preserving the
11-file kernel's interfaces.

---

## 14. The RCA Layered Fix Pattern

**Phase 4.5 RCA identified 27 findings clustering into 6 root causes.** The
fix order followed data flow: build correctly → run correctly → emit correctly
→ analyse correctly. Each layer depends on the one below.

**The three-regime department capacity model** is the most architecturally
significant fix:
- **Regime A** (beds ≥ departments): partitioned, per-dept SimPy Resources
- **Regime B** (0 < beds < departments): logical-only departments,
  facility-level capacity. THIS IS THE COMMON CASE for forward military
  facilities (R1/R2 with 1-5 beds).
- **Regime C** (beds == 0): waypoint, pass-through only

**Phase 5 readiness:** After 4.6.2, all 27 findings are closed. Phase 5
consumable events hook into TreatmentStarted/Completed via EventBus subscribers.
The breadth-first delivery guarantee (nested publishes queued, not inline) is
critical — a ConsumableManager publishing StockoutDeclared during a
TreatmentStarted handler must not interrupt other subscribers.

**DSE implication:** When proposing architecture changes, follow the same
layered approach. Fix the lowest layer first. Don't build analytics on broken
events. Don't build events on a broken engine. Don't build an engine on a
broken builder.

---

## 15. Known Gotchas (Save the DSE Agents Time)

| Gotcha | Details |
|--------|---------|
| py_trees blackboard is global | Must wrap in `SimBlackboard` to namespace per-patient |
| SimPy Resource.request() blocks | Can't do BT tick while waiting for resource — tick BEFORE request |
| NetworkX node attributes are mutable dicts | Easy to accidentally share state between runs |
| Pydantic BaseModel + SimPy don't mix well | Casualty uses Pydantic but SimPy processes need mutability |
| `env.timeout(0)` is not free | Zero-duration timeouts still create events and slow simulation |
| Dashboard imports engine internals | Tight coupling means engine refactoring breaks UI |
| YAML loading is slow for large configs | Cache parsed YAML, don't reload per casualty |
| Event log grows unbounded | 20-casualty run = ~150 events. 5000-casualty batch = OOM risk |
| Typed event fields empty in production | `_log_event()` uses legacy dicts; typed fields get defaults. Analytics on typed fields read zeros until emit sites are migrated. |
| EnsembleBuilder circular import | Import from `faer_m.events.ensemble` directly, never from `events/__init__.py` |
| Transport vehicles teleport by default | `physical_transport=False` is legacy. Enable for realistic bottleneck analysis. |
| Three department capacity regimes | Regime B (common for forward R1/R2) has NO per-dept Resources. Don't assume partition. |
| `get_metrics()` had hardcoded 3-outcome dict | Fixed to open-set. Phase 5 outcomes (STOCKOUT_DEATH, etc.) now visible. |
| EventBus delivery is breadth-first | Nested publishes queued, not inline. ConsumableManager won't interrupt current-event subscribers. |
| HOLD_RETRY ≠ separate delays | Deduplicate by (casualty_id, facility_id) episode before counting delays. |
| PFC_START is a state marker, not a delay | `delay_min = 0` for PFC_START nodes. Real delay is HOLD duration. |
| POI varies by context | LSCO uses POI-FRONT, not POI-1. Update POI maps if adding new contexts. |
| `x or default` treats 0 as falsy | `base_rate_per_hour: 0` becomes `2.0`. Use `if x is None: x = default`. |

---

## 16. What DSE Agents Must NOT Propose

Based on lessons learned, the following are pre-rejected:

1. **Async/await anywhere in the engine** — SimPy is cooperative, not async
2. **Separate processes for BT and DES** — The coupling is too tight, IPC overhead kills it (§12)
3. **Database-backed state** — SQLite/Postgres for simulation state adds 10x latency
4. **GraphQL API between engine and dashboard** — Overengineered for single-user tool
5. **Microservices** — Solo developer, local-first tool. One process.
6. **Complete rewrite** — Must be incremental from current codebase via strangler pattern
7. **Framework-level FAER/FAER-M unification** — Shared patterns yes, shared framework no
8. **Naive monolith split** — Cannot extract components that contain SimPy yields without preserving the generator ownership model (§6)
9. **Analytics on typed event fields without verifying emit sites** — Will silently read zeros (§15 gotcha)
10. **Absolute-time run() semantics** — Must support incremental execution for Phase 5 (§10)
