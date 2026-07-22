"""BUILD_S3 slice 3 — M2 waypoint semantics and golden-hour integrity.

Doctrine (ROUTING_SEMANTICS_NOTE D-A, signed): arrival at a medical node is
not clinical reception. Routing yields a clinical DESTINATION; graph-mode
intermediate path nodes are transit only.

Two things are asserted together, and the pairing is the point:

* waypoints skip treatment — the path-purity fix; and
* the golden-hour stamp becomes treatment-conditioned — because without
  that, M2 would hand the programme's flagship metric a free 100%: routing
  casualties THROUGH an R2 scored full compliance with zero care delivered
  (measured at round B, Q14.3(1)). A doctrine ruling must not weaponise a
  metrics bug.
"""

import pytest

from faer_dev.config.builder import build_engine_from_dict
from faer_dev.core.enums import TriageCategory
from faer_dev.decisions.mode import SimulationToggles
from faer_dev.events.canonical import canonical_log
from faer_dev.events.serialization import EventSerializer


def _toggles(*, typed: bool = False) -> SimulationToggles:
    return SimulationToggles(
        enable_extracted_routing=True,
        enable_graph_routing=True,
        enable_capability_routing=True,
        enable_typed_emitter=typed,
    )


def _canonical(engine) -> list[dict]:
    return canonical_log(
        [EventSerializer.event_to_dict(e) for e in engine.event_store.query()]
    )


def _force(engine, triage: TriageCategory):
    orig = engine.casualty_factory.create

    def forced(record):
        patient = orig(record)
        patient.triage = triage
        patient.initial_triage = triage
        return patient

    engine.casualty_factory.create = forced


def _through_r2_scenario(*, waypoint: bool) -> dict:
    """POI -> R2-NS (non-surgical) -> R3-S (surgical target).

    The T-5-7 topology exactly. With ``waypoint`` the intermediate declares
    itself passable; without it, nothing changes from today.
    """
    r2 = {
        "id": "R2-NS", "name": "FST non-surgical", "role": "R2", "beds": 8,
        "coordinates": [30.0, 0.0],
    }
    if waypoint:
        r2["waypoint_allowed"] = True
    return {
        "name": "s3_waypoint",
        "operational_context": "COIN",
        "arrivals": {"base_rate_per_hour": 6.0, "enable_mascal": False},
        "facilities": [
            {"id": "POI-1", "name": "POI", "role": "POI", "beds": 0,
             "coordinates": [0.0, 0.0]},
            r2,
            {"id": "R3-S", "name": "CSH surgical", "role": "R3", "beds": 20,
             "has_surgery": True, "has_blood": True,
             "coordinates": [100.0, 0.0]},
        ],
        "edges": [
            {"from": "POI-1", "to": "R2-NS", "travel_time_minutes": 45,
             "transport": "GROUND"},
            {"from": "R2-NS", "to": "R3-S", "travel_time_minutes": 60,
             "transport": "GROUND"},
        ],
    }


def _run(scenario, *, typed: bool = False, triage=TriageCategory.T1_SURGICAL):
    engine = build_engine_from_dict(
        scenario, toggles=_toggles(typed=typed), seed=42,
    )
    _force(engine, triage)
    engine.run(duration=0.0, max_patients=10)
    engine.step(1440.0)
    return engine, _canonical(engine)


# ---------------------------------------------------------------------------
# T-5-7w — the inversion (T-5-7 itself stays green as the defaults pin)
# ---------------------------------------------------------------------------

def test_t5_7w_waypoint_intermediate_is_not_treated():
    """T-5-7w: the waypoint-enabled twin of T-5-7.

    T-5-7 stays GREEN and is now the DEFAULTS PIN: with no waypoint_allowed
    anywhere, a T1_SURGICAL is still treated at the non-capable intermediate,
    exactly as before. This twin asserts the new behaviour on the opted-in
    scenario, so both the old default and the new mechanism are covered.

    Path purity is therefore resolved FOR WAYPOINT-ENABLED SCENARIOS. The
    default path is unchanged by design — the register row is narrowed, not
    closed.
    """
    engine, log = _run(_through_r2_scenario(waypoint=True))

    ns_treats = [
        e for e in log
        if e["event_type"] == "TREATMENT_START" and e["facility_id"] == "R2-NS"
    ]
    s_treats = [
        e for e in log
        if e["event_type"] == "TREATMENT_START" and e["facility_id"] == "R3-S"
    ]
    assert s_treats, "target selection failed: nobody reached the surgical R3"
    assert not ns_treats, (
        f"T1_SURGICAL treated at the waypointed intermediate: {ns_treats}"
    )


