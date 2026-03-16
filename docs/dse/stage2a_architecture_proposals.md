# FAER DSE — Stage 2a: Architecture Proposals
## Claude (Principal Architect) — Extended Reasoning Output

---

## COMPREHENSION GATE

**a) What is the kernel primitive? (KF-7)**
NB32 proves a complete simulation — 20 casualties → BT triage → graph route → treatment → outcome with survivability — runs in ~255 LOC across 6 layers (Types ~40, EventLog ~25, Blackboard+BT ~50, TreatmentNetwork ~40, DES Engine ~80, Survivability ~20). It is executable truth: the `_patient_process` generator contains the irreducible call sequence (arrival → `bb.set_mist_context()` → `bt.tick()` → evacuation chain with resource waits, transit timeouts, and contested route denial → disposition), demonstrating that every extension in the 4,508 LOC production kernel is additive, not structural.

**b) What is the primary DES↔BT coupling mechanism? (CP-1, IC-2, IC-3)**
The Blackboard (CP-1, `SimBlackboard` wrapping py_trees' global Blackboard). The engine writes patient context via `set_mist_context()` (IC-2: severity, region, mechanism, polytrauma, surgical, gcs, hr, context — 8 keys), then synchronously ticks the BT (zero yields, zero SimPy imports in the BT layer per HC-6), then reads decisions back (IC-3: `decision_triage`, `decision_department`, `decision_dcs`). This write→tick→read cycle is atomic relative to the SimPy event queue — it occurs between yield points, never during them. NB16 stress-tested concurrent blackboard access under SimPy's cooperative multitasking.

**c) What is the single biggest debt item and why? (K-1, KF-3, KF-5)**
K-1: `engine.py` at 1,309/1,335 LOC (30% of kernel), containing `_patient_journey()` — a 327 LOC monolithic SimPy generator with 5 yield points. The hold/PFC loop (KF-5) alone is 140 LOC of nested conditionals. This is the debt because: (i) it couples treatment, PFC, routing, transport, and event emission in one generator, (ii) 624 LOC (48%) is extractable without touching yields (KF-6) but hasn't been extracted, (iii) it blocks every extension point — EP-1 variant divergence, EP-3 PFC modelling, EP-6 multi-modal transport — because all variant logic must share the same 327 LOC control flow, and (iv) the generator ownership constraint means naive splits violate HC-1.

**d) What did NB31 prove about migration cost? (MC-1 to MC-4)**
NB31 replaced `DataDrivenInjurySampler` (86 LOC) with `MISTSampler` (~250 LOC + YAML schema) — a 3× LOC multiplier (MC-1). It took 1-2 days (MC-2) and required distribution calibration to ±5% target match (MC-3) using the injury-first flow (NB24-26 cross-validation). The strangler toggle pattern (MC-4) was critical: old sampler preserved behind `factory_mode` flag, new sampler validated on fixed seeds before flipping default. This is the empirically calibrated baseline for all migration cost estimates.

---

## SHARED SKELETON (applies to ALL 6 approaches — NOT repeated per approach)

The following are invariant across every proposed architecture:

- **11-file irreducible kernel (KF-2) preserved unchanged**: `enums.py`, `schemas.py`, `exceptions.py`, `mode.py`, `blackboard.py`, `bt_nodes.py`, `trees.py`, `topology.py`, `models.py`, `bus.py`, `store.py`. These are NOT architecture-dependent. The 5 orchestration files (`engine.py`, `arrivals.py`, `casualty_factory.py`, `transport.py`, `queues.py`) are the targets for restructuring.
- **Blackboard contract (IC-2, IC-3) preserved**: `set_mist_context()` writes 8 patient keys → BT tick (sync) → engine reads 3 decision keys. No architecture changes this write→tick→read cycle.
- **Event contract (IC-4) preserved**: `SimEvent(frozen=True)` published synchronously to EventBus (CP-2). Subscriber order deterministic. Breadth-first delivery (nested publishes queued).
- **DISPOSITION invariant (KL-6) enforced**: `count(DISPOSITION) == count(ARRIVAL)`. Every exit path (completion, routing failure, KIA, PFC ceiling) MUST emit DISPOSITION. If in transit, TRANSIT_END precedes DISPOSITION.
- **Network protocol (IC-5) preserved**: `get_next_facility()`, `get_travel_time()`, `is_route_denied()`, `update_edge_weight()`. Topology loaded from config dict.
- **HC-1 through HC-6 satisfied by construction**: SimPy generators, deterministic replay, temporal causality, event immutability, blackboard isolation, layer separation.
- **MC-4 toggle pattern**: Every migration step gated behind `SimulationToggles` flag. Old path preserved. Fixed-seed comparison validates before flipping.

---

## APPROACH S1: MINIMALIST PURE EXTRACT

### i) THESIS

Optimises for **velocity and risk minimisation**. Extracts 624 LOC of pure logic (KF-6) from `engine.py` into focused modules without moving any yield points or changing the generator structure. The single `_patient_journey()` generator retains ownership of all 5 yields. Trades away structural extensibility — variant divergence (EP-1) and multi-modal transport (EP-6) remain hard because the orchestration logic stays monolithic. This is Pattern A from the Pseudocode Reference: tidy, don't redesign. It is the fallback if every structural approach fails red-teaming (EC-1: ships in ≤2 weeks).

### ii) NEW INTERFACES

