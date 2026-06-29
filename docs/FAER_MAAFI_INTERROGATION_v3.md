# FAER-MIL MAAFI Codebase Interrogation v3
## Intrinsic / surface layer classification + testing-infrastructure audit

**Run via Claude Code against Pj-FAER-Dev repo.**
Paste each agent block as a separate CC prompt. Run in order:
Forward → Backward → Cross → Red Team → Arbiter (last).

**v3 adds:** a testing-infrastructure audit (F13, R16, R17) that checks
whether the codebase can support *behavioural* acceptance testing —
assertions about what the engine computes, not just whether it runs.
This determines whether the MVP acceptance-criteria mechanism
(MVP_ACCEPTANCE.md) is feasible as-is or needs harness work first.

---

## Layer classification — FAER-MIL (64 features)

Before running agents, every feature is pre-classified. The test:
**does removing this feature change the engine's computed output for
the same seed?** If yes → intrinsic. If no → surface.

### Intrinsic (43 features) — changes what the engine computes

| # | Feature | Sub-category |
|---|---------|-------------|
| 1 | Multi-POI arrival points | Arrival mechanism |
| 2 | Facility internal departments | Facility mechanism |
| 3 | Department capacity by type | Resource mechanism |
| 4 | Internal patient flow | Routing mechanism |
| 5 | Facility capability flags | Routing mechanism |
| 6 | Mobile facilities | Topology mechanism |
| 8 | Unit positioning | Arrival mechanism |
| 9 | Unit engagement intensity | Arrival mechanism |
| 10 | Threat zones | Contested mechanism |
| 11 | Dynamic threat changes | Contested mechanism |
| 12 | Vehicle type differentiation | Transport mechanism |
| 13 | Litter capacity per vehicle | Transport mechanism |
| 14 | Multi-modal transport selection | Transport mechanism |
| 15 | Physical transport constraint | Transport mechanism |
| 16 | Return-to-base vehicle cycle | Transport mechanism |
| 17 | MERT teams | Transport mechanism |
| 18 | MIST/ATMIST integration | Patient model |
| 19 | Injury-first casualty generation | Patient model |
| 20 | Vital signs trajectory | Patient model |
| 21 | Patient deterioration during hold | Patient model |
| 22 | Patient deterioration during transit | Patient model |
| 23 | Re-triage on deterioration | Clinical decisions |
| 24 | Multiple injury regions | Patient model |
| 25 | Surgical vs non-surgical pathway | Clinical decisions |
| 26 | Full BT triage tree | Clinical decisions |
| 27 | BT department routing | Clinical decisions |
| 28 | BT DCS decision | Clinical decisions |
| 29 | Alternative decision systems | Clinical decisions |
| 30 | MASCAL triage shift | Clinical decisions |
| 31 | CCP admission/discharge | PFC mechanism |
| 32 | CCP medic resource | PFC mechanism |
| 33 | PFC ceiling per triage | PFC mechanism |
| 35 | Blood product tracking | Consumable mechanism |
| 36 | Surgical kit tracking | Consumable mechanism |
| 37 | Oxygen/ventilator tracking | Consumable mechanism |
| 38 | Resupply events | Consumable mechanism |
| 39 | Stockout routing impact | Consumable mechanism |
| 46 | Route denial | Contested mechanism |
| 47 | Dynamic route destruction | Contested mechanism |
| 48 | Degraded comms | Contested mechanism |
| 49 | Counter-MEDEVAC threat | Contested mechanism |
| 55 | LLM-backed decision agents | Clinical decisions |
| 58 | Weather / environment layer | Contested mechanism |
| 59 | Medic fatigue / cognitive degradation | Clinical decisions |

### Surface (21 features) — changes observation, config, or analysis

| # | Feature | Sub-category |
|---|---------|-------------|
| 7 | Unit definitions | Config / narrative |
| 34 | PFC event stream | Observability |
| 40 | Survivability curves | Analytics |
| 41 | Golden hour compliance | Analytics |
| 42 | Facility utilisation over time | Analytics |
| 43 | Process mining / XES | Analytics / export |
| 44 | Ensemble confidence intervals | Analytics |
| 45 | Sensitivity analysis framework | Analytics |
| 50 | YAML-driven scenarios | Config |
| 51 | Operational context presets | Config |
| 52 | HADR variant | Config |
| 53 | Engine Room / X-Ray demo | Visualisation |
| 54 | Auto-generated AAR / Report Agent | Analytics / export |
| 56 | OPORD-to-config generation | Config |
| 57 | Agent memory across runs | Analytics / learning |
| 60 | Shadow agent / comparator | Analytics |
| 61 | Statistics upgrade | Analytics |
| 62 | MNEMOSYNE data pipeline export | Export |
| 63 | Supply chain cascade prediction | Analytics |
| 64 | Lessons learned KG integration | Export |

