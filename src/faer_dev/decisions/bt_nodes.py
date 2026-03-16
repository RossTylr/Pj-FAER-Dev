"""BT condition and action nodes for FAER-M clinical decisions.

11 nodes total: 1 gate, 7 conditions, 3 actions.
All nodes are standalone — zero SimPy imports.
"""

from __future__ import annotations

import py_trees
from py_trees import common
from py_trees.behaviour import Behaviour


# ═══════════════════════════════════════════════════════════════
# GATE NODE (1)
# ═══════════════════════════════════════════════════════════════


class CheckBranchEnabled(Behaviour):
    """Gate: SUCCESS if bt_enabled_{branch_name} is True on blackboard."""

    def __init__(self, branch_name: str, name: str = ""):
        super().__init__(name or f"Gate_{branch_name}")
        self.branch_name = branch_name
        self._key = f"bt_enabled_{branch_name}"
        self.bb = None

    def setup(self, **kwargs):
        self.bb = py_trees.blackboard.Client(name=self.name)
        self.bb.register_key(key=self._key, access=common.Access.READ)

    def update(self):
        if self.bb.get(self._key):
            return common.Status.SUCCESS
        return common.Status.FAILURE


# ═══════════════════════════════════════════════════════════════
# CONDITION NODES (7)
# ═══════════════════════════════════════════════════════════════


class CheckSeverity(Behaviour):
    """SUCCESS if patient_severity > threshold."""

    def __init__(self, name: str, threshold: float):
        super().__init__(name)
        self.threshold = threshold
        self.bb = None

    def setup(self, **kwargs):
        self.bb = py_trees.blackboard.Client(name=self.name)
        self.bb.register_key(key="patient_severity", access=common.Access.READ)

    def update(self):
        if self.bb.get("patient_severity") > self.threshold:
            return common.Status.SUCCESS
        return common.Status.FAILURE


class CheckRegionIn(Behaviour):
    """SUCCESS if patient_primary_region is in the given set."""

    def __init__(self, name: str, regions: list[str]):
        super().__init__(name)
        self.regions = set(regions)
        self.bb = None

    def setup(self, **kwargs):
        self.bb = py_trees.blackboard.Client(name=self.name)
        self.bb.register_key(
            key="patient_primary_region", access=common.Access.READ
        )

    def update(self):
        if self.bb.get("patient_primary_region") in self.regions:
            return common.Status.SUCCESS
        return common.Status.FAILURE


class CheckSurgicalRegion(Behaviour):
    """SUCCESS if patient_is_surgical is True.

    Reads the flag set by the caller — does NOT hardcode region lists.
    """

    def __init__(self, name: str = "CheckSurgical"):
        super().__init__(name)
        self.bb = None

    def setup(self, **kwargs):
        self.bb = py_trees.blackboard.Client(name=self.name)
        self.bb.register_key(
            key="patient_is_surgical", access=common.Access.READ
        )

    def update(self):
        if self.bb.get("patient_is_surgical"):
            return common.Status.SUCCESS
        return common.Status.FAILURE


class CheckMASCALActive(Behaviour):
    """SUCCESS if mascal_active is True."""

    def __init__(self, name: str = "CheckMASCAL"):
        super().__init__(name)
        self.bb = None

    def setup(self, **kwargs):
        self.bb = py_trees.blackboard.Client(name=self.name)
        self.bb.register_key(key="mascal_active", access=common.Access.READ)

    def update(self):
        if self.bb.get("mascal_active"):
            return common.Status.SUCCESS
        return common.Status.FAILURE


class CheckFacilityUtilisation(Behaviour):
    """SUCCESS if facility_utilisation > threshold."""

    def __init__(self, name: str, threshold: float):
        super().__init__(name)
        self.threshold = threshold
        self.bb = None

    def setup(self, **kwargs):
        self.bb = py_trees.blackboard.Client(name=self.name)
        self.bb.register_key(
            key="facility_utilisation", access=common.Access.READ
        )

    def update(self):
        if self.bb.get("facility_utilisation") > self.threshold:
            return common.Status.SUCCESS
        return common.Status.FAILURE


class CheckPolytrauma(Behaviour):
    """SUCCESS if patient_is_polytrauma is True."""

    def __init__(self, name: str = "CheckPolytrauma"):
        super().__init__(name)
        self.bb = None

    def setup(self, **kwargs):
        self.bb = py_trees.blackboard.Client(name=self.name)
        self.bb.register_key(
            key="patient_is_polytrauma", access=common.Access.READ
        )

    def update(self):
        if self.bb.get("patient_is_polytrauma"):
            return common.Status.SUCCESS
        return common.Status.FAILURE


class CheckGoldenHour(Behaviour):
    """SUCCESS if time_since_injury_minutes > threshold."""

    def __init__(self, name: str, threshold: float = 90.0):
        super().__init__(name)
        self.threshold = threshold
        self.bb = None

    def setup(self, **kwargs):
        self.bb = py_trees.blackboard.Client(name=self.name)
        self.bb.register_key(
            key="time_since_injury_minutes", access=common.Access.READ
        )

    def update(self):
        if self.bb.get("time_since_injury_minutes") > self.threshold:
            return common.Status.SUCCESS
        return common.Status.FAILURE


# ═══════════════════════════════════════════════════════════════
# ACTION NODES (3)
# ═══════════════════════════════════════════════════════════════


class SetTriage(Behaviour):
    """Write decision_triage and append to decision_path."""

    def __init__(self, name: str, triage: str):
        super().__init__(name)
        self.triage = triage
        self.bb = None

    def setup(self, **kwargs):
        self.bb = py_trees.blackboard.Client(name=self.name)
        self.bb.register_key(
            key="decision_triage", access=common.Access.WRITE
        )
        self.bb.register_key(
            key="decision_path", access=common.Access.WRITE
        )

    def update(self):
        self.bb.set("decision_triage", self.triage)
        path = self.bb.get("decision_path")
        path.append(f"SetTriage({self.triage})")
        return common.Status.SUCCESS


class SetDepartment(Behaviour):
    """Write decision_department and append to decision_path."""

    def __init__(self, name: str, department: str):
        super().__init__(name)
        self.department = department
        self.bb = None

    def setup(self, **kwargs):
        self.bb = py_trees.blackboard.Client(name=self.name)
        self.bb.register_key(
            key="decision_department", access=common.Access.WRITE
        )
        self.bb.register_key(
            key="decision_path", access=common.Access.WRITE
        )

    def update(self):
        self.bb.set("decision_department", self.department)
        path = self.bb.get("decision_path")
        path.append(f"SetDepartment({self.department})")
        return common.Status.SUCCESS


class SetDCS(Behaviour):
    """Write decision_dcs=True and append to decision_path."""

    def __init__(self, name: str = "SetDCS"):
        super().__init__(name)
        self.bb = None

    def setup(self, **kwargs):
        self.bb = py_trees.blackboard.Client(name=self.name)
        self.bb.register_key(key="decision_dcs", access=common.Access.WRITE)
        self.bb.register_key(
            key="decision_path", access=common.Access.WRITE
        )

    def update(self):
        self.bb.set("decision_dcs", True)
        path = self.bb.get("decision_path")
        path.append(f"SetDCS({self.name})")
        return common.Status.SUCCESS
