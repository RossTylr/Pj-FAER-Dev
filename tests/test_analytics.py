"""Tests for analytics/ (Pattern E decoupling).

Two modes:
  1. Unit tests: AnalyticsEngine + views with synthetic events (no SimPy)
  2. Integration: wire to real engine EventBus, compare with metrics
"""

from __future__ import annotations

import importlib
from unittest.mock import Mock

import pytest

from faer_dev.analytics.engine import AnalyticsEngine, MaterialisedView
from faer_dev.analytics.views import FacilityLoadView, GoldenHourView, OutcomeView
from faer_dev.events.bus import EventBus
from faer_dev.events.models import SimEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(event_type: str, sim_time: float = 0.0, **kwargs) -> SimEvent:
    """Create a minimal SimEvent for testing."""
    return SimEvent(event_type=event_type, sim_time=sim_time, **kwargs)


# ===========================================================================
# Purity Tests
# ===========================================================================

class TestAnalyticsPurity:
    """Verify analytics has no SimPy or engine state dependency."""

    def test_no_simpy_import_engine(self):
        source = importlib.util.find_spec("faer_dev.analytics.engine")
        assert source is not None and source.origin is not None
        with open(source.origin) as f:
            content = f.read()
        assert "import simpy" not in content
        assert "from simpy" not in content

    def test_no_simpy_import_views(self):
        source = importlib.util.find_spec("faer_dev.analytics.views")
        assert source is not None and source.origin is not None
        with open(source.origin) as f:
            content = f.read()
        assert "import simpy" not in content
        assert "from simpy" not in content

    def test_no_engine_import(self):
        """analytics/ must not import from simulation/engine.py."""
        for mod_name in ("faer_dev.analytics.engine", "faer_dev.analytics.views"):
            source = importlib.util.find_spec(mod_name)
            assert source is not None and source.origin is not None
            with open(source.origin) as f:
                content = f.read()
            assert "simulation.engine" not in content
            assert "PolyhybridEngine" not in content


# ===========================================================================
# AnalyticsEngine Unit Tests
# ===========================================================================

class TestAnalyticsEngine:
    """AnalyticsEngine integration with synthetic events."""

    def test_view_registration(self):
        bus = EventBus()
        analytics = AnalyticsEngine(bus)
        view = OutcomeView()
        analytics.register_view("outcomes", view)
        assert "outcomes" in analytics._views

    def test_event_dispatch_to_views(self):
        bus = EventBus()
        analytics = AnalyticsEngine(bus)
        view = OutcomeView()
        analytics.register_view("outcomes", view)

        bus.publish(_make_event("DISPOSITION", sim_time=100.0,
                                casualty_id="C1", metadata={"outcome": "RTD"}))

        snap = analytics.get_view("outcomes")
        assert snap["total_dispositions"] == 1

    def test_reset_clears_all_views(self):
        bus = EventBus()
        analytics = AnalyticsEngine(bus)
        view = OutcomeView()
        analytics.register_view("outcomes", view)

        bus.publish(_make_event("DISPOSITION", sim_time=50.0,
                                casualty_id="C1", metadata={"outcome": "RTD"}))
        assert analytics.get_view("outcomes")["total_dispositions"] == 1

        analytics.reset_all()
        assert analytics.get_view("outcomes")["total_dispositions"] == 0

    def test_materialised_view_protocol(self):
        """All views must satisfy MaterialisedView protocol."""
        for ViewClass in (OutcomeView, FacilityLoadView, GoldenHourView):
            view = ViewClass()
            assert isinstance(view, MaterialisedView)


# ===========================================================================
# Individual View Tests
# ===========================================================================

class TestOutcomeView:
    def test_counts_dispositions(self):
        view = OutcomeView()
        view.update(_make_event("DISPOSITION", metadata={"outcome": "RTD"}))
        view.update(_make_event("DISPOSITION", metadata={"outcome": "RTD"}))
        view.update(_make_event("DISPOSITION", metadata={"outcome": "DECEASED"}))
        snap = view.snapshot()
        assert snap["total_dispositions"] == 3
        assert snap["outcomes"]["RTD"] == 2
        assert snap["outcomes"]["DECEASED"] == 1

    def test_ignores_non_disposition(self):
        view = OutcomeView()
        view.update(_make_event("ARRIVAL"))
        view.update(_make_event("TREATMENT_START"))
        assert view.snapshot()["total_dispositions"] == 0


class TestFacilityLoadView:
    def test_tracks_load(self):
        view = FacilityLoadView()
        view.update(_make_event("FACILITY_ARRIVAL", facility_id="R1"))
        view.update(_make_event("FACILITY_ARRIVAL", facility_id="R1"))
        snap = view.snapshot()
        assert snap["R1"]["current"] == 2
        assert snap["R1"]["peak"] == 2

    def test_disposition_decrements(self):
        view = FacilityLoadView()
        view.update(_make_event("FACILITY_ARRIVAL", facility_id="R1"))
        view.update(_make_event("DISPOSITION", facility_id="R1"))
        snap = view.snapshot()
        assert snap["R1"]["current"] == 0
        assert snap["R1"]["peak"] == 1


class TestGoldenHourView:
    def test_tracks_arrival_to_disposition(self):
        view = GoldenHourView()
        view.update(_make_event("ARRIVAL", sim_time=10.0, casualty_id="C1"))
        view.update(_make_event("DISPOSITION", sim_time=70.0, casualty_id="C1"))
        snap = view.snapshot()
        assert snap["total_tracked"] == 1
        assert snap["mean_minutes"] == 60.0

    def test_pct_within_60(self):
        view = GoldenHourView()
        view.update(_make_event("ARRIVAL", sim_time=0.0, casualty_id="C1"))
        view.update(_make_event("DISPOSITION", sim_time=50.0, casualty_id="C1"))
        view.update(_make_event("ARRIVAL", sim_time=0.0, casualty_id="C2"))
        view.update(_make_event("DISPOSITION", sim_time=90.0, casualty_id="C2"))
        snap = view.snapshot()
        assert snap["pct_within_60"] == 0.5

    def test_empty_snapshot(self):
        view = GoldenHourView()
        snap = view.snapshot()
        assert snap["total_tracked"] == 0
        assert snap["mean_minutes"] == 0.0


# ===========================================================================
# Integration: wire to real engine
# ===========================================================================

class TestAnalyticsIntegration:
    """Wire AnalyticsEngine to real engine run, verify views populate."""

    def test_views_populated_after_run(self):
        from faer_dev.config.builder import build_engine_from_preset
        from faer_dev.decisions.mode import SimulationToggles

        engine = build_engine_from_preset(
            "coin", seed=42,
            toggles=SimulationToggles(enable_typed_emitter=True),
        )

        analytics = AnalyticsEngine(engine.event_bus)
        analytics.register_view("outcomes", OutcomeView())
        analytics.register_view("facility_load", FacilityLoadView())
        analytics.register_view("golden_hour", GoldenHourView())

        metrics = engine.run(duration=600.0, max_patients=20)

        outcome_snap = analytics.get_view("outcomes")
        assert outcome_snap["total_dispositions"] == metrics["completed"]

        load_snap = analytics.get_view("facility_load")
        assert len(load_snap) > 0
