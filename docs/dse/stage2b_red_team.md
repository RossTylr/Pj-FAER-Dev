# FAER DSE — Stage 2b: Red-Team Analysis
## Claude (Adversarial Architect) — Maximum Reasoning Output

**Source documents are no longer in context.** All factual references use
Context Index IDs (KF, HC, CP, IC, EX, MC, KL, K, EP, PR).

---

# PART 1: SELF-RED-TEAM (each approach attacks itself)

---

## S1: MINIMALIST PURE EXTRACT

### a) ACCEPTANCE TEST TRACE

```pseudo
# S1: 20 casualties, 3-node chain (POI → R1 → R2), POI→R1 contested (20% denial)

# --- DIFF FROM BASELINE: routing extracted (EX-1), metrics extracted (EX-2),
#     emitter protocol (EX-3), PFC sync logic extracted (EX-4 sync portion).
#     ALL yields remain in engine.py _patient_journey(). ---

def run(engine, until=600.0):
    for cas in engine.casualties:
        engine.env.process(engine._patient_journey(cas))    # 20 processes
    engine.env.run(until=until)

def _patient_journey(env, cas, ctx):                        # STILL IN engine.py
    yield env.timeout(cas.created_at)                       # stagger arrivals
    ctx.emitter.emit_arrival(cas, "POI", env.now)           # EX-3: emitter protocol

    # --- triage (sync BT tick, no yield) ---
    ctx.blackboard.clear()
    ctx.blackboard.set_mist_context(cas.mist)               # IC-2
    cas.triage = ctx.bt.tick(ctx.blackboard)                 # HC-5, HC-6
    ctx.emitter.emit_triage(cas, "POI", env.now)             # IC-3 read done

    current = "POI"
    while True:
        # --- routing: EXTRACTED to routing.py (EX-1) ---
        decision = routing.get_next_destination(             # DIFF: was inline
            cas, current, ctx.network, ctx.rng)

        if decision.next_facility is None:
            break

        # --- contested route: still in engine (routing returns is_denied) ---
        if decision.is_denied:                               # EP-2
            wait = ctx.rng.exponential(15)
            yield env.timeout(wait)                          # no yield point # (retry)
            cas.total_wait_time += wait
            ctx.emitter.emit_hold_retry(cas, current, env.now)
            continue

        # --- transit ---
        cas.state = IN_TRANSIT
        travel = decision.travel_time
        if cas.triage == T1: travel *= 0.7
        yield env.timeout(travel)                            # ← YIELD POINT 5 (travel)
        cas.total_transit_time += travel
        ctx.emitter.emit_transit_end(cas, decision.next_facility, env.now)

        # --- treatment (CP-3: resource wait) ---
        cas.state = IN_TREATMENT
        cas.current_facility = decision.next_facility
        resource = ctx.resources[decision.next_facility]
        with resource.request() as req:
            queue_start = env.now
            yield req                                        # ← YIELD POINT 1 (resource)
            cas.total_wait_time += env.now - queue_start
            treat_time = ctx.rng.exponential(20 + cas.mist.severity_score * 40)
            yield env.timeout(treat_time)                    # ← YIELD POINT 2 (treatment)
            cas.total_treatment_time += treat_time
            ctx.emitter.emit_treatment_complete(cas, decision.next_facility, "", env.now)

        # --- PFC check: decision EXTRACTED (EX-4), yield loop STAYS ---
        if hold_required(cas, decision.next_facility):
            hold_start = env.now
            while not downstream_available(ctx.network, decision.next_facility):
                pfc_action = pfc.evaluate_pfc(               # DIFF: was inline
                    cas, env.now - hold_start,
                    downstream_available(ctx.network, decision.next_facility),
                    PFC_THRESHOLD)
                if pfc_action == ESCALATE_PFC:
                    cas.state = PFC
                    ctx.emitter.emit_pfc_start(cas, decision.next_facility, env.now)
                yield env.timeout(RETRY_INTERVAL)            # ← YIELD POINT 3 (hold)

        current = decision.next_facility

    cas.outcome_time = env.now
    cas.state = DISCHARGED
    ctx.emitter.emit_disposition(cas, current, env.now)      # KL-6 invariant
```

**Yield ownership:** ALL 5 yields in `engine.py._patient_journey()`. No change from baseline.
**Module boundary crossings at yield time:** Zero. All extracted calls are sync (return before any yield).

### b) CP-3 STRESS

No CP-3 wrapping. Resources are accessed directly in `engine.py` using `with resource.request() as req: yield req`. Identical to baseline. **Zero added latency.**

However: the PFC hold loop still accesses `downstream_available()` which queries facility state — if this reads resource queue depths, it touches CP-3 in a read-only capacity between yields. Safe under cooperative multitasking (no concurrent mutation during a sync call), but the function call now crosses a module boundary (`pfc.evaluate_pfc()`), adding one function call overhead (~microseconds). **Negligible.**

### c) HADR FORK (2-day budget)

**Cost: HIGH (likely exceeds 2 days).** S1 has no structural support for EP-1. Creating FAER-HADR requires:
- New BT tree in `decisions/trees.py` (~100 LOC) — manageable
- Different routing logic — but routing is now in `routing.py` as a pure function. Still a SINGLE implementation. You'd need to add conditional dispatch or a second function. **This is where it breaks**: routing.py becomes `if context == HADR: ... elif context == MIL: ...` — exactly the branching KL-4 warns against.
- Different topology — loaded from config (already works via NB32 pattern).
- Different injury model — needs factory mode change.

**Verdict:** Possible in 2-3 days but creates ugly context-branching in extracted modules. S1 does not solve EP-1; it defers it.

### d) BATCH OOM (5,000 casualties)

Event log: 8-15 events/casualty (CP-2) × 5,000 = 40,000-75,000 `SimEvent` objects. Each `SimEvent` is a frozen dataclass with ~6 fields (~200 bytes). Total: ~15MB. **Not OOM for a single run.**

For Monte Carlo: 100 replications × 15MB = 1.5GB. `EventStore` is append-only with no flush mechanism. **OOM risk at ~500+ replications** unless EventStore is cleared between runs.

