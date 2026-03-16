# Phase 2 Build Instructions: Plug
## Conditional — Only When HADR Is Commissioned

---

## Prerequisites

- NB39 (Phase 1 Integration Gate) PASSED
- HADR variant has concrete requirements (not speculative)
- OR engine.py at ~800 LOC is still blocking new feature development

## Trigger Conditions

Phase 2 starts when ONE of these is true:
1. A real HADR/Hospital variant is needed within 8 weeks
2. EP-2 contested transport needs richer logic than current edge denial
3. EP-5 alternative BT (ML triage) is being developed

If NONE are true, Phase 2 waits. The engine works fine at Phase 1 state.

## Phase 2 Extractions

| Step | Notebook | Target | Risk |
|------|----------|--------|------|
| 0 (early) | NB44 | `yield from` exception safety proof | LOW |
| 1 | NB40 | Plugin Protocols (wrap Phase 1 functions) | MEDIUM |
| 2 | NB41 | EX-5 Treatment yield delegation (Y1+Y2) | MEDIUM-HIGH |
| 3 | NB42 | HADR variant implementation | MEDIUM |

## Build Order

### Step 0: NB44 — yield from Safety (Build FIRST)

Before any yield delegation, prove in isolation that `yield from` sub-generators
correctly release SimPy Resources under exception conditions. This is a 150 LOC
notebook with zero FAER dependencies. If it FAILS, Phase 2 approach needs revision.

See: `docs/phase2/NB44_yield_from_safety.md` (to be written when Phase 2 is triggered)

### Step 1: NB40 — Plugin Protocol Design

Wrap Phase 1 pure function signatures in Plugin Protocols:
- `routing.get_next_destination()` → `RoutingPlugin.select_destination()`
- `pfc.evaluate_pfc()` → `PFCPlugin.evaluate()`
- BT triage tick → `TriagePlugin.assign_triage()`

MilitaryPlugins wrap existing Phase 1 functions (~50 LOC per plugin).
Engine rewired to call `plugins.triage.assign_triage()` instead of direct functions.
Acceptance test must produce IDENTICAL output.

### Step 2: NB41 — EX-5 Treatment Yield Delegation

First yield-bearing extraction. treatment.py sub-generator owns Y1+Y2.
Engine calls `yield from treatment.treat_patient(ctx, cas)`.

**Key constraint (F-ARCH-3):** Y1 and Y2 MUST stay inside a single
`with resource.request() as req:` block. The sub-generator owns the entire
acquire-treat-release cycle, not just individual yields.

### Step 3: NB42 — HADR Variant

With plugins in place, implement HADR-specific plugins:
- `HADRTriagePlugin` — simplified field triage (rule-based, no BT)
- `HADRRoutingPlugin` — hub-and-spoke, capacity balancing
- `HADRTransportPlugin` — different vehicle types

Target: <300 LOC total for the full variant. Engine.py untouched.

## Phase 2 Exit Criteria

- [ ] engine.py ≤ 700 LOC (target ~650)
- [ ] HADR variant runs NB32 acceptance test
- [ ] Engine.py NOT modified for HADR
- [ ] 11-file kernel NOT modified
- [ ] HADR variant < 300 LOC total
- [ ] Y1+Y2 safely delegated (exception safety proven)
- [ ] MC-3: ±5% distribution match with Phase 1 baseline
