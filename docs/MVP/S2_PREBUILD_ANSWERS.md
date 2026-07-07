# S2_PREBUILD_ANSWERS — RNG architecture interrogation (Q0–Q9)

*2026-07-07 · produced for BUILD_S2.md finalisation · read-only interrogation; no src/ or
tests/ change; diagnostic scripts in session scratchpad (`q0_roster_hash.py`,
`q5_draw_volume.py`). Baseline HEAD 4b28bad, 134 tests collected.*

---

## Q0 — ROSTER-HASH DIAGNOSTIC (protocol 0a)

**Protocol:** identical to RNG_DIAGNOSTIC.md — coin preset, seed 42, `duration_min=1440`,
`max_patients=10⁶`, undrained, via the F0.2 harness (`tests/harness.py:30`).
Config A = all-default `SimulationToggles`; Config C = `enable_extracted_routing=True,
enable_graph_routing=True, enable_capability_routing=True`. Roster source: the canonical
ARRIVAL event payload, which carries exactly the eight requested fields
(`engine.py:681-688` — injury_mechanism, severity, recommended_triage, bypass_role1,
requires_dcs, priority, plus casualty_id and sim_time from the event envelope).

**Raw result:**

| | Config A | Config C |
|---|---|---|
| Arrivals | **31** | **30** (A-only id: CAS-0031) |
| Roster hash (all 8 fields) | `c42b6fba…332efb` | `0fc5d605…aa0ac3d` |
| Attribute-only hash (sim_time dropped) | `c07a008d…f641160` | `7d8d019e…c18f888` |

Per-field mismatch counts over the 30 shared ids:

| field | mismatches / 30 |
|---|---|
| mechanism | 19 |
| severity | 26 |
| recommended_triage | 17 |
| priority | 17 |
| bypass_role1 | 6 |
| requires_dcs | 2 |
| sim_time | 27 (identical prefix CAS-0001–0003, k=3 as in RNG_DIAGNOSTIC) |

**First divergent casualty: CAS-0003** — fields `mechanism` (A=BLAST, C=GSW), `severity`
(A=0.10411, C=0.38151), `recommended_triage` (A=T3, C=T2), `priority` (A=3, C=2). Its
`sim_time` is still identical: attribute divergence begins ONE CASUALTY EARLIER than the
timing divergence (k=3, CAS-0004). Mechanism: CAS-0003's interarrival draw landed on an
identical stream position, but its identity draws (triage/mechanism/region/severity) execute
at spawn (t=168.04), by which time A's and C's journey draws (treatment exponentials,
transport normals) have consumed different stream positions. Consistent with, and extending,
the RNG_DIAGNOSTIC verdict.

### VERDICT: **BOTH** — attribute contamination AND timing divergence.

Casualty identity is not config-invariant: "the same person under any doctrine" is false
as-built, in attributes and not merely spawn times. **0c's scope is therefore REPAIR of
attribute invariance, not formalisation of an invariance that already holds.**

---

## Q1 — FULL RNG CENSUS

### Generator constructions

| Site | Owning object | Seeded from | Status |
|---|---|---|---|
| `src/faer_dev/simulation/engine.py:142` `self._rng = np.random.default_rng(seed)` | `PolyhybridEngine._rng` | `seed` param ← `builder.py:158` ← `builder.py:144` (`seed` arg, else `scenario["seed"]`, else 42) | **SOLE seeded source — CONFIRMED** |
| `casualty_factory.py:48`, `:194` | Legacy/Inverted factory | `rng or np.random.default_rng()` | defensive fallback; engine always passes `self._rng` (`engine.py:179, 188`; inverted sampler `engine.py:170-172`) — dormant |
| `arrivals.py:112` | `ArrivalProcess` | same fallback pattern | dormant — engine passes `self._rng` (`engine.py:1246-1252`, `engine.py:1291-1298`) |
| `transport.py:204` | `TransportPool` | same fallback pattern | dormant — engine passes `self._rng` (`engine.py:207-209`) |
| `core/injury.py:162` | `InjuryProfileSampler` | same fallback pattern | dormant — factory passes `self.rng` (`casualty_factory.py:52`) |
| `core/triage.py:42-43` | `TriageDistribution.sample(rng=None)` | **fresh unseeded `default_rng()` per call when rng omitted** | dormant on the engine path — sole production caller passes `rng=self.rng` (`casualty_factory.py:74-76`) — see hazard note |
| `core/vitals.py:33` | `VitalsGenerator` | required param, no fallback | seeded — `engine.py:307` passes `self._rng` (toggle-gated) |

