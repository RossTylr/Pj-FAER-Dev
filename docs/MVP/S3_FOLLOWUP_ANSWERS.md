# S3 FOLLOW-UP INTERROGATION (round B) — mechanism-agnostic seam census

*Read-only reconnaissance, 21 July 2026. Answers Q11–Q19, continuing the numbering
from `docs/MVP/S3_PREBUILD_ANSWERS.md` (Q1–Q10). Every claim is cited `file:line`
against HEAD `5a78f82`; the Jul-7 round was treated as hints only and every line
number was re-verified at this HEAD. No `src/` or `tests/` change was made — the
supporting probes ran from a scratchpad directory outside the repo and are
reproduced inline where they carry a result.*

**Standing constraint:** BUILD_S3 remains UNAUTHORISED. This file plus the signed
ROUTING_SEMANTICS_NOTE are its inputs, not its licence.

---

## 0 — PRE-FLIGHT VERIFICATION

| Item | Required | Observed | Verdict |
|---|---|---|---|
| HEAD | `5a78f82` | `5a78f82 feat(tooling): uv migration executed …` | ✅ |
| Tree | clean | `git status --porcelain` → empty | ✅ |
| Suite | 163 green | `uv run pytest -q` → **163 passed in 1.51s** | ✅ |
| Probe | ALL PASS | `uv run python scripts/check_claude_md.py` → `check_claude_md: ALL PASS ✓` | ✅ |

Canonical invocation is `uv run <cmd>` (CLAUDE.md Rule 9; `AGENTS.md:19`). No
deviation; proceeding.

---

## Q11 — ARRIVAL PROCESS ANATOMY FOR N POIs

### 11.1 `ArrivalProcess` full state

Constructor `arrivals.py:103-130`. Instance state:

| Attribute | Line | Note |
|---|---|---|
| `self.env` | `arrivals.py:112` | the shared `simpy.Environment` |
| `self.config` | `:113` | `ArrivalConfig` (below) |
| `self.rng` | `:114-119` | **unconditional `ValueError` when `None`** (S2-D D4) |
| `self.keyed_rng` | `:122` | `KeyedRNGRoot` or `None` (shared mode) |
| `self.on_arrival` / `self.on_mascal` | `:123-124` | the two engine callbacks |
| `self.arrivals: list[ArrivalRecord]` | `:126` | per-instance arrival log |
| `self.mascal_events: list[MASCALEvent]` | `:127` | per-instance MASCAL log |
| `self._mascal_counter` | `:128` | per-instance; **sources `mascal_id`** (`:226`) |
| `self._max_arrivals` | `:129` | lifetime cap, set at `start()` |
| `self._started` | `:130` | idempotence latch (`:142-144`) |

`ArrivalConfig` fields (`arrivals.py:24-44`): `base_rate_per_hour` (2.0),
`mascal_enabled` (True), `mascal_rate_per_hour` (0.1), `mascal_size_mean` (15.0),
`mascal_size_std` (5.0), `mascal_size_min` (5), `mascal_size_max` (30),
`mascal_duration_minutes` (20.0); plus the two derived per-minute properties
`:38-44`. Context presets at `arrivals.py:48-73`.

**RNG usage — four draw sites, all system-axis:**

| Site | Line | Purpose | Draw |
|---|---|---|---|
| base inter-arrival | `arrivals.py:156-163` | `ARRIVALS` | `exponential(1/base_rate_per_minute)` |
| MASCAL inter-event gap | `:178-185` | `MASCAL_GAP` | `exponential(1/mascal_rate_per_minute)` |
| MASCAL cluster size | `:201-212` | `MASCAL_SIZE` | `normal(mean, std)`, clamped `:213-216` |
| MASCAL offsets | `:228-235` | `MASCAL_OFFSETS` | **one array draw per cluster**, `uniform(0, duration, size=size)` |

Each site has an `if self.keyed_rng is not None: … else: self.rng.…` fork — the
shared-mode legacy path is intact behind the fork, not deleted.

**MASCAL ownership is inside `ArrivalProcess`, not the engine.** `start()`
(`arrivals.py:137-148`) spawns `_base_arrival_process` unconditionally and
`_mascal_event_process` **iff `config.mascal_enabled`** (`:147-148`). Each MASCAL
parent then spawns its own `_mascal_cluster_process` (`:197`). So the
Neyman-Scott generator is a property of the arrival process instance: **N
ArrivalProcess instances ⇒ N independent MASCAL parent processes.**

### 11.2 How the engine wires it

There are **two construction sites, and one of them is dead code**:

- `engine.py:1374-1384` — the live site, inside `run()`. Guarded by
  `if self._poi_id and not self._arrivals_started`; constructs exactly ONE
  `ArrivalProcess`, calls `.start(max_arrivals=max_patients)`, sets
  `_arrivals_started = True`.
- `engine.py:1321-1339` — `PolyhybridEngine._arrival_process(poi_id, max_arrivals)`,
  a SimPy generator that duplicates the same construction and then
  `yield self.env.timeout(float("inf"))`. **It has zero callers**
  (`grep -rn "_arrival_process\b" src/ tests/ notebooks/ scripts/` returns only
  its own definition and the unrelated `arrivals.py:146/150`
  `_base_arrival_process`). Any multi-POI wiring must decide whether to revive or
  delete it; leaving a stale second wiring path is the silent-drift shape this
  programme keeps excavating.

`run(poi_id=...)` resolution order:

