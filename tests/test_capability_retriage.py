"""S1.2b — re-triage staleness fix + capability characterisations.

T-5-5 (split per gate ruling 2026-07-05): PFC-ceiling re-triage promotes a
held casualty to T1_SURGICAL — the recompute landed at the promotion site
keeps ``requires_dcs`` truthful (flag-level test, green). The hold
destination itself is committed BEFORE the hold gate and never re-evaluated,
so the promoted casualty is still treated at the pre-promotion destination
(characterisation; Step-3 entry criterion). The S1.2b tripwire fired as
designed: recompute alone was proven insufficient, and the re-route decision
was routed to Step 3 rather than expanded here.

T-5-6 / T-5-7: characterisations of current behaviour, not fixes.
"""

import pytest

from faer_dev.config.builder import build_engine_from_dict
from faer_dev.core.enums import TriageCategory
from faer_dev.decisions.mode import SimulationToggles
from faer_dev.events.canonical import canonical_log
from faer_dev.events.serialization import EventSerializer
from faer_dev.routing import get_next_destination, triage_decisions


def _toggles(*, graph: bool = False, ccp: bool = False) -> SimulationToggles:
    return SimulationToggles(
        enable_extracted_routing=True,
        enable_graph_routing=graph,
        enable_capability_routing=True,
        enable_ccp=ccp,
    )


def _force_casualties(engine, triage: TriageCategory,
                      severity: float | None = None,
                      treatment_modifier: float | None = None):
    """Wrap the factory so every casualty gets the given triage (and
    optionally severity / treatment-time modifier). CRN-preserving: the
    factory draws unchanged and the result is overwritten."""
    orig_create = engine.casualty_factory.create

    def forced(record):
        patient = orig_create(record)
        patient.triage = triage
        patient.initial_triage = triage
        if severity is not None:
            patient.severity_score = severity
        if treatment_modifier is not None:
            patient.treatment_time_modifier = treatment_modifier
        return patient

    engine.casualty_factory.create = forced


def _canonical(engine) -> list[dict]:
    raw = [EventSerializer.event_to_dict(e) for e in engine.event_store.query()]
    return canonical_log(raw)


def _surgical_treatments_at_non_surgical(engine, log):
    return [
        e for e in log
        if e["event_type"] == "TREATMENT_START"
        and e["triage"] == "T1_SURGICAL"
        and not engine.network.facilities[e["facility_id"]].has_surgery
    ]


# ---------------------------------------------------------------------------
# T-5-5 — stale requires_dcs after PFC-ceiling promotion
# ---------------------------------------------------------------------------

def _hold_promotion_scenario() -> dict:
    """Held facility (R1-HOLD) is NON-surgical; downstream R2-NS
    (non-surgical, one bed — the bottleneck) precedes the surgical
    alternative R2-S in insertion order. A coin deepcopy cannot produce
    the red state: coin's downstream facilities are all surgical."""
    return {
        "name": "s1_hold_promotion",
        "operational_context": "COIN",
        "arrivals": {"base_rate_per_hour": 12.0, "enable_mascal": False},
        "facilities": [
            {"id": "POI-1", "name": "POI", "role": "POI", "beds": 0,
             "coordinates": [0.0, 0.0]},
            {"id": "R1-HOLD", "name": "BAS", "role": "R1", "beds": 12,
             "coordinates": [10.0, 0.0]},
            {"id": "R2-NS", "name": "FST non-surgical", "role": "R2", "beds": 1,
             "coordinates": [30.0, 0.0]},
            {"id": "R2-S", "name": "FST surgical", "role": "R2", "beds": 8,
             "has_surgery": True, "has_blood": True,
             "coordinates": [30.0, 5.0]},
        ],
        "edges": [
            {"from": "POI-1", "to": "R1-HOLD", "travel_time_minutes": 20,
             "transport": "GROUND"},
            {"from": "R1-HOLD", "to": "R2-NS", "travel_time_minutes": 35,
             "transport": "GROUND"},
            {"from": "R1-HOLD", "to": "R2-S", "travel_time_minutes": 45,
             "transport": "GROUND"},
        ],
    }


