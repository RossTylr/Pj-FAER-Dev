"""Process mining analytics for FAER-M event store.

Phase 4 Iter 5. PRD section 7.5.

Provides:
- Bottleneck analysis with wait-to-service ratio (> 2.0 = bottleneck)
- Variant analysis (cluster patients by facility path)
- Throughput metrics (patients per hour)
- Golden hour compliance (% patients reaching definitive care within 60 min)
- Critical path identification
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from faer_dev.events.queries import TemporalQuery
from faer_dev.events.store import EventStore


@dataclass
class BottleneckReport:
    """Bottleneck analysis result for a facility."""

    facility_id: str = ""
    department: Optional[str] = None
    mean_wait_min: float = 0.0
    p95_wait_min: float = 0.0
    max_wait_min: float = 0.0
    total_patients_delayed: int = 0
    max_concurrent_queue: int = 0
    mean_treatment_min: float = 0.0
    wait_service_ratio: float = 0.0  # PRD section 7.5: > 2.0 = bottleneck


@dataclass
class ThroughputReport:
    """Throughput metrics."""

    total_patients: int = 0
    completed_patients: int = 0
    patients_per_hour: float = 0.0
    mean_journey_time_min: float = 0.0
    p95_journey_time_min: float = 0.0


@dataclass
class CriticalPathReport:
    """Critical path analysis result."""

    bottleneck_facility: str = ""
    bottleneck_wait_p95: float = 0.0
    mean_total_time_min: float = 0.0
    golden_hour_pct: float = 0.0


class ProcessMiner:
    """Process mining analytics engine.

    Reads from an EventStore and computes bottleneck analysis,
    variant analysis, throughput, and golden hour compliance.

    Usage::

        miner = ProcessMiner(engine.event_store)
        bottlenecks = miner.bottleneck_analysis()
        variants = miner.variant_analysis()
    """

    def __init__(self, store: EventStore) -> None:
        self._store = store
        self._query = TemporalQuery(store)

    def bottleneck_analysis(
        self,
        exclude_facilities: Optional[List[str]] = None,
    ) -> List[BottleneckReport]:
        """Identify facility bottlenecks ranked by p95 wait time.

        Computes wait-to-service ratio (PRD section 7.5):
        ratio = mean_wait / mean_treatment. Score > 2.0 = bottleneck.

        Args:
            exclude_facilities: Optional list of facility IDs to skip when
                extracting waits from hold events and patient journeys.
        """
        excluded = set(exclude_facilities or [])
        facility_waits: Dict[str, List[float]] = {}
        facility_treatments: Dict[str, List[float]] = {}
        hold_episode_max: Dict[str, Dict[tuple[str, str], float]] = {}

        # Track unique hold episodes from HOLD events.
        for event in self._store.events_of_type("HOLD_START"):
            fid = event.facility_id or "UNKNOWN"
            if fid in excluded:
                continue
            if fid not in facility_waits:
                facility_waits[fid] = []
            cid = event.casualty_id or "UNKNOWN"
            hold_episode_max.setdefault(fid, {})[(cid, fid)] = 0.0

        # Use HOLD_RETRY/HOLD_TIMEOUT max duration per (casualty, facility)
        # episode instead of counting every retry sample.
        for etype in ("HOLD_RETRY", "HOLD_TIMEOUT"):
            for event in self._store.events_of_type(etype):
                fid = event.facility_id or "UNKNOWN"
                if fid in excluded:
                    continue
                cid = event.casualty_id or "UNKNOWN"
                duration = float(getattr(event, "hold_duration_min", 0.0) or 0.0)
                key = (cid, fid)
                current = hold_episode_max.setdefault(fid, {}).get(key, 0.0)
                hold_episode_max[fid][key] = max(current, duration)

        # Materialise episode durations as wait samples.
        for fid, episodes in hold_episode_max.items():
            facility_waits.setdefault(fid, []).extend(episodes.values())

        # Also track treatment times per facility
        for event in self._store.events_of_type("TREATMENT_END"):
            fid = event.facility_id or "UNKNOWN"
            duration = getattr(event, "duration", 0.0)
            if fid not in facility_treatments:
                facility_treatments[fid] = []
            facility_treatments[fid].append(duration)

        # Build per-patient facility wait times from journey analysis
        for cid in self._query.patient_ids():
            journey = self._query.patient_journey(cid)
            _extract_facility_waits(journey, facility_waits, excluded)

        # Build reports
        all_facilities = set(facility_waits.keys()) | set(facility_treatments.keys())
        reports: List[BottleneckReport] = []

        for fid in all_facilities:
            waits = facility_waits.get(fid, [])
            treatments = facility_treatments.get(fid, [])

            report = BottleneckReport(facility_id=fid)

            if waits:
                report.mean_wait_min = statistics.mean(waits)
                report.max_wait_min = max(waits)
                report.total_patients_delayed = len(hold_episode_max.get(fid, {})) or len(waits)
                sorted_waits = sorted(waits)
                idx = int(len(sorted_waits) * 0.95)
                idx = min(idx, len(sorted_waits) - 1)
                report.p95_wait_min = sorted_waits[idx]

            if treatments:
                report.mean_treatment_min = statistics.mean(treatments)

            if report.mean_treatment_min > 0:
                report.wait_service_ratio = report.mean_wait_min / report.mean_treatment_min

            reports.append(report)

        # Rank by p95 wait time descending
        reports.sort(key=lambda r: r.p95_wait_min, reverse=True)
        return reports

    def variant_analysis(self) -> Dict[str, Dict[str, Any]]:
        """Cluster patients by facility path. Compare outcomes per variant.

        PRD section 7.5: Variant Analysis requirement.

        Returns::

            {
                "POI->R1->R2->R3": {"count": 45, "mean_time_min": 180.0},
                "POI->R2->R3": {"count": 12, "mean_time_min": 95.0},
            }
        """
        variants: Dict[str, Dict[str, list]] = {}

        for cid in self._query.patient_ids():
            journey = self._query.patient_journey(cid)
            facilities: List[str] = []
            for e in journey:
                fid = e.facility_id
                if fid and (not facilities or facilities[-1] != fid):
                    facilities.append(fid)
            path = "->".join(facilities)
            if not path:
                continue
            if path not in variants:
                variants[path] = {"patients": [], "times": []}
            total_time = journey[-1].sim_time - journey[0].sim_time if len(journey) > 1 else 0
            variants[path]["patients"].append(cid)
            variants[path]["times"].append(total_time)

        return {
            path: {
                "count": len(data["patients"]),
                "mean_time_min": statistics.mean(data["times"]) if data["times"] else 0.0,
            }
            for path, data in variants.items()
        }

    def throughput(self) -> ThroughputReport:
        """Compute throughput metrics."""
        t_range = self._query.time_range()
        duration_hours = (t_range[1] - t_range[0]) / 60.0 if t_range[1] > t_range[0] else 1.0

        arrivals = self._store.events_of_type("ARRIVAL")
        dispositions = self._store.events_of_type("DISPOSITION")

        journey_times: List[float] = []
        for cid in self._query.patient_ids():
            journey = self._query.patient_journey(cid)
            if len(journey) >= 2:
                journey_times.append(journey[-1].sim_time - journey[0].sim_time)

        report = ThroughputReport(
            total_patients=len(arrivals),
            completed_patients=len(dispositions),
            patients_per_hour=len(arrivals) / duration_hours if duration_hours > 0 else 0.0,
        )

        if journey_times:
            report.mean_journey_time_min = statistics.mean(journey_times)
            sorted_times = sorted(journey_times)
            idx = min(int(len(sorted_times) * 0.95), len(sorted_times) - 1)
            report.p95_journey_time_min = sorted_times[idx]

        return report

    def golden_hour_compliance(self) -> Dict[str, Dict[str, Any]]:
        """Golden hour compliance per triage category.

        Returns % of patients reaching definitive care (R2+) within 60 minutes.
        """
        by_triage: Dict[str, Dict[str, int]] = {}

        for cid in self._query.patient_ids():
            journey = self._query.patient_journey(cid)
            if not journey:
                continue

            # Get triage from first event metadata or attributes
            triage = "UNKNOWN"
            for e in journey:
                t = getattr(e, "triage", "") or getattr(e, "new_triage", "")
                if t:
                    triage = str(t)
                    break

            if triage not in by_triage:
                by_triage[triage] = {"total": 0, "within_60": 0}
            by_triage[triage]["total"] += 1

            # Check if patient reached R2+ within 60 minutes
            arrival_time = journey[0].sim_time
            for e in journey:
                fid = e.facility_id or ""
                if "R2" in fid or "R3" in fid or "R4" in fid:
                    if (e.sim_time - arrival_time) <= 60.0:
                        by_triage[triage]["within_60"] += 1
                    break

        return {
            triage: {
                "total": data["total"],
                "within_60": data["within_60"],
                "compliance_pct": (data["within_60"] / data["total"] * 100) if data["total"] > 0 else 0.0,
            }
            for triage, data in by_triage.items()
        }

    def critical_path(self) -> CriticalPathReport:
        """Identify the critical path bottleneck."""
        bottlenecks = self.bottleneck_analysis()
        throughput = self.throughput()
        golden_hour = self.golden_hour_compliance()

        total_within = sum(d["within_60"] for d in golden_hour.values())
        total_patients = sum(d["total"] for d in golden_hour.values())
        golden_pct = (total_within / total_patients * 100) if total_patients > 0 else 0.0

        report = CriticalPathReport(
            mean_total_time_min=throughput.mean_journey_time_min,
            golden_hour_pct=golden_pct,
        )

        if bottlenecks:
            report.bottleneck_facility = bottlenecks[0].facility_id
            report.bottleneck_wait_p95 = bottlenecks[0].p95_wait_min

        return report


def _extract_facility_waits(
    journey: List[Any],
    facility_waits: Dict[str, List[float]],
    exclude_facilities: Optional[set[str]] = None,
) -> None:
    """Extract wait times from a patient journey.

    Looks for FACILITY_ARRIVAL -> TREATMENT_START pairs to compute wait.
    """
    facility_arrival_times: Dict[str, float] = {}

    for event in journey:
        etype = event.event_type
        fid = event.facility_id or ""
        if fid and exclude_facilities and fid in exclude_facilities:
            continue

        if etype == "FACILITY_ARRIVAL" and fid:
            facility_arrival_times[fid] = event.sim_time
        elif etype == "TREATMENT_START" and fid:
            if fid in facility_arrival_times:
                wait = event.sim_time - facility_arrival_times[fid]
                if wait > 0:
                    if fid not in facility_waits:
                        facility_waits[fid] = []
                    facility_waits[fid].append(wait)
                del facility_arrival_times[fid]
