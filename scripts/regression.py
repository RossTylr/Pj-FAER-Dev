"""Regression test helpers for toggle-gated extraction validation.

Usage in notebooks and tests:
    from scripts.regression import compare_engines, assert_identical

These functions implement the MC-3/MC-4 validation pattern:
run old path vs new path on the same seed, assert identical output.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from typing import List, Any


@dataclass
class RegressionResult:
    """Result of comparing two engine runs."""
    events_match: bool
    outcomes_match: bool
    triage_match: bool
    disposition_invariant: bool
    event_count_old: int
    event_count_new: int
    mismatched_events: List[int]
    summary: str


def compare_events(events_old: list, events_new: list, tolerance: float = 0.001) -> tuple:
    """Compare two event lists element-by-element.

    Returns:
        (all_match: bool, mismatched_indices: list)
    """
    if len(events_old) != len(events_new):
        return False, [-1]

    mismatched = []
    for i, (old, new) in enumerate(zip(events_old, events_new)):
        if old.event_type != new.event_type:
            mismatched.append(i)
        elif old.casualty_id != new.casualty_id:
            mismatched.append(i)
        elif abs(old.sim_time - new.sim_time) > tolerance:
            mismatched.append(i)

    return len(mismatched) == 0, mismatched


def compare_outcomes(casualties_old: list, casualties_new: list, tolerance: float = 0.001) -> bool:
    """Compare per-casualty outcomes between two engine runs."""
    if len(casualties_old) != len(casualties_new):
        return False

    for old, new in zip(casualties_old, casualties_new):
        if old.triage != new.triage:
            return False
        if abs(old.outcome_time - new.outcome_time) > tolerance:
            return False
        if abs(old.total_wait_time - new.total_wait_time) > tolerance:
            return False
        if abs(old.total_transit_time - new.total_transit_time) > tolerance:
            return False
        if abs(old.total_treatment_time - new.total_treatment_time) > tolerance:
            return False

    return True


def check_disposition_invariant(events: list) -> bool:
    """KL-6: DISPOSITION count must equal ARRIVAL count."""
    arrival_types = {"ARRIVAL", "CREATED"}
    disposition_types = {"DISCHARGED", "DIED", "DISPOSITION"}

    arrivals = sum(1 for e in events if e.event_type in arrival_types)
    dispositions = sum(1 for e in events if e.event_type in disposition_types)

    return arrivals == dispositions


def check_distribution(casualties: list, expected: dict, tolerance: float = 0.05) -> bool:
    """MC-3: Triage distribution within ±5% of expected proportions."""
    triage_values = [c.triage.value if hasattr(c.triage, 'value') else str(c.triage)
                     for c in casualties]
    dist = Counter(triage_values)
    total = sum(dist.values())

    if total == 0:
        return False

    for cat, expected_prop in expected.items():
        actual_prop = dist.get(cat, 0) / total
        if abs(actual_prop - expected_prop) > tolerance:
            return False

    return True


def compare_engines(engine_old, engine_new) -> RegressionResult:
    """Full regression comparison of two engine runs.

    Call after running both engines with the same seed.

    Returns:
        RegressionResult with pass/fail for each criterion.
    """
    events_match, mismatched = compare_events(engine_old.log.events, engine_new.log.events)
    outcomes_match = compare_outcomes(engine_old.casualties, engine_new.casualties)
    triage_old = Counter(c.triage for c in engine_old.casualties)
    triage_new = Counter(c.triage for c in engine_new.casualties)
    triage_match = triage_old == triage_new
    disposition_ok = check_disposition_invariant(engine_new.log.events)

    parts = []
    if events_match:
        parts.append(f"Events: PASS ({len(engine_new.log.events)} identical)")
    else:
        parts.append(f"Events: FAIL ({len(mismatched)} mismatches)")
    if outcomes_match:
        parts.append(f"Outcomes: PASS ({len(engine_new.casualties)} identical)")
    else:
        parts.append("Outcomes: FAIL")
    if triage_match:
        parts.append("Triage: PASS")
    else:
        parts.append(f"Triage: FAIL (old={dict(triage_old)}, new={dict(triage_new)})")
    if disposition_ok:
        parts.append("DISPOSITION invariant: PASS")
    else:
        parts.append("DISPOSITION invariant: FAIL")

    return RegressionResult(
        events_match=events_match,
        outcomes_match=outcomes_match,
        triage_match=triage_match,
        disposition_invariant=disposition_ok,
        event_count_old=len(engine_old.log.events),
        event_count_new=len(engine_new.log.events),
        mismatched_events=mismatched,
        summary=" | ".join(parts),
    )


def assert_identical(engine_old, engine_new, context: str = "") -> None:
    """Assert two engine runs are identical. Raises AssertionError with details on failure."""
    result = compare_engines(engine_old, engine_new)
    prefix = f"[{context}] " if context else ""

    assert result.events_match, \
        f"{prefix}Event mismatch: {len(result.mismatched_events)} events differ"
    assert result.outcomes_match, \
        f"{prefix}Outcome mismatch"
    assert result.triage_match, \
        f"{prefix}Triage distribution mismatch"
    assert result.disposition_invariant, \
        f"{prefix}DISPOSITION invariant violated (KL-6)"

    print(f"{prefix}REGRESSION: ALL PASS ✓ ({result.event_count_new} events, "
          f"{len(engine_new.casualties)} casualties)")
