# FAER DSE: Pseudocode Reference
## Attach alongside Context Index. Gives LLMs concrete call sequences.

---

## Current Engine (THE BASELINE — what exists today)

```pseudo
# engine.py — _patient_journey() monolith (327 LOC, single SimPy generator)

def patient_journey(env, casualty, blackboard, bt, network, facilities):
    emit(ARRIVAL, casualty)
    
    # --- triage (sync BT tick, no yield) ---
    blackboard.set_mist_context(casualty.injury)          # IC-2
    bt.triage_tree.tick()                                   # HC-5, HC-6
    casualty.triage = blackboard.get("decision_triage")     # IC-3
    emit(TRIAGE_ASSIGNED, casualty)
    
    current_facility = casualty.poi
    
    while casualty.state != TERMINAL:
        # --- treatment (SimPy yield: RESOURCE WAIT) ---
        dept = resolve_department(casualty, current_facility)      # extractable (EX-1)
        resource = facilities[current_facility].resources[dept]
        with resource.request() as req:                            # CP-3: mutable
            yield req                                              # ← YIELD POINT 1
            yield env.timeout(treatment_time(casualty, dept))      # ← YIELD POINT 2
            emit(TREATMENT_COMPLETE, casualty)
        
        # --- PFC check (140 LOC nested conditionals in real code) ---
        if hold_required(casualty, current_facility):
            while not downstream_available(network, current_facility):
                yield env.timeout(RETRY_INTERVAL)                  # ← YIELD POINT 3
                if hold_duration > PFC_THRESHOLD:
                    casualty.state = PFC
                    emit(PFC_START, casualty)
        
        # --- routing (sync BT tick, no yield) ---
        blackboard.set_facility_state(facilities)
        bt.routing_tree.tick()
        next_dest = blackboard.get("decision_destination")
        
        # --- transport (SimPy yield: VEHICLE WAIT + TRAVEL) ---
        vehicle = transport_pool[edge].request()
        yield vehicle                                              # ← YIELD POINT 4
        emit(TRANSIT_START, casualty)
        yield env.timeout(travel_time(edge))                       # ← YIELD POINT 5
        # NOTE: with physical_transport=True, vehicle released HERE
        # with physical_transport=False (legacy), vehicle released at YIELD 4
        emit(TRANSIT_END, casualty)
        
        current_facility = next_dest
    
    emit(DISPOSITION, casualty)   # KL-6: MUST match ARRIVAL count
```

**Key facts for DSE agents:**
- 5 yield points in the generator
- Yields 1-2 (treatment) and 4-5 (transport) involve CP-3 shared mutable resources
- Yield 3 (hold/retry) is the 140-LOC nested conditional
- BT ticks are SYNC (no yields) — between yield points, not during
- The entire flow is ONE SimPy generator — cannot yield across module boundaries

---

## Pattern A: UNIFIED (Minimalist — tidy, don't redesign)

```pseudo
# Same generator, but pure functions extracted (EX-1, EX-2)

def patient_journey(env, casualty, ctx):           # ctx bundles dependencies
    emit(ARRIVAL, casualty)
    triage_casualty(casualty, ctx.blackboard, ctx.bt)    # extracted, still sync
    
    while casualty.state != TERMINAL:
        yield from treat(env, casualty, ctx)              # still inline generator
        check_pfc(casualty, ctx)                          # extracted state machine
        route_casualty(casualty, ctx.blackboard, ctx.bt)  # extracted, still sync
        yield from transport(env, casualty, ctx)          # still inline generator
    
    emit(DISPOSITION, casualty)

# engine.py shrinks from 1,309 → ~800 LOC
# New files: triage.py (~50), routing.py (~50), pfc.py (~111), metrics.py (~62)
# Generator still owns ALL yields
```

---

## Pattern B: PLUGIN (Family Divergence — hexagonal ports/adapters)

```pseudo
# Engine is generic. Variant-specific logic loaded as plugins.

class SimulationEngine:
    def __init__(self, plugins: VariantPlugins):
        self.triage    = plugins.triage_strategy      # Protocol
        self.routing   = plugins.routing_strategy      # Protocol  
        self.transport = plugins.transport_strategy    # Protocol
        self.injury    = plugins.injury_model          # Protocol

def patient_journey(env, casualty, engine):
    emit(ARRIVAL, casualty)
    engine.triage.assign(casualty, engine.blackboard)     # plugin call
    
    while casualty.state != TERMINAL:
        yield from engine.treat(env, casualty)            # engine owns yields
        engine.check_pfc(casualty)
        engine.routing.decide(casualty, engine.blackboard) # plugin call
        yield from engine.transport.move(env, casualty)   # plugin owns yields?
    
    emit(DISPOSITION, casualty)

# RISK: if transport plugin owns yields, it must be a SimPy generator.
# This means plugins are NOT pure functions — they're generator factories.
# Creating a new HADR variant means writing new generator code, not just config.

# New FAER-HADR variant:
plugins = VariantPlugins(
    triage=HADRTriageStrategy(),       # different BT tree
    routing=HADRRoutingStrategy(),     # different topology rules
    transport=HADRTransportStrategy(), # different vehicle types
    injury=HADRInjuryModel(),          # different MIST distributions
)
engine = SimulationEngine(plugins)
```

