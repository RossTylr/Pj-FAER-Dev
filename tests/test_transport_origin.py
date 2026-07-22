"""BUILD_S3 slice 4 — transport physics behind two toggles.

Two separate flags, both default False:

* ``enable_origin_transport`` — the batcher gains an ORIGIN dimension and
  the TRANSIT stream is keyed ``transit:<MODE>:<origin>``. These are ONE
  change, not two: a batch spanning origins has no single origin to key on,
  so the batcher dimension is a precondition for the scoped stream.
* ``enable_batched_turnaround`` — the batched path applies turnaround, which
  today only the unbatched path does.

They are separate flags because only the first is the transit-keying
provisional's subject. Bundling them would make the re-measure
uninterpretable — a ratio could not be attributed to keying rather than to a
physical change in vehicle downtime.

The load-bearing assertion here is the both-OFF one: coin is ALREADY
multi-origin (POI-1, R1-ALPHA and R2-MAIN all dispatch; the golden census
shows 3 transit draws), so an ungated re-scope would move the golden.
"""

import pytest

from faer_dev.config.builder import build_engine_from_dict, get_preset_raw
from faer_dev.core.enums import TransportMode
from faer_dev.data.roster import log_digest
from faer_dev.decisions.mode import SimulationToggles

from tests.harness import run_to_log

_O1_DIGEST = "d6546fbffb580bc508ebff37adab5c312c50cad0bfa92d99e0f6ac2d0d907479"


def _entities(engine) -> set[str]:
    """Entity strings the keyed root has actually drawn against."""
    return {entity for (entity, _purpose) in engine._keyed_rng._occurrence}


def _plural_origin_scenario() -> dict:
    """Two R1s feeding one R2, so two distinct origins dispatch the same
    mode and would batch together without the origin dimension."""
    return {
        "name": "s3_plural_origin",
        "operational_context": "COIN",
        "arrivals": {"base_rate_per_hour": 12.0, "enable_mascal": False},
        "facilities": [
            {"id": "POI-1", "name": "POI", "role": "POI", "beds": 0,
             "coordinates": [0.0, 0.0]},
            {"id": "R1-ALPHA", "name": "BAS A", "role": "R1", "beds": 6,
             "coordinates": [10.0, 5.0]},
            {"id": "R1-BRAVO", "name": "BAS B", "role": "R1", "beds": 6,
             "coordinates": [10.0, -5.0]},
            {"id": "R2-MAIN", "name": "FST", "role": "R2", "beds": 20,
             "has_surgery": True, "has_blood": True,
             "coordinates": [50.0, 0.0]},
        ],
        "edges": [
            {"from": "POI-1", "to": "R1-ALPHA", "travel_time_minutes": 15,
             "transport": "GROUND"},
            {"from": "POI-1", "to": "R1-BRAVO", "travel_time_minutes": 15,
             "transport": "GROUND"},
            {"from": "R1-ALPHA", "to": "R2-MAIN", "travel_time_minutes": 30,
             "transport": "ROTARY"},
            {"from": "R1-BRAVO", "to": "R2-MAIN", "travel_time_minutes": 30,
             "transport": "ROTARY"},
        ],
    }


# ---------------------------------------------------------------------------
# The load-bearing assertion
# ---------------------------------------------------------------------------

def test_both_toggles_off_is_byte_identical():
    """coin is already multi-origin, so an ungated re-scope moves the
    golden. With both flags off, nothing may change — golden digest AND
    the keyed draw census."""
    engine, log = run_to_log("coin", duration_min=480.0, max_patients=50,
                             drain=False)
    assert log_digest(log) == _O1_DIGEST
    assert engine._keyed_rng.draw_counts["transit"] == 3
    assert engine.transport_pool._origin_scoped is False
    assert engine.transport_pool._batched_turnaround is False


def test_toggle_off_keeps_the_bare_transit_entity():
    """The mechanism behind the preservation: the entity string is
    untouched, so the blake2b key and every occurrence index are too."""
    engine = build_engine_from_dict(get_preset_raw("coin"), seed=42)
    pool = engine.transport_pool
    pool.sample_trip_time(TransportMode.GROUND, origin="R1-ALPHA")
    assert "transit:GROUND" in _entities(engine)


# ---------------------------------------------------------------------------
# origin_transport ON
# ---------------------------------------------------------------------------

