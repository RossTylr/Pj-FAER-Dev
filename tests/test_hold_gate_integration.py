"""O4 — hold-gate sequence integration oracle (F0.3).

Rebuilt from the Red Team recipe (the passing /tmp test evaporated):
``_hold_timeout_override`` (engine.py:716) had zero callers and the
in-engine SimPy hold/PFC/timeout path had no integration test — only the
extracted pure functions were covered.

Recipe: bottleneck R2 to one bed, override the hold timeout to 75 min
(retries every 15 min, PFC triggers at 60 min), sustained arrivals; at
least one patient must traverse HOLD_START -> HOLD_RETRY -> PFC_START ->
HOLD_TIMEOUT in order.
"""

import copy

from faer_dev.config.builder import build_engine_from_dict, get_preset_raw


def test_o4_hold_gate_sequence():
    """O4: one patient traverses the full hold gate in order."""
    scenario = copy.deepcopy(get_preset_raw("coin"))
    for facility in scenario["facilities"]:
        if facility["id"] == "R2-MAIN":
            facility["beds"] = 1
    scenario["arrivals"]["base_rate_per_hour"] = 12.0
    scenario["arrivals"]["enable_mascal"] = False

    engine = build_engine_from_dict(scenario, seed=42)
    engine._hold_timeout_override = 75.0
    engine.run(duration=0.0, max_patients=100)
    engine.step(720.0)

    target = ["HOLD_START", "HOLD_RETRY", "PFC_START", "HOLD_TIMEOUT"]
    traversed = []
    timed_out = {e.casualty_id for e in engine.event_store.events_of_type("HOLD_TIMEOUT")}
    for casualty_id in timed_out:
        journey = [e.event_type for e in engine.event_store.patient_journey(casualty_id)]
        it = iter(journey)
        if all(step in it for step in target):
            traversed.append(casualty_id)

    assert traversed, (
        "no patient traversed HOLD_START -> HOLD_RETRY -> PFC_START -> "
        f"HOLD_TIMEOUT in order (patients timing out: {len(timed_out)})"
    )
