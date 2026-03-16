# FAER DSE: Demo Notebook Plan & Phases
## From Architecture Decision to Executable Proof

---

## Rationale

The DSE produced an architecture recommendation. Notebooks are how that recommendation becomes verified truth — the same way NB32 proved the kernel primitive and NB31 proved migration cost. Every phase gate below requires a notebook that PROVES the migration step works before the production code is touched.

This follows the established FAER methodology:
- **Notebook-first validation:** prove in NB, then extract to production (Lessons §8)
- **50-100 LOC iterations:** each notebook validates one extraction step
- **Fixed-seed comparison:** every NB must demonstrate identical output before/after

---

## Notebook Numbering Convention

NB30-32 are already taken (engine DNA, NB31 MIST migration, NB32 kernel primitive). The DSE notebooks continue the sequence.

| NB# | Phase | Purpose |
|-----|-------|---------|
| NB33 | Pre-Phase 1 | DSE Decision Record — architecture choice documented |
| NB34 | Phase 1 | EX-1 Routing Extraction Proof |
| NB35 | Phase 1 | EX-2 Metrics Extraction Proof |
| NB36 | Phase 1 | EX-3 Typed Emitter Proof + K-7 Closure |
| NB37 | Phase 1 | Pattern E Analytics Decoupling Proof |
| NB38 | Phase 1 | EX-4 PFC Sync Decision Extraction Proof |
| NB39 | Phase 1 | Phase 1 Integration Gate — Full Regression |
| NB40 | Phase 2 | Plugin Protocol Design Proof |
| NB41 | Phase 2 | EX-5 Treatment Yield Delegation Proof |
| NB42 | Phase 2 | HADR Variant Proof (EP-1) |
| NB43 | Phase 3 | EX-6 Hold/PFC Loop Extraction Proof (if needed) |
| NB44 | Phase 3 | `yield from` Exception Safety Proof |

---

## Phase 0: Decision Record (NB33)

### NB33 — DSE Architecture Decision Record

**Purpose:** Formalise the "Tidy, Decouple, Then Plug" decision as an executable document. This is the ADR that future notebooks reference. Not a demo — a stake in the ground.

**Contents:**
1. Architecture choice statement (1 paragraph)
2. The 5 yield points with current module owners (table)
3. The 6 extraction targets with risk ratings and phase assignments (table)
4. Exit criteria (EC-1 through EC-7) with current status
5. NB32 acceptance test trace through the FINAL recommended architecture (pseudocode)
6. Hard constraint checklist (HC-1 through HC-10, each verified)
7. Debt map: K-1 through K-8, resolved/inherited per phase
8. Open questions (OQ-1 through OQ-5) from the DSE

**Estimated LOC:** ~100 (markdown + tables + one pseudocode cell)
**Dependencies:** NB30, NB32, Context Index, this DSE output
**Validation:** Peer review (Ross signs off that the ADR matches intent)

---

## Phase 1: Tidy + Decouple (Weeks 1-2)

### NB34 — EX-1 Routing Extraction Proof

**Purpose:** Prove that `_get_next_destination()` and ATMIST generation can be extracted from engine.py into `routing.py` without changing simulation output.

**Demo structure:**
1. **Cell 1-2:** Load current engine. Run NB32 acceptance test (20 casualties, 3-node contested chain, seed=42). Capture full event log + per-casualty outcomes as BASELINE.
2. **Cell 3-4:** Define `routing.py` module inline:
   ```python
   @dataclass
   class RoutingDecision:
       next_facility: Optional[str]
       travel_time: float
       is_denied: bool

   def get_next_destination(casualty, current, network, rng) -> RoutingDecision:
       # Extracted logic from engine.py lines XXX-YYY
       ...
   ```
3. **Cell 5:** Monkey-patch engine to call `routing.get_next_destination()` instead of inline code. Re-run with seed=42.
4. **Cell 6:** REGRESSION CHECK — compare event logs. Assert identical triage distribution, identical per-casualty outcomes, identical event counts. Zero tolerance.
5. **Cell 7:** TOGGLE PROOF — show `SimulationToggles.use_extracted_routing` flag, demonstrate old path / new path switching.

**Estimated LOC:** ~200 (extraction ~70, test scaffold ~130)
**Risk:** LOW (EX-1 is zero-yield, pure function)
**Success criterion:** Event log diff = 0 events different. Per-casualty outcome diff = 0.

---

### NB35 — EX-2 Metrics Extraction Proof

**Purpose:** Prove that `get_metrics()` (~62 LOC) can be extracted from engine.py into `metrics.py` as a pure aggregation function over EventStore.

