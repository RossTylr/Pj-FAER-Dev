"""Tests for emitter.py (EX-3 extraction).

Two modes:
  1. Unit tests: Protocol conformance, purity, K-7 closure
  2. Regression tests: full engine toggle OFF vs ON, same seed, identical output
"""

from __future__ import annotations

import importlib
from unittest.mock import Mock

import pytest

from faer_dev.decisions.mode import SimulationToggles
from faer_dev.emitter import EventEmitter, TypedEmitter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_engine(toggles: SimulationToggles, seed: int = 42, max_patients: int = 20):
    """Run engine with COIN preset and return (metrics, events_list)."""
    from faer_dev.config.builder import build_engine_from_preset

    engine = build_engine_from_preset("coin", seed=seed, toggles=toggles)
    metrics = engine.run(duration=600.0, max_patients=max_patients)
    return metrics, engine.events


# ===========================================================================
# Unit Tests — emitter.py purity and protocol
# ===========================================================================

class TestEmitterPurity:
    """Verify emitter.py has no SimPy contamination."""

    def test_no_simpy_import(self):
        """emitter.py must have zero SimPy imports (HC-6)."""
        source = importlib.util.find_spec("faer_dev.emitter")
        assert source is not None and source.origin is not None
        with open(source.origin) as f:
            content = f.read()
        assert "import simpy" not in content
        assert "from simpy" not in content

    def test_typed_emitter_satisfies_protocol(self):
        """TypedEmitter must satisfy EventEmitter Protocol."""
        mock_bus = Mock()
        emitter = TypedEmitter(events_list=[], event_bus=mock_bus)
        assert isinstance(emitter, EventEmitter)


class TestTypedEmitterUnit:
    """Unit tests for TypedEmitter without engine."""

    def test_emit_appends_legacy_dict(self):
        """emit() should append a legacy-format dict to events_list."""
        events = []
        bus = Mock()
        emitter = TypedEmitter(events, bus)

        patient = Mock()
        patient.id = "CAS-001"
        patient.triage = Mock(name="T2")
        patient.triage.name = "T2"
        patient.state = Mock(name="ALIVE")
        patient.state.name = "ALIVE"

        emitter.emit("ARRIVAL", patient, "POI", {"severity": 0.5}, 10.0)

        assert len(events) == 1
        assert events[0]["type"] == "ARRIVAL"
        assert events[0]["patient_id"] == "CAS-001"
        assert events[0]["time"] == 10.0
        assert events[0]["details"]["severity"] == 0.5

    def test_emit_publishes_to_bus(self):
        """emit() should publish a typed event to the EventBus."""
        events = []
        bus = Mock()
        emitter = TypedEmitter(events, bus)

        patient = Mock()
        patient.id = "CAS-001"
        patient.triage = Mock(name="T2")
        patient.triage.name = "T2"
        patient.state = Mock(name="ALIVE")
        patient.state.name = "ALIVE"

        emitter.emit("ARRIVAL", patient, "POI", {"severity": 0.5}, 10.0)

        bus.publish.assert_called_once()
        typed_event = bus.publish.call_args[0][0]
        assert typed_event.event_type == "ARRIVAL"
        assert typed_event.casualty_id == "CAS-001"
        assert typed_event.sim_time == 10.0

    def test_emit_raw_no_patient(self):
        """emit_raw() should work without a patient object."""
        events = []
        bus = Mock()
        emitter = TypedEmitter(events, bus)

        emitter.emit_raw("MASCAL_ACTIVATE", 50.0, {"arrival_rate": 25.0})

        assert len(events) == 1
        assert events[0]["type"] == "MASCAL_ACTIVATE"
        assert events[0]["patient_id"] is None
        assert events[0]["time"] == 50.0
        bus.publish.assert_called_once()


class TestK3Closure:
    """Verify _triage_decisions dead code is deleted."""

    def test_legacy_triage_decisions_deleted(self):
        """K-3: _triage_decisions() should not exist as module-level function."""
        import faer_dev.simulation.engine as engine_mod

        # The module-level function should be gone
        source = importlib.util.find_spec("faer_dev.simulation.engine")
        assert source is not None and source.origin is not None
        with open(source.origin) as f:
            content = f.read()
        # Should not have the function definition (only the comment about deletion)
        assert "def _triage_decisions(" not in content


# ===========================================================================
# Regression Tests — full engine, toggle OFF vs ON, same seed
# ===========================================================================

class TestEmitterRegressionEquivalence:
    """Prove typed emitter produces identical engine output."""

    def test_identical_event_counts_seed42(self):
        """Event type counts must match between legacy and typed paths."""
        from collections import Counter

        _, events_legacy = _run_engine(
            SimulationToggles(enable_typed_emitter=False)
        )
        _, events_typed = _run_engine(
            SimulationToggles(enable_typed_emitter=True)
        )

        legacy_counts = Counter(e["type"] for e in events_legacy)
        typed_counts = Counter(e["type"] for e in events_typed)
        assert legacy_counts == typed_counts

    def test_identical_metrics_seed42(self):
        m_legacy, _ = _run_engine(
            SimulationToggles(enable_typed_emitter=False)
        )
        m_typed, _ = _run_engine(
            SimulationToggles(enable_typed_emitter=True)
        )

        assert m_legacy["total_arrivals"] == m_typed["total_arrivals"]
        assert m_legacy["completed"] == m_typed["completed"]
        assert m_legacy["outcomes"] == m_typed["outcomes"]

    def test_identical_metrics_seed99(self):
        m_legacy, _ = _run_engine(
            SimulationToggles(enable_typed_emitter=False), seed=99
        )
        m_typed, _ = _run_engine(
            SimulationToggles(enable_typed_emitter=True), seed=99
        )

        assert m_legacy["total_arrivals"] == m_typed["total_arrivals"]
        assert m_legacy["completed"] == m_typed["completed"]
        assert m_legacy["outcomes"] == m_typed["outcomes"]

    def test_disposition_plus_in_system_equals_arrival(self):
        """KL-6: DISPOSITION + in_system == ARRIVAL (duration-limited run)."""
        metrics, events = _run_engine(
            SimulationToggles(enable_typed_emitter=True)
        )

        arrivals = sum(1 for e in events if e["type"] == "ARRIVAL")
        dispositions = sum(1 for e in events if e["type"] == "DISPOSITION")
        in_system = metrics["in_system"]
        assert arrivals == dispositions + in_system
        assert arrivals > 0

    def test_all_toggles_combined(self):
        """All three extraction toggles ON should still match all-OFF."""
        m_legacy, _ = _run_engine(SimulationToggles(
            enable_extracted_routing=False,
            enable_extracted_metrics=False,
            enable_typed_emitter=False,
        ))
        m_all, _ = _run_engine(SimulationToggles(
            enable_extracted_routing=True,
            enable_extracted_metrics=True,
            enable_typed_emitter=True,
        ))

        assert m_legacy["total_arrivals"] == m_all["total_arrivals"]
        assert m_legacy["completed"] == m_all["completed"]
        assert m_legacy["outcomes"] == m_all["outcomes"]