1. `engine.py:1361-1366` — an explicit `poi_id` is accepted, but **raises
   `ValueError` if it changes after arrivals started** ("poi_id changed from … to
   … after arrivals started"). Note the guard fires only on *change*, never on
   *plurality*.
2. `engine.py:1368-1372` — with no `poi_id`, scan `self.network.facilities` and
   take the **first** node with `role == Role.POI` (dict insertion order).
3. `engine.py:1374-1384` — bind the single `ArrivalProcess`.

Callback path: `on_arrival=self._handle_arrival` (`engine.py:1379`) →
`_handle_arrival` (`engine.py:615-647`) → `poi_id = self._poi_id;
self.env.process(self._patient_journey(patient, poi_id))` (`engine.py:645-647`).
**The start facility is read from engine state, not from the `ArrivalRecord`** —
`ArrivalRecord` carries only `time`, `is_mascal`, `mascal_id`
(`arrivals.py:85-91`). This is the single most load-bearing seam for multi-POI:
either `ArrivalRecord` gains a source field, or the callback is closed over the
POI id per instance.

### 11.3 What a SECOND instance collides with

| Collision | Mechanism | Severity |
|---|---|---|
| **Arrival callback** | `_handle_arrival` reads `self._poi_id` (`engine.py:645`), a scalar. Two instances ⇒ both cohorts start at the same POI. | **Fatal to the feature** — silently, no error |
| **RNG stream keys** | All four draw sites key on the bare purpose literal (11.4). Two instances share one occurrence counter. | **Fatal to CRN** — demonstrated below |
| **MASCAL detector** | ONE global `MASCALDetector` (`engine.py:246-248`), fed by every arrival regardless of source (`engine.py:618`). | Semantic — see Q15 |
| **Casualty factory `_counter`** | One shared factory instance; `_counter` is per-factory (`casualty_factory.py:65`, `:226`). Interleaved POIs ⇒ interleaved uids. | Identity — see Q12 |
| **`env` scheduling / tie order** | Both instances `env.process(...)` at `start()`. Simultaneous arrivals break ties by process-creation order; `EventStore.query()` sorts by `sim_time` with Python's **stable** sort (`store.py:87`), so emission order survives into the canonical log. | O6 hazard — its docstring already flags re-assertion after step 3 (`test_oracles.py:238-240`) |
| **`_arrivals_started` latch** | Scalar (`engine.py:237`, set `:1384`); guards one process, not N. | Wiring |
| **`engine.arrival_process`** | Scalar attribute (`engine.py:234`, assigned `:1375`). `tests/harness.py:73-75` reaches into `engine.arrival_process._max_arrivals` to close the arrival window. | **Harness coupling** — a list/dict of processes breaks `run_to_log`'s drain path |

### 11.4 The stream-key literals, EXACTLY as constructed

`KeyedRNGRoot.system_draw` (`rng.py:165-167`) is one line:

```python
def system_draw(self, purpose: RNGPurpose) -> np.random.Generator:
    """System-axis draw: the stream name is the purpose's wire name."""
    return self.draw(purpose.value, purpose)
```

So **the entity-id string IS the enum's value**, verbatim. Enum values at
`rng.py:53-57`:

| Purpose | Enum value (= entity-id literal) | `_PURPOSE_INDEX` (`rng.py:60-62`) |
|---|---|---|
| `RNGPurpose.TRANSIT` | `"transit"` | 11 |
| `RNGPurpose.ARRIVALS` | `"arrivals"` | 12 |
| `RNGPurpose.MASCAL_GAP` | `"mascal_gap"` | 13 |
| `RNGPurpose.MASCAL_SIZE` | `"mascal_size"` | 14 |
| `RNGPurpose.MASCAL_OFFSETS` | `"mascal_offsets"` | 15 |

The one exception is TRANSIT, which does **not** use `system_draw`: `transport.py:303-305`
builds its entity string by hand as `f"transit:{mode.name}"` (i.e. `"transit:GROUND"`,
`"transit:ROTARY"`, `"transit:FIXED_WING"`) while keeping purpose `TRANSIT`. That
is the existing precedent for a scoped system-axis entity string — a per-POI
arrival key would be the same pattern applied to a second axis.

All five are in `_SYSTEM_AXIS` (`rng.py:68-74`), so they root on `self._key`
(master seed), not the identity key (`rng.py:146`). The entity string enters as
`counter[3] = blake2b-64(entity_id)` (`rng.py:77-81`, `:145`).

**Would per-POI keys move coin's bytes? Yes if applied unconditionally; no if the
bare literal is preserved for the designated POI.** Measured:

```
blake2b64('arrivals')       = 15893502557642533909
blake2b64('arrivals:POI-1') =  3007641973401867167
entity 'arrivals'       occurrence 0 → exponential(1.0) = 0.6987498762097039
entity 'arrivals:POI-1' occurrence 0 → exponential(1.0) = 0.6550553398843177
```

The 0.69875 value is not incidental: at coin's 1.5/h the scale is 40 min, and the
golden's first ARRIVAL is at `sim_time` 27.9499… = 40 × 0.69875. **Namespacing the
key unconditionally shifts every arrival time in the golden trace.**

**Conversely, the bare literal can be preserved.** A scheme that keys POI #1 as
`"arrivals"` and POI #2..N as `"arrivals:<poi_id>"` reproduces the single-POI
sequence byte-for-byte — verified: the counterfactual bare-literal series
`[27.949995, 38.382329, 64.838677, 89.170144, 104.021908, 168.270935]` is
identical to the live single-instance run. Whether that asymmetry is acceptable
is a design ruling, not a fact; but the *option* exists and is free.

**What is NOT optional: two concurrent instances on one key destroy the pairing.**
Two `ArrivalProcess` objects sharing one `KeyedRNGRoot` and the bare `"arrivals"`
key were run against one `simpy.Environment` (public API only, no `src/` change):

```
ONE process (POI-A) : 27.949995  38.382329  64.838677  89.170144 104.021908 168.270935
TWO processes, POI-A: 27.949995  52.281462  82.638196 137.518483 149.050275 199.181727
TWO processes, POI-B: 10.432334  36.888682  51.740446 115.989472 131.268724 133.804870
arrivals draw count: 6 → 12       POI-A identical to single-POI run: False
```

Only the first draw survives. The occurrence counter is per `(entity, purpose)`
(`rng.py:156-158`), so a shared entity string means the two generators alternately
consume the same ladder — reintroducing exactly the stream-position dependence the
keyed architecture removed (Hard Rule 8's addendum: "per-entity keyed streams" is
load-bearing). **Per-POI system-axis stream keys are a correctness requirement of
multi-POI, not a refinement.** The same argument applies unchanged to
`MASCAL_GAP`, `MASCAL_SIZE` and `MASCAL_OFFSETS`, since each ArrivalProcess owns
its own MASCAL parent process (11.1).

---

## Q12 — WHO CONSUMES GLOBAL ARRIVAL ORDER

### 12.1 The census

**Consumer 1 — the factory counter (the uid).** `LegacyCasualtyFactory._counter`
increments at `casualty_factory.py:78` and is rendered by `_generate_id`
(`:126-130`): `f"{self.id_prefix}-{self._counter:04d}"` when a prefix is set, else
`f"CAS-{self._counter:04d}"`. The inverted factory is identical
(`:239`, `:297-300`). The engine passes **no** `id_prefix` today (the two
`create_factory` calls at `engine.py:189-197` and `:199-204` supply none), so
every casualty is `CAS-NNNN` and NNNN *is* the global arrival ordinal.

**Consumer 2 — the MASCAL cluster id.** `ArrivalProcess._mascal_counter`
(`arrivals.py:128`, incremented `:217`, read `:226`) sources `ArrivalRecord.mascal_id`
(`:250`) → `Casualty.mascal_event_id` (`casualty_factory.py:116`, `:287`;
schema `schemas.py:90`). Per-instance, so N processes would each restart at 1 —
a collision under multi-POI.

**Consumer 3 — simultaneity tie order.** `EventStore.query()` returns
`sorted(results, key=lambda e: e.sim_time)` (`store.py:87`) — a **stable** sort, so
events tied on `sim_time` keep insertion (= emission) order. O6
(`test_oracles.py:233-260`) asserts that order is reproducible across two seed-42
runs, including the explicit `order_a == order_b` check on tied casualty ids
(`:256-260`). Interleaving two arrival processes changes which process emits first
at a tie, so O6's *content* changes even though its *property* (reproducibility)
should hold. Its own docstring already names this: "Re-assert this oracle after
step 3 (multi-POI) lands — concurrent arrival generators are the hazard it guards
(C5)" (`test_oracles.py:238-240`).

**Non-consumers, checked and cleared:**

- **Metrics** — `total_arrivals` is a count, not an ordinal
  (`metrics.py:74`; legacy twin `engine.py:1432`). Facility, outcome and
  golden-hour blocks (`metrics.py:98-133`) are all aggregations over sets.
- **Analytics views** (`analytics/views.py`) — `OutcomeView` is a `Counter`
  (`:26-31`); `FacilityLoadView` is a per-facility increment/decrement
  (`:52-65`); `GoldenHourView` keys a dict by `casualty_id` (`:91-100`). None
  reads an ordinal. `AnalyticsEngine._on_event` (`analytics/engine.py:46-56`)
  dispatches in registration order and swallows exceptions.
- **O6** depends on tie *order*, not on the arrival *ordinal* — see above.
- **Mining** — `_extract_facility_waits` (`mining.py:295-321`) pairs
  `FACILITY_ARRIVAL`→`TREATMENT_START` within one journey; `mining.py:250-262`
  scans a journey for the first `"R2"/"R3"/"R4"` substring in `facility_id`.
  Journey-local, ordinal-free.
- **Replay** — `ReplayEngine._apply_event` (`replay.py:111-141`) dispatches by
  `event_type` only.
- **Roster** — `roster_row` (`data/roster.py:39-49`) carries `casualty_id` but no
  ordinal, spawn time or MASCAL provenance (removed at S2-D D2, `:33-37`).

### 12.2 What observably changes when two POIs interleave

1. **The uid↔person mapping.** `CAS-0007` becomes a different person, because the
   shared `_counter` now interleaves two cohorts. Since the identity key is
   blake2b-64 of the uid *string* (`rng.py:77-81`), a different uid ⇒ a different
   Philox counter word ⇒ **every identity draw for that casualty changes**:
   triage, mechanism, regions, severity, polytrauma, frailty threshold.
2. **Roster digest** (`roster_digest`, `data/roster.py:52-54`) changes, since rows
   change and are appended in creation order (`engine.py:641-643`).
3. **Canonical log digest** changes (ARRIVAL payloads carry `triage`, `severity`,
   `injury_mechanism`, `recommended_triage` — `engine.py:736-743`).
4. **`mascal_event_id` collides** across POIs (12.1, consumer 2).
5. **I-2's cross-config comparison stays valid** only if the *same* POI set is used
   in both arms — I-2 compares config A vs C at a fixed scenario
   (`test_rng_keyed.py:115-121`), so it is unaffected as long as multi-POI is a
   scenario property, not a toggle.

### 12.3 Consequences of `id_prefix`-namespaced uids

Measured, at seed 42, purpose `TRIAGE`, occurrence 0:

| uid | blake2b-64 | first uniform |
|---|---|---|
| `CAS-0001` | 4525634368777823617 | 0.409773095893 |
| `POIA-0001` | 15309662056549830320 | 0.037022316342 |
| `POI-1-0001` | 16622491098476809080 | 0.108540609286 |

- **Key stability:** namespacing is a *total* re-keying of the identity axis. Every
  roster row, every ARRIVAL payload, and the golden trace change. There is no
  partial or incremental form — the hash is over the whole string.
- **Roster identity:** `casualty_id` is the roster's join key
  (`data/roster.py:40`) and the POLYBIUS input interface. Prefixing embeds POI
  provenance in the key *for free* — which is attractive, but it is a schema
  change to a published artefact and it silently invalidates any stored roster.
- **Collision safety:** conversely, per-POI prefixes are the *only* thing that
  makes N factories safe. Two factories emitting `CAS-0001` would collide on the
  identity key by construction. `id_prefix` already exists as a plumbed
  constructor arg on both factories (`casualty_factory.py:46`→`:56` legacy,
  `:209`→`:223` inverted; wired through `create_factory` at `:340` and `:357`)
  and the inverted factory additionally carries `source_id` (`:210`→`:224`, used
  at `:293`) — the seams are present and unused.
- **The register row is confirmed.** `docs/MVP/CURRENT.md`'s "AC-1.4 byte-identical
  defect — AMEND with context (per-POI sub-RNG dissolves into the key tuple)" is
  exactly right: no per-POI sub-generator is needed; the POI namespace dissolves
  into `counter[3]`. The amendment should also record that this is a *golden-moving*
  change if applied to a single-POI scenario.

---

## Q13 — WHERE IS A HELD CASUALTY

The hold block is `engine.py:776-921`: entry guard `:776-780`
(`current_facility.role == Role.R1 and next_id in self.queues`), retry loop
`:790-901`, post-loop disposition/PFC close `:903-921`.

### 13.1 Location fields as-built — measured

Probed with an `EventBus` subscriber sampling `engine.patients[cid]` at
`HOLD_START` / `HOLD_RETRY` on the T-5-5 hold fixture (public API only):

```
(event, cid, event.facility_id, current_facility, destination_facility, visited, state)
('HOLD_START', 'CAS-0004', 'R1-HOLD', 'R1-HOLD', 'R1-HOLD', ['R1-HOLD'], 'IN_TREATMENT')
('HOLD_RETRY', 'CAS-0004', 'R1-HOLD', 'R1-HOLD', 'R1-HOLD', ['R1-HOLD'], 'IN_TREATMENT')
('HOLD_START', 'CAS-0028', 'R1-HOLD', 'R1-HOLD', 'R1-HOLD', ['R1-HOLD'], 'IN_TREATMENT')
('HOLD_START', 'CAS-0019', 'R1-HOLD', 'R1-HOLD', 'R1-HOLD', ['R1-HOLD'], 'IN_TREATMENT')
```

Named attributes and their state during a hold:

| Attribute | Declared | Value during hold | Why |
|---|---|---|---|
| `patient.current_facility` | `schemas.py:98` | the **held (origin) facility** | last written at `engine.py:1033` on arriving at this facility |
| `patient.destination_facility` | `schemas.py:99` | **STALE — equals `current_facility`** | written at `engine.py:925`, i.e. *after* the hold block; it still holds the *previous* leg's destination, which is this facility |
| `patient.facilities_visited` | `schemas.py:107` | `[…, held facility]` | appended `engine.py:1034`; **the POI is never appended** (the first append happens only after the first transit) |
| `patient.state` | `schemas.py:97` | **`IN_TREATMENT` — stale** | last set at `engine.py:1243` in `_treat_in_queue`; the hold loop never sets a hold state. Overwritten only by PFC (`:826` → `IN_PFC`) or timeout (`:817` → `AWAITING_EVACUATION`) |
| the intended destination | — | **loop-local `next_id` only** (`engine.py:749-758`) | not on the casualty, not in the blackboard, not in any event field except the `HOLD_START` payload's `downstream_facility` (`engine.py:809`) |

**The intended destination is not persisted on the entity.** It exists as a Python
local in `_patient_journey` and, once, as an event payload key. Any re-plan
mechanism must either re-derive it or promote it to a field — this is the
narrowest fact in this document and the one BUILD_S3 will lean on hardest.

### 13.2 Physical semantics

**Waiting at the origin facility, holding nothing.** The sequence is: treat at R1
(`engine.py:1057-1060` → `_treat_in_queue`), whose `with queue.resource.request()`
block closes at `engine.py:1275` releasing the bed (the writer update at
`:1278-1279` is explicitly outside the `with`, "occupancy only reflects the release
here"); then the loop re-enters, computes `next_id`, and enters the hold. So a held
casualty:

- holds **no R1 bed** (released before the hold begins);
- holds **no transport resource** — the entire transport block
  (`engine.py:996-1021`: `record_request`, batcher/`resource.request`, the two
  `yield`s) sits *after* the hold block, at `:923` onward. Nothing is requested
  until the hold breaks;
- occupies **no modelled space at the destination** — the hold loop only *reads*
  `downstream_q.count >= downstream_q.capacity` (`engine.py:791`) and, under
  department routing, the target department's resource count (`:794-801`);
- **is** counted as resident at the origin by `FacilityLoadView`, which increments
  on `FACILITY_ARRIVAL` and decrements only on `DISPOSITION` (`views.py:57-65`) —
  the known register defect ("FacilityLoadView intermediate overcount").

The one resource a held casualty *can* hold is a CCP medic, and only transiently:
`self._ccp.medics.request()` with a 5-minute patience (`engine.py:832-833`),
released at `:842` or cancelled at `:845`. `_ccp.admit` (`:831`) /
`_ccp.discharge` (`:431`) bracket the episode.

So the physical reading is **"at the origin facility's door, unhoused"** — neither
occupying an origin bed nor queued at the destination. That is a modelling gap
worth naming in the ROUTING_SEMANTICS_NOTE regardless of which mechanism lands.

### 13.3 Which location would feed a divert

Both candidate sources agree, which removes an ambiguity BUILD_S3 might otherwise
have had to rule on:

- `_patient_journey` recomputes `current_facility = self.network.facilities[current_id]`
  at the top of each loop iteration (`engine.py:746`), and `current_id` during a
  hold is the held facility.
- `patient.current_facility` (the entity field) holds the same value, measured
  above.
- `get_next_destination(patient, current_facility, network, decisions, …)`
  (`routing.py:118-174`) uses `current_facility.role` for the ladder index
  (`:162`) and `current_facility.id` for edge/reachability tests (`:172`, `:113`).
- `network.get_route(patient, current_facility.id, target)` (`routing.py:156` →
  `topology.py:58-80`) likewise.

**Therefore the new-leg origin on a divert is the held R1 facility, reachable
identically from the loop-local and from `patient.current_facility`.** T-5-5a
already exercises exactly this call shape as a unit assertion, calling
`get_next_destination` with `engine.network.facilities["R1-HOLD"]` and asserting
`dest == "R2-S"` (`test_capability_retriage.py:166-172`) — i.e. **the routing call a
re-plan would make is already proven to return the right answer**; only the wiring
is missing. That is the content of T-5-5b's characterisation
(`test_capability_retriage.py:175-195`).

---

## Q14 — BEDS=0 PASS-THROUGH EVENT SIGNATURE (the waypoint template)

### 14.1 The mechanism

`add_facility` (`engine.py:292-310`) creates a `FacilityQueue` **only** when
`facility.role != Role.POI and facility.beds > 0` (`:295-296`); otherwise it logs
`"Facility %s has zero beds; skipping treatment queue creation."` (`:306-310`).
The journey's treatment dispatch is then a two-branch `if/elif` with **no else**
(`engine.py:1051-1060`):

```python
dept_graph = self.department_graphs.get(current_id)
if dept_graph and self.toggles.enable_department_routing:
    yield from self._treat_in_department(...)
elif current_id in self.queues:
    yield from self._treat_in_queue(...)
```

A beds=0 non-POI facility is in neither map, so both branches fall through and the
`while True` loop iterates straight to the next destination.

### 14.2 Measured event signature

Probe: `POI-1 → R2-ZERO (beds=0) → R3-MAIN (beds=20, surgical)`, all casualties
forced T2, seed 42. Full journey of `CAS-0001`:

```
t=   6.987  ARRIVAL            fac=POI-1
t=   6.987  TRANSIT_START      fac=POI-1
t=  26.987  TRANSIT_END        fac=R2-ZERO
t=  26.987  FACILITY_ARRIVAL   fac=R2-ZERO     ← waypoint hop
t=  26.987  TRANSIT_START      fac=R2-ZERO     ← no treatment; straight out
t=  61.987  TRANSIT_END        fac=R3-MAIN
t=  61.987  FACILITY_ARRIVAL   fac=R3-MAIN
t=  61.987  TREATMENT_START    fac=R3-MAIN
t= 162.145  TREATMENT_END      fac=R3-MAIN
t= 162.145  DISPOSITION        fac=R3-MAIN
```

| Event | Fires at a beds=0 hop? | Emission site |
|---|---|---|
| `TRANSIT_START` | ✅ | `engine.py:930-937` |
| `TRANSIT_END` | ✅ | `engine.py:1023-1028` |
| `FACILITY_ARRIVAL` | ✅ | `engine.py:1035` |
| `TREATMENT_START` | ❌ **skipped** | `engine.py:1141`/`:1190`/`:1245` |
| `TREATMENT_END` | ❌ **skipped** | `engine.py:1170`/`:1217`/`:1272` |
| `R1_DEPT`/`R2_DEPT` | ❌ | `engine.py:1118-1121` |
| `HOLD_*`/`PFC_*` | ❌ (hold gate is R1-only, `engine.py:777-780`) | `engine.py:808`/`:814`/`:899`/`:402` |
| `ATMIST_HANDOVER`/`NINE_LINER` | ✅ if toggled | `engine.py:940-941` (pre-transit, origin-side) |
| `DISPOSITION` | only if the journey ends there | `engine.py:711` |

Side-effects that still fire: `facilities_visited.append` (`:1034`), the facility
writer update (`:1036-1037`), `_update_facility_congestion` (`:1038`) — which
early-returns because `self.queues.get(facility_id)` is `None` (`:682-684`) — and
the golden-hour stamp (`:1040-1049`).

### 14.3 Consumers that would misread a no-treat arrival

**Does anything assume `FACILITY_ARRIVAL ⇒ treatment`? Yes — five places, one of
them a headline metric.**

1. **Golden-hour stamping — `engine.py:1040-1049`. The worst case.** The stamp is
   conditioned on `arrived_facility.role == Role.R2` *only*; treatment is never
   consulted. Measured on the probe: the T2 casualty is recorded
   `r2_arrival_time = 26.987`, `golden_hour_minutes = 20.0`, `golden_hour_met = True` —
   **while receiving no care whatsoever at that facility.** Run-level
   `metrics["golden_hour"]` reported `{'mean_minutes': 20.0, 'pct_within_60': 1.0,
   'total_tracked': 3}`. A waypoint mechanism that routes casualties *through* R2
   nodes therefore inflates the programme's flagship compliance metric to 100% for
   free. Both metric paths are affected (`metrics.py:121-133` and the legacy twin
   `engine.py:1477-1489`).
2. **`GoldenHourView`** (`analytics/views.py:83-116`) — measures ARRIVAL→DISPOSITION,
   so it is *not* fooled by a waypoint, but note it therefore measures something
   different from `metrics["golden_hour"]`. Two "golden hour" numbers with
   different definitions is itself a reporting hazard under the standing rule 5a.
3. **`FacilityLoadView`** (`views.py:52-65`) — increments `_current_load` on
   `FACILITY_ARRIVAL`, decrements only on `DISPOSITION`. A waypoint hop is a
   permanent +1 at that facility. This is the register's "FacilityLoadView
   intermediate overcount (views.py:65-66)" defect; waypoints make it structural
   rather than incidental.
4. **`mining._extract_facility_waits`** (`mining.py:295-321`) — records
   `facility_arrival_times[fid]` and waits for a `TREATMENT_START` at the same
   `fid` to compute a wait. At a waypoint the entry is written and **never
   consumed or deleted** (`:312-321`); harmless for the returned stats, but it
   means the wait census silently excludes the waypoint rather than reporting a
   zero.
5. **`mining` golden-hour compliance** (`mining.py:250-262`) — `if "R2" in fid or
   "R3" in fid or "R4" in fid: … break`. Substring match on the facility id, no
   treatment check — same false-positive as (1), and additionally fooled by any
   facility whose id merely contains "R2".
6. **`ReplayEngine._apply_facility_arrival`** (`replay.py:124-125`) — dispatches on
   `FACILITY_ARRIVAL` to mutate the snapshot; a no-treat arrival changes occupancy
   state in the replay without a matching treatment.
7. **`tests/test_facility_writer.py:110-114`** — asserts
   `expected_waiting = counts["FACILITY_ARRIVAL"] - counts["TREATMENT_START"]`. The
   arithmetic *is* the assumption. A waypoint mechanism reaching the writer
   fixtures makes this test's derivation wrong (its fixtures are coin-shaped
   today, so it survives unless the fixture changes).
8. **Oracles** — O1 (golden) has no beds=0 facility, so it is blind. O4
   (`test_hold_gate_integration.py`) is R1-hold-specific. T-5-7
   (`test_capability_retriage.py:252-312`) is the direct counterpart: it asserts
   `ns_treats` is non-empty, i.e. that a T1_SURGICAL **is** treated at a
   non-capable intermediate. **Waypoint semantics invert it.**

**Also note the beds=0 facility vanishes from `metrics["facilities"]` entirely**
(`metrics.py:99-113` iterates `queues`) — measured: only `R3-MAIN` appeared. A
waypoint is invisible to the facility metrics block, so throughput through it is
unreportable as-built.

---

## Q15 — MASCAL–POI COUPLING

### 15.1 Where cluster casualties are placed

Nowhere in particular — they inherit the engine's single POI. Chain:
`_mascal_cluster_process` (`arrivals.py:224-253`) builds
`ArrivalRecord(time=…, is_mascal=True, mascal_id=mascal_id)` (`:249-251`) →
`_emit_arrival` (`:259-266`) → `self.on_arrival(record)` (`:265`) =
`engine._handle_arrival` (wired `engine.py:1379`) → journey started at
`self._poi_id` (`engine.py:645-647`).

**Neither `MASCALEvent` nor `ArrivalRecord` carries a location.** `MASCALEvent` is
`(time, size, duration)` (`arrivals.py:76-82`); `ArrivalRecord` is
`(time, is_mascal, mascal_id)` (`:85-91`). The engine's own record of a MASCAL is
`_handle_mascal` (`engine.py:664-672`), which appends to `self._mascal_events` and
logs — no site. So a MASCAL is, as-built, a **theatre-wide temporal event with no
geography**.

### 15.2 What would determine the MASCAL site under N POIs

Nothing exists to determine it. Two structurally different answers follow from the
as-built code, and they are not equivalent:

- **Per-POI MASCAL (falls out of the wiring for free).** Because `start()`
  spawns `_mascal_event_process` per instance (`arrivals.py:147-148`), N
  ArrivalProcesses ⇒ N independent MASCAL generators, each drawing its own gap,
  size and offsets. The site is then implicitly the owning POI. Cost: the MASCAL
  rate is multiplied by N unless `mascal_rate_per_hour` is re-scaled per POI, and
  all N generators collide on the three shared stream keys (Q11.4) unless keys are
  scoped.
- **Theatre-level MASCAL, then site selection.** One generator, plus a rule that
  assigns the cluster to a POI (weighted, uniform, or configured). This needs a
  new draw purpose (site selection is stochastic) — an `RNGPurpose` addition is a
  reviewed change by the enum's own docstring (`rng.py:30-35`) and enters the I-3
  draw-count digest.

Both are config-expressible without a code branch per doctrine, so both satisfy
Hard Rule 8; the choice is a modelling ruling.

### 15.3 Is the detector threshold global or per-POI?

**Global, hardcoded, and not config-mappable.** One instance per engine:

```python
# engine.py:246-248
self.mascal_detector = MASCALDetector(
    window_minutes=15.0, threshold=20
)
```

`cooldown_minutes` is never passed and defaults to 30.0 (`mascal.py:33`). Fed by
**every** arrival regardless of source: `self.mascal_detector.record_arrival(record.time)`
at `engine.py:618`, the first statement of `_handle_arrival`. `MASCALDetector`
itself holds one flat `_arrival_times` list (`mascal.py:37`) and counts within the
window (`:46-49`) with no facility dimension. A full grep for
`MASCALDetector|mascal_detector|window_minutes|cooldown_minutes` across `src/` and
`tests/` shows **no builder mapping and no YAML key** — the numbers cannot be set
from a scenario at all.

Consequence for multi-POI: **two POIs' arrival streams sum into one detector**, so
N POIs at rate λ trip the 20-in-15-min threshold N times sooner than one POI at λ,
with no configuration recourse. Any multi-POI scenario tuning will hit this
immediately.

**One more as-built fact that matters for #30.** There are **two independent MASCAL
notions** and they are not connected:

- the *generator's* flag — `arrival.is_mascal`, which is what actually shifts
  triage (`casualty_factory.py:85-92` legacy; `:260` inverted, via the blackboard
  `mascal_active` key);
- the *detector's* state — which drives only the `MASCAL_ACTIVATE` /
  `MASCAL_DEACTIVATE` events (`engine.py:619-628`) and the
  `metrics["mascal_detector"]` block (`metrics.py:93-96`).

A casualty arriving during a detector-active window is **not** triaged as a MASCAL
casualty unless it also came from a cluster. AC-30's "triggered not always-on"
killer assertion (`MVP_ACCEPTANCE.md:208`) will have to say which notion it means.

---

## Q16 — ROLE LADDER / ROLE-4 CENSUS

### 16.1 `ROLE_ORDER` definition sites — there are two, duplicated

- `src/faer_dev/simulation/engine.py:77` — `ROLE_ORDER = [Role.POI, Role.R1, Role.R2, Role.R3, Role.R4]`
- `src/faer_dev/routing.py:28` — identical, with the comment "mirrors engine.py::ROLE_ORDER" (`:27`)

Both already include `Role.R4`. Used at `engine.py:95`, `:109-110` (legacy walk)
and `routing.py:91`, `:104-105` (highest-reachable), `:162-164` (extracted walk).
`Role` itself declares `POI=0 … R4=4` (`core/enums.py:28-43`, R4 documented at
`:37` as "Strategic/definitive care (CONUS)").

### 16.2 Hardcoded three-role assumptions — the complete touch-list

| # | Site | What is hardcoded | Effect on an R4 node |
|---|---|---|---|
| 1 | `engine.py:61-74` `DEFAULT_TREATMENT_TIMES` | keys are `Role.R1`, `Role.R2`, `Role.R3` **only** | Lookup at `engine.py:1151-1153` / `:1200-1202` / `:1257-1259` is `.get(role, {}).get(triage_key, 30)` → **silent 30-minute fallback for every triage at R4**. No warning. |
| 2 | `engine.py:300` department builder map | `{Role.R1: build_r1, Role.R2: build_r2, Role.R3: build_r3}` | `builder.get(facility.role)` returns `None` (`:301`) → no department graph at R4 → single-queue path only, even with `enable_department_routing` |
| 3 | Preset YAMLs | **no R4 node in any of the five** — `coin.yaml` (POI/R1/R2/R3, `:25,31,37,46`), `hadr.yaml` (same, `:25,31,37,46`), `iron_bridge.yaml` (POI/R1/R1/R2/R3, `:25,31,37,43,52`), `lsco.yaml` (POI/R1/R1/R2/R2/R3, `:25,31,37,43,52,61`), `specops.yaml` (`:25,31,37,46`) | R4 is unexercised end to end |
| 4 | Tests | `grep -rn "R4" tests/` → **zero hits** | no coverage at all |
| 5 | `engine.py:1042` golden-hour | `arrived_facility.role == Role.R2` | R4 arrival never stamps; correct as-is, but confirms the metric is R2-pinned |
| 6 | `engine.py:1069-1080` `_resolve_department` | department names `FST`/`ITU`/`ED`/`DCR`, fallback `"WARD"` (`:1080`) | R4's department vocabulary is undefined |
| 7 | `mining.py:259` | `if "R2" in fid or "R3" in fid or "R4" in fid` | **already R4-aware** (substring) |
| 8 | `events/models.py:136`, `:310` | `*_DEPT` event family documented as including `R4_DEPT` | already generic; the type is built from `f"{facility.role.name}_DEPT"` (`engine.py:1119`) |

**Already R4-capable, no change needed:** the `Role` enum (`enums.py:43`); the
builder's `_ROLE_MAP`, which maps both `4` and `"R4"` (`builder.py:36-37`); the
`Facility` schema, which types `role: Role` with no ladder assumption
(`schemas.py:150`); `TreatmentNetwork.add_facility`, which stores `role` as a node
attribute (`topology.py:34-40`); `guards.require_role_presence`, which only
requires *a* POI and *some* non-POI role (`guards.py:31-52`); both routing walks
(they iterate `ROLE_ORDER`, which already has five entries).

### 16.3 STRATEVAC-as-left-theatre semantics

`engine.py:760-774`, at the top of each loop iteration when `next_id is None`:

```python
if patient.triage == TriageCategory.T4:   patient.state = PatientState.DECEASED
elif patient.triage == TriageCategory.T3: patient.state = PatientState.RTD
else:                                     patient.state = PatientState.STRATEVAC
self._finalize_patient(patient, current_id, outcome=patient.state.name)
```

`PatientState.STRATEVAC` is documented as "Strategic evacuation (out of theatre)"
(`enums.py:83`, member `:100`). Two further, *different* STRATEVAC assignments
exist as failure modes: transport-capacity-zero (`engine.py:949`, outcome
`TRANSPORT_UNAVAILABLE`, `routing_failure=True`) and missing-edge
(`engine.py:976`, outcome `ROUTING_FAILURE`). T-5-6 characterises the second as a
"success-shaped silent disposition" (`test_capability_retriage.py:206`,
`:241`).

**So today STRATEVAC on the success path means "ran off the end of the built
ladder", not "evacuated out of theatre".** Because no preset declares an R4, every
T1/T2 that completes R3 is STRATEVAC'd there — the golden trace contains exactly
one such outcome (`tests/golden/coin_s42.json:1102`).

**Complete touch-list to add a Role 4 node as config:**

1. Add the facility + edges to a scenario YAML (parses today, no code change —
   `builder.py:36-37`, `:273-301`).
2. Add a `Role.R4` row to `DEFAULT_TREATMENT_TIMES` (`engine.py:61-74`) — otherwise
   the silent 30-min fallback. *Intrinsic change, mandatory human gate (Rule 3).*
3. Decide `build_r4` or accept single-queue (`engine.py:300`). Surface change.
4. Decide the STRATEVAC boundary: does STRATEVAC now mean "disposed at R4" (i.e.
   R4 is the last rung, unchanged code) or "left theatre from R4" (a new terminal
   distinct from the ladder-exhaustion case)? This is a *semantic* ruling with a
   metrics consequence — outcome counts (`metrics.py:116-119`) currently conflate
   ladder-exhaustion STRATEVAC with the two failure STRATEVACs only by outcome
   string, which does distinguish them (`STRATEVAC` vs `TRANSPORT_UNAVAILABLE` vs
   `ROUTING_FAILURE`).
5. Deduplicate or synchronise the two `ROLE_ORDER` definitions if the ladder ever
   becomes config-driven (`engine.py:77`, `routing.py:28`).
6. Golden impact: **none** unless an R4 is added to `coin.yaml`. The golden is a
   coin run (`test_oracles.py:38`); adding R4 elsewhere is inert to it.

---

## Q17 — GOLDEN/KEY IMPACT MATRIX PER MECHANISM

### 17.1 The regen surface, established first

`test_o1_golden_trace` (`test_oracles.py:30-45`) is the **only** test comparing
against a committed fixture (`tests/golden/coin_s42.json`, 110 events). Its run is
`run_to_log("coin", duration_min=480.0, max_patients=50, drain=False)` with
`toggles=None` — i.e. `SimulationToggles()` defaults: extracted routing **off**,
graph routing **off**, capability routing **off**, department routing **off**,
CCP **off**, typed emitter **off**, `rng_mode="keyed"`, `enable_event_store=True`
(`mode.py:47-74`).

Live digest re-verified at this HEAD:
`d6546fbffb580bc508ebff37adab5c312c50cad0bfa92d99e0f6ac2d0d907479` — matches the
committed fixture.

Golden event census (110 events):
`TRANSIT_START 17 · ARRIVAL 16 · TRANSIT_END 16 · FACILITY_ARRIVAL 16 ·
TREATMENT_START 16 · TREATMENT_END 15 · DISPOSITION 14`. Facilities touched:
`R1-ALPHA 60 · POI-1 32 · R2-MAIN 13 · R3-THEATRE 5`.
**No `HOLD_*`, no `PFC_*`, no `TRIAGE`, no `MASCAL_*` events at all.** Draw-count
census for the same run:
`triage 16 · mechanism 16 · primary_region 16 · secondary_count 16 ·
secondary_regions 16 · severity 16 · frailty_threshold 16 · treatment 16 ·
vehicle_return 14 · transit 3 · arrivals 17 · mascal_gap 1 · mascal_size 0`.
(One MASCAL gap was drawn; the timeout outlived the 480-min window, so no cluster
materialised.)

Two further **absolute** pins exist, both shared-mode string constants in
`tests/test_rng_keyed.py:184-189`: `_SHARED_O1_DIGEST_PREWIRE` (`9164bd97…`) and
`_SHARED_O1_DIGEST` (`9c9a3fda…`), asserted at `:206` and `:223`. Everything else
in the suite is a *relative* digest comparison (A==B), which survives a
behavioural change as long as both arms move together: `test_canonical.py:34`,
`:53`; `test_capability_routing.py:160`, `:191`, `:203`;
`test_facility_writer.py:196`, `:217`; `test_harness.py:34`;
`test_oracles.py:252`; `test_rng_keyed.py:107`, `:143`.

**So the O1-regen surface is exactly: one JSON fixture + two string constants.**
Rule 7 governs the mechanism (`pytest --regen-golden`, diff reviewed in the
commit); `docs/MVP/S2_0E_GOLDEN_REGEN.md` is the precedent record.

### 17.2 The matrix

| Mechanism | (a) coin DEFAULT event stream changes ⇒ O1 regen? | (b) RNG key layout changes ⇒ keyed digest shift? | (c) tests expected RED |
|---|---|---|---|
| **M1 — capability as hard edge-constraint** (`topology.py:65-68` infinite-weight pattern) | **NO**, under every sub-choice. *Sub-choice A — implement inside `get_route`:* `get_route` is unreachable on the default path (only `routing.py:149-159` calls it, gated on `use_graph_routing`, default False — `mode.py:60`). *Sub-choice B — also in the legacy/extracted walks:* still no, because the filter is gated on `use_capability_routing` (`routing.py:170`, default False, `mode.py:63`) **and** is vacuous on coin anyway — coin's R2-MAIN and R3-THEATRE both set `has_surgery: true` (`coin.yaml:40`, `:50`), which `test_t5_2c` already pins as a no-op (`test_capability_routing.py:176-191`). | **NO layout change** — no new `RNGPurpose`, no entity-string change. *But* a keyed **digest** shift on affected fixtures: changed paths ⇒ changed batch composition ⇒ shifted `TRANSIT` mission occurrence (per-mode global counter, `transport.py:303-305` + `rng.py:156-158`), and changed leg counts ⇒ shifted per-casualty `VEHICLE_RETURN` occurrence. Identity axis untouched, so **I-2/I-6/I-7 stay green by construction**. | **T-5-7** `test_capability_retriage.py:252-312` — asserts `ns_treats` non-empty; an edge constraint routes T1_SURGICAL around R2-NS, so it goes red (its docstring names this mechanism explicitly at `:263-265`). **Risk-red: T-5-8** `test_capability_routing.py:258` (over-filtering control — that is its job) and **T-5-4** `:210` (weight preference cannot readmit a non-capable candidate). O1, I-5 ×2, O4, O6 green. |
| **M2 — waypoint semantics** (transit-without-treatment) | **Depends on the trigger.** *Sub-choice A — per-facility config flag, default off:* **NO** (coin declares none). *Sub-choice B — derived from `beds == 0`:* **NO** (coin has no beds=0 non-POI node; `coin.yaml:32,38,48` are 4/8/50). *Sub-choice C — derived from capability:* **NO** (capability is off by default and vacuous on coin, as M1-B). *Sub-choice D — unconditional re-shaping of the arrival/treatment event pair (e.g. a new event type on every hop):* **YES, regen required.** | **NO layout change.** Skipping a treatment removes one `(casualty, TREATMENT)` draw, so that casualty's later `TREATMENT` occurrences shift down and `draw_counts["treatment"]` falls — an **I-3 digest shift on affected fixtures**, not a key-schema change. | **T-5-7** `:309-312` — **inverts** (`ns_treats` becomes empty). **Re-derivation needed, not necessarily red: `test_facility_writer.py:110-114`**, whose `waiting = FACILITY_ARRIVAL − TREATMENT_START` arithmetic *is* the assumption (survives only while its fixtures stay coin-shaped). Watch **`FacilityLoadView`** (`views.py:57-65`) — a waypoint arrival is a permanent +1; and **`metrics["golden_hour"]`**, which a waypoint through an R2 sets to met with zero care (Q14.3(1)) — no test pins it today, which is itself the finding. O1, I-1/2/3/5/6/7, O4, O6 green. |
| **M3 — re-plan triggers** (re-plan-on-promotion / on Clock-1) | **NO**, under every sub-choice — *because the trigger sites do not fire in the golden run.* The golden contains zero `HOLD_*`, zero `PFC_*` and zero `TRIAGE` events (17.1), so a re-plan hung on the PFC-ceiling promotion site (`engine.py:869-896`), on `HOLD_RETRY` (`:898-901`), or on every hold-loop iteration (`:790-901`) is unreachable there. Even a maximal "re-evaluate `next_id` every loop iteration" form is inert: coin's default path is the capability-blind legacy walk over a static topology, and congestion reweighting (`engine.py:674-686`) only touches `weight`, which the legacy walk never reads (`routing.py:172` uses `has_edge`; `topology.py:88-89` uses `base_time`). | **NO layout change.** Same TRANSIT/VEHICLE_RETURN occurrence exposure as M1(b) — and this is precisely the standing transit-provisional trigger: the register row "Transit keying = per-mode mission stream … REVISIT iff a transit-dependent estimand shows weak pairing" was arbitrated SUFFICIENT at ratio 776 on a **non-re-routing** topology. **A landing M3 re-opens that arbitration.** | **T-5-5b** `test_capability_retriage.py:175-195` — **inverts to `== 0`** by its own instruction (`:186-188`); do not delete. **Risk-red: O4** `test_hold_gate_integration.py:19-45` — it requires at least one casualty to traverse `HOLD_START → HOLD_RETRY → PFC_START → HOLD_TIMEOUT` in order; if a re-plan diverts held casualties to a free alternative, the timeout may stop reproducing. **T-5-5a** `:145-172` stays green (it asserts flag truthfulness plus a direct routing call). O1, I-5 ×2, O6 green. |
| **Multi-POI wiring itself** | **Depends on the key ruling, and on one live trap.** *Sub-choice A — preserve the bare `"arrivals"` (and `mascal_*`) literals for the designated/first POI, scope only POI #2..N:* **NO regen** — verified byte-identical (Q11.4). *Sub-choice B — namespace unconditionally:* **YES, regen required** — the first inter-arrival moves 0.69875 → 0.65506 and every downstream event with it. **Separately, and regardless of key ruling: adding a POI-prefixed edge source to a scenario silently steals the arrival source.** Measured on coin: appending an edge from an undeclared `POI-AAA` makes the builder synthesise it (`builder.py:249-259`, materialised `:269-271`) **before** the declared facilities (`:273-288`), so insertion order becomes `['POI-AAA', 'POI-1', 'R1-ALPHA', 'R2-MAIN', 'R3-THEATRE']`, `run()`'s first-POI scan (`engine.py:1369-1372`) picks `POI-AAA`, every ARRIVAL fires there, and the digest changes to `6c758cfd…`. Appending a *declared* second POI is inert (order `[…, 'POI-2']`, `_poi_id` stays `POI-1`, digest unchanged). | **YES if per-POI keys are adopted.** Two axes move: (i) the system-axis entity string for `ARRIVALS`/`MASCAL_GAP`/`MASCAL_SIZE`/`MASCAL_OFFSETS` gains a POI scope (`rng.py:165-167` currently hard-wires `purpose.value`) — this is a **key-schema change**, and the D6 register row's "key-schema version stamp" is the natural vehicle; (ii) if per-POI `id_prefix` is adopted, **every identity key changes** (blake2b of the uid string, `rng.py:77-81`; measured in Q12.3). Adding a MASCAL site-selection purpose would additionally extend the `RNGPurpose` enum and `_PURPOSE_INDEX` (`rng.py:29-62`) — a reviewed change that enters the I-3 digest. | **O1** red iff sub-choice B or the synthesised-POI trap. **I-5 ×2** (`test_rng_keyed.py:199-223`) green — shared mode on the one-POI coin preset is untouched by a *scoped* key. **I-1** `:102-108` green (determinism preserved). **I-2** `:115-121`, **I-6** `:258+`, **I-7** `:291+` green *provided* multi-POI is a scenario property compared like-for-like, not a toggle varied across arms. **O6** `test_oracles.py:233-260` — content changes and it must be re-asserted; its docstring already mandates this (`:238-240`). **AC-1.3 / Hard Rule 4** conservation (`arrivals == dispositions + in_system`) is the invariant to check after every engine change. `tests/harness.py:73-75` (`arrival_process._max_arrivals`) **breaks** if `engine.arrival_process` stops being a single object — a harness change, not a src change, but it gates every drained fixture in the suite. |

### 17.3 Reading of the matrix

Three of the four mechanisms are **golden-inert on coin under every sub-choice**,
for three different structural reasons: M1 because the default toggles never reach
the code, M2 because coin's facilities are all bedded and capable, M3 because the
golden trace contains no hold or promotion at all. **Only multi-POI wiring can move
the golden, and only via a key ruling that is a free choice.** That is a
substantially better position than the S3 scoping assumed, and it means the O1
regen question can be *decided* rather than *discovered*: pick the scoped-key
sub-choice and BUILD_S3 needs no golden regeneration for the routing mechanisms at
all.

The two characterisation tests that invert (T-5-5b under M3, T-5-7 under M1 or M2)
are the intended red — both carry explicit "invert, do not delete" instructions.

---

## Q18 — PER-POI ARRIVAL WEIGHTS SEAM (AC-1 ghost)

### 18.1 Where the arrival rate lives

**Field:** `ArrivalConfig.base_rate_per_hour: float = 2.0` (`arrivals.py:28`),
with the derived `base_rate_per_minute` property (`arrivals.py:38-40`) consumed at
the only two rate-reading sites, `arrivals.py:152` (the `<= 0` early return) and
`:159`/`:162` (the draw scale, `1.0 / base_rate_per_minute`).

**Builder mapping:** `builder.py:163-169` —

```python
arrivals_dict = scenario.get("arrivals", {}) or {}
arrival_defaults = get_arrival_config(context)
rate = _first_non_none(
    arrivals_dict.get("base_rate_per_hour"),
    arrivals_dict.get("base_rate"),
    arrival_defaults.base_rate_per_hour,
)
```

then `ArrivalConfig(base_rate_per_hour=rate, …)` at `builder.py:202-211`, passed as
`arrival_config=` to the engine (`:212-220`). The engine's own resolution ladder is
`arrival_config` arg → `config["arrival_rate"]` (the legacy dict path,
`engine.py:167-171`) → `get_arrival_config(context)` (`:172-173`).

**YAML keys:** `arrivals.base_rate_per_hour` (canonical — `coin.yaml:10`,
`lsco.yaml:10`, `hadr.yaml:10`, `specops.yaml:10`, `iron_bridge.yaml:10`) or the
alias `arrivals.base_rate`. A third, unrelated key exists on the Pydantic
`SimulationConfig` (`schemas.py:222`, `arrival_rate_per_hour`) which the builder
does **not** read — `build_engine_from_dict` takes the raw dict, and
`build_engine_from_preset` deliberately loads raw YAML because "SimulationConfig …
drops facilities/edges" (`builder.py:324-325`). Any per-POI extension must not be
put on `SimulationConfig` or it will be silently inert.

**Context defaults:** `ARRIVAL_CONFIGS` (`arrivals.py:48-73`), resolved by
`get_arrival_config` with a COIN fallback for PEACEKEEPING (`:269-273`).

### 18.2 Touch-list for a per-POI weight/rate extension

1. **Schema shape.** Decide *weights* (shares of one theatre rate; AC-1.1's
   language — "arrival weights 0.7 / 0.3") vs *rates* (independent λ per POI).
   Weights preserve the theatre total and keep MASCAL-detector tuning (Q15.3)
   stable; rates are simpler but multiply the effective load. **The AC as written
   asks for weights.**
2. **Config surface.** Either a per-facility key on POI facility entries (parsed at
   `builder.py:273-288`, which today reads only id/name/role/beds/coordinates/
   has_surgery/has_blood/has_imaging — note it **silently drops** or_tables,
   icu_beds, ventilators, has_lab, a register item) or an `arrivals.per_poi:` map.
   The per-facility form composes better with `apply_scenario_overrides`'
   list-by-`id` resolution (`builder.py:104-113`), which already supports
   `"facilities.POI-NORTH.weight": 0.7` addressing for free — and that is exactly
   what a `sweep` over spawn proportions would need (`tests/harness.py:93-119`).
3. **`ArrivalConfig`.** Either add a field, or construct N configs. The dataclass
   is shared by all four context presets (`arrivals.py:48-73`), so a new field
   needs a default that leaves single-POI behaviour identical.
4. **Builder.** Extend `builder.py:163-211` to build per-POI configs; keep
   `_first_non_none` fallback discipline so an unweighted scenario is unchanged.
5. **Engine wiring.** `engine.py:233-237` (`arrival_process`, `_poi_id`,
   `_arrivals_started` — all scalars) and `run()` `:1361-1384`. **Intrinsic change,
   mandatory human gate (Rule 3).**
6. **Callback.** `_handle_arrival` (`engine.py:615-647`) must learn the source POI —
   via an `ArrivalRecord` field (`arrivals.py:85-91`) or a per-instance closure.
7. **Stream keys.** Per-POI scoping of `ARRIVALS`/`MASCAL_*` (Q11.4). `rng.py:165-167`
   is the site.
8. **Provenance.** The ARRIVAL event's `facility_id` already carries the POI
   (`engine.py:736` with `current_id = start_facility_id`), so AC-1.1's spawn-share
   assertion is measurable from the canonical log with no new event field —
   provided each journey starts at its own POI.
9. **Harness.** `run_to_log`'s window-close poke reaches
   `engine.arrival_process._max_arrivals` (`tests/harness.py:73-75`); with N
   processes this needs a per-process loop or an engine-level close method.
10. **Guards.** `require_role_presence` (`guards.py:31-52`) checks POI *presence*,
    not plurality or weight-sum. A weight-sum guard (weights sum to 1.0 ± ε,
    mirroring `SimulationConfig.validate_distribution` at `schemas.py:243-250`) is
    the natural companion, and consistent with the guard family's stated purpose:
    "a spawn point that feeds nothing" (`guards.py:5`).

### 18.3 The AC-1 ghost lines, verbatim

From `docs/MVP/MVP_ACCEPTANCE.md`, section header at `:86`
("### 2nd — #1+#8 Multi-POI + unit positioning — INTRINSIC (bundle)"),
property statement at `:87-88`:

> **Property:** casualties spawn at multiple POIs in configured proportions,
> and each POI feeds its nearest R1.

```
:91  AC-1.1   Configure two POIs with arrival weights 0.7 / 0.3. Run 100 reps.
:92           Assert spawn proportion is 0.7 / 0.3 ± 0.05.
:93
:94  AC-1.2   Configure POI-NORTH nearest to R1-ALPHA and POI-SOUTH nearest
:95           to R1-BRAVO. Assert casualties from POI-NORTH predominantly
:96           route to R1-ALPHA (nearest-facility logic holds).
:97
:98  AC-1.3   INVARIANT: with two concurrent POI arrival processes, total
:99           DISPOSITION count still equals total ARRIVAL count.
:100
:101 AC-1.4   Determinism: two-POI scenario reproduces byte-identical at
:102          seed=42 (concurrent processes don't break determinism).
```

Wire-order row, `MVP_ACCEPTANCE.md:208`:

```
| #1+#8 multi-POI | I | AC-1.1–4 | Spawn proportions correct + invariant holds |
```

**Amendment notes for the authoring pass** (the ACs are not edited here — Rule:
`MVP_ACCEPTANCE.md` is never edited in this round):

- **AC-1.1 "arrival weights"** presumes the weights form (18.2 item 1). Nothing
  named `weight` exists in `ArrivalConfig` or any YAML today.
- **AC-1.2 "nearest-facility logic"** — **no such logic exists.** Facilities carry
  `coordinates` (`schemas.py:159`, populated `builder.py:274`, `:283`, stored as a
  node `pos` attribute `topology.py:38`) but **no code computes a distance from
  them**. Routing is first-match over `ROLE_ORDER` (`routing.py:161-174`) or
  Dijkstra over `weight`, which is initialised to `base_time` (`topology.py:53-54`)
  — i.e. **travel time, not geometry**. So AC-1.2 as written asserts a mechanism
  that would have to be built (either a coordinate-derived edge weight, or
  per-POI edges whose `travel_time_minutes` encode nearness — `iron_bridge.yaml`
  already does the latter with symmetric 15-min edges to both R1s, `:62-72`).
  **This is the single largest ghost in the AC set** and needs the amendment to
  say which reading is intended.
- **AC-1.3** is Hard Rule 4 in its drained form; `run_to_log(drain=True)`
  (`tests/harness.py:63-85`) already enforces `ARRIVAL == DISPOSITION` as a loop
  condition, so the AC is testable today with no new machinery.
- **AC-1.4** is the register's amendment target: per-POI sub-RNGs are unnecessary
  because the POI namespace dissolves into the key tuple (Q12.3) — but the
  amendment should add that *scoping the system-axis stream keys is mandatory*,
  not merely available (Q11.4), or "concurrent processes don't break determinism"
  will be satisfied while CRN pairing is silently destroyed. Determinism and
  pairing are different properties; AC-1.4 as written only tests the first.

---

## Q19 — VEHICLE RETURN UNDER MULTI-POI

### 19.1 Return-leg semantics as-built

**Pure capacity. There is no origin, home station, or position anywhere in the
transport model.** `TransportPool` (`transport.py:190-352`) holds exactly three
`simpy.PriorityResource` objects keyed by `TransportMode` (`:222-234`), each a
counted pool with no identity per vehicle and no location. Configured-zero modes
keep a `max(1, …)` placeholder gated by `has_capacity()` (`:224`, `:267-269`).

The return leg is `PolyhybridEngine._vehicle_return` (`engine.py:1281-1319`),
spawned as a detached process after the patient's outbound timeout
(`engine.py:1016-1021`):

```python
turnaround   = self.transport_pool.config.get_turnaround(mode)      # :1298
return_time  = max(10.0, keyed.draw(casualty_uid, VEHICLE_RETURN)
                          .normal(outbound_time, outbound_time*0.2)) # :1302-1308
total_downtime = return_time + turnaround                            # :1314
yield self.env.timeout(total_downtime)                               # :1315
resource.release(req)                                                # :1316
```

The docstring (`:1289-1296`) names the modelled phases — unload/handoff, return
flight, refuel/turnaround — but **"staging area" is narrative only**: no staging
node exists in `TreatmentNetwork`, the return time is drawn as a noisy mirror of
the *outbound* time rather than a distance to any base, and `resource.release`
returns the vehicle to an undifferentiated global pool. `get_turnaround` is a
per-mode constant (`transport.py:63-69`, defaults `:47-49`).

Two structural consequences for multi-POI:

- **A vehicle that delivers POI-A → R1-A is instantly available to POI-B.** There
  is no repositioning cost and no notion of "wrong side of the theatre". With N
  spatially separated POIs, transport becomes a perfectly-mobile shared pool — a
  modelling assumption that is currently invisible because there is one POI.
- **`VEHICLE_RETURN` is keyed per casualty, occurrence = delivery leg n**
  (`engine.py:1306`, entity `casualty_uid`). It is therefore **order-invariant by
  construction** and immune to multi-POI interleaving — provided uids are stable
  (Q12.3 caveat: per-POI `id_prefix` changes them).
- Note the **unbatched path only** spawns `_vehicle_return` (`engine.py:1008-1021`).
  On the batched path the vehicle is held inside `BatchCoordinator._dispatch_batch`'s
  `with self.resource.request(...)` for `trip_time` (`transport.py:444-457`) and
  released at context exit — **no turnaround is applied at all**. The two paths
  model vehicle downtime differently; multi-POI will exercise both far harder.

### 19.2 Would multi-POI change TRANSIT mission-ordinal determination?

**Yes — and this is the transit-provisional's standing trigger firing on a second,
independent mechanism.**

The TRANSIT stream is per *mode*, not per vehicle and not per POI
(`transport.py:299-308`):

```python
trip_time = self.keyed_rng.draw(
    f"transit:{mode.name}", RNGPurpose.TRANSIT
).normal(mean, std)
```

`draw()` auto-increments the occurrence per `(entity, purpose)` pair
(`rng.py:149-163`), so the ordinal is "how many trips this mode has drawn so far"
— a **global per-mode census**. `sample_trip_time` has exactly one live caller:
the batcher's `trip_time_fn` closure (`transport.py:252`, invoked at `:448`). The
module-level `transport_patient` helper (`transport.py:469-497`) also calls it at
`:492` but has no callers in `src/` or the engine.

Under multi-POI, every one of these shifts the ordinal:

1. **More missions per mode.** N POIs feeding the same R1/R2 set means more
   batches of the same mode; every additional dispatch shifts the occurrence index
   of **every subsequent mission** for that mode.
2. **Different batch composition.** `BatchCoordinator` pools by mode across the
   whole network with no origin dimension (`transport.py:391`, `_pending` is one
   flat list). Two POIs' casualties will batch *together* if they request the same
   mode within the window — a T1 (`priority <= 200`) from POI-B triggers immediate
   dispatch (`:407-410`) of a batch that may carry POI-A's casualties. Batch
   membership, and therefore trip count, becomes cross-POI coupled.
3. **Different request interleaving.** `PriorityResource` orders by
   (priority, request time, insertion ordinal); two arrival streams reorder
   requests at equal priority.

Per-casualty `VEHICLE_RETURN` draws are immune (19.1). Unbatched outbound times are
deterministic — the patient's transit duration is `network.get_travel_time`
(`engine.py:970` → `topology.py:82-90`, returning `base_time`, explicitly *not* the
congestion-adjusted `weight`), not a draw. **So the exposure is confined to batched
TRANSIT draws, exactly as Q4 established — but multi-POI enlarges it structurally
rather than incidentally.**

The register row reads: *"Transit keying = per-mode mission stream (provisional,
VR-1 arbitrated SUFFICIENT: ratio 776, leak 3/200 in 1/20 reps) — REVISIT iff a
transit-dependent estimand shows weak pairing. Trigger: Step-3 routing-semantics
interrogation."* **The trigger condition is met on two independent grounds** — M3
re-routing (Q17, mechanism M3(b)) and multi-POI batch coupling (this answer).
Whether the provisional must be *replaced* is a ruling for the doctrine session;
what this round establishes is that the arbitration cannot simply be carried
forward unexamined. The obvious candidate scoping, if it is replaced, is a
per-(mode, origin) or per-(mode, edge) mission stream — cheap, since the entity
string is already a hand-built scoped literal at `transport.py:304`.

