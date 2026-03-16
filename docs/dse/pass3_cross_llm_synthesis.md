# FAER DSE — Pass 3: Cross-LLM Synthesis
## Final Architectural Recommendation

---

# 1. CONVERGENCE (High Agreement = High Confidence)

## 1a. Universal Agreement (all 3 LLMs)

**Yield ownership must stay centralised.** All three LLMs agree that SimPy yields must remain in a single generator or its direct `yield from` delegates. No LLM's final recommendation moves yields into plugins, subscribers, or external processes. This is the strongest consensus finding and directly reflects HC-1, HC-9, PR-2, PR-8.

**Pattern D (Incrementalist/Strangler) is the safest migration mechanism.** All three select toggle-gated (MC-4), fixed-seed-validated (MC-3) incremental extraction as the delivery method — even when the TARGET architecture differs. Claude sequences S1 extractions behind toggles. Gemini deploys hexagonal boundaries via strangler toggles. ChatGPT makes Pattern D the entire recommendation. None propose a big-bang cutover.

**Pattern E (Dual-Speed Analytics) should be an early structural separation.** All three decouple analytics via EventBus (CP-2) in Phase 1 or very early Phase 2. Claude includes it in S3 (Phase 2). Gemini makes it Phase 1 step 1. ChatGPT makes it the "first structural split." The consensus: CP-2 is the lowest-cost boundary (Context Index §12), so exploit it immediately.

**EX-1→EX-3 form the safe Phase 1.** All three place pure function extraction (EX-1), metrics extraction (EX-2), and typed emitter formalisation (EX-3) in weeks 1-2. No LLM includes yield-bearing extractions (EX-4/EX-5/EX-6) in Phase 1. This directly reflects the validated extraction order from Lessons §6.

**The 11-file irreducible kernel (KF-2) is preserved.** All three explicitly state the 11 non-orchestration files are not architecture-dependent and must survive any rebuild unchanged. The 5 orchestration files are the targets.

**ECS Tick Architecture is dead.** All three killed full ECS replacement of SimPy (HC-1, PR-1). Gemini's SimPy-preserving ECS variant was flagged as a disputed kill in Step 1 triage but none of the three carried it into final recommendations.

**K-7 (typed event fields empty) resolved by EX-3.** All three identify that formalising the EventEmitter protocol as typed, frozen events closes K-7 and is a prerequisite for analytics decoupling.

**EventStore OOM is a universal risk at Monte Carlo scale.** All three flag unbounded event log growth at 5,000+ casualties. All propose incremental view computation or flush-between-runs as the mitigation.

## 1b. Strong Agreement (2 of 3 LLMs)

**Plugin/hexagonal architecture for EP-1 variant divergence.** Claude (S5) and Gemini (Hexagonal) both propose sync-only Plugin Protocols as the structural answer to FAER family divergence. ChatGPT does not include plugins in its recommendation, deferring variant support to "Phase 2/3 family-divergence seams" without specifying a mechanism.

**Phase 1 ships in ≤2 weeks with 8-12 iterations.** Claude (12 iterations, 6 days) and ChatGPT (8-12 iterations per exit criteria) explicitly confirm EC-1. Gemini's Phase 1 is scoped similarly but doesn't give a precise iteration count.

---

# 2. DIVERGENCE (Where They Disagree)

## 2a. CRITICAL DIVERGENCE: Plugin Architecture Timing

| | Claude | Gemini | ChatGPT |
|---|---|---|---|
| **Claim** | Plugins deferred to Phase 2, triggered ONLY when HADR is commissioned. Phase 1 extractions become plugin prototypes. | Plugins are the primary structural target. Phase 2 builds the hexagonal boundaries. | No plugins. Pattern D strangler + Pattern E analytics is sufficient. Deeper divergence seams deferred to Phase 3. |
| **Rationale** | KL-1: "Specification outran verification." Designing Protocols before a variant exists risks premature abstraction. | EP-1 is a stated requirement, not speculative. Scoring 10 on family divergence. | HC-7/HC-8: solo-developer velocity and incremental migration mean plugins are too much infrastructure too early. |

**Context Index evidence:** EP-1 (variant family) is listed as a required extension point, not optional. KL-4 warns against framework unification but supports shared patterns. KL-1 warns against specification outrunning verification. Both positions have support — this is a genuine tension.

