"""Canonical event serialisation — deterministic log digests (F0.1).

Typed events carry ``event_id`` (uuid4) and ``wall_time`` (wall clock), so
raw stores from two identical seed-42 runs never hash equal (MAAFI R1).
The canonical form strips exactly those two fields and sorts keys; all
other values are left untouched — floats are deliberately NOT rounded,
because masking real drift is worse than long decimals.

Pure module: no SimPy, no Streamlit (Hard Rule 5).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List

# The only fields that legitimately differ between identical runs.
_NON_DETERMINISTIC_FIELDS = frozenset({"event_id", "wall_time"})


def canonical_event(e: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of an event dict with the non-deterministic fields
    removed and keys sorted. Values are otherwise untouched."""
    return {k: e[k] for k in sorted(e) if k not in _NON_DETERMINISTIC_FIELDS}


def canonical_log(events: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map :func:`canonical_event` over a log, preserving order."""
    return [canonical_event(e) for e in events]


def log_digest(events: Iterable[Dict[str, Any]]) -> str:
    """SHA-256 of the JSON-dumped canonical log.

    Compact separators and sorted keys give a byte-stable dump;
    ``default=str`` covers stray datetimes or enums in metadata.
    """
    blob = json.dumps(
        canonical_log(events), sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
