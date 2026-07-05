# S1 FOLLOW-UP ANSWERS — FQ1 / FQ3 / FQ4

*Read-only interrogation per BUILD_S1 §7, 2026-07-05. Answered against the
S1.2a-committed tree (`98597de`). FQ2 was answered out-of-band (verbatim ACs +
Hard Rules sighted; recorded in BUILD_S1 §3/§5).*

---

## FQ1 — BT tick sites, live decision paths, thresholds

**Tick sites.** The ONLY production BT tick is
`self.triage_bt.tick()` inside `InvertedCasualtyFactory.create`
(`casualty_factory.py:231`), executed once per casualty at creation. The
engine builds that triage tree only on the inverted-factory branch
(`engine.py:163-183`, specifically `build_triage_tree()` at `engine.py:173`).
The DCS tree (`build_dcs_tree`, `trees.py:221-272`) and the
department-routing tree (`build_department_routing_tree`, `trees.py:160-213`)
are **never built or ticked anywhere in src/** — they are exported
(`decisions/__init__.py:32-33`) but have no engine call site.

**At default toggles: NO live decision path executes either node.**
`factory_mode` defaults to `"legacy"` (`mode.py:45`), so the inverted branch
never runs; the legacy factory has no blackboard at all, and the engine does
not even construct a `SimBlackboard` outside the inverted branch
(`engine.py:166-174`).

- `CheckMASCALActive` (`bt_nodes.py:104-117`) sits in the triage tree's
  T4 paths B and C (`trees.py:105`, `trees.py:114`) — live only in inverted
  mode — and in the DCS tree's MASCAL_Overload path (`trees.py:244`) — never
  ticked at all.
- `CheckFacilityUtilisation` (`bt_nodes.py:126-136`) sits ONLY in the two
  untick-ed trees: department routing (`trees.py:187`) and DCS
  (`trees.py:245-247`, `trees.py:262-264`). It is dormant even in inverted
  mode: the ticked triage tree does not contain it.

**Thresholds** (defaults `trees.py:40-61`, overridable per-build via the
`thresholds` argument; loader mapping `load_thresholds_from_loader`,
`trees.py:280-350`):

| Node instance | Threshold | Default | Loader-overridable? |
|---|---|---|---|
| Dept tree `FST_Util` (`trees.py:187`) | `dept_fst_capacity` | 0.90 (`trees.py:60`) | **No** — the loader mapping never sets it (`trees.py:341-348`); always 0.90 |
| DCS `DCS_Util80` (`trees.py:245-247`) | `dcs_mascal_utilisation` | 0.80 (`trees.py:52`) | Yes (`trees.py:331-333`) |
| DCS `DCS_Util95` (`trees.py:262-264`) | `dcs_critical_utilisation` | 0.95 (`trees.py:54`) | Yes (`trees.py:337-339`) |
| `CheckMASCALActive` (all instances) | none — truthiness read (`bt_nodes.py:115`) | — | — |

Note: the engine builds its inverted-mode triage tree with DEFAULTS
(`build_triage_tree()` bare call, `engine.py:173`) — the loader thresholds are
not passed in.

**Writer implication:** a facility writer that populates
`facility_utilisation` today feeds zero live readers at default toggles; its
first live consumer appears only when the DCS or department tree gains a tick
site (or `CheckFacilityUtilisation` joins a ticked tree). Populating the key
cannot flip a dormant decision until such a tick site exists — but the moment
one is added, the 0.80/0.90/0.95 thresholds above become live tripwires.

---

## FQ3 — Feature → blackboard key/reader map (#4, #42, #53, #58, #39)

Facility-group key shapes as declared (`blackboard.py:28-35`):
`facility_utilisation` float scalar · `facility_beds_available` dict ·
`department_queue_depth` dict · `department_capacity` dict ·
`fst_queue_depth` int scalar · `r1_beds_available` dict. Per Q7
(S1_PREBUILD_ANSWERS.md): only `facility_utilisation` and `mascal_active`
have readers today; for every other key the writer defines the contract.
Scalars are global (root-namespaced, shared storage) — last-writer-wins
across facilities; the dict keys are the per-facility-safe shapes.

| # | Feature (verdict line) | Consumer / reader | Keys consumed | What the writer must supply | Cadence | Per-facility or scalar |
|---|---|---|---|---|---|---|
| **#4** | Departments 2/3/4 — "Mechanism built/gated OFF (C7); needs the C2 blackboard writer + ON-path tests" (`MAAFI_VERDICT.md:102`) | Department-routing BT #27 via `CheckFacilityUtilisation` (`trees.py:187`); the engine's non-BT `_resolve_department` (`engine.py:982-1000`) reads the dept graph directly, not the blackboard | `facility_utilisation` (live); `department_queue_depth` / `department_capacity` (declared, reader-less) | Utilisation of the FACILITY BEING DECIDED, set immediately before that casualty's dept-tree tick; live sources: `queues[fid].count/capacity` (`engine.py:613-616`), dept resources (`engine.py:726-731`) | Per decision (per casualty, per facility arrival) — not wall-clock | Scalar key, so it must be re-set per decision (the verdict's "per-tick callback" shape, `MAAFI_VERDICT.md:83`); dict keys if written instead are per-facility-safe |
| **#42** | Facility-utilisation view — "View done; live occupancy needs the blackboard writer (C11)" (`MAAFI_ARBITER.md:175`; `MAAFI_VERDICT.md:73`) | Event-derived form: `FacilityLoadView` (`views.py:44-80`) — no blackboard. Live form: would read the facility group | `facility_utilisation` or `facility_beds_available` (dict) | Occupancy per facility on every occupancy-changing event (FACILITY_ARRIVAL, TREATMENT_END, DISPOSITION) | Per occupancy change | Per-facility (dict) — the scalar cannot represent N facilities. Note: `FacilityLoadView.current` decrements only on DISPOSITION (`views.py:65-66`), which fires at the FINAL facility — intermediate facilities never decrement, so the event-derived "current" overcounts intermediates; the live writer form fixes this |
| **#53-live** | Engine Room live blackboard inspector + occupancy — "Gated on C2 writer (C11)" (`MAAFI_VERDICT.md:108`) | `SimBlackboard.snapshot()` (`blackboard.py:182-184`) — dumps all 29 keys | The whole facility group (`blackboard.py:28-35`) | All six facility keys populated with live values | Per occupancy change (or per inspector poll) | Mixed as declared: 2 scalars + 4 dicts; scalars alias across facilities — inspector fidelity needs the dicts |
| **#58** | Weather/environment — "Needs C2 writer + `_WEATHER_KEYS` + consumer (C2)" (`MAAFI_VERDICT.md:123`) | None — `_WEATHER_KEYS` **do not exist** in `blackboard.py` (grep-confirmed), no consumer exists | New key group to be authored | New keys + a consumer; the writer alone is insufficient by the verdict's own line | Environment-event-driven | Scenario-scalar (weather is theatre-wide) unless zoned |
| **#39** | Stockout feedback — listed under Consumables 35-39: "`consumable.py` does not exist (F1); needs new module + `consumables` config block + bus subscriber + write-back loop for #39 feedback (C6)" (`MAAFI_VERDICT.md:120`) | None — no consumable keys in `ALL_KEYS` (`blackboard.py:65-72`), no module | New keys to be authored | See below — NOT this writer | Per consumption event (bus-driven) | Per-facility dicts |

**The handover's #39 question, resolved:** #39 does NOT belong to the C2
facility writer. The verdict's unblock list for the writer is exactly
"#4/#42/#53/#58" (`MAAFI_VERDICT.md:83`); #39 is filed under the consumables
bundle (`MAAFI_VERDICT.md:120`) whose write-back loop is a bus-subscriber
mechanism constrained by C6 (bus fires AFTER the routing decision —
CLAUDE.md Standing Constraints). The consumables write-back may REUSE the
writer's seam/pattern, but it is a separate mechanism with its own keys and
its own AC set — it should not be smuggled into S1.1's scope.

---

## FQ4 — Inverted-factory path and `mascal_active` at baseline

**Which toggle enables it:** `SimulationToggles.factory_mode == "inverted"`
(`engine.py:163`; factory dispatch `casualty_factory.py:301-310`). Default is
`"legacy"` (`mode.py:45`).

**Is `mascal_active` written at baseline (default toggles)? No.** The write
site `self.bb.set("mascal_active", arrival.is_mascal)`
(`casualty_factory.py:225`) is inside `InvertedCasualtyFactory.create` only.
The legacy factory has no blackboard reference (all `bb` usage in
`casualty_factory.py` is in the inverted class), and at default toggles the
engine never constructs a `SimBlackboard` at all (`engine.py:166-174` is the
inverted branch). Engine-side MASCAL detection (`MASCALDetector`,
`engine.py:210-212`, `engine.py:577-587`) emits MASCAL_ACTIVATE/DEACTIVATE
events but never touches the blackboard key. So at baseline the key exists
only if some other component instantiates a `SimBlackboard`, and then only as
its registered default `False` (`blackboard.py:38`, set at
`blackboard.py:95-96`).

**Who reads it and when:**

- `CheckMASCALActive` in the triage tree's T4 paths B and C (`trees.py:105`,
  `trees.py:114`), executed during `triage_bt.tick()` at
  `casualty_factory.py:231` — i.e. read once per casualty AT CREATION,
  inside the same `create()` call and immediately after the factory's own
  write at `casualty_factory.py:225`. Write→tick→read is atomic within one
  `create()`; nothing can interleave today.
- `CheckMASCALActive` in the DCS tree (`trees.py:244`) — never ticked (FQ1).

**Collision surface (C10), stated precisely:** today there is no live
collision — the sole reader consumes the factory's own same-call write. The
collision becomes real the moment an engine-side writer lands, because
`set_facility_context` writes `mascal_active=False` BY DEFAULT on every call
(`blackboard.py:151-160`): any writer invocation between a factory write and
a future reader (e.g. a ticked DCS tree, or any consumer added later) would
silently overwrite the per-casualty value. This is the basis of the
BUILD_S1 §6 required amendment (`mascal_active: bool | None = None`, write
only when not None) and the gate reviewer's `mascal_active` exclusion — both
S1.1 preconditions, untouched this session (blackboard.py read-only).
