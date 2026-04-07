"""Single-casualty journey waterfall — horizontal bar chart of journey phases.

Shows one casualty's journey as stacked bars: wait (red), transit (grey),
treatment (green). Replaces the heatmap when a casualty is focused.
"""
from __future__ import annotations

from typing import Any, Optional

import plotly.graph_objects as go


def compute_single_journey(
    events: list[dict[str, Any]],
    casualty_id: str,
    T: float,
) -> list[dict[str, Any]]:
    """Build ordered phase list for one casualty from events up to T.

    Returns list of phase dicts with: phase, facility/from/to, start, duration, colour.
    """
    cas_events = [
        e for e in events
        if e.get("patient_id") == casualty_id and e["time"] <= T
    ]
    if not cas_events:
        return []

    phases: list[dict[str, Any]] = []
    last_facility_arrival: Optional[dict[str, Any]] = None
    last_transit_start: Optional[dict[str, Any]] = None
    last_treat_start: Optional[dict[str, Any]] = None

    for e in cas_events:
        etype = e["type"]
        fac = e.get("facility", "")
        t = e["time"]

        if etype == "FACILITY_ARRIVAL":
            # Close any open transit
            if last_transit_start:
                dur = t - last_transit_start["time"]
                details = last_transit_start.get("details", {})
                phases.append({
                    "phase": "TRANSIT",
                    "from": details.get("origin", ""),
                    "to": details.get("destination", fac),
                    "start": last_transit_start["time"],
                    "duration": dur,
                    "colour": "#6B7280",
                })
                last_transit_start = None
            last_facility_arrival = e

        elif etype == "TREATMENT_START":
            # Wait phase: FACILITY_ARRIVAL -> TREATMENT_START
            if last_facility_arrival and last_facility_arrival.get("facility") == fac:
                dur = t - last_facility_arrival["time"]
                if dur > 0:
                    phases.append({
                        "phase": "WAIT",
                        "facility": fac,
                        "start": last_facility_arrival["time"],
                        "duration": dur,
                        "colour": "#EF4444",
                    })
                last_facility_arrival = None
            last_treat_start = e

        elif etype == "TREATMENT_END":
            if last_treat_start:
                dur = t - last_treat_start["time"]
                phases.append({
                    "phase": "TREATMENT",
                    "facility": fac,
                    "start": last_treat_start["time"],
                    "duration": dur,
                    "colour": "#10B981",
                })
                last_treat_start = None

        elif etype == "TRANSIT_START":
            last_transit_start = e

    return phases


def render_journey_waterfall(
    events: list[dict[str, Any]],
    casualty_id: str,
    T: float,
) -> Optional[go.Figure]:
    """Horizontal bar chart showing one casualty's journey phases."""
    phases = compute_single_journey(events, casualty_id, T)
    if not phases:
        return None

    labels = []
    durations = []
    colours = []
    for p in phases:
        if p["phase"] == "TRANSIT":
            labels.append(f"Transit {p.get('from', '?')} → {p.get('to', '?')}")
        else:
            labels.append(f"{p['phase']} @ {p.get('facility', '?')}")
        durations.append(p["duration"])
        colours.append(p["colour"])

    fig = go.Figure(go.Bar(
        y=labels, x=durations, orientation="h",
        marker_color=colours,
        text=[f"{d:.0f}m" for d in durations],
        textposition="inside",
        hovertemplate="<b>%{y}</b><br>%{x:.0f} min<extra></extra>",
    ))

    total = sum(durations)
    fig.update_layout(
        xaxis_title="Duration (minutes)",
        height=max(200, len(labels) * 35),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=150, r=20, t=20, b=40),
        yaxis=dict(autorange="reversed"),
        annotations=[dict(
            text=f"Total: {total:.0f} min",
            xref="paper", yref="paper", x=1, y=-0.15,
            showarrow=False, font=dict(size=11),
        )],
    )
    return fig
