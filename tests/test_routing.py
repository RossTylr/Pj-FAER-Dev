"""Tests for extracted routing module.

Two modes:
  1. Unit tests: test routing.py in isolation with mocks (SimPy-independence)
  2. Regression tests: run full engine toggle OFF vs ON, same seed, assert identical
"""

from __future__ import annotations

import pytest

from faer_dev.core.enums import OperationalContext, Role, TriageCategory
from faer_dev.core.schemas import Casualty, Facility
from faer_dev.decisions.mode import SimulationToggles
from faer_dev.network.topology import TreatmentNetwork
from faer_dev.routing import (
    get_next_destination,
    triage_decisions,
    _find_highest_reachable,
)
from faer_dev.simulation.engine import (
    PolyhybridEngine,
    _get_next_destination,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_patient(triage: TriageCategory) -> Casualty:
    """Create a minimal Casualty for routing tests."""
    return Casualty(
        id=f"TEST-{triage.name}",
        name=f"Test {triage.name}",
        triage=triage,
        initial_triage=triage,
        created_at=0.0,
        state_changed_at=0.0,
    )


def _make_network():
    """3-node chain: POI -> R1 -> R2."""
    net = TreatmentNetwork()
    net.add_facility(Facility(id="POI", name="POI", role=Role.POI, capacity=50))
    net.add_facility(Facility(id="R1", name="R1", role=Role.R1, capacity=4))
    net.add_facility(Facility(id="R2", name="R2", role=Role.R2, capacity=8))
    net.add_route("POI", "R1", base_time=30.0)
    net.add_route("R1", "R2", base_time=45.0)
    return net


def _run_engine(toggles: SimulationToggles, seed: int = 42, max_patients: int = 20):
    """Run engine with 3-node chain and return metrics."""
    engine = PolyhybridEngine(
        context=OperationalContext.COIN,
        seed=seed,
        toggles=toggles,
    )
    engine.add_facility(Facility(id="POI", name="POI", role=Role.POI, capacity=50))
    engine.add_facility(Facility(id="R1", name="R1", role=Role.R1, capacity=4))
    engine.add_facility(Facility(id="R2", name="R2", role=Role.R2, capacity=8))
    engine.add_route("POI", "R1", time_minutes=30.0, transport="ground")
    engine.add_route("R1", "R2", time_minutes=45.0, transport="ground")
    return engine.run(duration=600.0, poi_id="POI", max_patients=max_patients)


# ===========================================================================
# Unit Tests — routing.py in isolation, no SimPy
# ===========================================================================

class TestTriageDecisions:
    """Test extracted triage_decisions() (K-3: legacy deleted, this is the only path)."""

    @pytest.mark.parametrize("triage", list(TriageCategory))
    def test_returns_valid_decisions(self, triage):
        patient = _make_patient(triage)
        decisions = triage_decisions(patient)
        assert "recommended_triage" in decisions
        assert "bypass_role1" in decisions
        assert "requires_dcs" in decisions
        assert "priority" in decisions

    def test_t1_surgical_bypass_and_dcs(self):
        d = triage_decisions(_make_patient(TriageCategory.T1_SURGICAL))
        assert d["bypass_role1"] is True
        assert d["requires_dcs"] is True
        assert d["priority"] == 1

    def test_t1_medical_bypass_no_dcs(self):
        d = triage_decisions(_make_patient(TriageCategory.T1_MEDICAL))
        assert d["bypass_role1"] is True
        assert d["requires_dcs"] is False
        assert d["priority"] == 1

    def test_t2_no_bypass(self):
        d = triage_decisions(_make_patient(TriageCategory.T2))
        assert d["bypass_role1"] is False
        assert d["priority"] == 2

    def test_t3_no_bypass(self):
        d = triage_decisions(_make_patient(TriageCategory.T3))
        assert d["bypass_role1"] is False
        assert d["priority"] == 3

    def test_t4_stays(self):
        d = triage_decisions(_make_patient(TriageCategory.T4))
        assert d["priority"] == 5


class TestGetNextDestination:
    """Test extracted get_next_destination() matches legacy _get_next_destination()."""

    @pytest.mark.parametrize("triage", list(TriageCategory))
    def test_matches_legacy_from_poi(self, triage):
        net = _make_network()
        patient = _make_patient(triage)
        decisions = triage_decisions(patient)
        poi = net.facilities["POI"]

        legacy = _get_next_destination(patient, poi, net, decisions)
        extracted = get_next_destination(patient, poi, net, decisions)
        assert legacy == extracted, f"Mismatch from POI for {triage.name}"

    @pytest.mark.parametrize("triage", list(TriageCategory))
    def test_matches_legacy_from_r1(self, triage):
        net = _make_network()
        patient = _make_patient(triage)
        decisions = triage_decisions(patient)
        r1 = net.facilities["R1"]

        legacy = _get_next_destination(patient, r1, net, decisions)
        extracted = get_next_destination(patient, r1, net, decisions)
        assert legacy == extracted, f"Mismatch from R1 for {triage.name}"

    def test_t3_rtd_from_r1(self):
        net = _make_network()
        patient = _make_patient(TriageCategory.T3)
        decisions = triage_decisions(patient)
        assert get_next_destination(patient, net.facilities["R1"], net, decisions) is None

    def test_t4_stays(self):
        net = _make_network()
        patient = _make_patient(TriageCategory.T4)
        decisions = triage_decisions(patient)
        assert get_next_destination(patient, net.facilities["POI"], net, decisions) is None

    def test_t1_surgical_bypasses_r1(self):
        net = _make_network()
        # Add direct POI->R2 edge for bypass
        net.add_route("POI", "R2", base_time=60.0)
        patient = _make_patient(TriageCategory.T1_SURGICAL)
        decisions = triage_decisions(patient)
        dest = get_next_destination(patient, net.facilities["POI"], net, decisions)
        assert dest == "R2"


# ===========================================================================
# Regression Tests — full engine, toggle OFF vs ON, same seed
# ===========================================================================

class TestRegressionEquivalence:
    """Prove extracted routing produces identical engine output."""

    def test_identical_metrics_seed42(self):
        m_legacy = _run_engine(SimulationToggles(enable_extracted_routing=False))
        m_extracted = _run_engine(SimulationToggles(enable_extracted_routing=True))

        assert m_legacy["total_arrivals"] == m_extracted["total_arrivals"]
        assert m_legacy["completed"] == m_extracted["completed"]
        assert m_legacy["in_system"] == m_extracted["in_system"]
        assert m_legacy["outcomes"] == m_extracted["outcomes"]

    def test_identical_metrics_seed99(self):
        m_legacy = _run_engine(
            SimulationToggles(enable_extracted_routing=False), seed=99
        )
        m_extracted = _run_engine(
            SimulationToggles(enable_extracted_routing=True), seed=99
        )

        assert m_legacy["total_arrivals"] == m_extracted["total_arrivals"]
        assert m_legacy["completed"] == m_extracted["completed"]
        assert m_legacy["outcomes"] == m_extracted["outcomes"]

    def test_determinism_both_modes(self):
        """Same seed → same output in both modes."""
        m1 = _run_engine(SimulationToggles(enable_extracted_routing=False))
        m2 = _run_engine(SimulationToggles(enable_extracted_routing=False))
        assert m1["total_arrivals"] == m2["total_arrivals"]
        assert m1["completed"] == m2["completed"]

        m3 = _run_engine(SimulationToggles(enable_extracted_routing=True))
        m4 = _run_engine(SimulationToggles(enable_extracted_routing=True))
        assert m3["total_arrivals"] == m4["total_arrivals"]
        assert m3["completed"] == m4["completed"]

    def test_preset_coin_equivalence(self):
        """Equivalence via preset builder path."""
        from faer_dev.config.builder import build_engine_from_preset

        e1 = build_engine_from_preset(
            "coin", seed=42,
            toggles=SimulationToggles(enable_extracted_routing=False),
        )
        m1 = e1.run(duration=480, max_patients=20)

        e2 = build_engine_from_preset(
            "coin", seed=42,
            toggles=SimulationToggles(enable_extracted_routing=True),
        )
        m2 = e2.run(duration=480, max_patients=20)

        assert m1["total_arrivals"] == m2["total_arrivals"]
        assert m1["completed"] == m2["completed"]
        assert m1["outcomes"] == m2["outcomes"]


# ===========================================================================
# Phase 1.5 — Graph Routing Tests
# ===========================================================================

def _make_multipath_network():
    """5-node topology: POI -> R1-ALPHA, POI -> R1-BRAVO, both -> R2."""
    net = TreatmentNetwork()
    net.add_facility(Facility(id="POI", name="POI", role=Role.POI, beds=50))
    net.add_facility(Facility(id="R1-ALPHA", name="R1-A", role=Role.R1, beds=4))
    net.add_facility(Facility(id="R1-BRAVO", name="R1-B", role=Role.R1, beds=4))
    net.add_facility(Facility(id="R2", name="R2", role=Role.R2, beds=8))
    net.add_route("POI", "R1-ALPHA", base_time=30.0)
    net.add_route("POI", "R1-BRAVO", base_time=30.0)
    net.add_route("R1-ALPHA", "R2", base_time=45.0)
    net.add_route("R1-BRAVO", "R2", base_time=45.0)
    return net


class TestGraphRouting:
    """Phase 1.5: Dijkstra routing via enable_graph_routing toggle."""

    @pytest.mark.parametrize("triage", list(TriageCategory))
    def test_linear_graph_matches_legacy(self, triage):
        """On a linear chain, graph routing must produce same result as legacy."""
        net = _make_network()
        patient = _make_patient(triage)
        decisions = triage_decisions(patient)
        poi = net.facilities["POI"]

        legacy = get_next_destination(
            patient, poi, net, decisions, use_graph_routing=False
        )
        graph = get_next_destination(
            patient, poi, net, decisions, use_graph_routing=True
        )
        assert legacy == graph, f"Mismatch for {triage.name}"

    @pytest.mark.parametrize("triage", list(TriageCategory))
    def test_linear_graph_matches_legacy_from_r1(self, triage):
        """On a linear chain from R1, graph routing matches legacy."""
        net = _make_network()
        patient = _make_patient(triage)
        decisions = triage_decisions(patient)
        r1 = net.facilities["R1"]

        legacy = get_next_destination(
            patient, r1, net, decisions, use_graph_routing=False
        )
        graph = get_next_destination(
            patient, r1, net, decisions, use_graph_routing=True
        )
        assert legacy == graph, f"Mismatch for {triage.name}"

    def test_multipath_routes_to_r1(self):
        """Graph routing on multi-path topology reaches an R1 node."""
        net = _make_multipath_network()
        patient = _make_patient(TriageCategory.T2)
        decisions = triage_decisions(patient)
        poi = net.facilities["POI"]

        dest = get_next_destination(
            patient, poi, net, decisions, use_graph_routing=True
        )
        assert dest in ("R1-ALPHA", "R1-BRAVO")

    def test_multipath_congestion_shifts_route(self):
        """Congestion on R1-ALPHA pushes Dijkstra to prefer R1-BRAVO."""
        net = _make_multipath_network()
        patient = _make_patient(TriageCategory.T2)
        decisions = triage_decisions(patient)
        poi = net.facilities["POI"]

        # Heavy congestion on ALPHA — makes inbound edges 10x heavier
        net.update_congestion("R1-ALPHA", congestion_factor=9.0)

        dest = get_next_destination(
            patient, poi, net, decisions, use_graph_routing=True
        )
        assert dest == "R1-BRAVO"

    def test_find_highest_reachable(self):
        """Helper finds highest-role reachable facility."""
        net = _make_network()
        poi = net.facilities["POI"]
        decisions = {"bypass_role1": False}
        target = _find_highest_reachable(poi, net, decisions)
        assert target == "R2"  # highest reachable from POI

    def test_find_highest_reachable_bypass(self):
        """With bypass_role1, skips R1 but still finds R2."""
        net = _make_network()
        # Need direct POI->R2 edge for bypass to work
        net.add_route("POI", "R2", base_time=60.0)
        poi = net.facilities["POI"]
        decisions = {"bypass_role1": True}
        target = _find_highest_reachable(poi, net, decisions)
        assert target == "R2"


class TestGraphRoutingRegression:
    """Full engine regression: graph routing on linear chain == legacy."""

    def test_linear_toggle_equivalence(self):
        """enable_graph_routing ON produces identical output on linear chain."""
        m_legacy = _run_engine(
            SimulationToggles(
                enable_extracted_routing=True,
                enable_graph_routing=False,
            )
        )
        m_graph = _run_engine(
            SimulationToggles(
                enable_extracted_routing=True,
                enable_graph_routing=True,
            )
        )
        assert m_legacy["total_arrivals"] == m_graph["total_arrivals"]
        assert m_legacy["completed"] == m_graph["completed"]
        assert m_legacy["outcomes"] == m_graph["outcomes"]

    def test_congestion_wiring_determinism(self):
        """Graph routing with congestion is deterministic (same seed = same output)."""
        toggles = SimulationToggles(
            enable_extracted_routing=True,
            enable_graph_routing=True,
        )
        m1 = _run_engine(toggles, seed=42)
        m2 = _run_engine(toggles, seed=42)
        assert m1["total_arrivals"] == m2["total_arrivals"]
        assert m1["completed"] == m2["completed"]
        assert m1["outcomes"] == m2["outcomes"]

    def test_multipath_both_r1_get_traffic(self):
        """On 5-node topology with congestion, both R1 nodes receive traffic."""
        engine = PolyhybridEngine(
            context=OperationalContext.COIN,
            seed=42,
            toggles=SimulationToggles(
                enable_extracted_routing=True,
                enable_graph_routing=True,
            ),
        )
        engine.add_facility(Facility(id="POI", name="POI", role=Role.POI, beds=50))
        engine.add_facility(
            Facility(id="R1-ALPHA", name="R1-A", role=Role.R1, beds=4)
        )
        engine.add_facility(
            Facility(id="R1-BRAVO", name="R1-B", role=Role.R1, beds=4)
        )
        engine.add_facility(Facility(id="R2", name="R2", role=Role.R2, beds=8))
        engine.add_route("POI", "R1-ALPHA", time_minutes=30.0, transport="ground")
        engine.add_route("POI", "R1-BRAVO", time_minutes=30.0, transport="ground")
        engine.add_route("R1-ALPHA", "R2", time_minutes=45.0, transport="ground")
        engine.add_route("R1-BRAVO", "R2", time_minutes=45.0, transport="ground")

        metrics = engine.run(duration=2880.0, poi_id="POI", max_patients=50)

        # Count FACILITY_ARRIVAL events at each R1 node
        arrivals = engine.event_store.events_of_type("FACILITY_ARRIVAL")
        r1a_count = sum(
            1 for e in arrivals if e.facility_id == "R1-ALPHA"
        )
        r1b_count = sum(
            1 for e in arrivals if e.facility_id == "R1-BRAVO"
        )

        assert r1b_count > 0, "R1-BRAVO received zero traffic (first-match bias)"
        assert r1a_count > 0, "R1-ALPHA received zero traffic"
