# S1 PRE-BUILD INTERROGATION — ANSWERS

*Read-only interrogation, 2026-07-05. Every claim cited file:line against main
(`679ecc0`). Suite size confirmed: 114 tests collected.*

---

## Q1 — ROUTING PATH LIVENESS (fork risk)

**The 86/114 figure came from the EXTRACTED graph path, not the baseline's legacy
path — and the baseline never executes `_find_highest_reachable`.**

- **Provenance of 86/114:** MAAFI R16a (`docs/MAAFI/MAAFI_REDTEAM.md:225-231`) — a
  *custom* scenario (non-surgical R1+R2, surgical R3), 100% T1_SURGICAL arrivals,
  with "**both** routing toggles on". Both-on means
  `enable_extracted_routing=True` and `enable_graph_routing=True`, so per casualty
  the engine called `routing.get_next_destination(..., use_graph_routing=True)`
  (`engine.py:680-684`), which calls `_find_highest_reachable` (`routing.py:128`).
- **Baseline effective toggle values:** `coin.yaml` contains no toggles section and
  the builder never reads toggles from YAML (`builder.py:83-161` — toggles is a
  parameter only). `build_engine_from_preset(toggles=None)` (`builder.py:232-258`)
  → `PolyhybridEngine(toggles=None)` → `SimulationToggles()` defaults:
  **`enable_extracted_routing=False`** (`mode.py:53`),
  **`enable_graph_routing=False`** (`mode.py:58`). The F0 harness passes
  `toggles=None` by default (`tests/harness.py:36,49-51`), so the golden trace
  (O1) also runs at these defaults.
- **Function that actually executes per casualty at baseline:** the **legacy
  module-level role-walk** `engine._get_next_destination` (`engine.py:84-121`),
  selected at `engine.py:686-688`.

**Fork risk confirmed:** a filter placed only in `_find_highest_reachable` is dead
code under baseline toggles. The killer test must either set both toggles
explicitly (as R16a did) or the filter must live in every path the test exercises.

---

## Q2 — STRANGLER EQUIVALENCE (fork risk)

**Yes — 12 of the 114 tests assert legacy ≡ extracted (or role-walk ≡ graph)
routing equivalence.** Filtering one path only would break them.

Function-level (legacy engine walk vs extracted module):

| Test | Location | Asserts |
|---|---|---|
| `test_matches_legacy_from_poi` | `tests/test_routing.py:116-124` | `engine._get_next_destination(...) == routing.get_next_destination(...)` from POI, parametrised over all 5 triage categories |
| `test_matches_legacy_from_r1` | `tests/test_routing.py:126-135` | same, from R1 |

Function-level (extracted role-walk vs graph mode):

| Test | Location | Asserts |
|---|---|---|
| `test_linear_graph_matches_legacy` | `tests/test_routing.py:241-255` | `use_graph_routing=False` vs `True` equal on the linear chain, all triages |
| `test_linear_graph_matches_legacy_from_r1` | `tests/test_routing.py:257-271` | same, from R1 |

Full-engine toggle equivalence:

| Test | Location | Asserts |
|---|---|---|
| `test_identical_metrics_seed42` | `tests/test_routing.py:166-173` | routing toggle OFF vs ON: `total_arrivals`, `completed`, `in_system`, `outcomes` equal |
| `test_identical_metrics_seed99` | `tests/test_routing.py:175-185` | same at seed 99 (arrivals/completed/outcomes) |
| `test_preset_coin_equivalence` | `tests/test_routing.py:199-217` | coin preset, OFF vs ON: arrivals/completed/outcomes equal |
| `test_linear_toggle_equivalence` | `tests/test_routing.py:322-338` | extracted ON, graph OFF vs ON: arrivals/completed/outcomes equal |
| `test_both_toggles_combined` | `tests/test_metrics.py:154-167` | routing+metrics ON vs all-OFF: arrivals/completed/outcomes equal |
| `test_all_toggles_combined` | `tests/test_emitter.py:189-204` | routing+metrics+emitter ON vs all-OFF |
| `test_metrics_identical_seed42` / `_seed99` | `tests/test_phase1_integration.py:50-66` | ALL_ON vs ALL_OFF: metrics equal incl. per-facility dict |
| `test_event_counts_identical` | `tests/test_phase1_integration.py:68-77` | ALL_ON vs ALL_OFF: per-type event counts equal |

