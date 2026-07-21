# ROUTING SEMANTICS — the DP-4 doctrine ruling (FAER-MIL Step-3 gate)
### v3 — RULINGS ENTERED (exploration session, Jul 2026). Extracts filled, rulings drafted, §7 pre-filled — awaiting date/initials. When signed, return this file to the FAER-MIL planning chat (or commit to docs/MVP/ and say so) — BUILD_S3 is authored against it in one pass.

*Provenance of this pass: doctrine consulted was AJMedP-2 Allied Joint Doctrine for Medical Evacuation (STANAG 2546, Ed A V1, Aug 2018 — the MEDEVAC subordinate of AJP-4.10, and the closest thing NATO has to a rulebook for exactly these three questions) and AJP-4.10 Allied Joint Doctrine for Medical Support (STANAG 2228, Ed C V1, Sep 2019), both read from the NATO MILMED COE public STANAG library. US national doctrine (FM 4-02 lineage) located via secondary citation only — verify edition/paragraph at lift. Chacksfield (2025) and JTS CPG material used strictly as EVIDENCE, flagged. Extract slots below carry paragraph refs plus a key phrase; per verbatim-lift discipline, lift the full cited paragraphs from the source PDFs at commit time rather than trusting a transcription.*

---

## 1. Context (all you need)

FAER-MIL is a discrete-event simulation of military medical evacuation: casualties are generated at points of injury (POI), triaged, transported by finite vehicle fleets across a timed network of medical facilities (Role 1 → Role 2 → Role 3), treated at facilities with beds and capability flags (surgery, blood, imaging), and dispositioned. Its purpose is paired doctrine comparison — e.g. "+4 beds at Role 1 → +N% golden-hour compliance under contested conditions."

Step 3 makes the model geographically plural (multiple POIs) and doctrinally faithful in how casualties MOVE. Before it can be built, one decision must be made from doctrine rather than engineering preference — and the repository contains no doctrine source (grep-confirmed: zero hits for "Casualty Care Pathway" or "Stabilisation Point"). That decision is this file.

**The decision in one line:** what does a route mean — a sequence of treat-stops, or transit between designated treat-points — and what may change it mid-journey?

## 2. How to work this file in a separate session

- Explore the FP-IRTB corpus (Casualty Care Pathway, Stabilisation Points, bypass criteria) and any allied doctrine to hand — e.g. AJP-4.10 medical support, JSP 950, 10-1-2 planning timelines, DCR/DCS doctrine, LSCO stabilisation-point literature. Chacksfield (2025) prolonged hold and Kotwal/Howard golden-hour work are EVIDENCE, not doctrine — usable for D-B thresholds, flagged as such.
- Quote verbatim with source + paragraph refs into the ⟨EXTRACT⟩ slots. Short quotes suffice; the ruling matters more than the volume.
- "Doctrine is silent" is a legitimate finding — record it, and the ruling becomes an SME judgement (yours), minuted as such.
- Mixed answers are allowed and expected — e.g. D-A may differ by echelon (pass a Role 1, never pass a Role 2) or by platform (ground vs rotary).
- Do NOT redesign the engine in that session. The engineering consequences are pre-mapped in §5; the separate session's job is doctrine only.

## 3. The three questions

### D-A — Does every echelon visited treat?
Can a vehicle carrying a casualty pass a Role 1 / stabilisation point WITHOUT unloading and treating — or does arrival at a medical node imply care? Sub-prompts: does doctrine distinguish "staging/waypoint" presence from clinical reception? Do stabilisation points mandate assessment on arrival? Does the answer differ by echelon or platform?

