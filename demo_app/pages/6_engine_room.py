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
        # TODO: Plotly swimlane with yield markers (Y1-Y5)
        # Each event annotated with source module
        placeholder_events = [
            ("0.0", "ARRIVAL", "CAS-001", "POI", "emitter.py"),
            ("0.0", "TRIAGED", "CAS-001", "POI", "emitter.py"),
            ("0.0", "route_decide", "CAS-001", "—", "routing.py"),
            ("2.1", "Y5 travel", "CAS-001", "POI-R1", "engine.py"),
            ("32.1", "ARRIVED", "CAS-001", "R1", "emitter.py"),
            ("32.1", "Y1 resource", "CAS-001", "R1", "engine.py"),
            ("35.4", "Y2 treat", "CAS-001", "R1", "engine.py"),
            ("55.2", "TREATED", "CAS-001", "R1", "emitter.py"),
        ]
        for t, evt, cas, fac, mod in placeholder_events:
            if focused_cas == "All" or focused_cas == cas:
                prefix = "  " if "Y" not in evt else ">>"
                st.text(f"{prefix} T={t:>6s}  {evt:<14s} {cas} {fac:<6s} [{mod}]")

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
    with a1:
        st.metric("Golden Hour (T1)", "28.3 min", delta="-4.2 min",
                  help="Mean time to first treatment for T1 casualties")
    with a2:
        st.metric("R1 Peak Load", "4 / 4", delta="AT CAPACITY",
                  delta_color="inverse",
                  help="Peak concurrent occupancy at Role 1")
    with a3:
        st.metric("Mean P(survival)", "0.71", delta="+0.03",
                  help="Running survivability estimate across all casualties")

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
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        st.metric("Total Casualties", "20")
    with a2:
        st.metric("Golden Hour Compliance", "85%")
    with a3:
        st.metric("Route Denials", "4")
    with a4:
        st.metric("Mean P(survival)", "0.71")