### Boundary cases (rationale)
- **#7 Unit definitions**: Narrative labels only. No effect on simulation — units don't generate casualties (that's #9 engagement intensity, which IS intrinsic). Classification: **surface**.
- **#30 MASCAL triage shift**: Changes triage thresholds under surge. Different patients get different categories → different routing → different outcomes. Classification: **intrinsic**.
- **#34 PFC event stream**: Emits events but doesn't change hold logic. The engine holds patients identically whether events are emitted or not. Classification: **surface**.
- **#44 Ensemble CI**: Runs the engine N times and computes statistics. The engine itself is unchanged. Classification: **surface**.
- **#40-42 Analytics views**: Read-only subscribers to EventBus. Engine runs identically without them. Classification: **surface**.

---

## Agent 1 — Forward (greedy addition)

```
FORWARD AGENT — MAAFI Codebase Interrogation v2

You are the Forward agent in a MAAFI protocol run. Your goal is to
measure the true marginal cost of each feature and build a greedy
addition sequence, PRIORITISING INTRINSIC features over surface.

Every feature has been pre-classified as INTRINSIC (changes engine
computation) or SURFACE (changes observation/config/analysis). When
two features have similar marginal gain, the intrinsic one goes first.
A surface feature CANNOT be selected before the intrinsic feature it
depends on.

Answer all 13 questions. Cite file paths and line numbers as evidence.
Write answers to docs/MAAFI_FORWARD.md.

F1. ORPHAN DETECTION
    For each of: ccp.py, departments.py, pfc.py, vitals.py,
    transport.py, consumable.py, mining.py, xes_exporter.py, delay.py
    List all functions/classes DEFINED but NEVER CALLED from engine.py
    or any live code path. Tag each orphan as INTRINSIC or SURFACE
    based on whether it would change engine output if wired.

F2. TOGGLE AUDIT
    List every SimulationToggles field with default value. For each:
    (a) Is toggled-ON path tested? Is toggled-OFF path tested?
    (b) Is it ALWAYS ON in every test config?
    (c) Classify: does this toggle gate INTRINSIC logic (routing,
        treatment, PFC) or SURFACE logic (analytics, export)?

F3. SCHEMA INSPECTION — FACILITY
    Print the full Facility dataclass from schemas.py.
    Which of has_surgery, has_blood, has_xray, has_ventilator,
    departments, capability_flags ACTUALLY EXIST as fields?
    Tag each existing field: is it READ by routing.py (intrinsic
    impact) or only by analytics/display code (surface impact)?

F4. ROUTING DECISION INPUTS
    In routing.py, what does get_next_destination() currently read?
    Does it check facility attributes beyond role level? Does it
    call TreatmentNetwork? Trace the full decision path.
    This is INTRINSIC — the routing algorithm IS the mechanism.

F5. TREATMENT NETWORK API
    List ALL public methods on TreatmentNetwork. For each: called
    from engine.py or anywhere else, or defined-only?
    Does update_congestion() exist and get called?
    Classify each method: INTRINSIC (affects routing/travel time)
    or SURFACE (read-only query for analytics).

F6. ARRIVAL PARAMETERISATION
    In arrivals.py: single scalar rate or per-source rates? Does it
    accept multiple POI facility IDs? What would multi-POI (#1)
    actually require changing? This is INTRINSIC — arrival
    distribution directly changes who arrives where.

F7. CASUALTY FACTORY TRACE
    Trace CasualtyFactory inverted mode end-to-end:
    injury → triage → severity → regions → vitals.
    Is MIST/ATMIST populated? Which blackboard keys get written?
    All INTRINSIC — the patient model IS the mechanism.

F8. ENSEMBLE + SWEEP COMPATIBILITY
    Does EnsembleBuilder accept parameterised config for sweeps?
    What is output format? Can results be diffed automatically?
    This is SURFACE — the engine runs identically regardless.
    But note: sweep is only as good as the intrinsic features
    it sweeps over. Flag which intrinsic features MUST exist
    before a sweep produces meaningful results.

F9. YAML CONFIG SCHEMA + VERSIONING + CROSS-BLOCK COUPLING
    What does the YAML loader validate against? All top-level keys?
    Type validation or silent accept? SURFACE feature, but critical
    for all intrinsic features that are config-driven.

    Schema evolution (from prior MAAFI findings):
    (a) Is there a schema version field? Migration strategy?
    (b) Is validation via Pydantic models, JSON Schema, or raw dicts?
        If Pydantic: does the model auto-generate JSON Schema?
    (c) When a new intrinsic feature adds a YAML key, what happens
        to old scenario files that lack it — default, error, or
        silent ignore?
    (d) What are the logical config blocks (topology, units,
        transport, threat, clinical)? Print the top-level structure.

    Cross-block coupling (these blocks are NOT orthogonal):
    (e) Does unit positioning (#8) reference facility IDs from
        topology? What if the ID doesn't exist?
    (f) Do threat zones (#10) reference edge IDs? What if the
        edge is removed from topology?
    (g) Do vehicle type configs (#12) reference route types from
        topology? What constrains their compatibility?
    (h) If config supports overlays/presets (#51), how many
        overlay combinations are possible vs tested?

    Config coupling mirrors engine coupling. Bad config →
    bad intrinsic state → wrong numbers with no error.

F10. DEPENDENCY MANIFEST
     Print requirements/dependencies. Version pins? Would adding
     pm4py, scipy, or anthropic cause conflicts?

F11. BLACKBOARD COMPLETENESS
     Print all 29 SimBlackboard keys grouped by 6 groups.
     For each: who WRITES and who READS?
     Written-never-read = dead intrinsic state.
     Read-never-written = missing intrinsic data source.
     Is there capacity for new groups (departments, weather,
     consumables)?

F12. EVENT TYPE VOCABULARY
     Run the engine and print all emitted event types.
     Cross-reference against declared types in models.py.
     Declared-but-never-emitted = phantom features.
     Tag each: does the event type represent an INTRINSIC state
     change (ARRIVAL, TREATED, ROUTE_DENIED) or SURFACE observation
     (logged for analytics only)?

F13. TEST INFRASTRUCTURE INVENTORY
     The MVP needs behavioural acceptance tests (assertions about
     WHAT the engine computes, not just whether it runs). Audit
     whether the test harness can express these:
     (a) Is there a fixture/helper that runs the engine to completion
         and returns the event log for assertion?
     (b) Is there a fixture that runs an ENSEMBLE (N replications)
         and returns aggregate output for assertion?
     (c) Can a test currently assert a property over the event stream
         (e.g., "no event where a surgical casualty arrives at a
         non-surgical facility")? Show an example if one exists.
     (d) Can a test assert a property over ensemble output (e.g.,
         "mean golden-hour compliance increases monotonically as
         R1 beds increase")?
     (e) What test framework and assertion style is used? pytest
         plain asserts, hypothesis property-based, or custom?
     This determines whether MVP_ACCEPTANCE.md criteria can be
     written against the existing harness or need harness work first.
```

