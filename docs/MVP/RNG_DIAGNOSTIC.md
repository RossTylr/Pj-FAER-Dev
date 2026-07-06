# RNG_DIAGNOSTIC — arrival anomaly classification (S1.1 rider R1)

*2026-07-06 · produced under BUILD_S1_1.md v1.1 §8 R1 · read-only diagnostic; no src/ or tests/ change.*

## VERDICT: (b) STREAM CONTAMINATION — divergence index k = 3

The comparison lane is FROZEN: paired A-vs-C claims are unquotable until dual-stream
separation lands (DEFERRED REGISTER row exists; Step-2 home, IMMEDIATE priority per
this verdict). EXP-IB-1000's paired design is threatened as specified. **The S1.1
build outcome is UNAFFECTED** — the writer consumes no RNG (T-W-3a digest proof).

## Method — blind-first (evidentiary order)

The diff was run and recorded BEFORE any mechanism narrative; the verdict below is
stated from the diff shape alone; the mechanism trace follows it. Re-run: coin,
seed 42, 24 h window (`duration_min=1440`), uncapped (`max_patients=10⁶`),
undrained. Config A = all defaults. Config C = `enable_extracted_routing=True,
enable_graph_routing=True, enable_capability_routing=True`. Canonical ARRIVAL
events compared as (casualty_id, sim_time) pairs, in order.

## Raw comparison (recorded first)

| | Config A | Config C |
|---|---|---|
| ARRIVAL count | **31** | **30** |
| Identical (id, sim_time) prefix | 3 (indices 0–2) | — |
| First divergent index k | **3** (CAS-0004) | — |
| CAS-0004 sim_time | 204.0905 | 176.9856 |
| Gap 2→3 (CAS-0003→0004) | 36.048 min | 8.943 min |
| Last arrival | CAS-0031 @ 1424.765 | CAS-0030 @ 1428.163 |

The casualty-id sequence marches in lockstep; the TIMES diverge from index 3 and
never re-converge. The 31-vs-30 count difference is a consequence, not a separate
phenomenon: the shifted interarrival sequence in C pushes what would be a 31st
arrival past the 1440-minute window.

## Verdict from the diff shape

Interarrival sequence diverges from index k=3 → **(b) STREAM CONTAMINATION** per the
§8 classification. Not (a) DEFINITION DRIFT: the spawn sequences are not identical
with a counting-site difference — the spawn times themselves diverge. Not (c): the
shape matches (b) exactly.

## Mechanism trace (performed AFTER the verdict; file:line evidence)

**Seed fan-out.** One generator is constructed at `engine.py:142`
(`self._rng = np.random.default_rng(seed)`) and handed to every stochastic consumer:

| Consumer | Site |
|---|---|
| ArrivalProcess (interarrival exponentials) | `engine.py:1246-1249` / `engine.py:1291-1294` → `arrivals.py:146` |
| Casualty factory / injury sampler | `engine.py:171, 179, 188` |
| TransportPool (trip-time normals) | `engine.py:208` → `transport.py:291` |
| Treatment-time exponentials | `engine.py:1096, 1140, 1192` |
| Vehicle-return normals | `engine.py:1228` |
| Vitals generator (when toggled) | `engine.py:307` |

`patient_seed` on EnsembleBuilder is inert (register row) — there is no second stream.

**Routing is draw-free.** `routing.py` contains zero `rng`/`random` references;
graph-mode Dijkstra runs over static/congestion weights without consuming randomness.
The pre-verdict hypothesis "graph routing draws extra numbers" is therefore WRONG in
its literal form — the contamination is not routing-side draws.

**The actual culprit: draw interleaving on the shared stream.** The first full-log
divergence is event index 2: CAS-0001's first hop is POI-1→R1-ALPHA (20 min leg) in
A but POI-1→R2-MAIN (55 min leg) in C — the designed policy difference. From there
the two configs consume journey draws (treatment exponentials, transport/vehicle
normals) at different sim-times, in different order, and — once journeys visit
different echelon chains — in different NUMBER, all on the one generator that also
serves arrivals. CAS-0002's and CAS-0003's interarrival draws still land on
identical stream positions (equal times, the k<3 prefix); by the CAS-0004 draw at
t=168.04 the cumulative journey-draw counts differ between A and C, the generator
is at different positions, and every subsequent arrival shifts. A routing POLICY
choice thereby contaminates the exogenous DEMAND stream — precisely the effect CRN
exists to prevent, and precisely why no paired A-vs-C difference is attributable to
the policy.

## Consequences

1. **COMPARISON LANE FROZEN** (this verdict): no paired A-vs-C claim is quotable
   until arrivals draw from a dedicated stream. Single-config claims are unaffected.
2. **Dual-stream separation** (register row: "RNG dual-stream separation … home
   Step 2 — IMMEDIATE priority if R1 verdict = STREAM CONTAMINATION") is now that
   immediate priority at Step-2 entry.
3. **EXP-IB-1000** paired design threatened until separation lands.
4. **Equivalence-fixture lesson** (R3 iv): route-coincident fixtures cannot detect
   draw-count divergence between paths — both arms draw identically when routes
   coincide, which is why the 12-test equivalence suite stayed green throughout.
   A route-divergent fixture lands with stream separation.
5. **S1.1 build outcome UNAFFECTED**; nothing is reverted; the build stands.

*Scripts: session scratchpad (`r1_arrival_diff.py`, `r1_first_divergence.py`),
blind-diff output preserved in the session transcript. Scripting erratum recorded
for honesty: the first blind run's "gaps equal for first 6" line counted all
positionally-equal gaps rather than the prefix; the true equal-gap prefix is 2,
consistent with k=3. The verdict rests on the (id, sim_time) prefix, which was
computed correctly.*
