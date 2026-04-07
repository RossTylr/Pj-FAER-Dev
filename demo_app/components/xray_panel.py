"""Architecture X-Ray panel — patient journey phase diagram.

Shows 5 phases of the patient journey as a horizontal flow, with paradigm
labels, module names, coupling interfaces, and active event counts.
"""
from __future__ import annotations

from typing import Any, Optional

import streamlit as st


# Phase definitions: static architecture metadata
_PHASES: list[tuple[str, dict[str, str]]] = [
    ("TRIAGE", {
        "paradigm": "BT Sync Tick",
        "module": "Blackboard → BT",
        "coupling": "CP-1",
        "colour": "#f59e0b",   # amber
    }),
    ("TREATMENT", {
        "paradigm": "DES Yield (Y1+Y2)",
        "module": "engine.py",
        "coupling": "CP-3",
        "colour": "#3b82f6",   # blue
    }),
    ("HOLD/PFC", {
        "paradigm": "DES Yield (Y3)",
        "module": "pfc.py → engine.py",
        "coupling": "CP-3",
        "colour": "#f59e0b",   # amber
    }),
    ("ROUTING", {
        "paradigm": "Graph Query",
        "module": "routing.py (Dijkstra)",
        "coupling": "CP-4",
        "colour": "#10b981",   # green
    }),
    ("TRANSPORT", {
        "paradigm": "DES Yield (Y4+Y5)",
        "module": "engine.py",
        "coupling": "CP-3",
        "colour": "#3b82f6",   # blue
    }),
]

# Map event types to phases
_EVENT_TO_PHASE: dict[str, str] = {
    "TRIAGE": "TRIAGE",
    "ARRIVAL": "TRIAGE",
    "TREATMENT_START": "TREATMENT",
    "TREATMENT_END": "TREATMENT",
    "TREATMENT_COMPLETE": "TREATMENT",
    "HOLD_START": "HOLD/PFC",
    "HOLD_RETRY": "HOLD/PFC",
    "HOLD_TIMEOUT": "HOLD/PFC",
    "PFC_START": "HOLD/PFC",
    "PFC_END": "HOLD/PFC",
    "PFC_CEILING_EXCEEDED": "HOLD/PFC",
    "FACILITY_ARRIVAL": "ROUTING",
    "ROUTE_DENIED": "ROUTING",
    "TRANSIT_START": "TRANSPORT",
    "TRANSIT_END": "TRANSPORT",
    "MASCAL_ACTIVATE": "TRIAGE",
    "MASCAL_DEACTIVATE": "TRIAGE",
}


def compute_phase_activity(
    events: list[dict[str, Any]],
    T: float,
    window: float = 30.0,
) -> dict[str, int]:
    """Count events per journey phase in [T-window, T]."""
    lo = T - window
    counts: dict[str, int] = {name: 0 for name, _ in _PHASES}
    for e in events:
        t = e["time"]
        if t < lo:
            continue
        if t > T:
            break
        phase = _EVENT_TO_PHASE.get(e["type"])
        if phase:
            counts[phase] += 1
    return counts


def _get_focused_phase(
    events: list[dict[str, Any]],
    casualty_id: str,
    T: float,
) -> Optional[str]:
    """Determine a specific casualty's current phase from their last event."""
    last_type = None
    for e in events:
        if e["time"] > T:
            break
        if e.get("patient_id") == casualty_id:
            last_type = e["type"]
    if last_type is None:
        return None
    if last_type in ("DISPOSITION", "DISCHARGED"):
        return None  # casualty has left the system
    return _EVENT_TO_PHASE.get(last_type)


def render_xray(
    events: list[dict[str, Any]],
    T: float,
    window: float = 30.0,
    focused_casualty: Optional[str] = None,
) -> None:
    """Render the 5-phase patient journey diagram.

    Args:
        events: Full event list (sorted by time).
        T: Current simulation time.
        window: Trailing window in sim-minutes for activity counts.
        focused_casualty: If set, highlight only this casualty's current phase.
    """
    counts = compute_phase_activity(events, T, window=window)

    # When focused, determine which phase the casualty is in
    focused_phase: Optional[str] = None
    if focused_casualty:
        focused_phase = _get_focused_phase(events, focused_casualty, T)

    # Render horizontal flow
    cols = st.columns(len(_PHASES))
    for i, (phase_name, meta) in enumerate(_PHASES):
        count = counts[phase_name]
        active = count > 0

        # Dim phases that aren't the focused casualty's current phase
        dimmed = focused_casualty is not None and phase_name != focused_phase

        with cols[i]:
            with st.container(border=True):
                if dimmed or not active:
                    st.markdown(
                        f"<span style='color:#999; font-size:14px;'>"
                        f"{phase_name}</span>",
                        unsafe_allow_html=True,
                    )
                    st.caption(
                        f"<span style='color:#bbb'>{meta['paradigm']}</span>",
                        unsafe_allow_html=True,
                    )
                    st.caption(
                        f"<span style='color:#bbb'>`{meta['module']}`</span>",
                        unsafe_allow_html=True,
                    )
                else:
                    colour = meta["colour"]
                    st.markdown(
                        f"<span style='color:{colour}; font-weight:700; "
                        f"font-size:14px;'>{phase_name}</span>",
                        unsafe_allow_html=True,
                    )
                    st.caption(meta["paradigm"])
                    st.caption(f"`{meta['module']}`")
                    st.caption(f"Interface: {meta['coupling']}")
                    st.metric("Active", count, label_visibility="collapsed")

    # Flow arrows between phases
    arrow_cols = st.columns(len(_PHASES) * 2 - 1)
    for i in range(len(_PHASES)):
        with arrow_cols[i * 2]:
            st.empty()
        if i < len(_PHASES) - 1:
            with arrow_cols[i * 2 + 1]:
                st.markdown(
                    "<div style='text-align:center; color:#666; "
                    "font-size:18px; margin-top:-8px;'>→</div>",
                    unsafe_allow_html=True,
                )

    # Summary line
    busiest_name = max(counts, key=counts.get)  # type: ignore[arg-type]
    busiest_count = counts[busiest_name]
    if busiest_count > 0:
        meta = dict(_PHASES)[busiest_name]
        st.caption(
            f"Primary activity: **{busiest_name}** — "
            f"{meta['paradigm']} via `{meta['module']}` ({meta['coupling']})"
        )
    else:
        st.caption("No activity in trailing window")
