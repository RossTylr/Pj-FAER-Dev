"""Page 6: FAER Engine Room — Architecture X-Ray.

Real-time visualisation of the simulation engine's inner workings.
Shows which paradigm is active, which coupling interfaces are used,
and where the yield points pause the simulation clock.

Controls run the engine directly via preset scenarios or the Page 1 config.
Event replay (step mode) walks through the pre-computed event list.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import _path_setup  # noqa: F401, E402

import streamlit as st
from _engine_runner import run_engine

# ---------------------------------------------------------------------------
# Preset scenario configs (builder-compatible dicts)
# ---------------------------------------------------------------------------
PRESET_NB32 = {
    "operational_context": "COIN",
    "seed": 42,
    "facilities": [
        {"id": "POI-1", "name": "POI-1", "role": "POI", "beds": 50},
        {"id": "R1-1", "name": "R1-1", "role": "R1", "beds": 4},
        {"id": "R2-1", "name": "R2-1", "role": "R2", "beds": 8},
    ],
    "edges": [
        {"from": "POI-1", "to": "R1-1", "travel_time_minutes": 30, "transport": "ground"},
        {"from": "R1-1", "to": "R2-1", "travel_time_minutes": 45, "transport": "ground"},
    ],
    "arrivals": {"base_rate_per_hour": 3.0, "mascal_enabled": False},
}

PRESET_IRON_BRIDGE = {
    "operational_context": "LSCO",
    "seed": 42,
    "facilities": [
        {"id": "POI-FRONT", "name": "Forward Line", "role": "POI", "beds": 0},
        {"id": "R1-ALPHA", "name": "BAS Alpha", "role": "R1", "beds": 8},
        {"id": "R2-FORWARD", "name": "FST Forward", "role": "R2", "beds": 16},
        {"id": "R3-MAIN", "name": "Combat Support Hospital", "role": "R3", "beds": 100},
    ],
    "edges": [
        {"from": "POI-FRONT", "to": "R1-ALPHA", "travel_time_minutes": 15, "transport": "ground"},
        {"from": "R1-ALPHA", "to": "R2-FORWARD", "travel_time_minutes": 25, "transport": "ground"},
        {"from": "R2-FORWARD", "to": "R3-MAIN", "travel_time_minutes": 45, "transport": "ground"},
    ],
    "arrivals": {"base_rate_per_hour": 8.0, "mascal_enabled": True},
}

PRESETS = {
    "NB32 Acceptance (3-node, 24hr)": (PRESET_NB32, 1440.0),
    "IRON BRIDGE (LSCO, 4-node, 48hr)": (PRESET_IRON_BRIDGE, 2880.0),
}


def _get_scenario_dict():
    """Return scenario dict from preset or page 1 config."""
    if scenario_name == "Custom":
        if "scenario_config" not in st.session_state:
            return None, None
        config = st.session_state["scenario_config"]
        # Reuse page 2's builder logic
        from pages import _build_scenario_dict  # noqa: this won't work
        # Inline the conversion instead
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
    else:
        return PRESETS[scenario_name]


# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Engine Room Controls")

    scenario_name = st.radio(
        "Scenario",
        list(PRESETS.keys()) + ["Custom"],
    )

    view_mode = st.radio(
        "View mode",
        ["Engine Room (X-ray)", "Operations (output only)"],
        horizontal=True,
    )

    st.divider()

    run_btn = st.button("Run Simulation", type="primary", use_container_width=True)

    # Step mode: walk through events one at a time
    has_events = bool(st.session_state.get("events"))
    step_col1, step_col2 = st.columns(2)
    with step_col1:
        step_btn = st.button("Step +1", disabled=not has_events, use_container_width=True)
    with step_col2:
        reset_btn = st.button("Reset", disabled=not has_events, use_container_width=True)

    if "er_step_cursor" not in st.session_state:
        st.session_state["er_step_cursor"] = 0

    if reset_btn:
        st.session_state["er_step_cursor"] = 0
    if step_btn:
        max_idx = len(st.session_state.get("events", []))
        st.session_state["er_step_cursor"] = min(
            st.session_state["er_step_cursor"] + 1, max_idx
        )

    st.divider()
    st.caption("Paradigm colours:")
    st.markdown("""
    - :blue[Blue] — SimPy DES (yields, timeouts)
    - :orange[Amber] — BehaviorTree (BB writes, ticks)
    - :green[Green] — NetworkX (routing, paths)
    - :violet[Purple] — Events (publish, subscribe)
    """)

# ---------------------------------------------------------------------------
# Run engine if button pressed
# ---------------------------------------------------------------------------
if run_btn:
    sd, dur = _get_scenario_dict()
    if sd is None:
        st.error("Configure a scenario on Page 1 first, or select a preset.")
        st.stop()
    with st.spinner("Running engine..."):
        metrics = run_engine(sd, seed=sd.get("seed", 42), duration=dur)
    st.session_state["er_step_cursor"] = 0
    st.toast(
        f"Engine complete: {metrics['total_arrivals']} arrivals, "
        f"{metrics['completed']} completed"
    )

# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------
st.title("FAER Engine Room")

events = st.session_state.get("events", [])
analytics = st.session_state.get("analytics")
metrics = st.session_state.get("engine_metrics", {})
cursor = st.session_state.get("er_step_cursor", 0)

# Determine visible events based on step cursor
visible_events = events[:cursor] if cursor > 0 else events

# Casualty filter
all_pids = sorted({e.get("patient_id", "") for e in events if e.get("patient_id")})
focused_cas = st.selectbox(
    "Follow casualty",
    options=["All"] + all_pids,
    key="er_focus_cas",
)

if not events:
    st.info("No simulation data. Select a scenario and click **Run Simulation** in the sidebar.")
    st.stop()

if view_mode == "Engine Room (X-ray)":

    # Row 1: Timeline | X-Ray | Inspectors
    col_timeline, col_xray, col_inspect = st.columns([2, 4, 2])

    with col_timeline:
        st.subheader("Event Timeline")
        display = visible_events[-40:]
        if focused_cas != "All":
            display = [e for e in visible_events if e.get("patient_id") == focused_cas][-40:]
        for e in display:
            t = e.get("time", 0.0)
            etype = e.get("type", "?")
            pid = e.get("patient_id", "") or ""
            fac = e.get("facility", "") or ""
            st.text(f"T={t:>7.1f}  {etype:<20s} {pid:<10s} {fac}")
        if cursor > 0:
            st.caption(f"Showing {cursor}/{len(events)} events (step mode)")

    with col_xray:
        st.subheader("Architecture X-Ray")

        # Build the X-ray from the actual scenario topology
        scenario_dict = st.session_state.get("scenario_dict", {})
        facilities = scenario_dict.get("facilities", [])
        edges_list = scenario_dict.get("edges", [])

        # Colour events by paradigm
        last_event = visible_events[-1] if visible_events else {}
        last_type = last_event.get("type", "")

        # Determine active paradigm from last event type
        if last_type in ("ARRIVAL", "DISPOSITION", "TREATMENT_START", "TREATMENT_END",
                         "HOLD_START", "HOLD_TIMEOUT", "HOLD_RETRY"):
            active_paradigm = "des"
        elif last_type in ("TRIAGE",):
            active_paradigm = "bt"
        elif last_type in ("TRANSIT_START", "TRANSIT_END", "ROUTE_DENIED"):
            active_paradigm = "network"
        else:
            active_paradigm = "events"

        paradigm_colours = {
            "des": "#3b82f6", "bt": "#f59e0b",
            "network": "#10b981", "events": "#8b5cf6",
        }
        active_colour = paradigm_colours.get(active_paradigm, "#6b7280")

        # Build facility boxes from actual scenario
        fac_html_parts = []
        for fac in facilities:
            fac_html_parts.append(
                f'<div style="border: 1px solid {active_colour}; padding: 8px 12px; '
                f'border-radius: 6px; background: #1f2937; text-align: center;">'
                f'<span style="color: #e5e7eb; font-weight: 600;">{fac["id"]}</span><br/>'
                f'<span style="font-size: 10px; color: #9ca3af;">'
                f'{fac.get("role", "?")} | {fac.get("beds", 0)} beds</span>'
                f'</div>'
            )

        fac_row = ''.join(
            f'<div style="flex: 1; margin: 0 4px;">{part}</div>'
            for part in fac_html_parts
        )

        # Edge labels
        edge_labels = " → ".join(
            f'{e["from"]}→{e["to"]} ({e.get("travel_time_minutes", "?")}m)'
            for e in edges_list
        )

        xray_html = f"""
        <div style="font-family: system-ui, sans-serif; font-size: 12px;
                    background: #111827; color: #e5e7eb;
                    padding: 16px; border-radius: 8px;">
            <div style="text-align: center; margin-bottom: 8px;">
                <span style="color: {active_colour}; font-weight: 600; font-size: 13px;">
                    Active: {active_paradigm.upper()}
                </span>
                <span style="color: #6b7280;"> | Last: {last_type or '—'}</span>
            </div>
            <div style="display: flex; justify-content: center; gap: 8px;
                        margin-bottom: 12px;">
                {fac_row}
            </div>
            <div style="text-align: center; color: #6b7280; font-size: 10px;
                        margin-bottom: 12px;">
                {edge_labels}
            </div>
            <div style="display: flex; justify-content: center; gap: 16px;">
                <div style="border: 1px solid #059669; padding: 6px 10px;
                            border-radius: 4px; background: #064e3b;">
                    <span style="color: #34d399;">routing.py</span>
                    <span style="font-size: 9px; color: #6ee7b7;"> EX-1</span>
                </div>
                <div style="border: 1px solid #d97706; padding: 6px 10px;
                            border-radius: 4px; background: #451a03;">
                    <span style="color: #fbbf24;">pfc.py</span>
                    <span style="font-size: 9px; color: #fcd34d;"> EX-4</span>
                </div>
                <div style="border: 1px solid #7c3aed; padding: 6px 10px;
                            border-radius: 4px; background: #2e1065;">
                    <span style="color: #a78bfa;">emitter.py</span>
                    <span style="font-size: 9px; color: #c4b5fd;"> EX-3</span>
                </div>
                <div style="border: 1px solid #7c3aed; padding: 6px 10px;
                            border-radius: 4px; background: #2e1065;">
                    <span style="color: #a78bfa;">AnalyticsEngine</span>
                    <span style="font-size: 9px; color: #c4b5fd;"> Pattern E</span>
                </div>
            </div>
        </div>
        """
        st.components.v1.html(xray_html, height=220)

    with col_inspect:
        st.subheader("Blackboard")
        st.caption("BT blackboard state is internal to the engine generator. "
                   "Exposing it as a post-run snapshot requires engine instrumentation "
                   "(Phase 2 — HC-5 boundary).")
        # Show the last event's fields as a proxy for what we know
        if visible_events:
            last = visible_events[-1]
            st.json({
                "last_event_type": last.get("type"),
                "last_patient": last.get("patient_id"),
                "last_triage": last.get("triage"),
                "last_state": last.get("state"),
                "last_facility": last.get("facility"),
            })

        st.divider()

        # Topology from actual scenario
        st.subheader("Topology")
        if edges_list:
            for edge in edges_list:
                contested = edge.get("threat_level", 0) > 0.3
                marker = " (contested)" if contested else ""
                st.text(f"{edge['from']} →({edge.get('travel_time_minutes', '?')}m{marker})→ "
                        f"{edge['to']}")
        else:
            st.text("No edges in scenario.")

    # Row 2: Analytics Strip
    st.divider()
    st.subheader("Analytics Views")
    st.caption("Data source: AnalyticsEngine via EventBus — Pattern E boundary")
    a1, a2, a3 = st.columns(3)
    if analytics:
        golden = analytics.get_view("golden_hour")
        facility = analytics.get_view("facility_load")
        with a1:
            gh_mean = golden.get("mean_minutes", 0.0)
            st.metric("Golden Hour Mean", f"{gh_mean:.1f} min")
        with a2:
            max_peak = 0
            peak_fac = "—"
            for fid, data in facility.items():
                if data["peak"] > max_peak:
                    max_peak = data["peak"]
                    peak_fac = fid
            st.metric(f"Peak Load ({peak_fac})", f"{max_peak}")
        with a3:
            st.metric("Completed", metrics.get("completed", "—"))
    else:
        with a1:
            st.metric("Golden Hour", "—")
        with a2:
            st.metric("Peak Load", "—")
        with a3:
            st.metric("Completed", "—")

else:
    # Operations mode — stakeholder-facing, no architecture details
    st.subheader("Simulation Results")

    a1, a2, a3, a4 = st.columns(4)
    with a1:
        st.metric("Total Casualties", metrics.get("total_arrivals", "—"))
    with a2:
        if analytics:
            gh = analytics.get_view("golden_hour")
            st.metric("Golden Hour Compliance", f"{gh.get('pct_within_60', 0):.0%}")
        else:
            st.metric("Golden Hour Compliance", "—")
    with a3:
        denials = sum(1 for e in events if e.get("type") == "ROUTE_DENIED")
        st.metric("Route Denials", denials if events else "—")
    with a4:
        st.metric("Completed", metrics.get("completed", "—"))

    st.divider()

    # Full event stream in operations mode
    st.subheader("Event Stream")
    display = visible_events if cursor > 0 else events
    if focused_cas != "All":
        display = [e for e in display if e.get("patient_id") == focused_cas]
    if display:
        lines = []
        for e in display[-50:]:
            t = e.get("time", 0.0)
            etype = e.get("type", "?")
            pid = e.get("patient_id", "") or ""
            fac = e.get("facility", "") or ""
            lines.append(f"T={t:>7.1f}  {etype:<20s} {pid:<10s} {fac}")
        st.code("\n".join(lines))
    else:
        st.info("No events to display.")
