# BUILD_F0 — Correctness Foundation
### The validity layer. Nothing in the MVP is trustworthy until this exists.
### (Validity: components that do not change the result, but decide whether the result can be trusted.)

**Authority:** docs/MAAFI_VERDICT.md (A11: CORRECTNESS BLIND). This file
implements the five A11 prerequisites as four vertical slices.
**Effort:** ~175 LOC total (budget 120–180, O6 addition included). **Engine behaviour changes: ZERO**
— F0 is test infrastructure plus one pure serialisation module. If any slice
changes a simulation outcome at seed=42, that slice is wrong.

---

## How to run this file (Claude Code)

You are NOT in plan mode. You will create real files with the Write tool,
run pytest after every slice, and commit per slice with the message given.
Work the slices in order: F0.1 → F0.2 → F0.3 → F0.4. Within F0.3 the five
oracles are independent and may be built in any order.

Ground rules (RAIE):
- seed=42 everywhere; every new test must be deterministic across two runs
- Red-then-green: write each acceptance test FIRST, watch it fail (or error),
  then implement until it passes
- One commit per slice; do not batch
- Baseline protection: the original 99 tests stay green after every slice
- British English in comments and docstrings

---

## SLICE F0.1 — Canonical event serialiser (~30 LOC)

**Problem (R1):** every event carries `event_id` (uuid4) and `wall_time`
(datetime.now). Two identical seed-42 runs therefore hash differently on the
raw store, so replay/golden-trace comparison reports spurious
non-determinism.

**Build:** `src/faer_dev/events/canonical.py`
- `canonical_event(e: dict) -> dict` — returns a copy with `event_id` and
  `wall_time` removed, keys sorted. Values otherwise untouched (do NOT round
  floats — masking real drift is worse than long decimals).
- `canonical_log(events: list[dict]) -> list[dict]` — maps canonical_event,
  preserving order.
- `log_digest(events) -> str` — sha256 of the JSON-dumped canonical log
  (`sort_keys=True, separators=(",",":")`).

**Acceptance (tests/test_canonical.py):**
- AC-F0.1a  Two `build_engine_from_preset("coin", seed=42)` runs →
  `log_digest` EQUAL.
- AC-F0.1b  The RAW logs of those two runs are NOT equal (proves the
  serialiser is doing real work, not vacuously passing).
- AC-F0.1c  seed=42 vs seed=43 → digests DIFFER (we are not
  over-normalising away real differences).

**Commit:** `F0.1: canonical event serialiser — deterministic log digests`

---

## SLICE F0.2 — run_to_log() + sweep() fixtures (~50 LOC)

**Problem (F13, F12):** no fixture runs the engine to completion and returns
the event log; the ARRIVAL-31 / DISPOSITION-28 gap in a default run is an
undrained-cutoff artefact that would poison conservation assertions. And
there is no way to vary a scalar (e.g. R1 beds) across runs without editing
YAML on disk.

**Build:** `tests/harness.py` (imported by tests; not a plugin)
- `run_to_log(scenario, *, seed=42, duration_min=1440, max_patients=200,
  toggles=None, drain=True)` — accepts a preset name OR a scenario dict
  (via `build_engine_from_dict`). If `drain=True`, after the arrival window
  closes keep stepping the environment (bounded extra time, e.g. +24 h sim)
  until DISPOSITION count == ARRIVAL count, then stop. Returns
  `(engine, canonical_log)`.