```python
# --- routing.py ---
@dataclass
class RoutingDecision:
    next_facility: str
    travel_time: float
    is_denied: bool

def get_next_destination(
    casualty: Casualty,
    current_facility: str,
    network: TreatmentNetworkProtocol,
    rng: np.random.Generator,
) -> RoutingDecision:
    """Pure function. EX-1. No SimPy, no yields."""
    ...


# --- metrics.py ---
@dataclass(frozen=True)
class SimulationMetrics:
    triage_distribution: Dict[str, int]
    mean_wait_time: float
    mean_transit_time: float
    mean_treatment_time: float
    survivability_by_triage: Dict[str, float]
    facility_utilisation: Dict[str, float]

def compute_metrics(event_store: EventStoreProtocol) -> SimulationMetrics:
    """Pure aggregation. EX-2. Reads EventStore, returns frozen result."""
    ...


# --- emitter.py ---
class EventEmitter(Protocol):
    """EX-3. Typed emission protocol replacing legacy _log_event()."""
    def emit_arrival(self, cas: Casualty, facility_id: str, sim_time: float) -> None: ...
    def emit_triage(self, cas: Casualty, facility_id: str, sim_time: float) -> None: ...
    def emit_treatment_start(self, cas: Casualty, facility_id: str, dept: str, sim_time: float) -> None: ...
    def emit_treatment_complete(self, cas: Casualty, facility_id: str, dept: str, sim_time: float) -> None: ...
    def emit_transit_start(self, cas: Casualty, from_id: str, to_id: str, sim_time: float) -> None: ...
    def emit_transit_end(self, cas: Casualty, facility_id: str, sim_time: float) -> None: ...
    def emit_disposition(self, cas: Casualty, facility_id: str, sim_time: float) -> None: ...
    def emit_pfc_start(self, cas: Casualty, facility_id: str, sim_time: float) -> None: ...
    def emit_hold_retry(self, cas: Casualty, facility_id: str, sim_time: float) -> None: ...


# --- pfc.py ---
class PFCAction(Enum):
    CONTINUE_HOLD = "CONTINUE_HOLD"
    ESCALATE_PFC = "ESCALATE_PFC"
    RELEASE = "RELEASE"

@dataclass
class PFCState:
    hold_start: float
    hold_duration: float
    is_pfc: bool
    deterioration_factor: float

def evaluate_pfc(
    casualty: Casualty,
    hold_duration: float,
    downstream_available: bool,
    pfc_threshold: float,
) -> PFCAction:
    """Pure decision function. EX-4 sync portion. No yields."""
    ...
```

### iii) ENGINE.PY SPLIT

| Block (KF-4) | Current LOC | Destination | Post-split LOC |
|---|---|---|---|
| `_get_next_destination()` + ATMIST | ~70 (hot) | `routing.py` | 0 in engine |
| `get_metrics()` | ~62 (cold) | `metrics.py` | 0 in engine |
| `_log_event()` emission sites | ~73 (hot) | `emitter.py` (protocol) | ~20 (calls to emitter) |
| PFC decision logic (sync portion) | ~60 of 111 (hot) | `pfc.py` | ~50 (yield loop stays) |
| `_triage_decisions()` legacy | ~28 (legacy) | **DELETED** (K-3 closed) | 0 |
| Treatment time calc | ~30 (hot) | stays or `treatment_params.py` | ~30 |
| **Remaining engine.py** | — | — | **~800 LOC** |

The generator `_patient_journey()` shrinks from 327 → ~220 LOC. It still owns all 5 yield points. The hold/PFC `while` loop stays in the generator but calls `evaluate_pfc()` for the decision, reducing the nested conditional from 140 → ~80 LOC.

### iv) STATE OWNERSHIP

| Interface | Owner | Change from baseline |
|---|---|---|
| CP-1 (Blackboard) | engine.py (write) → BT (tick) → engine.py (read) | **No change** |
| CP-2 (EventBus) | `emitter.py` publishes, engine calls emitter | **Emitter owns publication, engine owns call sites** |
| CP-3 (SimPy Resources) | engine.py `_patient_journey()` | **No change** — all `resource.request()` and `env.timeout()` stay in generator |
| CP-4 (Topology) | `routing.py` reads network, engine calls routing | **Routing owns graph queries, engine owns call sites** |

### v) MIGRATION SEQUENCE

| Step | Target | EX# | New LOC | Engine LOC removed | Days | Iterations (50-100 LOC) |
|---|---|---|---|---|---|---|
| 1 | Pure functions → `routing.py` | EX-1 | ~70 × 3 = ~210 | ~70 | 1 | 3 |
| 2 | Metrics → `metrics.py` | EX-2 | ~62 × 3 = ~186 | ~62 | 1 | 3 |
| 3 | Event emitter protocol → `emitter.py` | EX-3 | ~73 × 3 = ~219 | ~53 (net, calls remain) | 1-2 | 3 |
| 4 | PFC sync logic → `pfc.py` | EX-4 (sync only) | ~60 × 3 = ~180 | ~60 | 1 | 2 |
| 5 | Delete legacy `_triage_decisions()` | K-3 | 0 | ~28 | 0.5 | 1 |
| **Total** | | | **~795 new** | **~273 removed** | **4.5-5.5** | **12** |

Post-migration: engine.py ~1,060 LOC. With internal cleanup, ~800 LOC target. Total kernel LOC rises temporarily (~795 new - ~273 removed + boilerplate) but settles at ~4,800 — within EC-6 ceiling. EX-5 and EX-6 (treatment orchestration, hold/PFC loop extraction) are explicitly deferred — they require yield delegation which is beyond this approach's scope.

### vi) COMPONENT DIAGRAM

```
┌─────────────────────────────────────────────────┐
│                  SHARED SKELETON                 │
│  enums │ schemas │ exceptions │ mode             │
│  blackboard │ bt_nodes │ trees                   │
│  topology │ event_models │ bus │ store            │
└────────────────────┬────────────────────────────┘
                     │
    ┌────────────────┼────────────────┐
    │                │                │
┌───▼───┐    ┌──────▼──────┐   ┌─────▼─────┐
│routing │    │  engine.py  │   │  metrics  │
│  .py   │◄───│  ~800 LOC   │───►│   .py     │
│ (EX-1) │    │ owns Y1-Y5  │   │  (EX-2)   │
└────────┘    │ calls all   │   └───────────┘
              │ extracted   │
┌─────────┐   │ modules     │   ┌───────────┐
│emitter  │◄──│             │   │  pfc.py   │
│  .py    │   │             │───►│  (EX-4    │
│ (EX-3)  │   └─────────────┘   │   sync)   │
└────┬────┘                     └───────────┘
     │
     ▼
  EventBus (CP-2)
```

---

## APPROACH S2: STRANGLER PER DEBT

### i) THESIS

Optimises for **continuous delivery safety and regression confidence**. Applies the NB31-proven strangler pattern (MC-4) to each extractable component (EX-1→EX-6) in validated order, with every step independently shippable, toggle-gated, and fixed-seed regression-tested. Trades away architectural ambition — after all 6 extractions, the result is structurally identical to S1 but with treatment and hold/PFC yields also delegated via `yield from`. No new architectural concepts are introduced. The generator remains the single orchestrator; it just gets thinner. This is Pattern D: the safe choice if any exit criterion (EC-1 to EC-7) is at risk.

### ii) NEW INTERFACES

All S1 interfaces apply (routing, metrics, emitter, pfc), PLUS:

