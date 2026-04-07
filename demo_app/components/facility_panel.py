"""Facility performance panel — occupancy timeseries per facility.

Shows per-facility occupancy over time as line traces with capacity
reference lines. Vertical marker at current T.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

import plotly.graph_objects as go


def compute_facility_timeseries(
    events: list[dict[str, Any]],
    T: float,
    facilities: list[dict[str, Any]],
    bin_minutes: int = 30,
) -> dict[str, list[dict[str, Any]]]:
    """Compute occupancy at regular time intervals per facility.

    Walks events chronologically, recording occupancy at each bin edge.
    Uses the same FACILITY_ARRIVAL/TRANSIT_START/DISPOSITION logic as
    compute_state_at_T (only counting patients that had a FACILITY_ARRIVAL).
    """
    fac_ids = [f["id"] for f in facilities]
    occupancy: dict[str, int] = {f: 0 for f in fac_ids}
    counted_at: dict[str, str] = {}  # patient -> facility (via FACILITY_ARRIVAL)
    timeseries: dict[str, list[dict[str, Any]]] = {f: [] for f in fac_ids}

    bin_edges = list(range(0, int(T) + bin_minutes, bin_minutes))
    event_idx = 0

    for bin_time in bin_edges:
        if bin_time > T:
            break
        # Process events up to this bin
        while event_idx < len(events) and events[event_idx]["time"] <= bin_time:
            e = events[event_idx]
            etype = e["type"]
            pid = e.get("patient_id", "")
            fac = e.get("facility", "")
            event_idx += 1

            if etype == "FACILITY_ARRIVAL":
                occupancy[fac] = occupancy.get(fac, 0) + 1
                counted_at[pid] = fac
            elif etype == "TRANSIT_START":
                if fac and counted_at.get(pid) == fac:
                    occupancy[fac] = max(0, occupancy[fac] - 1)
                    counted_at.pop(pid, None)
            elif etype == "DISPOSITION":
                if fac and counted_at.get(pid) == fac:
                    occupancy[fac] = max(0, occupancy[fac] - 1)
                    counted_at.pop(pid, None)

        for fac_id in fac_ids:
            timeseries[fac_id].append({
                "time": bin_time,
                "occupancy": occupancy.get(fac_id, 0),
            })

    return timeseries


def render_facility_performance(
    events: list[dict[str, Any]],
    T: float,
    topology: dict[str, Any],
    focused_facility: Optional[str] = None,
    focused_casualty: Optional[str] = None,
) -> go.Figure:
    """Build a Plotly figure of facility occupancy over time.

    Args:
        events: Full event list (sorted by time).
        T: Current simulation time.
        topology: Raw YAML dict with 'facilities'.
        focused_facility: If set, show only this facility with emphasis.
        focused_casualty: If set, highlight facilities they visited.
    """
    facilities = topology.get("facilities", [])
    capacity: dict[str, int] = {f["id"]: f.get("beds", 0) for f in facilities}

    # Determine which facilities to highlight
    visited: set[str] | None = None
    if focused_casualty:
        visited = {
            e.get("facility", "")
            for e in events
            if e.get("patient_id") == focused_casualty and e.get("facility")
        }

    timeseries = compute_facility_timeseries(events, T, facilities)

    fig = go.Figure()

    for fac_id, series in timeseries.items():
        beds = capacity.get(fac_id, 0)
        if beds == 0:
            continue  # skip POI (0 beds, no occupancy to track)

        times = [s["time"] for s in series]
        occ = [s["occupancy"] for s in series]

        # Determine visibility/opacity
        if focused_facility and fac_id != focused_facility:
            opacity = 0.15
        elif visited is not None and fac_id not in visited:
            opacity = 0.15
        else:
            opacity = 1.0

        fig.add_trace(go.Scatter(
            x=times, y=occ,
            name=f"{fac_id} ({beds} beds)",
            mode="lines",
            line=dict(width=2),
            opacity=opacity,
        ))

        # Capacity reference line
        if opacity > 0.5:
            fig.add_hline(
                y=beds,
                line_dash="dash",
                line_color="rgba(200,200,200,0.3)",
                annotation_text=f"{fac_id} cap",
                annotation_font_size=9,
                annotation_font_color="rgba(200,200,200,0.5)",
            )

    # Vertical line at current T
    fig.add_vline(x=T, line_dash="dot", line_color="red", line_width=1)

    fig.update_layout(
        xaxis_title="Simulation Time (minutes)",
        yaxis_title="Occupancy",
        height=280,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=30),
        legend=dict(orientation="h", yanchor="top", y=-0.15, font=dict(size=9)),
    )

    return fig