---

## Agent 2 — Backward (ablation)

```
BACKWARD AGENT — MAAFI Codebase Interrogation v2

You are the Backward agent. Your goal is to identify dead code,
redundant abstractions, and expendable features — with LAYER AWARENESS.

Key rule: removing an INTRINSIC feature has cascading impact (surface
features that depend on it become meaningless). Removing a SURFACE
feature never invalidates an intrinsic feature. Factor this asymmetry
into your loss-on-removal estimates.

Answer all 12 questions. Write to docs/MAAFI_BACKWARD.md.

B1. IMPORT ORPHANS
    List every .py file never imported by any other file (excl tests).
    Tag each: would wiring it add INTRINSIC capability (new mechanism)
    or SURFACE capability (new analytics/config)?

B2. INLINE DUPLICATION
    In engine.py, identify inline logic duplicating extracted modules
    (routing.py, pfc.py, ccp.py, metrics.py, emitter.py). List with
    line ranges and the module that supersedes it.
    All inline legacy is INTRINSIC — it's the old mechanism path.

B3. YIELD POINT AUDIT
    Grep entire codebase for yield self.env, yield env.timeout,
    yield *.request. List every occurrence with file:line.
    Any yields outside engine.py violate the 5-yield invariant.
    Yields are INTRINSIC — they ARE the time progression mechanism.

B4. TEST DEPTH — EXTRACTED MODULES
    For pfc.py, ccp.py, routing.py, metrics.py, emitter.py:
    (a) Test count?
    (b) Unit-only or integration through engine.py?
    (c) Toggle ON vs OFF seed-matched equivalence tested?
    Tag each module: INTRINSIC extraction or SURFACE extraction?

B5. BOUNDARY VIOLATION SCAN (HC-5, HC-6)
    Grep for: import simpy in decisions/ files, import networkx in
    decisions/ files, import py_trees in simulation/ or network/ files.
    Report ALL violations. Boundary violations corrupt the integration
    layer that all INTRINSIC features depend on.

B6. CALL-SITE VERIFICATION — "DONE" CLAIMS
    For each "done/built" feature:
    build_department_routing_tree() (#27) — INTRINSIC
    build_dcs_tree() (#28) — INTRINSIC
    MASCALTriageShift (#30) — INTRINSIC
    compute_survivability() (#40) — SURFACE
    GoldenHourView (#41) — SURFACE
    FacilityLoadView (#42) — SURFACE
    pfc.compute_deterioration() (#21) — INTRINSIC
    Is it (a) defined, (b) called from live code, (c) tested?
    Note: INTRINSIC "done" claims without tests are higher risk
    than SURFACE "done" claims without tests.

B7. PHANTOM EVENT TYPES
    List all declared event types in models.py. Grep for emission.
    Flag declared-but-never-emitted. Check specifically:
    HOLD_START, PFC_START, PFC_END, PFC_CEILING_EXCEEDED.
    These are SURFACE (observability) but their absence means PFC
    intrinsic logic (#31-33) can't be verified via events.

B8. ORPHANED ANALYTICS DEPENDENCIES
    For delay.py, mining.py, xes_exporter.py:
    (a) What do they import? (b) In dependency manifest?
    (c) Can they run or will they ImportError?
    All SURFACE. But if they can't run, #43 process mining is
    not "exists, orphaned" — it's "broken."

B9. TEST HEALTH BASELINE
    Run pytest --tb=short -q. Report total, passed, failed,
    skipped, xfail. Has count drifted from claimed 82/82 or 99?

B10. DEAD TOGGLE SCAN
     Toggles always ON in every config = permanent code in disguise.
     List candidates for toggle removal. Tag: INTRINSIC or SURFACE?

B11. ENGINE.PY ANATOMY
     Count lines in engine.py. Break down:
     imports, __init__, _patient_journey(), arrivals, helpers,
     inline legacy behind toggle-OFF.
     What percentage is active INTRINSIC logic vs dead legacy?

B12. UNUSED SCHEMA FIELDS
     In schemas.py: Casualty, Facility, and other core dataclasses.
     Fields DEFINED but never READ anywhere. Tag each:
     INTRINSIC (would change routing/treatment if read) or
     SURFACE (narrative/display only).
     "Partially exists" claims in the feature list often rest
     on these aspirational fields.
```

