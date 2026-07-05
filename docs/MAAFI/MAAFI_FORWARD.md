# MAAFI FORWARD AGENT — FAER-MIL Codebase Interrogation

**Run date:** 2026-06-17
**Repo:** Pj-FAER-Dev (FAER-MIL MEDEVAC poly-hybrid DES engine)
**Test baseline:** 99 passed / 0 failed (pytest 9.0.2, 0.41s)
**Agent role:** Forward (greedy addition, intrinsic-first marginal-cost mapping)

---

## GO / NO-GO GATE RESULTS (read first)

| Gate | Result | Evidence |
|------|--------|----------|
| **F4 — routing calls TreatmentNetwork** | ✅ **PASS — gate NOT hit** | `routing.get_next_destination()` calls `network.get_route()` ([routing.py:133](../src/faer_dev/routing.py#L133)), reads `network.graph` / `network.facilities` throughout. Capability flags (#5) have a place to plug in (Facility objects reachable via `network.facilities`). |
| Determinism (R1) | not in Forward scope | Deferred to Red Team. |
| Strangler drift (R5) | not in Forward scope | Deferred to Red Team. |

**Critical caveat to F4 (not a blocker):** routing reads **only** `role`, graph edges, and `bypass_role1`. It reads **none** of `has_surgery / has_blood / has_imaging / has_lab / or_tables / ventilators / icu_beds` (grep of routing.py + engine.py returns **empty**). So #5 is *greenfield wiring on an existing seam*, not a blocked feature. The seam exists; the capability logic does not.

---

## F1. ORPHAN DETECTION

Method: located each named file, grepped every public symbol against live `src/` call sites (excluding defs, `__pycache__`, `SOURCES.txt`, and tests).

| File (actual path) | Orphan status | Detail | Layer |
|---|---|---|---|
| **`pfc.py`** (top-level [pfc.py](../src/faer_dev/pfc.py)) | 🔴 **FULL IMPORT ORPHAN** | `from faer_dev.pfc` appears **only** in `tests/test_pfc.py:13` and a boundary assertion in `tests/test_phase1_integration.py:122`. **engine.py never imports it.** Both public fns are dead: `evaluate_hold()` ([pfc.py:41](../src/faer_dev/pfc.py#L41)) and `compute_deterioration()` ([pfc.py:96](../src/faer_dev/pfc.py#L96)). The engine's hold/PFC logic is entirely inline. | **INTRINSIC** — `evaluate_hold` is the PFC state machine (#31–33); `compute_deterioration` is #21. Wiring them would change disposition outcomes. |
| **`departments.py`** ([simulation/departments.py](../src/faer_dev/simulation/departments.py)) | 🟢 Wired (toggle-gated) | `FacilityInternalGraph`, `build_r1/r2/r3` imported + used at [engine.py:35,264](../src/faer_dev/simulation/engine.py#L264) behind `enable_department_routing`. Internal helpers (`_allocate_partitioned_beds`, `_build_by_regime`) all reached. No orphan functions. | INTRINSIC (#2–4) — but gated OFF by default. |
| **`ccp.py`** ([simulation/ccp.py](../src/faer_dev/simulation/ccp.py)) | 🟡 Partial | `CasualtyCollectionPoint`/`CCPConfig` imported + instantiated at [engine.py:244,246](../src/faer_dev/simulation/engine.py#L244) behind `enable_ccp`. **`apply_interventions()`** ([ccp.py:74](../src/faer_dev/simulation/ccp.py#L74)) and **`total_intervention_time`** ([ccp.py:96](../src/faer_dev/simulation/ccp.py#L96)) have **no engine call site** → orphan methods. | INTRINSIC (#31–32) — apply_interventions would change deterioration if wired. |
| **`vitals.py`** ([core/vitals.py](../src/faer_dev/core/vitals.py)) | 🟢 Wired (toggle-gated) | `VitalsGenerator` imported at [engine.py:289](../src/faer_dev/simulation/engine.py#L289) (behind `enable_vitals`) and `core/atmist.py:14`. | INTRINSIC (#20). |
| **`transport.py`** ([simulation/transport.py](../src/faer_dev/simulation/transport.py)) | 🟢 Wired | Imported at [engine.py:38](../src/faer_dev/simulation/engine.py#L38); transport pool/vehicle-cycle metrics appear in run output (`transport.rotary/ground/fixed_wing`). *Not exhaustively traced per-symbol — flagged for Backward B1.* | INTRINSIC (#12–17). |
| **`mining.py`** ([events/mining.py](../src/faer_dev/events/mining.py)) | 🔴 **IMPORT ORPHAN** | No `src/` importer (only `SOURCES.txt`). Whole module dead. | **SURFACE** (#43 process mining). |
| **`xes_exporter.py`** ([events/xes_exporter.py](../src/faer_dev/events/xes_exporter.py)) | 🟡 Lazy-wired | Imported on-demand at `events/store.py:119` (`store.to_xes()`). Reachable but never auto-invoked in a run. | **SURFACE** (#43 export). |
| **`delay.py`** ([events/delay.py](../src/faer_dev/events/delay.py)) | 🔴 **IMPORT ORPHAN** | No `src/` importer. Whole module dead. | **SURFACE** (analytics). |

**Bonus orphan (not in the list but material):** there is **no `consumable.py`** anywhere in the tree. The entire consumable mechanism (#35–39 blood/kit/oxygen/resupply/stockout, all INTRINSIC) is **unimplemented** — only narrative mentions in `events/bus.py:26` ("Phase 5+: ConsumableManager") and `decisions/trees.py:283`.

**Top Forward signal:** the single highest-value orphan is `pfc.py` — an *already-extracted, already-tested* intrinsic module that the engine simply never imports. `enable_extracted_pfc` exists ([mode.py:56](../src/faer_dev/decisions/mode.py#L56)) but is checked **nowhere** in `src/`. Lowest marginal cost to wire of any intrinsic feature.

---

## F2. TOGGLE AUDIT

All fields of `SimulationToggles` ([decisions/mode.py:37-58](../src/faer_dev/decisions/mode.py#L37)). "Tested" = appears in a `tests/` file exercising both states.

| Field | Default | ON path tested? | OFF path tested? | Always-ON? | Gates | Layer |
|---|---|---|---|---|---|---|
| `factory_mode` | `"legacy"` | ❌ no test | (default) | No | casualty generation mode | INTRINSIC |
| `decision_mode` | `RULE_BASED` | ❌ no test | (default) | No | rule vs BT decisions | INTRINSIC |
| `enable_department_routing` | `False` | ❌ no test | implicit | No | dept resource split (#2–4) | INTRINSIC |
| `enable_vitals` | `False` | ❌ no test | implicit | No | vitals trajectory (#20) | INTRINSIC |
| `enable_atmist` | `False` | ❌ no test | implicit | No | ATMIST handover (#18) | INTRINSIC |
| `enable_event_store` | `True` | ❌ no test | never tested OFF | **Effectively always ON** | event capture | SURFACE (observability) |
| `enable_ccp` | `False` | ❌ no test | implicit | No | CCP/PFC facility (#31–32) | INTRINSIC |
| `enable_extracted_routing` | `False` | ✅ 4 test files | ✅ | No | routing extraction (EX-1) | INTRINSIC |
| `enable_extracted_metrics` | `False` | ✅ 3 test files | ✅ | No | metrics extraction (EX-2) | INTRINSIC |
| `enable_typed_emitter` | `False` | ✅ 3 test files | ✅ | No | emitter extraction (EX-3) | SURFACE→INTRINSIC seam |
| `enable_extracted_pfc` | `False` | 🔴 "tested" but module **unwired** | n/a | No | **nothing** — pfc.py not imported by engine | INTRINSIC (dead toggle) |
| `enable_graph_routing` | `False` | ✅ 1 test file | ✅ | No | Dijkstra vs role-walk (Phase 1.5) | INTRINSIC |

**Findings:**
- **Tested:** the 4 Phase-1 extraction toggles + `enable_graph_routing` have ON-vs-OFF seed-matched tests (mostly in `test_routing.py`, `test_metrics.py`, `test_emitter.py`).
- **Untested:** the 6 *feature* toggles (`factory_mode`, `decision_mode`, `enable_department_routing`, `enable_vitals`, `enable_atmist`, `enable_ccp`) have **no toggle tests at all** — their ON paths are completely unverified. All but `event_store` are INTRINSIC.
- **Dead toggle:** `enable_extracted_pfc` gates code that doesn't exist in the live path (see F1). It is checked nowhere in `src/`.
- **Default-ON-only:** `enable_event_store=True` is the only default-ON toggle and is never tested OFF.

---

## F3. SCHEMA INSPECTION — FACILITY

`Facility` is a **Pydantic** `BaseModel` ([core/schemas.py:145-178](../src/faer_dev/core/schemas.py#L145)). Fields: `id, name, role, beds, or_tables, icu_beds, ventilators, coordinates, has_surgery, has_blood, has_imaging, has_lab, is_operational, current_occupancy` + `utilization` property.

| Asked field | Exists? | Actual field | Read by routing.py? | Layer impact |
|---|---|---|---|---|
| `has_surgery` | ✅ | line 162 | ❌ **never read** | SURFACE *as wired* (intrinsic potential) |
| `has_blood` | ✅ | line 163 | ❌ never read | SURFACE *as wired* |
| `has_xray` | ❌ | renamed `has_imaging` (line 164) | ❌ never read | SURFACE *as wired* |
| `has_ventilator` | ❌ | only int `ventilators` (line 156) | ❌ never read | SURFACE *as wired* |
| `departments` | ❌ **does not exist** | dept state lives in `FacilityInternalGraph`, not on Facility | n/a | — |
| `capability_flags` | ❌ **does not exist** | capabilities are discrete bools, no flag container | n/a | — |

**Headline:** every capability field that *does* exist (`has_surgery`, `has_blood`, `has_imaging`, `has_lab`) is **read by no routing or engine code** (confirmed by empty grep across `routing.py` + `engine.py`). They are written by the config builder ([builder.py:201-203](../src/faer_dev/config/builder.py#L201)) and otherwise inert. Today they are effectively **surface** (display/analytics only); #5 promotes them to intrinsic by making routing consult them.

Also note `or_tables`, `icu_beds`, `ventilators` exist on the schema but the **config builder never parses them** (builder reads only `beds`, `coordinates`, `has_surgery/blood/imaging`) — so `or_tables: 2` in `coin.yaml` is **silently dropped**.

---

## F4. ROUTING DECISION INPUTS  *(GATE — PASS)*

`get_next_destination()` ([routing.py:100-149](../src/faer_dev/routing.py#L100)) reads, in order:

1. `patient.triage` — T3 at R1/R2 → `None` (stop); T4 → `None` (line 119-125). Clinical short-circuit.
2. **Graph mode** (`use_graph_routing=True`): `_find_highest_reachable()` walks `ROLE_ORDER` high→low using `nx.has_path` over `network.graph`, excluding R1 nodes for bypass patients (lines 64-97), then `network.get_route(patient, from, target)` (line 133, Dijkstra) → returns `path[1]`.
3. **Legacy mode** (default): role-walk first-match — for each higher role, first facility with `network.graph.has_edge(current, fac_id)` (lines 138-149).

**Decision inputs actually consulted:** `patient.triage`, `patient.bypass_role1` (via `decisions` dict from `triage_decisions()`), `current_facility.role`, `current_facility.id`, and the **graph topology + `facility.role`**. 

**Does it check facility attributes beyond role?** ❌ **No.** It checks `role` and graph reachability only. It does **not** read `has_surgery`, `has_blood`, bed availability, occupancy, or any capability.

**Does it call TreatmentNetwork?** ✅ **Yes** — `network.get_route()` (line 133), `network.graph`, `network.facilities` (lines 79-96, 144-147). Engine wires it at [engine.py:681,686](../src/faer_dev/simulation/engine.py#L681) behind `enable_extracted_routing` (extracted) / `enable_graph_routing` (Dijkstra).

➡️ **Gate result: the seam for #5 capability flags exists** (Facility objects are reachable inside routing via `network.facilities[fac_id]`). The plug-in point is `_find_highest_reachable` (filter facilities by capability) and/or the legacy role-walk inner loop. **Not blocked.**

---

## F5. TREATMENT NETWORK API

`TreatmentNetwork` ([network/topology.py:21](../src/faer_dev/network/topology.py#L21)) — a `nx.DiGraph` wrapper.

| Method | Called from | Status | Layer |
|---|---|---|---|
| `add_facility()` (L32) | `engine.py:258`, `builder.py:188,205` | ✅ live | INTRINSIC (topology build) |
| `add_route()` (L42) | `engine.py:284`, `builder.py:218` | ✅ live | INTRINSIC (topology build) |
| `get_route()` (L58) | `routing.py:133` | ✅ live (graph mode only) | INTRINSIC (routing) |
| `get_travel_time()` (L82) | `engine.py:895` | ✅ live | INTRINSIC (transit duration) |
| `get_edge()` (L92) | `engine.py:852` | ✅ live | INTRINSIC (transport mode lookup) |
| `update_congestion()` (L98) | `engine.py:617` + `test_routing.py:293` | ✅ live + tested | INTRINSIC (dynamic routing weight) |

**`update_congestion()` exists and IS called** ([engine.py:617](../src/faer_dev/simulation/engine.py#L617)). **No defined-only/orphan methods** on TreatmentNetwork — every public method is reached. 

Caveat: `update_congestion` mutates `weight` (not `base_time`), and `get_travel_time` deliberately returns `base_time` (L89) — so congestion changes **routing choice** but never **transit duration**. Correct by design, but means congestion is invisible unless `enable_graph_routing` is ON (the legacy role-walk ignores weight entirely). With default toggles, `update_congestion` has **no behavioural effect**.

---

## F6. ARRIVAL PARAMETERISATION

[simulation/arrivals.py](../src/faer_dev/simulation/arrivals.py). `ArrivalConfig` ([L23](../src/faer_dev/simulation/arrivals.py#L23)) holds a **single scalar** `base_rate_per_hour` (+ MASCAL cluster params). `ArrivalProcess` ([L93](../src/faer_dev/simulation/arrivals.py#L93)) emits facility-agnostic `ArrivalRecord(time, is_mascal, mascal_id)` — it knows nothing about facilities or POI IDs. The engine's `run(poi_id=...)` takes **one** POI id; all casualties enter there.

**Single scalar or per-source?** → **Single scalar**, per *operational context* (`ARRIVAL_CONFIGS` dict, L47). No per-source rates. No multi-POI awareness.

**What multi-POI (#1) actually requires (INTRINSIC):**
1. Per-source `ArrivalConfig` (rate per POI) — either a `Dict[poi_id, ArrivalConfig]` or weighted source selection.
2. A source→facility-ID map so each `ArrivalRecord` carries its origin POI; today `ArrivalRecord` has no facility field (L84).
3. Engine arrival handler ([engine.py:667 `ARRIVAL`](../src/faer_dev/simulation/engine.py#L667)) changed from single `poi_id` to per-record origin.
4. Determinism: concurrent POI SimPy processes must draw from a single seeded RNG with a fixed merge order (cross-ref Cross C5). Currently one `np.random.Generator` (L112) feeds one process — multi-POI introduces an interleaving-order risk.

Marginal cost: **moderate** — arrivals.py is cleanly process-based, but `ArrivalRecord` and the engine arrival entry both need the origin field threaded through.

---

## F7. CASUALTY FACTORY TRACE

`CasualtyFactory` lives at [simulation/casualty_factory.py](../src/faer_dev/simulation/casualty_factory.py) (323 LOC). Inverted/injury-first mode is gated by `factory_mode` ([mode.py:45](../src/faer_dev/decisions/mode.py#L45)).

Pipeline (injury → triage → severity → regions → vitals): the factory composes `injury` ([core/injury.py](../src/faer_dev/core/injury.py)), `triage` ([core/triage.py](../src/faer_dev/core/triage.py)), `injury_sampler` ([simulation/injury_sampler.py](../src/faer_dev/simulation/injury_sampler.py)), and `VitalsGenerator` ([core/vitals.py](../src/faer_dev/core/vitals.py)). ATMIST is a separate module ([core/atmist.py](../src/faer_dev/core/atmist.py), 303 LOC, imports `VitalsGenerator`).

**Blackboard writes (confirmed):** the factory holds the `SimBlackboard` and writes the patient group before each triage tick —
- `reset_patient_context()` then `set_patient_context(...)` ([casualty_factory.py:216-217](../src/faer_dev/simulation/casualty_factory.py#L216)) → writes `patient_severity, patient_primary_region, patient_mechanism, patient_secondary_regions, patient_is_polytrauma, patient_is_surgical, patient_id`.
- `set("mascal_active", ...)` ([casualty_factory.py:225](../src/faer_dev/simulation/casualty_factory.py#L225)).

**MIST/ATMIST populated?** Only when `enable_atmist=True` (default OFF). ATMIST handover is emitted by the engine at [engine.py:462 `ATMIST_HANDOVER`](../src/faer_dev/simulation/engine.py#L462), not by the factory. In the default run **no `ATMIST_HANDOVER` events were emitted** (F12), so MIST is not populated in the baseline path.

*Caveat: I traced the factory's blackboard contract and module composition but did not line-trace every severity/region sampling branch — flagged for Cross C4 (PFC→re-triage data path) and Red Team R17 (stub-passes-tests on the patient model).*

---

## F8. ENSEMBLE + SWEEP COMPATIBILITY

`EnsembleBuilder` ([events/ensemble.py:127](../src/faer_dev/events/ensemble.py#L127)).

**Parameterised for sweeps?** ⚠️ **Partially.** Constructor takes `(preset, n_replications, base_seed, patient_seed, toggles)`; `run()` takes `(duration, poi_id, max_patients)`. You can sweep **seed, toggles, duration, preset-name** — but there is **no hook to vary an intrinsic scalar** (e.g. R1 bed count, capability flags, arrival rate) across runs without editing the preset YAML on disk. A bed-count sweep (the canonical MVP acceptance test, R16b) is **not expressible** through the current API; it needs a `scenario_dict`/override parameter.
- `patient_seed` is **inert** — accepted "for API stability" but has no effect (L167); CRN dual-seed not implemented.

**Output format:** `EnsembleSnapshot` with per-metric `AggStat` (mean/std/95% CI) and `to_dict()` → JSON ([L106](../src/faer_dev/events/ensemble.py#L106)). **Diffable** ✅ (round-4 floats, stable keys). Post-hoc `snapshot_at(t)`, `time_series()`, `triage_by_facility_at(t)` available after `run()`.

**Intrinsic prerequisites before a sweep is meaningful (SURFACE-gates-INTRINSIC):**
- #5 capability routing — else sweeping `has_surgery` changes nothing (routing ignores it).
- #1 multi-POI — else `poi_id` is a single entry point.
- #10 threat / #11 dynamic threat — else `threat_level` edges are inert (F9).
- A `run(scenario_overrides=...)` parameter — else only seed/duration/toggle sweeps are possible.

---

## F9. YAML CONFIG SCHEMA + VERSIONING + CROSS-BLOCK COUPLING

**Loader path:** `load_config()` ([loader.py:16](../src/faer_dev/config/loader.py#L16)) = bare `yaml.safe_load` → **raw dict, no validation**. Two consumers diverge:
- `load_scenario()` (L45) validates via Pydantic `SimulationConfig` — but `SimulationConfig` **drops `facilities`/`edges`** (builder docstring L239), so it's used only for `presets.py` registry, not the real build path.
- `build_engine_from_dict()` ([builder.py:83](../src/faer_dev/config/builder.py#L83)) — the **actual** path — uses **raw `dict.get()` with hard-coded defaults**. Unknown keys are silently accepted; missing keys silently defaulted.

**(a) Schema version field?** ❌ **None.** No `schema_version`/`version` key in any preset (grep empty). No migration strategy.

**(b) Validation mechanism?** **Mixed/raw.** Pydantic models (`Facility`, `SimulationConfig`) exist and *could* generate JSON Schema, but the live build path bypasses `SimulationConfig` and does raw dict access. No JSON Schema is generated or used.

**(c) New intrinsic key added to YAML, old file lacks it?** → **silent default** (e.g. `fac_config.get("has_surgery", False)`). No error, no warning. An old scenario keeps running with the feature silently off.

**(d) Logical config blocks (from `coin.yaml` / `iron_bridge.yaml`):**
```
name, description, operational_context,
arrivals{ base_rate_per_hour, triage_distribution, enable_mascal, mascal_* },
facilities[]{ id, name, role, beds, or_tables*, icu_beds*, has_surgery, has_blood, has_imaging, coordinates },
edges[]{ from, to, travel_time_minutes, transport, threat_level* },
duration_hours, warmup_hours, seed
```
`*` = present in YAML but **silently ignored by the builder** (`or_tables`, `icu_beds`, edge `threat_level`).

**Cross-block coupling:**
- **(e) unit positioning (#8):** ❌ **no `units` block exists** in any preset. #8 is not config-supported today.
- **(f) threat zones (#10):** ❌ **no `threat_zones` block.** `threat_level` exists as a per-edge scalar but the builder **never reads it** ([builder.py:207-218](../src/faer_dev/config/builder.py#L207) parses only from/to/travel_time/transport) → dynamic threat (#10/#11) has no config or engine path.
- **(g) vehicle types (#12):** `transport` is a per-edge string (`GROUND`/`ROTARY`); **no `vehicles` block**, no litter-capacity/compatibility constraints. Multi-modal selection is edge-level, not vehicle-level.
- **Cross-block validation that DOES exist:** the builder validates **edge→facility referential integrity** — raises `ConfigurationError` on an edge referencing an unknown source/destination ([builder.py:174-184](../src/faer_dev/config/builder.py#L174)), with a special-case for `POI*` synthetic sources. This is the one real cross-block guard.
- **(h) overlays/presets (#51):** ❌ **no overlay/composition system.** Five standalone monolithic preset files (`coin/lsco/hadr/specops/iron_bridge`). 0 overlay combinations possible → combinatorics N/A (but #51/#52 would have to *introduce* composition, then face the R14 explosion).

**Net F9 risk:** the config layer **silently drops** capability-relevant fields (`or_tables`, `icu_beds`, `threat_level`) and has **no version/migration**. Every future intrinsic feature that adds a YAML key inherits silent-default behaviour — wrong numbers, no error.

---

## F10. DEPENDENCY MANIFEST

[pyproject.toml](../pyproject.toml). Runtime deps (all **floor pins `>=`, no upper bounds, no lockfile**):
`simpy>=4.1.1, numpy>=1.24, networkx>=3.0, pydantic>=2.0, py-trees>=2.2, pyyaml>=6.0, streamlit>=1.30, plotly>=5.18`. Dev: `jupyter, jupyterlab, pytest>=7.0, pytest-cov, ruff, memory-profiler`.

**Adding the candidate libs:**
| Lib | Conflict risk | Note |
|---|---|---|
| `scipy` | 🟢 Low | numpy-compatible; needed for proper CI/stats (R3, #61). |
| `pm4py` | 🟡 Medium | pulls `pandas`, `graphviz`, `lxml`, deap — heavy; required to make `mining.py` (#43) actually run (it's an import-orphan now). |
| `anthropic` | 🟢 Low | pure-Python + `httpx`; needed for #55 LLM agents. No version conflict. |

Floor-only pins mean **low immediate conflict risk** but **no reproducibility** — a fresh install can pull a breaking major (e.g. networkx 4, pydantic 3) with no guard. Recommend a lockfile before MVP.

---

## F11. BLACKBOARD COMPLETENESS

`SimBlackboard` ([decisions/blackboard.py](../src/faer_dev/decisions/blackboard.py)) — **29 keys / 6 groups**.

| Group | Keys | Writers | Readers | Verdict |
|---|---|---|---|---|
| **Patient (8)** | `patient_severity, patient_primary_region, patient_secondary_regions, patient_mechanism, patient_is_polytrauma, patient_is_surgical, patient_triage, patient_id` | `casualty_factory.set_patient_context()` (L217) | `bt_nodes` reads `patient_severity`(L56), `patient_primary_region`(L76), `patient_is_surgical`(L98) | severity/region/is_surgical **live**; `secondary_regions, mechanism, is_polytrauma, triage, patient_id` **written-never-read** (dead intrinsic state, unless BT trees expanded) |
| **Facility (6)** | `facility_utilisation, facility_beds_available, department_queue_depth, department_capacity, fst_queue_depth, r1_beds_available` | `set_facility_context()` exists but **engine never calls it** (no `_blackboard.set` in engine beyond construction) | `bt_nodes` would read `fst_queue_depth` (DCS branch) | 🔴 **read-never-written / default-only** — the engine populates **no** live facility state. BT department routing has no real occupancy data → **missing intrinsic data source** |
| **Operational (4)** | `mascal_active, time_since_injury_minutes, time_awaiting_surgery_minutes, operational_context` | `casualty_factory` writes `mascal_active` (L225) | `bt_nodes` reads `mascal_active` (L115) | `mascal_active` live; the two `time_*` keys **written-never-read** (dead) |
| **Toggles (5)** | `bt_enabled_t4, _t1_surgical, _t1_medical, _t2, _dcs` | `set_toggle()` | `get_toggle()` / BT branch guards | live (config-time) |
| **Decisions (4)** | `decision_triage, decision_department, decision_dcs, decision_path` | `bt_nodes` (L202,226,247) | `observer.py:113` reads `decision_path`; `blackboard` properties (L166-178) | live (BT→observer) |
| **VOP reserved (2)** | `available_transport_modes, transport_clinical_capability` | none | none | 🔴 **reserved, written-never-read** (placeholder for Visual Operational Planner) |

**Capacity for new groups?** ✅ **Structural addition is trivial** — keys are plain dict entries merged into `ALL_KEYS` (L65). No hard limit. Adding a `_WEATHER_KEYS` / `_CONSUMABLE_KEYS` group is a ~5-line change. The **harder** problem is not capacity but **population**: the existing facility/department keys are already structurally present and still unfed by the engine, so adding more groups without an engine writer just adds more dead state. Department keys (`department_queue_depth`, `department_capacity`) are pre-registered for #4 and `FacilityInternalGraph.get_queue_depths()`/`get_capacities()` ([departments.py:96-108](../src/faer_dev/simulation/departments.py#L96)) exist to fill them — but the wiring is absent.

---

## F12. EVENT TYPE VOCABULARY

**Engine declares 21 types** in `KNOWN_EVENT_TYPES` ([engine.py:49](../src/faer_dev/simulation/engine.py#L49)). **`models.py` `EVENT_REGISTRY`** declares 22 fixed + a `_DEPT` dynamic pattern ([events/models.py:276](../src/faer_dev/events/models.py#L276)).

**Emitted in a real run** (`build_engine_from_preset("coin", seed=42)`, 1440 min, 200 cap) — **7 types**:
`ARRIVAL(31), FACILITY_ARRIVAL(40), TRANSIT_START(41), TRANSIT_END(40), TREATMENT_START(40), TREATMENT_END(38), DISPOSITION(28)`.
> ARRIVAL 31 = DISPOSITION 28 + in_system 3 — invariant holds modulo the 3 patients still mid-journey at the duration cutoff (run was not drained). Not a violation; flag a "drain to completion" mode for the acceptance harness.

**Has an emit site in engine code but conditional (not triggered in baseline):** `TRIAGE`(817), `HOLD_START`(738), `HOLD_RETRY`(824), `HOLD_TIMEOUT`(744), `PFC_START`(366), `PFC_END`(389), `PFC_CEILING_EXCEEDED`(801), `MASCAL_ACTIVATE`(581), `MASCAL_DEACTIVATE`(587), `{ROLE}_DEPT`(1039), `ATMIST_HANDOVER`(462), `NINE_LINER`(481). These fire only under congestion / MASCAL / `enable_department_routing` / `enable_atmist`.

**Phantom — declared but NO emit site anywhere:**
| Type | Declared in | Emitted? | Tag |
|---|---|---|---|
| **`DCS`** | engine KNOWN (L55) + models registry | ❌ **no `_log_event("DCS")` anywhere** | INTRINSIC state change (#28 DCS decision) — **the DCS decision can't be observed via events** |
| `QUEUE_ENTERED` | models only | ❌ never | SURFACE (forward-looking) |
| `HOLD_RELEASED` | models only | ❌ never | SURFACE (forward-looking; hold-release is implicit in loop exit) |
| `BT_DECISION` | models only | ❌ not in baseline (observer-emitted when BT active) | SURFACE (observability) |

Tagging the emitted/known set: **INTRINSIC state changes** = `ARRIVAL, TRIAGE, DISPOSITION, TRANSIT_*, TREATMENT_*, FACILITY_ARRIVAL, HOLD_*, PFC_*, MASCAL_*, {ROLE}_DEPT, DCS`. **SURFACE observations** = `ATMIST_HANDOVER, NINE_LINER, BT_DECISION, QUEUE_ENTERED` (handover/reporting artifacts).

**Biggest F12 risk for MVP:** `DCS` and `PFC_CEILING_EXCEEDED` are intrinsic decisions/ceilings that are either never emitted (`DCS`) or only conditionally emitted (`PFC_CEILING_EXCEEDED`) — so the "done" claims for #28 (DCS) and #33 (PFC ceiling) **cannot be verified from the event stream** in a default run. (Cross-ref Backward B7.)

---

## F13. TEST INFRASTRUCTURE INVENTORY

Framework: **pytest 9.0.2, plain `assert`** (no hypothesis, no custom harness). Layout: 6 flat test modules + `conftest.py`. 99 tests, 0.41s.

**(a) Fixture that runs the engine to completion and returns the event log?** ❌ **No.** `conftest.py` provides only **domain-object** fixtures (`sample_casualty`, `t1_surgical_casualty`, `sample_facility`, `role1_facility`, `sample_config`) + a `fixed_seed` + BT blackboard cleanup. There is **no run-to-completion fixture**. Tests that need a run call `build_engine_from_preset(...).run(...)` inline (e.g. `test_routing.py`).

**(b) Ensemble fixture?** ❌ **No.** `EnsembleBuilder` exists and is exercised in `test_analytics.py`, but there is **no fixture** returning aggregate output for assertion.

**(c) Property over the event stream — "no surgical casualty treated at a non-surgical facility"?** ❌ **Not writable as a passing assertion today**, on two counts:
1. The event store *can* be queried (`engine.event_store.events_of_type(...)`, `event_types`), so the **read mechanism exists**.
2. **But** routing ignores `has_surgery` entirely (F4), and `TREATMENT_*` events don't carry a capability field — so the property has *nowhere to plug in*: it would either trivially fail (capability is never enforced) or be unassertable (no `has_surgery` on the event). This is exactly the R16a gate.
*No existing test asserts a cross-event invariant; existing assertions are per-call equality (`legacy == extracted`) or count checks.*

**(d) Property over ensemble output — "golden-hour compliance rises with R1 beds"?** ❌ **Not writable.** Two blockers: (i) no fixture (b); (ii) `EnsembleBuilder` can't vary R1 bed count without on-disk YAML edits (F8 — no scenario-override param). The `golden_hour` metric *is* computed (seen in run metrics: `pct_within_60`), so the **output exists**; the **sweep mechanism does not**.

**(e) Framework/assertion style:** pytest plain asserts; equality/count-based; `pytest_generate_tests` parametrizes over triage/role enums ([conftest.py:160](../tests/conftest.py#L160)).

**F13 verdict (feeds A11):** the harness is **CORRECTNESS-CAPABLE for reads** (event store is queryable) but has a **HARNESS GAP** for behavioural acceptance: it lacks (1) a run-to-completion event-log fixture, (2) a parameter-sweep ensemble fixture, and (3) the intrinsic enforcement (#5) that would make capability assertions meaningful. Estimate: a thin `run_to_log()` + `sweep()` fixture pair (~40–60 LOC) closes (1) and (2); (3) is feature work (#5).

---

## FORWARD SYNTHESIS — greedy intrinsic-first marginal-cost ranking

| Rank | Feature | Layer | Marginal cost | Why first |
|---|---|---|---|---|
| 1 | **Wire `pfc.py` into engine** (#21/#31–33) | INTRINSIC | **Lowest** — module extracted, tested, just unimported; flip `enable_extracted_pfc` to a real branch | Highest value/cost ratio; unblocks PFC ceiling (#33) |
| 2 | **#5 capability-aware routing** | INTRINSIC | Low-moderate — seam exists in `_find_highest_reachable`; Facility objects in hand | Gates every capability sweep + the R16a acceptance test |
| 3 | Emit **`DCS`** + always-emit `PFC_CEILING_EXCEEDED` | INTRINSIC observability | Low | Makes #28/#33 verifiable from events (F12/B7) |
| 4 | **Acceptance harness** `run_to_log()` + `sweep()` fixtures | SURFACE (enabling) | ~40–60 LOC | Prerequisite for *all* behavioural MVP criteria (F13/R16) |
| 5 | **#1 multi-POI** + `ArrivalRecord.origin` | INTRINSIC | Moderate — thread origin through arrivals→engine; guard determinism | Arrival mechanism; gates #8, per-POI MASCAL |
| 6 | Config: read `threat_level`/`or_tables`/`icu_beds` + add `schema_version` | INTRINSIC-enabling | Moderate | Stop silent field-drop (F9); unblocks #10 |
| — | #44 ensemble CI / #45 sweep | SURFACE | — | **Cannot precede #5/#1** — sweep is only as good as the intrinsic features it varies |

**Surface features blocked on the above:** #43 mining (import-orphan + needs pm4py), #44/#45 ensemble/sweep (need #5 + scenario-override API), #53 Engine Room (needs the unfed facility/department blackboard keys populated).

---
*Forward agent complete. 13/13 answered. Awaiting Backward block.*
</content>
</invoke>