**Demo structure:**
1. **Cell 1-2:** Run NB32 scenario. Capture `engine.get_metrics()` output as BASELINE.
2. **Cell 3-4:** Define `metrics.py` module inline:
   ```python
   @dataclass(frozen=True)
   class SimulationMetrics:
       triage_distribution: Dict[str, int]
       mean_wait_time: float
       mean_transit_time: float
       mean_treatment_time: float
       facility_utilisation: Dict[str, float]

   def compute_metrics(event_store) -> SimulationMetrics:
       ...
   ```
3. **Cell 5:** Compare `engine.get_metrics()` vs `metrics.compute_metrics(event_store)`. Assert identical values.
4. **Cell 6:** Toggle proof.

**Estimated LOC:** ~180 (extraction ~62, test scaffold ~120)
**Risk:** LOW (EX-2 is zero-yield, read-only)
**Success criterion:** Metrics values identical within floating-point tolerance.

---

### NB36 — EX-3 Typed Emitter Proof + K-7 Closure

**Purpose:** Prove that replacing `_log_event(dict)` with a typed `EventEmitter` protocol produces identical events with populated typed fields. This closes K-7.

**Demo structure:**
1. **Cell 1-2:** Run NB32. Capture all events via legacy `_log_event()`. Show that typed fields (e.g., `SimEvent.triage_category`) are empty/default in current production events.
2. **Cell 3-4:** Define `emitter.py` protocol inline:
   ```python
   class EventEmitter(Protocol):
       def emit_arrival(self, cas, facility_id, sim_time) -> None: ...
       def emit_triage(self, cas, facility_id, sim_time) -> None: ...
       def emit_treatment_complete(self, cas, facility_id, dept, sim_time) -> None: ...
       def emit_disposition(self, cas, facility_id, sim_time) -> None: ...
       # ... all event types

   class TypedEmitter:
       """Concrete implementation publishing frozen SimEvent dataclasses."""
       def __init__(self, event_log: EventLog): ...
       def emit_arrival(self, cas, facility_id, sim_time):
           self.event_log.publish(SimEvent(
               sim_time=sim_time,
               event_type="ARRIVAL",
               casualty_id=cas.id,
               facility_id=facility_id,
           ))
   ```
3. **Cell 5:** Wire TypedEmitter into engine. Re-run with seed=42.
4. **Cell 6:** REGRESSION CHECK — event count identical. Event ordering identical.
5. **Cell 7:** K-7 CLOSURE CHECK — show that typed fields are now populated:
   ```python
   for event in log.events:
       if event.event_type == "TRIAGED":
           assert event.detail != ""  # was empty before, now populated
   ```
6. **Cell 8:** DISPOSITION INVARIANT (KL-6):
   ```python
   arrivals = len([e for e in log.events if e.event_type == "ARRIVAL"])
   dispositions = len([e for e in log.events if e.event_type == "DISPOSITION"])
   assert arrivals == dispositions == 20
   ```

**Estimated LOC:** ~250 (emitter protocol ~80, typed impl ~100, tests ~70)
**Risk:** MEDIUM (changes every emit call site in engine.py)
**Success criterion:** All typed fields populated. Event count identical. DISPOSITION == ARRIVAL.

---

### NB37 — Pattern E Analytics Decoupling Proof

**Purpose:** Prove that an AnalyticsEngine subscribing to EventBus can compute the same metrics as the current inline `get_metrics()`, and that the dashboard can read views instead of engine state.

**Demo structure:**
1. **Cell 1-2:** Run NB32 with TypedEmitter (from NB36). Capture `metrics.compute_metrics()` output as BASELINE.
2. **Cell 3-5:** Define AnalyticsEngine:
   ```python
   class AnalyticsEngine:
       def __init__(self, event_bus):
           event_bus.subscribe(self._on_event)
           self.golden_hour = GoldenHourView()
           self.survivability = SurvivabilityView()

       def _on_event(self, event):
           self.golden_hour.update(event)
           self.survivability.update(event)

       def get_view(self, name):
           return self.views[name].snapshot()
   ```
3. **Cell 6:** Compare `metrics.compute_metrics()` vs `analytics.get_view("metrics")`. Assert equivalent.
4. **Cell 7:** PERFORMANCE CHECK — measure time overhead of subscriber callbacks per event. Target: <1ms/event.
5. **Cell 8:** OOM CHECK — run 1,000 casualties. Monitor memory. Verify AnalyticsEngine memory is O(views) not O(events).