Note `ALL_ON` (`tests/test_phase1_integration.py:26-33`) sets
`enable_extracted_routing=True` but NOT `enable_graph_routing`, so the phase-1
tests compare legacy walk vs extracted walk, both on coin. A capability filter
must be applied to **all three** implementations (legacy `engine.py:84-121`,
extracted walk `routing.py:138-149`, graph `routing.py:127-136`) identically, or
be toggle-gated so these tests keep comparing like-with-like.

---

## Q3 — CONTROL FLOW + R1-ALPHA MECHANISM

Execution order inside `get_next_destination` (`routing.py:100-149`):

1. **Clinical short-circuits** — `routing.py:119-125`: T3 at R1/R2 → `None`;
   T4 → `None`. No candidates enumerated yet.
2. **Graph branch** (`use_graph_routing=True`, `routing.py:127-136`):
   - **Candidate enumeration** is delegated to `_find_highest_reachable`
     (called at `routing.py:128`; body at `routing.py:88-96`): walk `ROLE_ORDER`
     highest→lowest, inner loop over `network.facilities.items()`
     (`routing.py:92-96`), reachability via `nx.has_path` (`routing.py:95`).
   - **`bypass_role1` consulted** three times: `routing.py:77-84` (subgraph view
     excluding other R1 nodes), `routing.py:90-91` (skip R1 as a target role),
     and again inside `get_route` via `patient.bypass_role1`
     (`topology.py:63-68` — edges into R1 nodes get infinite weight).
   - **Edge weights enter** at `routing.py:133` → `network.get_route` →
     `nx.dijkstra_path` over `weight` (`topology.py:70-76`); weights are
     `base_time × (1 + congestion)` (`topology.py:50-56`, `topology.py:98-104`).
   - **Weight comparison overrides `bypass_role1`** at `routing.py:133-136`,
     committed by `return path[1]` at **`routing.py:136`** (the comparison
     itself executes at `topology.py:74-76`). Mechanism: for a NON-bypass
     casualty (`bypass_role1=False`, i.e. T2/T3), nothing forces an R1 visit.
     On coin, `_find_highest_reachable` returns R3-THEATRE; Dijkstra then
     compares POI→R2-MAIN (45 min, `coin.yaml:62-66`) against
     POI→R1-ALPHA→R2-MAIN (20+35 = 55 min, `coin.yaml:56-72`) and picks the
     direct edge — so `path[1]` is R2-MAIN for *every* casualty and R1-ALPHA
     receives zero traffic (confirmed live+headless, `HANDOVER.md` discovery 2).
     The per-casualty `bypass_role1=False` decision is thereby overridden for
     everyone by edge weights — the R1-ALPHA starvation mechanism.
3. **Legacy branch** (`use_graph_routing=False`, `routing.py:138-149`):
   candidates enumerated by role walk lowest→highest (`routing.py:140-148`),
   `bypass_role1` consulted at `routing.py:142`, first-match on
   `graph.has_edge` at `routing.py:147`. **Edge weights never enter** this
   branch.

---

## Q4 — FLAG PAIRING + ORDER

**Order — confirmed.** `decisions = _extracted_triage_decisions(patient)` runs at
`engine.py:655` and `patient.requires_dcs = decisions["requires_dcs"]` at
`engine.py:657`, both BEFORE the journey loop (`engine.py:676`) that calls
`get_next_destination` / `_find_highest_reachable` (`engine.py:680-684`). The
rule: `requires_dcs=True` iff `patient.triage == TriageCategory.T1_SURGICAL`
(`routing.py:47-50`); every other category leaves the default `False`
(`routing.py:43`). **Caveat:** a PFC-ceiling re-triage can promote
`patient.triage` to T1_SURGICAL mid-journey (`engine.py:807-810`) WITHOUT
recomputing `decisions` or `patient.requires_dcs` — the decisions dict is
computed once per journey at `engine.py:655`.

**Facility side (`schemas.py:162-165`):** `has_surgery: bool = Field(default=False)`
(:162), `has_blood` (:163), `has_imaging` (:164), `has_lab` (:165) — all `bool`,
schema default `False`. YAML spellings are the identical snake_case keys
(`coin.yaml:40-41`, `coin.yaml:50-52`). Parse behaviour (`builder.py:201-203`):
only `has_surgery`, `has_blood`, `has_imaging` are read from YAML (via
`_parse_bool(fac_config.get(..., False))`); **`has_lab` is never parsed** — it is
always `False` post-parse regardless of YAML. Default for any flag absent from
config: `False`.

