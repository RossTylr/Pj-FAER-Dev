"""State loader — save and load simulation state for replay and analysis.

Phase 4 scope: save event store + metadata, load for replay.
Phase 5 scope (deferred): resume-from-snapshot.

Saves two files:
- {name}.json: metadata snapshot (config, toggles, summary)
- {name}.events.json: full event store (via EventSerializer)
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict

from faer_dev.events.serialization import EventSerializer
from faer_dev.events.store import EventStore


class StateLoader:
    """Save and load simulation state for replay and analysis."""

    @staticmethod
    def save(engine: Any, filepath: str) -> Dict[str, Any]:
        """Save engine state to file.

        Saves event store (full history) + configuration snapshot.
        Does NOT save SimPy env state (not serializable).

        Args:
            engine: PolyhybridEngine instance (after run())
            filepath: Path for metadata JSON (events saved as .events.json)

        Returns:
            The snapshot dict that was saved.
        """
        # Build config from engine attributes
        config: Dict[str, Any] = {}
        if hasattr(engine, "config") and engine.config:
            # engine.config is the raw dict from builder
            config = dict(engine.config) if isinstance(engine.config, dict) else {}
        if not config:
            config = StateLoader._build_fallback_config(engine)

        # Toggles
        toggles: Dict[str, Any] = {}
        if hasattr(engine, "toggles"):
            try:
                toggles = asdict(engine.toggles)
            except Exception:
                toggles = vars(engine.toggles) if engine.toggles else {}

        snapshot: Dict[str, Any] = {
            "version": "4.0.0",
            "config": config,
            "toggles": toggles,
            "results_summary": {
                "total_events": engine.event_store.count,
                "event_types": sorted(engine.event_store.event_types),
                "completed_patients": len(getattr(engine, "completed_patients", [])),
            },
        }

        path = Path(filepath)
        path.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")

        events_path = str(path).replace(".json", ".events.json")
        EventSerializer.export_to_file(engine.event_store, events_path)

        return snapshot

    @staticmethod
    def _build_fallback_config(engine: Any) -> Dict[str, Any]:
        """Build deterministic config snapshot for non-builder engines."""
        fallback: Dict[str, Any] = {}

        context = getattr(engine, "context", None)
        if context is not None:
            fallback["operational_context"] = getattr(context, "name", str(context))

        arrival = getattr(engine, "_arrival_config", None)
        if arrival is not None:
            if is_dataclass(arrival):
                fallback["arrivals"] = asdict(arrival)
            else:
                fallback["arrivals"] = dict(vars(arrival))

        transport = getattr(engine, "_transport_config", None)
        if transport is not None:
            if is_dataclass(transport):
                fallback["transport"] = asdict(transport)
            else:
                fallback["transport"] = dict(vars(transport))

        network = getattr(engine, "network", None)
        if network is not None:
            facilities = []
            for fac in getattr(network, "facilities", {}).values():
                facilities.append({
                    "id": fac.id,
                    "name": fac.name,
                    "role": getattr(fac.role, "name", str(fac.role)),
                    "beds": fac.beds,
                })
            if facilities:
                fallback["facilities"] = facilities

            edges = []
            graph = getattr(network, "graph", None)
            if graph is not None:
                for src, dst, attrs in graph.edges(data=True):
                    edges.append({
                        "from": src,
                        "to": dst,
                        "travel_time_minutes": attrs.get("weight", 0.0),
                        "transport": attrs.get("transport", "ground"),
                    })
            if edges:
                fallback["edges"] = edges

        return fallback

    @staticmethod
    def load(filepath: str) -> Dict[str, Any]:
        """Load saved state.

        Returns dict with:
            - "snapshot": metadata dict
            - "event_store": EventStore populated from events file
        """
        path = Path(filepath)
        snapshot = json.loads(path.read_text(encoding="utf-8"))

        events_path = str(path).replace(".json", ".events.json")
        event_store = EventSerializer.import_from_file(events_path)

        return {"snapshot": snapshot, "event_store": event_store}
