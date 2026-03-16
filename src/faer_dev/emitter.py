"""Typed event emission extracted from engine.py (EX-3).

Replaces legacy _log_event(dict) with typed, frozen SimEvent publication.
Closes K-7 (typed fields empty in production).

Zero SimPy imports. Receives sim_time as a plain float from caller.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Protocol — what engine.py codes against
# ---------------------------------------------------------------------------

@runtime_checkable
class EventEmitter(Protocol):
    """Protocol for event emission.

    The engine calls emit() with event data. The implementation handles
    both legacy dict storage and typed EventBus publication.
    """

    def emit(
        self,
        event_type: str,
        patient: Any,
        facility: Optional[str],
        details: Optional[Dict[str, Any]],
        sim_time: float,
    ) -> None: ...

    def emit_raw(
        self,
        event_type: str,
        sim_time: float,
        details: Dict[str, Any],
    ) -> None: ...


# ---------------------------------------------------------------------------
# TypedEmitter — concrete implementation
# ---------------------------------------------------------------------------

class TypedEmitter:
    """Emits events to both legacy dict list and typed EventBus.

    Key difference from legacy _log_event: the typed EventBus path
    constructs events with ALL detail fields mapped to typed dataclass
    fields, closing K-7.
    """

    def __init__(
        self,
        events_list: List[Dict[str, Any]],
        event_bus: Any,
    ) -> None:
        self._events = events_list
        self._event_bus = event_bus

    def emit(
        self,
        event_type: str,
        patient: Any,
        facility: Optional[str],
        details: Optional[Dict[str, Any]],
        sim_time: float,
    ) -> None:
        """Emit event to both legacy dict list and typed EventBus."""
        triage_val = (
            patient.triage.name
            if isinstance(patient.triage, Enum)
            else patient.triage
        )
        state_val = (
            patient.state.name
            if isinstance(patient.state, Enum)
            else patient.state
        )

        # === LEGACY PATH (always — backward compat) ===
        self._events.append({
            "time": sim_time,
            "type": event_type,
            "patient_id": patient.id,
            "triage": triage_val,
            "state": state_val,
            "facility": facility,
            "details": details or {},
        })

        # === TYPED BUS PATH (K-7 fix: all detail fields mapped) ===
        from faer_dev.events.models import create_event

        typed_event = create_event(
            event_type,
            sim_time=sim_time,
            casualty_id=patient.id,
            facility_id=facility,
            source="engine",
            triage=triage_val,
            **(details or {}),
        )
        self._event_bus.publish(typed_event)

    def emit_raw(
        self,
        event_type: str,
        sim_time: float,
        details: Dict[str, Any],
    ) -> None:
        """Emit system event (no patient) to legacy list and typed EventBus."""
        # === LEGACY PATH ===
        self._events.append({
            "time": sim_time,
            "type": event_type,
            "patient_id": None,
            "triage": None,
            "state": None,
            "facility": None,
            "details": details,
        })

        # === TYPED BUS PATH ===
        from faer_dev.events.models import create_event

        typed_event = create_event(
            event_type,
            sim_time=sim_time,
            source="engine",
            **details,
        )
        self._event_bus.publish(typed_event)
