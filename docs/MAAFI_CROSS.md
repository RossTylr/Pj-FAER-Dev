# MAAFI CROSS — Feature Interaction Map (FAER-MIL, layer-aware)

**Agent:** Cross (feature-to-feature dependencies, synergies, conflicts)
**Date:** 2026-06-17
**Method:** Static trace + one real run (`build_engine_from_preset("coin", seed=42)`, 1440 min, 200 cap → 258 events). Every claim carries a `file:line`.
**Builds on:** [MAAFI_FORWARD.md](MAAFI_FORWARD.md), [MAAFI_BACKWARD.md](MAAFI_BACKWARD.md).

**Interaction types:** INTRINSIC×INTRINSIC (mechanism coupling — highest impact), INTRINSIC×SURFACE (surface wraps intrinsic → ordering constraint), SURFACE×SURFACE (usually independent).

---

## TOP CROSS FINDINGS (read first)

1. **The master ordering law holds with zero exceptions (C13):** every SURFACE feature traces to ≥1 INTRINSIC dependency that is currently *dormant or phantom*. No surface feature can rank above its intrinsic prerequisite. The four load-bearing intrinsics — **#5 capability routing, #1 multi-POI, #10 threat, #31-33 PFC** — gate 14 of the 20 surface features.
2. **Routing blast radius is tiny (C1):** `get_next_destination()` has exactly **one live consumer** — the engine journey loop ([engine.py:681,686](../src/faer_dev/simulation/engine.py#L681)). #5 capability routing is a localised change, not a cascade. The risk is *determinism* (it adds a facility-attribute read inside the hot loop), not breadth.
3. **The blackboard is the silent fault line (C2, C10, C11):** the facility/department key group is **structurally present, write-never-read, and has no engine writer**. #4 departments, #53 Engine Room, #58 weather, and #35-39 consumables all need the same missing piece — an **engine→blackboard writer**, not new keys. This is a single shared prerequisite masquerading as five separate features.
4. **DCS is a fully-wired phantom loop (C4):** `build_dcs_tree` writes `decision_dcs`, `requires_dcs` is computed and stored, the `DCS` event type is declared — **and none of it connects**. The tree is never ticked, the event never emits, `requires_dcs` only steers department selection. #28 is "done" but unobservable and unverifiable.
5. **MNEMOSYNE export (#62) maps ~3 of 9 survival-schema fields directly (C12):** `severity`, `triage`, `mechanism` are on events; `primary_region`, `r1_capacity_pct`, `route_threat_level`, `survival` are **absent**, and `pfc_duration` is phantom in the default run. The export is gated on intrinsic work, not serialisation work.

---

## C1. ROUTING CONSUMER TRACE — blast radius of capability-aware routing

`routing.py` public surface: `triage_decisions()`, `get_next_destination()`, `_find_highest_reachable()` (private). Live `src/` consumers (grep of `_extracted_get_next_destination` / `_extracted_triage_decisions`):

| Consumer | Site | Tag | Notes |
|---|---|---|---|
| Engine journey loop — `get_next_destination` | [engine.py:681](../src/faer_dev/simulation/engine.py#L681) (extracted) / [:686](../src/faer_dev/simulation/engine.py#L686) (legacy fallback) | **INTRINSIC** | The **only** behavioural consumer. Called once per echelon hop. |
| Engine journey loop — `triage_decisions` | [engine.py:655](../src/faer_dev/simulation/engine.py#L655) | **INTRINSIC** | Sets `patient.bypass_role1` / `requires_dcs`. |
| `_find_highest_reachable` | internal to `get_next_destination` (graph mode) | INTRINSIC | The exact #5 plug-in point ([routing.py:88-96](../src/faer_dev/routing.py#L88)). |
| Demo X-ray / architecture panels | [xray_panel.py:35](../demo_app/components/xray_panel.py#L35), [state_helpers.py:121](../demo_app/components/state_helpers.py#L121), [5_architecture.py:73](../demo_app/pages/5_architecture.py#L73) | **SURFACE** | String-label / LOC-counter references only — they name `"routing.py"`, they do not call it. Zero behavioural coupling. |
| Tests | `test_routing.py` (24), regression | test | Seed-matched OFF↔ON. |

**Blast radius verdict:** **narrow.** One intrinsic call-site. #5 capability filtering drops into `_find_highest_reachable` (graph mode) and the legacy role-walk inner loop ([routing.py:144-148](../src/faer_dev/routing.py#L144)) — both already hold the `Facility` object (`network.facilities[fac_id]`), so `fac.has_surgery` etc. are in hand with **no new plumbing**. The surface panels are immune. The real coupling is **C5/determinism** (a new attribute read inside the routing loop must not perturb RNG draw order — it won't, routing is pure/RNG-free per [routing.py:11-14](../src/faer_dev/routing.py#L11)) and the **R16a acceptance gate** ("no surgical casualty treated at non-surgical facility"), which only becomes assertable once this read exists.

---

## C2. BLACKBOARD CAPACITY vs POPULATION — capacity is fine, population is missing

Forward F11 confirmed: the 6 facility keys (`facility_utilisation, facility_beds_available, department_queue_depth, department_capacity, fst_queue_depth, r1_beds_available`, [blackboard.py:28-35](../src/faer_dev/decisions/blackboard.py#L28)) are registered but **the engine never calls `set_facility_context()`** — grep of `src/` shows the only `.set` on facility keys is the constructor default ([blackboard.py:96](../src/faer_dev/decisions/blackboard.py#L96)).

**Diagnosis: this is a POPULATION problem, not a capacity problem.** Adding key groups is a ~5-line dict merge into `ALL_KEYS` ([blackboard.py:65](../src/faer_dev/decisions/blackboard.py#L65)). What is missing is a **writer that runs each tick**.

| Feature | Capacity (new keys)? | Population (engine writer)? |
|---|---|---|
| **#4 departments** | ❌ none needed — `department_queue_depth`/`department_capacity` already exist | ✅ **required** — wire `FacilityInternalGraph.get_queue_depths()` / `get_capacities()` ([departments.py:96-108](../src/faer_dev/simulation/departments.py#L96)) into a per-tick `set()` |
| **#58 weather** | ✅ needs a `_WEATHER_KEYS` group | ✅ plus an engine writer + a consumer (BT/transport) |
| **#35-39 consumables** | ✅ needs `_CONSUMABLE_KEYS` (blood/kit/oxygen counts) | ✅ plus a `ConsumableManager` writer — module does not exist (Forward F1) |

**What would feed the existing department keys today:** the data source already exists — `FacilityInternalGraph` is built when `enable_department_routing` is ON ([engine.py:263-269](../src/faer_dev/simulation/engine.py#L263)) and exposes `get_queue_depths()`/`get_capacities()`. The missing link is exactly one engine callback that, on each `TREATMENT_START`/`TREATMENT_END`, does `blackboard.set("department_queue_depth", dept_graph.get_queue_depths())`. **No new structure — one writer.** Note: the DCS/dept BTs that *read* these keys are themselves never ticked (C4), so populating them only matters once the BT consumer path is also wired.

---

## C3. MULTI-EDGE GRAPH — DiGraph, single-edge, blocks #14 multi-modal

`TreatmentNetwork.graph` is an **`nx.DiGraph`** ([topology.py:29](../src/faer_dev/network/topology.py#L29)) — **not** MultiDiGraph. `add_route()` writes a *single* edge with one `transport` string and one `base_time`/`weight` ([topology.py:50-56](../src/faer_dev/network/topology.py#L50)).

**Consequence:** a second `add_route(A, B, ..., transport="rotary")` **overwrites** the existing A→B ground edge — DiGraph silently collapses parallel edges. So **one facility pair can hold exactly one transport mode** today.

**What #14 multi-modal selection requires (INTRINSIC, topology-level):**
1. Promote `graph` to `nx.MultiDiGraph` so A→B can carry `{ground, rotary, fixed_wing}` in parallel.
2. `get_route()` / `get_travel_time()` / `get_edge()` ([topology.py:58-96](../src/faer_dev/network/topology.py#L58)) must take a mode key (`graph[u][v][k]`) — currently `graph[u][v]` assumes one edge.
3. A selection policy (acuity + availability) at the engine transit point ([engine.py:854](../src/faer_dev/simulation/engine.py#L854) reads a single `transport_str`). The VOP `available_transport_modes` blackboard key ([blackboard.py:61](../src/faer_dev/decisions/blackboard.py#L61)) is the pre-registered home for this — currently write-never-read.

This is a foundational data-structure change, not an add-on. #12 (vehicle types) and #14 both block on it.

---

## C4. DCS / RE-TRIAGE DATA PATH — a closed loop with every wire cut (INTRINSIC×INTRINSIC)

Tracing the DCS path end-to-end:

- **`build_dcs_tree`** ([trees.py:221](../src/faer_dev/decisions/trees.py#L221)) constructs a Selector whose only writer is `SetDCS`, which does `bb.set("decision_dcs", True)` ([bt_nodes.py:247](../src/faer_dev/decisions/bt_nodes.py#L247)). **But the tree is exported and never instantiated/ticked** in the engine (Backward B6 — phantom). So `decision_dcs` is written **only** if someone ticks the tree; nobody does.
- **`decision_dcs` readers:** only the convenience property `blackboard.decision_dcs` ([blackboard.py:173](../src/faer_dev/decisions/blackboard.py#L173)) — no engine consumer.
- **`requires_dcs`** (the *other* DCS signal) is computed by `triage_decisions()` ([routing.py:43,50](../src/faer_dev/routing.py#L43)) and stored on the patient ([engine.py:657](../src/faer_dev/simulation/engine.py#L657)). It **is** read — but only to bias department selection toward FST ([engine.py:989](../src/faer_dev/simulation/engine.py#L989)). It never emits a `DCS` event (the type is declared at `engine.py:55` and emitted nowhere — Forward F12 / Backward B7).
- **Two parallel DCS notions that never meet:** rule-based `requires_dcs` (live, steers dept) vs BT `decision_dcs` (phantom, steers nothing). #28 "BT DCS decision" is the phantom one.

**The #21→#23 deterioration→re-triage path:**
- `pfc.compute_deterioration()` ([pfc.py:96](../src/faer_dev/pfc.py#L96)) is an **orphan** — returns a value, **never called** (Backward B1/B6).
- The engine instead runs inline `_retriage_for_deterioration()` ([engine.py:310-348](../src/faer_dev/simulation/engine.py#L310)), which **mutates `patient.severity_score` in place** (`+= 0.20 × multiplier`, [engine.py:330](../src/faer_dev/simulation/engine.py#L330)) and **returns a promoted `TriageCategory`** consumed inline in the hold loop. So re-triage today is a **return-value + in-place-mutation** path, not a blackboard path.
- **Model mismatch (Backward B2):** inline uses `0.20 × mult` step; `pfc.py` uses linear `0.01` rate. They are not equivalent. #23 cannot consume #21 via `pfc.py` until the model is reconciled.

**INTRINSIC×INTRINSIC verdict:** DCS and deterioration are each a closed loop with the consumer wire cut. Wiring #28 means (a) instantiating + ticking `build_dcs_tree`, (b) populating `facility_utilisation`/`mascal_active`/`time_since_injury_minutes` it reads (C2/C10 — three of those are write-never-read), and (c) emitting the `DCS` event. Three dependencies, all currently dormant.

---

## C5. MULTI-POI CONCURRENCY — determinism is the real blocker (INTRINSIC×INTRINSIC)

Today: one `ArrivalProcess` ([arrivals.py:93](../src/faer_dev/simulation/arrivals.py#L93)) with one seeded `np.random.Generator` ([engine.py:142](../src/faer_dev/simulation/engine.py#L142), shared across factory, transport, treatment), feeding one POI via `run(poi_id=...)`. `_handle_arrival` starts a journey rooted at the single `self._poi_id` ([engine.py:591-593](../src/faer_dev/simulation/engine.py#L591)).

**(a) Does DISPOSITION==ARRIVAL survive?** Yes structurally — `_handle_arrival` creates exactly one casualty per record and `_finalize_patient` emits exactly one DISPOSITION ([engine.py:642](../src/faer_dev/simulation/engine.py#L642)). The invariant is per-casualty, independent of origin count. (Verified this run: ARRIVAL 31 / DISPOSITION 28, delta = 3 in-flight at cutoff — not a violation, a drain artefact, Forward F12.)

**(b) Shared mutable state:**
- **Casualty ID counter** — `CasualtyFactory._counter` produces `CAS-%04d` sequentially ([casualty_factory.py:67,107](../src/faer_dev/simulation/casualty_factory.py#L67)). **One factory instance, one counter.** Multiple concurrent arrival processes all calling `factory.create()` is safe *only* because SimPy is single-threaded cooperative — but ID *assignment order* becomes a function of event-interleave order.
- **Shared `_rng`** — the single generator feeds arrivals, casualty sampling, transport trip times, and treatment times. This is the determinism hazard.
- **`self.patients` dict, `mascal_detector`** — shared, single-threaded-safe but order-sensitive.

**(c) Does interleaving break seed=42 determinism?** **This is the live risk.** SimPy orders concurrent events deterministically by `(time, priority, insertion-count)`, so *given a fixed process-start order* replay is stable. But two POI processes drawing inter-arrival times from **one shared RNG** means the draw sequence depends on which process the env schedules first at equal timestamps — and adding a second `env.process()` shifts every subsequent draw. **Same seed will NOT reproduce single-POI output**, and POI-A's stream is no longer independent of POI-B's.

**Minimal change to thread origin through (and stay deterministic):**
1. Add `origin: str` to `ArrivalRecord` ([arrivals.py:84](../src/faer_dev/simulation/arrivals.py#L84)) — defaults preserve single-POI.
2. `_handle_arrival` routes `self.env.process(self._patient_journey(patient, record.origin or self._poi_id))` ([engine.py:593](../src/faer_dev/simulation/engine.py#L593)).
3. **Per-POI sub-RNG** — `np.random.default_rng(seed).spawn(n_poi)` so each POI process has an independent stream; merge order then cannot perturb cross-POI draws. This is the determinism guard Forward F6 flagged.

INTRINSIC×INTRINSIC because multi-POI (#1) couples with MASCAL (#30, per-POI surge) and unit positioning (#8, which POI fires).

---

## C6. EVENT ARCHITECTURE — a real synchronous bus exists; consumables *could* subscribe

There **is** an `EventBus` ([bus.py:22](../src/faer_dev/events/bus.py#L22)) — a synchronous, re-entrancy-queued pub/sub. The engine wires exactly **one** subscriber today: `event_bus.subscribe_all(event_store.append)` ([engine.py:224](../src/faer_dev/simulation/engine.py#L224)). It supports `subscribe(type, cb)` and `subscribe_all(cb)` ([bus.py:35-43](../src/faer_dev/events/bus.py#L35)).

- **Synchronous + deterministic by design** — subscribers run inside the publish call, re-entrant publishes are FIFO-queued ([bus.py:51-58](../src/faer_dev/events/bus.py#L51)), preserving replay. Exceptions in subscribers are swallowed + logged ([bus.py:65,74](../src/faer_dev/events/bus.py#L65)) — a consumable manager that throws would be **silently dropped**, a real risk for #35-39.
- The docstring itself names the intended future subscribers: "Phase 5+: ConsumableManager, FacilityAgent" ([bus.py:26](../src/faer_dev/events/bus.py#L26)).

**Can #35-39 consumables subscribe to treatment events?** ✅ **Architecturally yes, today** — a `ConsumableManager.on_event` could `bus.subscribe("TREATMENT_START", ...)` and decrement blood/kit. **But** (a) the events carry no consumable payload (TREATMENT_START metadata is `{wait_time, department}`, [engine.py:1061](../src/faer_dev/simulation/engine.py#L1061)), and (b) consuming *synchronously to alter routing* (stockout → reroute, #39) needs the manager's state on the blackboard **before** the next routing decision — the bus fires *after* the decision. So the bus is sufficient for **tracking** (#35-37) but **not** for **feedback** (#39) without a blackboard write-back loop (C2).

**Can #54 Report Agent read?** ✅ — it reads the `EventStore` post-run (`store.query()`, `events_of_type()`), exactly as the Engine Room does (C11). No bus subscription needed for AAR.

---

## C7. TREATMENT YIELD SPLITTING — already dispatches to sub-resources, no restructure (INTRINSIC)

Departments (#2-4) do **not** require restructuring the facility-treatment yield. The engine already branches: `_treat_in_department` vs `_treat_in_queue` ([engine.py:973-980](../src/faer_dev/simulation/engine.py#L973)), dispatched via `yield from` to sub-generators.

- When `enable_department_routing` is ON, `_treat_in_department` requests the **department's own** `PriorityResource` (`dept.resource.request(priority=...)`, [engine.py:1052](../src/faer_dev/simulation/engine.py#L1052)) — the bed pool is *already split per department* by `FacilityInternalGraph` ([departments.py:78](../src/faer_dev/simulation/departments.py#L78)).
- The yield structure is **identical** to the single-queue path (request → `yield req` → `yield timeout(treatment_time)`), just against a sub-resource. The "5-yield invariant" framing is already moot here (Backward B3: these yields live in engine.py but treatment yields against department resources are within the journey generator).
- Three capacity regimes are pre-built: A (partitioned per-dept resources), B (shared facility capacity, dept labels only, [engine.py:1091-1130](../src/faer_dev/simulation/engine.py#L1091)), C (zero capacity). So sub-pool splitting is a **solved mechanism that is toggle-gated OFF** — not new yield work.

**Verdict:** #2-4 dispatch within the current yield block. The work is **population/wiring** (C2 — feed the blackboard, tick the dept BT) and **testing** (the ON path has zero tests, Backward B4), not yield restructuring.

---

## C8. PHYSICAL TRANSPORT × BATCHING — deadlock-free today; vehicle-held-through-journey adds the risk (INTRINSIC×INTRINSIC)

Current transport request/release (the two paths, [engine.py:920-943](../src/faer_dev/simulation/engine.py#L920)):
- **Batched** (`rotary`/`fixed_wing`, capacity>1): `BatchCoordinator._dispatch_batch` claims **one** vehicle via `with self.resource.request() ... yield req` ([transport.py:428-441](../src/faer_dev/simulation/transport.py#L428)), holds it for `trip_time`, releases at `with` exit. The patient process only `yield ready_event` then `yield timeout(travel_time)` — **the patient never holds the resource**, the coordinator does.
- **Unbatched** (`ground`): patient does `req = resource.request(); yield req; yield timeout(travel_time)` then **releases asynchronously** via `_vehicle_return` ([engine.py:941](../src/faer_dev/simulation/engine.py#L941)) — vehicle returns to base after the trip.

**Deadlock risk today: none.** Each path acquires exactly one resource and releases it on a timeout, no nested holds, no hold-and-wait across two pools.

**The #15 physical-transport-constraint risk:** #15 wants a vehicle **held for the entire patient journey** (or held while the patient also waits for a destination bed). That introduces **hold-and-wait across two resource pools**: vehicle (transport) + bed (facility/department). Concretely — if a patient holds a helicopter (`transport.PriorityResource`) while blocked in the R1→R2 **hold loop** waiting for a downstream bed ([engine.py:706-749](../src/faer_dev/simulation/engine.py#L706)), and the only path to free that bed needs the same helicopter to evacuate the bed's current occupant → **classic circular wait**. Today the hold loop runs *before* transport is requested, so the cycle can't form; #15 would invert that ordering. **#15 × batching × hold-at-R1 is the deadlock triad to model carefully.**

---

## C9. ENSEMBLE OUTPUT + OVERRIDE GAP — diffable output, but no scalar-override hook (SURFACE, gates the PoC)

`EnsembleBuilder` ([ensemble.py:127](../src/faer_dev/events/ensemble.py#L127)) constructor takes `(preset, n_replications, base_seed, patient_seed, toggles)`; `run()` takes `(duration, poi_id, max_patients)`. Output is `EnsembleSnapshot` with per-metric `AggStat` (mean/std/95% CI) and `to_dict()` round-4 floats ([ensemble.py:76-84](../src/faer_dev/events/ensemble.py#L76)) — **diffable ✅**.

**The override gap (confirms Forward F8):** every run goes through `build_engine_from_preset(self.preset, seed=rep_seed, toggles=...)` ([ensemble.py:190](../src/faer_dev/events/ensemble.py#L190)) — **preset name only**. There is no path to vary R1 bed count, capability flags, or arrival rate without editing the YAML on disk. `patient_seed` is **inert** ([ensemble.py:167](../src/faer_dev/events/ensemble.py#L167)).

**Minimal `scenario_overrides` to make AC-45.1 (golden-hour vs R1-beds sweep) expressible:**
1. `get_preset_raw(name)` already returns the editable raw dict ([builder.py:261](../src/faer_dev/config/builder.py#L261)).
2. Add `scenario_overrides: dict | None` to `EnsembleBuilder.__init__`; in `run()`, replace the `build_engine_from_preset` call with: `raw = get_preset_raw(self.preset); deep_merge(raw, overrides); build_engine_from_dict(raw, seed=rep_seed, toggles=...)`.
3. The sweep driver iterates `overrides = {"facilities": [{"id": "R1-ALPHA", "beds": n}]}` for n in range.

That is the **one threading point** ([ensemble.py:190](../src/faer_dev/events/ensemble.py#L190)) — `build_engine_from_dict` already accepts a full dict. **But (C13 ordering):** sweeping `beds` is only meaningful because beds *are* intrinsic (they gate the hold loop), whereas sweeping `has_surgery` changes **nothing** until #5 lands. The override param is necessary but not sufficient for capability sweeps.

---

## C10. BLACKBOARD WRITE CONFLICTS — no two writers share a key (no race), but most keys have no writer

All blackboard `.set()` writers across `casualty_factory`, `bt_nodes`, `engine`, `observer`:

| Key(s) | Writer | Site | Reader |
|---|---|---|---|
| `patient_*` (7 keys) | `casualty_factory` (via `set_patient_context`) | [casualty_factory.py:217](../src/faer_dev/simulation/casualty_factory.py#L217) | `bt_nodes` (severity/region/surgical/polytrauma) |
| `mascal_active` | `casualty_factory` | [casualty_factory.py:225](../src/faer_dev/simulation/casualty_factory.py#L225) | `bt_nodes.CheckMASCALActive` |
| `decision_triage` + `decision_path` | `bt_nodes.SetTriage` | [bt_nodes.py:202-204](../src/faer_dev/decisions/bt_nodes.py#L202) | `observer` (`decision_path`) |
| `decision_department` + `decision_path` | `bt_nodes.SetDepartment` | [bt_nodes.py:226-228](../src/faer_dev/decisions/bt_nodes.py#L226) | (none live) |
| `decision_dcs` + `decision_path` | `bt_nodes.SetDCS` | [bt_nodes.py:247-249](../src/faer_dev/decisions/bt_nodes.py#L247) | (none live — C4) |
| all keys (defaults) | `blackboard.__init__` / `reset_patient_context` | [blackboard.py:96,131](../src/faer_dev/decisions/blackboard.py#L96) | — |
| **engine** | **writes NOTHING to the blackboard** beyond construction | — | — |
| `observer` | read-only (`record_decision` reads `decision_path`, [observer.py:113](../src/faer_dev/decisions/observer.py#L113)) | — | — |

**Conflict analysis:**
- **`decision_path` is the one multi-writer key** — `SetTriage`, `SetDepartment`, `SetDCS` all **append** to it ([bt_nodes.py:204,228,249](../src/faer_dev/decisions/bt_nodes.py#L204)). This is append-not-overwrite, and `reset_patient_context` clears it between patients ([blackboard.py:133](../src/faer_dev/decisions/blackboard.py#L133)). **Race iff** triage/dept/DCS trees tick within the same patient *and* the reset doesn't run between them — currently only the triage tree ticks (inverted factory mode), so no live conflict. **If #27/#28 are wired** so all three trees tick per patient, `decision_path` accumulates across trees and the per-tree reset boundary must be enforced, else paths bleed between decisions.
- **`mascal_active` has two *potential* writers** — `casualty_factory.set("mascal_active", ...)` (live) and `set_facility_context(mascal_active=...)` ([blackboard.py:160](../src/faer_dev/decisions/blackboard.py#L160), never called). If C2's facility writer is added naively it would **fight the factory writer** — they'd set the same key from different truth sources (per-arrival flag vs facility-level detector). **This is the one designed-in collision to avoid.**
- **No interleave race today** because the engine blackboard path runs only in single-threaded SimPy and only the factory+triage-tree touch it. The danger is purely **future** (wiring more BT consumers).

---

## C11. ENGINE ROOM (#53) DATA DEPENDENCIES — events live, blackboard/occupancy dormant

#53 needs: event log, facility occupancy over time, casualty locations, module attribution, blackboard snapshots. Status of each input today:

| Engine Room input | Exists today? | Source | Blocker |
|---|---|---|---|
| Event log | ✅ live | `event_store.query()` — page reads `e.get("facility")` etc. ([6_engine_room.py:231,257](../demo_app/pages/6_engine_room.py#L231)) | none |
| **Module attribution** | ✅ live | `SimEvent.source` field (`"engine"` in this run) ([models.py:32](../src/faer_dev/events/models.py#L32)) | only ever `"engine"` until BT observer emits (`bt_observer` source unused) |
| Casualty locations | ✅ derivable | `facility_id` per event + `patient_journey()` | none — reconstructable from event stream |
| **Facility occupancy over time** | ⚠️ partial | `ReplayEngine.replay_to(t)` reconstructs `facilities[fid].occupancy` ([ensemble.py:263](../src/faer_dev/events/ensemble.py#L263)) from events | works via replay; **live blackboard occupancy is unfed** |
| **Blackboard snapshot inspector** | 🔴 **dormant** | `blackboard.snapshot()` exists ([blackboard.py:182](../src/faer_dev/decisions/blackboard.py#L182)) | facility keys are **write-never-read** (C2) — the inspector would show only defaults + patient keys; the "HC-5 isolation" demo (ideation L136) has nothing live to show on the facility side |

**Verdict:** the Engine Room's **event-derived** panels (timeline, triage focus, facility performance via replay) work **today**. Its headline **blackboard inspector** and **live occupancy bars** ([ENGINE_ROOM_IDEATION.md:120,145](ENGINE_ROOM_IDEATION.md)) are **blocked on C2** — they need the engine→blackboard writer before they show real state. #53 depends on the same unfed-keys fix as #4.

---

## C12. MNEMOSYNE EXPORT (#62) — 5 real events vs survival schema

5 sample events from the run (fields flattened):

```
ARRIVAL          t=96.2  CAS-0001 @POI-1   triage=T3 severity=0.070 mechanism=GSW
                          recommended_triage=T3 bypass_role1=False requires_dcs=False priority=3 source=engine
TRANSIT_START    t=96.2  CAS-0001 @POI-1   {origin:POI-1, destination:R1-ALPHA, transport_mode:ground}
TRANSIT_END      t=116.2 CAS-0001 @R1-ALPHA {transit_time:20.0}
TREATMENT_START  t=116.2 CAS-0001 @R1-ALPHA {wait_time:0.0}
DISPOSITION      t=117.7 CAS-0001 @R1-ALPHA outcome=RTD total_time=21.5
```

Mapping against a survival-dataset schema:

| Survival field | Present on events? | Source / gap |
|---|---|---|
| `severity` | ✅ | `ARRIVAL.severity` |
| `triage` | ✅ | every event's `triage` |
| `mechanism` | ✅ | `ARRIVAL.injury_mechanism` |
| `primary_region` | ❌ **missing** | exists on blackboard (`patient_primary_region`) + Casualty, but **never emitted** on any event |
| `pfc_duration` | ⚠️ **phantom in default run** | `PFC_END.pfc_duration_min` ([engine.py:385](../src/faer_dev/simulation/engine.py#L385)) only fires under `enable_ccp`/hold>60min — 0 in this run |
| `r1_capacity_pct` | ❌ **missing** | facility occupancy not on events; blackboard facility keys unfed (C2). Recoverable only via `ReplayEngine` post-hoc, not as an event field |
| `transport_eta` | ⚠️ proxy only | `TRANSIT_END.transit_time` is **actual**, not ETA; no pre-trip estimate emitted |
| `route_threat_level` | ❌ **missing** | `threat_level` is dropped by the builder (Forward F9) — never reaches an edge or event |
| `survival` (label) | ❌ **proxy only** | `DISPOSITION.outcome` ∈ {RTD, DECEASED, STRATEVAC, ...} ([engine.py:692-697](../src/faer_dev/simulation/engine.py#L692)) is a disposition label, **not** a modelled survival probability; no survivability computed in the engine (Backward B6: `compute_survivability` is UI-only) |

**Mapping cost for #62:** **~3 of 9 fields are direct**; 2 are phantom/conditional (`pfc_duration`, `survival`-as-outcome), 4 require **upstream intrinsic work** before they can be exported at all: emit `primary_region` on ARRIVAL (trivial), feed `r1_capacity_pct` (needs C2), read `threat_level` (needs #10 + C14), and compute a real `survival` target (needs #20/#40 wired into the engine). **The DCS/PFC phantoms (C4) leave the two clinically-richest columns empty in a default run.** #62 is gated on intrinsic completeness, not on the serialiser.

---

## C13. CROSS-LAYER DEPENDENCY MAP — the master ordering constraint

Every SURFACE feature and the INTRINSIC feature(s) it needs correct first. **No surface feature may rank above any intrinsic in its "depends on" column.**

| Surface # | Name | Depends on intrinsic # | Why |
|---|---|---|---|
| 34 | PFC event stream | 31, 32, 33 | nothing to stream until CCP/PFC ceiling are wired (PFC events conditional, C4) |
| 40 | Survivability curves | 20, 21, 22 | curve is a function of vitals + deterioration; both dormant/orphan |
| 41 | Golden-hour compliance | 1, (treatment/transit live) | metric computed today ([engine.py:960-969](../src/faer_dev/simulation/engine.py#L960)); meaningful sweep needs multi-POI inflow variation |
| 42 | Facility utilisation over time | 2, 3 | occupancy needs department/bed mechanics + the C2 writer |
| 43 | Process mining / XES | (all intrinsic event types) | variant analysis is wrong if DCS/PFC events are missing (C4) |
| 44 | Ensemble CI | 5, 1, 10 | CI over a metric only matters if the swept input is intrinsic (C9) |
| 45 | Sensitivity sweep | 5, 1, 10, 44 | wraps #44; varying inert scalars (has_surgery, threat) measures nothing until those are live |
| 50 | YAML-driven scenarios | 5, 10, 12 | config keys (`has_surgery`, `threat_level`, vehicles) are silently dropped until intrinsic readers exist (C14) |
| 51 | Operational context presets | (intrinsic configurability) | presets only differ where intrinsics read them |
| 52 | HADR variant | 1, 2 | a variant is a no-op unless arrival/facility mechanics differ |
| 53 | Engine Room / X-Ray | 2, 3, 4 | blackboard inspector + occupancy need the C2 writer (C11) |
| 54 | AAR / Report Agent | 28, 31-33 + event completeness | a report over phantom DCS/PFC reports gaps as facts |
| 56 | OPORD-to-config | 5, 8, 10 (+ config blocks) | generating config for features the engine can't read is dead text (C14) |
| 57 | Agent memory across runs | 55 | no agent, no memory |
| 60 | Shadow agent / comparator | 29 | needs ≥2 live decision systems; `decision_mode` is dead (Backward B10) |
| 61 | Statistics upgrade | 44 | upgrades the ensemble's stats — needs the ensemble producing real variance |
| 62 | MNEMOSYNE export | 5, 10, 20, 28, 31-33 | 6 of 9 survival fields are dormant/phantom (C12) |
| 63 | Supply-chain cascade | 35, 36, 37, 38, 39 | consumables module does not exist (Forward F1) |
| 64 | Lessons-learned KG | 54 + event completeness | builds on AAR; inherits its gaps |
| 7 | Unit definitions (config) | 8 | no `units` config block; #8 not config-supported (C14) |

**Load-bearing intrinsics (gate the most surface features):** **#5** (gates 44,45,50,56,62), **#1** (41,52,44), **#10** (44,45,50,56,62), **#31-33** (34,54,62,64), **#2-4** (42,53). Fix these five clusters and 14 surface features unblock.

---

## C14. CONFIG-TO-ENGINE COUPLING — which blocks feed which intrinsics

Mapping config blocks → engine modules they feed → currently parsed by the builder?

| Config block | Engine module(s) it feeds | Features affected | Parsed by builder? |
|---|---|---|---|
| `operational_context` | `ArrivalConfig`, `TransportConfig` selection ([builder.py:98-107](../src/faer_dev/config/builder.py#L98)) | #51, arrival/transport rates | ✅ yes |
| `arrivals.*` | `ArrivalConfig` (rate + MASCAL) ([builder.py:106-154](../src/faer_dev/config/builder.py#L106)) | #1 (single POI), #30 | ✅ yes |
| `facilities[].beds`, `role`, `coordinates` | `Facility` + `TreatmentNetwork.add_facility` + `FacilityQueue` ([builder.py:195-205](../src/faer_dev/config/builder.py#L195)) | #2-4, hold loop | ✅ yes |
| `facilities[].has_surgery/blood/imaging` | `Facility` schema only | **#5** | ⚠️ **parsed but never read** ([builder.py:201-203](../src/faer_dev/config/builder.py#L201); routing ignores — C1) |
| `facilities[].or_tables/icu_beds/ventilators` | nothing | #3 surgical/ICU capacity | 🔴 **silently dropped** (builder never reads) |
| `edges[].from/to/travel_time/transport` | `TreatmentNetwork.add_route` ([builder.py:207-218](../src/faer_dev/config/builder.py#L207)) | #12, #14 (single mode, C3) | ✅ yes |
| `edges[].threat_level` | nothing | **#10, #11** | 🔴 **silently dropped** |
| `units` | — | #7, #8, #9 | 🔴 **block does not exist** |
| `threat_zones` | — | #10, #11, #46-49 | 🔴 **block does not exist** |
| `vehicles` | — | #12, #13, #15, #17 | 🔴 **block does not exist** |
| `consumables` | — | #35-39 | 🔴 **block does not exist** |

**Intrinsic features that need builder changes before they can be configured at all:**
- **#5 capability flags:** flags *are* parsed onto `Facility` ([builder.py:201](../src/faer_dev/config/builder.py#L201)) — so #5 needs **no builder change**, only a routing reader (C1). Plus add `has_lab` (parsed nowhere) if needed.
- **#8 unit positioning:** needs a **new `units` block** + parser + a source→POI map (C5). Cannot be configured today.
- **#10 threat zones:** needs the builder to **stop dropping `edge.threat_level`** ([builder.py:207-218](../src/faer_dev/config/builder.py#L207)) and/or a new `threat_zones` block, plus an engine reader. Cannot be configured today.
- **#12 vehicle types:** `transport` is parsed as a per-edge string ([builder.py:213](../src/faer_dev/config/builder.py#L213)); true vehicle differentiation needs a **`vehicles` block** + MultiDiGraph (C3). Edge-level only today.

**Net coupling risk:** the builder is a raw-`dict.get()` path with hard-coded defaults ([builder.py:83](../src/faer_dev/config/builder.py#L83)) and **no schema version** (Forward F9). Three capability-relevant fields (`or_tables`, `icu_beds`, `threat_level`) are **silently dropped today** — any feature that adds a YAML key inherits silent-default behaviour: wrong numbers, no error. **#5 is the cheapest** (flags already parsed); **#10 and #12 are the most config-blocked** (dropped field + missing blocks).

---

## CROSS SYNTHESIS — interaction-ranked

**INTRINSIC×INTRINSIC (highest impact — model these together):**
1. **C2/C10/C11 — the engine→blackboard writer.** One missing writer is the shared prerequisite for #4 departments, #53 Engine Room, #58 weather, #35-39 consumable feedback. Watch the `mascal_active` two-writer collision (C10).
2. **C4 — DCS + deterioration closed loops.** Wiring #28/#23 means ticking the dormant trees, populating three write-never-read keys, reconciling the `0.20` vs `0.01` deterioration model (Backward B2), and emitting the phantom `DCS` event.
3. **C5 — multi-POI determinism.** Shared `_rng` + shared ID counter make a second arrival process perturb the seed=42 stream. Needs per-POI sub-RNGs (`rng.spawn`).
4. **C8 — #15 physical-transport × hold-at-R1 × batching deadlock triad.** Holding a vehicle across the bed-wait inverts the current safe ordering.
5. **C3 — DiGraph→MultiDiGraph** for #12/#14; foundational, touches every `topology.py` accessor.

**INTRINSIC×SURFACE (ordering constraints — C13 is the master table):**
- #5 capability routing gates #44/#45/#50/#56/#62. The routing blast radius is narrow (C1) but the acceptance gate (R16a) and MNEMOSYNE (C12) both wait on it.
- C9 `scenario_overrides` is a one-line threading change but only pays off behind #5/#1/#10.

**SURFACE×SURFACE (independent — low risk):** #61 statistics on #44, #64 KG on #54, #57 memory on #55 — each is a thin wrapper that inherits its base's gaps, no cross-conflict.

**The single cheapest high-leverage move:** the **engine→blackboard facility writer** (C2) — ~one callback, no new structure, unblocks #4/#42/#53 and feeds the C11 inspector and C12 `r1_capacity_pct`. Pair it with reading the already-parsed capability flags (C1, #5) and most surface features become *measurable*.

---
*Cross agent complete. 14/14 answered. Awaiting Red Team block.*
