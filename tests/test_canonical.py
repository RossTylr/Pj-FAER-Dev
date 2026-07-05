"""Acceptance tests for the canonical event serialiser (F0.1).

Every typed event carries ``event_id`` (uuid4) and ``wall_time``
(``datetime.now``), so two identical seed-42 runs hash differently on the
raw store (MAAFI R1). The canonical serialiser strips exactly those two
fields so that replay and golden-trace comparison report real differences
only — determinism is asserted on meaningful fields alone.
"""

import pytest

from faer_dev.config.builder import build_engine_from_preset
from faer_dev.events.canonical import canonical_event, canonical_log, log_digest
from faer_dev.events.serialization import EventSerializer


def _raw_typed_log(seed: int):
    """Run the coin preset and return the typed store as raw dicts."""
    engine = build_engine_from_preset("coin", seed=seed)
    engine.run(duration=480.0, max_patients=50)
    return [EventSerializer.event_to_dict(e) for e in engine.event_store.query()]


@pytest.fixture(scope="module")
def seed42_logs():
    """Two independent seed-42 coin runs, as raw typed-event dicts."""
    return _raw_typed_log(42), _raw_typed_log(42)


def test_ac_f01a_identical_seed42_runs_equal_digest(seed42_logs):
    """AC-F0.1a: two seed-42 runs produce EQUAL canonical digests."""
    log_a, log_b = seed42_logs
    assert len(log_a) > 0
    assert log_digest(log_a) == log_digest(log_b)


def test_ac_f01b_raw_logs_are_not_equal(seed42_logs):
    """AC-F0.1b: the RAW logs of those two runs differ.

    Proves the serialiser does real work (stripping uuid4 and wall-clock
    fields) rather than passing vacuously.
    """
    log_a, log_b = seed42_logs
    assert log_a != log_b


def test_ac_f01c_different_seeds_different_digest(seed42_logs):
    """AC-F0.1c: seed 42 vs seed 43 digests DIFFER.

    Guards against over-normalisation erasing real behavioural differences.
    """
    log_42, _ = seed42_logs
    assert log_digest(log_42) != log_digest(_raw_typed_log(43))


def test_canonical_event_strips_only_nondeterministic_fields(seed42_logs):
    """The canonical form drops event_id and wall_time, sorts keys, and
    leaves every other value untouched (floats are NOT rounded)."""
    log_a, _ = seed42_logs
    raw = log_a[0]
    canon = canonical_event(raw)
    assert "event_id" not in canon
    assert "wall_time" not in canon
    assert list(canon.keys()) == sorted(canon.keys())
    for key, value in canon.items():
        assert value == raw[key]
    # The input dict is not mutated.
    assert "event_id" in raw and "wall_time" in raw


def test_canonical_log_preserves_order(seed42_logs):
    """canonical_log maps events one-to-one, preserving order."""
    log_a, _ = seed42_logs
    canon = canonical_log(log_a)
    assert len(canon) == len(log_a)
    assert [e["sim_time"] for e in canon] == [e["sim_time"] for e in log_a]