**The pairing that enforces "surgical":** TODAY, none — no routing code reads any
capability flag (R16a, `MAAFI_REDTEAM.md:225-231`). The as-built flag pair S1
must wire per AC-5.1 (`docs/MVP/MVP_ACCEPTANCE.md:69-75`) is:

> casualty **`requires_dcs`** (`schemas.py:114`; written `routing.py:50`, copied
> to the patient at `engine.py:657`) ↔ facility **`has_surgery`**
> (`schemas.py:162`).

AC-5.1 names the casualty flag "`needs_surgery`" — no field of that name exists
anywhere; `requires_dcs` is the as-built equivalent. (The blackboard key
`patient_is_surgical`, `blackboard.py:23`, is a separate factory-side input on
the inverted path, `casualty_factory.py:222` — it is not the routing flag.)

---

## Q5 — EMPTY CAPABLE-SET BEHAVIOUR

**Today, "nothing reachable" returns `None` — never an exception in practice.**
Legacy: `engine.py:121`. Extracted walk: `routing.py:149`. Graph:
`routing.py:131-132` when `_find_highest_reachable` returns `None`
(`routing.py:97`). `get_route`'s `NoPathError` (`topology.py:77-80`) is
pre-empted by the `nx.has_path` check at `routing.py:95`; nothing in
`_patient_journey` catches it, so if it ever fired it would kill that SimPy
process — but it is unreachable given the pre-check.

**What the engine does with `None`** (`engine.py:690-704`): treats the journey as
COMPLETE — T4 → `DECEASED`, T3 → `RTD`, everything else → **`STRATEVAC`** — then
`_finalize_patient` emits a normal DISPOSITION and breaks. `None` is a
success-shaped disposition, not an error. (The distinct `ROUTING_FAILURE`
outcome exists only for a missing direct edge after a destination was chosen,
`engine.py:895-918`.)

**Post-filter:** "reachable but none capable" returning `None` hits EXACTLY that
same journey-complete path — a T1_SURGICAL casualty would be silently disposed
STRATEVAC at the POI with no distinguishing event or failure signal.

**Baseline reachability:** coin has a single POI (`coin.yaml:23-27`). Surgical
facilities R2-MAIN (`coin.yaml:40`) and R3-THEATRE (`coin.yaml:50`) are both
reachable from POI-1 — directly (`coin.yaml:62-66`), via R1-ALPHA
(`coin.yaml:56-72`), and onward R2→R3 (`coin.yaml:74-78`). **No casualty hits an
empty capable set in the baseline scenario.**

---

## Q6 — CAPABILITY DECLARATIONS AS-BUILT

**Baseline coin** (`coin.yaml:22-53`), effective post-parse values via
`builder.py:195-204`:

| Facility | YAML declares | Effective `has_surgery`/`has_blood`/`has_imaging`/`has_lab` |
|---|---|---|
| POI-1 | nothing | False / False / False / False |
| R1-ALPHA | nothing | False / False / False / False |
| R2-MAIN | `has_surgery: true`, `has_blood: true` (`coin.yaml:40-41`) | **True / True** / False / False |
| R3-THEATRE | `has_surgery/blood/imaging: true` (`coin.yaml:50-52`) | **True / True / True** / False |

Parse caveat: `or_tables`, `icu_beds`, `ventilators` and `has_lab` in YAML are
**silently dropped** — the builder constructs `Facility()` with only id, name,
role, beds, coordinates and the three parsed flags (`builder.py:195-204`), so
R2-MAIN's `or_tables: 2` (`coin.yaml:39`) is effectively 0.

**Oracle fixtures:**

- **O4** (`tests/test_hold_gate_integration.py:21-26`): `deepcopy` of the coin
  preset, edits only R2-MAIN `beds=1` + arrival rate — capability flags
  identical to baseline above.
- **O5** (`tests/test_oracles.py:151-172`): inline dict — POI-1, R1-A, R1-B
  declare nothing → all False; R2-MAIN declares `has_surgery: True`,
  `has_blood: True` (`tests/test_oracles.py:163`).
- **O7 does not exist.** The oracle set is O1–O6 (`tests/test_oracles.py:1-7`;
  grep of docs/ and tests/ finds no "O7"). Assuming O6 was meant: its fixture is
  a `deepcopy` of coin with arrival-parameter edits only
  (`tests/test_oracles.py:217-230`) — capabilities identical to baseline. (O2
  and O3 are likewise coin-derived: `tests/test_oracles.py:56-58`, `:97-103`.)

