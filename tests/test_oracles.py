"""Correctness oracles O1, O2, O3, O5 and O6 (F0.3).

Absolute behavioural checks on single-implementation mechanisms — the
blind spot MAAFI R17 exposed (forcing every casualty to T3 passed all
99 tests). None of these is a ``legacy == extracted`` comparison.
O4 (hold-gate sequence) lives in ``test_hold_gate_integration.py``.
"""

import copy
import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from faer_dev.config.builder import build_engine_from_dict, get_preset_raw
from faer_dev.decisions.mode import SimulationToggles
from faer_dev.events.canonical import canonical_log, log_digest
from faer_dev.events.serialization import EventSerializer

from tests.harness import run_to_log

GOLDEN_PATH = Path(__file__).parent / "golden" / "coin_s42.json"


# ---------------------------------------------------------------------------
# O1 — Golden trace
# ---------------------------------------------------------------------------

def test_o1_golden_trace(regen_golden):
    """O1: the canonical log of a short coin run matches the committed
    golden trace.

    Regeneration policy: this fixture may only be regenerated via
    ``pytest --regen-golden``, and the diff must be reviewed in the
    commit — never regenerated silently to make red go green.
    """
    _, log = run_to_log("coin", duration_min=480.0, max_patients=50, drain=False)

    if regen_golden:
        GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN_PATH.write_text(json.dumps(log, indent=2, default=str) + "\n")

    committed = json.loads(GOLDEN_PATH.read_text())
    assert log_digest(log) == log_digest(committed)


# ---------------------------------------------------------------------------
# O2 — Triage-distribution oracle (the anti-T3 kill-shot)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def o2_run():
    """Drained coin-style run with the arrival rate raised so at least
    100 casualties are observed."""
    scenario = copy.deepcopy(get_preset_raw("coin"))
    scenario["arrivals"]["base_rate_per_hour"] = 6.0
    engine, log = run_to_log(scenario, duration_min=1440.0, max_patients=300)
    arrivals = [e for e in log if e["event_type"] == "ARRIVAL"]
    assert len(arrivals) >= 100
    return scenario, arrivals


def test_o2_triage_distribution(o2_run):
    """O2: observed triage mix matches the configured distribution.

    Mode-agnostic: triage is read from emitted ARRIVAL events and
    compared to the scenario config — factory internals are not
    imported. This is the oracle that catches the R17 corruption
    (every casualty forced to T3).
    """
    scenario, arrivals = o2_run
    n = len(arrivals)
    shares = {k: v / n for k, v in Counter(e["triage"] for e in arrivals).items()}

    # (a) at least three distinct triage categories appear
    assert len(shares) >= 3

    # (b) no single category exceeds 90% of casualties
    assert max(shares.values()) <= 0.90

    # (c) observed T1/T2/T3 shares within ±0.15 absolute of config
    configured = scenario["arrivals"]["triage_distribution"]
    t1_observed = shares.get("T1_SURGICAL", 0.0) + shares.get("T1_MEDICAL", 0.0)
    t1_configured = configured.get("T1_SURGICAL", 0.0) + configured.get("T1_MEDICAL", 0.0)
    assert abs(t1_observed - t1_configured) <= 0.15
    assert abs(shares.get("T2", 0.0) - configured.get("T2", 0.0)) <= 0.15
    assert abs(shares.get("T3", 0.0) - configured.get("T3", 0.0)) <= 0.15


# ---------------------------------------------------------------------------
# O3 — Deterioration-direction oracle
# ---------------------------------------------------------------------------

def _bottlenecked_scenario():
    """Coin variant with R2 squeezed to one bed so R1 holds patients."""
    scenario = copy.deepcopy(get_preset_raw("coin"))
    for facility in scenario["facilities"]:
        if facility["id"] == "R2-MAIN":
            facility["beds"] = 1
    scenario["arrivals"]["base_rate_per_hour"] = 12.0
    scenario["arrivals"]["enable_mascal"] = False
    return scenario


def test_o3_deterioration_direction():
    """O3: severity_score is non-decreasing while a patient is held.

    Domain invariant — PFC deterioration direction must never silently
    reinterpret. Severity is sampled live at every hold/PFC event via an
    additive EventBus subscriber (no engine change). Direction only:
    magnitude and model choice are deferred to the step-4 PFC decision.
    """
    scenario = _bottlenecked_scenario()
    engine = build_engine_from_dict(scenario, seed=42)

    held_severity = defaultdict(list)
    hold_types = {"HOLD_START", "HOLD_RETRY", "PFC_START", "PFC_END", "HOLD_TIMEOUT"}

    def sample_severity(event):
        if event.event_type in hold_types and event.casualty_id in engine.patients:
            patient = engine.patients[event.casualty_id]
            held_severity[event.casualty_id].append(patient.severity_score)

    engine.event_bus.subscribe_all(sample_severity)
    engine.run(duration=0.0, max_patients=100)
    engine.step(720.0)

    assert held_severity, "no patient entered hold/PFC — bottleneck failed"
    for casualty_id, trajectory in held_severity.items():
        for earlier, later in zip(trajectory, trajectory[1:]):
            assert later >= earlier, (
                f"{casualty_id}: severity decreased while held ({earlier} -> {later})"
            )


# ---------------------------------------------------------------------------
# O5 — Graph congestion-shift (closes the R12 gap)
# ---------------------------------------------------------------------------

