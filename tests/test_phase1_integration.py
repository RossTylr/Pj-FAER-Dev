"""Phase 1 Integration Tests (NB39 equivalent in pytest).

Full regression suite: all Phase 1 toggles ON simultaneously.
This is the automated version of the NB39 integration gate notebook.
"""

from __future__ import annotations

import importlib

import pytest

from faer_dev.decisions.mode import SimulationToggles


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_OFF = SimulationToggles(
    enable_extracted_routing=False,
    enable_extracted_metrics=False,
    enable_typed_emitter=False,
    enable_extracted_pfc=False,
)

ALL_ON = SimulationToggles(
    enable_extracted_routing=True,
    enable_extracted_metrics=True,
    enable_typed_emitter=True,
    enable_extracted_pfc=True,
)


def _run(toggles: SimulationToggles, seed: int = 42, max_patients: int = 20):
    from faer_dev.config.builder import build_engine_from_preset

    engine = build_engine_from_preset("coin", seed=seed, toggles=toggles)
    metrics = engine.run(duration=600.0, max_patients=max_patients)
    return metrics, engine.events


# ===========================================================================
# All Toggles ON Regression
# ===========================================================================

class TestPhase1AllTogglesOn:
    """Run engine with ALL Phase 1 toggles enabled. Assert identical to baseline."""

    def test_metrics_identical_seed42(self):
        m_off, _ = _run(ALL_OFF)
        m_on, _ = _run(ALL_ON)

        assert m_off["total_arrivals"] == m_on["total_arrivals"]
        assert m_off["completed"] == m_on["completed"]
        assert m_off["in_system"] == m_on["in_system"]
        assert m_off["outcomes"] == m_on["outcomes"]
        assert m_off["facilities"] == m_on["facilities"]

    def test_metrics_identical_seed99(self):
        m_off, _ = _run(ALL_OFF, seed=99)
        m_on, _ = _run(ALL_ON, seed=99)

        assert m_off["total_arrivals"] == m_on["total_arrivals"]
        assert m_off["completed"] == m_on["completed"]
        assert m_off["outcomes"] == m_on["outcomes"]

    def test_event_counts_identical(self):
        """Every event type count must match."""
        from collections import Counter

        _, events_off = _run(ALL_OFF)
        _, events_on = _run(ALL_ON)

        counts_off = Counter(e["type"] for e in events_off)
        counts_on = Counter(e["type"] for e in events_on)
        assert counts_off == counts_on

    def test_deterministic_replay_hc2(self):
        """HC-2: Two runs with seed=42 produce identical output."""
        m1, _ = _run(ALL_ON)
        m2, _ = _run(ALL_ON)
        assert m1 == m2

    def test_disposition_invariant_kl6(self):
        """KL-6: DISPOSITION + in_system == ARRIVAL."""
        metrics, events = _run(ALL_ON)

        arrivals = sum(1 for e in events if e["type"] == "ARRIVAL")
        dispositions = sum(1 for e in events if e["type"] == "DISPOSITION")
        assert arrivals == dispositions + metrics["in_system"]
        assert arrivals > 0


# ===========================================================================
# Debt Closure
# ===========================================================================

class TestDebtClosure:
    """Verify Phase 1 debt items are closed."""

    def test_k3_legacy_triage_deleted(self):
        """K-3: _triage_decisions() must not exist in engine source."""
        source = importlib.util.find_spec("faer_dev.simulation.engine")
        assert source is not None and source.origin is not None
        with open(source.origin) as f:
            content = f.read()
        assert "def _triage_decisions(" not in content

    def test_k7_typed_emitter_wired(self):
        """K-7: TypedEmitter toggle exists and can be enabled."""
        toggles = SimulationToggles(enable_typed_emitter=True)
        assert toggles.enable_typed_emitter is True

    def test_all_extracted_modules_simpy_free(self):
        """HC-6: routing, metrics, emitter, pfc, analytics — zero SimPy imports."""
        for mod_name in (
            "faer_dev.routing",
            "faer_dev.metrics",
            "faer_dev.emitter",
            "faer_dev.pfc",
            "faer_dev.analytics.engine",
            "faer_dev.analytics.views",
        ):
            source = importlib.util.find_spec(mod_name)
            assert source is not None and source.origin is not None, f"{mod_name} not found"
            with open(source.origin) as f:
                content = f.read()
            assert "import simpy" not in content, f"{mod_name} has simpy import"
            assert "from simpy" not in content, f"{mod_name} has simpy import"


# ===========================================================================
# Analytics Integration
# ===========================================================================

class TestAnalyticsDecoupled:
    """Dashboard can read AnalyticsEngine, not engine state."""

    def test_analytics_populated_with_all_toggles(self):
        from faer_dev.analytics.engine import AnalyticsEngine
        from faer_dev.analytics.views import FacilityLoadView, GoldenHourView, OutcomeView
        from faer_dev.config.builder import build_engine_from_preset

        engine = build_engine_from_preset("coin", seed=42, toggles=ALL_ON)

        analytics = AnalyticsEngine(engine.event_bus)
        analytics.register_view("outcomes", OutcomeView())
        analytics.register_view("facility_load", FacilityLoadView())
        analytics.register_view("golden_hour", GoldenHourView())

        metrics = engine.run(duration=600.0, max_patients=20)

        outcome_snap = analytics.get_view("outcomes")
        assert outcome_snap["total_dispositions"] == metrics["completed"]