**Unseeded module-level draws: NONE live.** No bare `np.random.*` or `random.*` draws exist
in src/. One **latent hazard** (not a live defect): `triage.py:42-43` constructs a fresh
OS-entropy generator per call whenever a caller omits `rng`; any future caller of
`sample()`/`sample_one()` without `rng` silently breaks determinism. The other
`rng or default_rng()` fallbacks share the same latent shape at construction time.

### Draw sites (production path; counts = instrumented protocol run, A defaults)

| Draw site | Owner | Draw | Purpose | Calls (scalars) |
|---|---|---|---|---|
| `arrivals.py:146` | ArrivalProcess | `exponential` | interarrival gap | 32 |
| `arrivals.py:163` | ArrivalProcess | `exponential` | inter-MASCAL gap | 1 |
| `arrivals.py:182` | ArrivalProcess | `normal` | MASCAL event size | 0 this run (site live) |
| `arrivals.py:201` | ArrivalProcess | `uniform(size=mascal.size)` | cluster arrival offsets | 0 this run (site live) |
| `core/triage.py:60` | TriageDistribution (via factory `casualty_factory.py:74-76`) | `choice` | triage category | 31 |
| `core/injury.py:185` | InjuryProfileSampler | `choice` | mechanism | 31 |
| `core/injury.py:192` | InjuryProfileSampler | `choice` | primary region | 31 |
| `core/injury.py:202` | InjuryProfileSampler | `integers` | secondary-region count | 31 |
| `core/injury.py:212-214` | InjuryProfileSampler | `choice(size=n≤3, replace=False)` | secondary-region set | 11 (19) |
| `core/injury.py:221` | InjuryProfileSampler | `normal` | severity noise (μ=SEVERITY_BASE, σ=0.10) | 31 |
| `injury_sampler.py:53,59,62,68,74,76` | DataDrivenInjurySampler (inverted factory only) | choice/beta/random/integers/choice | mechanism/region/severity(Beta)/polytrauma/secondary count+set | 0 at default (`factory_mode="legacy"`) |
| `transport.py:291` | TransportPool | `normal` | transit leg round-trip time | 13 |
| `engine.py:1096` | engine (department path) | `exponential` | treatment duration | 0 at default |
| `engine.py:1140` | engine (regime-B fallback) | `exponential` | treatment duration | 0 at default |
| `engine.py:1192` | engine (legacy queue path) | `exponential` | treatment duration | 40 |
| `engine.py:1228` | engine `_vehicle_return` | `normal` | vehicle return time | 26 |
| `core/vitals.py:47` | VitalsGenerator (×5 per casualty) | `normal` | initial vitals (GCS/HR/BP/RR/SpO2) | 0 at default (`enable_vitals=False`) |

Draw-free (verified): `routing.py`, `metrics.py`, `emitter.py`, `pfc.py`, `analytics/`,
`mascal.py` (MASCALDetector — pure threshold logic), `facility_writer.py`, `state_loader.py`,
`queues.py`, `departments.py`, `ccp.py`.

### Test-side seeding patterns (separate)

- `tests/conftest.py:87-90` — `np.random.seed(42)` / `np.random.seed(None)` in the
  `fixed_seed` fixture (legacy global RNG; not autouse).
- `tests/conftest.py:158` — `seed=42` in `sample_config`.
- `tests/harness.py:33` — `run_to_log(..., seed=42)` default; `harness.py:123-124` — sweep
  replication seeds `seed .. seed+n_reps-1`.
- `src/faer_dev/events/ensemble.py:184` — `rep_seed = self.base_seed + i` (see Q5).

---

## Q2 — DRAW PURPOSE TABLE (classification + occurrence index)

