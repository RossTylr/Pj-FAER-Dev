"""BT tree builders for FAER-M clinical decisions.

Three trees:
- build_triage_tree: Disjunctive T4 with 3 OR paths
- build_department_routing_tree: FST / ITU / WARD routing
- build_dcs_tree: Damage Control Surgery triggers

Each tree is standalone (no SimPy imports) and parameterised by
threshold dicts loaded from InjuryDataLoader.

Current routing: one edge per facility pair.
Future (VOP): multiple edges, BT selects by acuity + clinical
capability + availability.
"""

from __future__ import annotations

from typing import Any

import py_trees
from py_trees import composites

from faer_dev.decisions.bt_nodes import (
    CheckBranchEnabled,
    CheckFacilityUtilisation,
    CheckGoldenHour,
    CheckMASCALActive,
    CheckPolytrauma,
    CheckRegionIn,
    CheckSeverity,
    CheckSurgicalRegion,
    SetDCS,
    SetDepartment,
    SetTriage,
)


# ── Default thresholds (matches injury_reference.yaml) ─────────

_DEFAULT_TRIAGE_THRESHOLDS: dict[str, Any] = {
    "t4_path_a_severity": 0.90,
    "t4_path_a_regions": ["HEAD", "SPINE"],
    "t4_path_b_severity": 0.96,
    "t4_path_c_severity": 0.86,
    "t4_path_c_regions": ["HEAD"],
    "t1_surgical_severity": 0.65,
    "t1_medical_severity": 0.70,
    "t2_severity": 0.35,
}

_DEFAULT_DCS_THRESHOLDS: dict[str, Any] = {
    "dcs_mascal_utilisation": 0.80,
    "dcs_golden_hour_minutes": 90.0,
    "dcs_critical_utilisation": 0.95,
}

_DEFAULT_DEPT_THRESHOLDS: dict[str, Any] = {
    "dept_fst_severity": 0.50,
    "dept_itu_severity": 0.75,
    "dept_fst_capacity": 0.90,
}


# ═══════════════════════════════════════════════════════════════
# TRIAGE TREE — disjunctive T4 (Issue spec: 3 OR paths)
# ═══════════════════════════════════════════════════════════════


def build_triage_tree(
    thresholds: dict[str, Any] | None = None,
) -> py_trees.trees.BehaviourTree:
    """Build triage BT with disjunctive T4.

    Tree structure::

        Triage (Selector, memory=False)
        +-- T4_Expectant (Selector — OR of 3 paths)
        |   +-- PathA: Gate -> Sev>0.90 -> Region[HEAD,SPINE] -> SetT4
        |   +-- PathB: Gate -> Sev>0.96 -> MASCAL -> SetT4
        |   +-- PathC: Gate -> Sev>0.86 -> Region[HEAD] -> MASCAL -> SetT4
        +-- T1_Surgical: Gate -> Sev>0.65 -> Surgical -> SetT1S
        +-- T1_Medical: Gate -> Sev>0.70 -> SetT1M
        +-- T2_Urgent: Gate -> Sev>0.35 -> SetT2
        +-- T3_Delayed: SetT3 (fallthrough)
    """
    t = {**_DEFAULT_TRIAGE_THRESHOLDS, **(thresholds or {})}

    root = composites.Selector("Triage", memory=False)

    # T4 — disjunctive (Selector = OR)
    t4 = composites.Selector("T4_Expectant", memory=False)

    t4_a = composites.Sequence("T4_PathA", memory=True)
    t4_a.add_children([
        CheckBranchEnabled("t4", "T4A_Gate"),
        CheckSeverity("T4A_Sev", t["t4_path_a_severity"]),
        CheckRegionIn("T4A_Region", t["t4_path_a_regions"]),
        SetTriage("Set_T4_A", "T4"),
    ])

    t4_b = composites.Sequence("T4_PathB", memory=True)
    t4_b.add_children([
        CheckBranchEnabled("t4", "T4B_Gate"),
        CheckSeverity("T4B_Sev", t["t4_path_b_severity"]),
        CheckMASCALActive("T4B_MASCAL"),
        SetTriage("Set_T4_B", "T4"),
    ])

    t4_c = composites.Sequence("T4_PathC", memory=True)
    t4_c.add_children([
        CheckBranchEnabled("t4", "T4C_Gate"),
        CheckSeverity("T4C_Sev", t["t4_path_c_severity"]),
        CheckRegionIn("T4C_Region", t["t4_path_c_regions"]),
        CheckMASCALActive("T4C_MASCAL"),
        SetTriage("Set_T4_C", "T4"),
    ])

    t4.add_children([t4_a, t4_b, t4_c])

    # T1_SURGICAL
    t1s = composites.Sequence("T1_Surgical", memory=True)
    t1s.add_children([
        CheckBranchEnabled("t1_surgical", "T1S_Gate"),
        CheckSeverity("T1S_Sev", t["t1_surgical_severity"]),
        CheckSurgicalRegion("T1S_Surgical"),
        SetTriage("Set_T1S", "T1_SURGICAL"),
    ])

    # T1_MEDICAL
    t1m = composites.Sequence("T1_Medical", memory=True)
    t1m.add_children([
        CheckBranchEnabled("t1_medical", "T1M_Gate"),
        CheckSeverity("T1M_Sev", t["t1_medical_severity"]),
        SetTriage("Set_T1M", "T1_MEDICAL"),
    ])

    # T2
    t2 = composites.Sequence("T2_Urgent", memory=True)
    t2.add_children([
        CheckBranchEnabled("t2", "T2_Gate"),
        CheckSeverity("T2_Sev", t["t2_severity"]),
        SetTriage("Set_T2", "T2"),
    ])

    # T3 — fallthrough
    t3 = SetTriage("Set_T3", "T3")

    root.add_children([t4, t1s, t1m, t2, t3])

    tree = py_trees.trees.BehaviourTree(root=root)
    tree.setup()
    return tree


