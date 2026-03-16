"""Ensemble builder — run N replications and aggregate statistics.

Reuses the builder API (Issue #4 fix) with per-replication seeds.
Produces EnsembleSnapshot with mean, std, and confidence intervals
for key metrics extracted from event stores.

Phase 4 Iter 3 (extended in Phase 4.5.1b: snapshot_at, time_series,
triage_by_facility_at, AggStat convenience methods).
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from faer_dev.config.builder import build_engine_from_preset
from faer_dev.decisions.mode import SimulationToggles
from faer_dev.events.store import EventStore

logger = logging.getLogger(__name__)


@dataclass
class AggStat:
    """Aggregated statistic across replications.

    Computes mean, std, and 95% confidence interval.
    """

    values: List[float] = field(default_factory=list)

    @classmethod
    def from_values(cls, vals: List[float]) -> AggStat:
        """Convenience constructor from a list of values."""
        return cls(values=list(vals))

    @property
    def n(self) -> int:
        return len(self.values)

    @property
    def mean(self) -> float:
        if not self.values:
            return 0.0
        return sum(self.values) / len(self.values)

    @property
    def std(self) -> float:
        if len(self.values) < 2:
            return 0.0
        m = self.mean
        variance = sum((v - m) ** 2 for v in self.values) / (len(self.values) - 1)
        return math.sqrt(variance)

    @property
    def ci_95(self) -> tuple[float, float]:
        """95% confidence interval (mean +/- 1.96 * std/sqrt(n))."""
        if len(self.values) < 2:
            return (self.mean, self.mean)
        se = self.std / math.sqrt(len(self.values))
        return (self.mean - 1.96 * se, self.mean + 1.96 * se)

    @property
    def ci_lower(self) -> float:
        """Lower bound of 95% CI. Convenience for ci_95[0]."""
        return self.ci_95[0]

    @property
    def ci_upper(self) -> float:
        """Upper bound of 95% CI. Convenience for ci_95[1]."""
        return self.ci_95[1]

    def to_dict(self) -> Dict[str, Any]:
        lo, hi = self.ci_95
        return {
            "n": self.n,
            "mean": round(self.mean, 4),
            "std": round(self.std, 4),
            "ci_95_lo": round(lo, 4),
            "ci_95_hi": round(hi, 4),
        }


@dataclass
class EnsembleSnapshot:
    """Aggregated results across N replications.

    Contains per-metric AggStat objects and per-replication event stores.
    """

    preset: str
    n_replications: int
    total_events: AggStat = field(default_factory=AggStat)
    completed_patients: AggStat = field(default_factory=AggStat)
    event_type_counts: Dict[str, AggStat] = field(default_factory=dict)
    stores: List[EventStore] = field(default_factory=list)
    # Phase 4.5.1b additions (backward compatible defaults)
    sim_time: float = 0.0
    facility_occupancy: Dict[str, AggStat] = field(default_factory=dict)
    patients_in_system: Optional[AggStat] = None
    mascal_active_proportion: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "preset": self.preset,
            "n_replications": self.n_replications,
            "total_events": self.total_events.to_dict(),
            "completed_patients": self.completed_patients.to_dict(),
            "event_type_counts": {
                k: v.to_dict() for k, v in self.event_type_counts.items()
            },
            "sim_time": self.sim_time,
            "mascal_active_proportion": self.mascal_active_proportion,
        }
        if self.facility_occupancy:
            result["facility_occupancy"] = {
                k: v.to_dict() for k, v in self.facility_occupancy.items()
            }
        if self.patients_in_system is not None:
            result["patients_in_system"] = self.patients_in_system.to_dict()
        return result


class EnsembleBuilder:
    """Run N replications of a preset and aggregate results.

    Uses builder seed= param (Issue #4 fix) for per-replication seeds.

    After calling run(), snapshot_at(t), time_series(), and
    triage_by_facility_at(t) become available for post-hoc analysis.

    Usage::

        builder = EnsembleBuilder("coin", n_replications=10, base_seed=42)
        snapshot = builder.run(duration=600.0, poi_id="POI-1", max_patients=50)
        print(snapshot.total_events.mean, snapshot.completed_patients.ci_95)

        # Post-hoc analysis
        snap_120 = builder.snapshot_at(120.0)
        ts = builder.time_series(0, 600, n_points=20)
    """

    def __init__(
        self,
        preset: str,
        n_replications: int = 10,
        base_seed: int = 42,
        patient_seed: Optional[int] = None,
        toggles: Optional[SimulationToggles] = None,
    ) -> None:
        """
        Args:
            preset: Scenario preset name (coin, lsco, hadr, specops).
            n_replications: Number of replications to run.
            base_seed: Base random seed; replication i uses base_seed + i.
            patient_seed: Reserved for CRN mode. Requires dual-seed engine
                support (not yet available). Accepted for API stability but
                currently has no effect on seed assignment.
            toggles: Simulation feature toggles.
        """
        self.preset = preset
        self.n_replications = n_replications
        self.base_seed = base_seed
        self.patient_seed = patient_seed  # Inert until engine supports dual seeds
        self.toggles = toggles or SimulationToggles()
        self._stores: List[EventStore] = []

    def run(
        self,
        duration: float = 600.0,
        poi_id: Optional[str] = None,
        max_patients: Optional[int] = None,
    ) -> EnsembleSnapshot:
        """Run all replications and return aggregated snapshot."""
        snapshot = EnsembleSnapshot(
            preset=self.preset,
            n_replications=self.n_replications,
        )

        for i in range(self.n_replications):
            rep_seed = self.base_seed + i
            logger.info(
                "Ensemble replication %d/%d (seed=%d)",
                i + 1, self.n_replications, rep_seed,
            )

            engine = build_engine_from_preset(
                self.preset, seed=rep_seed, toggles=self.toggles,
            )
            metrics = engine.run(
                duration=duration,
                poi_id=poi_id,
                max_patients=max_patients,
            )

            # Collect per-replication stats
            snapshot.total_events.values.append(float(engine.event_store.count))
            snapshot.completed_patients.values.append(float(metrics.get("completed", 0)))
            snapshot.stores.append(engine.event_store)

            # Per-type counts
            for etype in engine.event_store.event_types:
                if etype not in snapshot.event_type_counts:
                    # Backfill zeros for previous replications
                    snapshot.event_type_counts[etype] = AggStat(
                        values=[0.0] * i
                    )
                count = len(engine.event_store.events_of_type(etype))
                snapshot.event_type_counts[etype].values.append(float(count))

            # Backfill zeros for types seen in previous reps but not this one
            current_types = engine.event_store.event_types
            for etype, agg in snapshot.event_type_counts.items():
                if etype not in current_types and len(agg.values) <= i:
                    agg.values.append(0.0)

        self._stores = list(snapshot.stores)
        return snapshot

    # ------------------------------------------------------------------
    # Post-hoc analysis (require run() to have been called)
    # ------------------------------------------------------------------

    def _check_stores(self, method_name: str) -> None:
        if not self._stores:
            raise ValueError(
                f"No event stores available. Call run() before {method_name}()."
            )

    def snapshot_at(self, t: float) -> EnsembleSnapshot:
        """Reconstruct ensemble state at time T.

        Must call run() first to populate event stores.

        Raises:
            ValueError: If run() has not been called yet.
        """
        self._check_stores("snapshot_at")
        from faer_dev.events.replay import ReplayEngine

        facility_occupancies: Dict[str, List[float]] = defaultdict(list)
        patients_in_system: List[float] = []
        patients_completed: List[float] = []
        mascal_active_count = 0

        for store in self._stores:
            replay = ReplayEngine(store)
            snap = replay.replay_to(t)

            patients_in_system.append(float(len(snap.active_patients)))
            completed = len([
                p for p in snap.patients.values()
                if p.state == "COMPLETED"
            ])
            patients_completed.append(float(completed))

            if snap.mascal_active:
                mascal_active_count += 1

            for fid, fstate in snap.facilities.items():
                facility_occupancies[fid].append(float(fstate.occupancy))

        return EnsembleSnapshot(
            preset=self.preset,
            n_replications=self.n_replications,
            sim_time=t,
            facility_occupancy={
                fid: AggStat(values=occs)
                for fid, occs in facility_occupancies.items()
            },
            patients_in_system=AggStat(values=patients_in_system),
            completed_patients=AggStat(values=patients_completed),
            mascal_active_proportion=(
                mascal_active_count / len(self._stores)
            ),
            total_events=AggStat(),
            event_type_counts={},
            stores=self._stores,
        )

    def time_series(
        self,
        t_start: float,
        t_end: float,
        n_points: int = 50,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> List[EnsembleSnapshot]:
        """Generate time series of ensemble snapshots.

        Must call run() first. Returns n_points evenly spaced snapshots.
        Optional progress_callback(fraction) for UI progress bars.

        Raises:
            ValueError: If run() has not been called yet.
        """
        self._check_stores("time_series")
        import numpy as np

        times = np.linspace(t_start, t_end, n_points)
        results: List[EnsembleSnapshot] = []
        for i, t in enumerate(times):
            results.append(self.snapshot_at(float(t)))
            if progress_callback:
                progress_callback((i + 1) / n_points)
        return results

    _ALL_TRIAGE = ["T1_SURGICAL", "T1_MEDICAL", "T2", "T3", "T4"]

    def triage_by_facility_at(
        self, t: float,
    ) -> Dict[str, Dict[str, AggStat]]:
        """Per-facility triage distribution at time T.

        Patients with blank/unknown triage are excluded from the
        denominator. Proportions sum to 1.0 for triaged patients only.
        Returns empty dict if no facilities exist at time T.

        Must call run() first.

        Raises:
            ValueError: If run() has not been called yet.
        """
        self._check_stores("triage_by_facility_at")
        from faer_dev.events.replay import ReplayEngine

        facility_triage: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

        for i, store in enumerate(self._stores):
            replay = ReplayEngine(store)
            snap = replay.replay_to(t)

            facilities_seen_this_rep = set()
            for fid, fstate in snap.facilities.items():
                facilities_seen_this_rep.add(fid)
                triage_counts: Dict[str, int] = defaultdict(int)
                for pid in fstate.current_patients:
                    psnap = snap.patients.get(pid)
                    if psnap and psnap.triage in self._ALL_TRIAGE:
                        triage_counts[psnap.triage] += 1

                total = sum(triage_counts.values())
                for triage in self._ALL_TRIAGE:
                    proportion = (
                        triage_counts[triage] / total if total > 0 else 0.0
                    )
                    facility_triage[fid][triage].append(proportion)

            # Backfill zeros for facilities seen in earlier reps but absent here
            for fid in facility_triage:
                if fid not in facilities_seen_this_rep:
                    for triage in self._ALL_TRIAGE:
                        facility_triage[fid][triage].append(0.0)

        # Pad facilities that first appeared in later reps (missing leading zeros)
        n = len(self._stores)
        for fid, triages in facility_triage.items():
            for triage in self._ALL_TRIAGE:
                while len(triages[triage]) < n:
                    triages[triage].insert(0, 0.0)

        return {
            fid: {
                triage: AggStat(values=proportions)
                for triage, proportions in triages.items()
            }
            for fid, triages in facility_triage.items()
        }
