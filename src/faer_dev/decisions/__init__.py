"""Decision logic module for FAER-M.

Provides py-trees based behavior trees for clinical decisions,
a typed blackboard wrapper, and decision mode toggles.

Symbols from mode.py (DecisionMode, SimulationToggles) are imported eagerly
since they have zero third-party dependencies. All py-trees-dependent symbols
(blackboard, bt_nodes, trees, observer) are loaded lazily on first access
via __getattr__ (PEP 562) to avoid pulling in py_trees when only lightweight
types are needed.
"""

from faer_dev.decisions.mode import DecisionMode, SimulationToggles

# Lazy-loaded symbols mapped to their source submodules
_LAZY_IMPORTS: dict[str, str] = {
    # blackboard
    "SimBlackboard": "faer_dev.decisions.blackboard",
    # bt_nodes
    "CheckBranchEnabled": "faer_dev.decisions.bt_nodes",
    "CheckFacilityUtilisation": "faer_dev.decisions.bt_nodes",
    "CheckGoldenHour": "faer_dev.decisions.bt_nodes",
    "CheckMASCALActive": "faer_dev.decisions.bt_nodes",
    "CheckPolytrauma": "faer_dev.decisions.bt_nodes",
    "CheckRegionIn": "faer_dev.decisions.bt_nodes",
    "CheckSeverity": "faer_dev.decisions.bt_nodes",
    "CheckSurgicalRegion": "faer_dev.decisions.bt_nodes",
    "SetDCS": "faer_dev.decisions.bt_nodes",
    "SetDepartment": "faer_dev.decisions.bt_nodes",
    "SetTriage": "faer_dev.decisions.bt_nodes",
    # trees
    "build_dcs_tree": "faer_dev.decisions.trees",
    "build_department_routing_tree": "faer_dev.decisions.trees",
    "build_triage_tree": "faer_dev.decisions.trees",
    "load_thresholds_from_loader": "faer_dev.decisions.trees",
    # observer
    "BTObserver": "faer_dev.decisions.observer",
    "NodeMetrics": "faer_dev.decisions.observer",
    "DecisionRecord": "faer_dev.decisions.observer",
}


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Mode (eagerly loaded)
    "DecisionMode",
    "SimulationToggles",
    # Blackboard
    "SimBlackboard",
    # Nodes
    "CheckBranchEnabled",
    "CheckSeverity",
    "CheckRegionIn",
    "CheckSurgicalRegion",
    "CheckMASCALActive",
    "CheckFacilityUtilisation",
    "CheckPolytrauma",
    "CheckGoldenHour",
    "SetTriage",
    "SetDepartment",
    "SetDCS",
    # Trees
    "build_triage_tree",
    "build_department_routing_tree",
    "build_dcs_tree",
    "load_thresholds_from_loader",
    # Observer
    "BTObserver",
    "NodeMetrics",
    "DecisionRecord",
]