---

## Agent 3 — Cross (interaction)

```
CROSS AGENT — MAAFI Codebase Interrogation v2

You are the Cross agent. Your goal is to map feature-to-feature
dependencies, synergies, and conflicts — WITH LAYER AWARENESS.

Three interaction types:
- INTRINSIC × INTRINSIC: mechanism coupling (highest impact)
- INTRINSIC × SURFACE: the surface wraps the intrinsic (ordering constraint)
- SURFACE × SURFACE: usually independent (low impact)

Answer all 14 questions. Write to docs/MAAFI_CROSS.md.

C1. ROUTING CONSUMER TRACE
    If routing.py is modified for #5 capability flags (INTRINSIC),
    list ALL consumers of get_next_destination() and other routing
    public functions. Tag each consumer: INTRINSIC (engine treatment
    path) or SURFACE (analytics display).
    This maps the blast radius: intrinsic consumers break,
    surface consumers just show different data.

C2. BLACKBOARD CAPACITY
    Can SimBlackboard accommodate new key groups for:
    - Department state (#4, INTRINSIC)
    - Weather (#58, INTRINSIC)
    - Consumable levels (#35-39, INTRINSIC)
    Hard limit on keys/groups? Structural change or just new keys?

C3. MULTI-EDGE GRAPH SUPPORT
    Is TreatmentNetwork a DiGraph or MultiDiGraph? Can edges hold
    multiple transport modes? What does multi-modal transport (#14,
    INTRINSIC) actually require?

C4. PFC → RE-TRIAGE DATA PATH
    pfc.compute_deterioration() (#21 INTRINSIC) updates severity.
    Does it write to blackboard, return value, or modify patient?
    How would re-triage (#23 INTRINSIC) consume the output?
    This is an INTRINSIC × INTRINSIC synergy — both mechanisms
    must share a data path.

C5. MULTI-POI CONCURRENCY
    Multi-POI (#1 INTRINSIC) spawning from concurrent SimPy processes:
    (a) DISPOSITION == ARRIVAL invariant safe?
    (b) Shared mutable state (counters, ID generators)?
    (c) Seed sequence determinism under concurrent POIs?

C6. EVENT ARCHITECTURE
    Is there an EventBus / pub-sub system? Show the code.
    This is the boundary between INTRINSIC (engine emits) and
    SURFACE (subscribers observe). If no EventBus exists:
    - #35-39 consumables (INTRINSIC) can't subscribe to treatment events
    - #34 PFC event stream (SURFACE) can't observe hold events
    - #54 Report Agent (SURFACE) has nothing to read

C7. TREATMENT YIELD SPLITTING
    If departments (#2-4 INTRINSIC) split SimPy resource pools,
    does Y5 need restructuring? This is the hardest INTRINSIC ×
    INTRINSIC interaction — resource subdivision affects every
    patient journey.

C8. PHYSICAL TRANSPORT × BATCHING
    Toggle physical_transport (#15 INTRINSIC) + batching logic.
    Vehicle held exclusively AND waiting to batch = deadlock risk?
    Trace the interaction. INTRINSIC × INTRINSIC.

C9. ENSEMBLE OUTPUT FORMAT
    EnsembleBuilder (#44 SURFACE) output structure.
    If sensitivity_sweep (#45 SURFACE) calls it in a loop, can
    outputs be concatenated and diffed? SURFACE × SURFACE — low
    mechanism risk but determines usability.

C10. BLACKBOARD WRITE CONFLICTS
     Map ALL blackboard key writers across modules. Do any two
     modules write to the SAME key? INTRINSIC × INTRINSIC race
     condition if ticks interleave. Tag each writer module.

C11. ENGINE ROOM DATA DEPENDENCIES
     Engine Room demo (#53 SURFACE) needs: event log, facility
     occupancy, casualty locations, module attribution, blackboard
     snapshots. Which exist? Which need new capture?
     This is SURFACE depending on INTRINSIC event emission —
     identify the intrinsic prerequisites.

C12. MNEMOSYNE EXPORT COMPATIBILITY
     Print 5 sample events from engine output. Compare fields
     against MnemosyneGenerator's survival dataset schema.
     How much mapping needed? This is SURFACE (#62) depending
     on INTRINSIC event field completeness (#34, emitter quality).

C13. CROSS-LAYER DEPENDENCY MAP
     For every SURFACE feature in the 64-feature list, identify
     which INTRINSIC feature(s) it depends on being correct.
     Produce a table:
     | Surface # | Surface name | Depends on intrinsic # | Why |
     This is the master ordering constraint — no surface feature
     can be in a higher tier than its intrinsic dependency.

C14. CONFIG-TO-ENGINE COUPLING MAP
     The YAML config has logical blocks (topology, units, transport,
     threat, clinical). Map which config blocks feed which INTRINSIC
     engine features:
     | Config block | Engine module(s) it feeds | Features affected |
     Then check: if config block A changes (e.g., topology adds a
     facility), does config block B (e.g., unit positioning) need
     updating? Produce a config-block coupling matrix:
     | Block changed | Blocks that may break | Validation exists? |
     This is the config-layer mirror of C1 (routing blast radius)
     and C10 (blackboard write conflicts). Config coupling that
     isn't validated by the loader will produce valid-looking but
     wrong intrinsic state.
```