**Resolution:** Claude's phased approach resolves the tension: Phase 1 extractions shape the interfaces empirically, Phase 2 wraps them in Protocols when needed. This satisfies EP-1 without violating KL-1. **Flag for human judgment: when is HADR actually commissioned? If imminent, Gemini's urgency is correct. If 3+ months away, Claude's deferral is safer.**

## 2b. DIVERGENCE: Functional Core Shell

| | Claude | Gemini | ChatGPT |
|---|---|---|---|
| **Included in final?** | Evaluated but rejected for final hybrid. Cited big-bang cutover risk. | Evaluated, scored 6.15. Not in final hybrid. Cited CP-3 prediction friction. | Evaluated as runner-up. Praised conceptual clarity but cited velocity sacrifice. |

**Consensus:** All three acknowledge functional core/shell is the best testability architecture but too risky/slow for Phase 1. None include it in their primary recommendation. **This is a confirmed "good idea, wrong time" finding.**

## 2c. DIVERGENCE: Command Bus / Wildcard

| | Claude | Gemini | ChatGPT |
|---|---|---|---|
| **Evaluation** | Shortlisted as S6 wildcard. Found CP-3 compound command structural issue (Y1+Y2 in single `with` block). Scored 5.85. | Shortlisted as wildcard but replaced by Declarative Journey DSL. Scored DSL at 4.55. | Not shortlisted. Mentioned briefly as "strongest explicit-control architecture" but dismissed on velocity grounds. |

**Context Index evidence:** Claude's CP-3 compound command finding is the most specific technical discovery across all three analyses. The `with resource.request()` block must span both Y1 and Y2 — separate commands break this. Neither Gemini nor ChatGPT identified this structural flaw.

**Resolution:** Command Bus is confirmed as a Phase 3+ exploration, not a Phase 1-2 candidate. Claude's CP-3 finding should be preserved as a design constraint for any future command-based architecture.

## 2d. DIVERGENCE: Yield Delegation via `yield from`

| | Claude | Gemini | ChatGPT |
|---|---|---|---|
| **Position** | Defers EX-5/EX-6 yield delegation to optional Phase 3. Flags exception propagation risk. | Includes yield delegation (EX-5/EX-6) in Phase 2 via strangler. Accepts the risk. | Includes yield delegation in Phase 2 toggles. Notes CP-3 pass-by-reference is "negligible overhead." |

**Context Index evidence:** EX-5 is MEDIUM risk, EX-6 is HIGH risk (Context Index §validated extraction order). MC-1 says 3× LOC multiplier. The hold/PFC loop (140 LOC nested) is explicitly called out as the highest-risk extraction.

**Resolution:** Claude's caution is better calibrated to the risk data. Gemini and ChatGPT may be underweighting EX-6 risk. **Recommend: Phase 2 attempts EX-5 (treatment, MEDIUM risk). EX-6 (hold/PFC, HIGH risk) is Phase 3, gated on EX-5 success.**

---

# 3. COMPREHENSION QUALITY

## 3a. Comprehension Gate Comparison

| Question | Claude | Gemini | ChatGPT |
|---|---|---|---|
| **a) Kernel primitive (KF-7)** | "~255 LOC across 6 layers... 20 casualties → BT triage → graph route → treatment → outcome with survivability." Lists all 6 layers with LOC. References NB32 as executable truth. | "Verified core execution path... approximately 255 lines of code." Correct but surface-level. | No explicit comprehension gate (ChatGPT's Step 2a was the essay-format document, not structured). |
| **b) DES↔BT coupling (CP-1)** | "Write→tick→read cycle is atomic relative to SimPy event queue — occurs between yield points, never during them. NB16 stress-tested concurrent access." Precise mechanism + validation reference. | "Couple synchronously via the Blackboard (CP-1), which handles roughly 16 mutable read/write operations per casualty." Correct, references coupling data. | Covered in essay form: "The engine writes the context to the blackboard, ticks the tree synchronously, and reads the definitive output." Correct but buried in prose. |
| **c) Biggest debt (K-1)** | "K-1: engine.py at 1,309/1,335 LOC... _patient_journey() 327 LOC with 5 yield points. Hold/PFC loop 140 LOC. Blocks every extension point." Links to EP-1, EP-3, EP-6. | "1,309 LOC engine.py file (KF-3), specifically its 327 LOC _patient_journey() monolithic generator which deeply embeds a rigid 140 LOC nested conditional block." Correct, concise. | Covered extensively in essay. References all the same numbers. |
| **d) NB31 migration cost (MC-1 to MC-4)** | "86 LOC → ~250 LOC + YAML (3× multiplier). 1-2 days. ±5% distribution calibration. Strangler toggle with factory_mode flag." All 4 metrics referenced with specific values. | "1-2 days each (MC-2) and expands code by a 3x multiplier (MC-1), demanding toggles (MC-4) and ±5% calibration (MC-3)." All 4 referenced. | Not explicitly gated. MC values used throughout the essay but not confirmed upfront. |

