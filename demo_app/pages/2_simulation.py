"""Page 2: Run Simulation.

Executes the FAER engine with the configured scenario.
Displays real-time event stream and progress.
"""
import streamlit as st

st.header("Run Simulation")

if "scenario_config" not in st.session_state:
    st.warning("Configure a scenario first on the **Scenario Configuration** page.")
    st.stop()

config = st.session_state["scenario_config"]

st.markdown(f"""
**Scenario:** {len(config['topology'])} facilities, 
seed={config['seed']}, duration={config['sim_duration']}min,
arrival rate={config['arrival_rate']}/hr
""")

if st.button("Run Simulation", type="primary"):
    progress = st.progress(0, text="Initialising engine...")

    # TODO: Wire to actual FAEREngine once Phase 1 extractions are in place
    # For now, scaffold shows the integration pattern:
    #
    # from faer_dev.simulation.engine import FAEREngine
    # from faer_dev.decisions.mode import SimulationToggles
    # from faer_dev.emitter import TypedEmitter
    # from faer_dev.analytics.engine import AnalyticsEngine
    # from faer_dev.analytics.views import GoldenHourView, FacilityLoadView, SurvivabilityView
    #
    # toggles = SimulationToggles(
    #     use_extracted_routing=True,
    #     use_extracted_metrics=True,
    #     use_typed_emitter=True,
    #     use_extracted_pfc=True,
    # )
    # engine = FAEREngine(seed=config["seed"], toggles=toggles)
    # analytics = AnalyticsEngine(engine.log)
    # analytics.register_view("golden_hour", GoldenHourView())
    # analytics.register_view("facility_load", FacilityLoadView())
    # analytics.register_view("survivability", SurvivabilityView())
    #
    # engine.build_network(build_topology(config["topology"]))
    # engine.generate_casualties(n_from_arrival_rate(config))
    # engine.run(until=config["sim_duration"])
    #
    # st.session_state["engine"] = engine
    # st.session_state["analytics"] = analytics
    # st.session_state["events"] = engine.log.events

    import time
    for i in range(100):
        time.sleep(0.02)
        progress.progress(i + 1, text=f"Simulating... {i+1}%")

    st.success("Simulation complete. Navigate to **Analytics Dashboard** for results.")

    # Event stream preview
    st.subheader("Event Stream (last 20)")
    st.info("Event stream will display here once engine is wired.")
    # Example of what it will show:
    st.code("""
T=0.0   ARRIVAL     CAS-001  POI
T=0.0   TRIAGED     CAS-001  POI      T1
T=2.3   ARRIVAL     CAS-002  POI
T=2.3   TRIAGED     CAS-002  POI      T3
T=5.1   TREATED     CAS-001  R1
T=8.7   ROUTE_DENIED CAS-003 POI→CCP  (contested)
...
    """)
