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

import networkx as nx

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


def _meets_capability(patient: Casualty, facility: Facility) -> bool:
    """True when the facility can deliver the care the casualty needs.

    S1 wires surgery only: a casualty flagged ``requires_dcs`` may only be
    routed to a facility with ``has_surgery``. Applied as candidate-set
    exclusion, never weighting — weights silently dominate soft flags
    (the R1-ALPHA lesson). Extensible to further capability pairs.
    """
    return facility.has_surgery or not patient.requires_dcs


def _find_highest_reachable(
    current_facility: Facility,
    network: TreatmentNetwork,
    decisions: Dict[str, Any],
    patient: Optional[Casualty] = None,
    *,
    use_capability_routing: bool = False,
) -> Optional[str]:
    """Find the highest-role facility reachable from current position.

    Walks ROLE_ORDER from highest to lowest, returns the first facility
    reachable via nx.has_path(). For bypass patients, R1 nodes are
    excluded from the reachability graph. With capability routing,
    non-capable facilities are excluded from the candidate set before
    Dijkstra ever runs. O(roles × facilities).
    """
    current_idx = ROLE_ORDER.index(current_facility.role)
    # For bypass patients, exclude R1 nodes from reachability check
    if decisions["bypass_role1"]:
        current_id = current_facility.id
        r1_ids = {fid for fid, f in network.facilities.items()
                  if f.role == Role.R1 and fid != current_id}
        graph = nx.subgraph_view(
            network.graph,
            filter_node=lambda n: n not in r1_ids,
        )
    else:
        graph = network.graph

    for target_idx in range(len(ROLE_ORDER) - 1, current_idx, -1):
        target_role = ROLE_ORDER[target_idx]
        if target_role == Role.R1 and decisions["bypass_role1"]:
            continue
        for fac_id, fac in network.facilities.items():
            if fac.role != target_role:
                continue
            if use_capability_routing and not _meets_capability(patient, fac):
                continue
            if nx.has_path(graph, current_facility.id, fac_id):
                return fac_id
    return None


def get_next_destination(
    patient: Casualty,
    current_facility: Facility,
    network: TreatmentNetwork,
    decisions: Dict[str, Any],
    *,
    use_graph_routing: bool = False,
    use_capability_routing: bool = False,
) -> Optional[str]:
    """Determine the next facility in the treatment chain.

    Pure function: no SimPy, no RNG, no side effects.

    When use_graph_routing=False (default): legacy role-walk first-match.
    When use_graph_routing=True: Dijkstra via network.get_route().
    When use_capability_routing=True: non-capable facilities (S1: lacking
    has_surgery for a requires_dcs casualty) are excluded from the
    candidate set on both modes.

    Returns:
        Facility ID string, or None when journey is complete.
    """
    # Clinical short-circuits (unchanged regardless of routing mode)
    if patient.triage == TriageCategory.T3 and current_facility.role in (
        Role.R1,
        Role.R2,
    ):
        return None
    if patient.triage == TriageCategory.T4:
        return None

    if use_graph_routing:
        target = _find_highest_reachable(
            current_facility, network, decisions, patient,
            use_capability_routing=use_capability_routing,
        )
        if target is None:
            return None
        path = network.get_route(patient, current_facility.id, target)
        if len(path) < 2:
            return None
        return path[1]

    # Legacy role-walk (first-match)
    current_idx = ROLE_ORDER.index(current_facility.role)
    for next_idx in range(current_idx + 1, len(ROLE_ORDER)):
        next_role = ROLE_ORDER[next_idx]
        if next_role == Role.R1 and decisions["bypass_role1"]:
            continue
        for fac_id, fac in network.facilities.items():
            if fac.role != next_role:
                continue
            if use_capability_routing and not _meets_capability(patient, fac):
                continue
            if network.graph.has_edge(current_facility.id, fac_id):
                return fac_id
    return None