| Draw site | Purpose | Distribution / param source | Vectorised? | Index knowable at creation? | Class | Occurrence-index proposal (grounded in code) |
|---|---|---|---|---|---|---|
| `arrivals.py:146` | interarrival gap | Exp(1/base_rate_per_minute); `ArrivalConfig` per context (`arrivals.py:47-72`) | no | n/a (pre-identity) | **SYSTEM-AXIS** | `(stream="arrivals", n)` — n = arrival ordinal |
| `arrivals.py:163` | inter-MASCAL gap | Exp(1/mascal_rate_per_minute); `ArrivalConfig` | no | n/a | **SYSTEM-AXIS** | `(stream="mascal", event n, "gap")` |
| `arrivals.py:182` | MASCAL size | Normal(mascal_size_mean, mascal_size_std), clamped; `ArrivalConfig` | no | n/a | **SYSTEM-AXIS** | `(stream="mascal", event n, "size")` |
| `arrivals.py:201` | cluster offsets | Uniform(0, duration), size=mascal.size | **yes, n stochastic (drawn at :182)** | n/a | **SYSTEM-AXIS** | `(stream="mascal", event n, member m)` — or one keyed array draw per event |
| `triage.py:60` | triage category | categorical; `TRIAGE_DISTRIBUTIONS`/MASCAL shift (`triage.py:94-134`) | API vectorised, engine path always n=1 (`triage.py:67` via `casualty_factory.py:74-76`) | **yes** | **EAGER** | `(casualty_uid, TRIAGE)` |
| `injury.py:185` | mechanism | categorical; `MECHANISM_PROBABILITIES` (`injury.py:81-114`) | no | **yes** | **EAGER** | `(casualty_uid, MECHANISM)` |
| `injury.py:192` | primary region | categorical; `REGION_PROBABILITIES` (`injury.py:117-128`) | no | **yes** | **EAGER** | `(casualty_uid, PRIMARY_REGION)` |
| `injury.py:202` | secondary count | integers; `SECONDARY_REGION_COUNTS[triage]` (`injury.py:131-137`) | no | **yes** | **EAGER** | `(casualty_uid, SECONDARY_COUNT)` |
| `injury.py:212-214` | secondary set | choice w/o replacement, size≤3 | yes, n from :202 (same casualty, consumed together) | **yes** | **EAGER** | `(casualty_uid, SECONDARY_REGIONS)` — one keyed array draw |
| `injury.py:221` | severity noise | Normal(SEVERITY_BASE[triage], 0.10) (`injury.py:140-146`) | no | **yes** | **EAGER** | `(casualty_uid, SEVERITY)` |
| `injury_sampler.py:53-76` | data-driven variants of the above (+Beta severity `:62`, polytrauma Bernoulli `:68`) | params from injury-data YAML loader | `:76` size≤4 | **yes** | **EAGER** | same purposes as legacy; identical key set |
| `vitals.py:47` (×5) | initial vitals | 5× Normal; baselines from injury-data YAML per triage | no | **yes** | **EAGER** | `(casualty_uid, VITALS)` — one keyed draw event, 5 values |
| `engine.py:1096 / 1140 / 1192` | treatment duration | Exp(base); `DEFAULT_TREATMENT_TIMES[role][triage]` (`engine.py:60-73`) × `treatment_time_modifier` | no | **no** — depends on routing | **LAZY** | `(casualty_uid, TREATMENT, episode n)` — n = per-casualty ordinal of TREATMENT_START; the three sites are one purpose (same draw, different code path) |
| `transport.py:291` | transit leg time | Normal(μ,σ) from `TransportConfig.get_round_trip_params(mode)` | no | **no** | **LAZY** | `(casualty_uid, TRANSIT, leg n)` — n = per-casualty ordinal of transport legs |
| `engine.py:1228` | vehicle return | Normal(outbound, 0.2×outbound), floor 10.0 (hardcoded) | no | **no** | **LAZY** | spawned 1:1 with a completed patient delivery (`engine.py:1208-1233`, resource held until return) → natural key `(casualty_uid, VEHICLE_RETURN, leg n)`; note the draw semantically belongs to the vehicle, not the patient — keying decision (casualty-leg vs vehicle-mission stream) is a 0c design point, both indexes are well-defined in code today |

MASCAL is stochastic (three sites above, all system-axis). Vehicle returns are stochastic
(`engine.py:1228`). No other stochastic subsystems exist (Q1 draw-free list).

---

## Q3 — DETERIORATION AS-BUILT (the Sellke seam)

**The entire hold/PFC deterioration pathway is DETERMINISTIC — zero stochastic draws**
(confirmed by read and by instrumentation: no draw site between `engine.py:700-860`).