⟨EXTRACTS:⟩
1. **[DOCTRINE] AJMedP-2 §0104.4 (Medical Emergency Response).** The continuum of care is a medical organisational pattern, "not a linear pathway that has to be followed in a sequence". One or more emergency-response capabilities may be bypassed on three named grounds: the patient's needs; the availability, capacity and workload of MTFs; the capacity and capability of MEDEVAC assets. *This paragraph answers D-A directly and supplies D-C's inputs. Lift in full.*
2. **[DOCTRINE] AJMedP-2 §0104.3 and §0104.3.a.** Underlying principle: every patient to the most appropriate MTF as quickly as possible, on clinical imperatives first, tempered by the operational environment, which may necessitate direct transport to a higher level of care. Forward MEDEVAC goes to the most appropriate level of care — expressly *not necessarily the closest MTF* — within the 10-1-2 timelines.
3. **[DOCTRINE] AJMedP-2 §0101.3 — the continuity floor.** At no point in the evacuation chain may the level of care fall below that received at the previous MTF. (A recorded US reservation notes emergent evacuations may require dispersion to any MTF with capacity — footnote it.) This is the doctrinal *condition* on passing: a node may be passed only where the platform sustains the care level already achieved.
4. **[DOCTRINE] AJP-4.10 §2.47.b and §2.49 fn53.** Casualty staging units hold, prepare and transfer already-stabilised patients; casualty collection points collect and hand over. Presence-without-treatment node types exist in doctrine — physical arrival is not clinical reception. §2.43: triage is intrinsic to Role 1 — so clinical *reception* does imply assessment.
5. **[DOCTRINE — US national, secondary-sourced] FM 4-02 lineage.** As a general rule no role of care is bypassed except on grounds of "medical urgency, efficiency, or expediency" — a sequential default with grounds-based, case-adjudicated deviation. Verify exact edition/paragraph at lift.
6. **[SILENT / CORPUS] Stabilisation points.** Absent from AJP-4.10 / AJMedP-2 vocabulary (nearest analogues: R2F, CCP). FAER/SP/001/2026 treats reception at a stab point as triggering assessment — basis is corpus + SME, minuted as such.
7. **[EVIDENCE — flagged] Chacksfield (2025).** Stop value is intervention-relative: a stop that delivers a needed intervention buys survival; a stop that delivers nothing is delay plus exposure. Informs the conditional guard's *parameters* later, not this ruling.

**Ruling D-A: nodes-may-be-passed.** Arrival ≠ clinical reception; passing is conditional on the §0101.3 continuity floor (the platform must sustain the care level already achieved); clinical reception implies triage/assessment. The distinction doctrine actually draws is platform-capability-relative, not echelon-relative — no per-echelon "never pass" rule was found. Basis: doctrine (AJMedP-2 §0104.4, §0104.3/.3a, §0101.3; AJP-4.10 §2.47.b, §2.49 fn53, §2.43; FM 4-02 grounds triad); stab-point reception detail corpus/SME.

### D-B — What does deterioration re-open?
When a casualty's condition changes en route or while held awaiting a bed (re-triage, promotion to surgical priority), does doctrine DIVERT to the now-appropriate facility, or COMPLETE the committed move and re-plan afterwards? Sub-prompts: what state changes trigger re-evaluation (triage category? specific clinical events?); at what boundaries is re-evaluation permitted (any time / at holds / at leg boundaries); who authorises a divert?

⟨EXTRACTS:⟩
1. **[DOCTRINE] AJP-4.10 §1.86.a.** "'Clinical need' is the principal factor governing the priority, timing and means" of medical care and patient evacuation. Clinical need is the casualty's *current* state — when it changes, the governing input to the destination decision has changed.
2. **[DOCTRINE] AJMedP-2 §0115 (Patient Flow Management).** An *active, dynamic* process of directing and coordinating patient transfer from wounding through the continuum, explicitly weighing (e) the location, number and clinical condition of patients and (f) the current tactical situation and movement threats. §0111: the PECC coordinates flow and bed assignment continuously, 24/7.
3. **[DOCTRINE] AJMedP-2 §0112.7.c.** MEDEVAC communications exist expressly to permit precise tasking and *re-tasking* of assets. Re-decision is designed-in machinery, not an exception path. §0114.1: en-route treatment decisions are clinical decisions; T-classification governs forward, P-classification tactical/strategic.
4. **[DOCTRINE] AJP-4.10 §3.22–3.23.** Where clinical timelines cannot be met, the commander formally takes them *at risk* — recorded, mitigated, regularly reviewed. The movement consequence of a clinical state sits with command risk-holding, above the clinical assessment itself.
5. **[SILENT].** No NATO doctrine located that *mandates* divert on en-route deterioration, or that fixes triggers or permitted boundaries. The machinery and the permission are doctrinal; the mandate is absent. Triggers and boundaries below are therefore SME judgement, minuted.
6. **[EVIDENCE — flagged].** JTS CPG (en-route care): deterioration requiring en-route intervention is to be anticipated and mitigated *before departure* — supports the leg boundary as the natural decision point. Chacksfield (2025): movement is threat-gated and prolonged hold is normal — supports hold-retry as a decision point and bounded (not continuous) re-planning. Any detection cadence (15/30/60-min casualty review) is a build-time parameter with an evidence basis (clinical reassessment practice), not doctrine.

