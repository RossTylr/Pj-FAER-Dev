# S3 PRE-BUILD INTERROGATION — ANSWERS Q1–Q10

*Read-only interrogation ahead of BUILD_S3 authoring (Step 3: multi-POI +
routing semantics). All citations are against post-S2-D HEAD (`678eadb`);
where the tasking's cited line numbers have drifted, the drift is noted and
the actual site cited. No src/ or tests/ changes were made in Part B.*

---

## Q1 — JOURNEY ANATOMY

**Re-plans per hop.** `_patient_journey` (`engine.py:716`) runs a
`while True` loop (`engine.py:745`) that calls the routing function **once
per leg**: extracted `get_next_destination` at `engine.py:750-754`, legacy
`_get_next_destination` at `engine.py:756-758`. No stored path exists. In
graph mode the router internally computes a full Dijkstra path but returns
only `path[1]` — the next hop (`routing.py:156-159`) — so even graph mode
re-plans at every facility.

**Commit vs re-evaluate sites:**

| Site | Nature |
|---|---|
| `engine.py:750-758` | **RE-EVALUATED** — `next_id` computed fresh each loop iteration from current facility, patient state, and `decisions` |
| `engine.py:776-804` | **COMMITTED (pre-hold)** — the hold gate polls the queue of the *already-chosen* `next_id` (`downstream_q = self.queues[next_id]`, `engine.py:781`); the destination is not re-evaluated while holding. *(The tasking's cited `engine.py:680-688` now holds `_update_facility_congestion`; the pre-hold commit lives here.)* |
| `engine.py:924-925` | **COMMITTED (transit)** — `patient.destination_facility = next_id`; transit proceeds to the pre-hold choice unconditionally |
| `routing.py:156-159` | Dijkstra path computed then discarded beyond `path[1]` — the rest of the path is never committed |

**Seams where a mid-journey state change (triage promotion) could influence
the next routing decision:**

1. **Deterioration retriage inside the hold retry loop**
   (`engine.py:876-896`): sets `patient.triage` (`:880`) and
   `patient.requires_dcs` (`:883-885`), and pops the cached
   `target_department` (`:888-891`). But the loop then proceeds to transit
   with the **stale `next_id`** — the promotion influences routing only from
   the *following* hop.
2. **Stale `decisions` dict**: `decisions` is computed **once** at journey
   start (`engine.py:724`) and passed to every routing call. Retriage updates
   `patient.requires_dcs` but **not** `decisions["requires_dcs"]` or
   `decisions["bypass_role1"]`. Capability exclusion reads the live
   `patient.requires_dcs` (`routing.py:72`), so it tracks promotion; the
   bypass mechanism reads `decisions["bypass_role1"]`
   (`routing.py:93, :106, :165`), so it does **not**. A T2 promoted to
   T1_SURGICAL therefore gains capability-targeting but never gains R1
   bypass mid-journey.
3. **Clinical short-circuits** read live `patient.triage`
   (`routing.py:141-147`): a T2→T1 promotion removes the T3/T4 stop
   conditions from subsequent hops; conversely they fire immediately at the
   next re-evaluation for any demotion (none exists — promote-only,
   `engine.py:876`).
4. **`get_route` bypass weighting** reads live `patient.bypass_role1`
   (`topology.py:63`), which `_patient_journey` set once at
   `engine.py:725` from the original decisions — same staleness as (2).

---

## Q2 — TREAT-STOP COUPLING

**Exact path FACILITY_ARRIVAL → treatment start:** transit ends
(`TRANSIT_END`, `engine.py:1023-1028`) → `current_id = next_id`
(`engine.py:1032`) → `FACILITY_ARRIVAL` logged (`engine.py:1035`) →
golden-hour stamp if R2 (`engine.py:1040-1049`) → treatment dispatch gate
(`engine.py:1052-1060`):

- department routing ON and a dept graph exists →
  `yield from self._treat_in_department(...)` (`engine.py:1054-1056`);
- else if `current_id in self.queues` →
  `yield from self._treat_in_queue(...)` (`engine.py:1058-1060`), which
  requests the bed (`engine.py:1236-1237`), logs `TREATMENT_START`
  (`engine.py:1245-1248`), draws the keyed TREATMENT time
  (`engine.py:1260-1263`) and releases the bed at context exit
  (`engine.py:1276-1279`);
- **else: nothing** — the loop iterates to the next destination without any
  treatment event.

**Pass-through/no-treat branch today: YES, by queue absence.**
`add_facility` creates a queue only when
`facility.role != Role.POI and facility.beds > 0` (`engine.py:295-296`);
department graphs are built only inside that same branch
(`engine.py:298-305`). Consequently a POI — or **any beds=0 facility** —
has no queue and no dept graph, fails both arms of the dispatch gate, and is
transited through without treatment. This also silently skips the hold gate
for that hop, since holding requires `next_id in self.queues`
(`engine.py:778-780`).

**Smallest seam for a waypoint (transit-without-treatment):**

- **Config-only, exists today:** `beds: 0` on the intermediate facility —
  zero code lines; the facility becomes a de-facto waypoint (no
  TREATMENT_START, no hold against it).
- **First-class semantic waypoint** (a facility that *can* treat but this
  casualty should pass through): the decision point is the dispatch gate
  `engine.py:1052-1060` — intrinsic, ~1-3 lines of condition — plus,
  depending on the chosen semantics, a `Facility`/routing-level flag
  (schemas + `builder.py` parse, surface) or a per-casualty predicate in
  `routing.py` (surface). Functions touched: `_patient_journey` (gate only),
  optionally `_meets_capability`/`get_next_destination`. Intrinsic-only is
  achievable iff the waypoint predicate needs no new config; with config it
  is intrinsic-gate + surface-plumbing.

---

## Q3 — MULTI-POI AS-BUILT

**Premise correction:** `engine.py:1278-1281` is the tail of
`_treat_in_queue` / head of `_vehicle_return` — there is no single-POI
rejection there. The actual single-POI mechanism is in `run()`:

- `engine.py:1361-1366`: `run(poi_id=...)` **raises ValueError** only if
  `poi_id` is *changed* after arrivals started ("poi_id changed from … after
  arrivals started").
- `engine.py:1368-1372`: if no `poi_id` given, the engine scans
  `network.facilities` and takes the **first** facility with
  `role == Role.POI` (dict insertion order).
- `engine.py:1374-1384`: exactly **one** `ArrivalProcess` is constructed,
  bound to that single POI; `_handle_arrival` starts every journey at
  `self._poi_id` (`engine.py:645-647`).

**With 2+ POIs today, what breaks FIRST: the arrival process — silently.**
Nothing rejects the config: the builder parses any number of POI facilities
(facilities loop, `builder.py:273-288`) and additionally *synthesises* POI
nodes from unknown edge sources whose id starts with "POI"
(`builder.py:249-259`, materialised at `builder.py:269-271`). The engine
accepts them all. But `run()` binds ONE ArrivalProcess to the first POI;
every other POI receives zero arrivals and is simply dead topology. No
error, no warning — a starved-POI silence, not a rejection. The builder
schema is therefore **already multi-POI capable at parse level**; the
single-POI constraint is an engine `run()`/arrival-wiring property.

**IRON BRIDGE as parsed** (`src/faer_dev/config/defaults/iron_bridge.yaml`):
5 declared facility nodes — `POI-FRONT` (POI, beds 0, `:23-27`), `R1-ALPHA`
(R1, 8 beds, `:29-33`), `R1-BRAVO` (R1, 8 beds, `:35-39`), `R2-MAIN` (R2, 16
beds, has_surgery+has_blood, `:41-48`), `R3-MAIN` (R3, 100 beds,
surgery/blood/imaging, `:50-59`). **POI count: 1.** Edges (`:61-90`):
POI-FRONT→{R1-ALPHA, R1-BRAVO} (15 min GROUND), both R1s→R2-MAIN (25 min
GROUND), R2-MAIN→R3-MAIN (45 min ROTARY). Note: every edge carries
`threat_level`, which the builder's edge parser **silently drops** — it
reads only `travel_time_minutes`/`time_minutes` and `transport`/`mode`
(`builder.py:291-300`).

---

## Q4 — DISPATCH ORDER (standing question from the transit provisional)

**Assignment mechanics.** `TransportPool` (`transport.py:190`) keeps one
`simpy.PriorityResource` per mode (`transport.py:222-234`). Two paths from
the journey loop:

- **Unbatched** (`engine.py:1009-1021`): direct
  `resource.request(priority=patient.priority_value)` (`engine.py:1011`).
  Request ordering = SimPy PriorityResource semantics: sorted by
  (priority, request time, insertion ordinal) — FIFO within equal priority.
  The *outbound* time is NOT drawn: it is the deterministic edge
  `base_time` (`engine.py:970` via `topology.py:82-90`). The vehicle's
  return leg is drawn **per casualty** —
  `(casualty_uid, VEHICLE_RETURN)` keyed, occurrence = delivery leg n
  (`engine.py:1302-1308`) — i.e. order-invariant by construction.
- **Batched** (`engine.py:999-1007`; built when `batch_enabled` — default
  True, `transport.py:53` — and per-vehicle patient capacity > 1,
  `transport.py:240-255`): `BatchCoordinator.request_transport(id,
  priority)` pools patients; **trip times are the per-mode mission stream**:
  `sample_trip_time` draws from entity `f"transit:{mode.name}"` with purpose
  `TRANSIT` (`transport.py:299-308`). **Mission-ordinal determination:** the
  keyed occurrence auto-increments per (entity, purpose) pair
  (`rng.py:148-157`) — the ordinal is simply "how many trips this mode has
  drawn so far", a global per-mode census, not a per-casualty property.

**Would a mid-journey re-route or promotion ALTER request order?** Yes, on
three mechanisms — this is exactly the provisional's bite condition:

1. **Priority changes:** as-built, deterioration retriage does **not**
   recompute `patient.priority_value` (`engine.py:876-896` touches triage,
   requires_dcs, target_department only; `priority_value` set at creation,
   `schemas.py:94`). A promotion that *did* update priority would reorder
   the PriorityResource queue for everyone behind.
2. **Re-route changes the mode/edge requested:** a re-plan-on-promotion fix
   (T-5-5b) changes which edge — hence which mode — a patient requests and
   *when*, shifting the per-mode request sequence.
3. **Mission-ordinal shift:** because TRANSIT occurrence is a per-mode
   global counter, any change in trip count or order (batch composition,
   extra/omitted trip) shifts the occurrence index of **every subsequent
   mission** for that mode — the trip-time pairing between doctrine arms
   degrades from that point on. Per-casualty VEHICLE_RETURN draws are immune
   (keyed by casualty uid), and unbatched outbound times are deterministic —
   so as-built the exposure is confined to **batched TRANSIT draws**.
   VR-1 arbitrated this SUFFICIENT at current topology (ratio 776, leak
   3/200 in 1/20 reps — `docs/MVP/CURRENT.md` register row "Transit keying =
   per-mode mission stream"); a re-routing Step 3 re-opens that arbitration.

---

## Q5 — IDENTITY UNDER MULTI-POI

- **Factory: single shared instance per engine**, not per-POI. Constructed
  once in `PolyhybridEngine.__init__` (`engine.py:189-204` via
  `create_factory`, `casualty_factory.py:319`). Both factory classes carry a
  per-instance `_counter`; ids are `f"{id_prefix}-{counter:04d}"` when
  `id_prefix` is set, else `f"CAS-{counter:04d}"`
  (`casualty_factory.py:129-130`, inverted variant `:299-300`).
- **`id_prefix` flow:** constructor arg on both factories
  (`casualty_factory.py:46`, `:204`), plumbed via `create_factory(...,
  id_prefix=kwargs.get("id_prefix", ""))` (`casualty_factory.py:330`,
  `:346`). The engine passes no id_prefix today — all casualties are
  `CAS-NNNN`. The inverted factory additionally carries a `source_id`
  (`casualty_factory.py:205`) — an existing per-source labelling seam.
- **`uid_int` does not exist as-built.** That was the FINAL-v1 entropy
  layout; deviation **D1** (accepted as-built, `docs/MVP/BUILD_S2.md:52`)
  replaced it: the key-tuple entity component is **blake2b-64 of the uid
  string** (`rng.py:77-81`), fed into the Philox counter word 3
  (`rng.py:145`). Identity keying is therefore **global by uid string** —
  two factories emitting the same uid would collide; per-POI id prefixes
  (e.g. `POI-N-0001`) dissolve into the hash with no per-factory sub-RNG
  needed. (This is the "per-POI sub-RNG dissolves into the key tuple"
  register note on AC-1.4.)
- **ARRIVAL POI provenance:** the ARRIVAL event's `facility_id` **is** the
  start facility — `_log_event("ARRIVAL", patient, current_id, ...)`
  (`engine.py:736`) with `current_id = start_facility_id =` the engine's
  single `_poi_id` (`engine.py:645-647`, `:720`). The payload dict itself
  (`engine.py:737-743`: injury_mechanism, severity, recommended_triage,
  bypass_role1, requires_dcs, priority) carries no dedicated POI field.
  Under multi-POI, `facility_id` would carry provenance automatically iff
  each journey is started with its own POI id.

---

## Q6 — EDGE-CONSTRAINT SEAM

**Infinite-weight mechanism** — `topology.py:65-68`, inside
`get_route` (`topology.py:58-80`), active only for `patient.bypass_role1`:

```python
def weight_func(u: str, v: str, d: dict) -> float:
    if self.graph.nodes[v].get("role") == Role.R1:
        return float("inf")
    return d.get("weight", 1)
```

API: a per-call Dijkstra weight callable — **soft exclusion**. `float("inf")`
edges remain traversable to NetworkX; if the only path runs through R1, the
inf-cost path is still returned (the "weights silently dominate soft flags"
R1-ALPHA lesson, recorded at `routing.py:68-70`).

**Subgraph-view mechanics** — the tasking's `topology.py:77-84` has drifted:
`topology.py:77-80` is the `NoPathError` raise. The subgraph view lives in
**`routing.py:97-100`**, inside `_find_highest_reachable`:

```python
graph = nx.subgraph_view(
    network.graph,
    filter_node=lambda n: n not in r1_ids,
)
```

— a lazy read-only node-filtered view (no copy), rebuilt per call, excluding
all R1s except the current facility (`routing.py:94-96`). **Hard exclusion**,
used only for the reachability pre-check.

**`has_path` pre-check** — `routing.py:113` (the tasking's `:95` has
drifted): `if nx.has_path(graph, current_facility.id, fac_id):` — run against
the filtered view during target selection (`routing.py:104-114`), with
capability exclusion applied to the candidate set first (`routing.py:111-112`
via `_meets_capability`, `routing.py:72`).

**Consequences if capability reuses the infinite-weight mechanism for
`requires_dcs`:**

1. **Soft-vs-hard mismatch.** Infinite weight would not prevent routing
   *through* (or, with no alternative, *to*) a non-surgical node — it only
   disprefers it. AC-5.1's letter ("NEVER treated at a has_surgery=False
   facility") is a hard property; the existing candidate-set exclusion is
   hard, the weight mechanism is not.
2. **Interaction with the `has_path` pre-check:** `has_path` ignores weights
   entirely — an inf-weighted edge still yields reachability. Target
   selection would keep nominating targets whose only route crosses a
   non-capable node, and `get_route` would return that route at inf cost.
   To make edge-constraints bite in the pre-check, the exclusion must be a
   **node/edge filter on the view** (the `routing.py:97-100` pattern), not a
   weight.
3. **Starvation→None pathway:** with hard exclusion, when no capable
   facility is reachable `_find_highest_reachable` returns None
   (`routing.py:115`) → `get_next_destination` returns None
   (`routing.py:154-155`) → the journey terminates with a
   triage-mapped disposition: T4→DECEASED, T3→RTD, **else STRATEVAC**
   (`engine.py:760-774`). A starved T1_SURGICAL therefore exits as
   STRATEVAC — conserved (Rule 4) but clinically silent; there is no
   distinct "starved of capability" outcome today.

---

## Q7 — SIMULTANEITY

**Current tie-break:** SimPy's event heap orders by
`(time, priority, event_id)`, where `event_id` is a monotonically increasing
counter assigned at schedule time — so ties at one `sim_time` resolve by
**scheduling order**, which is itself determined by process creation order
and generator interleaving. There is no FAER-side tie-break code; the
determinism source is SimPy's insertion-ordered heap plus the engine's fixed
process-creation sequence (arrival processes started once at
`engine.py:1374-1384`; each casualty's journey process created at
`engine.py:645-647` in arrival order).

**What produces same-timestamp arrivals today:** MASCAL clusters — offsets
are drawn as one keyed array (`arrivals.py:228-236`), sorted, and can
coincide (zero-spread clusters force exact ties).

**What two-POI same-timestamp arrivals ADD:** today the base and MASCAL
generators are *coupled* through one ArrivalProcess bound to one POI. Two
POIs mean two **concurrent arrival generators** whose events can land on the
same `sim_time`; their relative order then depends solely on process
creation order and the deterministic interleaving of their timeout chains.
Keyed draws make the *values* order-invariant (arrival ordinals are
per-stream), but the **event order in the log** — and hence `log_digest`,
and any casualty *numbering* shared across POIs via the single factory
counter (Q5) — is exactly the hazard. A nondeterministic dict/set anywhere
in the wiring (e.g. facility iteration at `engine.py:1369-1372`) becomes
load-bearing.

**O6's exact assertion** (`docs/MVP/BUILD_F0.md:142-150`, verbatim):

> **O6 — Simultaneity tie-break determinism (closes a gap the interrogation
> missed).** MASCAL's signature is several casualties arriving at the SAME
> simulated instant, and SimPy tie-breaking at identical timestamps is
> exactly where determinism and CRN break silently. Build a scenario dict
> that forces k >= 3 arrivals at one sim-time (e.g. a MASCAL cluster with
> zero spread, or direct injection); run twice at seed=42 and assert
> `log_digest` EQUAL, including the relative order of the simultaneous
> events. Re-assert this oracle after step 3 (multi-POI) lands — concurrent
> arrival generators are the exact hazard it guards (C5).

---

## Q8 — RE-ROUTE HOOK (T-5-5b fix seam)

**Where the hook goes.** The hold retry loop is `engine.py:790-901` (the
tasking's `:843` region — PFC ceiling/retriage now sits at
`engine.py:854-896`). The natural hook is **immediately after the
deterioration retriage fires** (`engine.py:877-896`): the promotion is the
only in-loop event that invalidates the pre-hold destination. Re-evaluating
there means breaking out to the top of the outer journey loop
(`engine.py:745`) instead of continuing to poll the stale `next_id`'s queue.
A second, cheaper variant hooks **after hold release**
(`engine.py:916-921`, before the transit commit at `engine.py:924-925`) —
one re-evaluation per hold instead of per promotion.

**State required:**

- a refreshed `decisions` dict — the stale-decisions seam from Q1:
  `_extracted_triage_decisions(patient)` recomputed, or at minimum
  `decisions["requires_dcs"]`/`["bypass_role1"]` synchronised with the
  promoted triage (the retriage already updates `patient.requires_dcs`,
  `engine.py:883-885`, and pops the cached target department,
  `engine.py:888-891`);
- hold bookkeeping: `hold_start`/`held_so_far` (restart or carry the hold
  clock against a NEW downstream target — semantics decision), and the PFC
  state machine (`_is_pfc_active`, `pfc_started_at`) which must survive a
  destination change without double-starting or orphaning
  (`_finalize_pfc_if_active` currently fires only on release/timeout,
  `engine.py:905-919`);
- `patient.destination_facility` is not yet set during hold (set only at
  `engine.py:925`), so no unwind is needed there.

**Hold-queue slot release semantics: there is no slot.** The holder occupies
no SimPy resource while holding: its R1 bed was released at TREATMENT_END
(context-manager exit, `engine.py:1236/:1276-1279`) and the downstream bed
is not requested until after transit, inside the *next* hop's
`_treat_in_queue`. The hold gate is a **count poll**, not a reservation:
`downstream_q.count >= downstream_q.capacity` (`engine.py:791`). Release
from hold reserves nothing — the freed bed can be claimed by anyone before
the held patient arrives (they then wait in the destination's
PriorityResource queue). A re-route hook therefore has no slot to hand back;
the only state to unwind is the hold/PFC bookkeeping above.

**O4 recipe interaction** (`docs/MVP/BUILD_F0.md:122-129`): O4 rebuilds the
hold-gate integration test from the recipe "bottleneck R2 beds=1,
`_hold_timeout_override=75`, T2 arrivals; assert one patient traverses
HOLD_START → HOLD_RETRY → PFC_START → HOLD_TIMEOUT in order"
(`tests/test_hold_gate_integration.py`). A re-route hook adds a **new exit
arc** from that sequence (promotion → re-plan) that the recipe's
linear-order assertion does not model: T-5-5b's landing must either keep the
O4 fixture promotion-free (T2 arrivals under the 0.20× ladder can deteriorate
to T1 — the recipe relies on the ceiling *not* firing within 75 min) or
extend the asserted grammar with the re-route arc. The characterisation
tests INVERT to ==0 when the fix lands (CURRENT.md register row
"Hold re-route on promotion (T-5-5b) + path-purity (T-5-7)").

---

## Q9 — STEP-3 AC SET

**AC-1 bundle, verbatim** (`docs/MVP/MVP_ACCEPTANCE.md:91-102`; header
`:86-88` — "#1+#8 Multi-POI + unit positioning — INTRINSIC (bundle)"):

> ```
> AC-1.1   Configure two POIs with arrival weights 0.7 / 0.3. Run 100 reps.
>          Assert spawn proportion is 0.7 / 0.3 ± 0.05.
> ```
> (`MVP_ACCEPTANCE.md:91-92`)
>
> ```
> AC-1.2   Configure POI-NORTH nearest to R1-ALPHA and POI-SOUTH nearest
>          to R1-BRAVO. Assert casualties from POI-NORTH predominantly
>          route to R1-ALPHA (nearest-facility logic holds).
> ```
> (`MVP_ACCEPTANCE.md:94-96`)
>
> ```
> AC-1.3   INVARIANT: with two concurrent POI arrival processes, total
>          DISPOSITION count still equals total ARRIVAL count.
> ```
> (`MVP_ACCEPTANCE.md:98-99`)
>
> ```
> AC-1.4   Determinism: two-POI scenario reproduces byte-identical at
>          seed=42 (concurrent processes don't break determinism).
> ```
> (`MVP_ACCEPTANCE.md:101-102` — **the byte-identical defect line**; register
> row: "AC-1.4 byte-identical defect | AMEND with context (per-POI sub-RNG
> dissolves into the key tuple)", `docs/MVP/CURRENT.md` deferred register.)

**Other routing/multi-POI-relevant ACs, verbatim:**

> ```
> AC-5.1   THE KILLER ASSERTION. Configure one facility with
>          has_surgery=False. Run a scenario with surgical casualties.
>          Assert: NO event where a casualty with requires_dcs=True
>          is treated at the has_surgery=False facility.
>          (If this fails, routing ignores capability — the feature is
>          not wired, regardless of test execution status.)
> ```
> (`MVP_ACCEPTANCE.md:69-74`)
>
> ```
> AC-5.2   Configure all facilities has_surgery=True. Run. Surgical
>          casualties ARE treated (no casualty stuck unrouteable when
>          capability exists). Confirms the flag gates, doesn't block.
> ```
> (`MVP_ACCEPTANCE.md:76-78`)
>
> ```
> AC-5.3   Determinism: AC-5.1 produces byte-identical canonical log
>          (F0.1) across two runs at seed=42.
> ```
> (`MVP_ACCEPTANCE.md:80-81`)
>
> ```
> AC-10.1  Configure one high-threat edge (denial weight high) and one
>          low-threat edge (denial weight low) between the same role
>          levels. Run 100 reps. Assert denial rate on the high-threat
>          edge is measurably greater than on the low-threat edge.
> ```
> (`MVP_ACCEPTANCE.md:110-113`)
>
> ```
> AC-10.2  Set all threat zones to zero. Assert denial rate reduces to
>          the baseline route-denial probability (threat adds to, doesn't
>          replace, base denial).
> ```
> (`MVP_ACCEPTANCE.md:115-117`)

**Ghost-field census against code (post-S2-D HEAD):**

| AC field/concept | Status in code |
|---|---|
| `has_surgery` (AC-5.1) | **REAL** — `Facility` schema; parsed `builder.py:284`; consulted `routing.py:72` |
| `requires_dcs` (AC-5.1) | **REAL** — `schemas.py:114`; set `routing.py:47-50`; live-updated on retriage `engine.py:883-885`; in ARRIVAL payload `engine.py:741` |
| Per-POI **arrival weights** (AC-1.1) | **GHOST** — no schema key, no per-POI ArrivalConfig; one ArrivalProcess exists (`engine.py:1374-1384`) |
| "**nearest**-facility logic" (AC-1.2) | **GHOST as a mechanism** — no distance-based POI→R1 assignment exists; routing is role-walk first-match (`routing.py:161-174`) or congestion-weighted Dijkstra (`topology.py:70-76`); coordinates are stored (`builder.py:283`) but never enter routing |
| `denial_weight` / denial rate (AC-10.1) | **GHOST** — zero hits in src/; no route-denial mechanism exists; YAML `threat_level` on edges is **silently dropped** by the builder (`builder.py:291-300`); the dormant `Route` schema's `threat_multiplier`/`max_threat_level` (`schemas.py:193-198`) is not wired to `TreatmentNetwork` |
| `facility_utilisation` (AC-W.1) | **REAL** — blackboard default `blackboard.py:29`; read by BT node `bt_nodes.py:121-135` |
| `fst_queue_depth` (AC-W.1) | **REAL** — blackboard default `blackboard.py:33` |
| `mascal_active` (AC-W.2) | **REAL** — blackboard default `blackboard.py:38`; written per-casualty by the factory `casualty_factory.py:260`; read `bt_nodes.py:104-115` |

---

## Q10 — DOCTRINE SOURCES

**"Casualty Care Pathway": ABSENT from the repo.** Case-insensitive grep
over `docs/` returns zero hits. **"Stabilisation Point" / "Stabilization
Point": ABSENT** — zero hits. There is **no doctrine source in the
repository** governing "does every echelon treat?"; the human supplies the
FP-IRTB extracts for the doctrine note.

What the repo *does* contain are engineering statements about bypass and
per-hop treatment (not doctrine citations):

- `docs/MVP/BUILD_S1.md:59` — T-5-7 characterisation: "chain fixture
  POI→R1→R2(surgical); both routing toggles + capability ON; T1_SURGICAL.
  Document treatment at non-capable intermediates (Q3/Q5: **every
  FACILITY_ARRIVAL treats**). … Mechanism sketch for Step 3: capability as
  hard edge-constraint à la `bypass_role1` infinite weights (topology.py
  pattern), or **transit-without-treatment semantics** — decision then, not
  now."
- `docs/MVP/S1_PREBUILD_ANSWERS.md:89-109` — `bypass_role1` consulted three
  times (subgraph view; target-role skip; `get_route` weighting), and the
  finding that weight comparison can override `bypass_role1` for non-bypass
  casualties ("nothing forces an R1 visit").
- `docs/MAAFI/MAAFI_FORWARD.md:18` — "routing reads **only** `role`, graph
  edges, and `bypass_role1`. It reads **none** of has_surgery / has_blood /
  has_imaging / …" (pre-S1 state; capability wiring has since landed, but
  the doctrine vacuum it describes stands).

*(End of interrogation. Step 3 remains UNAUTHORISED; BUILD_S3 authoring is
the planning chat's move.)*