Hold pathway (`engine.py:721-849`):
- Constants: `hold_timeout = 480.0` min, overridable via test seam `_hold_timeout_override`
  (`engine.py:731`); `retry_interval = 15.0` (`engine.py:732`); `pfc_threshold = 60.0`
  (`engine.py:733`).
- Clock advances: retry tick `yield self.env.timeout(retry_interval)` (`engine.py:843`);
  CCP medic race `yield medic_req | self.env.timeout(5)` (`engine.py:778`); intervention
  time `yield self.env.timeout(total_time)` (`engine.py:786`) — total_time summed from
  injury-loader records, not drawn.
- PFC trigger: `held_so_far >= pfc_threshold` (`engine.py:766-771`).
- PFC ceiling: `pfc_hours >= max_hours` (`engine.py:814`), max_hours from
  `get_max_pfc_hours(triage)` (`engine.py:810-811`) else 24.0 (`engine.py:813`).

Severity step — the inline ladder (`engine.py:324-362`, fires ONLY on ceiling breach):
- `base_deterioration = 0.20` (`engine.py:338`); multiplier from
  `get_pfc_deterioration_multiplier(cmt_available)` (`engine.py:339-341`) else 0.6
  (`engine.py:343`); `severity = min(severity + 0.20*mult, 0.99)` (`engine.py:344-346`).
- Deterministic promote-only escalation: sev>0.65→T1_SURGICAL, >0.50→T1_MEDICAL,
  >0.35→T2, else no promotion (`engine.py:349-357`, rank guard `:359-361`).
- `requires_dcs` recomputed on promotion (`engine.py:828-830`).

`pfc.py` is decision-only: `evaluate_hold` pure (`pfc.py:41-93`); `compute_deterioration`
(`pfc.py:96-109`, linear `severity + hold_duration*0.01`) is **inert — never called by the
engine** (the adjudication is a deferred-register row; S2 scope excludes it).

**Per-casualty state to hang a frailty threshold on:** `Casualty.severity_score`
(`schemas.py:85`) and the free-form `Casualty.metadata` dict (`schemas.py:118`), which
already carries the PFC episode state: `pfc_active`/`pfc_started_at`/`cmt_available`
(`engine.py:377-379`), `pfc_ceiling_fired` (`engine.py:815`), `hold_timeout`
(`engine.py:763`). The cumulative-hazard clock would accrue where the deterministic clock
already ticks — the 15-min retry loop (`engine.py:843`) and the threshold checks at
`engine.py:758/766/814`.

**What O3 asserts** (`tests/test_oracles.py:106-134`, `test_o3_deterioration_direction`):
severity sampled via bus subscription on HOLD_START/HOLD_RETRY/PFC_START/PFC_END/
HOLD_TIMEOUT (`:118`), non-vacuity (`held_severity` non-empty, `:129`), and per-casualty
monotonicity only: `assert later >= earlier` (`:131-134`). **Direction-only, no
magnitudes.** A Sellke swap that keeps severity non-decreasing during hold (monotone
cumulative hazard + promote-only retriage) keeps O3 green knowingly — no re-baseline
required by construction; only the tuned scenario's non-vacuity needs a check (Q7).

---

## Q4 — IDENTITY STABILITY

- Scheme: `f"CAS-{self._counter:04d}"` (or `f"{id_prefix}-…"`) —
  `casualty_factory.py:104-108` (legacy), `:262-265` (inverted). `_counter` is per-factory
  instance (`:54`, `:197`), incremented at the top of `create()` (`:67`, `:209`).
- **Arrival-order-sequential: YES.** `create()` is called only from the arrival callback
  (`engine.py:588` `_handle_arrival` → `:603`), so id n ≡ nth arrival.
- **Config-invariance post-fix: YES for the current single-POI engine.** The id depends
  only on arrival order; once arrivals are keyed system-axis (config-invariant sequence),
  `CAS-nnnn` is stable across configs. Nothing else feeds the id (no POI, no config field;
  only the optional `id_prefix`, default "" — `casualty_factory.py:45`, `:187`).
- **Step-3 rider (note only):** one factory per engine today, single-POI enforced
  (`engine.py:1278-1281` rejects POI change after arrivals start). Multi-POI with a shared
  factory couples id n to cross-POI arrival interleaving (identity no longer per-POI
  stable); per-POI factories collide on `CAS-0001` unless `id_prefix` namespaces them —
  the existing `id_prefix` seam (`casualty_factory.py:106-107`) is the collision escape.

