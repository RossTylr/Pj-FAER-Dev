"""Materialised views for simulation analytics.

Each view receives events via update() and maintains aggregated state.
snapshot() returns a dict of current values.
All views are O(1) amortised per event — no full-store scans.

Zero SimPy imports. Reads only typed event fields.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List

import numpy as np


class OutcomeView:
    """Tracks outcome distribution from DISPOSITION events."""

    def __init__(self) -> None:
        self._outcomes: Counter = Counter()
        self._total: int = 0

    def update(self, event: Any) -> None:
        if event.event_type == "DISPOSITION":
            outcome = getattr(event, "outcome", None)
            if not outcome:
                outcome = event.metadata.get("outcome", "UNKNOWN")
            self._outcomes[str(outcome)] += 1
            self._total += 1

    def snapshot(self) -> Dict[str, Any]:
        return {
            "total_dispositions": self._total,
            "outcomes": dict(self._outcomes),
        }

    def reset(self) -> None:
        self._outcomes.clear()
        self._total = 0


class FacilityLoadView:
    """Tracks concurrent occupancy per facility over time."""

    def __init__(self) -> None:
        self._current_load: Dict[str, int] = defaultdict(int)
        self._peak_load: Dict[str, int] = defaultdict(int)
        self._arrivals: Dict[str, int] = defaultdict(int)

    def update(self, event: Any) -> None:
        fac = getattr(event, "facility_id", None)
        if not fac:
            return

        if event.event_type == "FACILITY_ARRIVAL":
            self._current_load[fac] += 1
            self._arrivals[fac] += 1
            self._peak_load[fac] = max(
                self._peak_load[fac],
                self._current_load[fac],
            )
        elif event.event_type == "DISPOSITION":
            self._current_load[fac] = max(0, self._current_load[fac] - 1)

    def snapshot(self) -> Dict[str, Any]:
        return {
            fac: {
                "current": self._current_load[fac],
                "peak": self._peak_load[fac],
                "total_arrivals": self._arrivals.get(fac, 0),
            }
            for fac in sorted(set(self._peak_load) | set(self._arrivals))
        }

    def reset(self) -> None:
        self._current_load.clear()
        self._peak_load.clear()
        self._arrivals.clear()


class GoldenHourView:
    """Tracks time from arrival to first R2+ treatment by triage category."""

    def __init__(self) -> None:
        self._arrival_times: Dict[str, float] = {}
        self._triage_map: Dict[str, str] = {}
        self._golden_hours: List[float] = []

    def update(self, event: Any) -> None:
        if event.event_type == "ARRIVAL" and event.casualty_id:
            self._arrival_times[event.casualty_id] = event.sim_time
            triage = getattr(event, "triage", "")
            if triage:
                self._triage_map[event.casualty_id] = str(triage)
        elif event.event_type == "DISPOSITION" and event.casualty_id:
            arrival = self._arrival_times.get(event.casualty_id)
            if arrival is not None:
                self._golden_hours.append(event.sim_time - arrival)

    def snapshot(self) -> Dict[str, Any]:
        if not self._golden_hours:
            return {
                "mean_minutes": 0.0,
                "median_minutes": 0.0,
                "pct_within_60": 0.0,
                "total_tracked": 0,
            }
        return {
            "mean_minutes": float(np.mean(self._golden_hours)),
            "median_minutes": float(np.median(self._golden_hours)),
            "pct_within_60": sum(1 for g in self._golden_hours if g <= 60.0)
            / len(self._golden_hours),
            "total_tracked": len(self._golden_hours),
        }

    def reset(self) -> None:
        self._arrival_times.clear()
        self._triage_map.clear()
        self._golden_hours.clear()
