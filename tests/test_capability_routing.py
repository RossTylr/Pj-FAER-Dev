"""S1.2a — capability routing tests (T-5-1, T-5-2, T-5-3, T-5-4, T-5-G).

Killer property (AC-5.1 as amended, MVP_ACCEPTANCE.md:69-75 / BUILD_S1 §3):
NO event where a casualty whose triage at that moment is T1_SURGICAL is
treated at a facility with ``has_surgery=False``. The as-built flag pair is
casualty ``requires_dcs`` ↔ facility ``has_surgery``; "byte-identical event
log" is read on the CANONICAL log (F0.1 — raw logs carry uuid/wall-time).

The filter lives on the strangler side only (extracted walk + graph
candidate loop). The legacy walk (engine.py:84-121) is capability-blind by
design and is NOT exercised here with capability on — the R11-family guard
makes that combination a construction-time error. R16a therefore remains
open at engine defaults until legacy retirement (gate minute).
"""

import pytest

from faer_dev.config.builder import build_engine_from_dict
from faer_dev.core.enums import TriageCategory
from faer_dev.core.exceptions import ConfigurationError
from faer_dev.decisions.mode import SimulationToggles
from faer_dev.events.canonical import canonical_log, log_digest
from faer_dev.events.serialization import EventSerializer

from tests.harness import run_to_log


# ---------------------------------------------------------------------------
# Fixtures — inline dicts only (Q9 house pattern)
# ---------------------------------------------------------------------------

def _killer_scenario(r2a_surgical: bool = False) -> dict:
    """POI with direct edges to two R2s; no other echelons.

    R2-A PRECEDES R2-B in facility insertion order — the extracted walk's
    first-match (routing.py:147) and the graph candidate loop
    (routing.py:92-96) both select by insertion order among same-role
    candidates, so R2-A-first is what makes the unfiltered red state
    manifest on both strangler params. R2-A also carries the LIGHTER edge
    weight, so graph mode prefers it for weight reasons too (T-5-4).
    R2-B is the surgical facility, reachable only via the heavier edge.
    """
    return {
        "name": "s1_killer",
        "operational_context": "COIN",
        "arrivals": {"base_rate_per_hour": 6.0, "enable_mascal": False},
        "facilities": [
            {"id": "POI-1", "name": "POI", "role": "POI", "beds": 0,
             "coordinates": [0.0, 0.0]},
            {"id": "R2-A", "name": "FST A", "role": "R2", "beds": 8,
             "has_surgery": r2a_surgical, "coordinates": [10.0, 0.0]},
            {"id": "R2-B", "name": "FST B", "role": "R2", "beds": 8,
             "has_surgery": True, "has_blood": True,
             "coordinates": [10.0, 5.0]},
        ],
        "edges": [
            {"from": "POI-1", "to": "R2-A", "travel_time_minutes": 20,
             "transport": "GROUND"},
            {"from": "POI-1", "to": "R2-B", "travel_time_minutes": 60,
             "transport": "GROUND"},
        ],
    }


def _toggles(*, graph: bool = False, capability: bool = True) -> SimulationToggles:
    return SimulationToggles(
        enable_extracted_routing=True,
        enable_graph_routing=graph,
        enable_capability_routing=capability,
    )


def _run_killer(toggles, *, r2a_surgical: bool = False, seed: int = 42,
                max_patients: int = 20):
    """Run the killer scenario with 100% T1_SURGICAL arrivals, drained.

    The factory is wrapped, not replaced: it draws its random numbers
    unchanged (CRN preserved) and the resulting casualty is overwritten to
    T1_SURGICAL — the 100%-surgical population AC-5.1 asks for.
    Drain loop mirrors tests/harness.run_to_log (window close via
    ``_max_arrivals``, the established test-level seam).
    """
    scenario = _killer_scenario(r2a_surgical=r2a_surgical)
    engine = build_engine_from_dict(scenario, toggles=toggles, seed=seed)

    orig_create = engine.casualty_factory.create

    def force_t1_surgical(record):
        patient = orig_create(record)
        patient.triage = TriageCategory.T1_SURGICAL
        patient.initial_triage = TriageCategory.T1_SURGICAL
        return patient

    engine.casualty_factory.create = force_t1_surgical

    engine.run(duration=0.0, max_patients=max_patients)
    engine.step(600.0)
    engine.arrival_process._max_arrivals = engine.arrival_process.count

    def _count(event_type: str) -> int:
        return len(engine.event_store.events_of_type(event_type))

    deadline = engine.env.now + 24 * 60.0
    while _count("ARRIVAL") != _count("DISPOSITION"):
        assert engine.env.now < deadline, "killer fixture failed to drain"
        engine.step(60.0)

    raw = [EventSerializer.event_to_dict(e) for e in engine.event_store.query()]
    return engine, canonical_log(raw)


def _surgical_treatments(log: list[dict]) -> list[dict]:
    """TREATMENT_START events whose casualty is T1_SURGICAL at that moment.

    The engine stamps the casualty's live triage onto every emitted event
    (engine.py:504-508), so the event's own ``triage`` field IS the
    at-that-moment value — no journey reconstruction needed.
    """
    return [
        e for e in log
        if e["event_type"] == "TREATMENT_START" and e["triage"] == "T1_SURGICAL"
    ]