@pytest.fixture(scope="module")
def hold_promotion_run():
    """One run of the probe-tuned hold-promotion recipe, shared by the
    T-5-5 pair (the ~100 h sim runs once).

    Recipe (O4-derived, probe-tuned): R2-NS beds=1; enable_ccp so the
    injury loader supplies the data-driven T2 ceiling of 15 h
    (injury_reference.yaml:243) instead of the 24 h fallback
    (engine.py:798); severity 0.70 puts every casualty on the
    T1_SURGICAL rung of the deterioration ladder whatever the
    multiplier; treatment_time_modifier 2.0 stretches the bottleneck's
    no-gap stretch past the ceiling; hold timeout overridden to 45 h so
    promoted casualties release rather than time out. Probe at seed=42
    (shared stream): 45 promotions, 21 post-promotion treatments.
    Recipe re-tune at S2 0e (keyed default): cohort 60 -> 120 — the keyed
    realisation drained the 60-patient backlog before any hold reached
    the 15 h ceiling; a deeper backlog restores starvation (probe at
    seed=42 keyed: 62 promotions). Assertions untouched.
    """
    engine = build_engine_from_dict(
        _hold_promotion_scenario(), toggles=_toggles(ccp=True), seed=42,
    )
    _force_casualties(
        engine, TriageCategory.T2, severity=0.70, treatment_modifier=2.0,
    )
    engine._hold_timeout_override = 2700.0

    engine.run(duration=0.0, max_patients=120)
    engine.step(100 * 60.0)  # 100 h sim: window, marathon holds, releases

    log = _canonical(engine)
    promotions = [
        e for e in log
        if e["event_type"] == "TRIAGE"
        and e.get("reason") == "deterioration_retriage"
        and e.get("new_triage") == "T1_SURGICAL"
    ]
    assert promotions, "vacuous: no PFC-ceiling promotion to T1_SURGICAL occurred"
    return engine, log, {e["casualty_id"] for e in promotions}


def test_requires_dcs_recomputed_on_promotion(hold_promotion_run):
    """T-5-5a, flag-level, GREEN — T-5-5 split per gate ruling 2026-07-05.

    What the recompute (engine.py promotion site) actually does: after a
    PFC-ceiling promotion to T1_SURGICAL, ``requires_dcs`` is truthful, so
    every event payload and future metric reads the right flag and the
    NEXT routing decision after the stale hop is capability-filtered —
    damage is bounded to one facility, not the remaining journey.
    """
    engine, log, promoted_ids = hold_promotion_run

    promoted = [p for p in engine.completed_patients if p.id in promoted_ids]
    assert promoted, "no promoted casualty completed its journey"
    for patient in promoted:
        assert patient.requires_dcs is True, (
            f"{patient.id} promoted to T1_SURGICAL but requires_dcs is stale"
        )

    # The CAS-0041 probe as a unit assertion: a direct routing call from
    # the hold location, with the truthful flag, selects the surgical
    # facility — this is the decision the fix makes truthful.
    patient = promoted[0]
    decisions = triage_decisions(patient)
    dest = get_next_destination(
        patient, engine.network.facilities["R1-HOLD"], engine.network,
        decisions, use_capability_routing=True,
    )
    assert dest == "R2-S"


def test_promotion_does_not_reroute_committed_hold(hold_promotion_run):
    """T-5-5b CHARACTERISATION — T-5-5 split per gate ruling 2026-07-05.

    The hold destination is chosen BEFORE the hold gate
    (engine.py:680-688); the hold loop re-checks that destination's
    fullness only and never re-evaluates it (engine.py:720-848). A
    casualty promoted mid-hold therefore still transits to and is treated
    at the pre-promotion, non-surgical destination despite the truthful
    ``requires_dcs`` flag.

    Step-3 entry criterion — re-plan-on-Clock-1 family, alongside T-5-7;
    EX-6 possible vehicle. This test INVERTS at Step 3 — when
    re-plan-on-promotion lands, flip the assertion to violations == 0;
    do not delete.
    """
    engine, log, promoted_ids = hold_promotion_run
    violations = _surgical_treatments_at_non_surgical(engine, log)
    assert len(violations) > 0, (
        "committed-hold staleness no longer reproduces — has Step 3's "
        "re-plan landed? If so, invert this assertion to == 0"
    )


# ---------------------------------------------------------------------------
# T-5-6 — CHARACTERISATION: capability starvation
# ---------------------------------------------------------------------------

