# FAER DSE: Lessons Learned & Findings Registry
## Multi-LLM Design Space Exploration — Post-Mortem & Forward Plan

**Date:** 16 March 2026
**Duration:** Single session, ~4 hours active work
**Participants:** Claude (Opus), Gemini (Deep Research), ChatGPT (o3)
**Orchestrator:** Ross (human-in-the-loop at every stage gate)

---

## Part 1: DSE Process Lessons

### L-DSE-1: The Staged Prompt Protocol Works

**Finding:** The four-stage protocol (Quick Scan → Architecture → Red-Team → Score/Synthesise) produced genuinely different outputs at each stage. Quick Scan generated breadth (30 approaches across 3 LLMs). Architecture generated depth (6 detailed proposals with interfaces). Red-Team found structural flaws that Architecture missed. Scoring forced explicit tradeoff articulation.

**Evidence:** Claude's CP-3 compound command issue (S6) was found in Red-Team, not Architecture. ChatGPT's "migration scaffolding ≠ progress" meta-risk appeared in Scoring, not Red-Team. Gemini's plugin CP-3 snapshot timing appeared in Red-Team mitigation, not Architecture design.

**Implication for future DSE runs:** Don't skip stages. Don't collapse Red-Team into Architecture. The adversarial mode produces qualitatively different reasoning than the constructive mode.

---

### L-DSE-2: Context Index + Pseudocode Reference Is the Minimum Viable DSE Input

**Finding:** The two-document input set (Context Index as compressed fact table + Pseudocode Reference as executable patterns) was sufficient for 3 LLMs to independently converge on the same Phase 1 recommendation. Source documents (NB30, NB32, Lessons) were needed for Stage 2a comprehension but could be dropped from context for all subsequent stages without loss of analytical quality.

**Evidence:** All Stage 2b/2c outputs reference Context Index IDs (KF-3, HC-1, CP-3, etc.) accurately. No LLM needed to re-read source documents after Stage 2a.

**Implication:** For future DSE runs on other codebases, invest in building the Context Index upfront. The compression ratio (NB30: 61KB → Context Index: 9.5KB) is ~6:1 with no analytical loss for downstream stages.

---

### L-DSE-3: Convergence Across LLMs Is the Strongest Signal

**Finding:** When all 3 LLMs independently converge on a finding, the confidence is very high. When only 1 LLM proposes something, it's either a blind spot the others missed (high value) or an unsupported speculation (low value). The distinction is whether the claim can be traced to specific Context Index evidence.

**Evidence of convergence value:**
- All 3: "yields must stay centralised" → directly traceable to HC-1, PR-8
- All 3: "Pattern D strangler for migration" → directly traceable to HC-8, MC-4, KL-11
- All 3: "EX-1/2/3 before EX-4/5/6" → directly traceable to validated extraction order
- All 3: "ECS-as-scheduler is dead" → directly traceable to HC-1, PR-1

**Evidence of unique-finding value:**
- Claude only: CP-3 compound command constraint → traceable to baseline pseudocode `with` block
- Claude only: Phase 1 extractions become Phase 2 Protocol prototypes → novel inference, not directly in Index
- ChatGPT only: migration scaffolding ≠ progress → traceable to KL-1, KL-11
- Gemini only: plugin CP-3 snapshot timing → concrete implementation detail not in Index

**Implication:** Weight convergent findings as decisions. Weight unique findings as investigation triggers. Discard proposals that only one LLM made AND cannot trace to Index evidence.

---

### L-DSE-4: LLM Comprehension Quality Varies and Should Be Measured

**Finding:** A structured comprehension gate (5 specific questions with verifiable answers) at Stage 2a entry reveals significant quality differences. Claude demonstrated deepest reading (referenced NB16 stress testing, listed all 6 NB32 layers with LOC counts, connected K-1 to specific EP blockages). Gemini was accurate but surface-level. ChatGPT produced thorough prose but lacked structured verification.

**Implication:** Always include a comprehension gate. Weight subsequent analysis by comprehension precision. An LLM that misses K-1's connection to EP-1/EP-3/EP-6 will produce a less grounded architecture than one that sees it.

---

### L-DSE-5: Red-Team Must Be a Separate Cognitive Mode

**Finding:** Asking an LLM to "propose architecture AND attack it" in the same prompt produces weak attacks. Asking it to ONLY attack (with the architecture already generated) produces materially stronger adversarial reasoning.

