"""Page 3: Analytics Dashboard.

Reads materialised views from AnalyticsEngine (Pattern E).
Never touches engine state directly — all data via get_view().
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from collections import Counter

st.header("Analytics Dashboard")

has_data = "analytics" in st.session_state and "engine_metrics" in st.session_state

if not has_data:
    st.warning("Run a simulation first on the **Run Simulation** page.")
    st.stop()

analytics = st.session_state["analytics"]
metrics = st.session_state["engine_metrics"]
events = st.session_state.get("events", [])

outcome_snap = analytics.get_view("outcomes")
facility_snap = analytics.get_view("facility_load")
golden_snap = analytics.get_view("golden_hour")

# --- Metrics Row ---
st.subheader("Key Metrics")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Casualties", metrics["total_arrivals"])
with col2:
    st.metric("Completed", metrics["completed"])
with col3:
    gh_pct = golden_snap.get("pct_within_60", 0.0)
    st.metric("Golden Hour Compliance", f"{gh_pct:.0%}")
with col4:
    denials = sum(1 for e in events if e.get("type") == "ROUTE_DENIED")
    st.metric("Route Denials", denials)

st.divider()

# --- Triage Distribution ---
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Triage Distribution")
    triage_events = [e for e in events if e.get("type") == "TRIAGE"]
    if triage_events:
        triage_counts = Counter(e.get("details", {}).get("category", "?") for e in triage_events)
        df_triage = pd.DataFrame(
            {"Triage": list(triage_counts.keys()), "Count": list(triage_counts.values())}
        )
        fig = px.bar(df_triage, x="Triage", y="Count", color="Triage",
                     color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_layout(showlegend=False, height=300)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No triage events recorded.")

with col_right:
    st.subheader("Outcome Distribution")
    outcomes = outcome_snap.get("outcomes", {})
    if outcomes:
        df_out = pd.DataFrame(
            {"Outcome": list(outcomes.keys()), "Count": list(outcomes.values())}
        )
        fig = px.pie(df_out, names="Outcome", values="Count",
                     color_discrete_sequence=px.colors.qualitative.Pastel)
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No outcome data.")

st.divider()

# --- Facility Load ---
st.subheader("Facility Load Summary")
if facility_snap:
    fac_data = []
    for fac_id, data in facility_snap.items():
        fac_data.append({
            "Facility": fac_id,
            "Current": data["current"],
            "Peak": data["peak"],
            "Total Arrivals": data["total_arrivals"],
        })
    df_fac = pd.DataFrame(fac_data)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Peak", x=df_fac["Facility"], y=df_fac["Peak"],
                         marker_color="#ef4444"))
    fig.add_trace(go.Bar(name="Current", x=df_fac["Facility"], y=df_fac["Current"],
                         marker_color="#3b82f6"))
    fig.update_layout(barmode="group", height=300, yaxis_title="Occupancy")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No facility load data.")

st.divider()

# --- Golden Hour ---
st.subheader("Time to Disposition")
if golden_snap["total_tracked"] > 0:
    col_g1, col_g2, col_g3 = st.columns(3)
    with col_g1:
        st.metric("Mean", f"{golden_snap['mean_minutes']:.1f} min")
    with col_g2:
        st.metric("Median", f"{golden_snap['median_minutes']:.1f} min")
    with col_g3:
        st.metric("Within 60 min", f"{golden_snap['pct_within_60']:.0%}")
else:
    st.info("No golden hour data tracked.")

st.divider()

# --- PFC Episodes ---
st.subheader("Prolonged Field Care Episodes")
pfc_events = [e for e in events if e.get("type") in ("PFC_START", "HOLD_START", "HOLD_TIMEOUT")]
if pfc_events:
    pfc_data = []
    for e in pfc_events:
        pfc_data.append({
            "Time": e.get("time", 0.0),
            "Type": e.get("type"),
            "Patient": e.get("patient_id", ""),
            "Facility": e.get("facility", ""),
        })
    st.dataframe(pd.DataFrame(pfc_data), use_container_width=True)
else:
    st.info("No PFC events in this run.")

st.divider()

st.caption("""
**Data source:** All metrics from `AnalyticsEngine.get_view()` —
EventBus subscribers (Pattern E). Dashboard never reads engine state directly.
""")
