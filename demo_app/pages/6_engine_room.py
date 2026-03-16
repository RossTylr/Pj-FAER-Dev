"""Page 6: FAER Engine Room — Architecture X-Ray.

Real-time visualisation of the simulation engine's inner workings.
Shows which paradigm is active, which coupling interfaces are used,
and where the yield points pause the simulation clock.

Build AFTER Phase 1 NB39 gate passes.
See: docs/ENGINE_ROOM_IDEATION.md for full design specification.
"""
import streamlit as st

# --- Sidebar Controls ---
with st.sidebar:
    st.header("Engine Room Controls")

    scenario = st.radio(
        "Scenario",
        ["NB32 Acceptance (20 cas, 3-node)",
         "IRON BRIDGE (LSCO, 5-node)",
         "Custom"],
    )

    speed = st.select_slider(
        "Simulation speed",
        options=["Step", "Slow", "Normal", "Fast", "Instant"],
        value="Normal",
    )

    view_mode = st.radio(
        "View mode",
        ["Engine Room (X-ray)", "Operations (output only)"],
        horizontal=True,
    )

    focused_cas = st.selectbox(
        "Follow casualty",
        options=["All"] + [f"CAS-{i:03d}" for i in range(20)],
    )

    st.divider()

    if speed == "Step":
        step_btn = st.button("Step Forward", type="primary", use_container_width=True)
    else:
        run_btn = st.button("Run Simulation", type="primary", use_container_width=True)

    st.divider()
    st.caption("Paradigm colours:")
    st.markdown("""
    - :blue[Blue] — SimPy DES (yields, timeouts)
    - :orange[Amber] — BehaviorTree (BB writes, ticks)
    - :green[Green] — NetworkX (routing, paths)
    - :violet[Purple] — Events (publish, subscribe)
    """)

# --- Main Layout ---
st.title("FAER Engine Room")