**Evidence:** Claude's Stage 2b found 7 critical issues across 6 approaches. The CP-3 compound command issue, the S4 big-bang cutover risk, and the S5/S6 journey-structure rigidity were NOT identified in Stage 2a proposals. They emerged only under explicit adversarial prompting.

**Implication:** Always separate construction from critique. Use maximum reasoning depth for red-teaming. The "ULTRATHINK" cognitive mode instruction correlates with deeper adversarial analysis.

---

### L-DSE-6: Cross-Red-Team Is Where Architecture Debates Get Honest

**Finding:** When approaches attack each other (velocity attacks extensibility, extensibility attacks velocity), the real tradeoffs become explicit. Self-red-team finds technical flaws. Cross-red-team finds strategic flaws.

**Key cross-red-team findings that shaped the final recommendation:**
- S1 (velocity) attacking S5 (extensibility): "You're building infrastructure for a hypothetical future" — forced the deferral decision
- S5 (extensibility) attacking S1 (velocity): "You'll pay the cost later with interest" — forced acknowledgment that EP-1 must eventually be solved
- S2 (incrementalist) attacking S4 (structural): "You can't toggle-gate your way to safety" — identified the big-bang cutover risk
- S4 (structural) attacking S2 (incrementalist): "You've shuffled files, not changed architecture" — forced acknowledgment that strangler is migration strategy, not architecture

**Implication:** Always include cross-red-team. It produces the most decision-relevant findings of any stage.

---

### L-DSE-7: The Pass 3 Synthesis Is Where Bias Cancels

**Finding:** Each LLM has a characteristic bias. Claude is conservative (defer until evidence). Gemini is extensibility-forward (build the plugin platform). ChatGPT is velocity-forward (ship the simplest thing). When synthesised, these biases cancel: the consolidated recommendation is more balanced than any individual output.

**Implication:** Multi-LLM DSE is not about finding the "smartest" LLM. It's about using disagreement productively. The synthesis of three biased analyses is less biased than any one.

---

## Part 2: Architectural Findings

### F-ARCH-1: The Five Yield Points Are the Non-Negotiable Architectural Spine

**Finding:** Every surviving architecture preserves the same 5 yield points in the same logical order:
1. Y1: `yield resource.request()` — treatment capacity acquisition (CP-3)
2. Y2: `yield env.timeout(treatment_duration)` — treatment execution
3. Y3: `yield env.timeout(retry_interval)` — PFC hold/retry loop
4. Y4: `yield vehicle.request()` — transport vehicle acquisition (CP-3)
5. Y5: `yield env.timeout(travel_time)` — transit execution

No surviving architecture moves yields into plugins, subscribers, or external processes. The question is only WHICH MODULE owns the generator containing these yields — not whether yields can be distributed.

**Constraint chain:** HC-1 (SimPy generator) → PR-8 (no naive split) → KF-5 (generator owns yields) → "yields are the spine"

---

### F-ARCH-2: CP-3 Is the Hardest Boundary; CP-2 Is the Easiest

**Finding:** All three LLMs independently ranked the 4 coupling interfaces identically:
- CP-3 (SimPy Resources): HIGHEST cost — 4-8 mutable ops/casualty, shared state, determinism-sensitive
- CP-1 (Blackboard): LOW cost — 16 r/w ops but atomic relative to BT tick, bounded mutability window
- CP-4 (Topology/NetworkX): LOW cost — read-heavy, safe behind protocol
- CP-2 (EventBus): LOWEST cost — immutable publish-only, already decoupled

**Architectural implication:** Start every migration at CP-2 (analytics). End at CP-3 (resources). Never do CP-3 first.

---

### F-ARCH-3: The Y1+Y2 Compound Yield Constraint

**Finding (Claude-unique):** Y1 (resource acquisition) and Y2 (treatment timeout) MUST occur inside a single `with resource.request() as req:` block. Any architecture that separates them into distinct commands, actions, or handler invocations will release the resource between Y1 and Y2, causing incorrect simulation behaviour.

**Evidence:** Baseline pseudocode shows:
```python
with resource.request() as req:
    yield req          # Y1
    yield env.timeout(treatment_time)  # Y2
```
The `with` block ensures resource release happens AFTER Y2, not between Y1 and Y2.

**Implication:** Command bus, action-token, and handler-dispatch architectures must treat Y1+Y2 as an atomic pair. Same applies to Y4+Y5 (vehicle acquisition + travel).

---

### F-ARCH-4: Sync-Only Plugin Discipline Is Non-Negotiable

