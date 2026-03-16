"""Page 4: Monte Carlo Ensemble.

Run N replications with different seeds, compute confidence intervals.
Demonstrates EP-4 (batch/Monte Carlo) capability.
"""
import streamlit as st
import numpy as np
import plotly.express as px
import pandas as pd

from faer_dev.config.builder import build_engine_from_dict
from faer_dev.decisions.mode import SimulationToggles
from faer_dev.analytics.engine import AnalyticsEngine
from faer_dev.analytics.views import OutcomeView, GoldenHourView

PHASE1_TOGGLES = SimulationToggles(
    enable_extracted_routing=True,
    enable_extracted_metrics=True,
    enable_typed_emitter=True,
    enable_extracted_pfc=True,
)

st.header("Monte Carlo Ensemble Analysis")

if "scenario_config" not in st.session_state:
    st.warning("Configure a scenario first.")
    st.stop()

config = st.session_state["scenario_config"]

def _build_scenario_dict(cfg):
    topo = cfg["topology"]
    facilities = []
    edges = []
    for i, node in enumerate(topo):
        facilities.append({
            "id": node["id"], "name": node["id"],
            "role": node["role"], "beds": node["capacity"],
        })
        if i < len(topo) - 1:
            next_node = topo[i + 1]
            edges.append({
                "from": node["id"], "to": next_node["id"],
                "travel_time_minutes": node["travel_time"], "transport": "ground",
            })
    return {
        "operational_context": "COIN", "seed": cfg["seed"],
        "facilities": facilities, "edges": edges,
        "arrivals": {
            "base_rate_per_hour": cfg["arrival_rate"],
            "mascal_enabled": cfg.get("mascal_enabled", False),
        },
    }


st.subheader("Ensemble Configuration")
col1, col2 = st.columns(2)
with col1:
    n_replications = st.number_input("Number of replications", 10, 1000, 100)
    base_seed = st.number_input("Base seed", 0, 99999, config["seed"])
with col2:
    ci_level = st.selectbox("Confidence interval", [0.90, 0.95, 0.99], index=1)

if st.button("Run Ensemble", type="primary"):
    progress = st.progress(0, text="Starting ensemble...")

    scenario_dict = _build_scenario_dict(config)
    results = []

    for i in range(n_replications):
        engine = build_engine_from_dict(
            scenario_dict, toggles=PHASE1_TOGGLES, seed=base_seed + i,
        )
        analytics = AnalyticsEngine(engine.event_bus)
        analytics.register_view("outcomes", OutcomeView())
        analytics.register_view("golden_hour", GoldenHourView())

        metrics = engine.run(
            duration=float(config["sim_duration"]),
            max_patients=None,
        )

        outcome_snap = analytics.get_view("outcomes")
        golden_snap = analytics.get_view("golden_hour")

        results.append({
            "seed": base_seed + i,
            "total_arrivals": metrics["total_arrivals"],
            "completed": metrics["completed"],
            "dispositions": outcome_snap["total_dispositions"],
            "golden_hour_mean": golden_snap["mean_minutes"],
            "golden_hour_pct60": golden_snap["pct_within_60"],
        })

        progress.progress((i + 1) / n_replications,
                          text=f"Replication {i+1}/{n_replications}")

    st.success(f"Ensemble complete: {n_replications} replications.")

    df = pd.DataFrame(results)

    # --- Summary Metrics ---
    st.subheader("Ensemble Results")
    alpha = 1 - ci_level
    completions = df["completed"].values
    mean_completed = np.mean(completions)
    ci_lo = np.percentile(completions, 100 * alpha / 2)
    ci_hi = np.percentile(completions, 100 * (1 - alpha / 2))

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Mean Completed", f"{mean_completed:.1f}",
                  help=f"{ci_level*100:.0f}% CI: [{ci_lo:.1f}, {ci_hi:.1f}]")
    with col2:
        worst = df.loc[df["completed"].idxmin()]
        st.metric("Worst-Case Run", f"Seed {worst['seed']:.0f}",
                  help=f"Completed: {worst['completed']}")
    with col3:
        best = df.loc[df["completed"].idxmax()]
        st.metric("Best-Case Run", f"Seed {best['seed']:.0f}",
                  help=f"Completed: {best['completed']}")

    st.divider()

    # --- Distribution Chart ---
    st.subheader("Completed Casualties Distribution")
    fig = px.histogram(df, x="completed", nbins=20,
                       labels={"completed": "Completed Casualties"},
                       color_discrete_sequence=["#3b82f6"])
    fig.add_vline(x=mean_completed, line_dash="dash", line_color="red",
                  annotation_text=f"Mean: {mean_completed:.1f}")
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)

    # --- Golden Hour Distribution ---
    st.subheader("Golden Hour Compliance Across Replications")
    fig2 = px.histogram(df, x="golden_hour_pct60", nbins=20,
                        labels={"golden_hour_pct60": "% Within 60 min"},
                        color_discrete_sequence=["#10b981"])
    fig2.update_layout(height=300)
    st.plotly_chart(fig2, use_container_width=True)

    # Store for other pages
    st.session_state["monte_carlo_results"] = df

st.divider()
st.caption("""
**Memory management:** Fresh engine per replication. AnalyticsEngine subscribes
to EventBus, views computed during run, then engine is garbage collected.
Peak memory bounded to single-run footprint.
""")
