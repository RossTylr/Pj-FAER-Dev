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
from faer_dev.routing import get_next_destination, triage_decisions
from faer_dev.simulation.engine import (
    PolyhybridEngine,
    _get_next_destination,
    _triage_decisions,
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
    """Test extracted triage_decisions() matches legacy _triage_decisions()."""

    @pytest.mark.parametrize("triage", list(TriageCategory))
    def test_matches_legacy(self, triage):
        patient = _make_patient(triage)
        legacy = _triage_decisions(patient)
        extracted = triage_decisions(patient)
        assert legacy == extracted, f"Mismatch for {triage.name}"

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
