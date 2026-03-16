"""Tests for metrics.py (EX-2 extraction).

Two modes:
  1. Unit tests: test compute_metrics() in isolation (SimPy-independence)
  2. Regression tests: run full engine toggle OFF vs ON, same seed, assert identical
"""

from __future__ import annotations

import importlib

import pytest

from faer_dev.core.enums import OperationalContext
from faer_dev.core.schemas import Facility
from faer_dev.decisions.mode import SimulationToggles
from faer_dev.simulation.engine import PolyhybridEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_engine(toggles: SimulationToggles, seed: int = 42, max_patients: int = 20):
    """Run engine with COIN preset and return metrics dict."""
    from faer_dev.config.builder import build_engine_from_preset

    engine = build_engine_from_preset("coin", seed=seed, toggles=toggles)
    return engine.run(duration=600.0, max_patients=max_patients)


# ===========================================================================
# Unit Tests — metrics.py purity
# ===========================================================================

class TestMetricsPurity:
    """Verify metrics.py has no SimPy contamination."""

    def test_no_simpy_import(self):
        """metrics.py must have zero SimPy imports (HC-6)."""
        source = importlib.util.find_spec("faer_dev.metrics")
        assert source is not None and source.origin is not None
        with open(source.origin) as f:
            content = f.read()
        assert "import simpy" not in content
        assert "from simpy" not in content


class TestComputeMetrics:
    """Unit tests for compute_metrics() with mock data."""

    def test_empty_data_returns_zeros(self):
        """Empty inputs should produce zero counts."""
        from unittest.mock import Mock

        from faer_dev.metrics import compute_metrics

        transport_pool = Mock()
        transport_pool.metrics.to_dict.return_value = {}
        mascal_detector = Mock()
        mascal_detector.activation_count = 0
        mascal_detector.active = False

        result = compute_metrics(
            events=[],
            completed_patients=[],
            active_patients={},
            queues={},
            transport_pool=transport_pool,
            mascal_detector=mascal_detector,
        )

        assert result["total_arrivals"] == 0
        assert result["completed"] == 0
        assert result["in_system"] == 0
        assert result["facilities"] == {}
        assert result["outcomes"] == {}

    def test_arrival_count(self):
        """Should count ARRIVAL events correctly."""
        from unittest.mock import Mock

        from faer_dev.metrics import compute_metrics

        events = [
            {"type": "ARRIVAL", "id": "C1"},
            {"type": "ARRIVAL", "id": "C2"},
            {"type": "TREATMENT_START", "id": "C1"},
        ]

        transport_pool = Mock()
        transport_pool.metrics.to_dict.return_value = {}
        mascal_detector = Mock()
        mascal_detector.activation_count = 0
        mascal_detector.active = False

        result = compute_metrics(
            events=events,
            completed_patients=[],
            active_patients={"C1": Mock(), "C2": Mock()},
            queues={},
            transport_pool=transport_pool,
            mascal_detector=mascal_detector,
        )

        assert result["total_arrivals"] == 2
        assert result["in_system"] == 2


# ===========================================================================
# Regression Tests — full engine, toggle OFF vs ON, same seed
# ===========================================================================

class TestMetricsRegressionEquivalence:
    """Prove extracted metrics produces identical engine output."""

    def test_identical_metrics_seed42(self):
        m_legacy = _run_engine(SimulationToggles(enable_extracted_metrics=False))
        m_extracted = _run_engine(SimulationToggles(enable_extracted_metrics=True))

        assert m_legacy["total_arrivals"] == m_extracted["total_arrivals"]
        assert m_legacy["completed"] == m_extracted["completed"]
        assert m_legacy["in_system"] == m_extracted["in_system"]
        assert m_legacy["outcomes"] == m_extracted["outcomes"]
        assert m_legacy["facilities"] == m_extracted["facilities"]
        assert m_legacy["transport"] == m_extracted["transport"]
        assert m_legacy["mascal_detector"] == m_extracted["mascal_detector"]
        if "golden_hour" in m_legacy:
            assert m_legacy["golden_hour"] == m_extracted["golden_hour"]

    def test_identical_metrics_seed99(self):
        m_legacy = _run_engine(
            SimulationToggles(enable_extracted_metrics=False), seed=99
        )
        m_extracted = _run_engine(
            SimulationToggles(enable_extracted_metrics=True), seed=99
        )

        assert m_legacy["total_arrivals"] == m_extracted["total_arrivals"]
        assert m_legacy["completed"] == m_extracted["completed"]
        assert m_legacy["outcomes"] == m_extracted["outcomes"]
        assert m_legacy["facilities"] == m_extracted["facilities"]

    def test_determinism_both_modes(self):
        """Same seed → same output in both modes."""
        m1 = _run_engine(SimulationToggles(enable_extracted_metrics=False))
        m2 = _run_engine(SimulationToggles(enable_extracted_metrics=False))
        assert m1 == m2

        m3 = _run_engine(SimulationToggles(enable_extracted_metrics=True))
        m4 = _run_engine(SimulationToggles(enable_extracted_metrics=True))
        assert m3 == m4

    def test_both_toggles_combined(self):
        """Both routing + metrics toggles ON should still match all-OFF."""
        m_legacy = _run_engine(SimulationToggles(
            enable_extracted_routing=False,
            enable_extracted_metrics=False,
        ))
        m_both = _run_engine(SimulationToggles(
            enable_extracted_routing=True,
            enable_extracted_metrics=True,
        ))

        assert m_legacy["total_arrivals"] == m_both["total_arrivals"]
        assert m_legacy["completed"] == m_both["completed"]
        assert m_legacy["outcomes"] == m_both["outcomes"]
