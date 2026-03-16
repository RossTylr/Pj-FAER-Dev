"""Tests for routing.py (EX-1 extraction).

These tests validate that the extracted routing module produces
identical decisions to the inline engine code, and that it has
zero SimPy dependency.

Run: pytest tests/test_routing.py -v
"""
import pytest
import importlib


class TestRoutingModulePurity:
    """Verify routing.py has no SimPy contamination."""

    def test_no_simpy_import(self):
        """routing.py must have zero SimPy imports (HC-6)."""
        # This test will work once routing.py is populated
        try:
            import faer_dev.routing as routing_mod
            source = importlib.util.find_spec("faer_dev.routing")
            if source and source.origin:
                with open(source.origin) as f:
                    content = f.read()
                assert "import simpy" not in content
                assert "from simpy" not in content
        except ImportError:
            pytest.skip("routing.py not yet implemented")


class TestRoutingDecision:
    """Unit tests for get_next_destination() — no SimPy fixtures needed."""

    def test_end_of_chain_returns_none(self, rng):
        """When no next facility exists, next_facility should be None."""
        pytest.skip("Implement after NB34 builds routing.py")

    def test_contested_route_denial(self, rng):
        """Contested route with high denial_prob should return is_denied=True."""
        pytest.skip("Implement after NB34 builds routing.py")

    def test_uncontested_route(self, rng):
        """Uncontested route should never be denied."""
        pytest.skip("Implement after NB34 builds routing.py")

    def test_travel_time_from_network(self, rng):
        """Travel time should match network edge weight."""
        pytest.skip("Implement after NB34 builds routing.py")


class TestRoutingRegression:
    """Toggle-gated regression: old path vs new path on same seed."""

    def test_nb32_identical_output(self, nb32_config):
        """NB32 acceptance test: 20 casualties, seed=42, zero difference."""
        pytest.skip("Implement after NB34 builds routing.py and engine wiring")