# ═══════════════════════════════════════════════════════════════
# DEPARTMENT ROUTING TREE
# ═══════════════════════════════════════════════════════════════


def build_department_routing_tree(
    thresholds: dict[str, Any] | None = None,
) -> py_trees.trees.BehaviourTree:
    """Build department routing BT (R2 post-ED).

    Tree structure::

        DeptRouting (Selector, memory=False)
        +-- FST_Route (Sequence):
        |   +-- CheckSurgical
        |   +-- Sev>0.5
        |   +-- FST_Capacity (Selector):
        |       +-- FST_Full (Sequence): Util>0.9 -> SetWARD
        |       +-- SetFST
        +-- ITU_Route: Sev>0.75 -> SetITU
        +-- WARD_Default: SetWARD (fallthrough)

    When FST utilisation exceeds threshold (default 0.9),
    surgical patients are routed to WARD instead (Issue #1).
    """
    t = {**_DEFAULT_DEPT_THRESHOLDS, **(thresholds or {})}

    root = composites.Selector("DeptRouting", memory=False)

    # FST route with capacity-awareness
    fst_full = composites.Sequence("FST_Full", memory=True)
    fst_full.add_children([
        CheckFacilityUtilisation("FST_Util", t["dept_fst_capacity"]),
        SetDepartment("Set_WARD_Overflow", "WARD"),
    ])

    fst_capacity = composites.Selector("FST_Capacity", memory=False)
    fst_capacity.add_children([fst_full, SetDepartment("Set_FST", "FST")])

    fst = composites.Sequence("FST_Route", memory=True)
    fst.add_children([
        CheckSurgicalRegion("FST_Surgical"),
        CheckSeverity("FST_Sev", t["dept_fst_severity"]),
        fst_capacity,
    ])

    itu = composites.Sequence("ITU_Route", memory=True)
    itu.add_children([
        CheckSeverity("ITU_Sev", t["dept_itu_severity"]),
        SetDepartment("Set_ITU", "ITU"),
    ])

    ward = SetDepartment("Set_WARD", "WARD")

    root.add_children([fst, itu, ward])

    tree = py_trees.trees.BehaviourTree(root=root)
    tree.setup()
    return tree


# ═══════════════════════════════════════════════════════════════
# DCS TREE — Damage Control Surgery triggers
# ═══════════════════════════════════════════════════════════════


