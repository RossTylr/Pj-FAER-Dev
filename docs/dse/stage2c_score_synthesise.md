# FAER DSE — Stage 2c: Score, Synthesise, Recommend
## Claude (Principal Architect) — Extended Reasoning Output

---

# EXECUTIVE SUMMARY (1 page)

## Recommendation: HYBRID S1→S5 ("Tidy First, Then Plug")

The recommended architecture is a **two-phase hybrid** that begins with S1 (Minimalist Pure Extract) as Phase 1 and evolves into S5 (Plugin Sync Hexagonal) as Phase 2 — taking the velocity of the minimalist approach and the extensibility of the plugin approach without either's weaknesses.

**Why this wins:** The red-team exposed a fundamental tension — S1 ships fast but creates HADR-blocking if/else branching (S5's attack on S1), while S5 builds plugin infrastructure before any variant exists, risking premature abstraction (S1's attack on S5). The hybrid resolves this: Phase 1 extracts 624 LOC of pure logic in 12 iterations (~6 days), delivering immediate K-1/K-7 debt reduction that is shippable and valuable on its own. Phase 2 promotes the extracted modules into Protocol-based plugins ONLY when the second variant (HADR) is actually commissioned — at which point the interface shapes are informed by real implementation experience, not speculation. This directly satisfies KL-1 ("specification must not outrun verification") while structurally enabling EP-1.

**Top risk:** Phase 2 plugin Protocol design. If Protocols are defined too early (before HADR requirements are concrete), they'll be wrong and require rework. **Mitigation:** Phase 1 extractions are deliberately shaped as standalone pure functions with clean input/output signatures. When Phase 2 arrives, wrapping these functions behind Protocols is mechanical (~50 LOC per plugin), not architectural. The extraction IS the Protocol discovery process.

