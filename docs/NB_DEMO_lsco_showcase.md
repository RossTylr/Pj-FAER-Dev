# NB-DEMO: LSCO Scenario Showcase
## Claude Code Instruction File

---

## Objective

Build a single compelling demo notebook that showcases the FAER-MIL engine's
full capability: realistic LSCO scenario, contested evacuation, Monte Carlo
with confidence intervals, and survivability analysis. This is the portfolio
piece — not a test notebook but a DEMONSTRATION.

## Why This Exists

The DSE honest assessment concluded: "FAER-MIL is closer to delivered than
you think — what it needs now is a compelling demonstration, not six more
weeks of internal reorganisation." This notebook IS that demonstration.

## Scenario: Operation IRON BRIDGE

A realistic LSCO forward medical evacuation scenario:

- **Topology:** 5-node chain: POI-FRONT → CCP → R1-FORWARD → R2-MAIN → R3-REAR
- **Contested links:** POI→CCP (30% denial, active contact zone), CCP→R1 (15% denial)
- **Capacity constraints:** CCP capacity=2, R1 capacity=4, R2 capacity=8
- **Arrivals:** Poisson λ=3/hour baseline, MASCAL burst at T=60 (15 casualties)
- **Duration:** 480 minutes (8-hour operational window)
- **Monte Carlo:** 100 replications for confidence intervals

## Notebook Structure

### Section 1: Scenario Definition (narrative + config)
```python
"""
# Operation IRON BRIDGE: LSCO Forward Medical Evacuation

British mechanised infantry brigade in contact. Forward POI receiving
casualties from a 3km engagement zone. Contested CASEVAC route through
CCP to Role 1 (Regimental Aid Post). Role 2 (Field Hospital) is 45min
MCAT from R1. Role 3 rear for definitive care.

Key challenges:
- Active contact zone: 30% route denial POI→CCP
- Capacity-constrained CCP (2 holding spaces)
- MASCAL event at T+60: IED strike on dismounted patrol (15 casualties)
- PFC risk: casualties held at CCP when R1 saturated
"""
```

### Section 2: Single Run Visualisation
- Event timeline (swimlane by casualty)
- Facility occupancy over time
- Triage distribution
- PFC episodes highlighted
- Route denials marked

### Section 3: Survivability Analysis
- P(survival) by triage category
- Golden hour compliance rate
- Time-to-treatment distribution
- PFC impact on outcomes

### Section 4: Monte Carlo Ensemble
- 100 replications with different seeds
- Mean survivability with 95% CI
- Worst-case scenario identification
- Sensitivity: what if R1 capacity = 2 vs 4 vs 8?

### Section 5: Key Findings Summary
- Narrative: "Under these conditions, T1 casualties have a X% survival rate..."
- Policy implication: "CCP capacity is the binding constraint..."
- Operational recommendation: "Pre-positioning a second surgical team at R1..."

## Technical Requirements

- Uses the Phase 1 engine (analytics decoupled, typed events)
- All visualisations use plotly for interactivity
- Runs in < 5 minutes for the full 100-replication Monte Carlo
- Colab-compatible (no local-only dependencies)

## This Is NOT a Test Notebook

This notebook does not compare old vs new paths, check toggles, or verify
regressions. It USES the engine to produce operational analysis. It's what
a Defence stakeholder would see. It's what Faculty AI would evaluate.