def test_defaults_still_treat_at_every_arrival():
    """The regression that protects every existing scenario: without the
    config flag, nothing about this topology changes."""
    engine, log = _run(_through_r2_scenario(waypoint=False))
    ns_treats = [
        e for e in log
        if e["event_type"] == "TREATMENT_START" and e["facility_id"] == "R2-NS"
    ]
    assert ns_treats, (
        "defaults changed: an un-flagged intermediate stopped treating"
    )


# ---------------------------------------------------------------------------
# Event signature — the measured beds=0 template (Q14.2)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("typed", [False, True], ids=["legacy", "typed"])
def test_waypoint_event_signature(typed):
    """A waypoint hop emits exactly the beds=0 pass-through signature:
    TRANSIT_END, FACILITY_ARRIVAL, TRANSIT_START — no TREATMENT_*.

    Run on BOTH emitter paths (beta rider 2). The alpha session found the
    typed emitter silently drops `state` where the legacy dict path keeps
    it, so "the flag survives the emitter" is not a safe assumption to
    make once and generalise.
    """
    engine, log = _run(_through_r2_scenario(waypoint=True), typed=typed)

    cid = next(e["casualty_id"] for e in log if e["event_type"] == "ARRIVAL")
    journey = [e for e in log if e["casualty_id"] == cid]
    at_r2 = [e["event_type"] for e in journey if e["facility_id"] == "R2-NS"]

    assert at_r2 == ["TRANSIT_END", "FACILITY_ARRIVAL", "TRANSIT_START"], (
        f"waypoint signature wrong on the {'typed' if typed else 'legacy'} "
        f"emitter: {at_r2}"
    )

    arrival = next(
        e for e in journey
        if e["event_type"] == "FACILITY_ARRIVAL" and e["facility_id"] == "R2-NS"
    )
    assert (arrival.get("metadata") or {}).get("waypoint") is True, (
        "metadata.waypoint did not survive the "
        f"{'typed' if typed else 'legacy'} emitter path"
    )

    # And the flag is absent — not merely False — at a real treat-stop.
    treat_stop = next(
        e for e in journey
        if e["event_type"] == "FACILITY_ARRIVAL" and e["facility_id"] == "R3-S"
    )
    assert "waypoint" not in (treat_stop.get("metadata") or {}), (
        "the flag is emitted at a treat-stop; it must be passed only when true"
    )


# ---------------------------------------------------------------------------
# Golden-hour integrity — the exploit M2 would otherwise have handed us
# ---------------------------------------------------------------------------

def test_waypoint_through_r2_does_not_stamp_golden_hour():
    """THE EXPLOIT, PINNED. Measured at round B: a casualty routed through
    an R2 with zero care recorded golden_hour_met=True and the run-level
    metric reported 100% compliance. Waypoints would have made that free
    and structural."""
    engine, _ = _run(_through_r2_scenario(waypoint=True))

    waypointed = [
        p for p in engine.completed_patients
        if "R2-NS" in p.facilities_visited
    ]
    assert waypointed, "vacuous: nobody was routed through the waypoint"
    for patient in waypointed:
        assert patient.metadata.get("r2_arrival_time") is None, (
            f"{patient.id} was stamped for a waypoint hop through R2-NS "
            "with no treatment delivered"
        )
        assert "golden_hour_met" not in patient.metadata


def test_treat_stop_at_r2_still_stamps():
    """The other half: conditioning on treatment must not stop a genuine
    R2 treat-stop from stamping, or the fix would just delete the metric."""
    scenario = _through_r2_scenario(waypoint=False)
    engine, _ = _run(scenario)

    treated = [
        p for p in engine.completed_patients
        if "R2-NS" in p.facilities_visited
    ]
    assert treated, "vacuous: nobody reached R2-NS"
    stamped = [p for p in treated if "r2_arrival_time" in p.metadata]
    assert stamped, "a treated R2 arrival failed to stamp the golden hour"
    for patient in stamped:
        assert patient.metadata["golden_hour_minutes"] == (
            patient.metadata["r2_arrival_time"] - patient.created_at
        ), "stamp is no longer ARRIVAL-timed"


