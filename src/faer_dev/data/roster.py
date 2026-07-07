"""Casualty roster artefact (S2 slice 0c-2).

The eager identity roster: one row per casualty, frozen at creation, holding
every identity-axis attribute (and the pre-drawn Sellke frailty threshold in
keyed mode). Under keyed draws the roster is config-invariant — "the same
person under any doctrine" becomes a diffable fact (invariant I-2), and the
parquet artefact is POLYBIUS's input interface.

Parquet is an OPTIONAL EXTRA (ruling, S2 kickoff): install with
``pip install faer-dev[roster]``. The in-memory roster and its digest need
no third-party dependency.

Pure module: no SimPy, no Streamlit (Hard Rule 5).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List

from faer_dev.events.canonical import log_digest


def _name(value: Any) -> Any:
    """Enum -> stable wire name; everything else passes through."""
    return value.name if isinstance(value, Enum) else value


def roster_row(casualty: Any) -> Dict[str, Any]:
    """Build one roster row from a just-created Casualty.

    Only identity-axis attributes final at creation belong here — no
    journey state, no routing-derived fields, no system-axis values.
    (S2-D D2: spawn_time and MASCAL provenance removed — schedule facts
    in the identity artefact broke dual-root axis separation; the event
    log carries both. I-7 clause 3 polices this. POLYBIUS may re-add
    provenance columns deliberately at D6 enrichment.)
    """
    return {
        "casualty_id": casualty.id,
        "initial_triage": _name(casualty.initial_triage),
        "mechanism": _name(casualty.mechanism),
        "primary_region": _name(casualty.primary_region),
        "secondary_regions": [_name(r) for r in casualty.secondary_regions],
        "severity_score": float(casualty.severity_score),
        "priority_value": int(casualty.priority_value),
        "treatment_time_modifier": float(casualty.treatment_time_modifier),
        "frailty_threshold": casualty.metadata.get("frailty_threshold"),
    }


def roster_digest(rows: List[Dict[str, Any]]) -> str:
    """SHA-256 of the canonical roster (reuses the F0.1 canonical dump)."""
    return log_digest(rows)


def write_roster_parquet(rows: List[Dict[str, Any]], path: str) -> None:
    """Write the roster to a parquet file. Requires the ``roster`` extra."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError(
            "Roster parquet output requires pyarrow — install the optional "
            "extra: pip install faer-dev[roster]"
        ) from exc

    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)
