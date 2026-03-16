# NB37: Pattern E Analytics Decoupling Proof
## Claude Code Instruction File

---

## Objective

Build an `AnalyticsEngine` that subscribes to the EventBus (CP-2) and computes
materialised views (survivability, facility load, golden hour) from the typed
event stream. Dashboard reads views, never engine state. This is Pattern E —
the cheapest structural separation because CP-2 is already the lowest-coupling
boundary in the system.

## Prerequisites

- NB36 complete (typed emitter publishing real events — K-7 closed)
- EventBus/EventLog has a working `subscribe()` mechanism

## What You're Building (Not Extracting)

This is NEW infrastructure, not extracted from engine.py. It consumes the
typed events that NB36's emitter now publishes correctly.

## Target Modules

### `src/faer_dev/analytics/engine.py`

```python
"""AnalyticsEngine — cold-path event subscriber (Pattern E).

Subscribes to EventBus. Never touches SimPy. Never reads engine state.
Materialises views that the dashboard reads via get_view().
"""
from __future__ import annotations
from typing import Dict, Any, Protocol


class MaterialisedView(Protocol):
    """Base protocol for analytics views."""
    def update(self, event) -> None: ...
    def snapshot(self) -> Dict[str, Any]: ...
    def reset(self) -> None: ...


class AnalyticsEngine:
    """Cold-path analytics. Subscribes to EventBus. Zero SimPy contact.

    RULES:
    - _on_event() is called synchronously during emit (between yields)
    - View.update() must be O(1) amortised — counter increments, not scans
    - If a view is slow, it will add latency to the hot path
    - For Monte Carlo: call reset() between replications
    """

    def __init__(self, event_bus):
        self._views: Dict[str, MaterialisedView] = {}
        event_bus.subscribe(self._on_event)

    def register_view(self, name: str, view: MaterialisedView) -> None:
        self._views[name] = view

    def _on_event(self, event) -> None:
        for view in self._views.values():
            view.update(event)

    def get_view(self, name: str) -> Dict[str, Any]:
        return self._views[name].snapshot()

    def reset_all(self) -> None:
        """Reset all views between Monte Carlo replications."""
        for view in self._views.values():
            view.reset()
```

### `src/faer_dev/analytics/views.py`

```python
"""Materialised views for simulation analytics.

Each view receives events via update() and maintains aggregated state.
snapshot() returns a frozen dict of current values.
All views are O(1) amortised per event — no full-store scans.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from typing import Dict, Any, List
import numpy as np


class GoldenHourView:
    """Tracks time from injury to first treatment by triage category."""

    def __init__(self):
        self._arrival_times: Dict[str, float] = {}
        self._treatment_times: Dict[str, float] = {}
        self._triage_map: Dict[str, str] = {}

    def update(self, event) -> None:
        if event.event_type == "ARRIVAL":
            self._arrival_times[event.casualty_id] = event.sim_time
        elif event.event_type == "TRIAGED":
            self._triage_map[event.casualty_id] = event.detail
        elif event.event_type == "TREATED":
            if event.casualty_id not in self._treatment_times:
                self._treatment_times[event.casualty_id] = event.sim_time

    def snapshot(self) -> Dict[str, Any]:
        by_triage = defaultdict(list)
        for cas_id, treat_time in self._treatment_times.items():
            arrival = self._arrival_times.get(cas_id, 0.0)
            triage = self._triage_map.get(cas_id, "UNKNOWN")
            by_triage[triage].append(treat_time - arrival)
        return {
            cat: {"mean": np.mean(times), "median": np.median(times), "n": len(times)}
            for cat, times in by_triage.items()
        }

    def reset(self) -> None:
        self._arrival_times.clear()
        self._treatment_times.clear()
        self._triage_map.clear()


class FacilityLoadView:
    """Tracks concurrent occupancy per facility over time."""

    def __init__(self):
        self._current_load: Dict[str, int] = defaultdict(int)
        self._peak_load: Dict[str, int] = defaultdict(int)

    def update(self, event) -> None:
        if event.event_type == "ARRIVAL" and event.facility_id:
            self._current_load[event.facility_id] += 1
            self._peak_load[event.facility_id] = max(
                self._peak_load[event.facility_id],
                self._current_load[event.facility_id],
            )
        elif event.event_type == "DISCHARGED" and event.facility_id:
            self._current_load[event.facility_id] = max(
                0, self._current_load[event.facility_id] - 1)

    def snapshot(self) -> Dict[str, Any]:
        return {fac: {"current": self._current_load[fac], "peak": self._peak_load[fac]}
                for fac in self._peak_load}

    def reset(self) -> None:
        self._current_load.clear()
        self._peak_load.clear()


class SurvivabilityView:
    """Computes survivability statistics from disposition events."""

    def __init__(self):
        self._outcomes: List[Dict] = []

    def update(self, event) -> None:
        if event.event_type == "DISCHARGED":
            self._outcomes.append({
                "casualty_id": event.casualty_id,
                "time": event.sim_time,
            })

    def snapshot(self) -> Dict[str, Any]:
        return {
            "total_dispositions": len(self._outcomes),
            "mean_time_to_disposition": np.mean([o["time"] for o in self._outcomes])
                if self._outcomes else 0.0,
        }

    def reset(self) -> None:
        self._outcomes.clear()
```

## Notebook Structure (NB37)

### Cell 1: Run engine with TypedEmitter, capture baseline metrics
### Cell 2: Define AnalyticsEngine + views inline
### Cell 3: Wire analytics to EventBus, re-run
### Cell 4: Compare analytics view output vs compute_metrics() baseline
### Cell 5: Performance — measure overhead per event (<1ms target)
### Cell 6: Memory — run 1,000 casualties, check analytics memory is O(views)
### Cell 7: Monte Carlo proof — run 3 replications with reset_all() between

## Success Criteria

- [ ] View snapshots match compute_metrics() baseline values
- [ ] Per-event overhead < 1ms
- [ ] Memory bounded (views only, not full event history)
- [ ] reset_all() works for Monte Carlo replications
- [ ] AnalyticsEngine has zero SimPy imports
- [ ] Dashboard CAN read get_view(), engine state NOT needed

## Estimated Effort

- AnalyticsEngine: ~50 LOC
- 3 views: ~150 LOC
- Notebook: ~100 LOC
- **Total: ~300 LOC across 3 iterations (days 6-7)**
