"""Event serialization for FAER-M.

Converts between typed SimEvent objects and plain dicts/JSON.
Supports file export/import for state saving and analysis.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from faer_dev.events.models import SimEvent, create_event
from faer_dev.events.store import EventStore


class EventSerializer:
    """Serialize and deserialize SimEvent objects."""

    @staticmethod
    def event_to_dict(event: SimEvent) -> Dict[str, Any]:
        """Convert a SimEvent to a plain dict.

        Converts datetime to ISO string for JSON compatibility.
        """
        d = dataclasses.asdict(event)
        d["__event_class__"] = type(event).__name__
        if isinstance(d.get("wall_time"), datetime):
            d["wall_time"] = d["wall_time"].isoformat()
        return d

    @staticmethod
    def dict_to_event(d: Dict[str, Any]) -> SimEvent:
        """Convert a dict back to a typed SimEvent.

        Uses create_event() factory for type resolution.
        event_id and wall_time are regenerated (not preserved from dict).
        """
        d = dict(d)  # shallow copy
        d.pop("__event_class__", None)
        d.pop("event_id", None)
        d.pop("wall_time", None)
        event_type = d.pop("event_type", "")
        return create_event(event_type, **d)

    @staticmethod
    def store_to_json(store: EventStore) -> str:
        """Serialize entire store to JSON string."""
        events = [EventSerializer.event_to_dict(e) for e in store._events]
        return json.dumps(events, indent=2, default=str)

    @staticmethod
    def json_to_store(json_str: str) -> EventStore:
        """Deserialize JSON string into a new EventStore."""
        events_data = json.loads(json_str)
        store = EventStore()
        for d in events_data:
            store.append(EventSerializer.dict_to_event(d))
        return store

    @staticmethod
    def export_to_file(store: EventStore, filepath: str) -> None:
        """Write store contents to a JSON file."""
        Path(filepath).write_text(
            EventSerializer.store_to_json(store), encoding="utf-8"
        )

    @staticmethod
    def import_from_file(filepath: str) -> EventStore:
        """Read store contents from a JSON file."""
        json_str = Path(filepath).read_text(encoding="utf-8")
        return EventSerializer.json_to_store(json_str)