```python
# --- treatment.py ---
@dataclass
class TreatmentContext:
    facility_id: str
    department: str
    resource: simpy.Resource      # CP-3: passed in, not owned
    env: simpy.Environment        # SimPy env for yields
    rng: np.random.Generator
    emitter: EventEmitter

def treat_patient(
    ctx: TreatmentContext,
    casualty: Casualty,
) -> Generator:
    """EX-5. SimPy sub-generator owning Yield Points 1+2.
    Delegated via `yield from treat_patient(ctx, cas)` from engine.
    """
    ...


# --- hold_pfc.py ---
@dataclass
class HoldPFCContext:
    facility_id: str
    env: simpy.Environment
    network: TreatmentNetworkProtocol
    rng: np.random.Generator
    emitter: EventEmitter
    pfc_threshold: float

def hold_and_check_pfc(
    ctx: HoldPFCContext,
    casualty: Casualty,
) -> Generator:
    """EX-6. SimPy sub-generator owning Yield Point 3.
    Contains the retry-while-hold loop. Returns PFCAction.
    Delegated via `yield from hold_and_check_pfc(ctx, cas)` from engine.
    HIGHEST RISK extraction. Must preserve nested conditional semantics.
    """
    ...
```

### iii) ENGINE.PY SPLIT

Same as S1 for steps 1-4, then continues:

| Block | Current LOC | Destination | Post-split LOC |
|---|---|---|---|
| Steps 1-4 (same as S1) | ~273 | routing, metrics, emitter, pfc | ~800 |
| Treatment orchestration | ~155 (hot) | `treatment.py` (sub-generator) | ~10 (`yield from`) |
| Hold/PFC loop | ~140 (hot) | `hold_pfc.py` (sub-generator) | ~10 (`yield from`) |
| **Final engine.py** | — | — | **~500 LOC** |

The generator `_patient_journey()` becomes a ~60 LOC orchestrator:
```pseudo
def _patient_journey(env, cas, ctx):
    emit(ARRIVAL, cas)
    triage_casualty(cas, ctx)           # sync, extracted (EX-1)
    while cas.state != TERMINAL:
        yield from treat_patient(ctx, cas)        # EX-5: owns Y1+Y2
        yield from hold_and_check_pfc(ctx, cas)   # EX-6: owns Y3
        route_casualty(cas, ctx)                   # sync, extracted
        yield from transport_patient(ctx, cas)     # future: owns Y4+Y5
    emit(DISPOSITION, cas)
```

### iv) STATE OWNERSHIP

| Interface | Owner | Change from baseline |
|---|---|---|
| CP-1 (Blackboard) | engine.py (write) → BT (tick) → engine.py (read) | **No change** |
| CP-2 (EventBus) | `emitter.py` publishes via protocol | **Same as S1** |
| CP-3 (SimPy Resources) | **Delegated**: `treatment.py` owns Y1+Y2 resource interactions; `hold_pfc.py` owns Y3 retry loop; engine still owns Y4+Y5 (transport extraction deferred) | **CHANGE: CP-3 crosses module boundary via `yield from`** |
| CP-4 (Topology) | `routing.py` | **Same as S1** |

**Critical risk at CP-3 boundary**: `yield from` delegates the sub-generator correctly in Python/SimPy, but exception propagation changes. If treatment raises during a `with resource.request()` block, the `__exit__` cleanup in the sub-generator must release the resource. Each extraction step MUST include `try/finally` resource release tests.

### v) MIGRATION SEQUENCE

| Step | Target | EX# | New LOC | Days | Iterations | Toggle |
|---|---|---|---|---|---|---|
| 1 | `routing.py` | EX-1 | ~210 | 1 | 3 | `toggles.use_extracted_routing` |
| 2 | `metrics.py` | EX-2 | ~186 | 1 | 3 | `toggles.use_extracted_metrics` |
| 3 | `emitter.py` | EX-3 | ~219 | 1.5 | 3 | `toggles.use_typed_emitter` |
| 4 | `pfc.py` (sync) | EX-4 | ~180 | 1 | 2 | `toggles.use_extracted_pfc` |
| 5 | `treatment.py` (generator) | EX-5 | ~155 × 3 = ~465 | 2 | 6 | `toggles.use_extracted_treatment` |
| 6 | `hold_pfc.py` (generator) | EX-6 | ~140 × 3 = ~420 | 2 | 6 | `toggles.use_extracted_hold_loop` |
| 7 | Delete legacy K-3 | — | 0 | 0.5 | 1 | — |
| **Total** | | | **~1,680 new** | **9-10** | **24** | |

Post-migration: engine.py ~500 LOC. Total new code ~1,680 LOC. Net kernel growth: ~1,680 - 624 extracted = ~1,056 new LOC (boilerplate, tests, protocols). Total kernel estimate: ~5,560 LOC — exceeds EC-6 (≤4,508) initially, but stabilises as toggle infrastructure and legacy paths are removed. Final steady-state: ~4,200 LOC.

### vi) COMPONENT DIAGRAM

```
┌─────────────────────────────────────────────────┐
│                  SHARED SKELETON                 │
└────────────────────┬────────────────────────────┘
                     │
┌────────┐  ┌───────┴────────┐  ┌───────────┐
│routing │  │   engine.py    │  │  metrics   │
│  .py   │◄─│   ~500 LOC     │─►│   .py      │
│(EX-1)  │  │                │  │  (EX-2)    │
└────────┘  │  orchestrator: │  └────────────┘
            │  yield from ─┬─│
┌─────────┐ │              │ │  ┌────────────┐
│emitter  │◄│   ┌──────────▼─┤  │ hold_pfc   │
│  .py    │ │   │treatment.py│  │   .py       │
│(EX-3)   │ │   │ Y1+Y2     │  │  Y3         │
└────┬────┘ │   └────────────┤  │  (EX-6)     │
     │      │                │  └─────────────┘
     ▼      │   ┌────────────┤
  EventBus  │   │ pfc.py     │
  (CP-2)    │   │ (sync,EX-4)│
            │   └────────────┘
            └────────────────┘
```

---

## APPROACH S3: TIDY THEN DECOUPLE (Pattern A + Pattern E)

### i) THESIS

Optimises for **pragmatic debt reduction combined with consumer decoupling**. Phase 1 applies all S1 extractions (Pattern A). Phase 2 adds a Dual-Speed analytics split (Pattern E) — moving all metrics computation and dashboard view materialisation behind EventBus subscribers so the hot path never computes analytics. Trades away the aggressive yield delegation of S2 (EX-5/EX-6 stay in engine) in exchange for decoupling the analytics consumer, which directly enables EP-4 (batch/Monte Carlo) by making the engine hot path lighter and making analytics independently evolvable. This is the "two bites" approach: S1 for the engine, Pattern E for the consumers.