**Ruling D-B: divert-on-state-change — permitted and bounded.** Triggers: change of triage category (either direction) or change of surgical requirement. Boundaries: leg boundaries and hold-retry — committed legs complete; no mid-leg divert at Step 3. At each boundary the full destination decision recomputes (both per-journey flags). Authoriser: the regulation layer (PECC-equivalent — in-model, the routing decision layer) on clinical input at handover; the movement consequence remains threat-gateable per §3.22–3.23. Basis: doctrine for machinery and permission (AJP-4.10 §1.86.a; AJMedP-2 §0115, §0111, §0112.7.c, §0114.1); SME for triggers/boundaries (doctrine silent), evidence-flagged support (JTS CPG; Chacksfield).

### D-C — Whose decision is bypass?
Is bypassing an echelon (POI direct to Role 2/3) a per-casualty clinical call, a standing doctrine policy, or an emergent consequence of routing? Does deterioration mid-journey CONFER bypass a casualty didn't have at creation? Sub-prompts: bypass criteria as written (state-based? capability-based?); when re-assessed; whether "surgical requirement" itself implies bypass.

⟨EXTRACTS:⟩
1. **[DOCTRINE] AJMedP-2 §0104.4 — decisive here too.** The three bypass grounds are all *time-varying*: the patient's needs change with clinical state; MTF availability, capacity and workload change with load; asset capacity and capability change with tasking. A bypass status derived from time-varying inputs cannot be a creation-time constant.
2. **[DOCTRINE] AJP-4.10 Fig 1-1 principle 4 and §1.86.a.** Primacy of clinical need: the per-casualty decision is clinical, exercised *within* the commander's standing framework (the evacuation plan, medical laydown and theatre patient evacuation policy, AJMedP-2 §0106 — which governs in-theatre holding, not per-casualty destination).
3. **[DOCTRINE — US national, secondary-sourced] FM 4-02 lineage.** Bypass as a case-adjudicated exception to a sequential default, on named grounds — i.e. a *decision taken about a casualty*, not a property stamped on one.
4. **[SILENT].** No doctrine located that freezes bypass at the point of injury.

**Ruling D-C: mixed — standing framework, per-casualty clinical decision, re-assessed at the D-B boundaries.** Bypass is emergent from capability/need matching at decision time; deterioration CAN confer bypass a casualty lacked at creation (and improvement can withdraw it); "surgical requirement" implies bypass *conditionally* — wherever the intervening node cannot advance the casualty toward the required capability within the timeline, not categorically. Consequence for the recorded finding: the as-built creation-time-only Role-1 bypass is a REAL staleness defect, not by-design — **the zero-cost close is foreclosed by doctrine.** Closure rides the D-B mechanism regardless (bypass joins the recompute set: one mechanism, two flags). An SME may still overrule to the cheap row under §6, but that must be minuted as an explicit doctrine deviation, not a doctrine reading. Basis: doctrine (AJMedP-2 §0104.4, §0106; AJP-4.10 Fig 1-1 pr.4, §1.86.a; FM 4-02 grounds triad).

## 4. As-built facts the ruling lands on (for reference; engine at commit 5a78f82, 163 tests green)