# ---------------------------------------------------------------------------
# T-5-1 — THE KILLER (↔ AC-5.1 as amended), both strangler params
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode", ["extracted-walk", "graph"])
def test_t5_1_killer_no_surgical_treatment_at_non_surgical_facility(mode):
    """T-5-1: no T1_SURGICAL casualty is treated at has_surgery=False.

    Red before the filter: both the extracted walk (first-match) and the
    graph candidate loop (insertion order, then weight) select the
    non-surgical R2-A. The legacy walk is out of scope — capability-blind
    by design; R16a stays open at engine defaults until legacy retirement.
    """
    toggles = _toggles(graph=(mode == "graph"))
    engine, log = _run_killer(toggles)

    surgical_treats = _surgical_treatments(log)
    assert surgical_treats, "vacuous run: no T1_SURGICAL treatment observed"
    for event in surgical_treats:
        facility = engine.network.facilities[event["facility_id"]]
        assert facility.has_surgery, (
            f"{event['casualty_id']} (T1_SURGICAL at that moment) treated at "
            f"non-surgical facility {event['facility_id']}"
        )


# ---------------------------------------------------------------------------
# T-5-2 — CONTROL + LIVENESS (↔ AC-5.2)
# ---------------------------------------------------------------------------

def test_t5_2a_digest_control_filter_vacuous_when_all_capable():
    """T-5-2a: with every facility surgical, toggle ON vs OFF canonical
    digests are byte-identical — the filter is vacuous when all qualify."""
    _, log_on = _run_killer(_toggles(), r2a_surgical=True)
    _, log_off = _run_killer(_toggles(capability=False), r2a_surgical=True)
    assert log_digest(log_on) == log_digest(log_off)


def test_t5_2b_liveness_all_surgical_casualties_are_treated():
    """T-5-2b (AC-5.2 letter): all facilities surgical, capability ON —
    every surgical casualty gets at least one TREATMENT_START; the flag
    gates, it doesn't block."""
    _, log = _run_killer(_toggles(), r2a_surgical=True)
    arrived = {e["casualty_id"] for e in log if e["event_type"] == "ARRIVAL"}
    treated = {e["casualty_id"] for e in log if e["event_type"] == "TREATMENT_START"}
    assert arrived, "vacuous run: no arrivals"
    assert arrived <= treated, (
        f"surgical casualties never treated: {sorted(arrived - treated)}"
    )


def test_t5_2c_coin_capability_toggle_is_noop():
    """T-5-2c: coin preset, extracted ON in BOTH arms, capability ON vs
    OFF — canonical digests identical (coin's T1s already reach surgical
    facilities, Q6; holding extracted fixed isolates the capability toggle
    from strangler equivalence)."""
    off = SimulationToggles(enable_extracted_routing=True)
    on = SimulationToggles(
        enable_extracted_routing=True, enable_capability_routing=True,
    )
    _, log_off = run_to_log(
        "coin", duration_min=480.0, max_patients=50, toggles=off, drain=False,
    )
    _, log_on = run_to_log(
        "coin", duration_min=480.0, max_patients=50, toggles=on, drain=False,
    )
    assert log_digest(log_on) == log_digest(log_off)


# ---------------------------------------------------------------------------
# T-5-3 — DETERMINISM (↔ AC-5.3 as amended)
# ---------------------------------------------------------------------------

def test_t5_3_determinism_double_run_equal_digests():
    """T-5-3: the killer config at seed=42, run twice — canonical digests
    equal (the F0.1/R1 gate re-applied to the capability path)."""
    _, log_a = _run_killer(_toggles())
    _, log_b = _run_killer(_toggles())
    assert log_digest(log_a) == log_digest(log_b)


# ---------------------------------------------------------------------------
# T-5-4 — NON-DOMINANCE (R1-ALPHA non-inheritance)
# ---------------------------------------------------------------------------

def test_t5_4_weight_preference_cannot_readmit_non_capable_candidate():
    """T-5-4: graph mode — the weight-preferred R2-A (20 min vs 60 min) is
    excluded from the candidate set; casualties route to R2-B despite the
    worse weight. Candidate-set exclusion, never weighting: no weight
    advantage re-admits a non-capable candidate (the R1-ALPHA lesson)."""
    engine, log = _run_killer(_toggles(graph=True))

    surgical_treats = _surgical_treatments(log)
    assert surgical_treats, "vacuous run: no T1_SURGICAL treatment observed"
    assert all(e["facility_id"] == "R2-B" for e in surgical_treats)
    r2a_arrivals = [
        e for e in log
        if e["event_type"] == "FACILITY_ARRIVAL" and e["facility_id"] == "R2-A"
    ]
    assert not r2a_arrivals, "non-capable R2-A re-admitted by weight preference"


# ---------------------------------------------------------------------------
# T-5-G — GUARD (R11 family)
# ---------------------------------------------------------------------------

def test_t5_g_capability_without_extracted_is_a_config_error():
    """T-5-G: capability ON + extracted OFF raises at construction.

    Without the guard we recreate the R11 silent-toggle trap: a capability
    toggle that is inert on the default (legacy) path. Legacy + capability
    is an invalid combination by design."""
    with pytest.raises(ConfigurationError):
        SimulationToggles(enable_capability_routing=True)


def test_t5_g_valid_combinations_construct():
    """Guard does not over-fire: capability with extracted (and with
    graph) constructs; capability OFF is unconstrained."""
    SimulationToggles(
        enable_extracted_routing=True, enable_capability_routing=True,
    )
    SimulationToggles(
        enable_extracted_routing=True, enable_graph_routing=True,
        enable_capability_routing=True,
    )
    SimulationToggles()