### ii) NEW INTERFACES

All S1 interfaces, PLUS:

```python
# --- analytics/engine.py ---
class AnalyticsEngine:
    """Cold-path analytics. Subscribes to EventBus. Never touches SimPy."""

    def __init__(self, event_bus: EventBusProtocol):
        event_bus.subscribe(self._on_event)
        self._views: Dict[str, MaterialisedView] = {}

    def _on_event(self, event: SimEvent) -> None:
        """Dispatch to registered views."""
        ...

    def get_view(self, name: str) -> MaterialisedView:
        ...


# --- analytics/views.py ---
class MaterialisedView(Protocol):
    """Base protocol for analytics views."""
    def update(self, event: SimEvent) -> None: ...
    def snapshot(self) -> Dict[str, Any]: ...

class GoldenHourView:
    """Tracks time-to-treatment by triage category."""
    def update(self, event: SimEvent) -> None: ...
    def snapshot(self) -> Dict[str, Any]: ...

class FacilityLoadView:
    """Tracks concurrent occupancy per facility over time."""
    def update(self, event: SimEvent) -> None: ...
    def snapshot(self) -> Dict[str, Any]: ...

class SurvivabilityView:
    """Computes P(survival) from journey events."""
    def update(self, event: SimEvent) -> None: ...
    def snapshot(self) -> Dict[str, Any]: ...

class ConsumableView:
    """EP-7 hook: tracks blood/O2/surgical kit depletion."""
    def update(self, event: SimEvent) -> None: ...
    def snapshot(self) -> Dict[str, Any]: ...
```

### iii) ENGINE.PY SPLIT

Phase 1 (same as S1): engine.py 1,309 → ~800 LOC
Phase 2 (analytics decoupling):

| Block | Current LOC | Destination | Post-split LOC in engine |
|---|---|---|---|
| `get_metrics()` | ~62 (cold) | Already in `metrics.py` from Phase 1 | 0 |
| Event query logic (inline analytics) | ~40 (cold) | `analytics/engine.py` subscribers | 0 |
| Dashboard coupling points | ~30 (cold) | Dashboard reads `AnalyticsEngine.get_view()` | 0 |
| **Final engine.py** | — | — | **~730 LOC** |

### iv) STATE OWNERSHIP

Same as S1, PLUS:

| Interface | Owner | Change from baseline |
|---|---|---|
| Analytics state | **NEW: `AnalyticsEngine`** owns all materialised views | **CHANGE: Dashboard NEVER reads engine state. Reads views via `AnalyticsEngine.get_view()`.** |
| EP-7 consumables | **NEW: `ConsumableView`** subscribes to treatment events | **CHANGE: Consumable tracking is a subscriber, not an engine modification.** |

The critical boundary: `AnalyticsEngine` subscribes to EventBus (CP-2, already the lowest-coupling interface). It has ZERO access to CP-3 (SimPy Resources). Engine refactoring cannot break analytics. Analytics evolution cannot break the engine.

### v) MIGRATION SEQUENCE

| Step | Target | Phase | New LOC | Days | Iterations |
|---|---|---|---|---|---|
| 1-4 | S1 extractions (EX-1 to EX-4 sync) | 1 | ~795 | 4.5-5.5 | 12 |
| 5 | `AnalyticsEngine` scaffold + EventBus subscription | 2 | ~150 | 1 | 2 |
| 6 | `GoldenHourView` + `FacilityLoadView` | 2 | ~200 | 1.5 | 3 |
| 7 | `SurvivabilityView` | 2 | ~120 | 1 | 2 |
| 8 | Dashboard migration (read views, not engine) | 2 | ~100 (rewiring) | 1 | 2 |
| **Total** | | | **~1,365 new** | **9-10** | **21** |

### vi) COMPONENT DIAGRAM

```
┌─────────────────────────────────────────────────┐
│                  SHARED SKELETON                 │
└────────────────────┬────────────────────────────┘
                     │
┌────────┐  ┌───────┴────────┐  ┌───────────────┐
│routing │  │   engine.py    │  │   pfc.py      │
│  .py   │◄─│   ~730 LOC     │─►│   (EX-4)     │
│(EX-1)  │  │  owns Y1-Y5   │  └───────────────┘
└────────┘  └───────┬────────┘
                    │ publishes via emitter
┌─────────┐         │
│emitter  │◄────────┘
│  .py    │
│(EX-3)   │
└────┬────┘
     │ publishes to
     ▼
┌─────────────────────────────────────────────────┐
│                   EventBus (CP-2)                │
└────┬─────────────┬──────────────┬───────────────┘
     │             │              │
┌────▼────┐  ┌─────▼─────┐  ┌────▼──────┐
│ Golden  │  │ Facility  │  │Survivab-  │
│ Hour    │  │ Load      │  │ility      │
│ View    │  │ View      │  │ View      │
└────┬────┘  └─────┬─────┘  └────┬──────┘
     │             │              │
┌────▼─────────────▼──────────────▼───────────────┐
│              AnalyticsEngine                     │
│         Dashboard reads views here               │
└─────────────────────────────────────────────────┘
```

---

## APPROACH S4: FUNCTIONAL CORE SHELL

### i) THESIS

Optimises for **unit testability of domain logic and clean separation of "what" from "when"**. All business logic (triage, routing, PFC evaluation, treatment planning, transport planning) becomes pure functions returning immutable decision objects. A thin imperative SimPy shell (~120 LOC) reads these decisions and executes the corresponding yields. Trades away simplicity — the shell must translate decision objects into SimPy operations, adding an indirection layer. The PFC retry loop creates irreducible shell complexity (~80 LOC) because the decision function must be called repeatedly inside a yield loop. But the payoff is massive: every decision function is testable without SimPy, making EP-5 (ML triage swap) trivial and enabling formal property testing on the decision space.

### ii) NEW INTERFACES