**Ranking: Claude > Gemini > ChatGPT on comprehension precision.**

Claude demonstrated the deepest reading — referencing NB16 stress testing, listing all 6 NB32 layers with LOC, and connecting K-1 to specific extension point blockages. Gemini was accurate but more surface-level. ChatGPT produced a thorough essay but lacked the structured comprehension verification, making it harder to assess precision vs. recall.

**Weighting implication:** Claude's subsequent analysis carries highest confidence on technical specifics. Gemini's carries highest confidence on structural architecture (strong EP-1 focus). ChatGPT's carries confidence on risk identification and migration mechanics but should be verified on technical details.

---

# 4. BLIND SPOTS (Highest-Value Unique Findings)

## 4a. Claude Found, Others Missed

**CP-3 Compound Command Issue (S6 red-team §b).** The `with resource.request()` context manager must span both Y1 (acquisition) and Y2 (treatment timeout). Separate commands in a command bus architecture release the resource between them. This is a structural constraint on any future command-based or action-token architecture. **Neither Gemini nor ChatGPT identified this.**

**Big-Bang Cutover Risk for Functional Core Shell (S4 red-team §g).** Claude identified that the shell replaces the entire engine at once — MC-4 toggle pattern applies at full-engine granularity, not per-component. This is a materially different risk profile from strangler extractions. **ChatGPT noted this indirectly but didn't quantify the rollback asymmetry.**

**Phase 1 extractions AS Protocol prototypes.** Claude's insight that Phase 1 pure function signatures become Phase 2 Plugin Protocol shapes — making Phase 1 work a discovery process, not throwaway work — is unique and resolves the premature abstraction tension. **Neither Gemini nor ChatGPT articulated this connection.**

## 4b. Gemini Found, Others Missed

**Declarative Journey DSL as a wildcard.** Gemini was the only LLM to carry the DSL approach through all three stages with a full acceptance test trace. While it scored poorly (4.55), the concept of representing the journey as a step graph interpreted by the engine is a genuine alternative paradigm. **Claude mentioned it in Step 1 triage but didn't carry it forward. ChatGPT didn't propose it.**

**Plugin CP-3 snapshot timing.** Gemini's risk mitigation #3 specifies that the engine passes a "freshly locked snapshot" of facility state precisely when the synchronous plugin `decide()` method is invoked. This is a concrete implementation detail for the sync-plugin contract that Claude and ChatGPT left implicit.

## 4c. ChatGPT Found, Others Missed

**Migration scaffolding ≠ architecture progress.** ChatGPT's "biggest risk" paragraph articulates that Pattern D can stall in a half-modernised state if Phase 2 never arrives. "The mitigation is to define success at each phase in operational terms, not aesthetic terms." This is the most mature meta-risk observation across all three analyses. **Claude and Gemini defined phase gates but didn't explicitly name this failure mode.**