**Estimated LOC:** ~300 (analytics engine ~150, views ~100, tests ~50)
**Risk:** LOW-MEDIUM (new infrastructure, but CP-2 is lowest-cost boundary)
**Success criterion:** Metrics equivalent. Overhead <1ms/event. Memory bounded.

---

### NB38 — EX-4 PFC Sync Decision Extraction Proof

**Purpose:** Prove that the synchronous decision portion of the PFC hold logic (~60 LOC of the 111 LOC EX-4) can be extracted as a pure function while the yield loop stays in engine.py.

**Demo structure:**
1. **Cell 1-2:** Run NB32 scenario WITH a topology that triggers PFC holds (add capacity constraints so downstream becomes unavailable). Capture PFC event sequence as BASELINE.
2. **Cell 3-4:** Define `pfc.py` inline:
   ```python
   class PFCAction(Enum):
       CONTINUE_HOLD = "CONTINUE_HOLD"
       ESCALATE_PFC = "ESCALATE_PFC"
       RELEASE = "RELEASE"

   def evaluate_pfc(casualty, hold_duration, downstream_available, threshold) -> PFCAction:
       if downstream_available:
           return PFCAction.RELEASE
       if hold_duration > threshold:
           return PFCAction.ESCALATE_PFC
       return PFCAction.CONTINUE_HOLD
   ```
3. **Cell 5:** Patch engine to call `pfc.evaluate_pfc()` inside the hold loop. Re-run with seed=42.
4. **Cell 6:** REGRESSION CHECK — identical PFC event sequence. Identical hold durations.
5. **Cell 7:** UNIT TEST — test `evaluate_pfc()` with synthetic inputs. No SimPy required.
   ```python
   assert evaluate_pfc(cas, 10.0, True, 30.0) == PFCAction.RELEASE
   assert evaluate_pfc(cas, 45.0, False, 30.0) == PFCAction.ESCALATE_PFC
   assert evaluate_pfc(cas, 10.0, False, 30.0) == PFCAction.CONTINUE_HOLD
   ```

**Estimated LOC:** ~200 (extraction ~60, PFC-triggering scenario ~80, tests ~60)
**Risk:** MEDIUM (EX-4 touches PFC path, but only sync decision portion)
**Success criterion:** PFC events identical. Pure function passes unit tests without SimPy.

---

### NB39 — Phase 1 Integration Gate

**Purpose:** Full regression test of ALL Phase 1 extractions running together. This is the go/no-go gate for Phase 1 completion.

**Demo structure:**
1. **Cell 1:** Load engine with ALL Phase 1 toggles ON:
   - `use_extracted_routing = True`
   - `use_extracted_metrics = True`
   - `use_typed_emitter = True`
   - `use_extracted_pfc = True`
2. **Cell 2:** Run NB32 acceptance test (20 casualties, seed=42). Full comparison against pre-Phase-1 baseline.
3. **Cell 3:** Run 1,000 casualties, seed=42. Distribution comparison:
   ```python
   triage_diff = abs(new_triage_dist - baseline_triage_dist)
   assert all(triage_diff < 0.05)  # MC-3: ±5% tolerance
   ```
4. **Cell 4:** Run 5,000 casualties. Memory profile. Verify no OOM.
5. **Cell 5:** Deterministic replay (HC-2): Run twice with seed=42, assert identical.
6. **Cell 6:** engine.py LOC count. Assert ≤ 850 (target ~800).
7. **Cell 7:** Debt closure checklist:
   ```
   K-3 (legacy triage dead code): CLOSED ✓
   K-7 (typed fields empty): CLOSED ✓
   K-1 (monolith): REDUCED (1,309 → ~800) ✓
   ```
8. **Cell 8:** Phase 1 EXIT CRITERIA summary table.

**Estimated LOC:** ~150 (test scaffold only)
**Risk:** LOW (integration of already-proven extractions)
**Success criterion:** All assertions pass. All EC verified. Decision: GO/NO-GO for Phase 2.

---

## Phase 2: Plug (Weeks 3-6, Conditional on HADR)

### NB40 — Plugin Protocol Design Proof

**Purpose:** Prove that Phase 1 pure function signatures can be mechanically wrapped in Plugin Protocols, and that Military plugin implementations pass the same acceptance test.

**Demo structure:**
1. **Cell 1-3:** Define Plugin Protocols derived FROM Phase 1 signatures:
   ```python
   class TriagePlugin(Protocol):
       def assign_triage(self, casualty, blackboard) -> None: ...

   class RoutingPlugin(Protocol):
       def select_destination(self, casualty, current, network, snapshot) -> RoutingDecision: ...

   class PFCPlugin(Protocol):
       def evaluate(self, casualty, hold_duration, downstream) -> HoldDecision: ...
   ```
