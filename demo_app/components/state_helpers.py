"""Pure helper functions for Engine Room panels.

All functions take (events, T, ...) and return derived state.
Events are legacy dicts with keys: time, type, patient_id, triage, state, facility, details.

Actual legacy event types (from engine runs):
  ARRIVAL, FACILITY_ARRIVAL, TRANSIT_START, TRANSIT_END,
  TREATMENT_START, TREATMENT_END, DISPOSITION,
  MASCAL_ACTIVATE, MASCAL_DEACTIVATE

No SimPy imports. No Streamlit imports.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def compute_state_at_T(
    events: list[dict[str, Any]],
    T: float,
    topology: dict[str, Any],
) -> dict[str, Any]:
    """Compute facility occupancy and casualty positions at time T.

    Occupancy: +1 on FACILITY_ARRIVAL, -1 on TRANSIT_START and DISPOSITION.
    """
    facility_occupancy: dict[str, int] = defaultdict(int)
    casualty_locations: dict[str, str] = {}
    # Track which patients were counted into occupancy via FACILITY_ARRIVAL
    counted_at: dict[str, str] = {}
    transit_starts: dict[str, tuple[str, str]] = {}  # patient -> (origin, dest)
    route_denials = 0

    # Initialise occupancy at 0 for all known facilities
    for fac in topology.get("facilities", []):
        facility_occupancy[fac["id"]] = 0

    for e in events:
        if e["time"] > T:
            break
        etype = e["type"]
        pid = e.get("patient_id", "")
        fac = e.get("facility", "")

        if etype == "ARRIVAL":
            # ARRIVAL places casualty at POI but no FACILITY_ARRIVAL is
            # emitted for the initial POI. Track location only, not occupancy.
            casualty_locations[pid] = fac

        elif etype == "FACILITY_ARRIVAL":
            facility_occupancy[fac] += 1
            casualty_locations[pid] = fac
            counted_at[pid] = fac
            transit_starts.pop(pid, None)

        elif etype == "TRANSIT_START":
            # Only decrement if patient was counted via FACILITY_ARRIVAL
            if fac and counted_at.get(pid) == fac:
                facility_occupancy[fac] -= 1
                counted_at.pop(pid, None)
            details = e.get("details", {})
            origin = details.get("origin", fac)
            dest = details.get("destination", "")
            transit_starts[pid] = (origin, dest)
            casualty_locations[pid] = f"transit:{origin}->{dest}"

        elif etype == "TRANSIT_END":
            transit_starts.pop(pid, None)

        elif etype == "DISPOSITION":
            # Only decrement if patient was counted via FACILITY_ARRIVAL
            if fac and counted_at.get(pid) == fac:
                facility_occupancy[fac] -= 1
                counted_at.pop(pid, None)
            casualty_locations.pop(pid, None)

        elif etype == "ROUTE_DENIED":
            # Not in legacy events currently, but future-proof
            route_denials += 1

    active_transits = [
        (pid, origin, dest) for pid, (origin, dest) in transit_starts.items()
    ]

    return {
        "facility_occupancy": dict(facility_occupancy),
        "casualty_locations": casualty_locations,
        "active_transits": active_transits,
        "route_denials": route_denials,
    }


def compute_module_activity(
    events: list[dict[str, Any]],
    T: float,
    window: float = 10.0,
) -> dict[str, int]:
    """Count events attributable to each module in [T-window, T]."""
    lo = T - window
    recent = [e for e in events if lo <= e["time"] <= T]
    n = len(recent)

    activity: dict[str, int] = {
        "engine.py": 0,
        "routing.py": 0,
        "pfc.py": 0,
        "BT": 0,
        "Blackboard": 0,
        "emitter.py": n,        # all events pass through emitter
        "EventBus": n,          # all events published to bus
        "AnalyticsEngine": n,   # all events subscribed
        "MASCAL": 0,
    }

    for e in recent:
        etype = e["type"]
        if etype in ("ARRIVAL", "TREATMENT_START", "TREATMENT_END", "DISPOSITION"):
            activity["engine.py"] += 1
        elif etype in ("FACILITY_ARRIVAL", "TRANSIT_START", "TRANSIT_END"):
            activity["routing.py"] += 1
        elif etype in ("PFC_START", "PFC_END", "PFC_CEILING_EXCEEDED"):
            activity["pfc.py"] += 1
        elif etype == "TRIAGE":
            activity["BT"] += 1
            activity["Blackboard"] += 1
        elif etype in ("MASCAL_ACTIVATE", "MASCAL_DEACTIVATE"):
            activity["MASCAL"] += 1

    return activity


def get_last_triage_context(
    events: list[dict[str, Any]],
    T: float,
) -> dict[str, Any] | None:
    """Extract triage context from the most recent ARRIVAL before T.

    TRIAGE events are absent from the legacy dict path — triage category
    lives on ARRIVAL events' "triage" field, injury details in "details".
    """
    last_arrival = None
    for e in events:
        if e["time"] > T:
            break
        if e["type"] == "ARRIVAL":
            last_arrival = e

    if last_arrival is None:
        return None

    details = last_arrival.get("details", {})
    return {
        "casualty": last_arrival.get("patient_id", ""),
        "time": last_arrival["time"],
        "triage_category": last_arrival.get("triage", ""),
        "facility": last_arrival.get("facility", ""),
        "injury_mechanism": details.get("injury_mechanism", ""),
        "severity": details.get("severity", 0.0),
        "recommended_triage": details.get("recommended_triage", ""),
    }


def compute_analytics_at_T(
    events: list[dict[str, Any]],
    T: float,
) -> dict[str, Any]:
    """Compute analytics snapshots from events up to T.

    Walks events manually (cannot reuse AnalyticsEngine which only has
    final-state snapshots, not time-windowed views).
    """
    arrivals: dict[str, float] = {}     # patient -> arrival time
    first_treat: dict[str, float] = {}  # patient -> first treatment time
    facility_occ: dict[str, int] = defaultdict(int)
    peak_load: dict[str, int] = defaultdict(int)
    patient_at: dict[str, str] = {}     # patient -> last FACILITY_ARRIVAL fac
    completed = 0

    for e in events:
        if e["time"] > T:
            break
        etype = e["type"]
        pid = e.get("patient_id", "")
        fac = e.get("facility", "")

        if etype == "ARRIVAL":
            arrivals[pid] = e["time"]

        elif etype == "TREATMENT_START":
            if pid not in first_treat:
                first_treat[pid] = e["time"]

        elif etype == "FACILITY_ARRIVAL":
            facility_occ[fac] += 1
            patient_at[pid] = fac
            if facility_occ[fac] > peak_load[fac]:
                peak_load[fac] = facility_occ[fac]

        elif etype == "TRANSIT_START":
            # Only decrement if patient had a FACILITY_ARRIVAL at this fac
            if fac and patient_at.get(pid) == fac:
                facility_occ[fac] -= 1
                patient_at.pop(pid, None)

        elif etype == "DISPOSITION":
            completed += 1
            if fac and patient_at.get(pid) == fac:
                facility_occ[fac] -= 1
                patient_at.pop(pid, None)

    # Golden hour: mean time from ARRIVAL to first TREATMENT_START
    wait_times = []
    for pid, arr_t in arrivals.items():
        if pid in first_treat:
            wait_times.append(first_treat[pid] - arr_t)
    gh_mean = sum(wait_times) / len(wait_times) if wait_times else 0.0

    # Peak facility
    peak_fac = "—"
    peak_val = 0
    for fac, pk in peak_load.items():
        if pk > peak_val:
            peak_val = pk
            peak_fac = fac

    return {
        "golden_hour_mean": gh_mean,
        "peak_load": peak_val,
        "peak_facility": peak_fac,
        "completed": completed,
    }


def compute_contention_at_T(
    events: list[dict[str, Any]],
    T: float,
) -> int:
    """Count casualties currently waiting (arrived at facility but not yet treated).

    A patient is 'waiting' if they have a FACILITY_ARRIVAL at some facility
    but no subsequent TREATMENT_START at that same facility before T.
    Resets on new FACILITY_ARRIVAL. Removed on DISPOSITION/TRANSIT_START.
    """
    waiting_at: dict[str, str] = {}   # patient -> facility they're waiting at
    treated: set[str] = set()

    for e in events:
        if e["time"] > T:
            break
        etype = e["type"]
        pid = e.get("patient_id", "")

        if etype == "FACILITY_ARRIVAL":
            waiting_at[pid] = e.get("facility", "")
            treated.discard(pid)
        elif etype == "TREATMENT_START":
            treated.add(pid)
            waiting_at.pop(pid, None)
        elif etype in ("DISPOSITION", "TRANSIT_START"):
            waiting_at.pop(pid, None)
            treated.discard(pid)

    return len(waiting_at)