```python
# --- decisions/plans.py (new file) ---
@dataclass(frozen=True)
class TreatmentPlan:
    """Pure decision: what treatment to perform."""
    facility_id: str
    department: str
    estimated_duration: float       # mean for rng sampling

@dataclass(frozen=True)
class TransportPlan:
    """Pure decision: how to move the casualty."""
    from_facility: str
    to_facility: str
    travel_time: float
    is_denied: bool                 # contested route check result
    denial_wait: float              # if denied, how long to wait

@dataclass(frozen=True)
class HoldDecision:
    """Pure decision: what to do during hold."""
    action: PFCAction               # CONTINUE_HOLD | ESCALATE_PFC | RELEASE
    retry_interval: float
    deterioration_delta: float

@dataclass(frozen=True)
class JourneyStep:
    """Union of possible next actions."""
    step_type: str                  # "TREAT" | "TRANSPORT" | "HOLD" | "DISPOSE"
    treatment: Optional[TreatmentPlan] = None
    transport: Optional[TransportPlan] = None
    hold: Optional[HoldDecision] = None


# --- core_logic/planner.py ---
class JourneyPlanner(Protocol):
    """Pure functional core. No SimPy. No side effects."""

    def plan_treatment(
        self, casualty: Casualty, facility_state: FacilitySnapshot,
    ) -> TreatmentPlan: ...

    def plan_transport(
        self, casualty: Casualty, current_facility: str,
        network: TreatmentNetworkProtocol, rng: np.random.Generator,
    ) -> TransportPlan: ...

    def evaluate_hold(
        self, casualty: Casualty, hold_duration: float,
        downstream_available: bool, pfc_threshold: float,
    ) -> HoldDecision: ...

    def decide_next_step(
        self, casualty: Casualty, current_facility: str,
        facility_state: FacilitySnapshot,
        network: TreatmentNetworkProtocol, rng: np.random.Generator,
    ) -> JourneyStep: ...


# --- shell.py ---
class SimPyShell:
    """Imperative shell. Executes plans as SimPy yields.
    This is the ONLY module that imports simpy.
    Owns all 5 yield points.
    """

    def __init__(
        self,
        env: simpy.Environment,
        planner: JourneyPlanner,
        emitter: EventEmitter,
        resources: Dict[str, simpy.Resource],
        rng: np.random.Generator,
    ): ...

    def patient_journey(self, casualty: Casualty) -> Generator:
        """SimPy generator. Calls planner for decisions, yields for execution."""
        ...
```

### iii) ENGINE.PY SPLIT

| Block | Current LOC | Destination | Notes |
|---|---|---|---|
| Triage logic | ~50 (hot) | `core_logic/planner.py` → `plan_triage()` | Pure function |
| Routing logic | ~70 (hot) | `core_logic/planner.py` → `plan_transport()` | Pure function |
| Department resolution | ~42 (hot) | `core_logic/planner.py` → `plan_treatment()` | Pure function |
| PFC evaluation (sync) | ~60 (hot) | `core_logic/planner.py` → `evaluate_hold()` | Pure function |
| Treatment yield execution | ~155 (hot) | `shell.py` → `_execute_treatment()` | Yields Y1+Y2 |
| Hold/PFC yield loop | ~140 (hot) | `shell.py` → PFC retry loop | Yields Y3 |
| Transport yield execution | ~100 (hot) | `shell.py` → `_execute_transport()` | Yields Y4+Y5 |
| Metrics | ~62 (cold) | `metrics.py` (same as S1) | Pure |
| Event emission | ~73 (hot) | `emitter.py` (same as S1) | Protocol |
| `__init__` + setup | ~117 (cold) | `shell.py` `__init__` | Wiring |
| Legacy triage | ~28 | **DELETED** | K-3 |
| **shell.py** | — | — | **~120 LOC** |
| **core_logic/planner.py** | — | — | **~250 LOC** |
| **engine.py becomes shell.py** | — | — | **engine.py eliminated** |

### iv) STATE OWNERSHIP

| Interface | Owner | Change from baseline |
|---|---|---|
| CP-1 (Blackboard) | `planner.py` writes context, calls BT tick, reads decisions | **MOVED from engine to planner (but same contract)** |
| CP-2 (EventBus) | `shell.py` calls emitter after each yield | **Shell owns emission timing, emitter owns publication** |
| CP-3 (SimPy Resources) | `shell.py` exclusively | **CENTRALISED: only shell.py touches SimPy. Planner has zero SimPy imports.** |
| CP-4 (Topology) | `planner.py` queries network for `TransportPlan` | **MOVED from engine to planner (read-only, safe)** |

Key insight: CP-3 (highest decoupling cost) is now confined to a single module (~120 LOC). All other modules are SimPy-free. This maximally isolates the hardest interface.

### v) MIGRATION SEQUENCE

| Step | Target | New LOC | Days | Iterations |
|---|---|---|---|---|
| 1 | Define plan dataclasses (`decisions/plans.py`) | ~80 | 0.5 | 1 |
| 2 | Extract `plan_triage()` + `plan_transport()` pure functions | ~120 | 1 | 2 |
| 3 | Extract `plan_treatment()` + `evaluate_hold()` | ~130 | 1 | 2 |
| 4 | Build `shell.py` scaffold (treatment yield execution) | ~60 | 1 | 1 |
| 5 | Migrate treatment path: shell calls planner, yields | ~200 | 2 | 3 |
| 6 | Migrate hold/PFC: shell retry loop calling `evaluate_hold()` | ~250 | 2 | 3 |
| 7 | Migrate transport path | ~180 | 1.5 | 2 |
| 8 | Wire `emitter.py`, delete legacy engine.py | ~100 | 1 | 2 |
| 9 | Extract `metrics.py` (same as S1 EX-2) | ~186 | 1 | 2 |
| **Total** | | **~1,306 new** | **11-12** | **18** |

### vi) COMPONENT DIAGRAM

```
┌─────────────────────────────────────────────────┐
│                  SHARED SKELETON                 │
└────────────────────┬────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │    FUNCTIONAL CORE      │
        │  (zero SimPy imports)   │
        │                         │
        │  ┌───────────────────┐  │
        │  │  planner.py       │  │
        │  │  plan_triage()    │  │
        │  │  plan_treatment() │  │
        │  │  plan_transport() │  │
        │  │  evaluate_hold()  │  │
        │  └────────┬──────────┘  │
        │           │decisions    │
        │  ┌────────▼──────────┐  │
        │  │  plans.py         │  │
        │  │  TreatmentPlan    │  │
        │  │  TransportPlan    │  │
        │  │  HoldDecision     │  │
        │  └───────────────────┘  │
        └────────────┬────────────┘
                     │ frozen plan objects
        ┌────────────▼────────────┐
        │    IMPERATIVE SHELL     │
        │    shell.py ~120 LOC    │
        │                         │
        │    Y1: resource.req()   │
        │    Y2: env.timeout()    │ ◄── CP-3: ONLY HERE
        │    Y3: retry timeout    │
        │    Y4: vehicle.req()    │
        │    Y5: travel timeout   │
        └────────────┬────────────┘
                     │ emits
                     ▼
              EventBus (CP-2)
```

---

## APPROACH S5: PLUGIN SYNC HEXAGONAL

