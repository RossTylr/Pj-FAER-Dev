# Option C: Graph-Based Routing via NetworkX Dijkstra

## Status: Phase 2 — First Iteration Candidate

## The Problem

`get_next_destination()` in routing.py (and its legacy twin in engine.py) uses a
manual role-walk loop: iterate ROLE_ORDER, for each role iterate all facilities,
return the first one with a matching direct edge.

This has two consequences:

1. **First-match bias.** When multiple facilities share the same role (e.g. two
   R1 nodes in an LSCO topology), the function always returns the first one
   added to the network dict. There is no load-balancing, no shortest-path
   consideration, no awareness of congestion. Parallel facilities are dead
   weight.

2. **The graph is ignored.** `TreatmentNetwork` wraps a NetworkX DiGraph with
   Dijkstra pathfinding (`get_route()`), edge weights, and a congestion update
   method (`update_congestion()`). None of this is used by routing. The graph
   infrastructure was built for this purpose but never wired.

### Evidence

IRON BRIDGE preset (5-node, LSCO): R1-BRAVO received zero traffic across a
48-hour simulation with 553 arrivals. All casualties routed to R1-ALPHA
because it appears first in `network.facilities.items()`.

Preset was simplified to 4-node linear chain as a workaround. This document
describes the proper fix.

## What Option C Does

Replace the role-walk loop with a Dijkstra shortest-path query through the
existing `TreatmentNetwork`. The network already supports:

- **Weighted edges** — `base_time` set from scenario config, `weight` is the
  dynamic copy that congestion modifies.
- **Bypass-R1 routing** — `get_route()` already inflates R1 node weights to
  infinity for bypass patients. No new logic needed.
- **Congestion updates** — `update_congestion()` multiplies inbound edge weights
  by a congestion factor. Currently never called by engine.py.

### New Routing Logic (pseudocode)

```python
def get_next_destination(patient, current_facility, network, decisions):
    # Clinical short-circuits (unchanged)
    if patient.triage == T3 and current_facility.role in (R1, R2):
        return None  # RTD
    if patient.triage == T4:
        return None  # expectant, stays

    # Find highest-role facility reachable from current position
    target = _find_highest_reachable(current_facility, network, decisions)
    if target is None:
        return None  # end of chain

    # Dijkstra shortest path (respects weights, congestion, bypass)
    path = network.get_route(patient, current_facility.id, target)
    if len(path) < 2:
        return None
    return path[1]  # next hop
```

### Supporting Change: Congestion Wiring

For graph routing to be meaningful, engine.py must call
`network.update_congestion()` when facility load changes. Candidate trigger
points:

- `FACILITY_ARRIVAL` — increment congestion factor
- `DISPOSITION` / `TRANSIT_START` (leaving) — decrement congestion factor
- Factor formula: `current_occupancy / bed_capacity` (0.0 = empty, 1.0 = full,
  >1.0 = over capacity)

This makes edge weights dynamic: routes into congested facilities become
"heavier", pushing Dijkstra to prefer less-loaded alternatives.

## Implementation Considerations

### 1. Toggle Gating (MC-4)

New toggle: `enable_graph_routing` in `SimulationToggles`, default `False`.

- OFF: current first-match role-walk (all existing baselines preserved)
- ON: Dijkstra path with congestion awareness

This follows the same pattern as all Phase 1 extractions. The toggle ensures
HC-2 deterministic replay is maintained for existing seeds when OFF.

### 2. Determinism (HC-2)

Dijkstra on a weighted graph is deterministic for the same graph state. Same
seed → same arrival order → same congestion updates → same weights → same
paths. HC-2 is preserved.

Edge case: if two paths have identical total weight, NetworkX Dijkstra returns
the lexicographically first. This is deterministic but could produce different
results from the role-walk. Acceptable — the toggle gate isolates this.

### 3. T3/T4 Clinical Rules

