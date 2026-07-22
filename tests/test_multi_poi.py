"""BUILD_S3 slice 2 — multi-POI wiring, AC-1.1 to AC-1.4.

The asymmetry under test: a single-POI scenario keeps every legacy form
(bare "arrivals" stream literal, CAS-NNNN uids, integer mascal ids), so all
committed digests are preserved byte for byte; a scenario with N>=2 POIs
gets POI-scoped streams and POI-prefixed uids, because two instances sharing
one occurrence ladder destroys CRN pairing (Q11.4, measured) and two
unprefixed factories collide on the identity key.

Both halves are asserted here: the preservation AND the scoping.
"""

import pytest

from faer_dev.config.builder import (
    build_engine_from_dict,
    get_preset_raw,
    scenario_stamp,
)
from faer_dev.config.guards import (
    count_pois,
    poi_count_from_stamp,
    require_comparable_arms,
)
from faer_dev.core.exceptions import ConfigurationError
from faer_dev.data.roster import log_digest
from faer_dev.decisions.mode import SimulationToggles
from faer_dev.events.canonical import canonical_log
from faer_dev.events.serialization import EventSerializer

from tests.harness import run_to_log


def _two_poi_scenario(weights: tuple[float, float] = (0.7, 0.3)) -> dict:
    """Two POIs, each with a shorter edge to its own R1 (the AC-1.2
    edges-encode-nearness reading), converging on one R2."""
    north, south = weights
    return {
        "name": "s3_two_poi",
        "operational_context": "COIN",
        "arrivals": {
            "base_rate_per_hour": 6.0,
            "enable_mascal": False,
            "per_poi": {"POI-NORTH": north, "POI-SOUTH": south},
        },
        "facilities": [
            {"id": "POI-NORTH", "name": "POI North", "role": "POI", "beds": 0,
             "coordinates": [0.0, 10.0]},
            {"id": "POI-SOUTH", "name": "POI South", "role": "POI", "beds": 0,
             "coordinates": [0.0, -10.0]},
            {"id": "R1-ALPHA", "name": "BAS Alpha", "role": "R1", "beds": 8,
             "coordinates": [10.0, 10.0]},
            {"id": "R1-BRAVO", "name": "BAS Bravo", "role": "R1", "beds": 8,
             "coordinates": [10.0, -10.0]},
            {"id": "R2-MAIN", "name": "FST", "role": "R2", "beds": 12,
             "has_surgery": True, "has_blood": True,
             "coordinates": [40.0, 0.0]},
        ],
        "edges": [
            {"from": "POI-NORTH", "to": "R1-ALPHA", "travel_time_minutes": 10,
             "transport": "GROUND"},
            {"from": "POI-NORTH", "to": "R1-BRAVO", "travel_time_minutes": 40,
             "transport": "GROUND"},
            {"from": "POI-SOUTH", "to": "R1-BRAVO", "travel_time_minutes": 10,
             "transport": "GROUND"},
            {"from": "POI-SOUTH", "to": "R1-ALPHA", "travel_time_minutes": 40,
             "transport": "GROUND"},
            {"from": "R1-ALPHA", "to": "R2-MAIN", "travel_time_minutes": 30,
             "transport": "GROUND"},
            {"from": "R1-BRAVO", "to": "R2-MAIN", "travel_time_minutes": 30,
             "transport": "GROUND"},
        ],
    }


def _canonical(engine) -> list[dict]:
    return canonical_log(
        [EventSerializer.event_to_dict(e) for e in engine.event_store.query()]
    )


# ---------------------------------------------------------------------------
# The asymmetry's proof — single POI is untouched
# ---------------------------------------------------------------------------

def test_single_poi_digest_is_byte_preserved():
    """The load-bearing assertion of the whole keying ruling.

    coin has one POI, so the N-instance wiring must produce the exact
    digest recorded at round B (S3_FOLLOWUP Q17.1) — no scope on the
    stream key, no prefix on the uid, no behavioural change at all.
    """
    _, log = run_to_log("coin", duration_min=480.0, max_patients=50,
                        drain=False)
    assert log_digest(log) == (
        "d6546fbffb580bc508ebff37adab5c312c50cad0bfa92d99e0f6ac2d0d907479"
    )


