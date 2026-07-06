"""S1.1 facility context writer — AC-W.1–W.5 (BUILD_S1_1.md v1.1 §3).

Test isolation: py_trees Blackboard storage is PROCESS-GLOBAL and shared
across every SimBlackboard instance, so it leaks across tests. Every test
in this module relies on the autouse ``_bt_blackboard_cleanup`` fixture
(tests/conftest.py:46-55), which clears
``py_trees.blackboard.Blackboard.storage`` before and after each test.
Without it, green here would be order-dependent and meaningless.

Fixtures are inline dicts (no YAML under tests/); seed=42 throughout.
"""

from __future__ import annotations

from typing import Dict, List

from faer_dev.config.builder import build_engine_from_dict
from faer_dev.decisions.blackboard import SimBlackboard
from faer_dev.decisions.mode import SimulationToggles
from faer_dev.events.canonical import log_digest

from tests.harness import run_to_log


# ── Inline two-facility fixture (model: test_capability_routing._killer_scenario) ──

def _two_facility_scenario() -> dict:
    """POI with direct edges to two R2s of unequal capacity; no other echelons."""
    return {
        "name": "s1_1_writer",
        "operational_context": "COIN",
        "arrivals": {"base_rate_per_hour": 6.0, "enable_mascal": False},
        "facilities": [
            {"id": "POI-1", "name": "POI", "role": "POI", "beds": 0,
             "coordinates": [0.0, 0.0]},
            {"id": "R2-A", "name": "FST A", "role": "R2", "beds": 2,
             "has_surgery": True, "coordinates": [10.0, 0.0]},
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


_WRITER_EVENT_TYPES = ("FACILITY_ARRIVAL", "TREATMENT_START", "TREATMENT_END")


def _facility_counts(log: List[Dict], facility_id: str) -> Dict[str, int]:
    """Count writer-site events for one facility from the canonical log."""
    counts = {t: 0 for t in _WRITER_EVENT_TYPES}
    for event in log:
        if event["facility_id"] == facility_id and event["event_type"] in counts:
            counts[event["event_type"]] += 1
    return counts


# ── T-W-1 KILLER (↔AC-W.1) ─────────────────────────────────────────────────


def test_t_w_1_killer_snapshot_matches_event_stream_derivation():
    """T-W-1 (↔AC-W.1): writer ON, undrained two-facility run — the final
    blackboard snapshot must equal an independent derivation from the event
    stream. Positive assertion; "no crash" is not evidence.

    Engine call-sites under test (cited): FACILITY_ARRIVAL emission at
    engine.py:963; post-bed-acquire after the TREATMENT_START log in
    ``_treat_in_queue`` (engine.py:1161-1164); post-bed-release at the
    ``with``-block context exit (engine.py:1184 vicinity — TREATMENT_END
    logs INSIDE the block, so occupancy only reflects the release at exit).

    Derivation: per facility, beds_available[fid] == capacity −
    (#TREATMENT_START − #TREATMENT_END); the global scalar pair matches the
    LAST-written facility (the facility of the last writer-site event).
    Isolation via the autouse ``_bt_blackboard_cleanup`` fixture.
    """
    toggles = SimulationToggles(enable_facility_writer=True)
    engine, log = run_to_log(
        _two_facility_scenario(), seed=42, duration_min=480.0,
        max_patients=30, toggles=toggles, drain=False,
    )
    snapshot = engine._blackboard.snapshot()
    capacities = {"R2-A": 2, "R2-B": 8}

    writer_events = [e for e in log if e["event_type"] in _WRITER_EVENT_TYPES]
    assert writer_events, "fixture produced no writer-site events"

    # Per-facility dict entries vs event-stream derivation.
    beds_available = snapshot["facility_beds_available"]
    for fid, capacity in capacities.items():
        counts = _facility_counts(log, fid)
        if any(counts.values()):
            occupancy = counts["TREATMENT_START"] - counts["TREATMENT_END"]
            assert beds_available[fid] == capacity - occupancy, fid
        else:
            # Never written — write-through semantics leave no entry.
            assert fid not in beds_available, fid

    # Scalar pair vs derivation for the LAST-written facility.
    last_event = writer_events[-1]
    last_fid = last_event["facility_id"]
    counts = _facility_counts(log, last_fid)
    occupancy = counts["TREATMENT_START"] - counts["TREATMENT_END"]
    assert snapshot["facility_utilisation"] == occupancy / capacities[last_fid]
    # Waiting = arrived-not-yet-treating; at a FACILITY_ARRIVAL write-site
    # the just-arrived casualty has not yet requested a bed, so the live
    # resource queue excludes it.
    expected_waiting = counts["FACILITY_ARRIVAL"] - counts["TREATMENT_START"]
    if last_event["event_type"] == "FACILITY_ARRIVAL":
        expected_waiting -= 1
    assert snapshot["fst_queue_depth"] == expected_waiting


# ── T-W-2 SENTINEL (↔AC-W.2, collision C10) ────────────────────────────────


def test_t_w_2_sentinel_preserves_factory_mascal_value():
    """T-W-2 (↔AC-W.2): ``set_facility_context`` with no mascal argument must
    NOT clobber a factory-style per-casualty ``mascal_active`` value.

    Red before the sentinel amendment: the current signature defaults
    ``mascal_active=False`` and writes it unconditionally
    (blackboard.py:151-160), so the factory's True is overwritten.
    Isolation via the autouse ``_bt_blackboard_cleanup`` fixture.
    """
    board = SimBlackboard(name="test")
    board.set("mascal_active", True)  # factory-style per-casualty write

    board.set_facility_context(utilisation=0.5, fst_queue=2)

    assert board.get("mascal_active") is True
    assert board.get("facility_utilisation") == 0.5
    assert board.get("fst_queue_depth") == 2


def test_t_w_2_sentinel_explicit_mascal_still_writes():
    """T-W-2 companion: an EXPLICIT ``mascal_active`` argument must still be
    written — the sentinel suppresses only the omitted-argument case.
    Isolation via the autouse ``_bt_blackboard_cleanup`` fixture.
    """
    board = SimBlackboard(name="test")
    board.set("mascal_active", True)

    board.set_facility_context(utilisation=0.1, fst_queue=0, mascal_active=False)

    assert board.get("mascal_active") is False


def test_t_w_2_combined_toggles_smoke_inverted_plus_writer():
    """T-W-2 companion smoke (§3): inverted factory + writer ON on a
    coin-derived drained run — green, Rule-4 conserved (drained special
    case ``arrivals == dispositions``). The two SimBlackboard instances
    share py_trees' process-global storage by construction; the sentinel
    is what makes that safe. Isolation via the autouse
    ``_bt_blackboard_cleanup`` fixture.
    """
    toggles = SimulationToggles(
        factory_mode="inverted", enable_facility_writer=True,
    )
    engine, log = run_to_log(
        "coin", seed=42, duration_min=240.0, max_patients=20,
        toggles=toggles, drain=True,
    )
    arrivals = sum(1 for e in log if e["event_type"] == "ARRIVAL")
    dispositions = sum(1 for e in log if e["event_type"] == "DISPOSITION")
    assert arrivals > 0
    assert arrivals == dispositions


# ── T-W-3a TRACE NEUTRALITY (↔AC-W.3) ──────────────────────────────────────


def test_t_w_3a_writer_toggle_is_trace_neutral():
    """T-W-3a (↔AC-W.3): writer ON vs OFF, same scenario/seed — canonical
    digests byte-identical. Basis: zero live readers (FQ1) and the writer
    consumes no RNG and emits no events.

    If (a) ever fails, a consumer went live — STOP and re-gate; this test
    is the standing tripwire.

    (3b, defaults untouched, is the suite-level O1 golden test in
    tests/test_oracles.py.) Isolation via ``_bt_blackboard_cleanup``.
    """
    _, log_off = run_to_log(
        "coin", seed=42, duration_min=480.0, max_patients=50, drain=False,
    )
    _, log_on = run_to_log(
        "coin", seed=42, duration_min=480.0, max_patients=50,
        toggles=SimulationToggles(enable_facility_writer=True), drain=False,
    )
    assert log_digest(log_on) == log_digest(log_off)


# ── T-W-4 DETERMINISM (↔AC-W.4) ────────────────────────────────────────────


def test_t_w_4_writer_on_double_run_deterministic():
    """T-W-4 (↔AC-W.4): writer ON, identical double run — canonical digests
    equal. Isolation via the autouse ``_bt_blackboard_cleanup`` fixture is
    load-bearing here: without clearing the process-global py_trees storage
    the second run would start from the first run's residue.
    """
    toggles = SimulationToggles(enable_facility_writer=True)
    _, log_one = run_to_log(
        _two_facility_scenario(), seed=42, duration_min=480.0,
        max_patients=30, toggles=toggles, drain=False,
    )
    _, log_two = run_to_log(
        _two_facility_scenario(), seed=42, duration_min=480.0,
        max_patients=30, toggles=toggles, drain=False,
    )
    assert log_digest(log_one) == log_digest(log_two)


# ── T-W-5 NO ALIASING (↔AC-W.5) ────────────────────────────────────────────


def test_t_w_5_no_aliasing_colocated_reads():
    """T-W-5 (↔AC-W.5): two concurrently active facilities — at each
    ``update()`` invocation a colocated read observes that facility's own
    scalar values, and end-state dict entries are independently correct
    for both facilities.

    Approach (choice cited per §3): dict-correctness + interleaved-write
    unit calls on a built engine, with occupancy manufactured directly on
    the SimPy resources — a spy/wrapper on ``update()`` would add nothing
    over direct colocated reads. Isolation via ``_bt_blackboard_cleanup``.
    """
    toggles = SimulationToggles(enable_facility_writer=True)
    engine = build_engine_from_dict(
        _two_facility_scenario(), toggles=toggles, seed=42,
    )
    writer = engine._facility_writer
    board = engine._blackboard
    queue_a = engine.queues["R2-A"]
    queue_b = engine.queues["R2-B"]

    # Manufacture distinct live states: R2-A full (2/2) with 1 waiting;
    # R2-B partially occupied (3/8), none waiting.
    for _ in range(3):
        queue_a.resource.request(priority=1)
    for _ in range(3):
        queue_b.resource.request(priority=1)
    assert (queue_a.count, queue_a.queue_length) == (2, 1)
    assert (queue_b.count, queue_b.queue_length) == (3, 0)

    writer.update("R2-A")
    assert board.get("facility_utilisation") == 1.0
    assert board.get("fst_queue_depth") == 1
    assert board.get("facility_beds_available")["R2-A"] == 0

    writer.update("R2-B")
    assert board.get("facility_utilisation") == 3 / 8
    assert board.get("fst_queue_depth") == 0
    beds = board.get("facility_beds_available")
    assert beds["R2-B"] == 5
    assert beds["R2-A"] == 0  # earlier entry untouched — no aliasing

    writer.update("R2-A")  # interleave back
    assert board.get("facility_utilisation") == 1.0
    assert board.get("fst_queue_depth") == 1
    beds = board.get("facility_beds_available")
    assert beds["R2-A"] == 0
    assert beds["R2-B"] == 5  # other facility's entry survives the rewrite
