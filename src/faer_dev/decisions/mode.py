"""Decision mode and simulation toggles for FAER-M.

DecisionMode controls how clinical decisions are made:
- RULE_BASED: Phase 2 hardcoded _triage_decisions() — baseline
- BT_DRIVEN: BT nodes make all decisions — production target
- HYBRID: BT decides, rule-based validates, logs discrepancies

SimulationToggles centralises feature flags for Iter 3 engine wiring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class DecisionMode(Enum):
    """How clinical decisions are made."""

    RULE_BASED = auto()
    BT_DRIVEN = auto()
    HYBRID = auto()

    @property
    def uses_bt(self) -> bool:
        return self in (DecisionMode.BT_DRIVEN, DecisionMode.HYBRID)

    @property
    def uses_rules(self) -> bool:
        return self in (DecisionMode.RULE_BASED, DecisionMode.HYBRID)

    @property
    def logs_discrepancies(self) -> bool:
        return self is DecisionMode.HYBRID


@dataclass
class SimulationToggles:
    """Feature flags for engine wiring.

    All defaults are the legacy/off path so that existing e2e_check.py
    exercises the Phase 2 code path until explicitly promoted.
    """

    factory_mode: str = "legacy"
    decision_mode: DecisionMode = field(default=DecisionMode.RULE_BASED)
    enable_department_routing: bool = False
    enable_vitals: bool = False
    enable_atmist: bool = False
    enable_event_store: bool = True
    enable_ccp: bool = False
    # Extraction toggles — when ON, call extracted module; when OFF, legacy inline
    enable_extracted_routing: bool = False
    enable_extracted_metrics: bool = False
    enable_typed_emitter: bool = False
    enable_extracted_pfc: bool = False
    # Phase 1.5: graph-based Dijkstra routing (replaces role-walk first-match)
    enable_graph_routing: bool = False