**Expected timeline:**
- **Phase 1 (weeks 1-2):** S1 extractions (EX-1→EX-4 sync, K-3 delete, EX-3 emitter). engine.py 1,309→~800 LOC. 12 iterations. Debt items K-1 (partial), K-3, K-7 resolved. Shippable.
- **Phase 2 (weeks 3-6):** When HADR is commissioned: promote extractions to Plugin Protocols. Build MilitaryPlugins (wrap existing) + HADRPlugins (new). Add AnalyticsEngine (Pattern E). 12-15 iterations. K-2, K-4 resolved.
- **Phase 3 (weeks 7-12, only if needed):** EX-5/EX-6 yield delegation (S2's treatment/hold extraction). Only pursue if engine.py at ~800 LOC is still the bottleneck after Phase 2. 12 iterations.

---

# FULL ANALYSIS

## SCORECARD

Scoring key: 1-3 = poor, 4-5 = acceptable, 6-7 = good, 8-9 = excellent, 10 = optimal.

### S1: Minimalist Pure Extract

| Criterion | Wt | Score | Justification |
|---|---|---|---|
| Solo-developer velocity | 20% | **9** | 12 iterations, 6 days. Lowest of all approaches. Each extraction is 50-100 LOC with immediate validation. Red-team §g confirmed no risk adjustments needed. |
| Migration risk | 20% | **9** | Zero yield movement. All extractions are pure functions (EX-1, EX-2, EX-4 sync) or protocols (EX-3). Red-team §b: "zero added latency." MC-4 toggle-gated throughout. 4 of 5 orchestration files preserved (§h). |
| FAER family divergence | 20% | **3** | Red-team §c: "No structural support for EP-1." HADR creates if/else branching in routing.py — exactly what KL-4 forbids. Cross-red-team: S5 attacks S1 on this point directly. |
| Notebook-first validation | 15% | **9** | Each extraction can be validated in a notebook: import routing.py, call with test data, compare against inline result. NB32 primitive runs unchanged. |
| Contested scenario extensibility | 15% | **4** | EP-2 contested transport is handled by routing.get_next_destination() returning is_denied. No interceptor chain, no command denial. Adding new denial modes requires modifying the routing function. |
| LOC efficiency | 10% | **8** | engine.py 1,309→~800. Total kernel ~4,800 (within EC-6 ceiling). ~795 new LOC is modest. |
| **WEIGHTED TOTAL** | | **6.65** | |

### S2: Strangler Per Debt

| Criterion | Wt | Score | Justification |
|---|---|---|---|
| Solo-developer velocity | 20% | **6** | 24 iterations base, worst-case 30 (red-team §g: EX-6 HIGH risk). 12.5 days base, potentially 15. Tight against EC-1 2-week target. |
| Migration risk | 20% | **8** | Each step independently toggle-gated and reversible (MC-4). Red-team §b flagged yield-from exception propagation as a concern but confirmed Python handles it correctly. Risk concentrated in EX-6. |
| FAER family divergence | 20% | **3** | Same as S1 — no plugin infrastructure. Red-team §c: "Same cost as S1." Extracted modules are single-implementation. |
| Notebook-first validation | 15% | **8** | Each strangler step testable independently. But EX-5/EX-6 (yield-bearing extractors) require SimPy fixtures in notebooks, unlike S1's pure functions. |
| Contested scenario extensibility | 15% | **4** | Same as S1. No structural EP-2 support. |
| LOC efficiency | 10% | **6** | engine.py→~500 LOC (best of non-radical approaches), but ~1,680 new LOC. Total kernel ~5,560 initially (exceeds EC-6), settling to ~4,200 after toggle removal. Temporary bloat during migration. |
| **WEIGHTED TOTAL** | | **5.75** | |

### S3: Tidy Then Decouple (A+E)

| Criterion | Wt | Score | Justification |
|---|---|---|---|
| Solo-developer velocity | 20% | **7** | 19 iterations, ~9.5 days. Phase 1 (S1 extractions) ships in 6 days; Phase 2 (analytics) adds 3.5 days. Comfortable within EC-1. |
| Migration risk | 20% | **8** | Phase 1 same as S1 (lowest risk). Phase 2 (AnalyticsEngine) subscribes to EventBus (CP-2, lowest decoupling cost per Context Index). Red-team §b flagged sync view updates adding latency to emit calls — but quantified at ~450μs/casualty, acceptable. |
| FAER family divergence | 20% | **4** | Slightly better than S1: AnalyticsEngine is variant-agnostic (views work for any event schema). But engine-side variant support still absent. Red-team §c: "+0.5 days for HADR-specific views" but core problem unchanged. |
| Notebook-first validation | 15% | **9** | S1 extractions notebook-validated. AnalyticsEngine testable by publishing synthetic events to a bus and checking view snapshots. No SimPy required for analytics testing. |
| Contested scenario extensibility | 15% | **4** | Same as S1. Analytics can subscribe to ROUTE_DENIED events for reporting, but no structural EP-2 support in the engine. |
| LOC efficiency | 10% | **7** | engine.py→~730 LOC. ~1,365 new LOC total. Kernel ~4,600 (within EC-6). |
| **WEIGHTED TOTAL** | | **6.35** | |

### S4: Functional Core Shell

| Criterion | Wt | Score | Justification |
|---|---|---|---|
| Solo-developer velocity | 20% | **6** | 18 iterations, 9 days. Red-team §g flagged risk adjustment +4 for cutover risk → worst-case 22 iterations, 11 days. |
| Migration risk | 20% | **5** | Red-team §a §g: "big-bang cutover" — cannot toggle-gate per-component. S2 attacks S4: "MC-4 applies at full-engine granularity, not per-extraction." This is the most significant risk finding. Dual-path running is possible but coarser rollback than S1/S2. |
| FAER family divergence | 20% | **6** | Red-team §c: "Planner is a Protocol — implement HADRPlanner." 2-2.5 days. But S5 attacks S4: "JourneyPlanner IS a plugin bundle that won't admit it." Composition (mil triage + HADR routing) requires planner decomposition. |
| Notebook-first validation | 15% | **10** | The killer feature. Pure planner functions testable with plain asserts — no SimPy, no fixtures. Every decision function can be validated in a notebook with synthetic inputs. Red-team §b confirmed zero CP-3 exposure in planner. Best testability of all approaches. |
| Contested scenario extensibility | 15% | **5** | Planner can include contested route check in plan_transport(). Better than S1 (centralised decision), but no interceptor pattern. Adding new denial modes requires modifying planner. |
| LOC efficiency | 10% | **8** | engine.py eliminated. shell.py ~120 LOC + planner ~250 LOC. Total kernel ~4,100. Best LOC efficiency. |
| **WEIGHTED TOTAL** | | **6.30** | |

### S5: Plugin Sync Hexagonal

| Criterion | Wt | Score | Justification |
|---|---|---|---|
| Solo-developer velocity | 20% | **6** | 18 iterations, 9 days. Red-team §g: +3 risk for Protocol design uncertainty → worst-case 21, 10.5 days. Protocol definitions must be designed before any plugin exists. |
| Migration risk | 20% | **6** | Protocol definitions are speculative until a second variant exists. Red-team cross-team: S1 attacks S5 on premature abstraction (KL-1). Engine rewrite to accept plugins is a moderate structural change, not a pure extraction. |
| FAER family divergence | 20% | **9** | Red-team §c: "1.5-2 days for HADR. MEETS TARGET." Best variant support. New variant = new plugin files, not branch modification. KL-4 satisfied. But §c also flagged: "yield STRUCTURE is not pluggable, only decisions." |
| Notebook-first validation | 15% | **7** | Plugins testable in isolation (sync, no SimPy). But plugin integration requires engine wiring. Plugin Protocol conformance must be tested against the engine, not just in isolation. |
| Contested scenario extensibility | 15% | **6** | TransportPlugin can incorporate contested logic. But no interceptor chain — contested denial is a plugin decision, not an orthogonal concern. EP-2 partially addressed. |
| LOC efficiency | 10% | **6** | engine.py→~650 LOC. ~1,275 new LOC + plugin implementations. Total kernel ~4,400. Acceptable. |
| **WEIGHTED TOTAL** | | **6.70** | |

### S6: Deterministic Command Bus (Wildcard)

| Criterion | Wt | Score | Justification |
|---|---|---|---|
| Solo-developer velocity | 20% | **4** | 22 iterations, 11 days base. Red-team §g: +3 for CP-3 compound command issue → worst-case 25, 12.5 days. Most infrastructure of any approach (Commands, Dispatcher, Interceptors, CommandLog). |
| Migration risk | 20% | **4** | Red-team §b found structural CP-3 issue: Y1+Y2 must share a `with resource.request()` block but separate commands release between them. "THIS IS A POTENTIAL FATAL FLAW." Fixable via compound commands but undermines the abstraction. Most orchestration file disruption (§h: 1 eliminated, 2 partially rewritten). |
| FAER family divergence | 20% | **8** | Good variant support via swappable policies. Better than S5 for execution-order divergence (S6 attacks S5 on this). But same journey-structure rigidity concern. |
| Notebook-first validation | 15% | **6** | Policies testable (sync, pure). But dispatcher requires SimPy fixtures. CommandLog replay testable in notebooks. Mixed. |
| Contested scenario extensibility | 15% | **9** | Best EP-2 support. ContestedRouteInterceptor denies BeginTransit commands. Interceptor chain is orthogonal — add ConsumableInterceptor (EP-7) without modifying any existing code. Red-team §e: best replay capability. |
| LOC efficiency | 10% | **4** | ~1,685 new LOC. CommandLog adds ~375MB/Monte Carlo. Total kernel ~4,900 (borderline EC-6). Most new code of any approach. |
| **WEIGHTED TOTAL** | | **5.70** | |

---

### SCORECARD SUMMARY TABLE

| Approach | Velocity (20%) | Risk (20%) | Divergence (20%) | Notebook (15%) | Contested (15%) | LOC (10%) | **TOTAL** |
|---|---|---|---|---|---|---|---|
| S1 Minimalist | 9 (1.80) | 9 (1.80) | 3 (0.60) | 9 (1.35) | 4 (0.60) | 8 (0.80) | **6.95** |
| S2 Strangler | 6 (1.20) | 8 (1.60) | 3 (0.60) | 8 (1.20) | 4 (0.60) | 6 (0.60) | **5.80** |
| S3 A+E | 7 (1.40) | 8 (1.60) | 4 (0.80) | 9 (1.35) | 4 (0.60) | 7 (0.70) | **6.45** |
| S4 Func Core | 6 (1.20) | 5 (1.00) | 6 (1.20) | 10 (1.50) | 5 (0.75) | 8 (0.80) | **6.45** |
| S5 Plugin Hex | 6 (1.20) | 6 (1.20) | 9 (1.80) | 7 (1.05) | 6 (0.90) | 6 (0.60) | **6.75** |
| S6 Cmd Bus | 4 (0.80) | 4 (0.80) | 8 (1.60) | 6 (0.90) | 9 (1.35) | 4 (0.40) | **5.85** |

**Ranking: S1 (6.95) > S5 (6.75) > S3 (6.45) = S4 (6.45) > S6 (5.85) > S2 (5.80)**

S1 and S5 are Pareto-dominant across different dimensions: S1 wins velocity+risk, S5 wins divergence. Neither dominates the other. This is precisely why the hybrid exists.

---

## SYNTHESIS

### a) HYBRID: "Tidy First, Then Plug" (S1 → S5, with S3's analytics)

The hybrid takes specific components from three approaches:

**From S1 (Phase 1 — immediate):**
- `routing.py` (EX-1): pure function, ~70 LOC extracted
- `metrics.py` (EX-2): pure aggregation, ~62 LOC extracted
- `emitter.py` (EX-3): EventEmitter Protocol replacing legacy `_log_event()`
- `pfc.py` (EX-4 sync): pure PFC evaluation function
- K-3 deletion (legacy triage dead code)
- All MC-4 toggle-gated. All validated per MC-3 (±5% distribution match on fixed seeds).

**From S5 (Phase 2 — when HADR commissioned):**
- `plugins/protocols.py`: TriagePlugin, RoutingPlugin, TransportPlugin, PFCPlugin, InjuryPlugin
- `plugins/military.py`: wraps Phase 1 pure functions behind Plugin Protocols (~50 LOC per plugin — mechanical wrapping, not redesign)
- `plugins/hadr.py`: new HADR implementations
- `plugins/registry.py`: VariantPlugins bundle + load_variant() factory
- engine.py rewired to accept VariantPlugins in __init__

**From S3 (Phase 2 — concurrent with plugins):**
- `analytics/engine.py`: AnalyticsEngine subscribing to EventBus (CP-2)
- `analytics/views.py`: GoldenHourView, FacilityLoadView, SurvivabilityView
- Dashboard reads views, not engine state (resolves I-1, I-4)

**NOT taken from S4:**
- The functional core/shell split. Red-team proved the big-bang cutover risk outweighs testability gains for a solo developer. The PLANNER pattern is excellent but can be adopted incrementally — Phase 1's pure functions ARE the functional core. If Phase 3 is needed, converting extracted functions into a formal JourneyPlanner Protocol is a small step from the hybrid's Phase 2 state.

**NOT taken from S6:**
- The command bus infrastructure. Red-team found the CP-3 compound command issue and the high iteration count. The interceptor concept IS valuable for EP-2, but can be implemented as a simpler `TransportPlugin.check_denial()` call in S5's architecture without the full command/dispatcher machinery.

**NOT taken from S2:**
- EX-5/EX-6 yield delegation is deferred to Phase 3. The risk of hold/PFC extraction (red-team §g: iteration count could double) is not justified until Phase 1+2 are proven. engine.py at ~650 LOC (post-Phase 2) may be acceptable without further extraction.

### b) MIGRATION PLAN

#### Phase 1: Tidy (Weeks 1-2) — SHIPS STANDALONE VALUE

**Goal:** Extract 624 LOC of pure logic from engine.py. Resolve K-1 (partial), K-3, K-7.

| Week | Step | EX# | Action | New LOC | Engine delta | Toggle |
|------|------|-----|--------|---------|-------------|--------|
| 1.1 | 1 | EX-1 | Extract `routing.py` (get_next_destination + ATMIST) | ~210 | -70 | `toggles.use_extracted_routing` |
| 1.2 | 2 | EX-2 | Extract `metrics.py` (compute_metrics from EventStore) | ~186 | -62 | `toggles.use_extracted_metrics` |
| 1.3 | 3 | K-3 | Delete legacy `_triage_decisions()` | 0 | -28 | — (pure deletion) |
| 2.1 | 4 | EX-3 | Extract `emitter.py` (EventEmitter Protocol + TypedEmitter impl) | ~219 | -53 | `toggles.use_typed_emitter` |
| 2.2 | 5 | EX-4 | Extract `pfc.py` (evaluate_pfc sync decision function) | ~180 | -60 | `toggles.use_extracted_pfc` |
| 2.3 | 6 | — | Integration test: run NB32 acceptance test through all toggles ON | ~50 (test) | 0 | all ON |

**Phase 1 exit state:**
- engine.py: 1,309 → ~800 LOC (after extracting ~273 LOC net, plus cleanup)
- New files: routing.py, metrics.py, emitter.py, pfc.py (~795 LOC)
- Total kernel: ~5,030 LOC (temporary inflation from Protocols + toggle infrastructure)
- K-1: partial (800 vs 1,309). K-3: resolved. K-7: resolved.
- **12 iterations. ~6 days. Shippable independently.**
- **Validation:** Fixed-seed regression on every toggle flip. NB32 acceptance test. ±5% distribution match (MC-3).

#### Phase 2: Plug + Decouple (Weeks 3-6) — TRIGGERED BY HADR COMMISSION

**Goal:** Promote extractions to Plugin Protocols. Build HADR variant. Decouple analytics.

| Week | Step | Action | New LOC | Engine delta |
|------|------|--------|---------|-------------|
| 3.1 | 7 | Define Plugin Protocols (`plugins/protocols.py`) from Phase 1 function signatures | ~120 | 0 |
| 3.2 | 8 | Wrap Phase 1 pure functions as MilitaryPlugins (mechanical wrapping) | ~150 | 0 |
| 4.1 | 9 | Build `VariantPlugins` + `load_variant()` + engine wiring | ~120 | +30 (plugin init) |
| 4.2 | 10 | Rewire engine.py to call plugins instead of direct imports | ~80 (rewiring) | -50 (simplification) |
| 5.1 | 11 | Build HADRTriagePlugin + HADRRoutingPlugin | ~160 | 0 |
| 5.2 | 12 | Build HADRTransportPlugin + HADRPFCPlugin | ~130 | 0 |
| 5.3 | 13 | AnalyticsEngine scaffold + EventBus subscription | ~150 | 0 |
| 6.1 | 14 | Build GoldenHourView + FacilityLoadView + SurvivabilityView | ~200 | 0 |
| 6.2 | 15 | Dashboard migration (read views, not engine state) | ~100 | -40 (query removal) |
| 6.3 | 16 | Integration: run MIL + HADR variants, validate both | ~50 (test) | 0 |

**Phase 2 exit state:**
- engine.py: ~800 → ~650 LOC (plugin injection simplifies decision call sites)
- New files: protocols.py, military.py, hadr.py, registry.py, analytics/*.py (~1,260 LOC)
- Total kernel: ~5,300 LOC (but analytics is cold-path, so hot-path kernel ~4,100)
- K-1: resolved (650). K-2: resolved (InjuryPlugin replaces dual factory). K-4: resolved (TransportPlugin loads from config). K-7: resolved. I-1, I-4: resolved.
- **10 iterations. ~5 days. But only after HADR is actually commissioned.**

#### Phase 3: Delegate (Weeks 7-12) — ONLY IF PHASE 2 PROVES INSUFFICIENT

**Goal:** Extract yield-bearing generators via `yield from` (S2's EX-5/EX-6).

| Step | Action | New LOC | Risk |
|------|--------|---------|------|
| 17 | Extract treatment.py sub-generator (Y1+Y2) | ~465 | MEDIUM |
| 18 | Extract hold_pfc.py sub-generator (Y3) | ~420 | HIGH |
| 19 | Validate exception propagation in yield-from + resource blocks | ~100 (test) | HIGH |

**Phase 3 exit state:**
- engine.py: ~650 → ~500 LOC (orchestrator with `yield from`)
- New files: treatment.py, hold_pfc.py (~885 LOC)
- **12 iterations. ~6 days. HIGH RISK — only pursue if K-1 at 650 LOC is still the bottleneck.**
- **Gating criterion:** If Phase 2 engine.py at ~650 LOC is manageable for the solo developer, Phase 3 is unnecessary. The 650 LOC engine with plugins is significantly simpler than the current 1,309 LOC monolith.

### c) TOP 5 RISKS WITH MITIGATIONS

| # | Risk | Probability | Impact | Mitigation |
|---|------|-------------|--------|------------|
| 1 | **Phase 2 Plugin Protocols designed wrong** — interface shapes don't match HADR needs | Medium | High (rework ~300 LOC) | Phase 1 pure function signatures ARE the Protocol prototypes. `routing.get_next_destination()` → `RoutingPlugin.select_destination()` is mechanical. Design FROM implementations, not TO implementations. If HADR reveals a shape mismatch, the Protocol changes — not the engine. |
| 2 | **Phase 1 EX-3 (emitter) breaks event determinism** — typed emitter publishes events in a different order than legacy `_log_event()` | Low | High (HC-2 violation) | Fixed-seed regression test before and after toggle flip. EventBus subscriber order preserved. EX-3 is a protocol change (what publishes), not a timing change (when). Events published at exactly the same SimPy `env.now` values. |
| 3 | **Phase 2 AnalyticsEngine sync view updates slow down hot path** — complex views add latency between yields | Medium | Medium (perf degradation) | Red-team quantified: ~450μs/casualty at 3 views. For 5,000 casualties: 2.25s total. Acceptable. If views grow complex (EP-7 consumables), move to deferred update mode (queue events, process in batch after run()). This is a Phase 2+ optimisation, not a design change. |
| 4 | **Phase 3 EX-6 hold/PFC extraction breaks timing** — nested generator exception propagation alters resource release order | Medium | High (CP-3 corruption) | Gate Phase 3 on proof: build EX-6 in a notebook first (NB33). Run 10,000-casualty comparison on fixed seed. If ANY casualty diverges, do not merge. S2's red-team confirmed Python handles yield-from correctly, but the hold/PFC loop's 140 LOC of nested conditionals is the highest-risk extraction in the kernel. |
| 5 | **EventStore OOM at Monte Carlo scale** — 100+ replications × 15MB/run | Medium | Medium (OOM crash) | Phase 2 AnalyticsEngine enables incremental view computation. After views capture all needed analytics, EventStore can be flushed between replications. `EventStore.clear()` after each `engine.run()` completion. Views retain only aggregated snapshots (~100 bytes/view). |

### d) "Choose this because..."

Choose S1→S5 hybrid because it is the only approach that delivers shippable value in Week 1 (pure extractions reducing K-1 from 1,309 to ~800 LOC) while structurally preparing for FAER family divergence without building speculative infrastructure. Phase 1 is Pattern A — the lowest-risk, highest-velocity, all-three-LLMs-converged approach. Phase 2 is Pattern B (sync-only) — the highest-extensibility approach for EP-1, triggered only when a real variant demands it. Every Phase 1 extraction becomes a Phase 2 plugin component with mechanical wrapping (~50 LOC/plugin), so no Phase 1 work is thrown away. The architecture grows from NB32's kernel primitive exactly as NB32 instructs: "Each DSE agent must explain how their proposed architecture GROWS this kernel into the full engine — not how they'd replace it." This hybrid grows the kernel through validated extractions (Phase 1) then structured extension (Phase 2), never replacement.

### e) "The biggest risk is..."

The biggest risk is that Phase 2 Plugin Protocols are designed prematurely — before HADR's actual requirements are known — and must be reworked when reality diverges from speculation. This is KL-1 in miniature: "Specification outran verification." The mitigation is deliberate: Phase 1's pure function signatures serve as empirical interface prototypes. `routing.get_next_destination(casualty, current_facility, network, rng) → RoutingDecision` has been validated by running real casualties through real networks. When Phase 2 arrives, wrapping this into `RoutingPlugin.select_destination()` requires adding one level of indirection, not redesigning the data flow. If the HADR variant reveals that the function signature is wrong (e.g., HADR routing needs facility-level load data that MIL routing doesn't), the Protocol gains a parameter — a local change, not an architectural one. The risk is real but bounded: Protocol rework affects ~300 LOC of interface definitions, not the 11-file kernel or the Phase 1 extractions.

### f) NB32 ACCEPTANCE TEST TRACES

#### TRACE 1: Phase 1 State (S1 — Pure Extractions, engine.py ~800 LOC)

```pseudo
# 20 casualties, POI→R1→R2, POI→R1 contested 20% denial, seed=42

# --- Setup (unchanged from NB32 except emitter wiring) ---
engine = FAEREngine(seed=42)
engine.emitter = TypedEmitter(engine.log)                   # NEW: EX-3
engine.build_network(topology)                               # unchanged
engine.generate_casualties(20)                               # unchanged
engine.run(until=600.0)

# --- Per-casualty process (engine.py, ~220 LOC generator) ---
def _patient_process(self, cas):
    yield self.env.timeout(cas.created_at)
    cas.state = WAITING
    self.emitter.emit_arrival(cas, "POI", self.env.now)      # EX-3: was self._log(...)

    # Triage — sync BT tick (unchanged contract)
    self.bb.clear()
    self.bb.set_mist_context(cas.mist)                       # IC-2: 8 keys written
    cas.triage = self.bt.tick(self.bb)                        # HC-5/HC-6: sync
    self.emitter.emit_triage(cas, "POI", self.env.now)       # IC-3 read

    current = "POI"
    while True:
        # Routing — EXTRACTED (EX-1)
        decision = routing.get_next_destination(              # was: inline code
            cas, current, self.network, self.rng)             # module: routing.py
        if decision.next_facility is None:
            break

        # Contested check — decision comes from routing (EP-2)
        if decision.is_denied:
            wait = self.rng.exponential(15)
            yield self.env.timeout(wait)
            cas.total_wait_time += wait
            self.emitter.emit_hold_retry(cas, current, self.env.now)
            continue

        # Transit
        cas.state = IN_TRANSIT
        travel = decision.travel_time
        if cas.triage == T1: travel *= 0.7
        yield self.env.timeout(travel)                       # ← YIELD 5   owner: engine.py
        cas.total_transit_time += travel
        self.emitter.emit_transit_end(cas, decision.next_facility, self.env.now)

        # Treatment — CP-3 resource interaction (STAYS in engine)
        cas.state = IN_TREATMENT
        cas.current_facility = decision.next_facility
        cas.facilities_visited.append(decision.next_facility)
        resource = self._resources[decision.next_facility]
        with resource.request() as req:
            queue_start = self.env.now
            yield req                                        # ← YIELD 1   owner: engine.py
            cas.total_wait_time += self.env.now - queue_start
            treat_time = self.rng.exponential(20 + cas.mist.severity_score * 40)
            yield self.env.timeout(treat_time)               # ← YIELD 2   owner: engine.py
            cas.total_treatment_time += treat_time
            self.emitter.emit_treatment_complete(cas, decision.next_facility, "", self.env.now)

        # PFC check — EXTRACTED decision (EX-4), yield loop in engine
        if hold_required(cas, decision.next_facility):
            hold_start = self.env.now
            while not downstream_available(self.network, decision.next_facility):
                action = pfc.evaluate_pfc(                   # was: 140 LOC inline
                    cas, self.env.now - hold_start,           # module: pfc.py
                    False, PFC_THRESHOLD)
                if action == ESCALATE_PFC:
                    cas.state = PFC
                    self.emitter.emit_pfc_start(cas, decision.next_facility, self.env.now)
                yield self.env.timeout(RETRY_INTERVAL)       # ← YIELD 3   owner: engine.py

        current = decision.next_facility

    cas.outcome_time = self.env.now
    cas.state = DISCHARGED
    self.emitter.emit_disposition(cas, current, self.env.now) # KL-6: MUST match ARRIVAL

# --- Survivability (unchanged) ---
for cas in engine.casualties:
    p_surv = compute_survivability(cas)

# --- Verification ---
# Triage: Counter(c.triage for c in engine.casualties)
# Events: len(log.events_of_type("DISCHARGED")) == 20
# Determinism: engine2 = FAEREngine(seed=42); ... assert match
```

**Module ownership at each yield:**
| Yield | Location | Module | Change from NB32 baseline |
|-------|----------|--------|--------------------------|
| Y1 | `yield req` | engine.py | No change |
| Y2 | `yield env.timeout(treat_time)` | engine.py | No change |
| Y3 | `yield env.timeout(RETRY_INTERVAL)` | engine.py | No change (decision extracted, yield stays) |
| Y5 | `yield env.timeout(travel)` | engine.py | No change |
| (stagger) | `yield env.timeout(cas.created_at)` | engine.py | No change |

**Sync call sites that CHANGED:**
- `routing.get_next_destination()`: was inline → now `routing.py`
- `pfc.evaluate_pfc()`: was 140 LOC inline → now `pfc.py`
- `self.emitter.emit_*()`: was `self._log_event(dict)` → now typed protocol

#### TRACE 2: Phase 2 State (S1→S5 Hybrid — Plugins, engine.py ~650 LOC)

```pseudo
# Same scenario. DIFF: plugins injected, analytics decoupled.

# --- Setup ---
plugins = load_variant("LSCO", config)                      # NEW: returns VariantPlugins
# plugins.triage = MilitaryTriagePlugin(bt_tree, blackboard)
# plugins.routing = MilitaryRoutingPlugin()
# plugins.transport = MilitaryTransportPlugin()
# plugins.pfc = MilitaryPFCPlugin()
# plugins.injury = MilitaryInjuryPlugin(mist_sampler)

engine = FAEREngine(seed=42, plugins=plugins)                # plugins injected
analytics = AnalyticsEngine(engine.log.bus)                  # NEW: subscribes to EventBus
engine.build_network(topology)
engine.generate_casualties(20)
engine.run(until=600.0)

# --- Per-casualty process (engine.py, ~180 LOC generator) ---
def _patient_process(self, cas):
    yield self.env.timeout(cas.created_at)
    cas.state = WAITING
    self.emitter.emit_arrival(cas, "POI", self.env.now)

    # Triage — PLUGIN (sync)
    self.plugins.triage.assign_triage(cas, self.bb)          # DIFF: was routing.* call
    cas.triage = self.bb.get("decision_triage")              # IC-3: same contract

    current = "POI"
    while True:
        # Routing — PLUGIN (sync)
        decision = self.plugins.routing.select_destination(   # DIFF: was routing.* call
            cas, current, self.network, self._facility_states())

        if decision.next_facility is None:
            break

        # Transport plan — PLUGIN (sync, includes contested check)
        plan = self.plugins.transport.select_transport_mode(  # DIFF: replaces inline denial
            cas, current, decision.next_facility,
            self.network, self.rng)

        if plan.is_denied:
            yield self.env.timeout(plan.denial_wait)
            cas.total_wait_time += plan.denial_wait
            self.emitter.emit_hold_retry(cas, current, self.env.now)
            continue

        # Transit — engine owns yield
        cas.state = IN_TRANSIT
        yield self.env.timeout(plan.travel_time)             # ← YIELD 5   owner: engine.py
        cas.total_transit_time += plan.travel_time
        self.emitter.emit_transit_end(cas, decision.next_facility, self.env.now)

        # Treatment — engine owns yields (CP-3)
        cas.state = IN_TREATMENT
        cas.current_facility = decision.next_facility
        cas.facilities_visited.append(decision.next_facility)
        resource = self._resources[decision.next_facility]
        with resource.request() as req:
            queue_start = self.env.now
            yield req                                        # ← YIELD 1   owner: engine.py
            cas.total_wait_time += self.env.now - queue_start
            treat_time = self.rng.exponential(20 + cas.mist.severity_score * 40)
            yield self.env.timeout(treat_time)               # ← YIELD 2   owner: engine.py
            cas.total_treatment_time += treat_time
            self.emitter.emit_treatment_complete(
                cas, decision.next_facility, "", self.env.now)

        # PFC — PLUGIN decision (sync), engine owns yield loop
        hold_start = self.env.now
        while True:
            downstream = downstream_available(self.network, decision.next_facility)
            hold = self.plugins.pfc.evaluate(                # DIFF: was pfc.evaluate_pfc()
                cas, self.env.now - hold_start, downstream)
            if hold.action == RELEASE:
                break
            if hold.action == ESCALATE_PFC:
                cas.state = PFC
                self.emitter.emit_pfc_start(cas, decision.next_facility, self.env.now)
            yield self.env.timeout(hold.retry_interval)      # ← YIELD 3   owner: engine.py

        current = decision.next_facility

    cas.outcome_time = self.env.now
    cas.state = DISCHARGED
    self.emitter.emit_disposition(cas, current, self.env.now) # KL-6

# --- Analytics (NEW cold path — runs synchronously during emit) ---
# AnalyticsEngine._on_event() called for each SimEvent published by emitter
# GoldenHourView, FacilityLoadView, SurvivabilityView updated incrementally
# Dashboard reads: analytics.get_view("survivability").snapshot()

# --- Survivability ---
surv_data = analytics.get_view("survivability").snapshot()
# OR: compute_survivability(cas) for per-casualty (unchanged)

# --- Verification ---
# Same as Phase 1: deterministic replay, event count match, ±5% distribution
```

**Module ownership at each yield (Phase 2 — UNCHANGED from Phase 1):**
| Yield | Module | Change from Phase 1 |
|-------|--------|---------------------|
| Y1 | engine.py | No change |
| Y2 | engine.py | No change |
| Y3 | engine.py | No change (plugin provides decision, engine yields) |
| Y5 | engine.py | No change |

**Sync call sites that changed Phase 1 → Phase 2:**
- `routing.get_next_destination()` → `plugins.routing.select_destination()` (wrapped behind Protocol)
- `pfc.evaluate_pfc()` → `plugins.pfc.evaluate()` (wrapped behind Protocol)
- NEW: `plugins.triage.assign_triage()` (replaces direct BT tick — but internally still calls bb.set_mist_context → bt.tick → bb.get)
- NEW: `plugins.transport.select_transport_mode()` (includes contested route check)
- NEW: `AnalyticsEngine` subscribes to EventBus (zero engine code change)

**Critical invariant preserved:** All 5 yields in engine.py. Plugins are sync-only. EventBus subscription is synchronous (called during emit, between yields, not during). HC-1 through HC-6 satisfied by construction. KL-6 DISPOSITION count enforced by generator structure (one emit_disposition per generator exit). HC-2 deterministic replay verified by fixed-seed comparison across Phase 1 → Phase 2 migration.