S1 inherits this problem. `metrics.py` (EX-2) now computes from EventStore, which means the store must persist for the full run. **Mitigation**: compute metrics incrementally as events arrive (S3's analytics approach), then flush store.

### e) REPLAY (restart from T=45)

**Cost: FULL RE-RUN.** S1 has no event-sourced replay. To restart from T=45 with a changed parameter, you must re-instantiate the engine with the same seed, run to T=45 (which produces identical results per HC-2), then change the parameter and continue. The cost is proportional to T=45's position in the simulation. No branching possible.

### f) DEBT RESOLUTION

| Debt | Status | Notes |
|------|--------|-------|
| K-1 engine.py monolith | **PARTIALLY RESOLVED** | 1,309 → ~800 LOC. Still large. |
| K-2 Dual factory modes | **INHERITED** | Not addressed. |
| K-3 Legacy triage dead code | **RESOLVED** | Deleted. |
| K-4 Transport hardcoded configs | **INHERITED** | Not addressed. |
| K-5 Single-edge topology | **INHERITED** | Not addressed. |
| K-6 Transport teleportation | **INHERITED** | Not addressed (transport yields untouched). |
| K-7 Typed fields empty | **RESOLVED** | EX-3 emitter publishes typed events. |
| K-8 run() time semantics | **INHERITED** | Not addressed but independent fix. |

**Score: 2 resolved, 1 partial, 5 inherited.**

### g) ITERATION COUNT

EX-1 (routing): 3 iterations. EX-2 (metrics): 3. EX-3 (emitter): 3. EX-4 sync (PFC): 2. K-3 delete: 1.
**Total: 12 iterations × ~75 LOC average = ~900 LOC touched.**
At 1 iteration/half-day: **6 days.** Well within EC-1 (≤2 weeks).

### h) KERNEL TRUTH (5 orchestration files)

| File | Action |
|------|--------|
| `engine.py` (1,335 LOC) | **REWRITTEN** (shrunk to ~800) |
| `arrivals.py` (239 LOC) | **PRESERVED** |
| `casualty_factory.py` (323 LOC) | **PRESERVED** |
| `transport.py` (481 LOC) | **PRESERVED** |
| `queues.py` (98 LOC) | **PRESERVED** |

**1 rewritten, 4 preserved.** Minimal disruption to orchestration layer.

---

## S2: STRANGLER PER DEBT

### a) ACCEPTANCE TEST TRACE

```pseudo
# S2: Same scenario. DIFF: treatment and hold/PFC delegated via yield from.

def _patient_journey(env, cas, ctx):                        # engine.py ~60 LOC orchestrator
    yield env.timeout(cas.created_at)
    ctx.emitter.emit_arrival(cas, "POI", env.now)

    # --- triage (sync, same as S1) ---
    triage_casualty(cas, ctx.blackboard, ctx.bt)             # extracted (EX-1)

    current = "POI"
    while True:
        decision = routing.get_next_destination(cas, current, ctx.network, ctx.rng)
        if decision.next_facility is None:
            break

        if decision.is_denied:
            wait = ctx.rng.exponential(15)
            yield env.timeout(wait)
            cas.total_wait_time += wait
            continue

        # --- transit (yields 4+5 STILL IN ENGINE — transport extraction deferred) ---
        cas.state = IN_TRANSIT
        travel = decision.travel_time
        if cas.triage == T1: travel *= 0.7
        yield env.timeout(travel)                            # ← YIELD POINT 5
        cas.total_transit_time += travel
        ctx.emitter.emit_transit_end(cas, decision.next_facility, env.now)

        # --- treatment: DELEGATED to treatment.py ---
        yield from treatment.treat_patient(                  # ← YIELD POINTS 1+2
            TreatmentContext(
                facility_id=decision.next_facility,
                department="",
                resource=ctx.resources[decision.next_facility],
                env=env, rng=ctx.rng, emitter=ctx.emitter),
            cas)

        # --- PFC: DELEGATED to hold_pfc.py ---
        yield from hold_pfc.hold_and_check_pfc(              # ← YIELD POINT 3
            HoldPFCContext(
                facility_id=decision.next_facility,
                env=env, network=ctx.network,
                rng=ctx.rng, emitter=ctx.emitter,
                pfc_threshold=PFC_THRESHOLD),
            cas)

        current = decision.next_facility

    cas.outcome_time = env.now
    cas.state = DISCHARGED
    ctx.emitter.emit_disposition(cas, current, env.now)      # KL-6
```

**Yield ownership:**
- Y1+Y2: `treatment.py` (via `yield from`)
- Y3: `hold_pfc.py` (via `yield from`)
- Y4+Y5: `engine.py` (transport extraction deferred)

**Diff from baseline:** Three modules now own yields. The orchestrator uses `yield from` to delegate.

### b) CP-3 STRESS

**THIS IS THE CRITICAL RISK.** `treatment.py` receives a `simpy.Resource` object in `TreatmentContext`. It executes:
```pseudo
def treat_patient(ctx, cas):
    with ctx.resource.request() as req:
        yield req                          # Y1
        yield ctx.env.timeout(duration)    # Y2
```

The `with` block manages resource acquisition and release. If an exception propagates through `yield from` during Y1 or Y2, the `__exit__` handler must release the resource. **Python's generator protocol handles this correctly** — `yield from` propagates `throw()` and `close()` into the sub-generator, which triggers `__exit__`.

**BUT:** If `hold_pfc.py` raises during Y3 AFTER treatment has completed and released the resource, there is no issue. The risk is specifically: what happens if the orchestrator is garbage-collected mid-yield? SimPy's `Environment.step()` would not send `close()` to a process it's not currently waiting on. **This is safe** — SimPy processes are either active (waiting on an event) or finished. A process blocked on Y1 can only be interrupted by SimPy's own interrupt mechanism, which correctly propagates.

**Added latency:** One additional function call frame per yield point (~nanoseconds). **Negligible.**

**Hidden risk:** `TreatmentContext` passes `simpy.Resource` across module boundaries. If a future developer stores this reference, they could access CP-3 from outside the yield context. **Discipline required.**

### c) HADR FORK

**Same cost as S1.** S2 has no plugin infrastructure. The extracted modules (`treatment.py`, `hold_pfc.py`, `routing.py`) are single-implementation. HADR would require either duplicating them or adding context-branching. **2-3 days, same ugly branching problem.**

### d) BATCH OOM

Same as S1. EventStore unbounded. Additionally, S2 has more modules holding references — `TreatmentContext` and `HoldPFCContext` dataclasses are created per-casualty. These are lightweight (just references), but 5,000 × 2 contexts = 10,000 small objects. **Not a concern** — they're GC'd after each process completes.

### e) REPLAY

**Same as S1: full re-run.** No event-sourced state. The `yield from` delegation doesn't change replay capability.

### f) DEBT RESOLUTION

| Debt | Status | Notes |
|------|--------|-------|
| K-1 engine.py monolith | **RESOLVED** | 1,309 → ~500 LOC |
| K-2 Dual factory modes | **INHERITED** | |
| K-3 Legacy triage dead code | **RESOLVED** | Deleted |
| K-4 Transport hardcoded configs | **INHERITED** | |
| K-5 Single-edge topology | **INHERITED** | |
| K-6 Transport teleportation | **INHERITED** (but transport.py is next extraction target) | |
| K-7 Typed fields empty | **RESOLVED** | EX-3 emitter |
| K-8 run() time semantics | **INHERITED** | |

**Score: 3 resolved, 0 partial, 5 inherited.** Better than S1 on K-1.

### g) ITERATION COUNT

S1 iterations (12) + EX-5 treatment (6) + EX-6 hold_pfc (6) + K-3 delete (1) = **25 iterations.**
At 1 iteration/half-day: **12.5 days.** Tight against EC-1 but achievable.

**Risk:** EX-6 is HIGH risk (Context Index). If the hold/PFC extraction encounters unexpected yield interactions, iterations could double for that step alone. **Worst case: 31 iterations (~15.5 days), exceeding 2-week target.**

### h) KERNEL TRUTH

| File | Action |
|------|--------|
| `engine.py` | **REWRITTEN** (shrunk to ~500 LOC orchestrator) |
| `arrivals.py` | **PRESERVED** |
| `casualty_factory.py` | **PRESERVED** |
| `transport.py` | **PRESERVED** (extraction deferred) |
| `queues.py` | **PRESERVED** |

**1 rewritten, 4 preserved.** Same disruption as S1.

---

## S3: TIDY THEN DECOUPLE (A+E)

### a) ACCEPTANCE TEST TRACE

```pseudo
# S3: Same as S1 for hot path. DIFF: AnalyticsEngine subscribes to EventBus.

# Hot path: IDENTICAL to S1 trace. All 5 yields in engine.py.
# emitter.emit_*() publishes typed SimEvent to EventBus (CP-2).

# Cold path (NEW — runs synchronously within each publish call):
class AnalyticsEngine:
    def __init__(self, event_bus):
        event_bus.subscribe(self._on_event)
        self.golden_hour = GoldenHourView()
        self.facility_load = FacilityLoadView()
        self.survivability = SurvivabilityView()

    def _on_event(self, event: SimEvent):
        # Dispatched synchronously by EventBus (breadth-first, KL-14)
        self.golden_hour.update(event)
        self.facility_load.update(event)
        self.survivability.update(event)

# After engine.run():
dashboard_data = analytics_engine.get_view("survivability").snapshot()
# Dashboard reads THIS, not engine state.
```

**Yield ownership:** Identical to S1 (all in engine.py).
**Analytics boundary:** EventBus subscriber called synchronously during `emitter.emit_*()`. No yield involved. The subscriber executes between yield points as part of the emit call stack.

### b) CP-3 STRESS

Same as S1 — no CP-3 wrapping. **But new concern:** AnalyticsEngine's `_on_event()` is called synchronously during the hot path (inside `emitter.emit_*()`). If any view's `update()` method is slow (e.g., `SurvivabilityView` doing complex calculations), it adds latency to every emit call, which occurs BETWEEN yield points.

**Quantification:** 8-15 emit calls per casualty. If each view update takes 10μs, with 3 views: 30μs × 15 = 450μs per casualty. At 5,000 casualties: 2.25 seconds. **Acceptable but not free.** If views grow complex (e.g., EP-7 consumable tracking with depletion calculations), this could become a bottleneck.

**Mitigation:** Views must be O(1) amortised (counter increments, not full recomputation). The EventBus breadth-first delivery (Lessons §14) ensures nested publishes don't compound.

### c) HADR FORK

**Same cost as S1 for the engine.** The AnalyticsEngine is variant-agnostic (subscribes to events, not engine internals), so HADR analytics come for free IF the events have the same schema. **But:** HADR may need different views (e.g., `SupplyChainView` instead of `GoldenHourView`). Adding a new view: ~80 LOC, 1 iteration. **Net cost: S1's 2-3 days + 0.5 days for HADR-specific views = 2.5-3.5 days.**

### d) BATCH OOM

**IMPROVED over S1.** If analytics computes incrementally via views, the EventStore can be flushed after each replication. Views retain only aggregated state (~100 bytes per view per run). Monte Carlo: 100 replications × ~100 bytes × 3 views = 30KB. **OOM eliminated for analytics.**

**BUT:** If EventStore is still needed for post-hoc analysis (process mining, replay), it's still unbounded. S3 creates a tension: analytics decoupled via views (good), but EventStore needed for other consumers (unchanged). **The OOM risk shifts from analytics to EventStore consumers.**

### e) REPLAY

**Same as S1: full re-run.** Analytics views are projections, not replay sources. They lose event ordering — `SurvivabilityView.snapshot()` returns aggregated data, not the events that produced it.

**Potential improvement path:** If `EventStore` is retained (accepting OOM risk), replay is available through the existing `events/replay.py` module. S3 doesn't make this better or worse.

### f) DEBT RESOLUTION

Same as S1 (2 resolved, 1 partial, 5 inherited), PLUS:
- **I-1 (Dashboard imports engine internals):** **RESOLVED.** Dashboard reads `AnalyticsEngine.get_view()`, not engine state.
- **I-4 (No API layer):** **PARTIALLY RESOLVED.** `AnalyticsEngine` is a de facto service boundary.

**Score: 2 resolved + 2 interface debts resolved, 1 partial, 5 inherited.** Better than S1 for consumer decoupling.

### g) ITERATION COUNT

S1 iterations (12) + AnalyticsEngine scaffold (2) + 3 views (3) + dashboard rewiring (2) = **19 iterations.**
At 1 iteration/half-day: **9.5 days.** Comfortable within EC-1.

### h) KERNEL TRUTH

Same as S1: 1 rewritten (engine.py), 4 preserved. AnalyticsEngine is a NEW file, not a rewrite.

---

## S4: FUNCTIONAL CORE SHELL

### a) ACCEPTANCE TEST TRACE

```pseudo
# S4: 20 casualties, 3-node chain. ALL business logic in planner (pure).
#     ALL yields in shell.py.

def patient_journey(shell, cas):                            # shell.py
    yield shell.env.timeout(cas.created_at)
    shell.emitter.emit_arrival(cas, "POI", shell.env.now)

    # --- triage (sync, planner calls BT) ---
    plan = shell.planner.plan_triage(cas, shell.bb)          # pure function
    cas.triage = plan.triage                                 # IC-3

    current = "POI"
    while True:
        # --- routing decision (pure) ---
        transport_plan = shell.planner.plan_transport(       # pure function
            cas, current, shell.network, shell.rng)

        if transport_plan.to_facility is None:
            break

        # --- contested route (decision in planner, retry in shell) ---
        if transport_plan.is_denied:
            yield shell.env.timeout(transport_plan.denial_wait)  # retry yield
            cas.total_wait_time += transport_plan.denial_wait
            continue

        # --- transit execution (shell owns yields) ---
        cas.state = IN_TRANSIT
        travel = transport_plan.travel_time
        yield shell.env.timeout(travel)                      # ← YIELD POINT 5
        cas.total_transit_time += travel
        shell.emitter.emit_transit_end(cas, transport_plan.to_facility, shell.env.now)

        # --- treatment decision (pure) → execution (shell) ---
        treat_plan = shell.planner.plan_treatment(           # pure function
            cas, FacilitySnapshot(transport_plan.to_facility, ...))

        cas.state = IN_TREATMENT
        cas.current_facility = transport_plan.to_facility
        resource = shell.resources[transport_plan.to_facility]
        with resource.request() as req:
            queue_start = shell.env.now
            yield req                                        # ← YIELD POINT 1
            cas.total_wait_time += shell.env.now - queue_start
            duration = shell.rng.exponential(treat_plan.estimated_duration)
            yield shell.env.timeout(duration)                # ← YIELD POINT 2
            cas.total_treatment_time += duration
            shell.emitter.emit_treatment_complete(
                cas, transport_plan.to_facility, treat_plan.department,
                shell.env.now)

        # --- PFC check (decision in planner, yield loop in shell) ---
        hold_start = shell.env.now
        while True:
            downstream = downstream_available(shell.network, transport_plan.to_facility)
            hold_decision = shell.planner.evaluate_hold(     # pure function
                cas, shell.env.now - hold_start, downstream, PFC_THRESHOLD)

            if hold_decision.action == RELEASE:
                break
            if hold_decision.action == ESCALATE_PFC:
                cas.state = PFC
                shell.emitter.emit_pfc_start(cas, transport_plan.to_facility, shell.env.now)

            yield shell.env.timeout(hold_decision.retry_interval)  # ← YIELD POINT 3

        current = transport_plan.to_facility

    cas.outcome_time = shell.env.now
    cas.state = DISCHARGED
    shell.emitter.emit_disposition(cas, current, shell.env.now)  # KL-6
```

**Yield ownership:** ALL 5 yields in `shell.py`. Planner is pure (zero yields).
**Diff from baseline:** Decision logic extracted to pure functions. Shell structure mirrors baseline generator closely — the indirection is in the CALLS, not the YIELDS.

**CRITICAL FINDING:** The shell's PFC retry loop is structurally identical to the baseline's. The "functional core" benefit here is that `evaluate_hold()` is a pure function that can be unit-tested, but the shell still contains the same `while True: ... yield env.timeout(...)` structure (~30 LOC). The **irreducible shell complexity is real** — approximately 80 LOC of yield-bearing control flow that cannot be made pure.

### b) CP-3 STRESS

Shell accesses CP-3 directly, same as baseline. No wrapping. **Zero added latency.**

The planner creates a `TreatmentPlan` with `estimated_duration` — but the ACTUAL duration is sampled by the shell using `rng.exponential(treat_plan.estimated_duration)`. This is a design choice: the planner proposes a mean, the shell samples. **Risk:** If the planner needs to influence the distribution shape (not just mean), the `TreatmentPlan` dataclass must grow. For now, acceptable.

**Concern:** `FacilitySnapshot` must be constructed by the shell before calling `plan_treatment()`. This snapshot must capture current resource queue depths (CP-3 read). If constructing the snapshot requires accessing `resource.count` or `resource.queue`, it's a sync read between yield points — safe, but it couples the snapshot construction to SimPy's Resource API.

### c) HADR FORK

**BETTER THAN S1, WORSE THAN S5.** The planner is a Protocol — you can implement `HADRPlanner` with different `plan_triage()`, `plan_transport()`, `evaluate_hold()`. **But:** the shell structure (which yields to execute, in what order) is FIXED. If HADR needs a fundamentally different journey structure (e.g., no PFC, different treatment-before-routing order), the shell must be duplicated or parameterised.

**Cost estimate:** New `HADRPlanner` implementation: ~200 LOC, 1.5 days. Shell is reusable IF journey structure matches. **If journey structure differs: +1 day for shell variant. Total: 2-2.5 days.** Tight but feasible.

### d) BATCH OOM

Same as S1. Pure planner doesn't help with event log growth. `TreatmentPlan` and `TransportPlan` objects are created per decision (~50 bytes each, short-lived). **No additional OOM risk from plan objects.**

### e) REPLAY

**Marginally better than S1.** If plans are logged alongside events (adding `plan` field to SimEvent metadata), replay can distinguish decisions from execution. But full SimPy replay still requires re-running from seed. **Cost: same as S1 (full re-run).**

### f) DEBT RESOLUTION

| Debt | Status | Notes |
|------|--------|-------|
| K-1 engine.py monolith | **RESOLVED** | engine.py eliminated; shell.py ~120 LOC + planner ~250 LOC |
| K-2 Dual factory modes | **INHERITED** | |
| K-3 Legacy triage dead code | **RESOLVED** | Doesn't exist in new structure |
| K-4 Transport hardcoded configs | **INHERITED** | |
| K-5 Single-edge topology | **INHERITED** | |
| K-6 Transport teleportation | **ADDRESSABLE** | Shell controls vehicle yield timing — fix is localised to shell transport section |
| K-7 Typed fields empty | **RESOLVED** | EX-3 emitter |
| K-8 run() time semantics | **INHERITED** | |

**Score: 3 resolved, 1 addressable, 4 inherited.** Best K-1 resolution of any approach.

### g) ITERATION COUNT

Plan dataclasses (1) + pure functions (2+2) + shell scaffold (1) + treatment migration (3) + PFC migration (3) + transport migration (2) + emitter+wiring (2) + metrics (2) = **18 iterations.**
At 1 iteration/half-day: **9 days.** Within EC-1.

**Risk:** The shell migration requires building the entire `patient_journey` in shell.py while the old engine.py still runs. This is a parallel construction, not a strangler. The toggle-gate must switch ENTIRE patient processing from old engine to new shell. **This is a bigger-bang cutover than S1 or S2.** If it fails, rollback is to the full old engine. MC-4 toggle pattern still applies but at a coarser granularity.

### h) KERNEL TRUTH

| File | Action |
|------|--------|
| `engine.py` | **ELIMINATED** → replaced by `shell.py` + `planner.py` |
| `arrivals.py` | **PRESERVED** |
| `casualty_factory.py` | **PRESERVED** |
| `transport.py` | **PRESERVED** |
| `queues.py` | **PRESERVED** |

**1 eliminated + 2 new files, 4 preserved.**

---

## S5: PLUGIN SYNC HEXAGONAL

### a) ACCEPTANCE TEST TRACE

```pseudo
# S5: 20 casualties, 3-node chain. Plugins provide decisions. Engine yields.

def _patient_journey(env, cas, engine):                     # engine.py ~650 LOC
    yield env.timeout(cas.created_at)
    engine.emitter.emit_arrival(cas, "POI", env.now)

    # --- triage (PLUGIN: sync, writes BB) ---
    engine.plugins.triage.assign_triage(cas, engine.bb)      # DIFF: plugin call
    cas.triage = engine.bb.get("decision_triage")            # IC-3

    current = "POI"
    while True:
        # --- routing (PLUGIN: sync) ---
        decision = engine.plugins.routing.select_destination(
            cas, current, engine.network,
            engine.facility_states)                          # DIFF: plugin call

        if decision.next_facility is None:
            break

        # --- contested (PLUGIN: transport plugin checks) ---
        transport_plan = engine.plugins.transport.select_transport_mode(
            cas, current, decision.next_facility,
            engine.network, engine.rng)                      # DIFF: plugin call

        if transport_plan.is_denied:
            yield env.timeout(transport_plan.denial_wait)
            cas.total_wait_time += transport_plan.denial_wait
            continue

        # --- transit (ENGINE owns yields) ---
        cas.state = IN_TRANSIT
        yield env.timeout(transport_plan.travel_time)        # ← YIELD POINT 5
        cas.total_transit_time += transport_plan.travel_time
        engine.emitter.emit_transit_end(cas, decision.next_facility, env.now)

        # --- treatment (ENGINE owns yields, plugin provides params) ---
        cas.state = IN_TREATMENT
        cas.current_facility = decision.next_facility
        resource = engine.resources[decision.next_facility]
        with resource.request() as req:
            queue_start = env.now
            yield req                                        # ← YIELD POINT 1
            cas.total_wait_time += env.now - queue_start
            duration = engine.rng.exponential(
                20 + cas.mist.severity_score * 40)
            yield env.timeout(duration)                      # ← YIELD POINT 2
            cas.total_treatment_time += duration
            engine.emitter.emit_treatment_complete(
                cas, decision.next_facility, "", env.now)

        # --- PFC (PLUGIN: sync evaluation, ENGINE: yield loop) ---
        hold_start = env.now
        while True:
            downstream = downstream_available(engine.network, decision.next_facility)
            hold_decision = engine.plugins.pfc.evaluate(     # DIFF: plugin call
                cas, env.now - hold_start, downstream)
            if hold_decision.action == RELEASE:
                break
            if hold_decision.action == ESCALATE_PFC:
                cas.state = PFC
                engine.emitter.emit_pfc_start(cas, decision.next_facility, env.now)
            yield env.timeout(hold_decision.retry_interval)  # ← YIELD POINT 3

        current = decision.next_facility

    cas.outcome_time = env.now
    cas.state = DISCHARGED
    engine.emitter.emit_disposition(cas, current, env.now)   # KL-6
```

**Yield ownership:** ALL 5 yields in `engine.py`. Plugins are strictly sync.
**Diff from baseline:** Decision call sites replaced with plugin protocol calls. Yield structure unchanged.

### b) CP-3 STRESS

Same as baseline — engine accesses CP-3 directly. Plugins never see SimPy resources. **Zero added latency.**

**Concern:** The `RoutingPlugin.select_destination()` receives `facility_states: Dict[str, FacilitySnapshot]`. The engine must construct these snapshots before calling the plugin. If constructing snapshots requires reading CP-3 resource queues, this is a sync read. For the NB32 primitive (3 facilities), this is 3 reads — negligible. For production topologies (10+ facilities), it's still O(N) sync reads. **Acceptable.**

### c) HADR FORK

**THIS IS S5'S RAISON D'ÊTRE.** Cost:
- `HADRTriagePlugin` (~80 LOC, rule-based, no BT): 1 day
- `HADRRoutingPlugin` (~80 LOC, hub-and-spoke): 0.5 day
- `HADRTransportPlugin` (~50 LOC, different mode selection): 0.5 day
- YAML topology (already works)
- `load_variant("HADR", config)` → returns `VariantPlugins` bundle

**Total: 1.5-2 days. MEETS TARGET.**

**BUT:** The engine's yield structure (treatment → PFC → routing → transport) is fixed. If HADR needs a different journey order (e.g., no PFC, direct transport without treatment at some echelons), the engine loop must be parameterised. **This is a latent rigidity** — the yield STRUCTURE is not pluggable, only the decisions between yields.

### d) BATCH OOM

Same as S1. Plugin objects are lightweight singletons (one per variant, reused across casualties). **No additional OOM.**

### e) REPLAY

Same as S1: full re-run. Plugins don't add replay capability.

### f) DEBT RESOLUTION

| Debt | Status | Notes |
|------|--------|-------|
| K-1 engine.py monolith | **PARTIALLY RESOLVED** | 1,309 → ~650 LOC. Decision logic moved to plugins. |
| K-2 Dual factory modes | **RESOLVED** | `InjuryPlugin` replaces dual factory with variant-specific generation |
| K-3 Legacy triage dead code | **RESOLVED** | Plugin replaces both paths |
| K-4 Transport hardcoded configs | **RESOLVED** | `TransportPlugin` loads from config |
| K-5 Single-edge topology | **INHERITED** (EP-6 hook exists but not implemented) |
| K-6 Transport teleportation | **INHERITED** |
| K-7 Typed fields empty | **RESOLVED** | EX-3 emitter |
| K-8 run() time semantics | **INHERITED** |

**Score: 4 resolved, 1 partial, 3 inherited.** Best debt coverage of the non-wildcard approaches.

### g) ITERATION COUNT

Plugin Protocols (2) + MilTriagePlugin (1) + MilRoutingPlugin (2) + MilTransport+PFC (2) + VariantPlugins+wiring (2) + EX-2+EX-3 (4) + HADRPlugins (3) + toggle validation (2) = **18 iterations.**
At 1 iteration/half-day: **9 days.** Within EC-1.

### h) KERNEL TRUTH

| File | Action |
|------|--------|
| `engine.py` | **REWRITTEN** (shrunk to ~650, plugins injected) |
| `arrivals.py` | **PRESERVED** |
| `casualty_factory.py` | **PARTIALLY REWRITTEN** (delegates to InjuryPlugin) |
| `transport.py` | **PRESERVED** (but TransportPlugin wraps it) |
| `queues.py` | **PRESERVED** |

**1 rewritten, 1 partially rewritten, 3 preserved.**

---

## S6: DETERMINISTIC COMMAND BUS (WILDCARD)

### a) ACCEPTANCE TEST TRACE

```pseudo
# S6: 20 casualties, 3-node chain. Policies emit commands. Dispatcher yields.

def _patient_journey(env, cas, policies, dispatcher):       # orchestrator ~80 LOC
    yield env.timeout(cas.created_at)
    dispatcher.emitter.emit_arrival(cas, "POI", env.now)

    # --- triage (sync policy, no commands — writes BB directly) ---
    policies.triage.decide(cas, dispatcher.bb)

    current = "POI"
    while True:
        # --- routing policy → commands ---
        transport_cmds = policies.routing.plan(cas, current, dispatcher.network)
        # Returns: [AcquireVehicle(...), BeginTransit(...)]
        # OR returns empty if no next facility

        if not transport_cmds:
            break

        # --- dispatch transport commands through interceptor chain ---
        for cmd in transport_cmds:
            yield from dispatcher.dispatch(cmd, cas)         # ← YIELD POINTS 4+5
            # Interceptor may DENY BeginTransit (EP-2 contested)
            # If denied: dispatcher emits ROUTE_DENIED, returns without yielding
            # Orchestrator must check denial and retry:
            if dispatcher.last_outcome == "DENIED":
                wait = dispatcher.rng.exponential(15)
                yield env.timeout(wait)                      # retry wait
                cas.total_wait_time += wait
                break                                        # back to routing

        if dispatcher.last_outcome == "DENIED":
            continue

        # --- treatment policy → commands ---
        treat_cmds = policies.treatment.plan(cas, current)
        # Returns: [AcquireResource(...), BeginTreatment(...)]
        for cmd in treat_cmds:
            yield from dispatcher.dispatch(cmd, cas)         # ← YIELD POINTS 1+2

        # --- PFC policy → commands (iterative) ---
        while True:
            pfc_cmds = policies.pfc.evaluate(cas, current)
            # Returns: [HoldRetry(...)] or [Dispose("RELEASE")] or []
            if not pfc_cmds or pfc_cmds[0].command_type == "RELEASE":
                break
            for cmd in pfc_cmds:
                yield from dispatcher.dispatch(cmd, cas)     # ← YIELD POINT 3

        current = ...  # updated by transit completion

    dispatcher.emitter.emit_disposition(cas, current, env.now)  # KL-6
```

**Yield ownership:** ALL 5 yields in `dispatcher.py` handlers. Orchestrator uses `yield from`.

**CRITICAL FINDING — ORCHESTRATOR COMPLEXITY:** The orchestrator is NOT as simple as the thesis claims. It must:
1. Handle denial outcomes from the interceptor chain (checking `dispatcher.last_outcome`)
2. Implement retry logic for contested routes
3. Manage the PFC while-loop (repeated policy calls + dispatches)
4. Track current facility updates from transit completion

This pushes the orchestrator from ~80 LOC to **~120 LOC** with error handling. The "decide→enqueue→dispatch→yield→publish" pipeline is clean in theory but the retry and iteration patterns add orchestrator complexity that mirrors the baseline's control flow.

### b) CP-3 STRESS

**Dispatcher handlers access CP-3.** Each handler is a mini-generator:
```pseudo
# In dispatcher.py
def _handle_acquire_resource(self, cmd, cas):
    resource = self.resources[cmd.facility_id]
    with resource.request() as req:
        yield req                                            # Y1
        # resource acquired

def _handle_begin_treatment(self, cmd, cas):
    duration = self.rng.exponential(cmd.estimated_duration)
    yield self.env.timeout(duration)                         # Y2
```

**Concern:** `AcquireResource` and `BeginTreatment` are separate commands, but in the baseline they occur inside a single `with resource.request()` block. If dispatched as separate commands, **the resource is acquired in handler 1 and the treatment timeout happens in handler 2 — but the resource `with` block has already exited after handler 1 returns.**

**THIS IS A POTENTIAL FATAL FLAW.** The `with resource.request()` context manager MUST span both the acquisition yield (Y1) and the treatment yield (Y2). If these are in separate handlers dispatched sequentially, the resource is released between them.

**Fix options:**
1. **Merge Y1+Y2 into a single `TreatResource` command** — but this defeats the command granularity.
2. **Handler 1 returns a held resource reference, handler 2 receives it** — but this leaks CP-3 state between handlers.
3. **Single handler for the entire treatment phase** — effectively a `TreatmentHandler` sub-generator that owns both yields.

Option 3 is viable but means the command bus has COMPOUND commands (one command → multiple yields), reducing the "one command, one yield" elegance.

**This must be resolved in Stage 2c or the approach has a structural issue.**

### c) HADR FORK

**Good structural support.** New policies: `HADRTriagePolicy`, `HADRRoutingPolicy`, `HADRTreatmentPolicy`. Interceptors are variant-agnostic (contested route denial works for any variant). Dispatcher is generic.

**Cost:** ~200 LOC for HADR policies + wiring. **1.5-2 days.** Meets target.

**BUT:** Same journey-structure rigidity as S5. The orchestrator's loop order (routing → transport → treatment → PFC) is fixed. HADR variants with different phase ordering need orchestrator changes.

### d) BATCH OOM

**CommandLog is an additional growth vector.** 5 commands/casualty × 5,000 casualties = 25,000 Command objects. At ~150 bytes each: ~3.75MB per run. For Monte Carlo: 100 reps × 3.75MB = 375MB. **Add to EventStore's 15MB/run = ~1.9GB total. Approaching OOM.**

**Mitigation:** CommandLog must be flushable between replications, same as EventStore.

### e) REPLAY

**BEST REPLAY OF ALL APPROACHES.** CommandLog IS the replay source. To restart from T=45:
1. Replay CommandLog up to T=45 (re-dispatch commands, deterministic per HC-2)
2. Modify parameter at T=45
3. Continue dispatching with modified policies

**Cost: O(commands_before_T=45), not full re-run.** This is the command bus's killer feature.

**Caveat:** Replay requires that CommandLog captures enough state to reconstruct CP-3 resource states. If resource queue ordering depends on SimPy's internal priority queue, replaying commands in the same order produces the same queue — but only if the SimPy environment is freshly instantiated. **Partial replay (skip to T=45) is actually a full re-run to T=45, then branch.** Still better than S1 (which must re-run to completion and then re-run again with changes).

### f) DEBT RESOLUTION

| Debt | Status | Notes |
|------|--------|-------|
| K-1 engine.py monolith | **RESOLVED** | Replaced by orchestrator (~120) + dispatcher (~200) + policies |
| K-2 Dual factory modes | **INHERITED** | |
| K-3 Legacy triage dead code | **RESOLVED** | |
| K-4 Transport hardcoded configs | **ADDRESSABLE** | TransportPolicy can load from config |
| K-5 Single-edge topology | **INHERITED** | |
| K-6 Transport teleportation | **RESOLVED** | Dispatcher handler controls vehicle lifecycle explicitly |
| K-7 Typed fields empty | **RESOLVED** | Emitter publishes typed events |
| K-8 run() time semantics | **INHERITED** | |

**Score: 4 resolved, 1 addressable, 3 inherited.** Ties with S5.

### g) ITERATION COUNT

Command dataclasses (2) + dispatcher scaffold (3) + hold/PFC handler (2) + transport handler (2) + policies (3) + orchestrator (1) + interceptor EP-2 (1) + CommandLog (2) + EX-2+EX-3 (4) + toggle validation (2) = **22 iterations.**
At 1 iteration/half-day: **11 days.** Within EC-1 but tight.

**Risk:** The CP-3 compound command issue (§b above) could add 2-3 iterations to resolve. **Worst case: 25 iterations, ~12.5 days.**

### h) KERNEL TRUTH

| File | Action |
|------|--------|
| `engine.py` | **ELIMINATED** → replaced by `orchestrator.py` + `dispatcher.py` + `policies/*.py` |
| `arrivals.py` | **PRESERVED** |
| `casualty_factory.py` | **PRESERVED** |
| `transport.py` | **PARTIALLY REWRITTEN** (handlers replace TransportPool interface) |
| `queues.py` | **PARTIALLY REWRITTEN** (handlers replace FacilityQueue interface) |

**1 eliminated + 3 new, 2 partially rewritten, 2 preserved.** Most disruption of any approach.

---

# PART 2: CROSS-RED-TEAM (approaches attack each other)

## VELOCITY attacks EXTENSIBILITY

### S1 (velocity) attacks S5 (extensibility)

**"You're building infrastructure you don't need yet."** S5 adds ~200 LOC of Protocol definitions, a plugin registry, and a `load_variant()` factory — all for a variant (HADR) that doesn't exist yet. YAGNI. S1 ships in 6 days; S5 ships in 9. Those 3 extra days buy plugin infrastructure for a hypothetical future. If HADR is never built, S5 wasted 30% more time.

**S5's weakness exposed:** The plugin Protocols must be defined BEFORE the first plugin exists. This means predicting the interface shape for HADR/Hospital variants based on speculation, not implementation experience. KL-1 warns: "Specification outran verification." Plugin interfaces designed before a variant is built risk being wrong.

### S1 attacks S6 (wildcard)

**"Your command bus is an architecture astronaut's dream."** S6 adds Commands, a Dispatcher, Interceptors, a CommandLog — ~1,685 LOC of new infrastructure for an engine that currently works. The compound command issue (Y1+Y2 in one `with` block) proves the abstraction leaks. The orchestrator ends up at ~120 LOC of control flow that mirrors the baseline anyway. You've added 4 new concepts (Command, Dispatcher, Interceptor, CommandLog) where S1 adds 0.

**S6's weakness exposed:** The "replay from T=45" feature is only partial replay (re-run to T=45, then branch). The CommandLog adds ~375MB/Monte Carlo. The interceptor chain adds per-command overhead on the hot path.

### S2 (incrementalist) attacks S4 (structural)

**"You can't toggle-gate your way to safety."** S4 replaces the entire engine with a shell+planner. The toggle must switch ALL patient processing at once — no per-component strangler. If the shell has a subtle timing bug, you can't rollback to "shell for treatment, old engine for transport." MC-4 applies at full-engine granularity, not per-extraction. S2 can rollback any single step.

**S4's weakness exposed:** The migration requires building the complete shell BEFORE testing any part of it in production. This is the "big bang cutover" that KL-1 warns against. S2's strangler approach validates each extraction independently.

## EXTENSIBILITY attacks VELOCITY

### S5 attacks S1

**"You'll pay the cost later, with interest."** S1's `routing.py` is a single pure function. When HADR needs different routing, you'll add `if context == HADR: ...` branching — exactly what KL-4 forbids. Every future variant adds another branch. After 3 variants, `routing.py` becomes a new monolith. S5 pays the Protocol cost upfront but every subsequent variant is a new file, not a branch.

**S1's weakness exposed:** S1 optimises for TODAY's engine. It doesn't address EP-1 (variant family), EP-2 (contested transport), or EP-5 (alternative BT). These are stated requirements, not speculative. Deferring them means paying S5's cost later PLUS refactoring S1's single-implementation modules.

### S4 attacks S2

**"You've shuffled files, not changed architecture."** After S2's 25 iterations, you have 6 new modules... that are still called in the same order, with the same data flow, by the same generator pattern. You've made the monolith thinner but not more testable. The extracted treatment.py is a SimPy generator — you still can't unit-test it without SimPy. S4's planner is pure — every decision function is testable with plain asserts.

**S2's weakness exposed:** `yield from` delegation preserves yield semantics but not testability. `treatment.py` requires SimPy fixtures to test. `hold_pfc.py` requires SimPy fixtures AND network fixtures. S4's functional core needs neither.

### S6 attacks S5

**"Your plugins solve variant decisions but ignore variant execution."** S5's plugins return sync decisions. The engine's yield structure (treatment→PFC→routing→transport) is hardcoded. If HADR needs a different journey structure (e.g., triage→transport→treatment with no PFC), you need a second engine. S6's command bus naturally supports different command sequences for different variants — the policies emit different commands, the dispatcher handles them generically.

**S5's weakness exposed:** Pluggable decisions with a fixed execution skeleton is only half the extensibility story. Execution-order divergence requires engine changes in S5 but only policy changes in S6.

### S5 attacks S4

**"Your planner protocol is a plugin system that won't admit it."** `JourneyPlanner` is a Protocol with `plan_triage()`, `plan_treatment()`, `plan_transport()`, `evaluate_hold()`. That IS a plugin bundle — it just doesn't have variant-aware loading, registry, or composition. You'd end up building `MilitaryPlanner`, `HADRPlanner`, etc. — exactly S5's plugins without the infrastructure.

**S4's weakness exposed:** The shell is variant-agnostic, but a single `JourneyPlanner` implementation must handle all variants. Swapping the entire planner for HADR works, but composition (use military triage + HADR routing) requires planner decomposition into... plugins.

---

# SUMMARY: KEY FINDINGS

## Critical Issues Surfaced

| # | Issue | Approaches Affected | Severity |
|---|-------|-------------------|----------|
| 1 | **S6 CP-3 compound command**: Y1+Y2 must share a `with resource.request()` block. Separate commands break resource lifecycle. | S6 only | **HIGH** — structural, must be resolved |
| 2 | **S4 big-bang cutover**: Cannot toggle-gate per-component; entire shell replaces entire engine. Violates spirit of MC-4. | S4 only | **MEDIUM** — mitigatable with dual-path running but coarser than S2 |
| 3 | **S1/S2 HADR branching**: No plugin infrastructure means variant logic becomes if/else branching in extracted modules. | S1, S2, S3 | **MEDIUM** — acceptable if only 2-3 variants ever exist |
| 4 | **S5/S6 fixed journey structure**: Plugin/policy decisions are pluggable but the yield execution order is fixed. HADR with different phase ordering requires engine/orchestrator changes. | S5, S6 | **LOW-MEDIUM** — most variants share treatment→PFC→route→transport order |
| 5 | **All approaches: EventStore OOM**: 15MB/run × 100+ Monte Carlo replications unbounded. | All | **MEDIUM** — must add flush-between-runs regardless of architecture |
| 6 | **All approaches: replay is full re-run**: Only S6 offers even partial replay. | S1-S5 | **LOW** — replay not an exit criterion (EC-1 to EC-7) |
| 7 | **S2 EX-6 risk**: Hold/PFC extraction is HIGH risk. Iteration count could double for that step. | S2 only | **MEDIUM** — worst case pushes past 2-week target |

## Debt Resolution Comparison

| Debt Item | S1 | S2 | S3 | S4 | S5 | S6 |
|-----------|----|----|----|----|----|----|
| K-1 Monolith | Partial (800) | ✓ (500) | Partial (730) | ✓ (elim) | Partial (650) | ✓ (elim) |
| K-2 Dual factory | — | — | — | — | ✓ | — |
| K-3 Legacy dead code | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| K-4 Transport config | — | — | — | — | ✓ | Addr |
| K-5 Single-edge | — | — | — | — | — | — |
| K-6 Teleportation | — | — | — | Addr | — | ✓ |
| K-7 Typed fields | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| K-8 run() semantics | — | — | — | — | — | — |
| **Resolved count** | **2** | **3** | **2+2I** | **3+1A** | **4+1P** | **4+1A** |

*Legend: ✓=resolved, Partial=reduced, Addr=addressable, —=inherited, I=interface debt, P=partial*

## Iteration Count Summary (calibrated against MC-1, MC-2)

| Approach | Base iterations | Risk adjustment | Worst case | Days |
|----------|----------------|-----------------|------------|------|
| S1 | 12 | +0 (low risk) | 12 | 6 |
| S2 | 24 | +6 (EX-6 risk) | 30 | 15 |
| S3 | 19 | +2 (view complexity) | 21 | 10.5 |
| S4 | 18 | +4 (cutover risk) | 22 | 11 |
| S5 | 18 | +3 (protocol design) | 21 | 10.5 |
| S6 | 22 | +3 (CP-3 compound) | 25 | 12.5 |