---

## Agent 4 — Red Team (adversarial)

```
RED TEAM AGENT — MAAFI Codebase Interrogation v2

You are the Red Team agent. Challenge assumptions, verify claims,
stress-test "done" assertions — WITH LAYER AWARENESS.

Key adversarial principle: a SURFACE feature built on an incorrect
INTRINSIC foundation is WORSE than no feature at all, because it
creates false confidence. A beautiful dashboard showing wrong numbers
is more dangerous than no dashboard.

Answer all 17 questions. Run actual tests where indicated.
Write to docs/MAAFI_REDTEAM.md.

R1. DETERMINISM TEST
    Run full test suite with seed=42 twice. Byte-identical?
    This tests INTRINSIC correctness — the foundation.

R2. CLAIM-TEST MATRIX
    For every "done/built" feature, find the test. Create table:
    | # | Name | Layer | Claimed | Test file:func | Verdict |
    INTRINSIC features without tests are HIGH RISK.
    SURFACE features without tests are MEDIUM RISK.

R3. PERFORMANCE BASELINE
    Time single NB32 run. Time 100 replications.
    Extrapolate: 100 reps × 4 param values (#45 sweep).
    Under 5 min = acceptable. Over 20 min = problematic.
    Performance limits gate ALL surface analytics features.

R4. HOLD GATE INTEGRATION TEST
    15 min retry → PFC at 60 min → timeout at 8 hrs.
    Integration test for full sequence? Or unit-only?
    This is INTRINSIC — the hold gate is a core state machine.
    If no integration test, write one and see if it passes.

R5. STRANGLER VALIDATION — CURRENT
    For each Phase 1 toggle (routing, metrics, emitter, pfc):
    ALL OFF vs ALL ON, same seed. Outputs identical?
    These are INTRINSIC extractions — if they've drifted,
    the extracted mechanisms are suspect.

R6. STRESS CEILING
    Run: 500 casualties, 2880 min, IRON BRIDGE topology.
    Complete? Runtime? Memory bounded? Break point?
    This gates the LSCO showcase — if the INTRINSIC engine
    can't handle scale, no SURFACE feature matters.

R7. TECHNICAL DEBT INVENTORY
    Grep engine.py for TODO, FIXME, HACK, XXX, NOQA, type: ignore.
    List with line numbers. Every debt item in engine.py is
    INTRINSIC debt — it affects the mechanism.

R8. CONFIG VALIDATION + SCHEMA VERSIONING
    Feed YAML loader:
    (a) Facility with no coordinates
    (b) Edge referencing nonexistent facility
    (c) Negative bed count
    (d) Unknown key (e.g., "weather: cloudy")
    (e) Missing required section
    (f) A scenario file from 3 months ago — does it still load
        after recent schema changes, or does it break silently?
    SURFACE (#50) but gates every config-driven intrinsic feature.

    Then check schema evolution:
    (g) Is there a schema version field in the YAML format?
    (h) Is there any migration strategy (auto-upgrade, deprecation
        warnings, semver on config format)?
    (i) If a new intrinsic feature (#5 capability flags, #58 weather)
        adds a YAML key, what happens to existing scenario files
        that lack that key — default, error, or silent ignore?
    (j) Is there a Pydantic model (or equivalent) validating config,
        or is it raw dict access? If Pydantic: does the model
        generate a JSON Schema for documentation/validation?

    Without schema versioning, every future intrinsic feature that
    adds a config parameter risks breaking existing scenarios silently.
    This is the strongest config-layer finding from prior MAAFI runs.

R9. REPLICATION ISOLATION
    Does each EnsembleBuilder replication get fresh SimPy env?
    Any global mutable state leaking between reps?
    SURFACE (#44) but if broken, all analytics are invalid —
    correlated runs produce falsely narrow CIs.

R10. IMPORT OVERHEAD
     Time `import faer_dev`. Heavy module-level imports?
     If >1 second, it's a hidden tax on 100-rep sweeps.

R11. GRAPH ROUTING CORRECTNESS
     IRON BRIDGE, enable_graph_routing=True, two R1 nodes.
     Both receive casualties? Set one R1 to 2 beds, other to 20.
     Does Dijkstra shift traffic? This is INTRINSIC — the routing
     mechanism must work correctly before any surface feature
     (sensitivity sweep, Engine Room) can display meaningful results.

R12. PHASE 1.5 REGRESSION
     Do all original Phase 1 tests still pass after Phase 1.5?
     New tests specifically for graph routing? How many?

R13. LAYER MISCLASSIFICATION CHALLENGE
     Review the layer classification table at the top of this
     document. Challenge any feature you believe is misclassified:
     - Is any "surface" feature actually changing engine output?
       (e.g., does PFC event emission #34 have side effects?)
     - Is any "intrinsic" feature actually just labelling/config?
       (e.g., is #7 unit definitions truly surface, or does it
       feed into arrival weighting?)
     Produce a table of challenged classifications with evidence.

R14. CONFIG OVERLAY COMBINATORICS
     If the config system supports overlays or composable presets
     (e.g., LSCO base + contested overlay + MASCAL overlay):
     (a) How many distinct overlay combinations exist or are possible?
     (b) How many are tested?
     (c) Do overlays compose cleanly, or can overlay A + overlay B
         produce an invalid state (e.g., overlay A sets 2 POIs,
         overlay B references a POI that only exists in overlay C)?
     (d) Is there a validation step after overlay composition?
     If overlays compose freely, the test surface is combinatorial.
     5 overlays × 4 topologies × 3 threat levels = 60 combinations.
     What fraction is covered? This gates #51 operational presets
     and #52 HADR variant — both are overlay-based.

R15. CONFIG BLOCK COUPLING
     The YAML config has logical blocks: topology, units, transport,
     threat, clinical. These are NOT orthogonal:
     - Topology changes can invalidate unit positioning (#8)
     - Threat zones (#10) reference edges that may not exist
     - Vehicle types (#12) constrain which routes are available
     - Facility capabilities (#5) affect routing decisions
     Check: does the config loader validate CROSS-BLOCK references?
     If topology defines facilities A, B, C but a threat zone
     references edge A→D (where D doesn't exist), what happens?
     If unit positioning references POI-NORTH but topology only
     has POI-FRONT, what happens?
     Cross-block coupling in config mirrors cross-feature coupling
     in the engine. Surface validation gates intrinsic correctness.

R16. BEHAVIOURAL ASSERTION CAPABILITY
     The MVP acceptance criteria are behavioural — they assert what
     the engine computes, not whether it runs. Test whether the
     harness can express these:
     (a) Write a throwaway test asserting "no casualty with
         needs_surgery=True is ever treated at a facility with
         has_surgery=False." Does the harness let you read the
         event log and make this assertion? Does it currently PASS
         (capability routing works) or have nowhere to plug in
         (routing ignores capability)?
     (b) Write a throwaway test asserting an ensemble property:
         run 20 reps at R1=4 beds and 20 reps at R1=8 beds, assert
         mean golden-hour compliance is higher with more beds.
         Can the harness express this? Does it pass?
     Report whether these assertions are WRITABLE against the
     current harness, and whether they PASS. If not writable,
     the acceptance mechanism needs harness work first.

R17. STUB-PASSES-TESTS CHECK
     This is the failure mode proved in HEPHAESTUS: a feature can
     pass all tests while being mechanistically wrong.
     Take ONE existing "done" intrinsic feature — capability-aware
     routing if it exists, else triage. Deliberately break it
     (e.g., make routing ignore capability flags, or make triage
     always return T3). Run the full test suite.
     Does ANY existing test catch the break?
     - If yes: the suite tests CORRECTNESS. Good.
     - If no: the suite tests EXECUTION only. Every "done" claim
       is "runs without error," not "computes correctly." This
       is the single most important finding for MVP risk.
     Revert the break after testing.
```

