# Demo App Build Instructions
## Wire After Phase 1 NB39 Gate Passes

---

## What This App Is

A 5-page Streamlit app demonstrating the FAER-MIL engine's full capability.
It is a portfolio piece for Faculty AI and Defence stakeholders, not an
internal development tool.

## Current State: Scaffolded

All 5 pages exist with layout, placeholder metrics, and TODO comments showing
exactly where to wire the engine. The app runs today (`streamlit run demo_app/app.py`)
and shows the UI structure without live data.

## Wiring Sequence (After Phase 1)

### Step 1: Wire Page 2 (Simulation)

Replace the placeholder progress loop with actual engine execution:

```python
from faer_dev.simulation.engine import FAEREngine
from faer_dev.decisions.mode import SimulationToggles
from faer_dev.emitter import TypedEmitter
from faer_dev.analytics.engine import AnalyticsEngine
from faer_dev.analytics.views import GoldenHourView, FacilityLoadView, SurvivabilityView

toggles = SimulationToggles(
    use_extracted_routing=True,
    use_extracted_metrics=True,
    use_typed_emitter=True,
    use_extracted_pfc=True,
)
engine = FAEREngine(seed=config["seed"], toggles=toggles)
emitter = TypedEmitter(engine.log)
engine.emitter = emitter

analytics = AnalyticsEngine(engine.log)
analytics.register_view("golden_hour", GoldenHourView())
analytics.register_view("facility_load", FacilityLoadView())
analytics.register_view("survivability", SurvivabilityView())

engine.build_network(build_topology_from_config(config["topology"]))
engine.generate_casualties(n_from_arrival_rate(config))
engine.run(until=config["sim_duration"])

st.session_state["engine"] = engine
st.session_state["analytics"] = analytics
```

### Step 2: Wire Page 3 (Analytics Dashboard)

Replace placeholder metrics with:
```python
analytics = st.session_state["analytics"]
gh = analytics.get_view("golden_hour")
fl = analytics.get_view("facility_load")
sv = analytics.get_view("survivability")
```

Build plotly charts from view snapshots.

### Step 3: Wire Page 4 (Monte Carlo)

Implement the ensemble loop with `analytics.reset_all()` between replications.

### Step 4: Wire Page 5 (Architecture)

Replace static data with live introspection of the engine state
(LOC counts, toggle states, extraction status).

## Key Principle

The dashboard reads `AnalyticsEngine.get_view()`, NEVER engine state.
This is the Pattern E boundary that protects the dashboard from engine refactoring.