**Codegen Journey Templates.** ChatGPT was the only LLM to propose compiled journey templates as an approach (their Approach #6 in the red-team). While not recommended, the concept of precompiled, variant-specific generators loaded from a registry is a novel idea that could combine with the plugin architecture. **Neither Claude nor Gemini proposed this.**

---

# 5. SCORECARD COMPARISON

## 5a. Score Overlay (normalised to 1-10 scale, same criteria)

| Criterion (Weight) | Claude: S1→S5 Hybrid | Gemini: Hex CQRS Incr | ChatGPT: D+E Hybrid |
|---|---|---|---|
| Solo-dev velocity (20%) | S1=9, S5=6 → Phase-weighted: **8** | **5** (hex boilerplate tax) | **9** (Pattern D is fastest) |
| Migration risk (20%) | S1=9, S5=6 → Phase-weighted: **8** | **6** (protocol design uncertainty) | **9** (safest by design) |
| Family divergence (20%) | S1=3, S5=9 → Phase-weighted: **6** | **10** (raison d'être) | **6** (deferred to Phase 3) |
| Notebook validation (15%) | **9** | **8** | **10** (toggle comparisons) |
| Contested extensibility (15%) | **5** | **9** | **6** |
| LOC efficiency (10%) | **7** | **6** | **7** |
| **WEIGHTED TOTAL** | **7.10** | **7.35** | **7.95** |

## 5b. Divergences >2 Points

| Criterion | Claude | Gemini | ChatGPT | Investigation |
|---|---|---|---|---|
| Family divergence | 6 (Phase 2) | 10 (Phase 2) | 6 (Phase 3) | Gemini scores its own approach highest here because plugins ARE the recommendation. Claude and ChatGPT defer plugins, so score lower. **The gap reflects timing, not capability.** All three agree plugins solve EP-1; they disagree on WHEN. |
| Velocity | 8 (Phase 1 is S1) | 5 (hex boilerplate) | 9 (pure D+E) | Gemini's lower velocity score is self-consistent — hexagonal boundaries add ceremony. ChatGPT's Pattern D+E has the least new infrastructure. Claude's Phase 1 matches ChatGPT's velocity. **Gap is real: Gemini trades velocity for earlier extensibility.** |
| Contested extensibility | 5 (S1) | 9 (plugins) | 6 (deferred) | Gemini scores highest because plugins provide a natural EP-2 injection point. Claude's S1 Phase 1 has no structural EP-2 support. **Gap closes when Claude enters Phase 2 (S5 plugins).** |

---

# 6. PARETO FRONT

The three hybrid recommendations represent genuinely different points on the velocity-extensibility frontier:

```
                    HIGH EXTENSIBILITY
                          │
                     Gemini: Hex CQRS Incr
                     (7.35 weighted)
                     EP-1 ready in Phase 2
                     Velocity: 5/10
                          │
              ────────────┼────────────── 
                          │
     Claude: S1→S5        │
     (7.10 weighted)      │
     EP-1 ready when      │
     commissioned         │
     Velocity: 8/10       │
                          │
                          │        ChatGPT: D+E Hybrid
                          │        (7.95 weighted)
                          │        EP-1 deferred to Phase 3
                          │        Velocity: 9/10
                          │
                    HIGH VELOCITY
```

**No single recommendation dominates.** The tradeoff is real:
- ChatGPT's D+E is fastest to ship but weakest on EP-1
- Gemini's Hex CQRS is strongest on EP-1 but slowest Phase 1
- Claude's S1→S5 is the compromise — fast Phase 1, extensible Phase 2

**The deciding factor is HADR timing.** If HADR is imminent (next 6 weeks), Gemini's approach avoids rework. If HADR is 3+ months out, Claude's or ChatGPT's approach ships faster and defers the cost.

---

# 7. FINAL RECOMMENDATION

## 7a. Consolidated Architecture: "Tidy, Decouple, Then Plug"

This consolidation takes the strongest insight from each LLM:

**From ChatGPT:** Phase 1 is pure Pattern D+E. No new architectural concepts. EX-1, EX-2, EX-3 extracted behind toggles. AnalyticsEngine subscribes to EventBus. This is the fastest, safest start. Define success in operational terms, not aesthetic terms.

**From Claude:** Phase 1 pure function signatures ARE Phase 2 Plugin Protocol prototypes. No Phase 1 work is thrown away when Phase 2 arrives. The extraction IS the Protocol discovery process. CP-3 compound command constraint preserved as a design rule for any future command-based work.

**From Gemini:** Plugin Protocols enforce sync-only boundaries. Plugins return Plan dataclasses, never generators. Engine passes freshly snapshotted facility state at the moment of plugin invocation. The EventBus enforces ephemeral publish-subscribe with no unbounded append-only store.

### Architecture Summary

**Phase 1 state (weeks 1-2):** Pattern A+E. engine.py ~800 LOC. Pure functions extracted. Analytics decoupled via EventBus. All 5 yields in engine.py. Typed emitter closes K-7.

**Phase 2 state (weeks 3-6, triggered by HADR or continued refactoring):** Pattern B (sync-only). Phase 1 functions promoted to Plugin Protocols (~50 LOC/plugin wrapping). MilitaryPlugins wrap existing. HADRPlugins are new implementations. EX-5 treatment extraction via `yield from`. engine.py ~650 LOC.

**Phase 3 state (weeks 7-12, only if needed):** EX-6 hold/PFC extraction (HIGH risk, gated on EX-5 success). Deeper variant seams. engine.py ~500 LOC.

### Yield Ownership (EC-2)

| Yield | Phase 1 Owner | Phase 2 Owner | Phase 3 Owner |
|---|---|---|---|
| Y1 (resource acquire) | engine.py | engine.py | engine.py (or treatment.py via `yield from`) |
| Y2 (treatment timeout) | engine.py | engine.py | engine.py (or treatment.py via `yield from`) |
| Y3 (PFC retry) | engine.py | engine.py | engine.py (or hold_pfc.py via `yield from`) |
| Y4 (vehicle acquire) | engine.py | engine.py | engine.py |
| Y5 (travel timeout) | engine.py | engine.py | engine.py |

### Hard Constraint Verification (EC-4)

| HC | Status | How |
|---|---|---|
| HC-1 SimPy generator model | ✓ | Single generator throughout. `yield from` in Phase 3 only. |
| HC-2 Deterministic replay | ✓ | MC-4 toggles + MC-3 ±5% calibration at every step. |
| HC-3 Temporal causality | ✓ | No future state observation. BT ticks sync between yields. |
| HC-4 Event immutability | ✓ | EX-3 typed emitter publishes `@dataclass(frozen=True)`. |
| HC-5 Blackboard isolation | ✓ | Plugins read/write BB via IC-2/IC-3 contract only. |
| HC-6 Layer separation | ✓ | BT: zero SimPy imports. Plugins: zero SimPy imports. |
| HC-7 Solo-developer velocity | ✓ | 50-100 LOC iterations. Phase 1 = 12 iterations. |
| HC-8 Incremental migration | ✓ | Strangler pattern. Every step toggle-gated and reversible. |
| HC-9 Single process | ✓ | No microservices. No IPC. |
| HC-10 Python-first | ✓ | No Cython/Rust in Phase 1-2. |

### Debt Map (EC-5)

| Debt | Phase 1 | Phase 2 | Phase 3 |
|---|---|---|---|
| K-1 Monolith (1,309 LOC) | Partial (→~800) | Resolved (→~650) | Resolved (→~500) |
| K-2 Dual factory modes | Inherited | Resolved (InjuryPlugin) | — |
| K-3 Legacy triage dead code | Resolved (deleted) | — | — |
| K-4 Transport hardcoded configs | Inherited | Resolved (TransportPlugin) | — |
| K-5 Single-edge topology | Inherited | Inherited | Addressable |
| K-6 Transport teleportation | Inherited | Addressable | Resolved |
| K-7 Typed fields empty | Resolved (EX-3) | — | — |
| K-8 run() time semantics | Inherited | Inherited | Addressable |

### LOC Projection (EC-6)

| Phase | engine.py | New modules | Total kernel estimate |
|---|---|---|---|
| Current | 1,335 | — | 4,508 |
| Phase 1 | ~800 | ~795 (routing, metrics, emitter, pfc, analytics) | ~5,030 (temp inflation) |
| Phase 2 | ~650 | +~700 (protocols, plugins, registry) | ~4,900 (toggle cleanup) |
| Phase 2 steady | ~650 | toggles removed | ~4,400 ✓ |
| Phase 3 | ~500 | +~885 (treatment.py, hold_pfc.py) | ~4,200 ✓ |

## 7b. Migration Plan with Confidence

| Phase | Weeks | Iterations | Confidence | Gate |
|---|---|---|---|---|
| Phase 1: Tidy + Decouple | 1-2 | 12 | **HIGH** (all 3 LLMs agree, EX-1/2/3 are LOW risk, no yields move) | Fixed-seed regression. ±5% distribution match. NB32 acceptance test passes. |
| Phase 2: Plug (if HADR) | 3-6 | 10-15 | **MEDIUM** (Claude+Gemini agree on plugins, ChatGPT defers. Protocol design risk.) | HADR variant runs with same acceptance test. EX-5 toggle comparison passes. |
| Phase 3: Delegate (if needed) | 7-12 | 12 | **LOW** (EX-6 is HIGH risk. Only Claude fully red-teamed the exception propagation issue.) | NB33 notebook proof. 10,000-casualty fixed-seed comparison. |

## 7c. What the Engineer Should Investigate Before Committing

1. **When is HADR actually commissioned?** If <6 weeks, start Plugin Protocol design in Phase 1 (Gemini's urgency). If >3 months, defer to Phase 2 (Claude's caution).

2. **Is the PFC hold loop truly 140 LOC of irreducible complexity?** All three LLMs treat this as the hardest extraction. Before Phase 3, build NB33 to prove or disprove whether `yield from` delegation works correctly with the nested `with resource.request()` blocks.

3. **What is the actual Monte Carlo memory budget?** All three flag EventStore OOM but none quantify the threshold. Run a 1,000-replication benchmark on the current engine to establish the baseline before adding analytics subscribers.

4. **Does the sync-plugin contract hold for EP-7 consumables?** Gemini flagged that consumable tracking may need to "pause" the simulation (violating sync-only plugins). Investigate whether consumables can be modelled as EventBus subscribers (Pattern E) rather than inline yield-bearing operations.

5. **Is `yield from` exception propagation actually safe with SimPy Resource `with` blocks?** Claude flagged this as a theoretical risk. Write a minimal reproduction test before committing to Phase 3's EX-5/EX-6 extractions.

---

# 8. ONE-PAGE DECISION BRIEF

## FAER Engine Architecture: Decision Brief

**Prepared for:** Ross (Technical Decision-Maker / Solo Developer)
**Date:** 16 March 2026
**Status:** GO with Phase 1. CONDITIONAL GO for Phase 2.

### Architecture Choice

**"Tidy, Decouple, Then Plug"** — a three-phase hybrid consolidating the strongest findings from independent analyses by Claude, Gemini, and ChatGPT.

Phase 1 extracts pure functions and decouples analytics (Pattern A+E). Phase 2 promotes extractions into sync-only Plugin Protocols for FAER family divergence (Pattern B). Phase 3 optionally delegates yield-bearing generators via `yield from` (Pattern D). All phases use toggle-gated strangler migration with fixed-seed regression.

### Why This Architecture

Three independent architectural analyses converged on the same core finding: the FAER engine's 1,309 LOC monolith contains 624 LOC of extractable pure logic that can be safely removed without touching any SimPy yield point. This is the highest-confidence, lowest-risk starting point. The phased approach satisfies the solo-developer velocity constraint (12 iterations in 2 weeks) while structurally preparing for variant divergence — Phase 1 function signatures become Phase 2 Plugin Protocol shapes, so no work is discarded.

### Timeline

| Phase | Weeks | What Ships | Risk |
|---|---|---|---|
| 1: Tidy + Decouple | 1-2 | EX-1/2/3 extracted. Analytics on EventBus. engine.py 1,309→~800 LOC. K-3, K-7 resolved. | LOW |
| 2: Plug | 3-6 | Plugin Protocols. Military + HADR plugins. EX-5. engine.py→~650 LOC. K-2, K-4 resolved. | MEDIUM |
| 3: Delegate | 7-12 | EX-6 hold/PFC extraction. engine.py→~500 LOC. | HIGH (conditional) |

### Top 3 Risks

1. **Plugin Protocol design is premature** if HADR requirements aren't concrete. *Mitigation:* Phase 1 signatures are the prototypes. Protocols wrap them mechanically (~50 LOC each).

2. **EX-6 hold/PFC extraction breaks timing** due to nested generator exception propagation. *Mitigation:* Gate Phase 3 on NB33 notebook proof with 10,000-casualty fixed-seed comparison. Don't merge if any casualty diverges.

3. **Migration stalls in half-modernised state** (ChatGPT's meta-risk). *Mitigation:* Define Phase 1 success as "K-3 closed, K-7 closed, NB32 passes, analytics decoupled." Define Phase 2 success as "HADR variant runs NB32 acceptance test." Operational gates, not aesthetic ones.

### Go/No-Go Criteria

| Criterion | Verified? |
|---|---|
| EC-1: Phase 1 ships in ≤2 weeks (12 iterations × 50-100 LOC) | ✓ All 3 LLMs confirm |
| EC-2: All 5 yield points accounted for with module owners | ✓ Traced in pseudocode |
| EC-3: ≥2 of 3 LLMs converge on top approach | ✓ All 3 agree on D+E Phase 1; Claude+Gemini agree on plugins Phase 2 |
| EC-4: HC-1 through HC-10 satisfied | ✓ Checked per constraint |
| EC-5: Debt items K-1 to K-8 mapped | ✓ Resolved vs inherited per phase |
| EC-6: LOC estimate ≤4,508 (current kernel) | ✓ Steady-state ~4,200-4,400 |
| EC-7: NB32 acceptance test fully traced | ✓ Claude Phases 1+2 traces |

**DECISION: GO.** Begin Phase 1 Monday. First extraction: EX-1 (routing.py, ~70 LOC, ~210 LOC with MC-1 multiplier). Toggle: `use_extracted_routing`. Validate with NB32 on fixed seed before proceeding to EX-2.
