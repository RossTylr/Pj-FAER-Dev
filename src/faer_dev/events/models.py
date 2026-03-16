"""Typed event models for FAER-M simulation.

Immutable dataclasses for all engine-known event types.
Convention: UPPER_SNAKE_CASE event_type strings matching engine.KNOWN_EVENT_TYPES.
Dict keys in legacy path: "time", "type", "patient_id", "triage", "state", "facility", "details".
"""

from __future__ import annotations

import dataclasses
import uuid
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SimEvent:
    """Base class for all simulation events. Immutable.

    Fields match PRD v7.0 section 7.2 EventEnvelope contract:
    - event_id: UUID for unique identification
    - sim_time: SimPy env.now
    - event_type: string matching engine KNOWN_EVENT_TYPES convention
    - casualty_id: correlation ID for patient journey queries
    - facility_id: facility where event occurred
    - source: emitting module ("engine", "bt_observer", "mascal_detector")
    - wall_time: real clock time (for run timing analysis)
    - metadata: overflow dict for fields not on typed subclass
    """

    sim_time: float
    event_type: str
    casualty_id: Optional[str] = None
    facility_id: Optional[str] = None
    triage: str = ""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""
    wall_time: datetime = field(default_factory=lambda: datetime.now(tz=__import__("datetime").timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Patient lifecycle
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CasualtyCreated(SimEvent):
    """A new casualty has arrived at the point of injury."""

    triage: str = ""
    injury_mechanism: str = ""
    severity: float = 0.0
    recommended_triage: str = ""
    bypass_role1: bool = False
    requires_dcs: bool = False
    priority: int = 0


@dataclass(frozen=True)
class TriageAssigned(SimEvent):
    """Triage category assigned or changed."""

    old_triage: str = ""
    new_triage: str = ""
    reason: str = ""  # "bt_initial", "deterioration_retriage"


@dataclass(frozen=True)
class OutcomeRecorded(SimEvent):
    """Patient journey complete — final disposition."""

    outcome: str = ""
    total_time: float = 0.0
    reason: str = ""


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TransitStarted(SimEvent):
    """Patient begins transport between facilities."""

    origin: str = ""
    destination: str = ""
    transport_mode: str = ""


@dataclass(frozen=True)
class TransitCompleted(SimEvent):
    """Patient transport complete."""

    transit_time: float = 0.0
    reason: str = ""


# ---------------------------------------------------------------------------
# Facility
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FacilityArrival(SimEvent):
    """Patient arrives at a facility."""

    pass


@dataclass(frozen=True)
class TreatmentStarted(SimEvent):
    """Patient begins treatment at a facility."""

    resource_type: str = ""
    wait_time: float = 0.0
    department: str = ""


@dataclass(frozen=True)
class TreatmentCompleted(SimEvent):
    """Patient treatment complete."""

    duration: float = 0.0
    department: str = ""


@dataclass(frozen=True)
class DepartmentAssigned(SimEvent):
    """Patient assigned to a department within a facility.

    Used for all *_DEPT event types: R1_DEPT, R2_DEPT, R3_DEPT, R4_DEPT, POI_DEPT.
    Resolved via _DYNAMIC_PATTERNS suffix matching.
    """

    department: str = ""
    bt_path: str = ""


@dataclass(frozen=True)
class QueueEntered(SimEvent):
    """Patient enters a facility queue."""

    queue_position: int = 0


# ---------------------------------------------------------------------------
# Hold & PFC
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HoldStarted(SimEvent):
    """Patient hold begins (downstream queue full)."""

    reason: str = ""
    downstream_facility: str = ""
    constrained_resource: str = ""


@dataclass(frozen=True)
class HoldRetried(SimEvent):
    """Periodic retry during hold."""

    hold_duration_min: float = 0.0


@dataclass(frozen=True)
class HoldTimedOut(SimEvent):
    """Hold duration exceeded maximum."""

    hold_duration_min: float = 0.0


@dataclass(frozen=True)
class HoldReleased(SimEvent):
    """Hold released — patient can proceed."""

    hold_duration_min: float = 0.0


@dataclass(frozen=True)
class PFCStarted(SimEvent):
    """Prolonged field care initiated."""

    hold_duration_at_trigger: float = 0.0
    cmt_available: bool = True


@dataclass(frozen=True)
class PFCEnded(SimEvent):
    """Prolonged field care ended."""

    pfc_duration_min: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class PFCCeilingExceeded(SimEvent):
    """PFC ceiling exceeded for triage category."""

    pfc_duration_hours: float = 0.0
    max_hours: float = 0.0
    triage_at_ceiling: str = ""


# ---------------------------------------------------------------------------
# System / MASCAL
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MASCALDeclared(SimEvent):
    """MASCAL event activated."""

    arrival_rate: float = 0.0
    threshold: float = 0.0
    activation_count: int = 0


@dataclass(frozen=True)
class MASCALCleared(SimEvent):
    """MASCAL event deactivated."""

    duration_min: float = 0.0


@dataclass(frozen=True)
class DCSActivated(SimEvent):
    """Damage control surgery activated."""

    trigger_reason: str = ""


# ---------------------------------------------------------------------------
# Handover
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ATMISTGenerated(SimEvent):
    """ATMIST handover report generated."""

    handover_number: int = 0
    from_facility: str = ""
    to_facility: str = ""


@dataclass(frozen=True)
class NineLinerGenerated(SimEvent):
    """9-Liner MEDEVAC request generated."""

    from_facility: str = ""
    to_facility: str = ""


# ---------------------------------------------------------------------------
# Decision (from BTObserver)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BTDecisionLogged(SimEvent):
    """BT decision recorded by observer."""

    tree_name: str = ""
    decision: str = ""
    node_path: str = ""


# ---------------------------------------------------------------------------
# Registry + dynamic pattern matching
# ---------------------------------------------------------------------------

# Fixed registry: UPPER_SNAKE_CASE keys matching engine KNOWN_EVENT_TYPES
EVENT_REGISTRY: Dict[str, type] = {
    # Patient lifecycle
    "ARRIVAL": CasualtyCreated,
    "TRIAGE": TriageAssigned,
    "DISPOSITION": OutcomeRecorded,
    # Transport
    "TRANSIT_START": TransitStarted,
    "TRANSIT_END": TransitCompleted,
    # Facility
    "FACILITY_ARRIVAL": FacilityArrival,
    "TREATMENT_START": TreatmentStarted,
    "TREATMENT_END": TreatmentCompleted,
    # Hold & PFC
    "HOLD_START": HoldStarted,
    "HOLD_RETRY": HoldRetried,
    "HOLD_TIMEOUT": HoldTimedOut,
    "PFC_START": PFCStarted,
    "PFC_END": PFCEnded,
    # System
    "MASCAL_ACTIVATE": MASCALDeclared,
    "MASCAL_DEACTIVATE": MASCALCleared,
    "DCS": DCSActivated,
    # Handover
    "ATMIST_HANDOVER": ATMISTGenerated,
    "NINE_LINER": NineLinerGenerated,
    # Forward-looking (no engine counterpart yet)
    "QUEUE_ENTERED": QueueEntered,
    "HOLD_RELEASED": HoldReleased,
    "PFC_CEILING_EXCEEDED": PFCCeilingExceeded,
    "BT_DECISION": BTDecisionLogged,
}

# Dynamic event type patterns — match suffix to typed class.
# Engine emits f"{facility.role.name}_DEPT" for department events
# (POI_DEPT, R1_DEPT, R2_DEPT, R3_DEPT, R4_DEPT).
_DYNAMIC_PATTERNS: Dict[str, type] = {
    "_DEPT": DepartmentAssigned,
}


def _resolve_event_class(event_type: str) -> type:
    """Resolve event type string to class.

    Checks exact registry match first, then dynamic suffix patterns.
    Falls back to base SimEvent if nothing matches.
    """
    cls = EVENT_REGISTRY.get(event_type)
    if cls is not None:
        return cls
    for suffix, fallback_cls in _DYNAMIC_PATTERNS.items():
        if event_type.endswith(suffix):
            return fallback_cls
    return SimEvent


def create_event(event_type: str, **kwargs: Any) -> SimEvent:
    """Create a typed event from event_type string + kwargs.

    Handles both fixed registry types AND dynamic patterns
    (e.g. R3_DEPT -> DepartmentAssigned).
    Falls back to base SimEvent if type not matched anywhere.
    Unrecognised kwargs are placed in metadata.
    """
    cls = _resolve_event_class(event_type)
    valid_fields = {f.name for f in dataclasses.fields(cls)}
    filtered = {k: v for k, v in kwargs.items() if k in valid_fields}
    remaining = {k: v for k, v in kwargs.items() if k not in valid_fields}
    if remaining:
        known_type = event_type in EVENT_REGISTRY or any(
            event_type.endswith(suffix) for suffix in _DYNAMIC_PATTERNS
        )
        if known_type:
            warnings.warn(
                f"Event '{event_type}' received unexpected keys {sorted(remaining.keys())}",
                stacklevel=2,
            )
        filtered["metadata"] = {**filtered.get("metadata", {}), **remaining}
    return cls(event_type=event_type, **filtered)
