"""Scenario and toggle guard family (BUILD_S2 slice 1, GM-3/GM-5 lineage).

Silent defaults are the defect class this programme keeps excavating: a
world that is accidentally empty, a spawn point that feeds nothing, an
analysis run on the capability-blind legacy walk. Each guard turns one of
those silences into a construction-time error.

Pure module: no SimPy, no Streamlit (Hard Rule 5).
"""

from __future__ import annotations

from typing import Any, Dict

from faer_dev.core.exceptions import ConfigurationError


def require_facilities(scenario: Dict[str, Any]) -> None:
    """Empty or absent ``facilities`` raises (gate ruling 2026-07-07: RAISE).

    A legitimate empty-world use case can earn an explicit ``allow_empty``
    flag later; what it may not be is silent.
    """
    if not scenario.get("facilities"):
        raise ConfigurationError(
            "Scenario has no facilities. An empty world must be requested "
            "explicitly (allow_empty flag — deferred), never defaulted into."
        )


def require_role_presence(scenario: Dict[str, Any]) -> None:
    """The scenario must contain a casualty source and somewhere to treat.

    Without a POI, arrivals never start and the run is silently empty;
    without a non-POI facility, every journey dead-ends at spawn.
    """
    facilities = scenario.get("facilities") or []
    roles = {str(f.get("role", "")).upper() for f in facilities}
    edge_poi = any(
        str(e.get("from", "")).upper().startswith("POI")
        for e in scenario.get("edges") or []
    )
    if "POI" not in roles and not edge_poi:
        raise ConfigurationError(
            "Scenario has no POI (facility role or POI-prefixed edge "
            "source): arrivals would never start."
        )
    if not (roles - {"POI", ""}):
        raise ConfigurationError(
            "Scenario has no treatment facility (only POI roles present): "
            "every journey would dead-end at spawn."
        )


def count_pois(scenario: Dict[str, Any]) -> int:
    """How many POIs a scenario spawns from.

    Declared POI facilities plus any POI-prefixed edge source the builder
    would synthesise. One definition, used by both the arrival weights
    guard and the scenario stamp, so they cannot disagree.
    """
    facilities = scenario.get("facilities") or []
    declared = {
        str(f.get("id")) for f in facilities
        if str(f.get("role", "")).upper() in ("POI", "0")
    }
    synthesised = {
        str(e.get("from")) for e in scenario.get("edges") or []
        if str(e.get("from", "")).upper().startswith("POI")
    } - {str(f.get("id")) for f in facilities}
    return len(declared | synthesised)


def require_arrival_weights_sum(scenario: Dict[str, Any]) -> None:
    """``arrivals.per_poi`` weights are SHARES and must sum to 1.0 +/- eps.

    Weights preserve the theatre arrival total, which is what keeps MASCAL
    detector tuning stable across POI counts (AC-1.1, S3-AMEND-3). Rates
    that silently sum to 1.4 would inflate the whole theatre and no
    assertion downstream would notice.

    Mirrors SimulationConfig.validate_distribution's tolerance.
    """
    per_poi = (scenario.get("arrivals") or {}).get("per_poi")
    if not per_poi:
        return
    total = sum(float(v) for v in per_poi.values())
    if abs(total - 1.0) > 0.01:
        raise ConfigurationError(
            f"arrivals.per_poi weights sum to {total:.4f}, not 1.0 "
            f"(+/-0.01): {per_poi}. Weights are shares of the theatre "
            "arrival rate, not independent rates."
        )
    known = {str(f.get("id")) for f in scenario.get("facilities") or []}
    unknown = {str(k) for k in per_poi} - known
    if unknown:
        raise ConfigurationError(
            f"arrivals.per_poi names unknown facilities: {sorted(unknown)}"
        )


def require_comparable_arms(stamp_a: str, stamp_b: str) -> None:
    """Two ensemble arms may only be compared at equal POI count.

    The keying is asymmetric by design: a single-POI scenario keeps the
    bare stream literals and CAS-NNNN uids (preserving every committed
    digest), while N>=2 gets per-POI scoped streams and prefixed uids. Arms
    that differ in POI count therefore differ in KEY SCHEMA, so their draws
    are not paired and any measured difference is uninterpretable — the
    Hard-Rule-8 failure mode, caught here rather than published.
    """
    a, b = poi_count_from_stamp(stamp_a), poi_count_from_stamp(stamp_b)
    if a is not None and b is not None and a != b:
        raise ConfigurationError(
            f"cross-arm comparison at different POI counts ({a} vs {b}): "
            "the arms use different RNG key schemas (bare stream literals "
            "at N=1, POI-scoped at N>=2), so their draws are not paired. "
            "Compare like with like."
        )


def poi_count_from_stamp(stamp: str) -> Any:
    """Read the POI count a scenario stamp carries, or None if absent."""
    _, _, suffix = str(stamp).partition(":poi")
    return int(suffix) if suffix.isdigit() else None


def require_analysis_toggles(toggles: Any) -> None:
    """GM-3 capability-ON interim rule: every analysis/doctrine scenario
    sets capability (+extracted) routing until the legacy-walk retirement
    milestone (GM-4). Enforcement home: EnsembleBuilder(analysis=True)."""
    if not (
        toggles.enable_extracted_routing and toggles.enable_capability_routing
    ):
        raise ConfigurationError(
            "Analysis runs require enable_extracted_routing and "
            "enable_capability_routing (GM-3 capability-ON interim rule; "
            "retires with the legacy walk at GM-4)."
        )