def test_origin_scoping_changes_the_transit_entity():
    toggles = SimulationToggles(enable_origin_transport=True)
    engine = build_engine_from_dict(
        get_preset_raw("coin"), toggles=toggles, seed=42,
    )
    pool = engine.transport_pool
    pool.sample_trip_time(TransportMode.GROUND, origin="R1-ALPHA")
    keys = _entities(engine)
    assert "transit:GROUND:R1-ALPHA" in keys
    assert "transit:GROUND" not in keys


def test_batches_do_not_mix_origins():
    """The physical claim: one vehicle serves one departure point per trip.

    Asserted at the coordinator, where batch membership is decided —
    end-to-end the property is invisible because every member gets the same
    trip time either way.
    """
    toggles = SimulationToggles(enable_origin_transport=True)
    engine = build_engine_from_dict(
        _plural_origin_scenario(), toggles=toggles, seed=42,
    )
    batcher = engine.transport_pool.get_batcher(TransportMode.ROTARY)
    if batcher is None:
        pytest.skip("ROTARY is not batched under this transport config")

    dispatched: list[list[str]] = []
    original = batcher._dispatch_batch

    def spy():
        before = list(batcher._pending)
        gen = original()
        after_first = None
        try:
            next(gen)
        except StopIteration:
            pass
        taken = [s for s in before if s not in batcher._pending]
        if taken:
            dispatched.append([s.origin for s in taken])
        return gen

    batcher._dispatch_batch = spy
    engine.run(duration=0.0, max_patients=40)
    engine.step(600.0)

    mixed = [origins for origins in dispatched if len(set(origins)) > 1]
    assert dispatched, "vacuous: no batch was dispatched"
    assert not mixed, f"batches mixed origins: {mixed}"


def test_scoped_key_draw_census():
    """I-3: the draw census must still account for every transit draw, and
    the scoped run must spread them across origin-qualified streams."""
    toggles = SimulationToggles(enable_origin_transport=True)
    engine, _ = run_to_log(
        _plural_origin_scenario(), duration_min=600.0, max_patients=30,
        drain=True, toggles=toggles,
    )
    keys = [k for k in _entities(engine) if k.startswith("transit:")]
    assert keys, "vacuous: no transit draws"
    assert all(k.count(":") == 2 for k in keys), (
        f"unscoped transit entity survived under the toggle: {keys}"
    )
    scoped_total = sum(
        engine._keyed_rng._occurrence[(k, p)]
        for (k, p) in engine._keyed_rng._occurrence
        if k.startswith("transit:")
    )
    assert scoped_total == engine._keyed_rng.draw_counts["transit"], (
        "draw census and occurrence ladder disagree"
    )


# ---------------------------------------------------------------------------
# batched_turnaround ON
# ---------------------------------------------------------------------------

def test_batched_turnaround_holds_the_vehicle_longer():
    """The two downtime models agree once the flag is on.

    Off, the batched path releases the vehicle after the round trip and
    applies no turnaround at all; on, it holds for trip + turnaround, which
    is what the unbatched _vehicle_return model has always done.
    """
    scenario = _plural_origin_scenario()
    off = build_engine_from_dict(scenario, seed=42)
    on = build_engine_from_dict(
        scenario, toggles=SimulationToggles(enable_batched_turnaround=True),
        seed=42,
    )
    b_off = off.transport_pool.get_batcher(TransportMode.ROTARY)
    b_on = on.transport_pool.get_batcher(TransportMode.ROTARY)
    if b_off is None or b_on is None:
        pytest.skip("ROTARY is not batched under this transport config")

    expected = off.transport_pool.config.get_turnaround(TransportMode.ROTARY)
    assert b_off.turnaround == 0.0
    assert b_on.turnaround == expected > 0.0


def test_turnaround_toggle_is_inert_when_off():
    _, log = run_to_log(
        "coin", duration_min=480.0, max_patients=50, drain=False,
        toggles=SimulationToggles(enable_batched_turnaround=False),
    )
    assert log_digest(log) == _O1_DIGEST


# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------

def test_analysis_runs_require_origin_scoping():
    from faer_dev.config.guards import require_analysis_toggles
    from faer_dev.core.exceptions import ConfigurationError

    with pytest.raises(ConfigurationError, match="enable_origin_transport"):
        require_analysis_toggles(SimulationToggles(
            enable_extracted_routing=True, enable_capability_routing=True,
        ))
    require_analysis_toggles(SimulationToggles(
        enable_extracted_routing=True, enable_capability_routing=True,
        enable_origin_transport=True,
    ))
