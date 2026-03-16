"""PFC sync decision logic extracted from engine.py (EX-4 sync portion).

Pure functions for Prolonged Field Care evaluation. No SimPy. No yields.
The engine calls these between yield points to decide what to do next.
The engine owns the actual yield (Y3 retry timeout).

Extracted from:
  - engine.py hold/PFC nested conditionals (~60 LOC decision logic)

Hard Constraints preserved:
  - HC-1: No SimPy imports
  - HC-2: Same inputs → same decision as legacy inline code
  - Y3 (retry timeout) stays in engine.py
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PFCAction(Enum):
    """Decision output from evaluate_hold(). Engine translates to yields/state changes."""

    CONTINUE_HOLD = "CONTINUE_HOLD"      # keep waiting, yield retry timeout
    ESCALATE_TO_PFC = "ESCALATE_TO_PFC"  # transition to PFC status, then keep holding
    RELEASE = "RELEASE"                  # downstream available, stop holding
    HOLD_TIMEOUT = "HOLD_TIMEOUT"        # hold exceeded max, dispose patient


@dataclass(frozen=True)
class HoldEvaluation:
    """Immutable result from evaluate_hold(). Engine reads fields to act."""

    action: PFCAction
    hold_duration: float     # minutes held so far
    should_emit_hold_start: bool = False  # first iteration only
    should_emit_timeout: bool = False


def evaluate_hold(
    hold_duration: float,
    downstream_available: bool,
    is_pfc_active: bool,
    pfc_threshold: float,
    hold_timeout: float,
    is_first_check: bool = False,
) -> HoldEvaluation:
    """Pure hold/PFC decision function. No SimPy. No yields. No side effects.

    Called by engine.py inside the hold retry loop BETWEEN yield points.
    Returns a HoldEvaluation that the engine translates into:
    - RELEASE: break the hold loop
    - HOLD_TIMEOUT: finalize patient with timeout outcome
    - ESCALATE_TO_PFC: set PFC state + emit PFC_START + continue holding
    - CONTINUE_HOLD: yield retry timeout + continue

    Args:
        hold_duration: Time elapsed since hold started (minutes).
        downstream_available: Whether next facility has capacity.
        is_pfc_active: Whether patient already has PFC status.
        pfc_threshold: Minutes before escalating to PFC (typically 60).
        hold_timeout: Maximum hold duration before timeout disposal.
        is_first_check: True on first iteration (emit HOLD_START).

    Returns:
        HoldEvaluation frozen dataclass.
    """
    if downstream_available:
        return HoldEvaluation(
            action=PFCAction.RELEASE,
            hold_duration=hold_duration,
        )

    if hold_duration >= hold_timeout:
        return HoldEvaluation(
            action=PFCAction.HOLD_TIMEOUT,
            hold_duration=hold_duration,
            should_emit_timeout=True,
        )

    if hold_duration >= pfc_threshold and not is_pfc_active:
        return HoldEvaluation(
            action=PFCAction.ESCALATE_TO_PFC,
            hold_duration=hold_duration,
            should_emit_hold_start=is_first_check,
        )

    return HoldEvaluation(
        action=PFCAction.CONTINUE_HOLD,
        hold_duration=hold_duration,
        should_emit_hold_start=is_first_check,
    )


def compute_deterioration(
    current_severity: float,
    hold_duration: float,
    base_rate: float = 0.01,
) -> float:
    """Compute severity deterioration during PFC hold.

    EP-3 extension point: configurable deterioration model.
    Currently linear; can be replaced with exponential/logistic.

    Returns:
        New severity score (clamped to [0.0, 1.0]).
    """
    return min(1.0, current_severity + hold_duration * base_rate)