---

## Q5 — SEED PLUMBING + ENSEMBLE

**Master seed → generators (complete chain):**
`build_engine_from_dict(seed)` — `builder.py:144` (`resolved_seed = seed if seed is not
None else scenario.get("seed", 42)`) → `builder.py:158` (`seed=resolved_seed`) →
`engine.py:142` (`self._rng = np.random.default_rng(seed)`) → by reference to: inverted
injury sampler `engine.py:170-172` · factory `engine.py:179/188` · TransportPool
`engine.py:207-209` · VitalsGenerator `engine.py:307` · ArrivalProcess
`engine.py:1246-1252` / `1291-1298`. One object, one stream, every consumer.

**EnsembleBuilder as-built** (`src/faer_dev/events/ensemble.py`):
- Replication seeding: `rep_seed = self.base_seed + i` (`ensemble.py:184`), consumed at
  `ensemble.py:190-192` (`build_engine_from_preset(self.preset, seed=rep_seed, …)`).
- Inert `patient_seed`: constructor param `ensemble.py:151` (`patient_seed: Optional[int]
  = None`), docstring declares it reserved/no-effect (`ensemble.py:159-161`), stored at
  `ensemble.py:167` (`# Inert until engine supports dual seeds`), never read again.

**Where root `SeedSequence(entropy=(master_seed, replication_index))` would be
constructed:** `engine.py:142` is the sole Generator construction point and therefore the
root's home; the replication index currently reaches it pre-mixed (`base_seed + i` at
`ensemble.py:184` flowing through `builder.py:158`'s single `seed` int). For the entropy
tuple to carry `replication_index` separately, the value must survive
`ensemble.py:190-192 → builder.py:144/158 → engine.py:142` as a second parameter — those
three sites are the full plumbing surface.

**numpy / Philox:** numpy **2.4.3**; `from numpy.random import Philox` — OK (verified in
env). `pyproject.toml` pins `numpy>=1.24` (no upper bound).

**Per-run draw volume (instrumented, not estimated):** protocol run (coin/42/24 h/uncapped,
undrained): **278 generator calls / 286 scalar values**. Drained F0.2 harness run:
285 calls / 293 scalars. Per-site breakdown in Q1. Volume is trivial — three orders of
magnitude below any perf-relevant threshold at ~9 ms/run (Q6).

---

## Q6 — BULK DRAWS + PERF SEAMS

**Vectorised (`size=n`) draws and per-draw-keying impact:**

| Site | n | Impact of per-draw keying |
|---|---|---|
| `arrivals.py:201` uniform cluster offsets | `mascal.size` — itself stochastic (drawn `:182`) | the only genuine runtime-sized bulk draw; decomposes to `(stream="mascal", event n, member m)` or one keyed array draw per event; array semantics not load-bearing (offsets are sorted into individual scheduled arrivals) |
| `injury.py:212-214` / `injury_sampler.py:76` secondary regions | ≤3 / ≤4, from the immediately preceding count draw | per-casualty, consumed atomically with their count draw; one keyed draw event each |
| `triage.py:60` choice | API takes n, **engine path always n=1** (`triage.py:67` `sample(1, rng)` via `casualty_factory.py:74-76`) | no bulk semantics in production; batch form used nowhere in src |

No `.rvs`/scipy draws exist. Nothing else is vectorised.

**Perf baseline:** measured this session (warm, darwin): undrained protocol run
**8.9–9.3 ms** (5 runs), drained harness run **10.0 ms**. The "~44 ms/run" figure in
`BUILD_S2.md:13` is NOT reproduced — actual is ~5× faster; headroom for keyed-draw
construction is larger than assumed. (At 286 scalars/run, even naive per-draw
`Generator(Philox(key=…))` construction is bounded by ~hundreds of μs.)

**Natural cache homes for per-(casualty, purpose) generators (facts, no recommendation):**
the engine already owns the identity map `self.patients: Dict[str, Casualty]`
(`engine.py:229`) and the construction site `engine.py:142`; `Casualty.metadata`
(`schemas.py:118`) is the existing per-casualty mutable carrier (already used by the PFC
episode state, Q3). An engine-level dict keyed `(casualty_uid, purpose)` beside `_rng`
sits at the same construction chokepoint every consumer already receives.

