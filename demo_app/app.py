"""FAER-Dev Demo App: Poly-Hybrid Simulation Engine.

Multi-page Streamlit app demonstrating the FAER-MIL simulation capabilities.
Designed as a portfolio piece showing the engine's full analytical power.

Run: streamlit run demo_app/app.py
"""
import streamlit as st

st.set_page_config(
    page_title="FAER-MIL Simulation",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("FAER-MIL: Field Ambulance Emergency Response")
st.markdown("""
**Poly-hybrid discrete-event simulation** combining SimPy (DES),
Behavior Trees (clinical decisions), and NetworkX (evacuation topology)
to model military medical evacuation under contested conditions.
""")

st.divider()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Engine Kernel", "4,508 LOC", help="16 files, 4 layers")
with col2:
    st.metric("Simulation Paradigms", "3", help="SimPy + BehaviorTrees + NetworkX")
with col3:
    st.metric("Hard Constraints", "10", help="HC-1 to HC-10 verified")

st.divider()

st.subheader("Pages")
st.page_link("pages/1_scenario.py", label="Scenario Configuration", icon="⚙️")
st.page_link("pages/2_simulation.py", label="Run Simulation", icon="▶️")
st.page_link("pages/3_analytics.py", label="Analytics Dashboard", icon="📊")
st.page_link("pages/4_monte_carlo.py", label="Monte Carlo Ensemble", icon="🎲")
st.page_link("pages/5_architecture.py", label="Architecture Explorer", icon="🏗️")
st.page_link("pages/6_engine_room.py", label="Engine Room (X-Ray)", icon="🔬")
st.page_link("pages/6_engine_room.py", label="Engine Room (X-Ray)", icon="🔬")

st.divider()
st.caption("Built with RAIE v3 engineering discipline. DSE-validated architecture.")