**Finding:** All surviving plugin/hexagonal architectures enforce the same rule: plugins return synchronous decision objects (dataclasses, enums, Plan objects). Plugins NEVER yield, NEVER import SimPy, NEVER touch CP-3 resources directly.

**Evidence:** Claude and Gemini converged independently. ChatGPT's quick-scan variant allowing transport yield delegation was not carried into any final recommendation.

**Rule:** `TriagePlugin.assign()` returns `None` (writes BB). `RoutingPlugin.select_destination()` returns `RoutingDecision`. `PFCPlugin.evaluate()` returns `HoldDecision`. The engine translates these into yields.

---

### F-ARCH-5: Phase 1 Extractions Become Phase 2 Protocol Shapes

**Finding (Claude-unique):** The pure function signatures created during Phase 1 extraction (e.g., `routing.get_next_destination(casualty, facility, network, rng) → RoutingDecision`) are empirically validated interface shapes. When Phase 2 Plugin Protocols are needed, wrapping these functions is mechanical (~50 LOC/plugin), not architectural redesign.

**Implication:** Phase 1 is not throwaway cleanup. It is protocol discovery. The extraction IS the interface design process, grounded in real implementation rather than speculation. This resolves the KL-1 tension ("specification outran verification") because the specification (Protocol shape) emerges from verified extraction, not from abstract design.

---

### F-ARCH-6: The PFC Hold Loop Is Irreducibly Complex (~80 LOC in Any Architecture)

**Finding:** All three LLMs identified the 140 LOC hold/PFC nested conditional (KF-5, EX-6) as the single hardest extraction target. Even the Functional Core Shell (S4), which maximises purity, retains ~80 LOC of irreducible generator complexity in the shell's PFC section because the pure decision function must be called repeatedly inside a yield-bearing while loop.

**Implication:** No architecture eliminates PFC complexity. The best architectures (S4's pure evaluate_hold(), S5's PFCPlugin.evaluate()) make the DECISION testable without SimPy while accepting that the EXECUTION (the retry loop) requires a generator. EX-6 extraction should be Phase 3, gated on EX-5 success.

---

### F-ARCH-7: EventStore OOM Is Universal at Monte Carlo Scale

**Finding:** At 8-15 events/casualty × 5,000 casualties × 100+ replications, an append-only EventStore grows to ~1.5GB+. All three LLMs flagged this. No proposed architecture solves it structurally.

**Mitigation consensus:**
1. Compute analytics incrementally via MaterialisedView subscribers (Pattern E)
2. Flush EventStore between replications once views have captured needed aggregates
3. Never retain full event histories for Monte Carlo — only for single-run debugging

---

### F-ARCH-8: Replay from T=45 Is a Full Re-Run in Every Surviving Architecture

**Finding:** No Phase 1-2 architecture provides constant-time restart from a mid-simulation point. Deterministic replay (HC-2) means re-running from seed to T=45 and then branching. The Command Bus (S6) offered the best partial replay via command log, but its structural issues (F-ARCH-3) demoted it.

**Implication:** Don't optimise for replay in Phase 1-2. It requires state checkpointing infrastructure that is orthogonal to the core migration. File under Phase 3+.

---

### F-ARCH-9: Journey Structure Rigidity Is a Latent Risk

**Finding:** All plugin and policy architectures make DECISIONS pluggable but leave the EXECUTION ORDER fixed (triage → treat → PFC → route → transport). If FAER-HADR needs a fundamentally different phase order (e.g., triage → transport → treat, no PFC), the engine/orchestrator itself needs modification.

