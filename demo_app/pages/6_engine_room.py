"""Page 6: FAER Engine Room — Architecture X-Ray.

Time-slider driven visualisation of the simulation engine's inner workings.
All panels are pure functions of (event_log, T). Streamlit reruns naturally
on slider change — no animation loops, no time.sleep in the render path.

Presets load real YAML topologies via build_engine_from_preset.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import _path_setup  # noqa: F401, E402

import streamlit as st
from _engine_runner import run_engine, run_engine_preset
from components.state_helpers import (
    compute_state_at_T,
    get_last_triage_context,
    compute_analytics_at_T,
    compute_contention_at_T,
)
from components.bottleneck import render_bottleneck_alert
from components.network_panel import render_network
from components.timeline_panel import render_timeline, detect_mascal_windows
from components.xray_panel import render_xray
from components.facility_panel import render_facility_performance
from components.event_rate import render_event_rate
from components.journey_heatmap import render_journey_heatmap
from components.journey_waterfall import render_journey_waterfall
from components.survivability_curve import render_survivability_curve
from components.paradigm_pie import render_paradigm_pie

# ---------------------------------------------------------------------------
# Presets: name -> (preset_key, duration_minutes)
# ---------------------------------------------------------------------------
SCENARIO_MAP = {
    "COIN — 4-node counter-insurgency, 72hr": ("coin", 4320.0),
    "IRON BRIDGE — 5-node LSCO, 48hr": ("iron_bridge", 2880.0),
}


def _build_custom_scenario() -> tuple[dict, float] | tuple[None, None]:
    """Convert Page 1 scenario_config to a builder-compatible dict."""
    if "scenario_config" not in st.session_state:
        return None, None
    config = st.session_state["scenario_config"]
    topo = config["topology"]
    facilities = []
    edges = []
    for i, node in enumerate(topo):
        facilities.append({
            "id": node["id"], "name": node["id"],
            "role": node["role"], "beds": node["capacity"],
        })
        if i < len(topo) - 1:
            edges.append({
                "from": node["id"], "to": topo[i + 1]["id"],
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
    }, float(config["sim_duration"])


# ---------------------------------------------------------------------------
# Sidebar — 4 clearly separated sections
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Engine Room")

    # --- Scenario ---
    st.subheader("Scenario")
    scenario_name = st.radio(
        "Select scenario",
        list(SCENARIO_MAP.keys()) + ["Custom"],
        label_visibility="collapsed",
    )
    if scenario_name == "Custom" and "scenario_config" not in st.session_state:
        st.warning("Configure a scenario on the Scenario page first.")

    st.divider()

    # --- View Mode ---
    st.subheader("View mode")
    view_mode = st.radio(
        "Select view",
        ["X-Ray — full architecture visibility",
         "Operations — clean output only"],
        label_visibility="collapsed",
    )
    is_xray = "X-Ray" in view_mode

    st.divider()

    # --- Playback ---
    st.subheader("Playback")
    auto_play = st.checkbox("Auto-play")
    if auto_play:
        play_speed = st.slider("Speed (sim-min/frame)", 1.0, 50.0, 10.0, step=1.0)
    else:
        play_speed = 10.0

    st.divider()

    # --- Run ---
    run_btn = st.button("Run Simulation", type="primary", use_container_width=True)

    st.divider()
    st.caption("Paradigm colours:")
    st.markdown("""
    - :blue[Blue] — SimPy DES (yields, timeouts)
    - :orange[Amber] — BehaviorTree (BB writes, ticks)
    - :green[Green] — NetworkX (routing, paths)
    - :violet[Purple] — Events (publish, subscribe)
    """)

# ---------------------------------------------------------------------------
# Run engine
# ---------------------------------------------------------------------------
if run_btn:
    if scenario_name == "Custom":
        sd, dur = _build_custom_scenario()
        if sd is None:
            st.error("Configure a scenario on the Scenario page first.")
            st.stop()
        with st.spinner("Running engine..."):
            metrics = run_engine(sd, seed=sd.get("seed", 42), duration=dur)
    else:
        preset_key, duration = SCENARIO_MAP[scenario_name]
        with st.spinner("Running engine..."):
            metrics = run_engine_preset(preset_key, duration)
    st.toast(
        f"Engine complete: {metrics['total_arrivals']} arrivals, "
        f"{metrics['completed']} completed"
    )

# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------
st.title("FAER Engine Room")

events = st.session_state.get("events", [])
metrics = st.session_state.get("engine_metrics", {})

if not events:
    st.info("No simulation data. Select a scenario and click **Run Simulation** in the sidebar.")
    st.stop()

# ---------------------------------------------------------------------------
# Time slider
# ---------------------------------------------------------------------------
min_time = events[0]["time"]
max_time = events[-1]["time"]
T = st.slider(
    "Simulation time",
    min_value=min_time, max_value=max_time, value=max_time,
    step=1.0, key="er_T",
)

visible_events = [e for e in events if e["time"] <= T]

# Human-readable time
hours = T / 60
days = int(hours // 24)
remaining_hours = hours % 24
st.caption(
    f"T+{hours:.1f}h — Day {days + 1}, "
    f"{int(remaining_hours):02d}:{int((remaining_hours % 1) * 60):02d} — "
    f"{len(visible_events)}/{len(events)} events"
)

# ---------------------------------------------------------------------------
# Metrics strip (4 cards)
# ---------------------------------------------------------------------------
analytics_snap = compute_analytics_at_T(events, T)
contention = compute_contention_at_T(events, T)
col_a1, col_a2, col_a3, col_a4 = st.columns(4)
with col_a1:
    st.metric("Golden Hour", f"{analytics_snap['golden_hour_mean']:.0f} min")
with col_a2:
    st.metric("Peak Load", f"{analytics_snap['peak_load']} @ {analytics_snap['peak_facility']}")
with col_a3:
    st.metric("Completed", f"{analytics_snap['completed']} casualties")
with col_a4:
    st.metric("Waiting", str(contention),
              delta=f"-{contention}" if contention > 5 else None,
              delta_color="inverse")

# Bottleneck alert (both modes)
render_bottleneck_alert(events, T)

# ---------------------------------------------------------------------------
# Focus selector
# ---------------------------------------------------------------------------
topology = st.session_state.get("scenario_dict", {})
all_pids = sorted({e.get("patient_id", "") for e in events if e.get("patient_id")})
all_facs = [f["id"] for f in topology.get("facilities", []) if f.get("beds", 0) > 0]

fc1, fc2 = st.columns([1, 2])
with fc1:
    focus_mode = st.radio("Focus", ["All", "Casualty", "Facility"],
                          horizontal=True, key="er_focus_mode")
with fc2:
    if focus_mode == "Casualty":
        focus_target = st.selectbox("Casualty", all_pids, key="er_focus_cas")
    elif focus_mode == "Facility":
        focus_target = st.selectbox("Facility", all_facs, key="er_focus_fac")
    else:
        focus_target = None

focused_casualty = focus_target if focus_mode == "Casualty" else None
focused_facility = focus_target if focus_mode == "Facility" else None

# ---------------------------------------------------------------------------
# Compute derived state
# ---------------------------------------------------------------------------
state = compute_state_at_T(visible_events, T, topology)
mascal_windows = detect_mascal_windows(events)

# Blackboard context — filtered by focus
if focused_casualty:
    triage_events = [e for e in events if e.get("patient_id") == focused_casualty]
elif focused_facility:
    triage_events = [e for e in events if e.get("facility") == focused_facility]
else:
    triage_events = events
triage_ctx = get_last_triage_context(triage_events, T)

xray_events = (
    [e for e in events if e.get("patient_id") == focused_casualty]
    if focused_casualty else events
)

# ---------------------------------------------------------------------------
# Timeline + Network (side by side)
# ---------------------------------------------------------------------------
col_left, col_right = st.columns([1.2, 1])

with col_left:
    tl_label, tl_group = st.columns([2, 1])
    with tl_label:
        st.subheader("Timeline")
    with tl_group:
        tl_mode = st.radio(
            "Group", ["Facility", "Patient"],
            horizontal=True, key="er_tl_mode", label_visibility="collapsed",
        )

    tl_events = (
        [e for e in events if e.get("facility") == focused_facility]
        if focused_facility else events
    )
    fig_tl = render_timeline(
        tl_events, T, focused_casualty=focused_casualty,
        group_by=tl_mode.lower(), mascal_windows=mascal_windows,
    )
    st.plotly_chart(fig_tl, use_container_width=True)

with col_right:
    st.subheader("Evacuation Chain")
    fig_net = render_network(topology, state, focused_casualty=focused_casualty)
    st.plotly_chart(fig_net, use_container_width=True)

    with st.expander("Last Triage Decision", expanded=False):
        if triage_ctx:
            triage = triage_ctx["triage_category"]
            triage_colours = {
                "T1_SURGICAL": "red", "T1_MEDICAL": "red", "T1": "red",
                "T2": "orange", "T3": "green", "T4": "grey",
            }
            colour = triage_colours.get(triage, "grey")
            st.markdown(f"**{triage_ctx['casualty']}** @ {triage_ctx['facility']}")
            st.markdown(f":{colour}[**{triage}**]")
            st.caption(f"Mechanism: {triage_ctx.get('injury_mechanism', '—')}")
            st.caption(f"Severity: {triage_ctx.get('severity', 0):.2f}")
            st.progress(min(triage_ctx.get("severity", 0), 1.0))
        else:
            st.caption("No triage events yet")

# ---------------------------------------------------------------------------
# Journey analysis (full width)
# ---------------------------------------------------------------------------
if focus_mode == "Casualty" and focused_casualty:
    st.subheader(f"Journey: {focused_casualty}")
    fig_wf = render_journey_waterfall(events, focused_casualty, T)
    if fig_wf:
        st.plotly_chart(fig_wf, use_container_width=True)
    else:
        st.caption("No journey data for this casualty at current T")
else:
    st.subheader("Journey Heatmap")
    fig_jh = render_journey_heatmap(events, T, focused_casualty=focused_casualty)
    st.plotly_chart(fig_jh, use_container_width=True)

# ---------------------------------------------------------------------------
# Facility saturation (full width, both modes)
# ---------------------------------------------------------------------------
st.subheader("Facility Saturation")
fig_fp = render_facility_performance(
    events, T, topology,
    focused_facility=focused_facility,
    focused_casualty=focused_casualty,
)
st.plotly_chart(fig_fp, use_container_width=True)

# ---------------------------------------------------------------------------
# Event rate (compact, both modes)
# ---------------------------------------------------------------------------
fig_er = render_event_rate(events, T, mascal_windows=mascal_windows)
st.plotly_chart(fig_er, use_container_width=True)

# ---------------------------------------------------------------------------
# X-Ray only panels
# ---------------------------------------------------------------------------
if is_xray:
    # Survivability curve
    st.subheader("Survivability")
    fig_sc = render_survivability_curve(events, T, focused_casualty=focused_casualty)
    st.plotly_chart(fig_sc, use_container_width=True)

    # Architecture X-Ray + Paradigm pie side by side
    col_xray, col_pie = st.columns([4, 1])
    with col_xray:
        st.subheader("Architecture X-Ray")
        render_xray(xray_events, T, window=30.0, focused_casualty=focused_casualty)
    with col_pie:
        st.subheader("Paradigm")
        fig_pp = render_paradigm_pie(events, T)
        st.plotly_chart(fig_pp, use_container_width=True)

# ---------------------------------------------------------------------------
# Auto-play
# NOTE: time.sleep blocks the Streamlit server thread. Acceptable for
# single-user local demo. For multi-user, swap to streamlit-autorefresh.
# ---------------------------------------------------------------------------
if auto_play and T < max_time:
    import time as _time
    st.session_state["er_T"] = min(T + play_speed, max_time)
    _time.sleep(0.1)
    st.rerun()