---

## Q7 — RE-BASELINE SURFACE (census of all 134 tests)

Classification criterion, applied honestly: a test breaks under re-keying only if it
compares post-change output against a **pre-change committed artefact or pre-change tuned
absolute number**. Tests asserting equality between two runs BOTH executed post-change
(double-run determinism, toggle-arm equality) survive re-keying mechanically — both arms
re-key identically — and are listed PROPERTY-SAFE even though their assertion style is
"absolute equality". This corrects the naive absolute-vs-distributional split.

### RE-BASELINE list (breaks at 0e by design; one sanctioned regen + reviewed diff)

| Test | Site | What breaks |
|---|---|---|
| **O1 golden trace** | `tests/test_oracles.py:30-45` vs committed `tests/golden/coin_s42.json`; regen only via `--regen-golden` (`tests/conftest.py:24-39`) | the ONLY committed absolute baseline in the suite; full regen at 0e, diff reviewed (Rule 7) |

**Recipe-sensitive riders (assertions are property-shaped and stay; the TUNED SCENARIO may
go vacuous under re-keyed draws — if so, re-tune the recipe, never the assertion):**
- `hold_promotion_run` fixture (`tests/test_capability_retriage.py:118-138`): guard
  `assert promotions` (non-empty) — promotions depend on realised treatment-time
  exponentials producing ≥60-min holds; severity itself is forced (`_force_casualties`),
  insulating the ladder arithmetic.
- O3 non-vacuity (`test_oracles.py:129`), O4 hold-gate traversal non-empty
  (`test_hold_gate_integration.py:42`), O5 congestion scenario (`test_oracles.py:189-210`),
  T-5-6/T-5-7 characterisation scenarios (`test_capability_retriage.py:200+, 248-308`).
- O2's observed shares move within its ±0.15 band (expected to hold; n≈31 at coin/42).

### PROPERTY-SAFE list (must survive unmodified)

- **O2 triage distribution** — ±0.15 band + shape guards (`test_oracles.py:64-88`).
- **O3 deterioration direction** — monotonicity only (`test_oracles.py:106-134`).
- **T-5-5a/b** — `requires_dcs is True`, routing probe `dest == "R2-S"`, violations `> 0`
  (`test_capability_retriage.py:141-190`); T-5-5b inverts to `==0` at Step 3 by its own
  docstring, not at S2.
- **Conservation (Rule 4)** — `arrivals == dispositions` drained
  (`test_harness.py:24-25`); `arrivals == dispositions + in_system`
  (`test_emitter.py:186`, `test_phase1_integration.py:92`).
- **Safety/liveness invariants** — no surgical treatment at non-capable facility
  (`test_capability_routing.py:141-148`), all surgical treated (`:167-173`), weight
  preference cannot readmit (`:220-224`).