def test_single_poi_keeps_legacy_uid_and_stream_forms():
    """The mechanism behind the preservation, asserted directly."""
    engine, log = run_to_log("coin", duration_min=480.0, max_patients=20,
                             drain=False)
    assert len(engine.arrival_processes) == 1
    process = engine.arrival_process
    assert process._stream_scope is None
    assert process._mascal_id_prefix is None
    assert not engine._poi_factories, "no per-POI factory at N=1"
    assert all(
        e["casualty_id"].startswith("CAS-")
        for e in log if e["event_type"] == "ARRIVAL"
    )
    assert engine._keyed_rng.draw_counts["arrivals"] > 0


# ---------------------------------------------------------------------------
# AC-1.3 — conservation with two concurrent arrival processes
# ---------------------------------------------------------------------------

def test_ac_1_3_conservation_two_poi_drained():
    """Hard Rule 4 in its terminal (drained) form, with N=2.

    run_to_log(drain=True) loops until ARRIVAL == DISPOSITION, so reaching
    the end at all is the assertion; the explicit counts document it.
    """
    engine, log = run_to_log(
        _two_poi_scenario(), duration_min=600.0, max_patients=25, drain=True,
    )
    arrivals = [e for e in log if e["event_type"] == "ARRIVAL"]
    dispositions = [e for e in log if e["event_type"] == "DISPOSITION"]
    assert len(arrivals) == len(dispositions), (
        f"conservation broken: {len(arrivals)} arrivals, "
        f"{len(dispositions)} dispositions"
    )
    assert not engine.patients, "casualties still in system after drain"
    assert len(engine.arrival_processes) == 2


def test_both_pois_actually_spawn():
    """The defect multi-POI exists to fix: before slice 2 a second POI
    parsed, joined the network, and then silently received nothing."""
    _, log = run_to_log(
        _two_poi_scenario(), duration_min=600.0, max_patients=25, drain=True,
    )
    sources = {
        e["facility_id"] for e in log if e["event_type"] == "ARRIVAL"
    }
    assert sources == {"POI-NORTH", "POI-SOUTH"}, (
        f"expected both POIs to spawn casualties, saw {sources}"
    )


# ---------------------------------------------------------------------------
# AC-1.4 (amended) — determinism AND pairing
# ---------------------------------------------------------------------------

def test_ac_1_4a_two_poi_determinism():
    """(a) Two-POI scenario reproduces byte-identically at seed=42.

    Concurrent arrival generators are exactly where determinism breaks
    silently, so this is asserted on the full canonical digest.
    """
    scenario = _two_poi_scenario()
    _, log_a = run_to_log(scenario, duration_min=600.0, max_patients=25,
                          drain=True)
    _, log_b = run_to_log(scenario, duration_min=600.0, max_patients=25,
                          drain=True)
    assert log_digest(log_a) == log_digest(log_b)


def test_ac_1_4b_two_poi_identity_pairing():
    """(b) I-2-style paired invariance on a fixed two-POI scenario.

    Determinism alone is insufficient (S3-AMEND-2): a run can be perfectly
    reproducible while its streams are cross-contaminated. This asserts the
    property determinism cannot see — that changing a system-axis toggle
    leaves casualty IDENTITY and ARRIVAL timing untouched, which is what
    CRN pairing means.

    The guard is invoked in the arrange step, as the amendment requires.
    """
    scenario = _two_poi_scenario()
    require_comparable_arms(scenario_stamp(scenario), scenario_stamp(scenario))

    def _arrivals(toggles):
        _, log = run_to_log(scenario, duration_min=600.0, max_patients=25,
                            drain=True, toggles=toggles)
        return [e for e in log if e["event_type"] == "ARRIVAL"]

    arm_a = _arrivals(SimulationToggles(rng_mode="keyed"))
    arm_c = _arrivals(SimulationToggles(
        rng_mode="keyed", enable_extracted_routing=True,
        enable_capability_routing=True,
    ))
    assert arm_a, "vacuous: no arrivals"
    assert arm_a == arm_c, (
        "identity/arrival invariance broken across a routing-toggle change: "
        "the per-POI stream scoping is not isolating the system axis"
    )


def test_mascal_ids_do_not_collide_across_pois():
    """Each ArrivalProcess owns its MASCAL counter, so N POIs would each
    restart at 1. Prefixing is what keeps cluster ids unique."""
    scenario = _two_poi_scenario()
    scenario["arrivals"]["enable_mascal"] = True
    scenario["arrivals"]["mascal_rate_per_hour"] = 3.0
    engine, _ = run_to_log(scenario, duration_min=600.0, max_patients=40,
                           drain=True)

    ids = [
        p.mascal_event_id
        for p in engine.completed_patients
        if p.mascal_event_id is not None
    ]
    assert ids, "vacuous: no MASCAL casualties generated"
    assert all(isinstance(i, str) for i in ids), (
        f"expected POI-prefixed string ids when plural, got {set(map(type, ids))}"
    )
    prefixes = {str(i).rsplit("-", 1)[0] for i in ids}
    assert prefixes == {"POI-NORTH", "POI-SOUTH"}, (
        f"MASCAL ids not scoped to both POIs: {prefixes}"
    )


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