### i) THESIS

Optimises for **FAER family divergence (EP-1) and alternative decision systems (EP-5)**. Introduces a ports/adapters architecture where variant-specific logic (triage algorithms, routing policies, injury models, transport selection) is injected as sync-only plugins implementing Python Protocols. The engine core becomes a generic orchestrator that calls plugin methods between yield points. Trades away simplicity for extensibility — the plugin registry, protocol definitions, and wiring boilerplate add ~200 LOC of infrastructure. **CRITICAL CONSTRAINT**: plugins return decision artefacts (blackboard deltas, `TransportPlan`, `RoutingDecision`), NEVER generators. All 5 yields stay in the engine core. This is the sync-only variant where Claude and Gemini converged in Step 1, rejecting ChatGPT's generator-factory delegation.

### ii) NEW INTERFACES

```python
# --- plugins/protocols.py ---
class TriagePlugin(Protocol):
    """Variant-specific triage. Returns decision via blackboard contract."""
    def assign_triage(
        self, casualty: Casualty, blackboard: BlackboardProtocol,
    ) -> None:
        """Write patient context to bb, tick internal decision logic,
        write decision keys. Engine reads IC-3 keys after return.
        Must be sync. Must not yield. Must not import simpy."""
        ...

class RoutingPlugin(Protocol):
    """Variant-specific routing policy."""
    def select_destination(
        self, casualty: Casualty, current_facility: str,
        network: TreatmentNetworkProtocol,
        facility_states: Dict[str, FacilitySnapshot],
    ) -> RoutingDecision:
        """Pure routing decision. Sync. No yields."""
        ...

class TransportPlugin(Protocol):
    """Variant-specific transport selection (EP-6 hook)."""
    def select_transport_mode(
        self, casualty: Casualty, from_id: str, to_id: str,
        network: TreatmentNetworkProtocol,
        rng: np.random.Generator,
    ) -> TransportPlan:
        """Select mode and compute travel time. Sync. No yields."""
        ...

class InjuryPlugin(Protocol):
    """Variant-specific casualty generation."""
    def generate_profile(self, rng: np.random.Generator) -> MISTProfile:
        """Generate MIST profile for this operational context."""
        ...

class PFCPlugin(Protocol):
    """Variant-specific PFC deterioration model (EP-3)."""
    def evaluate(
        self, casualty: Casualty, hold_duration: float,
        downstream_available: bool,
    ) -> HoldDecision:
        """PFC decision. Sync. No yields."""
        ...


# --- plugins/registry.py ---
@dataclass
class VariantPlugins:
    """Plugin bundle for a single FAER variant."""
    triage: TriagePlugin
    routing: RoutingPlugin
    transport: TransportPlugin
    injury: InjuryPlugin
    pfc: PFCPlugin
    context: str                    # "LSCO" | "HADR" | "HOSPITAL" | etc.

def load_variant(context: str, config: Dict) -> VariantPlugins:
    """Factory: loads plugins from config. EP-1 entry point."""
    ...


# --- plugins/military.py ---
class MilitaryTriagePlugin:
    """FAER-MIL: BT-based triage using py_trees."""
    def __init__(self, bt_tree, blackboard): ...
    def assign_triage(self, casualty, blackboard): ...

class MilitaryRoutingPlugin:
    """FAER-MIL: Forward chain with bypass logic."""
    def select_destination(self, casualty, current, network, states): ...


# --- plugins/hadr.py ---
class HADRTriagePlugin:
    """FAER-HADR: Simplified field triage (no BT, rule-based)."""
    def assign_triage(self, casualty, blackboard): ...

class HADRRoutingPlugin:
    """FAER-HADR: Hub-and-spoke with capacity balancing."""
    def select_destination(self, casualty, current, network, states): ...
```

### iii) ENGINE.PY SPLIT

| Block | Current LOC | Destination | Notes |
|---|---|---|---|
| Triage call site | ~50 | Engine calls `plugins.triage.assign_triage()` | ~5 LOC call |
| Routing logic | ~70 | `plugins.routing.select_destination()` | ~5 LOC call |
| PFC decision | ~60 (sync) | `plugins.pfc.evaluate()` | ~5 LOC call |
| Treatment yields | ~155 | **Stays in engine** | Y1+Y2 owned by engine |
| Hold/PFC yield loop | ~80 (yield portion) | **Stays in engine** (calls plugin for decision) | Y3 owned by engine |
| Transport yields | ~100 | **Stays in engine** | Y4+Y5 owned by engine |
| Casualty generation | ~50 | Engine calls `plugins.injury.generate_profile()` | ~5 LOC call |
| Metrics | ~62 | `metrics.py` | Same as S1 |
| Event emission | ~73 | `emitter.py` | Same as S1 |
| Plugin wiring | 0 | Engine `__init__` gains plugin registry | +30 LOC |
| **Final engine.py** | — | — | **~650 LOC** |

### iv) STATE OWNERSHIP

| Interface | Owner | Change from baseline |
|---|---|---|
| CP-1 (Blackboard) | **Plugins write/read** via `TriagePlugin.assign_triage()` | **DELEGATED to plugins but same contract shape** |
| CP-2 (EventBus) | `emitter.py` | Same as S1 |
| CP-3 (SimPy Resources) | **Engine exclusively** | **UNCHANGED — plugins never touch SimPy** |
| CP-4 (Topology) | `RoutingPlugin` reads, engine passes network reference | **Read access delegated, write access stays in engine** |

### v) MIGRATION SEQUENCE

| Step | Target | New LOC | Days | Iterations |
|---|---|---|---|---|
| 1 | Define plugin Protocols (`plugins/protocols.py`) | ~120 | 1 | 2 |
| 2 | Extract `MilitaryTriagePlugin` (wrap existing BT) | ~80 | 1 | 1 |
| 3 | Extract `MilitaryRoutingPlugin` (wrap existing logic) | ~100 | 1 | 2 |
| 4 | Extract `MilitaryTransportPlugin` + `MilitaryPFCPlugin` | ~150 | 1.5 | 2 |
| 5 | Build `VariantPlugins` + `load_variant()` + engine wiring | ~120 | 1 | 2 |
| 6 | S1 extractions (EX-2 metrics, EX-3 emitter) | ~405 | 2 | 4 |
| 7 | Build `HADRTriagePlugin` + `HADRRoutingPlugin` (EP-1 proof) | ~200 | 2 | 3 |
| 8 | Toggle-gated validation, legacy cleanup | ~100 | 1 | 2 |
| **Total** | | **~1,275** | **10.5-12** | **18** |

