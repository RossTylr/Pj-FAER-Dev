"""Timeline panel — Plotly scatter of events over time.

X = simulation time, Y = patient ID (categorical), color = event type.
Events after T are faded. Vertical dashed line marks current T.
"""
from __future__ import annotations

from typing import Any, Optional

import plotly.graph_objects as go


EVENT_COLOURS: dict[str, str] = {
    "ARRIVAL": "#3B82F6",           # blue
    "CREATED": "#3B82F6",           # blue (alias)
    "TRIAGE": "#8B5CF6",            # purple
    "FACILITY_ARRIVAL": "#06B6D4",  # cyan
    "TREATMENT_START": "#10B981",   # green
    "TREATMENT_END": "#10B981",     # green
    "TREATMENT_COMPLETE": "#10B981",# green (alias)
    "PFC_START": "#F59E0B",         # orange
    "HOLD_START": "#F59E0B",        # orange
    "TRANSIT_START": "#6B7280",     # grey
    "TRANSIT_END": "#6B7280",       # grey
    "ROUTE_DENIED": "#EF4444",      # red
    "MASCAL_ACTIVATE": "#EF4444",   # red
    "MASCAL_DEACTIVATE": "#F87171", # light red
    "DISPOSITION": "#111827",       # black
    "DISCHARGED": "#111827",        # black (alias)
}

# Deduplicated legend entries (canonical type -> colour)
_LEGEND: list[tuple[str, str]] = [
    ("Arrival", "#3B82F6"),
    ("Triage", "#8B5CF6"),
    ("Facility Arrival", "#06B6D4"),
    ("Treatment", "#10B981"),
    ("PFC / Hold", "#F59E0B"),
    ("Transit", "#6B7280"),
    ("Denied / MASCAL", "#EF4444"),
    ("Disposition", "#111827"),
]


def detect_mascal_windows(
    events: list[dict[str, Any]],
) -> list[tuple[float, float]]:
    """Detect MASCAL periods from MASCAL_ACTIVATE/DEACTIVATE event pairs."""
    windows: list[tuple[float, float]] = []
    active_start: Optional[float] = None
    for e in events:
        if e["type"] == "MASCAL_ACTIVATE":
            active_start = e["time"]
        elif e["type"] == "MASCAL_DEACTIVATE" and active_start is not None:
            windows.append((active_start, e["time"]))
            active_start = None
    # Handle unclosed MASCAL (still active at sim end)
    if active_start is not None and events:
        windows.append((active_start, events[-1]["time"]))
    return windows


def render_timeline(
    events: list[dict[str, Any]],
    T: float,
    focused_casualty: Optional[str] = None,
    group_by: str = "facility",
    mascal_windows: Optional[list[tuple[float, float]]] = None,
) -> go.Figure:
    """Build a Plotly scatter showing all events, fading those after T.

    Args:
        events: Full event list (not just visible).
        T: Current simulation time.
        focused_casualty: If set, full opacity only for this casualty.
            Auto-switches to patient grouping when set.
        group_by: "facility" for facility swimlanes, "patient" for per-casualty rows.
            Ignored (forced to "patient") when focused_casualty is set.
    """
    # Auto-switch to patient view when following a specific casualty
    if focused_casualty:
        group_by = "patient"

    xs, ys, colors, opacities, hovers = [], [], [], [], []

    for e in events:
        t = e.get("time", 0.0)
        pid = e.get("patient_id", "") or ""
        etype = e.get("type", "?")
        fac = e.get("facility", "") or ""

        xs.append(t)
        ys.append(fac if group_by == "facility" else pid)
        colors.append(EVENT_COLOURS.get(etype, "#6B7280"))

        # Opacity: faded if after T, or if focused on a different casualty
        if t > T:
            opacities.append(0.15)
        elif focused_casualty and pid != focused_casualty:
            opacities.append(0.1)
        else:
            opacities.append(1.0)

        hovers.append(f"T={t:.1f} {etype}<br>{pid} @ {fac}")

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=xs, y=ys,
        mode="markers",
        marker=dict(size=7, color=colors, opacity=opacities),
        hoverinfo="text",
        hovertext=hovers,
        showlegend=False,
    ))

    # Legend entries
    for label, color in _LEGEND:
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=7, color=color),
            name=label, showlegend=True,
        ))

    # Vertical line at current T
    fig.add_vline(x=T, line_dash="dash", line_color="white", line_width=1)

    # MASCAL shaded bands
    if mascal_windows:
        for start, end in mascal_windows:
            fig.add_vrect(
                x0=start, x1=end,
                fillcolor="rgba(239,68,68,0.08)", line_width=0,
                annotation_text="MASCAL",
                annotation_position="top left",
                annotation_font_color="#EF4444",
                annotation_font_size=10,
            )

    fig.update_layout(
        xaxis_title="Simulation Time",
        yaxis_title="",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=30),
        height=350,
        yaxis=dict(categoryorder="category ascending"),
        legend=dict(orientation="h", yanchor="top", y=-0.15, font=dict(size=9)),
    )

    return fig
