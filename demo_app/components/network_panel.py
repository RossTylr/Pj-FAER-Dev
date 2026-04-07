"""Network topology panel — Plotly graph of facilities and casualty positions.

Renders facilities as nodes (colored by occupancy), edges with travel
time labels, and casualty dots at their current locations.
"""
from __future__ import annotations

from typing import Any, Optional

import plotly.graph_objects as go


# Role → fallback x-position when coordinates are missing
_ROLE_X = {"POI": 0.0, "R1": 1.0, "R2": 2.0, "R3": 3.0, "R4": 4.0}


def _occupancy_color(current: int, beds: int) -> str:
    """Green < 50%, amber 50-80%, red > 80%."""
    if beds <= 0:
        return "#6b7280"  # grey for POI (0 beds)
    ratio = current / beds
    if ratio < 0.5:
        return "#10b981"  # green
    if ratio < 0.8:
        return "#f59e0b"  # amber
    return "#ef4444"      # red


def render_network(
    topology: dict[str, Any],
    state: dict[str, Any],
    focused_casualty: Optional[str] = None,
) -> go.Figure:
    """Build a Plotly figure showing the facility network at current time.

    Args:
        topology: Raw YAML dict with 'facilities' and 'edges'.
        state: Output of compute_state_at_T().
        focused_casualty: If set, highlight this casualty and fade others.
    """
    facilities = topology.get("facilities", [])
    edges = topology.get("edges", [])
    occupancy = state.get("facility_occupancy", {})
    cas_locations = state.get("casualty_locations", {})
    active_transits = state.get("active_transits", [])

    # Build position lookup, with fallback for missing coordinates
    pos: dict[str, tuple[float, float]] = {}
    role_counts: dict[str, int] = {}
    for fac in facilities:
        coords = fac.get("coordinates")
        if coords and len(coords) == 2:
            pos[fac["id"]] = (coords[0], coords[1])
        else:
            role = fac.get("role", "POI")
            x = _ROLE_X.get(role, 0.0)
            n = role_counts.get(role, 0)
            role_counts[role] = n + 1
            y = 0.3 * (n - 0.5) if n > 0 else 0.0
            pos[fac["id"]] = (x, y)

    fig = go.Figure()

    # --- Edges ---
    for edge in edges:
        f_id, t_id = edge["from"], edge["to"]
        if f_id not in pos or t_id not in pos:
            continue
        x0, y0 = pos[f_id]
        x1, y1 = pos[t_id]
        threat = edge.get("threat_level", 0)
        contested = threat > 0.3
        travel = edge.get("travel_time_minutes", "?")
        transport = edge.get("transport", "")

        fig.add_trace(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None],
            mode="lines",
            line=dict(
                color="#ef4444" if contested else "#4b5563",
                width=2,
                dash="dash" if contested else "solid",
            ),
            hoverinfo="text",
            text=f"{f_id}→{t_id} {travel}min {transport}",
            showlegend=False,
        ))

        # Edge label at midpoint
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        label = f"{travel}m"
        if contested:
            label += " !"
        fig.add_annotation(
            x=mx, y=my, text=label,
            showarrow=False, font=dict(size=9, color="#9ca3af"),
        )

    # --- Facility nodes ---
    for fac in facilities:
        fid = fac["id"]
        beds = fac.get("beds", 0)
        occ = occupancy.get(fid, 0)
        x, y = pos[fid]
        color = _occupancy_color(occ, beds)
        label = f"{fid}<br>{occ}/{beds}" if beds > 0 else fid

        fig.add_trace(go.Scatter(
            x=[x], y=[y],
            mode="markers+text",
            marker=dict(size=28, color=color, line=dict(width=2, color="white")),
            text=f"{fid}<br>{occ}/{beds}" if beds > 0 else fid,
            textposition="bottom center",
            textfont=dict(size=10, color="#e5e7eb"),
            hoverinfo="text",
            hovertext=f"{fid} ({fac.get('role', '?')})<br>{occ}/{beds} beds",
            showlegend=False,
        ))

    # --- Casualty dots at facilities ---
    fac_cas_count: dict[str, int] = {}
    for cid, loc in cas_locations.items():
        if loc.startswith("transit:"):
            continue
        fac_cas_count.setdefault(loc, 0)
        offset = fac_cas_count[loc] * 0.15
        fac_cas_count[loc] += 1

        if loc not in pos:
            continue
        fx, fy = pos[loc]
        opacity = 1.0
        if focused_casualty and cid != focused_casualty:
            opacity = 0.15

        fig.add_trace(go.Scatter(
            x=[fx + offset], y=[fy + 0.4],
            mode="markers",
            marker=dict(size=8, color="#60a5fa", opacity=opacity),
            hoverinfo="text",
            hovertext=cid,
            showlegend=False,
        ))

    # --- In-transit dots at edge midpoints ---
    for cid, origin, dest in active_transits:
        if origin not in pos or dest not in pos:
            continue
        x0, y0 = pos[origin]
        x1, y1 = pos[dest]
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        opacity = 1.0
        if focused_casualty and cid != focused_casualty:
            opacity = 0.15

        fig.add_trace(go.Scatter(
            x=[mx], y=[my + 0.2],
            mode="markers",
            marker=dict(size=8, color="#fbbf24", symbol="diamond", opacity=opacity),
            hoverinfo="text",
            hovertext=f"{cid} in transit",
            showlegend=False,
        ))

    fig.update_layout(
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x"),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        height=350,
    )

    return fig
