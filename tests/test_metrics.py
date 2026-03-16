"""Tests for metrics.py (EX-2 extraction).

Validates compute_metrics() produces identical results to
engine.get_metrics() and works without SimPy fixtures.

Run: pytest tests/test_metrics.py -v
"""
import pytest


class TestMetricsPurity:
    """Verify metrics.py has no SimPy contamination."""

    def test_no_simpy_import(self):
        pytest.skip("Implement after NB35 builds metrics.py")


class TestComputeMetrics:
    """Unit tests for compute_metrics() with mock EventStore."""

    def test_empty_store_returns_zeros(self):
        pytest.skip("Implement after NB35")

    def test_triage_distribution_correct(self):
        pytest.skip("Implement after NB35")

    def test_frozen_dataclass_output(self):
        """SimulationMetrics must be frozen (immutable)."""
        pytest.skip("Implement after NB35")


class TestMetricsRegression:
    """Toggle-gated regression: old get_metrics() vs new compute_metrics()."""

    def test_nb32_identical_metrics(self, nb32_config):
        pytest.skip("Implement after NB35 and engine wiring")
