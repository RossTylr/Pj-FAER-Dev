"""Structured run logging for FAER-M.

Appends one JSONL entry per simulation run for audit trail and analysis.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_LOG_PATH = "run_log.jsonl"


@dataclass
class RunLogEntry:
    """One entry per simulation run."""

    timestamp: str = ""
    context: str = ""
    n_patients: int = 0
    factory_mode: str = "legacy"
    toggles: Dict[str, Any] = field(default_factory=dict)
    duration_sec: float = 0.0
    completed: int = 0
    events_emitted: int = 0
    test_name: Optional[str] = None
    status: str = "PASS"
    error_message: Optional[str] = None

    @staticmethod
    def from_engine_run(
        engine: Any,
        duration_sec: float,
        status: str = "PASS",
        error: Optional[str] = None,
    ) -> RunLogEntry:
        """Create entry from engine after a run.

        Safely accesses engine attributes — never crashes if fields are missing.
        """
        # Context
        context = str(getattr(engine, "context", "UNKNOWN"))

        # Patient count
        n_patients = len(getattr(engine, "completed_patients", []))
        n_patients += len(getattr(engine, "patients", {}))

        # Factory mode from toggles
        toggles = getattr(engine, "toggles", None)
        factory_mode = getattr(toggles, "factory_mode", "legacy") if toggles else "legacy"
        toggles_dict: Dict[str, Any] = {}
        if toggles and hasattr(toggles, "__dataclass_fields__"):
            toggles_dict = asdict(toggles)

        # Event count
        event_store = getattr(engine, "event_store", None)
        events_emitted = event_store.count if event_store else len(getattr(engine, "events", []))

        # Completed patients
        completed = len(getattr(engine, "completed_patients", []))

        return RunLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            context=context,
            n_patients=n_patients,
            factory_mode=factory_mode,
            toggles=toggles_dict,
            duration_sec=round(duration_sec, 3),
            completed=completed,
            events_emitted=events_emitted,
            test_name=os.environ.get("PYTEST_CURRENT_TEST"),
            status=status,
            error_message=error,
        )


class RunLogger:
    """Append-only JSONL run logger."""

    def __init__(self, filepath: Optional[str] = None) -> None:
        self.filepath = Path(filepath or _DEFAULT_LOG_PATH)

    def log_run(self, entry: RunLogEntry) -> None:
        """Append a run log entry as one JSONL line."""
        try:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(entry), default=str) + "\n")
        except Exception:
            logger.warning("Failed to write run log entry", exc_info=True)

    def read_all(self) -> List[RunLogEntry]:
        """Read all entries from the log file."""
        if not self.filepath.exists():
            return []
        entries: List[RunLogEntry] = []
        for line in self.filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            entries.append(RunLogEntry(**{
                k: v for k, v in d.items()
                if k in RunLogEntry.__dataclass_fields__
            }))
        return entries

    def tail(self, n: int = 5) -> List[RunLogEntry]:
        """Return the last N entries."""
        return self.read_all()[-n:]
