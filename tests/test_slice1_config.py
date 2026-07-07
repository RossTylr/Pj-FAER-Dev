"""BUILD_S2 slice 1 — guard family, version stamp, triage_distribution
wire, scenario_overrides API.

Rulings under test (gate, 2026-07-07): empty-facilities = RAISE ·
triage_distribution = WIRE (O2 polices the band; the wiring test here is
the direct-shape check). Fixtures are inline dicts (house pattern).
"""

import pytest

from faer_dev.config.builder import (
    apply_scenario_overrides,
    build_engine_from_dict,
    get_preset_raw,
    scenario_stamp,
)
from faer_dev.config.guards import require_analysis_toggles
from faer_dev.core.exceptions import ConfigurationError
from faer_dev.decisions.mode import SimulationToggles
from faer_dev.events.ensemble import EnsembleBuilder

from tests.harness import run_to_log


def _minimal_scenario(**kw) -> dict:
    scenario = {
        "name": "slice1_minimal",
        "operational_context": "COIN",
        "arrivals": {"base_rate_per_hour": 6.0, "enable_mascal": False},
        "facilities": [
            {"id": "POI-1", "name": "POI", "role": "POI", "beds": 0,
             "coordinates": [0.0, 0.0]},
            {"id": "R1-A", "name": "BAS", "role": "R1", "beds": 4,
             "coordinates": [10.0, 0.0]},
        ],
        "edges": [
            {"from": "POI-1", "to": "R1-A", "travel_time_minutes": 20,
             "transport": "GROUND"},
        ],
    }
    scenario.update(kw)
    return scenario


# ---------------------------------------------------------------------------
# Guard family
# ---------------------------------------------------------------------------

def test_empty_facilities_raises():
    """Ruling: RAISE — an empty world must be explicit, never silent."""
    with pytest.raises(ConfigurationError, match="no facilities"):
        build_engine_from_dict(_minimal_scenario(facilities=[]))


def test_absent_facilities_key_raises():
    scenario = _minimal_scenario()
    del scenario["facilities"]
    with pytest.raises(ConfigurationError, match="no facilities"):
        build_engine_from_dict(scenario)


def test_no_poi_raises():
    scenario = _minimal_scenario()
    scenario["facilities"] = [f for f in scenario["facilities"]
                              if f["role"] != "POI"]
    scenario["edges"] = []
    with pytest.raises(ConfigurationError, match="no POI"):
        build_engine_from_dict(scenario)


def test_poi_only_raises():
    scenario = _minimal_scenario()
    scenario["facilities"] = [f for f in scenario["facilities"]
                              if f["role"] == "POI"]
    scenario["edges"] = []
    with pytest.raises(ConfigurationError, match="no treatment facility"):
        build_engine_from_dict(scenario)


def test_gm3_analysis_guard():
    """GM-3: analysis runs must be capability-ON (+extracted)."""
    with pytest.raises(ConfigurationError, match="GM-3"):
        EnsembleBuilder("coin", n_replications=1, analysis=True)
    require_analysis_toggles(SimulationToggles(
        enable_extracted_routing=True, enable_capability_routing=True,
    ))  # compliant toggles pass


# ---------------------------------------------------------------------------
# Version stamp
# ---------------------------------------------------------------------------

def test_scenario_stamp_deterministic_and_sensitive():
    scenario = _minimal_scenario()
    engine = build_engine_from_dict(scenario, seed=42)
    assert engine.scenario_stamp == scenario_stamp(scenario)
    edited = apply_scenario_overrides(scenario, {"facilities.R1-A.beds": 5})
    assert scenario_stamp(edited) != engine.scenario_stamp


# ---------------------------------------------------------------------------
# triage_distribution wire (ruling: WIRE; O2 polices the coin preset)
# ---------------------------------------------------------------------------

def test_triage_distribution_wired():
    """A distribution the context default (T3=0.50) would essentially
    never produce must dominate the observed mix when configured."""
    scenario = _minimal_scenario()
    scenario["arrivals"]["triage_distribution"] = {
        "T1_SURGICAL": 0.01, "T1_MEDICAL": 0.01,
        "T2": 0.01, "T3": 0.96, "T4": 0.01,
    }
    _, log = run_to_log(scenario, duration_min=1440.0, max_patients=80,
                        drain=False)
    triages = [e["triage"] for e in log if e["event_type"] == "ARRIVAL"]
    assert len(triages) >= 40, "vacuous: too few arrivals"
    t3_share = triages.count("T3") / len(triages)
    assert t3_share >= 0.80, f"wired T3=0.96 not honoured: {t3_share=}"


def test_triage_distribution_absent_uses_context_default():
    """No YAML key → context distribution, exactly as before slice 1."""
    scenario = _minimal_scenario()
    assert "triage_distribution" not in scenario["arrivals"]
    engine = build_engine_from_dict(scenario, seed=42)
    from faer_dev.core.triage import TRIAGE_DISTRIBUTIONS
    from faer_dev.core.enums import OperationalContext
    assert engine.casualty_factory.triage_shift.base == (
        TRIAGE_DISTRIBUTIONS[OperationalContext.COIN]
    )


# ---------------------------------------------------------------------------
# scenario_overrides API
# ---------------------------------------------------------------------------

def test_apply_scenario_overrides_deep_copies():
    scenario = _minimal_scenario()
    edited = apply_scenario_overrides(scenario, {"facilities.R1-A.beds": 9})
    assert edited["facilities"][1]["beds"] == 9
    assert scenario["facilities"][1]["beds"] == 4  # base untouched


def test_ensemble_scenario_overrides_applied():
    """The override reaches the engines: the snapshot stamp equals the
    stamp of the edited dict, not the raw preset."""
    overrides = {"facilities.R1-ALPHA.beds": 2}
    snapshot = EnsembleBuilder(
        "coin", n_replications=1, scenario_overrides=overrides,
    ).run(duration=120.0, max_patients=10)
    expected = scenario_stamp(
        apply_scenario_overrides(get_preset_raw("coin"), overrides)
    )
    assert snapshot.scenario_stamp == expected
    assert snapshot.scenario_stamp != scenario_stamp(get_preset_raw("coin"))