---

## APPENDIX — DEFERRED-REGISTER ITEMS TOUCHED BY THIS ROUND

Recorded for the register pass; nothing is amended here.

| Register item | What this round found |
|---|---|
| **AC-1.4 byte-identical defect** (AMEND) | Confirmed and enlarged: per-POI sub-RNGs are unnecessary (Q12.3), but system-axis stream scoping is **mandatory** (Q11.4) and AC-1.4's wording tests determinism, not pairing (Q18.3) |
| **Hold re-route on promotion (T-5-5b) + path-purity (T-5-7)** | Both invert; the routing call a re-plan needs is already proven correct at `test_capability_retriage.py:166-172` (Q13.3). Q17 gives the per-mechanism red list |
| **Transit keying = per-mode mission stream** (provisional) | **Trigger met on two grounds** (Q19.2) |
| **FacilityLoadView intermediate overcount** (`views.py:65-66`) | Waypoint semantics make it structural rather than incidental (Q14.3) |
| **Builder silent drops** (or_tables / icu_beds / ventilators / has_lab) | Re-confirmed at `builder.py:278-287`; a per-POI weight key would join the same parse site (Q18.2) |
| *(new, unregistered)* **Dead second arrival wiring** | `engine.py:1321-1339` `_arrival_process` has zero callers (Q11.2) |
| *(new, unregistered)* **Synthesised-POI insertion order steals the arrival source** | `builder.py:269-271` inserts before declared facilities; `engine.py:1369-1372` takes the first — measured digest change on coin (Q17.2) |
| *(new, unregistered)* **MASCAL detector is unconfigurable and global** | Hardcoded `engine.py:246-248`; no YAML path; sums all POIs (Q15.3) |
| *(new, unregistered)* **Two unconnected MASCAL notions** | Generator flag vs detector state (Q15.3) — AC-30 must say which it means |
| *(new, unregistered)* **Golden-hour stamp ignores treatment** | `engine.py:1040-1049`; measured `golden_hour_met=True` with zero care through a beds=0 R2 (Q14.3) |
| *(new, unregistered)* **Held casualty holds nothing and its state is stale `IN_TREATMENT`** | Q13.2 — no bed, no vehicle, no destination-side queue |
| *(new, unregistered)* **`nearest-facility` logic does not exist** | Coordinates are stored but never used for distance; AC-1.2 asserts an unbuilt mechanism (Q18.3) |

---

*Round B complete. Q11–Q19 answered against HEAD `5a78f82`, 163 tests green,
`check_claude_md: ALL PASS`. BUILD_S3 remains UNAUTHORISED pending this file and
the signed ROUTING_SEMANTICS_NOTE.*