**Consequences asked for:** the AC-5.2 all-surgical control is an
**edit-of-baseline** — set `has_surgery: true` on R1-ALPHA in a deepcopied coin
dict (POI-1 has `beds: 0` so it never treats; no queue is created for it,
`engine.py:259-274`). On patching: in every coin-derived fixture (O1 golden, O2,
O3, O4, O6) and in O5, T1_SURGICAL casualties bypass R1 to a `has_surgery=True`
R2, and the casualties that do visit non-surgical R1s are T2/T3 with
`requires_dcs=False` — so a `requires_dcs ↔ has_surgery` filter changes no
routing decision in any existing fixture and **no oracle fixture should need
patching** (to be verified by running the suite at build time, not assumed).

---

## Q7 — WRITER CONTRACT

**Signature** (`blackboard.py:151-160`):

```python
def set_facility_context(
    self,
    utilisation: float = 0.0,
    fst_queue: int = 0,
    mascal_active: bool = False,
) -> None:
```

Writes exactly three keys (`blackboard.py:158-160`):
`"facility_utilisation"` ← `utilisation`, `"fst_queue_depth"` ← `fst_queue`,
`"mascal_active"` ← `mascal_active`.

**Namespacing:** py-trees global blackboard, root namespace — keys are stored as
`/facility_utilisation`, `/fst_queue_depth`, `/mascal_active` (verified
empirically against `py_trees.blackboard.Blackboard.storage`). The client name
(`"sim"`/`"engine"`, `blackboard.py:91-92`) does NOT namespace keys; every
`SimBlackboard` instance and every BT node Client shares the same global storage.

**Callers today: zero.** No call site of `set_facility_context` exists in `src/`
or `tests/` (grep).

**Readers today:**