### vi) COMPONENT DIAGRAM

```
┌─────────────────────────────────────────────────┐
│                  SHARED SKELETON                 │
└────────────────────┬────────────────────────────┘
                     │
    ┌────────────────┴────────────────────┐
    │         Plugin Protocols            │
    │  TriagePlugin │ RoutingPlugin       │
    │  TransportPlugin │ PFCPlugin        │
    │  InjuryPlugin                       │
    └───┬─────────────────┬───────────────┘
        │                 │
┌───────▼──────┐  ┌───────▼──────┐
│ FAER-MIL     │  │ FAER-HADR    │
│ Military*    │  │ HADR*        │
│ Plugins      │  │ Plugins      │
│ (py_trees)   │  │ (rules)      │
└───────┬──────┘  └───────┬──────┘
        │  selected by     │
        │  OperationalContext
        ▼                  ▼
┌───────────────────────────────────┐
│         engine.py ~650 LOC        │
│  __init__(plugins: VariantPlugins)│
│                                   │
│  _patient_journey():              │
│    plugins.triage.assign()  sync  │
│    ──── Y1: resource.req() ────── │
│    ──── Y2: env.timeout()  ────── │
│    plugins.pfc.evaluate()   sync  │
│    ──── Y3: retry timeout  ────── │
│    plugins.routing.select() sync  │
│    ──── Y4: vehicle.req()  ────── │
│    ──── Y5: travel timeout ────── │
│    emit(DISPOSITION)              │
└───────────────────────────────────┘
```

---

## APPROACH S6: DETERMINISTIC COMMAND BUS (WILDCARD)

### i) THESIS

Optimises for **explicit control flow, replayability, and contested-environment modelling (EP-2)**. Decision modules emit immutable Command objects into a per-casualty command queue. A centralised Dispatcher executes commands as yield-bearing handlers. This makes the decide→enqueue→dispatch→yield→publish pipeline fully inspectable and interceptable. Trades away simplicity for power: the command/handler abstraction adds ~300 LOC of infrastructure and an indirection layer between decision and execution. The payoff is that commands can be inspected, modified, denied, or replayed before execution — making contested transport (EP-2) a first-class operation (deny a `BeginTransit` command) rather than a bolted-on edge check. Also natural for deterministic replay (HC-2): the command log IS the execution trace.

### ii) NEW INTERFACES

```python
# --- commands/models.py ---
@dataclass(frozen=True)
class Command:
    """Immutable action request. HC-4 compliant."""
    command_id: str                 # UUID
    casualty_id: str
    command_type: str
    created_at: float               # sim_time when decision was made

@dataclass(frozen=True)
class AcquireResource(Command):
    command_type: str = "ACQUIRE_RESOURCE"
    facility_id: str = ""
    department: str = ""

@dataclass(frozen=True)
class BeginTreatment(Command):
    command_type: str = "BEGIN_TREATMENT"
    facility_id: str = ""
    department: str = ""
    estimated_duration: float = 0.0

@dataclass(frozen=True)
class HoldRetry(Command):
    command_type: str = "HOLD_RETRY"
    facility_id: str = ""
    retry_interval: float = 0.0

@dataclass(frozen=True)
class AcquireVehicle(Command):
    command_type: str = "ACQUIRE_VEHICLE"
    from_facility: str = ""
    to_facility: str = ""
    transport_mode: str = ""

@dataclass(frozen=True)
class BeginTransit(Command):
    command_type: str = "BEGIN_TRANSIT"
    from_facility: str = ""
    to_facility: str = ""
    travel_time: float = 0.0

@dataclass(frozen=True)
class Dispose(Command):
    command_type: str = "DISPOSE"
    facility_id: str = ""
    outcome: str = ""


# --- commands/dispatcher.py ---
class CommandDispatcher:
    """Centralised yield executor. ONLY module that touches CP-3.
    Owns all 5 yield points.
    """
    def __init__(
        self,
        env: simpy.Environment,
        resources: Dict[str, simpy.Resource],
        emitter: EventEmitter,
        interceptors: List[CommandInterceptor],   # EP-2 hook
    ): ...

    def dispatch(self, command: Command, casualty: Casualty) -> Generator:
        """Execute a single command as a SimPy yield sequence.
        Returns after yields complete.
        """
        for interceptor in self.interceptors:
            command = interceptor.intercept(command, casualty)
            if command is None:
                return  # command denied (EP-2: contested transport)
        handler = self._handlers[command.command_type]
        yield from handler(command, casualty)


# --- commands/interceptors.py ---
class CommandInterceptor(Protocol):
    """Inspects/modifies/denies commands before execution. EP-2 hook."""
    def intercept(
        self, command: Command, casualty: Casualty,
    ) -> Optional[Command]:
        """Return modified command, or None to deny execution."""
        ...

class ContestedRouteInterceptor:
    """EP-2: Denies BeginTransit commands on contested routes."""
    def __init__(self, network: TreatmentNetworkProtocol, rng: np.random.Generator): ...
    def intercept(self, command, casualty):
        if isinstance(command, BeginTransit):
            if self.network.is_route_denied(command.from_facility,
                                            command.to_facility, self.rng):
                return None  # DENIED
        return command

class ConsumableInterceptor:
    """EP-7: Checks resource availability before treatment."""
    def intercept(self, command, casualty):
        if isinstance(command, BeginTreatment):
            if not self.consumable_store.has_required(command.department):
                return None  # STOCKOUT
        return command


# --- commands/log.py ---
class CommandLog:
    """Append-only command history. Deterministic replay source (HC-2)."""
    def __init__(self): ...
    def append(self, command: Command, outcome: str) -> None: ...
    def replay_to(self, time: float) -> List[Command]: ...
```

### iii) ENGINE.PY SPLIT

| Block | Current LOC | Destination | Notes |
|---|---|---|---|
| Triage logic | ~50 | `policies/triage_policy.py` (emits no commands, writes BB) | Sync, same as S5 |
| Routing logic | ~70 | `policies/routing_policy.py` (emits `AcquireVehicle` + `BeginTransit`) | Sync decision, commands created |
| PFC evaluation | ~60 | `policies/pfc_policy.py` (emits `HoldRetry` commands) | Sync decision |
| Treatment decision | ~42 | `policies/treatment_policy.py` (emits `AcquireResource` + `BeginTreatment`) | Sync decision |
| **All yield execution** | ~400 | `commands/dispatcher.py` handlers | **Y1-Y5 centralised** |
| Metrics | ~62 | `metrics.py` | Same as S1 |
| Event emission | ~73 | `emitter.py` (called by dispatcher after yields) | Same as S1 |
| **engine.py becomes orchestrator** | — | — | **~80 LOC loop** |

