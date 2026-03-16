"""Extracted routing module — pure functions for patient routing decisions.

This module extracts routing logic from engine.py into SimPy-independent
pure functions. The engine calls these behind the `enable_extracted_routing`
toggle; when OFF, the legacy inline code runs unchanged.

Extracted from:
  - engine.py::_triage_decisions() (lines 75-102)
  - engine.py::_get_next_destination() (lines 105-142)

Hard Constraints preserved:
  - HC-1: Deterministic (no RNG, no SimPy, no side effects)
  - HC-2: Same input → same output as legacy code
  - HC-5: Pure functions, testable in isolation
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from faer_dev.core.enums import Role, TriageCategory
from faer_dev.core.schemas import Casualty, Facility
from faer_dev.network.topology import TreatmentNetwork

# Role progression order — mirrors engine.py::ROLE_ORDER
ROLE_ORDER = [Role.POI, Role.R1, Role.R2, Role.R3, Role.R4]


def triage_decisions(patient: Casualty) -> Dict[str, Any]:
    """Evaluate triage category and return clinical routing decisions.

    Pure function: no SimPy, no RNG, no side effects.
    Exact replica of engine.py::_triage_decisions().

    Returns:
        Dict with keys: recommended_triage, bypass_role1, requires_dcs, priority
    """
    decisions: Dict[str, Any] = {
        "recommended_triage": patient.triage,
        "bypass_role1": False,
        "requires_dcs": False,
        "priority": 5,
    }

    if patient.triage == TriageCategory.T1_SURGICAL:
        decisions["priority"] = 1
        decisions["bypass_role1"] = True
        decisions["requires_dcs"] = True
    elif patient.triage == TriageCategory.T1_MEDICAL:
        decisions["priority"] = 1
        decisions["bypass_role1"] = True
    elif patient.triage == TriageCategory.T2:
        decisions["priority"] = 2
    elif patient.triage == TriageCategory.T3:
        decisions["priority"] = 3
    elif patient.triage == TriageCategory.T4:
        decisions["priority"] = 5

    return decisions


def get_next_destination(
    patient: Casualty,
    current_facility: Facility,
    network: TreatmentNetwork,
    decisions: Dict[str, Any],
) -> Optional[str]:
    """Determine the next facility in the treatment chain.

    Pure function: no SimPy, no RNG, no side effects.
    Exact replica of engine.py::_get_next_destination().

    Returns:
        Facility ID string, or None when journey is complete.
    """
    current_idx = ROLE_ORDER.index(current_facility.role)

    # T3 can RTD from R1 or R2
    if patient.triage == TriageCategory.T3 and current_facility.role in (
        Role.R1,
        Role.R2,
    ):
        return None

    # T4 stays at current location
    if patient.triage == TriageCategory.T4:
        return None

    # Walk up the chain looking for the next facility
    for next_idx in range(current_idx + 1, len(ROLE_ORDER)):
        next_role = ROLE_ORDER[next_idx]

        # Skip R1 if bypass indicated
        if next_role == Role.R1 and decisions["bypass_role1"]:
            continue

        for fac_id, fac in network.facilities.items():
            if fac.role != next_role:
                continue
            if network.graph.has_edge(current_facility.id, fac_id):
                return fac_id

    return None