2. **Cell 4-5:** Wrap Phase 1 functions as MilitaryPlugins:
   ```python
   class MilitaryRoutingPlugin:
       def select_destination(self, casualty, current, network, snapshot):
           return routing.get_next_destination(casualty, current, network, self.rng)
   ```
3. **Cell 6:** Wire plugins into engine. Run NB32 acceptance test.
4. **Cell 7:** REGRESSION CHECK — identical output to Phase 1 engine.
5. **Cell 8:** PROTOCOL CONFORMANCE — verify plugins satisfy Protocol type checks:
   ```python
   assert isinstance(MilitaryRoutingPlugin(), RoutingPlugin)
   ```

**Estimated LOC:** ~250 (protocols ~120, military wrappers ~80, tests ~50)
**Risk:** MEDIUM (new abstraction layer, but wrapping proven functions)
**Success criterion:** MilitaryPlugins produce identical output. Protocol conformance verified.

---

### NB41 — EX-5 Treatment Yield Delegation Proof

**Purpose:** Prove that treatment yields (Y1+Y2) can be safely delegated to a `treatment.py` sub-generator via `yield from` without breaking resource semantics or determinism.

**Demo structure:**
1. **Cell 1-2:** Run NB32 with Phase 1+Plugin engine. Capture BASELINE.
2. **Cell 3-5:** Define `treatment.py` sub-generator:
   ```python
   def treat_patient(ctx, casualty):
       resource = ctx.resources[ctx.facility_id]
       with resource.request() as req:
           queue_start = ctx.env.now
           yield req                    # Y1 — now owned by treatment.py
           casualty.total_wait_time += ctx.env.now - queue_start
           duration = ctx.rng.exponential(...)
           yield ctx.env.timeout(duration)  # Y2 — now owned by treatment.py
           casualty.total_treatment_time += duration
           ctx.emitter.emit_treatment_complete(...)
   ```
3. **Cell 6:** Wire via `yield from treatment.treat_patient(ctx, cas)` in engine.
4. **Cell 7:** REGRESSION CHECK — identical output.
5. **Cell 8:** EXCEPTION SAFETY TEST (F-TECH-1):
   ```python
   # Deliberately raise during Y1. Verify resource is released.
   # Deliberately raise during Y2. Verify resource is released.
   ```
6. **Cell 9:** RESOURCE ACCOUNTING — verify resource.count and resource.queue are identical at every time step.

**Estimated LOC:** ~350 (treatment module ~155, exception tests ~100, comparison ~95)
**Risk:** MEDIUM-HIGH (first yield delegation, CP-3 boundary crossing)
**Success criterion:** Output identical. Resource accounting identical. Exception safety proven.

---

### NB42 — HADR Variant Proof (EP-1)

**Purpose:** Prove that a FAER-HADR variant can be created by implementing new Plugin instances without modifying engine.py or the 11-file kernel.

**Demo structure:**
1. **Cell 1-3:** Define HADR plugins:
   ```python
   class HADRTriagePlugin:
       """Simplified field triage. No BT — rule-based severity threshold."""
       def assign_triage(self, casualty, blackboard): ...

   class HADRRoutingPlugin:
       """Hub-and-spoke. Capacity balancing across aid stations."""
       def select_destination(self, casualty, current, network, snapshot): ...
   ```
2. **Cell 4:** Define HADR topology (different from MIL: hub-and-spoke, no contested links).
3. **Cell 5:** Load HADR variant:
   ```python
   plugins = load_variant("HADR", hadr_config)
   engine = FAEREngine(seed=42, plugins=plugins)
   engine.build_network(hadr_topology)
   ```
4. **Cell 6:** Run 20 casualties. Verify events, triage distribution, survivability.
5. **Cell 7:** Run MILITARY variant with same seed. Verify DIFFERENT outputs (proving variant divergence is real).
6. **Cell 8:** Verify engine.py was NOT modified. Verify 11-file kernel was NOT modified.
7. **Cell 9:** COST ACCOUNTING — count LOC added for HADR variant. Target: <300 LOC total.

**Estimated LOC:** ~300 (HADR plugins ~200, HADR config ~50, tests ~50)
**Risk:** MEDIUM (first real variant, tests plugin architecture under load)
**Success criterion:** HADR runs successfully. Engine untouched. <300 LOC for full variant.

---

## Phase 3: Delegate (Weeks 7-12, Only If Needed)

