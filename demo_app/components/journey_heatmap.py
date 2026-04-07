"""Journey heatmap — casualties x phases, colour = duration in minutes.

Shows where the system fails patients: long red cells = bottlenecks.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

import plotly.graph_objects as go


def compute_journey_phases(
    events: list[dict[str, Any]],
    T: float,
) -> list[dict[str, Any]]:
    """Compute per-casualty phase durations from events up to T.

    Phases:
    - WAIT: FACILITY_ARRIVAL → TREATMENT_START (per facility visit)
    - TRANSIT: TRANSIT_START → TRANSIT_END
    - TREATMENT: TREATMENT_START → TREATMENT_END
    - HOLD: always 0 (HOLD_START absent from legacy events)
    """
    # Build per-casualty event lists
    by_patient: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        if e["time"] > T:
            break
        pid = e.get("patient_id", "")
        if pid:
            by_patient[pid].append(e)

    results = []
    for pid, pevents in by_patient.items():
        wait = 0.0
        transit = 0.0
        treatment = 0.0

        arrival_at: dict[str, float] = {}  # facility -> FACILITY_ARRIVAL time
        transit_start_t: Optional[float] = None
        treat_start_t: Optional[float] = None

        for e in pevents:
            etype = e["type"]
            fac = e.get("facility", "")
            t = e["time"]

            if etype == "FACILITY_ARRIVAL":
                arrival_at[fac] = t
                transit_start_t = None  # transit ended
            elif etype == "TREATMENT_START":
                if fac in arrival_at:
                    wait += t - arrival_at[fac]
                    del arrival_at[fac]
                treat_start_t = t
            elif etype == "TREATMENT_END":
                if treat_start_t is not None:
                    treatment += t - treat_start_t
                    treat_start_t = None
            elif etype == "TRANSIT_START":
                transit_start_t = t
            elif etype == "TRANSIT_END":
                if transit_start_t is not None:
                    transit += t - transit_start_t
                    transit_start_t = None

        total = wait + transit + treatment
        if total > 0:
            results.append({
                "casualty": pid,
                "wait": wait,
                "transit": transit,
                "treatment": treatment,
                "hold": 0.0,
                "total": total,
            })

    return results


def render_journey_heatmap(
    events: list[dict[str, Any]],
    T: float,
    focused_casualty: Optional[str] = None,
) -> go.Figure:
    """Plotly heatmap: casualties x phases, colour = duration."""
    phases = compute_journey_phases(events, T)
    phases.sort(key=lambda p: p["total"], reverse=True)

    # Cap at 50 rows: worst 25 + best 25
    if len(phases) > 50:
        phases = phases[:25] + phases[-25:]

    if not phases:
        fig = go.Figure()
        fig.update_layout(height=100, annotations=[
            dict(text="No journey data", x=0.5, y=0.5, showarrow=False)])
        return fig

    casualties = [p["casualty"] for p in phases]
    columns = ["Wait", "Transit", "Treatment", "Hold/PFC"]
    z = [[p["wait"], p["transit"], p["treatment"], p["hold"]] for p in phases]

    fig = go.Figure(data=go.Heatmap(
        z=z, x=columns, y=casualties,
        colorscale=[[0, "#10B981"], [0.5, "#F59E0B"], [1, "#EF4444"]],
        text=[[f"{v:.0f}m" for v in row] for row in z],
        texttemplate="%{text}",
        hovertemplate="<b>%{y}</b><br>%{x}: %{z:.0f} min<extra></extra>",
    ))
    fig.update_layout(
        height=max(300, len(casualties) * 18),
        yaxis=dict(autorange="reversed"),
        xaxis=dict(side="top"),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=80, r=20, t=40, b=20),
    )
    return fig
