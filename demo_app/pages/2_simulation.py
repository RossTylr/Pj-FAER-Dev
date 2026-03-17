"""Page 2: Run Simulation.

Executes the FAER engine with the configured scenario.
Displays real-time event stream and progress.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import _path_setup  # noqa: F401, E402

import streamlit as st
from _engine_runner import run_engine


def _build_scenario_dict(config):
    """Convert Page 1 flat topology list into builder-compatible dict."""
    topo = config["topology"]
    facilities = []
    edges = []
    for i, node in enumerate(topo):
        facilities.append({
            "id": node["id"],
            "name": node["id"],
            "role": node["role"],
            "beds": node["capacity"],
        })
        if i < len(topo) - 1:
            next_node = topo[i + 1]
            edges.append({
                "from": node["id"],
                "to": next_node["id"],
                "travel_time_minutes": node["travel_time"],
                "transport": "ground",
            })
    return {
        "operational_context": "COIN",
        "seed": config["seed"],
        "facilities": facilities,
        "edges": edges,
        "arrivals": {
            "base_rate_per_hour": config["arrival_rate"],
            "mascal_enabled": config.get("mascal_enabled", False),
        },
    }


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

    scenario_dict = _build_scenario_dict(config)
    progress.progress(20, text="Running simulation...")

    metrics = run_engine(
        scenario_dict,
        seed=config["seed"],
        duration=float(config["sim_duration"]),
    )

    progress.progress(100, text="Complete")

    st.success(
        f"Simulation complete: {metrics['total_arrivals']} arrivals, "
        f"{metrics['completed']} completed, {metrics['in_system']} in system. "
        f"Navigate to **Analytics Dashboard** for results."
    )

    # Event stream preview
    st.subheader("Event Stream (last 20)")
    events = st.session_state.get("events", [])
    if events:
        lines = []
        for e in events[-20:]:
            t = e.get("time", 0.0)
            etype = e.get("type", "?")
            pid = e.get("patient_id", "")
            fac = e.get("facility", "")
            lines.append(f"T={t:>7.1f}  {etype:<20s} {pid or '':<10s} {fac}")
        st.code("\n".join(lines))
    else:
        st.info("No events recorded.")
