"""Event rate chart — histogram of events per time bin.

Shows the rhythm of the simulation: steady baseline with MASCAL spikes.
Events after T are faded. Optional MASCAL period shading.
"""
from __future__ import annotations

from typing import Any, Optional

import plotly.graph_objects as go


def render_event_rate(
    events: list[dict[str, Any]],
    T: float,
    bin_minutes: int = 5,
    mascal_windows: Optional[list[tuple[float, float]]] = None,
) -> go.Figure:
    """Histogram of event rate over time.

    Args:
        events: Full event list.
        T: Current simulation time.
        bin_minutes: Bin width in sim-minutes.
        mascal_windows: List of (start, end) tuples for MASCAL shading.
    """
    times_before = [e["time"] for e in events if e["time"] <= T]
    times_after = [e["time"] for e in events if e["time"] > T]

    fig = go.Figure()

    fig.add_trace(go.Histogram(
        x=times_before, xbins=dict(start=0, size=bin_minutes),
        marker_color="#3B82F6", name="Events",
        hovertemplate="T=%{x}: %{y} events<extra></extra>",
    ))

    if times_after:
        fig.add_trace(go.Histogram(
            x=times_after, xbins=dict(start=0, size=bin_minutes),
            marker_color="rgba(59,130,246,0.15)", name="Future",
            hovertemplate="T=%{x}: %{y} events<extra></extra>",
        ))

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

    fig.add_vline(x=T, line_dash="dot", line_color="red", line_width=1)
    fig.update_layout(
        xaxis_title="Simulation Time (min)",
        yaxis_title=f"Events / {bin_minutes} min",
        height=180,
        barmode="stack",
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=10, b=40),
    )
    return fig
