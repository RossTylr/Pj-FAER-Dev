"""Page 3: Analytics Dashboard.

Reads materialised views from AnalyticsEngine (Pattern E).
Never touches engine state directly — all data via get_view().
"""
import streamlit as st

st.header("Analytics Dashboard")

if "analytics" not in st.session_state:
    st.warning("Run a simulation first on the **Run Simulation** page.")
    st.info("Showing placeholder layout. Wire to AnalyticsEngine after Phase 1.")

# --- Metrics Row ---
st.subheader("Key Metrics")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Casualties", "—", help="From survivability view")
with col2:
    st.metric("Mean P(survival)", "—", help="Across all triage categories")
with col3:
    st.metric("Golden Hour Compliance", "—%", help="% treated within 60min")
with col4:
    st.metric("Route Denials", "—", help="Contested route denial count")

st.divider()

# --- Triage Distribution ---
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Triage Distribution")
    st.info("Bar chart: T1/T2/T3/T4 counts from triage view")
    # TODO: plotly bar chart from analytics.get_view("triage")

with col_right:
    st.subheader("Survivability by Triage")
    st.info("Box plot: P(survival) distribution per triage category")
    # TODO: plotly box from analytics.get_view("survivability")

st.divider()

# --- Facility Load ---
st.subheader("Facility Occupancy Over Time")
st.info("Stacked area chart: concurrent occupancy per facility from facility_load view")
# TODO: plotly area chart from analytics.get_view("facility_load")

st.divider()

# --- Golden Hour ---
st.subheader("Time to First Treatment")
st.info("Histogram: minutes from injury to first treatment, split by triage")
# TODO: plotly histogram from analytics.get_view("golden_hour")

st.divider()

# --- PFC Episodes ---
st.subheader("Prolonged Field Care Episodes")
st.info("Timeline: PFC holds with duration and facility, highlighting capacity bottlenecks")
# TODO: plotly gantt from PFC events

st.divider()

st.caption("""
**Data source:** All metrics from `AnalyticsEngine.get_view()` — 
EventBus subscribers (Pattern E). Dashboard never reads engine state directly.
""")
