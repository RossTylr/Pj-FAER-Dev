"""Paradigm activity pie — donut chart of DES/BT/Graph/System split.

Quantifies the poly-hybrid nature: what percentage of engine activity
is discrete-event scheduling vs graph routing vs system lifecycle.
"""
from __future__ import annotations

from typing import Any

import plotly.graph_objects as go


def compute_paradigm_split(
    events: list[dict[str, Any]],
    T: float,
    window: float = 30.0,
) -> dict[str, int]:
    """Classify recent events by architectural paradigm.

    DES: yield-bearing phases (treatment, transit)
    Graph: routing decisions (facility arrival)
    System: engine lifecycle (arrival, disposition, MASCAL)
    BT: triage decisions (absent from legacy events — will be 0)
    """
    lo = T - window
    split = {
        "DES Scheduling": 0,
        "BT Decisions": 0,
        "Graph Routing": 0,
        "System Events": 0,
    }

    for e in events:
        t = e["time"]
        if t < lo:
            continue
        if t > T:
            break
        etype = e["type"]

        if etype in ("TREATMENT_START", "TREATMENT_END",
                     "TRANSIT_START", "TRANSIT_END"):
            split["DES Scheduling"] += 1
        elif etype == "TRIAGE":
            # Absent from legacy events — included for future-proofing
            split["BT Decisions"] += 1
        elif etype == "FACILITY_ARRIVAL":
            split["Graph Routing"] += 1
        else:
            # ARRIVAL, DISPOSITION, MASCAL_ACTIVATE, MASCAL_DEACTIVATE
            split["System Events"] += 1

    return split


def render_paradigm_pie(
    events: list[dict[str, Any]],
    T: float,
) -> go.Figure:
    """Donut chart of paradigm activity split."""
    split = compute_paradigm_split(events, T)
    colours = {
        "DES Scheduling": "#3B82F6",
        "BT Decisions": "#8B5CF6",
        "Graph Routing": "#14B8A6",
        "System Events": "#6B7280",
    }

    labels = list(split.keys())
    values = list(split.values())
    total = sum(values)

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker_colors=[colours[l] for l in labels],
        hole=0.5,
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>%{value} events (%{percent})<extra></extra>",
    ))
    fig.update_layout(
        height=250, width=250,
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        annotations=[dict(text=str(total), x=0.5, y=0.5,
                         font_size=20, showarrow=False)],
    )
    return fig