def test_waypoint_then_treat_records_the_treating_r2():
    """F3, the case the ruling had to decide.

    A casualty waypointed through R2-A and treated at R2-B records R2-B's
    arrival time, not R2-A's. The stamp is 'first R2 arrival AT WHICH
    treatment occurs' — a different number from the old 'first R2 arrival',
    not merely a suppressed one.
    """
    scenario = {
        "name": "s3_two_r2",
        "operational_context": "COIN",
        "arrivals": {"base_rate_per_hour": 6.0, "enable_mascal": False},
        "facilities": [
            {"id": "POI-1", "name": "POI", "role": "POI", "beds": 0,
             "coordinates": [0.0, 0.0]},
            {"id": "R2-A", "name": "FST A (waypoint)", "role": "R2",
             "beds": 8, "waypoint_allowed": True,
             "coordinates": [30.0, 0.0]},
            {"id": "R2-B", "name": "FST B (treats)", "role": "R2", "beds": 8,
             "has_surgery": True, "has_blood": True,
             "coordinates": [60.0, 0.0]},
            {"id": "R3-S", "name": "CSH", "role": "R3", "beds": 20,
             "has_surgery": True, "has_blood": True,
             "coordinates": [200.0, 0.0]},
        ],
        "edges": [
            {"from": "POI-1", "to": "R2-A", "travel_time_minutes": 20,
             "transport": "GROUND"},
            {"from": "R2-A", "to": "R2-B", "travel_time_minutes": 25,
             "transport": "GROUND"},
            {"from": "R2-B", "to": "R3-S", "travel_time_minutes": 90,
             "transport": "GROUND"},
        ],
    }
    engine, log = _run(scenario)

    subjects = [
        p for p in engine.completed_patients
        if "R2-A" in p.facilities_visited and "R2-B" in p.facilities_visited
    ]
    assert subjects, "vacuous: nobody traversed R2-A then R2-B"

    for patient in subjects:
        arrivals = {
            e["facility_id"]: e["sim_time"] for e in log
            if e["casualty_id"] == patient.id
            and e["event_type"] == "FACILITY_ARRIVAL"
        }
        stamped = patient.metadata.get("r2_arrival_time")
        if stamped is None:
            continue  # never treated at either R2 within the window
        assert stamped == arrivals["R2-B"], (
            f"{patient.id} recorded {stamped}; expected R2-B's arrival "
            f"{arrivals['R2-B']}, not R2-A's {arrivals.get('R2-A')}"
        )


def test_denominator_shift_is_measured_and_reported(capsys):
    """G7: the pre-named denominator fixture IS the T-5-7w scenario.

    Conditioning on treatment means an R2 arrival that never treats carries
    no stamp, so `total_tracked` can fall on non-coin fixtures. Standing
    rule 5a requires that shift be quoted with its numerator and
    denominator rather than absorbed silently.
    """
    engine, _ = _run(_through_r2_scenario(waypoint=True))
    completed = engine.completed_patients
    reached_r2 = [p for p in completed if "R2-NS" in p.facilities_visited]
    tracked = [p for p in completed if "r2_arrival_time" in p.metadata]

    print(
        f"\nG7 denominator shift on the T-5-7w fixture: "
        f"reached R2 = {len(reached_r2)}/{len(completed)}; "
        f"golden-hour tracked = {len(tracked)}/{len(completed)} "
        f"(was {len(reached_r2)}/{len(completed)} under arrival-stamping). "
        f"Delta = {len(reached_r2) - len(tracked)} casualties no longer "
        f"counted as golden-hour compliant for a zero-care pass-through."
    )

    assert reached_r2, "vacuous: nobody reached the R2"
    assert len(tracked) < len(reached_r2), (
        "no denominator shift observed — the conditioning is inert here, "
        "so this fixture cannot evidence G7"
    )
    assert capsys.readouterr().out
