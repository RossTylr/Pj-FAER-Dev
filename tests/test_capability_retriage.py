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


def test_promotion_reroutes_at_the_hold_boundary(hold_promotion_run):
    """T-5-5b — INVERTED at BUILD_S3 slice 1, per its own instruction.

    Was a characterisation of the committed-hold staleness: the destination
    was chosen once, before the hold gate, and the hold loop only re-checked
    that destination's fullness. A casualty promoted mid-hold still transited
    to the pre-promotion, non-surgical destination despite a truthful
    ``requires_dcs``.

    M3 lands the doctrine ruling (ROUTING_SEMANTICS_NOTE D-B/D-C: divert on
    state change, bounded to leg boundaries and hold-retry). The retry
    boundary now recomputes both flags and re-derives the destination, so a
    promoted casualty diverts to the surgical alternative. Committed legs
    still complete — there is no mid-leg divert.

    Red witnessed before inversion at slice 1: ``assert 0 > 0``, i.e.
    violations fell from a reproducing population to exactly zero.
    """
    engine, log, promoted_ids = hold_promotion_run
    violations = _surgical_treatments_at_non_surgical(engine, log)
    assert len(violations) == 0, (
        "a T1_SURGICAL casualty was treated at a non-surgical facility after "
        f"the M3 hold-boundary re-decision landed: {violations}"
    )


def test_promoted_casualty_diverts_to_surgical_alternative(hold_promotion_run):
    """M3 divert, positively asserted (BUILD_S3 slice 1).

    T-5-5b proves the violation is gone; this proves the casualty went
    somewhere *better* rather than simply stopping. Every promoted casualty
    that reached a downstream R2 must have reached the surgical one — the
    destination the T-5-5a probe call already proved routing would select.
    """
    engine, log, promoted_ids = hold_promotion_run

    arrivals_after_promotion: dict[str, set[str]] = {}
    promoted_at: dict[str, float] = {}
    for event in log:
        cid = event["casualty_id"]
        if cid not in promoted_ids:
            continue
        if (event["event_type"] == "TRIAGE"
                and event.get("new_triage") == "T1_SURGICAL"):
            promoted_at.setdefault(cid, event["sim_time"])
        elif event["event_type"] == "FACILITY_ARRIVAL":
            if cid in promoted_at and event["sim_time"] >= promoted_at[cid]:
                arrivals_after_promotion.setdefault(cid, set()).add(
                    event["facility_id"]
                )

    reached_r2 = {
        cid: facs for cid, facs in arrivals_after_promotion.items()
        if facs & {"R2-NS", "R2-S"}
    }
    assert reached_r2, "vacuous: no promoted casualty reached a downstream R2"
    for cid, facs in reached_r2.items():
        assert "R2-NS" not in facs, (
            f"{cid} was promoted to T1_SURGICAL and still arrived at the "
            f"non-surgical R2-NS (arrived at {sorted(facs)})"
        )


def test_held_casualty_state_is_holding_not_in_treatment(hold_promotion_run):
    """Hold-state truth (BUILD_S3 slice 1).

    A held casualty holds no bed (released before the hold begins), no
    vehicle, and no slot at the destination. Its state was a stale
    ``IN_TREATMENT`` inherited from ``_treat_in_queue``; it is now the
    honest ``HOLDING``. PFC and timeout still override with their own
    states, so this asserts the state carried by the HOLD_START event —
    the moment the hold is entered.

    Asserted against ``engine.events`` (the legacy dict path), not the
    canonical log: the typed emitter drops ``state`` from the payload, so
    the canonical log cannot witness this. That asymmetry is itself worth
    knowing — the canonical trace carries triage but not state.
    """
    engine, log, promoted_ids = hold_promotion_run

    hold_starts = [e for e in engine.events if e["type"] == "HOLD_START"]
    assert hold_starts, "vacuous: no HOLD_START in the fixture"
    states = {e.get("state") for e in hold_starts}
    assert states == {"HOLDING"}, (
        f"HOLD_START carried states {states}, expected only HOLDING"
    )


def test_intended_destination_is_engine_internal(hold_promotion_run):
    """G8 RULE: ``intended_destination`` appears in no event payload.

    The field is the live routing decision, honest at every boundary where
    ``destination_facility`` is stale. It is deliberately NOT published: the
    roster side is policed by the roster_row whitelist plus I-7 clause 3,
    and this is the event side of the same rule.
    """
    engine, log, promoted_ids = hold_promotion_run

    # Non-vacuity on an IN-FLIGHT casualty: at journey end the last
    # loop-top recompute writes None (no next destination), so completed
    # casualties correctly carry None. A short separate run catches the
    # field while it is live.
    probe = build_engine_from_dict(
        _hold_promotion_scenario(), toggles=_toggles(), seed=42,
    )
    probe.run(duration=0.0, max_patients=10)
    probe.step(120.0)
    assert any(
        p.intended_destination is not None for p in probe.patients.values()
    ), "vacuous: no in-flight casualty carries an intended_destination"

    for event in log:
        assert "intended_destination" not in event, (
            f"{event['event_type']} leaked intended_destination into the "
            "canonical log"
        )
        metadata = event.get("metadata") or {}
        assert "intended_destination" not in metadata, (
            f"{event['event_type']} leaked intended_destination into metadata"
        )
    for event in engine.events:  # legacy dict path carries its own payload
        assert "intended_destination" not in (event.get("details") or {}), (
            f"{event['type']} leaked intended_destination into legacy details"
        )


@pytest.mark.parametrize("triage,expect_bypass,expect_dcs", [
    (TriageCategory.T1_SURGICAL, True, True),
    (TriageCategory.T1_MEDICAL, True, False),
    (TriageCategory.T2, False, False),
    (TriageCategory.T3, False, False),
    (TriageCategory.T4, False, False),
])
def test_triage_decisions_recompute_is_symmetric(
    triage, expect_bypass, expect_dcs,
):
    """M3 mechanism-level symmetry, INCLUDING the demotion branch.

    The engine promotes only (CP4 gate #7), so withdrawal-of-bypass has no
    reachable path today — but the ratified D-B ruling names triage change
    in EITHER direction as a trigger, and the recompute must be honest in
    both. Asserted where it is reachable: on the pure function.

    Also pins the property the whole zero-regen posture rests on — the
    recompute is idempotent, so re-deciding at a boundary is a no-op unless
    the casualty changed.
    """
    from faer_dev.core.schemas import Casualty

    patient = Casualty(
        id="CAS-TEST", triage=triage, initial_triage=triage,
        created_at=0.0, state_changed_at=0.0,
    )

    first = triage_decisions(patient)
    assert first["bypass_role1"] is expect_bypass
    assert first["requires_dcs"] is expect_dcs

    # Idempotence: recomputing without a state change is a no-op.
    assert triage_decisions(patient) == first

    # Promotion confers, demotion withdraws — the same pure function.
    patient.triage = TriageCategory.T1_SURGICAL
    promoted = triage_decisions(patient)
    assert promoted["bypass_role1"] is True
    assert promoted["requires_dcs"] is True

    patient.triage = triage
    assert triage_decisions(patient) == first, (
        "recompute is not symmetric: returning to the original triage did "
        "not restore the original decisions"
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