---

## Pattern C: EVENT HISTORIAN (Replay — simulation IS the event stream)

```pseudo
# Every state change is an event. State is a projection.

def patient_journey(env, casualty, store, blackboard, bt):
    store.append(ArrivalEvent(casualty))
    
    triage = triage_casualty(casualty, blackboard, bt)
    store.append(TriageEvent(casualty, triage))
    
    while not terminal(casualty):
        dept, resource = resolve_treatment(casualty)
        with resource.request() as req:
            yield req
            store.append(TreatmentStartEvent(casualty, dept, 
                         state_snapshot=casualty.copy()))          # ← OVERHEAD
            yield env.timeout(treatment_time(casualty, dept))
            store.append(TreatmentEndEvent(casualty, dept,
                         state_snapshot=casualty.copy()))          # ← OVERHEAD
        
        # ... transport with similar event wrapping ...
    
    store.append(DispositionEvent(casualty, state_snapshot=casualty.copy()))

# Replay: state_at(T=45) = reduce(apply_event, store.events_before(T=45))
# Branch: branch_at(T=45, changes) = replay to T=45, apply changes, continue

# COST: ~1KB per event pair × 15 events/casualty × 5000 casualties = 75MB/run
# COST: state_snapshot copy on every event adds ~40% overhead to hot path
# BENEFIT: full replay, branching, survivability from complete history
```

---

## Pattern D: INCREMENTALIST (NB31 pattern × N — no new architecture)

```pseudo
# Current engine. Strangle one component at a time.

# Migration 1: extract _get_next_destination() (EX-1)
# Before: engine.py line 847: dest = self._get_next_destination(cas, facility)
# After:  engine.py line 847: dest = routing.get_next_destination(cas, facility)
#         routing.py: 70 LOC, tested independently, toggle-gated

# Migration 2: extract get_metrics() (EX-2)  
# Before: engine.py line 1200: return self._compute_metrics()
# After:  engine.py line 1200: return metrics.compute(self.event_store)
#         metrics.py: 62 LOC, tested independently, toggle-gated

# Migration 3: extract EventEmitter (EX-3)
# Before: engine.py line 400: self._log_event("TRIAGE", {...legacy dict...})
# After:  engine.py line 400: self.emitter.emit(TriageEvent(...typed...))
#         emitter.py: 73 LOC, closes K-7 (typed fields empty in production)

# ... repeat for EX-4, EX-5, EX-6 ...

# After 6 migrations:
# engine.py: ~500 LOC (down from 1,309)
# New files: routing.py, metrics.py, emitter.py, pfc.py, treatment.py
# Each behind SimulationToggles flag
# Each tested with fixed-seed comparison against pre-migration output
# NO architectural change. Same generator. Same yields. Same interfaces.
```

---

## Pattern E: DUAL-SPEED (Hot/Cold Split — decouple analytics)

```pseudo
# Engine (hot path) publishes events. Analytics (cold path) subscribes.

class SimulationEngine:
    # HOT PATH — only simulation logic, zero analytics
    def patient_journey(env, casualty, ...):
        # identical to current, but NO metrics computation
        # emit() publishes to EventBus (CP-2: already decoupled)
        ...

class AnalyticsEngine:
    # COLD PATH — subscribes to EventBus, materialises views
    def __init__(self, event_bus):
        event_bus.subscribe("ARRIVAL", self._on_arrival)
        event_bus.subscribe("DISPOSITION", self._on_disposition)
        event_bus.subscribe("TREATMENT_COMPLETE", self._on_treatment)
        event_bus.subscribe("TRANSIT_END", self._on_transit)
    
    def _on_disposition(self, event):
        self.golden_hour_view.update(event)
        self.survivability_view.update(event)
        self.facility_load_view.update(event)
    
    def get_view(self, name) -> MaterializedView:
        return self.views[name]

# Dashboard reads AnalyticsEngine, NEVER engine state
# Engine refactoring doesn't break dashboard
# Phase 5 consumables: ConsumableManager subscribes to same EventBus

# engine.py loses: get_metrics() (62 LOC), event query logic (~40 LOC)
# engine.py gains: nothing
# Net: engine.py 1,309 → ~1,200 LOC (modest), but dashboard fully decoupled
```

---

## Usage in DSE

### Pass 1 (Quick Scan)
LLMs can reference these patterns: "My approach is Pattern D + Pattern E"
or "Pattern B but with transport yields staying in engine, not plugin."

### Pass 2 (Architecture)
LLMs must show their proposed patient_journey pseudocode showing WHERE
each yield lives and WHICH module owns it. Diff against the baseline.

### Pass 2b (Red-Team)
LLMs trace the NB32 acceptance test through their pseudocode:
"20 casualties enter at line X, BT ticks at line Y, yield at line Z..."
