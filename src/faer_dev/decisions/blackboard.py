"""SimBlackboard — typed wrapper around py-trees blackboard.

Provides a consistent API for engine <-> BT communication with
29 registered keys in 6 groups.
"""

from __future__ import annotations

from typing import Any

import py_trees
from py_trees import common


# ── Key definitions with defaults, grouped by purpose ──────────

_PATIENT_KEYS: dict[str, Any] = {
    "patient_severity": 0.5,
    "patient_primary_region": "EXTERNAL",
    "patient_secondary_regions": [],
    "patient_mechanism": "BLUNT",
    "patient_is_polytrauma": False,
    "patient_is_surgical": False,
    "patient_triage": "T3",
    "patient_id": "",
}

_FACILITY_KEYS: dict[str, Any] = {
    "facility_utilisation": 0.0,
    "facility_beds_available": {},
    "department_queue_depth": {},
    "department_capacity": {},
    "fst_queue_depth": 0,
    "r1_beds_available": {},
}

_OPERATIONAL_KEYS: dict[str, Any] = {
    "mascal_active": False,
    "time_since_injury_minutes": 0.0,
    "time_awaiting_surgery_minutes": 0.0,
    "operational_context": "LSCO",
}

_TOGGLE_KEYS: dict[str, Any] = {
    "bt_enabled_t4": True,
    "bt_enabled_t1_surgical": True,
    "bt_enabled_t1_medical": True,
    "bt_enabled_t2": True,
    "bt_enabled_dcs": True,
}

_DECISION_KEYS: dict[str, Any] = {
    "decision_triage": "T3",
    "decision_department": "WARD",
    "decision_dcs": False,
    "decision_path": [],
}

# VOP reserved — pre-registered for Visual Operational Planner
_VOP_KEYS: dict[str, Any] = {
    "available_transport_modes": [],
    "transport_clinical_capability": "NONE",
}

ALL_KEYS: dict[str, Any] = {
    **_PATIENT_KEYS,
    **_FACILITY_KEYS,
    **_OPERATIONAL_KEYS,
    **_TOGGLE_KEYS,
    **_DECISION_KEYS,
    **_VOP_KEYS,
}


def _copy_default(value: Any) -> Any:
    """Deep-enough copy for default values (lists, dicts)."""
    if isinstance(value, (list, dict)):
        return value.copy()
    return value


class SimBlackboard:
    """Typed wrapper around py-trees blackboard for engine <-> BT comms.

    29 keys in 6 groups: patient (8), facility (6), operational (4),
    toggles (5), decisions (4), VOP reserved (2).
    """

    KEYS = ALL_KEYS

    def __init__(self, name: str = "sim"):
        self._client = py_trees.blackboard.Client(name=name)
        for key in ALL_KEYS:
            self._client.register_key(key=key, access=common.Access.WRITE)
        for key, default in ALL_KEYS.items():
            self._client.set(key, _copy_default(default))

    # ── Core accessors ─────────────────────────────────────────

    def get(self, key: str) -> Any:
        """Read a blackboard key."""
        return self._client.get(key)

    def set(self, key: str, value: Any) -> None:
        """Write a blackboard key."""
        self._client.set(key, value)

    # ── Batch setters ──────────────────────────────────────────

    def set_patient_context(
        self,
        severity: float,
        primary_region: str,
        mechanism: str = "BLUNT",
        secondary_regions: list[str] | None = None,
        is_polytrauma: bool = False,
        is_surgical: bool = False,
        patient_id: str = "",
    ) -> None:
        """Set all patient keys in one call before ticking triage BT."""
        self.set("patient_severity", severity)
        self.set("patient_primary_region", primary_region)
        self.set("patient_mechanism", mechanism)
        self.set("patient_secondary_regions", secondary_regions or [])
        self.set("patient_is_polytrauma", is_polytrauma)
        self.set("patient_is_surgical", is_surgical)
        self.set("patient_id", patient_id)

    def reset_patient_context(self) -> None:
        """Reset patient + decision keys to defaults between patients."""
        for key, default in _PATIENT_KEYS.items():
            self.set(key, _copy_default(default))
        for key, default in _DECISION_KEYS.items():
            self.set(key, _copy_default(default))

    # Alias (Issue #5 fix)
    reset_patient = reset_patient_context

    def set_toggle(self, branch_name: str, enabled: bool) -> None:
        """Enable/disable a BT branch by name (t4, t1_surgical, etc.)."""
        key = f"bt_enabled_{branch_name}"
        if key not in ALL_KEYS:
            raise KeyError(f"Unknown toggle: {key}")
        self.set(key, enabled)

    def get_toggle(self, branch_name: str) -> bool:
        """Check if a BT branch is enabled."""
        key = f"bt_enabled_{branch_name}"
        return self.get(key)

    def set_facility_context(
        self,
        utilisation: float = 0.0,
        fst_queue: int = 0,
        mascal_active: bool = False,
    ) -> None:
        """Set facility-level context before ticking DCS/dept BT."""
        self.set("facility_utilisation", utilisation)
        self.set("fst_queue_depth", fst_queue)
        self.set("mascal_active", mascal_active)

    # ── Convenience properties (Issue #6 fix) ──────────────────

    @property
    def decision_triage(self) -> str:
        return self.get("decision_triage")

    @property
    def decision_department(self) -> str:
        return self.get("decision_department")

    @property
    def decision_dcs(self) -> bool:
        return self.get("decision_dcs")

    @property
    def decision_path(self) -> list[str]:
        return self.get("decision_path")

    # ── Snapshot ───────────────────────────────────────────────

    def snapshot(self) -> dict:
        """Return all 29 keys as a flat dict (for observer/logging)."""
        return {k: self.get(k) for k in ALL_KEYS}

    @property
    def key_count(self) -> int:
        return len(ALL_KEYS)