---

## Agent 5 — Arbiter (synthesis)

```
ARBITER AGENT — MAAFI Codebase Interrogation v2

Read docs/MAAFI_FORWARD.md, docs/MAAFI_BACKWARD.md,
docs/MAAFI_CROSS.md, and docs/MAAFI_REDTEAM.md.

You score on 5 axes. The split value axis means INTRINSIC features
have a natural 10-point advantage (0.25 max vs 0.15 max) over
SURFACE features. This is deliberate — the mechanism must be correct
before the wrapper can be meaningful.

| Axis | Weight |
|------|--------|
| Mechanistic fidelity | 0.25 (intrinsic only, surface scores 0) |
| Analytical utility | 0.15 (surface only, intrinsic scores 0) |
| Parsimony | 0.20 |
| Robustness | 0.20 |
| Readiness | 0.20 |

Layer-aware tiebreaker: no SURFACE feature can be in a higher tier
than the INTRINSIC feature it depends on (use Cross C13 map).

Answer these 11 questions. Write to docs/MAAFI_ARBITER.md.

A1. FORWARD vs RED TEAM CONFLICTS
    For features where Forward says "easy/exists" and Red Team
    says "untested/unverified": read the file, count real code,
    check tests. Verdict per feature:
    CONFIRMED EASY | HARDER THAN CLAIMED | NOT ACTUALLY DONE
    Tag each with layer.

A2. SYNERGY BUNDLE MERGE RISK
    For each bundle:
    - #1+#8 multi-POI + positioning (INTRINSIC × INTRINSIC)
    - #12+#13 vehicle types + capacity (INTRINSIC × INTRINSIC)
    - #20+#23 vitals + re-triage (INTRINSIC × INTRINSIC)
    - #2+#3+#4 departments triple (INTRINSIC × INTRINSIC × INTRINSIC)
    - #44+#45 ensemble + sweep (SURFACE × SURFACE)
    Do both touch same file? Parallel or sequential dev?

A3. BACKWARD EXPENDABILITY vs FORWARD DEPENDENCY
    Features Backward flagged expendable — does any MVP or Tier 1
    feature depend on them? Check cross-layer: if an orphaned
    intrinsic file is removed, does any surface feature break?

A4. STRANGLER MIGRATION HEALTH
    Extracted-module code vs inline-engine code ratio.
    Is migration on track for ~800 LOC? Should new INTRINSIC
    features go in extracted modules or engine.py?

A5. COMPLETION MOMENTUM RANKING
    For all 64 features:
    momentum = (lines_written / lines_needed) × has_test
    Rank top 15 by momentum. Tag each with layer.
    When two features tie on score, prefer: (a) intrinsic over
    surface, then (b) higher momentum.

A6. MVP GROUND TRUTH
    Update the 10-feature MVP based on all agent reports:
    | # | Name | Layer | Claimed LOC | Actual LOC | Risk | Verdict |
    Are any MVP features harder than claimed?
    Does the MVP have enough INTRINSIC features to produce
    meaningful results, or is it surface-heavy?

A7. CRITICAL PATH WITH LAYER ORDERING
    Draw the MVP wiring sequence respecting the rule:
    intrinsic before surface that depends on it.
    What MUST wire first? What parallelises?

    Expected order (verify against codebase):
    1. #5 capability flags (INTRINSIC) — routing needs this first
    2. #1+#8 multi-POI + positioning (INTRINSIC) — arrival mechanism
    3. #10 threat zones (INTRINSIC) — contested routing
    4. #30 MASCAL triage shift (INTRINSIC) — surge mechanism
    5. #44 ensemble CI (SURFACE) — activate, measures intrinsic changes
    6. #45 sensitivity sweep (SURFACE) — last, wraps everything above

    Verify:
    - Does #5 need to land before #1+#8, or are they independent?
    - Does #10 require any routing.py changes from #5?
    - Can #1+#8 and #10 parallelise, or do they share arrivals.py?
    - Does #30 MASCAL shift need #1 multi-POI to trigger per-POI?
    - Does #45 sweep call #44 ensemble, or build beside it?

A8. CROSS-LAYER DEPENDENCY AUDIT
    Using Cross agent's C13 map, verify: does any SURFACE feature
    in Tier 0-2 depend on an INTRINSIC feature in Tier 3-4?
    If so, either promote the intrinsic or demote the surface.

A9. LAYER BALANCE PER TIER
    For the final tier assignments, compute intrinsic:surface ratio
    per tier. A healthy pattern is:
    - Tier 0-1: intrinsic-heavy (build the mechanism first)
    - Tier 2: mixed (polish with surface features)
    - Tier 3-4: surface-heavy (defer analytics until mechanism stable)
    If Tier 1 is surface-heavy, something is wrong.

A10. FINAL TIER ASSIGNMENTS
     Produce the updated MAAFI verdict for all 64 features with
     layer classification enforced. Format:

     TIER 0 (activate): [list, tagged I/S, with evidence]
     TIER 1 (MVP wire): [list, tagged I/S, actual LOC, risk]
       — Must be intrinsic-dominant
     TIER 2 (showcase polish): [list, tagged I/S]
       — Mixed intrinsic + surface allowed
     TIER 3 (Phase 2 bundles): [list, tagged I/S, bundle groups]
     TIER 4 (parked): [list, tagged I/S, reason]

     Save as docs/MAAFI_VERDICT.md

A11. ACCEPTANCE-TESTING FEASIBILITY VERDICT
     From F13, R16, R17 — produce a clear verdict on whether the
     MVP acceptance-criteria mechanism (MVP_ACCEPTANCE.md) can run
     against the current harness:
     (a) Can behavioural assertions over the event log be written
         today? (F13c, R16a)
     (b) Can ensemble-property assertions be written today? (F13d, R16b)
     (c) Does the existing suite catch a deliberately broken feature,
         or test execution only? (R17)
     Output one of three verdicts:
     - READY: harness supports behavioural acceptance tests, write
       MVP_ACCEPTANCE.md criteria directly
     - HARNESS GAP: add a thin acceptance-test fixture first
       (estimate LOC), then write criteria
     - CORRECTNESS BLIND: existing tests check execution only — this
       is a prerequisite fix before ANY MVP feature is trusted as done
     Save the verdict at the top of docs/MAAFI_VERDICT.md.
```