def test_poi_id_override_rejected_when_plural():
    """Pinning one POI in a multi-POI scenario would silently starve the
    rest — the exact defect slice 2 removes. It raises instead."""
    engine = build_engine_from_dict(_two_poi_scenario(), seed=42)
    with pytest.raises(ValueError, match="single-POI only"):
        engine.run(duration=0.0, poi_id="POI-NORTH", max_patients=5)


def test_poi_id_override_still_allowed_when_single():
    engine = build_engine_from_dict(get_preset_raw("coin"), seed=42)
    engine.run(duration=10.0, poi_id="POI-1", max_patients=5)
    assert engine._poi_id == "POI-1"


def test_require_comparable_arms_raises_across_poi_counts():
    """The Hard-Rule-8 guard: arms at different POI counts use different
    key schemas, so comparing them is invalid however tidy the numbers."""
    single = scenario_stamp(get_preset_raw("coin"))
    plural = scenario_stamp(_two_poi_scenario())
    assert poi_count_from_stamp(single) == 1
    assert poi_count_from_stamp(plural) == 2

    require_comparable_arms(single, single)
    require_comparable_arms(plural, plural)
    with pytest.raises(ConfigurationError, match="different POI counts"):
        require_comparable_arms(single, plural)


def test_arrival_weight_sum_guard():
    bad = _two_poi_scenario(weights=(0.7, 0.5))
    with pytest.raises(ConfigurationError, match="sum to"):
        build_engine_from_dict(bad, seed=42)

    unknown = _two_poi_scenario()
    unknown["arrivals"]["per_poi"] = {"POI-GHOST": 1.0}
    with pytest.raises(ConfigurationError, match="unknown facilities"):
        build_engine_from_dict(unknown, seed=42)


def test_count_pois_counts_declared_and_synthesised():
    assert count_pois(get_preset_raw("coin")) == 1
    assert count_pois(_two_poi_scenario()) == 2


# ---------------------------------------------------------------------------
# AC-1.1 — spawn proportions (slow: needs replications to resolve)
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_ac_1_1_spawn_proportions():
    """AC-1.1: two POIs weighted 0.7 / 0.3; assert the realised spawn
    proportion is 0.7 / 0.3 +/- 0.05 over replications.

    Weights are SHARES of the theatre rate (S3-AMEND-3), so the theatre
    total is preserved and the MASCAL detector's tuning is untouched.

    The fixture runs mascal_enabled=False deliberately: the detector is
    global, hardcoded and unconfigurable (Q15.3), so N POIs trip its
    20-in-15-min threshold N times sooner with no config recourse. That is
    registered to #30; suppressing clusters here keeps this AC measuring
    the split rather than the detector's mistuning.

    ``max_patients`` is a PER-POI lifetime cap, so it must be set high
    enough not to bind: a binding cap truncates the heavier POI first and
    drags the measured split toward 50/50 (observed at cap=25: 0.637). The
    cap is asserted non-binding below, so this test cannot silently become
    a measurement of the cap instead of the rate.
    """
    scenario = _two_poi_scenario()
    cap = 500
    north = south = 0
    for rep in range(40):
        engine, log = run_to_log(
            scenario, duration_min=600.0, max_patients=cap, drain=True,
            seed=42, replication_index=rep,
        )
        for process in engine.arrival_processes.values():
            assert process.count < cap, (
                f"rep {rep}: arrival cap bound at {process.count}; the "
                "measured split would reflect the cap, not the weights"
            )
        for event in log:
            if event["event_type"] != "ARRIVAL":
                continue
            if event["facility_id"] == "POI-NORTH":
                north += 1
            else:
                south += 1

    total = north + south
    assert total > 0, "vacuous: no arrivals across replications"
    share_north = north / total
    assert abs(share_north - 0.7) <= 0.05, (
        f"POI-NORTH share {share_north:.4f} (={north}/{total}) outside "
        "0.7 +/- 0.05"
    )
    assert abs((south / total) - 0.3) <= 0.05, (
        f"POI-SOUTH share {south / total:.4f} (={south}/{total}) outside "
        "0.3 +/- 0.05"
    )
