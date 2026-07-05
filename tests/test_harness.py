"""Acceptance tests for the run/sweep harness (F0.2).

``run_to_log`` drains the engine so conservation assertions are not
poisoned by the undrained-cutoff artefact (MAAFI F13/F12: ARRIVAL 31 vs
DISPOSITION 28 in a default coin run). ``sweep`` formalises the
R16b-proven dict-edit pattern so a scalar can be varied across runs
without editing YAML on disk.
"""

from faer_dev.config.builder import get_preset_raw

from tests.harness import run_to_log, sweep


def _count(engine, event_type: str) -> int:
    return len(engine.event_store.events_of_type(event_type))


def test_ac_f02a_drained_run_conserves_casualties():
    """AC-F0.2a: drained coin run — ARRIVAL count == DISPOSITION count."""
    engine, log = run_to_log("coin")
    arrivals = _count(engine, "ARRIVAL")
    dispositions = _count(engine, "DISPOSITION")
    assert arrivals > 0
    assert arrivals == dispositions


def test_ac_f02b_fixture_is_deterministic():
    """AC-F0.2b: two identical run_to_log calls give equal digests."""
    from faer_dev.events.canonical import log_digest

    _, log_a = run_to_log("coin")
    _, log_b = run_to_log("coin")
    assert log_digest(log_a) == log_digest(log_b)


def test_ac_f02c_sweep_is_ordered_and_repeatable():
    """AC-F0.2c: sweep over R1 beds returns keys in given order, n_reps
    values per key, and identical output when re-run."""

    def metric(engine, log):
        return _count(engine, "DISPOSITION")

    coin = get_preset_raw("coin")
    result_a = sweep(
        coin, "facilities.R1-ALPHA.beds", [2, 8], n_reps=3, metric_fn=metric
    )
    result_b = sweep(
        coin, "facilities.R1-ALPHA.beds", [2, 8], n_reps=3, metric_fn=metric
    )

    assert list(result_a.keys()) == [2, 8]
    assert all(len(reps) == 3 for reps in result_a.values())
    assert result_a == result_b


def test_sweep_does_not_mutate_base_scenario():
    """The dict-edit pattern deep-copies: the base scenario is untouched."""

    coin = get_preset_raw("coin")
    r1 = next(f for f in coin["facilities"] if f["id"] == "R1-ALPHA")
    beds_before = r1["beds"]

    sweep(
        coin,
        "facilities.R1-ALPHA.beds",
        [2],
        n_reps=1,
        metric_fn=lambda engine, log: _count(engine, "ARRIVAL"),
    )

    assert r1["beds"] == beds_before