def test_t5_6_characterise_capability_starvation_is_silent_stratevac():
    """T-5-6 CHARACTERISATION, not a fix: when no surgical facility is
    reachable, a T1_SURGICAL casualty's route comes back None and the
    engine treats the journey as COMPLETE (engine.py:690-704) —
    success-shaped silent disposition: STRATEVAC at the POI, zero
    treatment events, no failure signal.

    Gate discussion item; Step-5 golden-hour metric contamination risk.
    """
    scenario = {
        "name": "s1_starvation",
        "operational_context": "COIN",
        "arrivals": {"base_rate_per_hour": 6.0, "enable_mascal": False},
        "facilities": [
            {"id": "POI-1", "name": "POI", "role": "POI", "beds": 0,
             "coordinates": [0.0, 0.0]},
            {"id": "R2-NS", "name": "FST non-surgical", "role": "R2", "beds": 8,
             "coordinates": [30.0, 0.0]},
        ],
        "edges": [
            {"from": "POI-1", "to": "R2-NS", "travel_time_minutes": 45,
             "transport": "GROUND"},
        ],
    }
    engine = build_engine_from_dict(scenario, toggles=_toggles(), seed=42)
    _force_casualties(engine, TriageCategory.T1_SURGICAL)
    engine.run(duration=0.0, max_patients=10)
    engine.step(600.0)

    log = _canonical(engine)
    arrivals = [e for e in log if e["event_type"] == "ARRIVAL"]
    dispositions = [e for e in log if e["event_type"] == "DISPOSITION"]
    treatments = [e for e in log if e["event_type"] == "TREATMENT_START"]

    assert arrivals, "vacuous: no arrivals"
    assert not treatments  # nobody is ever treated
    assert len(dispositions) == len(arrivals)
    for e in dispositions:
        assert e["facility_id"] == "POI-1"  # disposed where they arrived
        assert e["outcome"] == "STRATEVAC"  # success-shaped outcome
    # No failure signal anywhere: no ROUTING_FAILURE outcome, no reason field
    assert not any(e.get("outcome") == "ROUTING_FAILURE" for e in dispositions)
    assert not any(e.get("reason") for e in dispositions)


# ---------------------------------------------------------------------------
# T-5-7 — CHARACTERISATION: per-hop treatment in graph mode
#          (STEP-3 ENTRY CRITERION, not optional polish)
# ---------------------------------------------------------------------------

def test_t5_7_characterise_graph_mode_treats_at_non_capable_intermediates():
    """T-5-7 CHARACTERISATION, not a fix: graph-mode capability filtering
    is target-capability only (_find_highest_reachable). Dijkstra's path
    to a capable TARGET may pass through non-capable intermediates, and
    every FACILITY_ARRIVAL treats (engine.py:971-980) — so a T1_SURGICAL
    casualty IS treated at a non-surgical intermediate en route.

    This is a KNOWN NONCONFORMANCE against AC-5.1's letter (a
    treatment-site property) in multi-hop graph topologies — tolerable in
    S1 (graph is default-off; single-hop fixtures conform) but it MUST be
    resolved before Step 5's #45 sweep, i.e. during Step 3 multi-POI.
    Mechanism sketch for Step 3 (decision then, not now): capability as a
    hard edge-constraint a la bypass_role1 infinite weights
    (topology.py:63-68 pattern), or transit-without-treatment semantics.
    """
    scenario = {
        "name": "s1_per_hop",
        "operational_context": "COIN",
        "arrivals": {"base_rate_per_hour": 6.0, "enable_mascal": False},
        "facilities": [
            {"id": "POI-1", "name": "POI", "role": "POI", "beds": 0,
             "coordinates": [0.0, 0.0]},
            {"id": "R2-NS", "name": "FST non-surgical", "role": "R2", "beds": 8,
             "coordinates": [30.0, 0.0]},
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
    engine = build_engine_from_dict(
        scenario, toggles=_toggles(graph=True), seed=42,
    )
    _force_casualties(engine, TriageCategory.T1_SURGICAL)
    engine.run(duration=0.0, max_patients=10)
    engine.step(1440.0)

    log = _canonical(engine)
    ns_treats = [
        e for e in log
        if e["event_type"] == "TREATMENT_START"
        and e["facility_id"] == "R2-NS"
        and e["triage"] == "T1_SURGICAL"
    ]
    s_treats = [
        e for e in log
        if e["event_type"] == "TREATMENT_START" and e["facility_id"] == "R3-S"
    ]
    # Current behaviour: the capable TARGET is selected (casualties do
    # reach R3-S), but they are ALSO treated at the non-capable
    # intermediate on the way — the documented per-hop nonconformance.
    assert s_treats, "target selection failed: nobody reached the surgical R3"
    assert ns_treats, (
        "per-hop nonconformance no longer reproduces — behaviour changed; "
        "re-evaluate T-5-7 and the Step-3 entry criterion"
    )
