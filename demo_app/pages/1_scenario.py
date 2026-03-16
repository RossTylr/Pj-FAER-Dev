"""Page 1: Scenario Configuration.

Configure topology, arrival rates, contested edges, and simulation parameters.
Stores config in st.session_state for use by other pages.
"""
import streamlit as st

st.header("Scenario Configuration")

# --- Topology ---
st.subheader("Evacuation Chain Topology")
st.markdown("Define the treatment chain from Point of Injury to definitive care.")

num_nodes = st.slider("Number of facilities", 3, 7, 4)

topology = []
for i in range(num_nodes):
    with st.expander(f"Facility {i+1}", expanded=(i < 2)):
        col1, col2, col3 = st.columns(3)
        with col1:
            roles = ["POI", "R1", "R2", "R3", "R4"]
            role = st.selectbox(f"Role", roles, index=min(i, len(roles)-1), key=f"role_{i}")
        with col2:
            capacity = st.number_input(f"Bed capacity", 1, 100, [50, 4, 8, 16, 32][min(i, 4)], key=f"cap_{i}")
        with col3:
            fac_id = st.text_input(f"ID", f"{role}-{i+1}", key=f"id_{i}")

        if i < num_nodes - 1:
            st.markdown("**Route to next facility:**")
            c1, c2, c3 = st.columns(3)
            with c1:
                travel_time = st.number_input("Travel time (min)", 5, 120, [30, 20, 45, 60, 90][min(i, 4)], key=f"tt_{i}")
            with c2:
                contested = st.checkbox("Contested route", value=(i == 0), key=f"con_{i}")
            with c3:
                denial_prob = st.slider("Denial probability", 0.0, 1.0, 0.2 if contested else 0.0, key=f"dp_{i}")

        topology.append({
            "id": fac_id, "role": role, "capacity": capacity,
            "travel_time": travel_time if i < num_nodes - 1 else 0,
            "contested": contested if i < num_nodes - 1 else False,
            "denial_prob": denial_prob if i < num_nodes - 1 else 0.0,
        })

# --- Arrivals ---
st.subheader("Casualty Arrival Configuration")
col1, col2 = st.columns(2)
with col1:
    arrival_rate = st.number_input("Base arrival rate (per hour)", 0.5, 20.0, 3.0)
    sim_duration = st.number_input("Simulation duration (minutes)", 60, 1440, 480)
with col2:
    mascal_enabled = st.checkbox("Enable MASCAL burst", True)
    if mascal_enabled:
        mascal_time = st.number_input("MASCAL onset (minutes)", 0, sim_duration, 60)
        mascal_size = st.number_input("MASCAL cluster size", 5, 50, 15)

# --- Seed ---
st.subheader("Reproducibility")
seed = st.number_input("Random seed", 0, 99999, 42)

# Store in session state
st.session_state["scenario_config"] = {
    "topology": topology,
    "arrival_rate": arrival_rate,
    "sim_duration": sim_duration,
    "mascal_enabled": mascal_enabled,
    "mascal_time": mascal_time if mascal_enabled else None,
    "mascal_size": mascal_size if mascal_enabled else None,
    "seed": seed,
}

st.success("Configuration saved. Navigate to **Run Simulation** to execute.")