- **Double-run determinism** (this IS invariant I-1's existing form) —
  `test_canonical.py:30-34`, `test_harness.py:28-34`, `test_oracles.py:251-252` (O6),
  `test_facility_writer.py:217`, `test_capability_routing.py:203`.
- **Seed-difference** — digests differ across seeds (`test_canonical.py:47-53`).
- **Toggle trace-neutrality / toggle-arm equality** — writer neutrality
  (`test_facility_writer.py:196`), capability no-op digests
  (`test_capability_routing.py:160, 191`), legacy-vs-extracted metric equality suites
  (`test_metrics.py:121-142`, `test_routing.py:170-186, 336-350`,
  `test_emitter.py:150-204`, `test_phase1_integration.py:55-67, 84`). These survive
  re-keying mechanically; a post-flip failure here is a KEYING DEFECT signal (draw-purpose
  divergence between arms), not baseline drift — exactly what I-2/I-3 formalise.
- **Pure unit tests** (no engine RNG): `test_pfc.py` (`evaluate_hold` decisions),
  routing decision units (`test_routing.py:73-148`), analytics view units
  (`test_analytics.py:115-173`), metrics units (`test_metrics.py:52-77`), K-3/debt-closure
  structure asserts (`test_emitter.py:115-129`, `test_phase1_integration.py:103-131`).

Golden inventory: `tests/golden/` contains exactly one file, `coin_s42.json`.

---

## Q8 — ROSTER/PARQUET SEAM

**Availability:** pandas **2.3.3**, pyarrow **23.0.1** — both importable in the dev env,
but **neither is declared** in `pyproject.toml [project].dependencies` (numpy/simpy/
networkx/pydantic/pyyaml/py-trees only). A roster parquet writer needs a dependency
declaration decision (hard dep vs optional-extra vs pandas-free pyarrow write).

**Where attributes are assembled:** `LegacyCasualtyFactory.create()`
(`casualty_factory.py:61-98`) — all identity attributes (triage `:74-76`, injury bundle
`:78`, priority `:79`, modifier `:80`) final at the `Casualty(...)` return `:82-98`.
Inverted flow: `casualty_factory.py:203-260`. Engine consumes at `_handle_arrival`
(`engine.py:588` → `create` at `:603` → journey process `:607`).

**Derived decision fields:** `recommended_triage`/`bypass_role1`/`requires_dcs`/`priority`
are computed at journey start by the draw-free routing module (`engine.py:669-671`,
`routing.py:38-50`) — deterministic functions of the creation-time attributes — and land
in the ARRIVAL payload (`engine.py:681-688`), which is what Q0 hashed.

**Natural write points behind a flag (facts):** (i) post-`create()` at `engine.py:603`
— identity attributes only; (ii) the ARRIVAL emission `engine.py:681-688` — identity +
derived decision fields, i.e. the full Q0 roster row. Toggle pattern to follow: declare on
`SimulationToggles` (`decisions/mode.py:40-76`; exemplar `enable_facility_writer` at
`:66`), wire conditionally in `engine.__init__` (`engine.py:195-203`), with the S1.1
writer's trace-neutrality proof (`T-W-3a`) as the acceptance pattern for "consumes no RNG,
perturbs no events".

**POLYBIUS in docs/ (complete grep, case-insensitive):** appears only in
`docs/MVP/BUILD_S2.md`:
- `BUILD_S2.md:10` — "…draw at spawn, freeze to the roster (parquet artefact behind a
  flag — POLYBIUS's input interface)…"
- `BUILD_S2.md:21` — "OUT: … POLYBIUS itself (the roster parquet is the interface
  artefact only) …"
- `BUILD_S2.md:26` — "…eager roster at creation + parquet writer behind flag…"
No parquet-digest expectation exists anywhere else in docs/ — the artefact contract is
whatever 0c defines; nothing external constrains its schema yet.

---

## Q9 — DRAW-COUNT INSTRUMENTATION

**Cheapest seam — demonstrated, not theorised:** every consumer receives the ONE Generator
object constructed at `engine.py:142` by reference (hand-offs: `engine.py:170-172, 179,
188, 207-209, 307, 1246-1252, 1291-1298`). A counting wrapper installed at that single
site is inherited by all 17 production draw sites with zero further change — this session's
Q5 instrumentation did exactly that in-memory and recovered the full per-site table (Q1).
The enum-keyed counter-dict alternative requires touching every draw site individually.
Note for 0c: the keyed draw API is itself a per-purpose chokepoint — once every draw passes
through `draw(casualty_uid, purpose, occurrence)`, the counter is a dict increment inside
that API and the wrapper-vs-dict distinction dissolves.

**canonical.py extension point — confirmed:** `log_digest(events)`
(`src/faer_dev/events/canonical.py:33-42`) SHA-256-hashes the JSON dump of
`canonical_log(events)`; `canonical_event` strips exactly `{event_id, wall_time}`
(`canonical.py:19, 22-25`). Per-purpose counts enter the digest either by widening
`log_digest`'s input (counts merged into the hashed blob) or as a synthetic terminal
event appended to the log before digesting — both flow through the same `canonical.py:39`
dump. Digest consumers that would then police draw-count desync for free (10 sites):
`test_canonical.py:34, 53` · `test_harness.py:34` · `test_oracles.py:45, 252` ·
`test_facility_writer.py:196, 217` · `test_capability_routing.py:160, 191, 203`.

---

*Scripts: session scratchpad `q0_roster_hash.py` (roster build, hashes, per-field diff),
`q5_draw_volume.py` (counting-proxy instrumentation), `q0_rosters.json` (full A/C rosters).
All runs via the F0.2 harness; no src/, tests/, or golden change.*