**Implication:** Monitor during Phase 2 HADR development. If HADR requires journey-order changes, the Declarative Journey DSL (Gemini's wildcard) may need to be resurrected as a Phase 3 option.

---

### F-ARCH-10: Migration Scaffolding Can Masquerade as Progress

**Finding (ChatGPT-unique):** Pattern D strangler migration is safe partly because it tolerates duplication and transitional ugliness. But that means it can stall permanently in a half-modernised state with "double rent" on old and new paths.

**Mitigation:** Define Phase 1 success in operational terms:
- K-3 closed (legacy dead code deleted)
- K-7 closed (typed emitter publishes real events)
- NB32 acceptance test passes with all toggles ON
- Analytics decoupled (dashboard reads views, not engine state)

NOT "engine.py is slightly tidier." Operational gates, not aesthetic ones.

---

## Part 3: Technical Findings

### F-TECH-1: `yield from` Exception Propagation Needs Proof

**Finding:** When treatment.py owns Y1+Y2 via `yield from`, and an exception occurs during Y1 inside a `with resource.request()` block, the `__exit__` handler must correctly release the resource. Python's generator protocol handles this — `yield from` propagates `throw()` and `close()` into sub-generators, which triggers `__exit__`.

**Status:** Theoretically safe. NOT empirically proven in the FAER codebase. Must be proven with a minimal reproduction test (proposed NB34) before Phase 3 commits to EX-5/EX-6.

---

### F-TECH-2: Plugin CP-3 Snapshot Must Be Fresh at Invocation Time

**Finding (Gemini-unique):** When the engine calls a sync plugin's `decide()` method, the facility state snapshot passed to the plugin must be constructed at that exact moment — not cached from a previous yield point. SimPy resource queues mutate between yields as other casualties process.

**Implication:** `engine.py` must call something like `snapshot = self._build_facility_snapshot()` immediately before every `plugins.routing.select_destination(casualty, current, network, snapshot)` call.

---

### F-TECH-3: The 11-File Kernel Is Truly Irreducible

**Finding:** NB32 proved a primitive runs with 11 of 16 kernel files. The remaining 5 (engine.py, arrivals.py, casualty_factory.py, transport.py, queues.py) are orchestration infrastructure. Every proposed architecture rewrites orchestration files; none touches the 11-file kernel.

**Implication:** The 11 files are the PLATFORM. The 5 files are the TARGET. Any future architecture work should be framed as "how to reorganise the 5 orchestration files" not "how to redesign the engine."

---

### F-TECH-4: Typed Event Emission (EX-3) Is a Prerequisite for Everything

**Finding:** K-7 (typed event fields empty in production) blocks analytics decoupling, dashboard reliability, and replay correctness. PR-9 explicitly warns: "Analytics on typed fields without verifying emits will read zeros."

**Implication:** EX-3 must complete BEFORE any EventBus subscriber (AnalyticsEngine, ConsumableView, etc.) is trusted. This is why EX-3 is in Phase 1 and analytics wiring follows it, not precedes it.

---

### F-TECH-5: Monte Carlo Memory Budget Is Unknown

**Finding:** All three LLMs flag EventStore OOM as a risk, but none quantify the actual memory threshold for the current engine. The estimate of ~15MB/run × 100 replications = 1.5GB is theoretical.

**Action required:** Run a 1,000-replication benchmark on the CURRENT engine before Phase 1 to establish the baseline memory profile. This determines whether EventStore flushing is Phase 1 urgent or Phase 2 housekeeping.

---

## Part 4: Process Meta-Findings

### F-META-1: The DSE Operator's Manual Works

**Finding:** The staged protocol with explicit cognitive mode instructions, context management (source docs in Stage 2a, dropped in 2b), and exit criteria produced a coherent, verifiable recommendation from three independent analyses in approximately 4 hours of active work. The exit criteria served as a forcing function — every phase was checked against EC-1 through EC-7.

---

### F-META-2: Human-in-the-Loop at Stage Gates Is Essential

**Finding:** The Human Checkpoint between Step 1 (Quick Scan) and Step 2 (Architecture) was where Ross selected the 6 approaches for deep evaluation from 30 candidates. This curation step prevented wasted analysis on killed approaches and ensured diversity in the shortlist. No LLM can substitute for the domain expert's judgment about which approaches deserve depth.

---

### F-META-3: The "Fallback to Pattern D" Escape Hatch Removes Decision Paralysis

**Finding:** Knowing that pure Pattern D (incrementalist, no new architecture) is ALWAYS available and ALWAYS safe removed the pressure to "pick the perfect architecture." The DSE became "what's the BEST architecture we can confidently recommend, with Pattern D as the floor?" rather than "what architecture should we bet the codebase on?"

---

## Part 5: Open Questions for Phase 2 Investigation

| # | Question | Why It Matters | When to Answer |
|---|----------|----------------|----------------|
| OQ-1 | When is HADR actually commissioned? | Determines Phase 2 plugin timing | Before Phase 1 ends |
| OQ-2 | Does HADR need different journey ORDER or just different decisions? | Determines if plugins suffice or DSL is needed | During Phase 2 requirements |
| OQ-3 | Can EP-7 consumables be modelled as EventBus subscribers? | Determines if sync-only plugin contract holds | Phase 2 design |
| OQ-4 | Is `yield from` exception propagation safe with SimPy Resource `with` blocks? | Gates Phase 3 EX-5/EX-6 | NB34 proof notebook |
| OQ-5 | What is the actual Monte Carlo memory budget? | Determines EventStore flush urgency | Pre-Phase 1 benchmark |
