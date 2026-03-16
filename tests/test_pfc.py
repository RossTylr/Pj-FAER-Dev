"""Tests for pfc.py (EX-4 sync extraction).

Validates evaluate_hold() as a pure decision function testable without SimPy.
Yield Point 3 stays in engine.py — only the DECISION is extracted.
"""

from __future__ import annotations

import importlib

import pytest

from faer_dev.pfc import (
    HoldEvaluation,
    PFCAction,
    compute_deterioration,
    evaluate_hold,
)


# ===========================================================================
# Purity Tests
# ===========================================================================

class TestPFCPurity:
    """Verify pfc.py has no SimPy contamination."""

    def test_no_simpy_import(self):
        source = importlib.util.find_spec("faer_dev.pfc")
        assert source is not None and source.origin is not None
        with open(source.origin) as f:
            content = f.read()
        assert "import simpy" not in content
        assert "from simpy" not in content

    def test_hold_evaluation_is_frozen(self):
        result = evaluate_hold(10.0, False, False, 60.0, 240.0)
        with pytest.raises(AttributeError):
            result.action = PFCAction.RELEASE  # type: ignore[misc]


# ===========================================================================
# evaluate_hold() Unit Tests
# ===========================================================================

class TestEvaluateHold:
    """Pure decision function tests — no SimPy, no engine, plain asserts."""

    def test_release_when_downstream_available(self):
        """Downstream available → RELEASE regardless of hold duration."""
        result = evaluate_hold(
            hold_duration=120.0, downstream_available=True,
            is_pfc_active=False, pfc_threshold=60.0, hold_timeout=240.0,
        )
        assert result.action == PFCAction.RELEASE

    def test_continue_hold_below_threshold(self):
        """Below PFC threshold, downstream unavailable → CONTINUE_HOLD."""
        result = evaluate_hold(
            hold_duration=30.0, downstream_available=False,
            is_pfc_active=False, pfc_threshold=60.0, hold_timeout=240.0,
        )
        assert result.action == PFCAction.CONTINUE_HOLD

    def test_escalate_above_threshold(self):
        """Above PFC threshold, not yet PFC → ESCALATE_TO_PFC."""
        result = evaluate_hold(
            hold_duration=65.0, downstream_available=False,
            is_pfc_active=False, pfc_threshold=60.0, hold_timeout=240.0,
        )
        assert result.action == PFCAction.ESCALATE_TO_PFC

    def test_continue_hold_when_already_pfc(self):
        """Already PFC, below timeout → CONTINUE_HOLD (no re-escalation)."""
        result = evaluate_hold(
            hold_duration=100.0, downstream_available=False,
            is_pfc_active=True, pfc_threshold=60.0, hold_timeout=240.0,
        )
        assert result.action == PFCAction.CONTINUE_HOLD

    def test_hold_timeout(self):
        """Exceeded hold timeout → HOLD_TIMEOUT."""
        result = evaluate_hold(
            hold_duration=250.0, downstream_available=False,
            is_pfc_active=True, pfc_threshold=60.0, hold_timeout=240.0,
        )
        assert result.action == PFCAction.HOLD_TIMEOUT
        assert result.should_emit_timeout is True

    def test_timeout_takes_priority_over_escalation(self):
        """Timeout fires even if not yet PFC (edge case: threshold > timeout)."""
        result = evaluate_hold(
            hold_duration=250.0, downstream_available=False,
            is_pfc_active=False, pfc_threshold=60.0, hold_timeout=240.0,
        )
        assert result.action == PFCAction.HOLD_TIMEOUT

    def test_first_check_emits_hold_start(self):
        """First iteration should flag hold_start emission."""
        result = evaluate_hold(
            hold_duration=0.0, downstream_available=False,
            is_pfc_active=False, pfc_threshold=60.0, hold_timeout=240.0,
            is_first_check=True,
        )
        assert result.action == PFCAction.CONTINUE_HOLD
        assert result.should_emit_hold_start is True

    def test_release_at_zero_duration(self):
        """Downstream available immediately → RELEASE."""
        result = evaluate_hold(
            hold_duration=0.0, downstream_available=True,
            is_pfc_active=False, pfc_threshold=60.0, hold_timeout=240.0,
        )
        assert result.action == PFCAction.RELEASE


# ===========================================================================
# Deterioration Model Tests
# ===========================================================================

class TestDeteriorationModel:
    """EP-3 extension point: configurable deterioration."""

    def test_linear_deterioration(self):
        new_sev = compute_deterioration(0.5, hold_duration=60.0, base_rate=0.005)
        assert abs(new_sev - 0.8) < 0.001

    def test_severity_clamped_to_unit_interval(self):
        new_sev = compute_deterioration(0.9, hold_duration=200.0, base_rate=0.01)
        assert new_sev == 1.0

    def test_zero_duration_no_change(self):
        new_sev = compute_deterioration(0.3, hold_duration=0.0, base_rate=0.01)
        assert new_sev == 0.3