| Key | Reader | Expected shape |
|---|---|---|
| `facility_utilisation` | `CheckFacilityUtilisation` — `bt_nodes.py:126-136` (READ registered :131, compared `> threshold` :135) | float |
| `mascal_active` | `CheckMASCALActive` — `bt_nodes.py:104-117` (read :115, truthiness) | bool |
| `fst_queue_depth`, `facility_beds_available`, `department_queue_depth`, `department_capacity`, `r1_beds_available` | **no readers anywhere in src/ or tests/** (grep) | shapes exist only as defaults at `blackboard.py:28-35` (int 0; dicts for the `*_available`/`*_depth`/`*_capacity` maps) |

So: for everything except `facility_utilisation` and `mascal_active`, **readers
do not yet exist and the S1 writer defines the contract.** One conflict to note:
`mascal_active` already has a second writer — the inverted-factory path sets it
per casualty (`casualty_factory.py:225`, `bb.set("mascal_active",
arrival.is_mascal)`) — which is presumably what the gate reviewer's
"`mascal_active` exclusion" directive refers to.

---

## Q8 — EVENT SUFFICIENCY + SUBSCRIBER SAFETY

**Event types fired** — engine emits the string types in `KNOWN_EVENT_TYPES`
(`engine.py:49-57`): ARRIVAL, TRIAGE, TRANSIT_START, TRANSIT_END,
FACILITY_ARRIVAL, TREATMENT_START, TREATMENT_END, DISPOSITION,
MASCAL_ACTIVATE/DEACTIVATE, HOLD_START/RETRY/TIMEOUT, PFC_START/END,
PFC_CEILING_EXCEEDED, `{ROLE}_DEPT` (dynamic), DCS, ATMIST_HANDOVER, NINE_LINER.
Typed payloads (`events/models.py:276-306` registry; envelope
`models.py:37-45` = sim_time, event_type, casualty_id, facility_id, triage,
event_id, source, wall_time, metadata):

- ARRIVAL→`CasualtyCreated` (mechanism, severity, recommended_triage,
  bypass_role1, **requires_dcs**, priority — `models.py:53-62`)
- TREATMENT_START→`TreatmentStarted` (resource_type, wait_time, department —
  `models.py:116-121`); TREATMENT_END→`TreatmentCompleted` (duration,
  department — `models.py:125-129`)
- FACILITY_ARRIVAL→`FacilityArrival` (envelope only — `models.py:109-112`)
- TRANSIT_START/END (origin, destination, transport_mode / transit_time, reason
  — `models.py:88-101`); DISPOSITION→`OutcomeRecorded` (outcome, total_time,
  reason — `models.py:75-80`); hold/PFC/MASCAL classes at `models.py:155-227`.
- No event carries any capability field (R16a: TREATMENT_START metadata is empty
  of capability — `MAAFI_REDTEAM.md:227-228`).

**Occupancy derivable from events?** Yes, exactly, for bed-holding: the SimPy bed
is acquired immediately before TREATMENT_START is emitted (`engine.py:1146-1157`)
and released immediately after TREATMENT_END (context-manager exit,
`engine.py:1146-1178`), so live bed occupancy per facility =
`#TREATMENT_START − #TREATMENT_END` at that facility. Facility entry is marked by
FACILITY_ARRIVAL (`engine.py:957`), and department is carried on
TREATMENT_START/END and `*_DEPT` events, so waiting counts and department state
are also event-derivable. If a subscriber instead wants the engine's own live
number (`queue.count / queue.capacity`, `engine.py:613-616`), it must capture the
engine in a closure — **reachable and safe**: the bus is synchronous
(`bus.py:6-8`), and this is the established house pattern (O3 reads
`engine.patients` inside its callback, `tests/test_oracles.py:120-125`; O5 calls
`engine.network.update_congestion`, `tests/test_oracles.py:194-196`). Note
`Facility.current_occupancy` (`schemas.py:169`) is never written by the engine —
`queue.count` is the live figure, not that field.

**Invocation order deterministic:** yes — wildcard subscribers first in
subscription order, then type-matched subscribers in subscription order
(`bus.py:59-80`); re-entrant publishes are queued FIFO and processed after the
current pass (`bus.py:45-57`). Exceptions are logged and swallowed, subscriber
stays attached (`bus.py:62-80`).

**AnalyticsEngine._on_event reads no blackboard key** — it only dispatches the
event to registered views (`analytics/engine.py:46-56`); the module imports no
py-trees/blackboard ("Never reads engine state", `analytics/engine.py:3-4`).

---

## Q9 — REGEN + FIXTURE MECHANICS

**O1 regen invocation as built:** `pytest --regen-golden` — the flag is
registered in `tests/conftest.py:24-39` and exposed as the `regen_golden`
fixture (`conftest.py:36-39`). The only regen site is `test_o1_golden_trace`
(`tests/test_oracles.py:30-45`): when the flag is set it rewrites
`tests/golden/coin_s42.json` (`json.dumps(log, indent=2, default=str)`) from
`run_to_log("coin", duration_min=480.0, max_patients=50, drain=False)`, then
still asserts digest equality. Narrowed form:
`pytest tests/test_oracles.py::test_o1_golden_trace --regen-golden`.

**Trace size:** 31,438 bytes / 1,254 lines / **99 canonical events, 13
casualties** (18 TRANSIT_START, 15 TRANSIT_END, 15 FACILITY_ARRIVAL,
15 TREATMENT_START, 14 TREATMENT_END, 13 ARRIVAL, 9 DISPOSITION).

**Diff tooling:** none for golden files. `scripts/regression.py` compares two
in-memory engine runs (`compare_events` `regression.py:28-46`,
`compare_engines`/`assert_identical` `regression.py:98-158`) — it does not read
or diff JSON fixtures. Golden review is a plain `git diff` of the
pretty-printed JSON; at 99 events / indent=2 that is line-oriented and
reviewable.

**Reviewability verdict:** a raw diff of an 86-casualty re-route would indeed be
unreviewable — but that situation does not arise here. The 86/114 came from the
custom R16a scenario, not the golden run; the golden trace is 13 casualties at
default (legacy-routing) toggles, where T1_SURGICAL already bypasses to the
surgical R2-MAIN, so a `requires_dcs ↔ has_surgery` filter is expected to
produce a **zero-line golden diff**. Any non-empty golden diff at default
toggles would mean the legacy path's behaviour changed — which Hard Rule 2
requires toggle-gating, not regenerating.

**F0 house pattern for test fixtures:** no YAML under `tests/` — `tests/data/`
does not exist (the `conftest.py:69-71` fixture pointing at it is unused).
The pattern is: (a) `copy.deepcopy(get_preset_raw("coin"))` + in-place dict
edits (`tests/test_oracles.py:56-58`, `:97-103`, `:220-230`;
`tests/test_hold_gate_integration.py:21-26`); (b) fully inline scenario dicts
for purpose-built topologies (`tests/test_oracles.py:151-172`); (c)
programmatic engine assembly via `add_facility`/`add_route` for unit-scale
networks (`tests/test_routing.py:43-66`). S1 tests should use inline dicts or
deepcopied presets — no YAML fixture files.