The orchestrator loop:
```pseudo
def _patient_journey(env, cas, policies, dispatcher):
    emit(ARRIVAL, cas)
    policies.triage.decide(cas, bb)   # sync, writes BB
    while cas.state != TERMINAL:
        cmds = policies.treatment.plan(cas, facility)
        for cmd in cmds:
            yield from dispatcher.dispatch(cmd, cas)
        cmds = policies.pfc.evaluate(cas, hold_state)
        for cmd in cmds:
            yield from dispatcher.dispatch(cmd, cas)
        cmds = policies.routing.plan(cas, current)
        for cmd in cmds:
            yield from dispatcher.dispatch(cmd, cas)
    emit(DISPOSITION, cas)
```

### iv) STATE OWNERSHIP

| Interface | Owner | Change from baseline |
|---|---|---|
| CP-1 (Blackboard) | Policies write/read (same contract) | **DELEGATED to policies** |
| CP-2 (EventBus) | Dispatcher calls emitter after each handler completes | **Emission coupled to command completion, not inline** |
| CP-3 (SimPy Resources) | **Dispatcher exclusively** | **CENTRALISED in dispatcher handlers. Policies forbidden from CP-3 access.** |
| CP-4 (Topology) | `routing_policy.py` reads network | **Same as S5** |
| **NEW: Command Log** | `commands/log.py` | **Every command + outcome persisted. Full replay source.** |

### v) MIGRATION SEQUENCE

| Step | Target | New LOC | Days | Iterations |
|---|---|---|---|---|
| 1 | Define Command dataclasses | ~150 | 1 | 2 |
| 2 | Build Dispatcher scaffold + treatment handler (Y1+Y2) | ~200 | 2 | 3 |
| 3 | Build hold/PFC handler (Y3) | ~150 | 1.5 | 2 |
| 4 | Build transport handler (Y4+Y5) | ~150 | 1.5 | 2 |
| 5 | Extract triage + routing + PFC policies | ~250 | 2 | 3 |
| 6 | Build orchestrator loop (new engine.py) | ~80 | 1 | 1 |
| 7 | `ContestedRouteInterceptor` (EP-2 proof) | ~80 | 1 | 1 |
| 8 | `CommandLog` + replay verification (HC-2) | ~120 | 1 | 2 |
| 9 | S1 extractions (metrics, emitter) | ~405 | 2 | 4 |
| 10 | Toggle-gated migration, legacy cleanup | ~100 | 1 | 2 |
| **Total** | | **~1,685** | **14-15** | **22** |

### vi) COMPONENT DIAGRAM

```
┌─────────────────────────────────────────────────┐
│                  SHARED SKELETON                 │
└────────────────────┬────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │       POLICIES          │
        │  (sync, no SimPy)       │
        │                         │
        │  triage_policy.py       │
        │  routing_policy.py      │──► emits Commands
        │  treatment_policy.py    │
        │  pfc_policy.py          │
        └────────────┬────────────┘
                     │ Command objects (frozen)
                     ▼
        ┌────────────────────────────────────────┐
        │  ┌──────────────────────────────────┐  │
        │  │     INTERCEPTOR CHAIN (EP-2)     │  │
        │  │  ContestedRouteInterceptor       │  │
        │  │  ConsumableInterceptor (EP-7)    │  │
        │  └──────────────┬───────────────────┘  │
        │                 │                      │
        │  ┌──────────────▼───────────────────┐  │
        │  │     DISPATCHER ~200 LOC          │  │
        │  │                                  │  │
        │  │  handle_acquire_resource: Y1     │  │
        │  │  handle_begin_treatment:  Y2     │  │ ◄── CP-3: ONLY HERE
        │  │  handle_hold_retry:       Y3     │  │
        │  │  handle_acquire_vehicle:  Y4     │  │
        │  │  handle_begin_transit:    Y5     │  │
        │  └──────────────┬───────────────────┘  │
        │      COMMAND BUS                       │
        └─────────────────┬──────────────────────┘
                          │ publishes
                          ▼
        ┌─────────────────────────────────────┐
        │  EventBus (CP-2) + CommandLog       │
        └─────────────────────────────────────┘

        ┌─────────────────────────────────────┐
        │  ORCHESTRATOR (engine.py ~80 LOC)   │
        │  for each casualty:                 │
        │    policies.decide() → commands     │
        │    yield from dispatcher.dispatch() │
        └─────────────────────────────────────┘
```

---

## COMPARISON MATRIX

| Criterion | S1 Minimalist | S2 Strangler | S3 A+E | S4 Func Core | S5 Plugin Hex | S6 Cmd Bus |
|---|---|---|---|---|---|---|
| **engine.py final LOC** | ~800 | ~500 | ~730 | eliminated | ~650 | ~80 |
| **Total iterations** | 12 | 24 | 21 | 18 | 18 | 22 |
| **Days to parity** | 4.5-5.5 | 9-10 | 9-10 | 11-12 | 10.5-12 | 14-15 |
| **Yield ownership** | all in engine | delegated via yield from | all in engine | all in shell | all in engine | all in dispatcher |
| **EP-1 variant family** | ✗ no structural support | ✗ same | ✗ same | ◐ swappable planner | ✓ plugin protocol | ◐ swappable policies |
| **EP-2 contested transport** | manual edge check | manual edge check | manual edge check | manual check in planner | manual check in plugin | ✓ interceptor chain |
| **EP-5 alt BT/ML** | manual swap | manual swap | manual swap | ✓ swap planner impl | ✓ swap TriagePlugin | ◐ swap triage policy |
| **EP-7 consumables** | engine modification | engine modification | ✓ EventBus subscriber | emitter modification | engine modification | ✓ interceptor |
| **Unit testability** | moderate | moderate | moderate + analytics | ✓ excellent (pure core) | good (plugins testable) | good (policies testable) |
| **Risk** | LOWEST | LOW | LOW | MEDIUM | MEDIUM | MEDIUM-HIGH |
| **EC-1 (≤2 weeks)** | ✓ easily | ✓ Phase 1 only | ✓ Phase 1 only | ◐ tight | ◐ tight | ✗ likely exceeds |
| **EC-6 (≤4,508 LOC)** | ✓ ~4,800 | ◐ ~4,200 steady | ✓ ~4,600 | ✓ ~4,100 | ✓ ~4,400 | ◐ ~4,900 |