- `sweep(base_scenario: dict, set_path: str, values: list, *, n_reps=20,
  seed=42, metric_fn)` — the R16b-proven dict-edit pattern, formalised:
  deep-copy base, set the dotted path (e.g. `"facilities.R1-ALPHA.beds"`),
  run n_reps with seeds `seed..seed+n_reps-1`, return
  `{value: [metric per rep]}` with stable key order. (This is the interim
  mechanism; step 2 of the main plan adds the real `scenario_overrides`
  API on EnsembleBuilder — the fixture's signature should survive that swap.)

**Acceptance (tests/test_harness.py):**
- AC-F0.2a  Drained coin run: ARRIVAL count == DISPOSITION count (the
  conservation invariant, now assertable).
- AC-F0.2b  Two identical `run_to_log` calls → equal digests (fixture is
  itself deterministic).
- AC-F0.2c  `sweep(coin_dict, "facilities.R1-ALPHA.beds", [2, 8], n_reps=3)`
  returns two keys in given order, three values each, and re-running yields
  identical output.

**Commit:** `F0.2: run_to_log + sweep harness — drained, deterministic`

---

## SLICE F0.3 — Correctness oracles (~95 LOC across six tests)

**Problem (R17):** forcing every casualty to T3 passed all 99 tests. These
five oracles are absolute behavioural checks — none may be implemented as
`legacy == extracted`.

**O1 — Golden trace.** `tests/golden/coin_s42.json`: commit the canonical
log of a short coin run (e.g. duration 480 min, cap 50). Test asserts the
live digest equals the committed digest.
*Regeneration policy (goes in the test docstring AND CLAUDE.md):* the golden
file may only be regenerated via `pytest --regen-golden` (implement a simple
flag/env check), and the diff must be reviewed in the commit — never
regenerated silently to make red go green.

**O2 — Triage-distribution oracle (the anti-T3 kill-shot).** Over a drained
coin run (≥100 casualties, raise arrival rate or duration as needed): assert
(a) at least three distinct triage categories appear; (b) no single category
exceeds 90% of casualties; (c) the observed shares of T1/T2/T3 are within
±0.15 absolute of the scenario's configured `triage_distribution`.
Mode-agnostic: read triage from emitted ARRIVAL/TRIAGE events, compare to
config — do not import factory internals.

**O3 — Deterioration-direction oracle.** Domain invariant: PFC deterioration
direction must never silently reinterpret. Bottleneck a facility so at least
one patient enters hold/PFC; assert that patient's `severity_score` is
non-decreasing across its event sequence while held. Direction only —
magnitude and model choice are deferred to the step-4 PFC decision.

**O4 — Hold-gate sequence (REBUILD from recipe — verified gone).** The
Red Team's passing /tmp test has evaporated; codebase check (main @ 9bc7daf)
confirms `_hold_timeout_override` (engine.py:716) still has zero callers and
the in-engine SimPy hold/PFC/timeout path (engine.py:710-847) has no
integration test — only the extracted pure functions are covered. Rebuild in
`tests/test_hold_gate_integration.py` from the recipe: bottleneck R2 beds=1,
`_hold_timeout_override=75`, T2 arrivals; assert one patient traverses
HOLD_START → HOLD_RETRY → PFC_START → HOLD_TIMEOUT in order.

**O5 — Graph congestion-shift (closes the R12 gap, corrected).** Codebase
check: 17 graph-routing tests exist, but the 3 branching ones are weak
oracles (either-R1 accepted; static one-call unit check; >0-traffic only).
Crucially, routing is STATIC Dijkstra — the engine tracks
`current_occupancy` but never feeds it back into edge weights; dynamic
occupancy→weight feedback is UNBUILT (later tier, pairs with the 1b
writer). So assert the property that exists: minimal branching dict (one
POI, two R1s, one R2), BOTH routing toggles on; mid-run, drive
`update_congestion()` against one R1 and assert the traffic split shifts
toward the other. Directional with tolerance — not exact counts.

**O6 — Simultaneity tie-break determinism (closes a gap the interrogation
missed).** MASCAL's signature is several casualties arriving at the SAME
simulated instant, and SimPy tie-breaking at identical timestamps is exactly
where determinism and CRN break silently. Build a scenario dict that forces
k >= 3 arrivals at one sim-time (e.g. a MASCAL cluster with zero spread, or
direct injection); run twice at seed=42 and assert `log_digest` EQUAL,
including the relative order of the simultaneous events. Re-assert this
oracle after step 3 (multi-POI) lands — concurrent arrival generators are
the exact hazard it guards (C5).

**Meta-acceptance for the whole slice (run once, do not commit the break):**
re-apply the R17 corruption — force triage to always return T3 — and run the
suite. It must now FAIL (O2 catches it). Revert. Record the result in the
commit message.

**Commit:** `F0.3: six correctness oracles — R17 corruption now caught`

---

## SLICE F0.4 — CLAUDE.md ratifications (docs only, no code)

Append/amend four items:
1. **Yield rule (B3, ratified):** replace "all 5 yield points stay in
   engine.py" with: "SimPy yields may live in extracted generator modules
   (arrivals, transport, ccp) provided they are exception-safe and covered
   by the strangler/oracle suite. engine.py remains the sole *orchestrator*
   of patient journeys." The old rule was aspirational, not load-bearing —
   determinism holds with 10 distributed yields.
2. **Authority pointer:** docs/MAAFI_VERDICT.md governs tier and build
   order; it supersedes all earlier feature plans.
3. **Event-bus constraints (C6, for Phase 2 — verified):** the bus
   logs-but-swallows subscriber exceptions (bus.py:62-80 — non-fatal,
   subscriber stays attached), and fires AFTER the routing decision —
   sufficient for consumable tracking (#35-37), insufficient for stockout
   feedback (#39) without a blackboard write-back loop. Two wildcard
   subscribers already exist (event_store.append, AnalyticsEngine); a
   throwing ConsumableManager degrades quietly, so subscribers must be
   exception-safe by design.
4. **Golden-trace regeneration policy** (from O1).
5. **Doctrine-as-config rule (standing, for #29 and all future policy
   comparisons):** any compared doctrines/policies must run through
   IDENTICAL code paths, differing only in configuration — never a code
   branch per doctrine. Branching breaks CRN: different paths draw
   different random numbers, and the measured difference stops being
   attributable to the policy. Nothing violates this today; this rule
   keeps it that way.

**Commit:** `F0.4: CLAUDE.md — yield rule, verdict authority, bus constraints, doctrine-as-config`

---

## Definition of done — F0 phase gate (human confirmation point)

- [ ] All four slices committed in order, each with its message
- [ ] Original 99 tests green, PLUS the new tests (expect ~13–16 new)
- [ ] `log_digest` stable across two consecutive full-suite runs
- [ ] The R17 T3-break experiment FAILS the suite (recorded in F0.3 commit)
- [ ] Zero diffs in any simulation outcome at seed=42 vs pre-F0 baseline
- [ ] CLAUDE.md carries the four ratifications

When all boxes tick, STOP and report. The next instruction file covers
Step 1 (capability routing ∥ blackboard writer) — do not start it inside
this session.

---
*F0 exists because a beautiful number from an unverified mechanism is worse
than no number. After this gate, every acceptance criterion in
MVP_ACCEPTANCE.md is writable, and every green test means what it says.*