The early-exit rules (T3 RTD from R1/R2, T4 stays) are clinical logic, not
routing logic. They must remain as pre-routing short-circuits before the
Dijkstra call. Do not encode triage termination rules into graph weights.

### 4. Target Selection

The Dijkstra call needs a target node. Current routing implicitly targets "next
role up". Graph routing should target the highest-role facility reachable in
the network from the current position.

`_find_highest_reachable()` helper: walk ROLE_ORDER from highest to lowest,
check if any facility of that role is reachable via `nx.has_path()`. Return the
first hit. This is O(roles × facilities) — negligible.

### 5. LOC Budget

- routing.py changes: ~25 LOC (replace loop, add helper)
- engine.py congestion wiring: ~15 LOC (3 call sites)
- SimulationToggles: +1 field
- Tests: ~30 LOC (multi-path scenario, congestion scenario, toggle comparison)

Total: ~70 LOC. Within single-iteration budget (50-100 LOC).

Congestion wiring could be a separate iteration if preferred (routing first,
congestion second). This splits into two ~35 LOC iterations.

### 6. Test Strategy

```python
# Iteration 1: Graph routing without congestion
# Prove: linear chain produces same next-hop as role-walk
engine_old = build(toggles=SimulationToggles(enable_graph_routing=False))
engine_new = build(toggles=SimulationToggles(enable_graph_routing=True))
# On linear topology: output must be identical (only one path exists)
assert events_match(engine_old, engine_new)

# Iteration 2: Multi-path with congestion
# Prove: parallel R1 nodes both receive traffic
iron_bridge_5node = build(topology_with_r1_alpha_and_r1_bravo)
run(duration=2880)
r1a_count = count_events(facility="R1-ALPHA")
r1b_count = count_events(facility="R1-BRAVO")
assert r1b_count > 0  # no longer starved
assert abs(r1a_count - r1b_count) / (r1a_count + r1b_count) < 0.3  # roughly balanced
```

### 7. Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Dijkstra path differs from role-walk on linear chain | LOW | Test proves identical on single-path topologies |
| Congestion oscillation (routes flip rapidly) | MEDIUM | Dampen factor with exponential moving average |
| `nx.has_path()` performance on large graphs | LOW | FAER graphs are <20 nodes; negligible |
| T3/T4 short-circuit missed in refactor | LOW | Unit tests for each triage category |

## When to Trigger

This work begins when one of these happens:

1. **LSCO showcase notebook** needs multi-path routing to demonstrate contested
   evacuation chains with parallel R1 nodes.
2. **HADR plugin** needs alternate routing logic (different facility roles,
   different progression rules).
3. **Engine Room demo** feedback requests visible load-balancing across parallel
   facilities.

The first trigger is most likely — it's priority #2 on the current stack.

## What This Unlocks

- Multi-path LSCO topologies (parallel R1, parallel R2)
- Congestion-aware routing (casualties avoid overloaded facilities)
- Dynamic rerouting during MASCAL events (surge pushes congestion, routes shift)
- Foundation for contested-edge denial (set edge weight to infinity on denial)
- Foundation for HADR plugin routing (different role progression, civilian
  facility types)

## Files Touched

| File | Change |
|------|--------|
| `src/faer_dev/routing.py` | Replace role-walk with Dijkstra path query |
| `src/faer_dev/decisions/mode.py` | Add `enable_graph_routing` toggle |
| `src/faer_dev/simulation/engine.py` | Wire `update_congestion()` calls at admission/departure |
| `tests/test_routing.py` | Multi-path and congestion test cases |
| `notebooks/phase2/NB40_graph_routing.ipynb` | Proof notebook (rule #6) |

## Sequence

1. NB40 proof notebook: demonstrate Dijkstra routing on multi-path topology
2. Add toggle + routing.py changes (iteration 1, ~35 LOC)
3. Wire congestion in engine.py (iteration 2, ~35 LOC)
4. Restore IRON BRIDGE 5-node preset
5. Update LSCO showcase notebook with live multi-path results