if view_mode == "Engine Room (X-ray)":

    # Row 1: Timeline | X-Ray | Inspectors
    col_timeline, col_xray, col_inspect = st.columns([2, 4, 2])

    with col_timeline:
        st.subheader("Event Timeline")
        events = st.session_state.get("events", [])
        if events:
            for e in events[-30:]:
                t = e.get("time", 0.0)
                etype = e.get("type", "?")
                pid = e.get("patient_id", "") or ""
                fac = e.get("facility", "") or ""
                if focused_cas == "All" or focused_cas == pid:
                    st.text(f"T={t:>7.1f}  {etype:<20s} {pid:<10s} {fac}")
        else:
            st.info("Run a simulation first to see live events.")

    with col_xray:
        st.subheader("Architecture X-Ray")

        # Static SVG placeholder — replace with animated version post-Phase 1
        xray_html = """
        <div style="font-family: system-ui, sans-serif; font-size: 12px;
                    line-height: 1.6; background: #111827; color: #e5e7eb;
                    padding: 20px; border-radius: 8px; text-align: center;">
            <div style="border: 1px solid #374151; padding: 8px; margin-bottom: 16px;
                        border-radius: 6px; background: #1f2937;">
                <span style="color: #9ca3af; font-size: 11px;">IRREDUCIBLE KERNEL (11 files)</span><br/>
                <span style="font-size: 10px; color: #6b7280;">
                    enums | schemas | blackboard | bt_nodes | trees | topology | models | bus | store
                </span>
            </div>
            <div style="display: flex; justify-content: center; gap: 16px; margin-bottom: 16px;">
                <div style="border: 1px solid #059669; padding: 10px 14px; border-radius: 6px;
                            background: #064e3b;">
                    <span style="color: #34d399;">routing.py</span><br/>
                    <span style="font-size: 10px; color: #6ee7b7;">EX-1 | sync</span>
                </div>
                <div style="border: 2px solid #3b82f6; padding: 14px 20px; border-radius: 6px;
                            background: #1e3a5f;">
                    <span style="color: #93c5fd; font-weight: 600;">engine.py</span><br/>
                    <span style="font-size: 11px; color: #60a5fa;">Y1 Y2 Y3 Y4 Y5</span><br/>
                    <span style="font-size: 10px; color: #93c5fd;">orchestrator</span>
                </div>
                <div style="border: 1px solid #d97706; padding: 10px 14px; border-radius: 6px;
                            background: #451a03;">
                    <span style="color: #fbbf24;">pfc.py</span><br/>
                    <span style="font-size: 10px; color: #fcd34d;">EX-4 | sync</span>
                </div>
            </div>
            <div style="color: #4b5563; font-size: 18px;">|</div>
            <div style="border: 1px solid #7c3aed; padding: 8px; margin: 8px auto;
                        border-radius: 6px; background: #2e1065; max-width: 180px;">
                <span style="color: #a78bfa;">emitter.py</span><br/>
                <span style="font-size: 10px; color: #c4b5fd;">EX-3 | typed events</span>
            </div>
            <div style="color: #4b5563; font-size: 18px;">|</div>
            <div style="border: 1px solid #7c3aed; padding: 8px; margin: 8px auto;
                        border-radius: 6px; background: #2e1065; max-width: 180px;">
                <span style="color: #a78bfa;">EventBus (CP-2)</span>
            </div>
            <div style="color: #4b5563; font-size: 18px;">|</div>
            <div style="border: 1px solid #7c3aed; padding: 8px; margin: 8px auto;
                        border-radius: 6px; background: #2e1065; max-width: 180px;">
                <span style="color: #a78bfa;">AnalyticsEngine</span><br/>
                <span style="font-size: 10px; color: #c4b5fd;">Pattern E | cold path</span>
            </div>
        </div>
        """
        st.components.v1.html(xray_html, height=430)

    with col_inspect:
        # Blackboard Inspector
        st.subheader("Blackboard")
        st.caption("IC-2: Engine writes (before BT tick)")
        st.json({
            "patient_severity": 0.72,
            "patient_primary_region": "CHEST",
            "patient_mechanism": "BLAST",
            "patient_is_polytrauma": False,
            "patient_is_surgical": True,
            "patient_gcs": 9,
        })
        st.caption("IC-3: BT writes (after tick)")
        st.json({
            "decision_triage": "T1",
            "decision_department": "FST",
            "decision_dcs": True,
        })

        st.divider()

        # Network Topology placeholder
        st.subheader("Topology")
        st.markdown("""
        ```
        POI ──(30m, contested)──► R1 ──(45m)──► R2
        cap:50                   cap:4          cap:8
        ```
        """)
        st.caption("Contested edges pulse red on denial. "
                   "Casualty positions marked on nodes.")

    # Row 2: Analytics Strip
    st.divider()
    st.subheader("Analytics Views")
    st.caption("Data source: AnalyticsEngine via EventBus — Pattern E boundary")
    a1, a2, a3 = st.columns(3)
    analytics = st.session_state.get("analytics")
    metrics = st.session_state.get("engine_metrics", {})
    if analytics:
        golden = analytics.get_view("golden_hour")
        facility = analytics.get_view("facility_load")
        with a1:
            gh_mean = golden.get("mean_minutes", 0.0)
            st.metric("Golden Hour Mean", f"{gh_mean:.1f} min",
                      help="Mean time to disposition")
        with a2:
            max_peak = 0
            peak_fac = "—"
            for fid, data in facility.items():
                if data["peak"] > max_peak:
                    max_peak = data["peak"]
                    peak_fac = fid
            st.metric(f"Peak Load ({peak_fac})", f"{max_peak}",
                      help="Highest peak occupancy across facilities")
        with a3:
            st.metric("Completed", metrics.get("completed", "—"),
                      help="Total completed casualties")
    else:
        with a1:
            st.metric("Golden Hour", "—")
        with a2:
            st.metric("Peak Load", "—")
        with a3:
            st.metric("Completed", "—")

else:
    # Operations mode
    st.subheader("Simulation Results")

    col_ops_left, col_ops_right = st.columns([3, 2])
    with col_ops_left:
        st.info("Operations view: expanded timeline + analytics. "
                "Architecture X-ray hidden. For stakeholder presentations.")
    with col_ops_right:
        st.info("Network status with current casualties and route status.")

    st.divider()
    metrics = st.session_state.get("engine_metrics", {})
    analytics = st.session_state.get("analytics")
    events = st.session_state.get("events", [])
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