---

## Post-run checklist

1. `docs/MAAFI_FORWARD.md` — 13 questions (incl F13 test infrastructure)
2. `docs/MAAFI_BACKWARD.md` — 12 questions, layer-tagged
3. `docs/MAAFI_CROSS.md` — 14 questions (incl C13 cross-layer map, C14 config coupling)
4. `docs/MAAFI_REDTEAM.md` — 17 questions (incl R13 misclassification, R14 overlay combinatorics, R15 config coupling, R16 behavioural assertion, R17 stub-passes-tests)
5. `docs/MAAFI_ARBITER.md` — 11 questions (incl A11 acceptance-testing feasibility)
6. `docs/MAAFI_VERDICT.md` — final verdict + acceptance-testing feasibility at top

Total: 67 questions across 5 agents.

Expected shifts from v1: surface features that were Tier 1 will drop
to Tier 2 unless they're config features that gate intrinsic wiring.
Intrinsic features that were Tier 2 will promote to Tier 1 if their
mechanism is more important than previously scored. The MVP should
become more intrinsic-dominant.

Specific shifts already applied in the pre-interrogation verdict:
- #45 sweep: Tier 0 → Tier 1 (gated on #5 intrinsic)
- #30 MASCAL: Tier 0 → Tier 1 (needs trigger wiring, not zero LOC)
- #33 PFC ceiling: Tier 3 → Tier 2 (intrinsic, easy, changes mortality)
- #7 unit definitions: Tier 1 → Tier 2 (surface, narrative only)
- #53 Engine Room: Tier 2 → Tier 3 (surface, mechanism must settle first)
- Tier 1 composition: was ~50/50 → now 5 intrinsic, 2 surface

The interrogation may shift these further once ground truth is known.

Config-layer findings integrated from prior MAAFI run on YAML explainer:
- Schema versioning is missing — R8 now probes this explicitly
- Config blocks are NOT orthogonal — F9, C14, R15 probe cross-block coupling
- Overlay combinatorics create untested state space — R14 quantifies this
- Pydantic → JSON Schema path exists but may not be wired — F9 checks
These findings mean #50 YAML scenarios stays Tier 0 but carries three
caveats (versioning, cross-block validation, overlay testing).

