"""Bottleneck detector — identifies facility with worst queue at time T.

Displays as a coloured alert card: green (flowing), amber (moderate),
red (critical). No SimPy imports.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

import streamlit as st


def detect_bottleneck(
    events: list[dict[str, Any]],
    T: float,
    window: float = 60.0,
) -> Optional[dict[str, Any]]:
    """Find facility with worst wait-to-treatment ratio in [T-window, T].

    For each facility, count:
    - waiting: patients with FACILITY_ARRIVAL but no TREATMENT_START
    - treating: patients with TREATMENT_START but no TREATMENT_END

    Returns dict with facility, waiting, treating, ratio, est_wait_minutes.
    Returns None if no facilities have activity.
    """
    lo = T - window
    # Track per-facility state
    fac_waiting: dict[str, set[str]] = defaultdict(set)
    fac_treating: dict[str, set[str]] = defaultdict(set)

    for e in events:
        if e["time"] > T:
            break
        if e["time"] < lo:
            continue
        etype = e["type"]
        pid = e.get("patient_id", "")
        fac = e.get("facility", "")
        if not fac or not pid:
            continue

        if etype == "FACILITY_ARRIVAL":
            fac_waiting[fac].add(pid)
            fac_treating[fac].discard(pid)
        elif etype == "TREATMENT_START":
            fac_waiting[fac].discard(pid)
            fac_treating[fac].add(pid)
        elif etype == "TREATMENT_END":
            fac_treating[fac].discard(pid)
        elif etype in ("DISPOSITION", "TRANSIT_START"):
            fac_waiting[fac].discard(pid)
            fac_treating[fac].discard(pid)

    worst: Optional[dict[str, Any]] = None
    worst_ratio = -1.0

    all_facs = set(fac_waiting.keys()) | set(fac_treating.keys())
    for fac in all_facs:
        w = len(fac_waiting[fac])
        t = len(fac_treating[fac])
        ratio = w / max(t, 1)
        if ratio > worst_ratio:
            worst_ratio = ratio
            # Rough estimate: each waiting patient waits avg treatment time
            # Use 30 min as a default treatment duration estimate
            est_wait = w * 30.0 / max(t, 1)
            worst = {
                "facility": fac,
                "waiting": w,
                "treating": t,
                "ratio": ratio,
                "est_wait_minutes": est_wait,
            }

    return worst


def render_bottleneck_alert(events: list[dict[str, Any]], T: float) -> None:
    """Display bottleneck as a coloured alert card."""
    bottleneck = detect_bottleneck(events, T)

    if bottleneck is None or bottleneck["waiting"] == 0:
        st.success("System flowing — no bottleneck")
    elif bottleneck["ratio"] < 2.0:
        st.warning(
            f"Moderate queue at **{bottleneck['facility']}** — "
            f"{bottleneck['waiting']} waiting, "
            f"est. {bottleneck['est_wait_minutes']:.0f} min"
        )
    else:
        st.error(
            f"Critical bottleneck at **{bottleneck['facility']}** — "
            f"{bottleneck['waiting']} waiting, "
            f"est. {bottleneck['est_wait_minutes']:.0f} min"
        )
