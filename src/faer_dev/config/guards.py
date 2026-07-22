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


def require_single_poi(scenario: Dict[str, Any]) -> None:
    """INTERIM (BUILD_S3 slice 0, LIFTED at slice 2).

    The engine binds exactly one ``ArrivalProcess`` to one scalar ``_poi_id``,
    so a second POI is parsed, added to the network, and then silently
    starved — it never receives an arrival. Until the N-instance wiring
    lands, say so at construction rather than let a two-POI scenario report
    a plausible single-POI run.
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
    total = len(declared | synthesised)
    if total > 1:
        raise ConfigurationError(
            f"Scenario declares {total} POIs ({sorted(declared | synthesised)}); "
            "multi-POI wiring lands at BUILD_S3 slice 2. Until then only the "
            "first POI would receive arrivals and the rest would be silently "
            "starved."
        )


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