### NB43 — EX-6 Hold/PFC Loop Extraction Proof

**Purpose:** Prove that the 140 LOC hold/PFC retry loop can be extracted into a `hold_pfc.py` sub-generator via `yield from` without breaking the nested conditional semantics.

**Demo structure:**
1. **Cell 1-2:** Build a scenario that HEAVILY exercises PFC: high casualty volume, constrained downstream, extended holds. Capture detailed PFC event timeline as BASELINE.
2. **Cell 3-5:** Extract `hold_and_check_pfc()` as a sub-generator owning Y3.
3. **Cell 6:** REGRESSION CHECK — PFC event timeline identical.
4. **Cell 7:** 10,000-casualty fixed-seed comparison (MC-3: ±5% tolerance).
5. **Cell 8:** Exception safety for nested `with` blocks.

**Estimated LOC:** ~400 (extraction ~140 × 3 MC-1, tests ~180)
**Risk:** HIGH (KF-5: most complex extraction in the kernel)
**Gate:** Only proceed if NB41 (EX-5) succeeded AND NB39 (Phase 1 gate) is clean.

---

### NB44 — `yield from` Exception Safety Proof

**Purpose:** Prove, with minimal reproduction, that `yield from` delegation into sub-generators preserves SimPy Resource cleanup semantics under all failure modes.

**Demo structure:**
1. **Cell 1:** Minimal SimPy setup: 1 resource, 2 processes competing.
2. **Cell 2:** Sub-generator acquires resource, yields, raises exception during hold.
3. **Cell 3:** Verify resource is released (not leaked) despite exception.
4. **Cell 4:** Sub-generator acquires resource, yields, calling generator throws into it.
5. **Cell 5:** Verify resource is released.
6. **Cell 6:** Sub-generator acquires resource, calling generator is garbage collected.
7. **Cell 7:** Verify resource is released.
8. **Cell 8:** Document findings for F-TECH-1 resolution.

**Estimated LOC:** ~150 (pure SimPy tests, no FAER dependencies)
**Risk:** LOW (isolated proof, no production code)
**Recommendation:** Build this BEFORE NB41 (EX-5). It de-risks all yield delegation work.

---

## Summary: Notebook Sequence and Dependencies

```
NB33 (ADR)
  │
  ├── NB34 (EX-1 routing) ──┐
  ├── NB35 (EX-2 metrics) ──┤
  ├── NB36 (EX-3 emitter) ──┤── NB39 (Phase 1 Gate)
  ├── NB37 (analytics) ──────┤       │
  └── NB38 (EX-4 pfc sync) ─┘       │
                                      │
                              NB44 (yield from safety) ← build EARLY
                                      │
                              NB40 (plugin protocols) ──┐
                              NB41 (EX-5 treatment) ────┤── NB42 (HADR variant)
                                                        │
                                                NB43 (EX-6 hold/PFC) ← PHASE 3, GATED
```

## Phase Gates

| Gate | Notebook | Criteria | Decision |
|------|----------|----------|----------|
| Phase 1 Entry | NB33 | ADR signed off | GO |
| Phase 1 Exit | NB39 | All assertions pass, K-3 closed, K-7 closed, engine ≤850 LOC | GO/PAUSE |
| Phase 2 Entry | NB40 | Plugin protocols wrap Phase 1 functions identically | GO |
| Phase 2 Exit | NB42 | HADR variant runs, engine untouched, <300 LOC variant cost | GO/PAUSE |
| Phase 3 Entry | NB44 + NB41 | yield from exception safety proven, EX-5 regression clean | GO |
| Phase 3 Exit | NB43 | 10,000-casualty fixed-seed comparison within ±5% | DONE |

---

## Effort Estimates

| Phase | Notebooks | Total LOC (approx) | Calendar Days | Iterations (50-100 LOC) |
|-------|-----------|--------------------:|:-------------:|:-----------------------:|
| 0 | NB33 | ~100 | 0.5 | 1 |
| 1 | NB34-39 | ~1,280 | 8-10 | 12-15 |
| 2 | NB40-42, NB44 | ~1,050 | 8-12 | 10-12 |
| 3 | NB43 | ~400 | 4-6 | 5-6 |
| **Total** | **12 notebooks** | **~2,830** | **~20-28** | **~28-34** |

Phase 1 is the commitment. Phase 2 is conditional on HADR. Phase 3 is conditional on Phase 2 proving insufficient at engine.py ~650 LOC. The fallback at any point is pure Pattern D: stop extracting, keep what you have, the engine still works.
