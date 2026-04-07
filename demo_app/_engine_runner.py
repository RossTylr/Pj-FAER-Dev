"""Shared engine runner for demo app pages.

Builds and runs the FAER engine, wires analytics, and stores results
in st.session_state. Used by both the Simulation page and Engine Room.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st

from faer_dev.config.builder import build_engine_from_dict, build_engine_from_preset, get_preset_raw
from faer_dev.decisions.mode import SimulationToggles
from faer_dev.analytics.engine import AnalyticsEngine
from faer_dev.analytics.views import GoldenHourView, FacilityLoadView, OutcomeView

PHASE1_TOGGLES = SimulationToggles(
    enable_extracted_routing=True,
    enable_extracted_metrics=True,
    enable_typed_emitter=True,
    # enable_extracted_pfc intentionally left at default (False).
    # pfc.py is extracted and tested but not wired into engine.py.
    # Wiring deferred to Phase 3 hold loop delegation (EX-6).
    # See: docs/phase3/PFC_HOLD_DELEGATION.md
)


def run_engine(
    scenario_dict: Dict[str, Any],
    seed: int = 42,
    duration: float = 480.0,
    toggles: Optional[SimulationToggles] = None,
) -> Dict[str, Any]:
    """Run the FAER engine and store results in session_state.

    Returns the metrics dict. Also populates:
        st.session_state["engine_metrics"]
        st.session_state["analytics"]
        st.session_state["events"]
        st.session_state["scenario_dict"]
    """
    _toggles = toggles or PHASE1_TOGGLES

    engine = build_engine_from_dict(scenario_dict, toggles=_toggles, seed=seed)

    analytics = AnalyticsEngine(engine.event_bus)
    analytics.register_view("outcomes", OutcomeView())
    analytics.register_view("facility_load", FacilityLoadView())
    analytics.register_view("golden_hour", GoldenHourView())

    metrics = engine.run(duration=duration, max_patients=None)

    st.session_state["engine_metrics"] = metrics
    st.session_state["analytics"] = analytics
    st.session_state["events"] = engine.events
    st.session_state["scenario_dict"] = scenario_dict

    return metrics


# --- Engine Room (Phase 2) ---------------------------------------------------

ENGINE_ROOM_TOGGLES = SimulationToggles(
    enable_extracted_routing=True,
    enable_extracted_metrics=True,
    enable_typed_emitter=True,
    # PFC wiring deferred to Phase 3 (EX-6 hold loop delegation)
    enable_extracted_pfc=False,
    enable_graph_routing=True,
)


def run_engine_preset(
    preset_name: str,
    duration: float,
    toggles: Optional[SimulationToggles] = None,
) -> Dict[str, Any]:
    """Run the FAER engine from a named preset and store results.

    Uses build_engine_from_preset (loads real YAML topology) instead of
    hardcoded scenario dicts. Stores the raw YAML dict as scenario_dict
    so panels can read facility coordinates, edges, and threat levels.

    Returns the metrics dict. Also populates:
        st.session_state["engine_metrics"]
        st.session_state["analytics"]
        st.session_state["events"]
        st.session_state["scenario_dict"]
    """
    _toggles = toggles or ENGINE_ROOM_TOGGLES

    engine = build_engine_from_preset(preset_name, toggles=_toggles)

    analytics = AnalyticsEngine(engine.event_bus)
    analytics.register_view("outcomes", OutcomeView())
    analytics.register_view("facility_load", FacilityLoadView())
    analytics.register_view("golden_hour", GoldenHourView())

    metrics = engine.run(duration=duration, max_patients=None)

    st.session_state["engine_metrics"] = metrics
    st.session_state["analytics"] = analytics
    st.session_state["events"] = engine.events
    st.session_state["scenario_dict"] = get_preset_raw(preset_name)

    return metrics