def build_dcs_tree(
    thresholds: dict[str, Any] | None = None,
) -> py_trees.trees.BehaviourTree:
    """Build DCS decision BT.

    DCS decision records include facility_id alongside trigger reason
    (VOP pins DCS events to map markers).

    Tree structure::

        DCS (Selector, memory=False)
        +-- MASCAL_Overload: Gate -> MASCAL -> Util>0.8 -> SetDCS
        +-- Golden_Hour: Gate -> GH>90min -> Polytrauma -> SetDCS
        +-- Critical_Saturation: Gate -> Util>0.95 -> SetDCS
        (no fallthrough — decision_dcs stays False from reset)
    """
    t = {**_DEFAULT_DCS_THRESHOLDS, **(thresholds or {})}

    root = composites.Selector("DCS", memory=False)

    mascal = composites.Sequence("MASCAL_Overload", memory=True)
    mascal.add_children([
        CheckBranchEnabled("dcs", "DCS_Gate_MASCAL"),
        CheckMASCALActive("DCS_MASCAL"),
        CheckFacilityUtilisation(
            "DCS_Util80", t["dcs_mascal_utilisation"]
        ),
        SetDCS("DCS_MASCAL_Trigger"),
    ])

    golden = composites.Sequence("Golden_Hour", memory=True)
    golden.add_children([
        CheckBranchEnabled("dcs", "DCS_Gate_GH"),
        CheckGoldenHour("DCS_GH", t["dcs_golden_hour_minutes"]),
        CheckPolytrauma("DCS_Poly"),
        SetDCS("DCS_GoldenHour_Trigger"),
    ])

    critical = composites.Sequence("Critical_Saturation", memory=True)
    critical.add_children([
        CheckBranchEnabled("dcs", "DCS_Gate_Crit"),
        CheckFacilityUtilisation(
            "DCS_Util95", t["dcs_critical_utilisation"]
        ),
        SetDCS("DCS_Critical_Trigger"),
    ])

    root.add_children([mascal, golden, critical])

    tree = py_trees.trees.BehaviourTree(root=root)
    tree.setup()
    return tree


# ═══════════════════════════════════════════════════════════════
# LOADER HELPER
# ═══════════════════════════════════════════════════════════════


def load_thresholds_from_loader(loader) -> dict[str, Any]:
    """Extract threshold dict from InjuryDataLoader for tree builders.

    Returns a flat dict consumable by build_triage_tree(),
    build_dcs_tree(), and build_department_routing_tree().
    """
    raw = loader.get_triage_thresholds()
    result: dict[str, Any] = {}

    # Triage thresholds
    t4 = raw.get("t4", {})
    paths = t4.get("paths", {})
    pa = paths.get("path_a", {})
    pb = paths.get("path_b", {})
    pc = paths.get("path_c", {})

    result["t4_path_a_severity"] = pa.get(
        "severity_min", _DEFAULT_TRIAGE_THRESHOLDS["t4_path_a_severity"]
    )
    result["t4_path_a_regions"] = (
        ["HEAD", "SPINE"] if pa.get("requires_head") else
        _DEFAULT_TRIAGE_THRESHOLDS["t4_path_a_regions"]
    )
    result["t4_path_b_severity"] = pb.get(
        "severity_min", _DEFAULT_TRIAGE_THRESHOLDS["t4_path_b_severity"]
    )
    result["t4_path_c_severity"] = pc.get(
        "severity_min", _DEFAULT_TRIAGE_THRESHOLDS["t4_path_c_severity"]
    )
    result["t4_path_c_regions"] = (
        ["HEAD"] if pc.get("requires_head") else
        _DEFAULT_TRIAGE_THRESHOLDS["t4_path_c_regions"]
    )

    t1s = raw.get("t1_surgical", {})
    result["t1_surgical_severity"] = t1s.get(
        "severity_min", _DEFAULT_TRIAGE_THRESHOLDS["t1_surgical_severity"]
    )

    t1m = raw.get("t1_medical", {})
    result["t1_medical_severity"] = t1m.get(
        "severity_min", _DEFAULT_TRIAGE_THRESHOLDS["t1_medical_severity"]
    )

    t2_raw = raw.get("t2", {})
    result["t2_severity"] = t2_raw.get(
        "severity_min", _DEFAULT_TRIAGE_THRESHOLDS["t2_severity"]
    )

    # DCS thresholds (defaults if not in YAML)
    dcs = raw.get("dcs", {})
    result["dcs_mascal_utilisation"] = dcs.get(
        "mascal_utilisation", _DEFAULT_DCS_THRESHOLDS["dcs_mascal_utilisation"]
    )
    result["dcs_golden_hour_minutes"] = dcs.get(
        "golden_hour_minutes", _DEFAULT_DCS_THRESHOLDS["dcs_golden_hour_minutes"]
    )
    result["dcs_critical_utilisation"] = dcs.get(
        "critical_utilisation", _DEFAULT_DCS_THRESHOLDS["dcs_critical_utilisation"]
    )

    # Department thresholds (defaults if not in YAML)
    dept = raw.get("department", {})
    result["dept_fst_severity"] = dept.get(
        "fst_severity", _DEFAULT_DEPT_THRESHOLDS["dept_fst_severity"]
    )
    result["dept_itu_severity"] = dept.get(
        "itu_severity", _DEFAULT_DEPT_THRESHOLDS["dept_itu_severity"]
    )

    return result