def test_o5_congestion_shifts_traffic():
    """O5: with both routing toggles ON, driving update_congestion()
    against one R1 shifts the traffic split toward the other.

    Routing is static Dijkstra over edge weights; dynamic
    occupancy->weight feedback is unbuilt (later tier). So the property
    asserted is the one that exists: pushed congestion reweights inbound
    edges and new arrivals route around the congested facility.
    Directional with tolerance — not exact counts.
    """
    scenario = {
        "name": "o5_branching",
        "operational_context": "COIN",
        "arrivals": {"base_rate_per_hour": 6.0, "enable_mascal": False},
        "facilities": [
            {"id": "POI-1", "name": "POI", "role": "POI", "beds": 0,
             "coordinates": [0.0, 0.0]},
            {"id": "R1-A", "name": "BAS A", "role": "R1", "beds": 4,
             "coordinates": [10.0, 0.0]},
            {"id": "R1-B", "name": "BAS B", "role": "R1", "beds": 4,
             "coordinates": [10.0, 5.0]},
            {"id": "R2-MAIN", "name": "FST", "role": "R2", "beds": 8,
             "or_tables": 2, "has_surgery": True, "has_blood": True,
             "coordinates": [30.0, 0.0]},
        ],
        "edges": [
            {"from": "POI-1", "to": "R1-A", "travel_time_minutes": 20, "transport": "GROUND"},
            {"from": "POI-1", "to": "R1-B", "travel_time_minutes": 20, "transport": "GROUND"},
            {"from": "R1-A", "to": "R2-MAIN", "travel_time_minutes": 35, "transport": "GROUND"},
            {"from": "R1-B", "to": "R2-MAIN", "travel_time_minutes": 35, "transport": "GROUND"},
        ],
    }
    toggles = SimulationToggles(
        enable_extracted_routing=True, enable_graph_routing=True,
    )
    engine = build_engine_from_dict(scenario, toggles=toggles, seed=42)
    engine.run(duration=0.0, max_patients=200)

    def r1_split(events):
        a = sum(1 for e in events if e.facility_id == "R1-A")
        b = sum(1 for e in events if e.facility_id == "R1-B")
        return a, b

    # Segment 1: undisturbed routing.
    engine.step(480.0)
    t_mark = engine.env.now
    seg1 = engine.event_store.events_of_type("FACILITY_ARRIVAL")
    a1, b1 = r1_split(seg1)
    assert a1 + b1 > 0

    # Mid-run: drive congestion against R1-A, and keep re-applying it so
    # the engine's own occupancy-based updates cannot silently reset it.
    engine.network.update_congestion("R1-A", 10.0)
    engine.event_bus.subscribe_all(
        lambda event: engine.network.update_congestion("R1-A", 10.0)
    )

    # Segment 2: traffic should shift toward R1-B.
    engine.step(480.0)
    seg2 = [
        e for e in engine.event_store.events_of_type("FACILITY_ARRIVAL")
        if e.sim_time > t_mark
    ]
    a2, b2 = r1_split(seg2)
    assert a2 + b2 > 0

    share_b_before = b1 / (a1 + b1)
    share_b_after = b2 / (a2 + b2)
    # Directional with tolerance: R1-B's share must clearly increase.
    assert share_b_after > share_b_before + 0.10


# ---------------------------------------------------------------------------
# O6 — Simultaneity tie-break determinism
# ---------------------------------------------------------------------------

def _simultaneous_arrival_scenario():
    """MASCAL clusters with zero spread: every cluster casualty arrives
    at the same simulated instant."""
    scenario = copy.deepcopy(get_preset_raw("coin"))
    scenario["arrivals"].update({
        "base_rate_per_hour": 0.5,
        "enable_mascal": True,
        "mascal_rate_per_hour": 2.0,
        "mascal_cluster_spread_minutes": 0.0,
        "mascal_cluster_mean": 6,
        "mascal_size_min": 4,
        "mascal_size_max": 8,
    })
    return scenario


def test_o6_simultaneity_tie_break_determinism():
    """O6: k >= 3 arrivals at one sim-time; two seed-42 runs give EQUAL
    digests, including the relative order of the simultaneous events.

    SimPy tie-breaking at identical timestamps is exactly where
    determinism and CRN break silently. Re-assert this oracle after
    step 3 (multi-POI) lands — concurrent arrival generators are the
    hazard it guards (C5).
    """
    scenario = _simultaneous_arrival_scenario()
    _, log_a = run_to_log(scenario, duration_min=480.0, max_patients=60)
    _, log_b = run_to_log(scenario, duration_min=480.0, max_patients=60)

    arrivals = [e for e in log_a if e["event_type"] == "ARRIVAL"]
    time_counts = Counter(e["sim_time"] for e in arrivals)
    k = max(time_counts.values())
    assert k >= 3, f"no simultaneous cluster observed (max k = {k})"

    # Digest equality covers content AND relative order of tied events.
    assert log_digest(log_a) == log_digest(log_b)

    # Belt-and-braces: the tied events' order is explicitly identical.
    tied_time = time_counts.most_common(1)[0][0]
    order_a = [e["casualty_id"] for e in log_a
               if e["event_type"] == "ARRIVAL" and e["sim_time"] == tied_time]
    order_b = [e["casualty_id"] for e in log_b
               if e["event_type"] == "ARRIVAL" and e["sim_time"] == tied_time]
    assert order_a == order_b
