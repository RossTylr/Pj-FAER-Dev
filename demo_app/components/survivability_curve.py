"""Survivability curve — scatter of time since injury vs P(survival).

Each active casualty as a dot. Dots drift right and downward as time
passes without treatment. Treated casualties stabilise.
"""
from __future__ import annotations

import math
from typing import Any, Optional

import plotly.graph_objects as go


_TRIAGE_COLOURS = {
    "T1_SURGICAL": "#EF4444", "T1_MEDICAL": "#EF4444", "T1": "#EF4444",
    "T2": "#F59E0B", "T3": "#10B981", "T4": "#6B7280",
}


def compute_survivability_at_T(
    events: list[dict[str, Any]],
    T: float,
) -> list[dict[str, Any]]:
    """For each casualty active at time T, compute current P(survival).

    Uses logistic: logit = 3.0 - 4.0*severity - 0.8*min(t/60, 5.0)
    Treatment adds +1.5 to logit (stabilisation).
    """
    arrivals: dict[str, dict] = {}       # pid -> arrival event
    treated: set[str] = set()
    disposed: set[str] = set()

    for e in events:
        if e["time"] > T:
            break
        pid = e.get("patient_id", "")
        etype = e["type"]

        if etype == "ARRIVAL":
            arrivals[pid] = e
        elif etype == "TREATMENT_START":
            treated.add(pid)
        elif etype == "DISPOSITION":
            disposed.add(pid)

    results = []
    for pid, arr in arrivals.items():
        if pid in disposed:
            continue
        details = arr.get("details", {})
        severity = details.get("severity", 0.5)
        triage = arr.get("triage", "T2")
        time_since = T - arr["time"]
        time_factor = min(time_since / 60.0, 5.0)

        logit = 3.0 - 4.0 * severity - 0.8 * time_factor
        if pid in treated:
            logit += 1.5
        p_survival = 1.0 / (1.0 + math.exp(-logit))

        results.append({
            "casualty": pid,
            "time_since_injury": time_since,
            "p_survival": p_survival,
            "triage": triage,
            "is_treated": pid in treated,
            "severity": severity,
        })

    return results


def render_survivability_curve(
    events: list[dict[str, Any]],
    T: float,
    focused_casualty: Optional[str] = None,
) -> go.Figure:
    """Scatter: time since injury vs P(survival), coloured by triage."""
    data = compute_survivability_at_T(events, T)

    fig = go.Figure()
    for d in data:
        opacity = 1.0
        if focused_casualty and d["casualty"] != focused_casualty:
            opacity = 0.15
        colour = _TRIAGE_COLOURS.get(d["triage"], "#6B7280")

        fig.add_trace(go.Scatter(
            x=[d["time_since_injury"]], y=[d["p_survival"]],
            mode="markers",
            marker=dict(size=7, color=colour, opacity=opacity),
            showlegend=False,
            hovertemplate=(
                f"<b>{d['casualty']}</b> ({d['triage']})<br>"
                f"P(surv): {d['p_survival']:.2f}<br>"
                f"Time: {d['time_since_injury']:.0f} min<br>"
                f"{'Treated' if d['is_treated'] else 'Waiting'}"
                f"<extra></extra>"
            ),
        ))

    # Golden hour line
    fig.add_vline(x=60, line_dash="dash", line_color="rgba(239,68,68,0.3)",
                  annotation_text="Golden Hour",
                  annotation_font_color="#EF4444")

    fig.update_layout(
        xaxis_title="Time Since Injury (minutes)",
        yaxis_title="P(survival)",
        yaxis=dict(range=[0, 1.05]),
        height=300,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=20, b=40),
    )
    return fig