- The journey loop RE-PLANS PER HOP (engine.py:743+, get_next_destination per leg) — no stored path exists; "re-plan" is a decision change, not data-structure surgery.
- Every FACILITY_ARRIVAL currently treats, except the beds=0 POI quasi-pass-through — the only existing no-treat branch, and the natural seed of any waypoint mechanic.
- The hold gate reserves NO slot (count poll) — diverting a held casualty relinquishes nothing; the retry boundary is a free re-decision point.
- Per-journey decisions are computed once: surgical-requirement is recomputed on promotion (fixed); Role-1 bypass is NOT — promotion never confers bypass as-built. D-B/D-C rule both flags with one mechanism.
- Transit randomness is keyed per vehicle-mode mission stream (accepted at 3/200 pairing leakage); a divert mechanic that reorders vehicle requests is the trigger to re-measure.
- Multi-POI parses today but silently starves the second POI; an interim guard rides Step 3.

## 5. Decision table — each ruling selects its engineering (pre-mapped; do not re-litigate in the exploring session)

| Ruling | Step-3 mechanism |
|---|---|
| D-A: nodes may be passed | M2 waypoint semantics — FACILITY_ARRIVAL splits into treat-stop vs waypoint (generalising the beds=0 seam). Largest intrinsic touch. |
| D-A: every visited node treats | M1 edge-constraint — inappropriate nodes excluded from routes à la the existing bypass infinite-weight mechanism. Cheapest; the per-hop-treatment characterisation test inverts to ==0. |
| D-B: divert on state change | M3 re-plan triggers at hold-retry and leg boundaries; full decisions recompute (both flags); pairing re-measured post-build. |
| D-B: complete then re-plan | Decisions recompute at the next natural hop only. Smallest change; scope documented. |
| D-C: per-casualty clinical, re-assessed | Bypass joins the M3 recompute set — one mechanism, two flags. |
| D-C: standing policy, creation-time | Bypass stays creation-time; the "staleness" finding is reclassified BY-DESIGN and closed at zero code. |

## 6. Where doctrine is silent — the SME fallback

If any question returns silence: rule it yourself, mark the ruling "SME judgement — doctrine silent", and note the operational rationale in one sentence. A silent-doctrine ruling is revisitable when better sources surface; an unstated assumption is not. Either way the ruling below is what governs the build.

*Applied in this pass: D-B triggers and boundaries are SME (doctrine supplies machinery and permission, no mandate); stab-point reception-implies-assessment is corpus + SME. Operational rationale, one sentence each: decision points must coincide with communication/handover points a real chain possesses (leg boundaries, hold retries); a stabilisation point that receives a casualty without assessing them has no function.*

## 7. RATIFICATION BLOCK

D-A ruling: **nodes-may-be-passed** (arrival ≠ clinical reception; conditional on the §0101.3 continuity floor; platform-capability-relative, not echelon-relative) · basis: AJMedP-2 §0104.4, §0104.3/.3a, §0101.3; AJP-4.10 §2.47.b, §2.49 fn53, §2.43; FM 4-02 grounds triad (verify at lift); stab-point detail corpus/SME
D-B ruling: **divert-on-state-change, permitted and bounded** · triggers/boundaries: triage-category or surgical-requirement change; at leg boundaries and hold-retry only (committed legs complete); full recompute of both flags; authoriser = regulation layer, threat-gateable · basis: AJP-4.10 §1.86.a, §3.22–3.23; AJMedP-2 §0115, §0111, §0112.7.c, §0114.1; triggers/boundaries SME — doctrine silent; JTS CPG + Chacksfield as flagged evidence
D-C ruling: **mixed — standing framework, per-casualty clinical, re-assessed at D-B boundaries; deterioration confers bypass** · staleness finding = real defect, zero-cost close foreclosed · basis: AJMedP-2 §0104.4, §0106; AJP-4.10 Fig 1-1 pr.4, §1.86.a; FM 4-02 grounds triad
Mechanisms selected (auto from §5): **M2 + M3 (both flags recompute)** · riders from §4: pairing-leakage re-measure is armed (divert reorders vehicle requests); beds=0 seam generalises under M2; multi-POI interim guard unaffected
Date / initials: 21 July 2026 / RT

## 8. Return path

Signed block → back to the FAER-MIL planning chat (or committed to docs/MVP/ROUTING_SEMANTICS_NOTE.md with a one-line say-so). BUILD_S3 is then authored in one pass against this file as authority; the human Rule-3 gate follows; the build fires. This is the last item on the programme's critical path that requires a human ruling.
