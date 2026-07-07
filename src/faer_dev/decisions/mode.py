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

from faer_dev.core.exceptions import ConfigurationError


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
    # S1.2a: capability-aware routing (requires_dcs ↔ has_surgery), strangler
    # side only — the legacy walk stays capability-blind until retirement
    enable_capability_routing: bool = False
    # S1.1: facility context writer — engine pushes live facility state onto
    # the blackboard at three call-sites; contract-first, no consumer wired
    enable_facility_writer: bool = False
    # S2 slice 0: RNG architecture — "keyed" (default since 0e) draws every
    # stochastic value from a per-(entity, purpose, occurrence) Philox
    # stream; "shared" is the legacy single-stream path, retained behind the
    # toggle for archaeology until a later retirement milestone
    rng_mode: str = "keyed"
    # S2 slice 0c-2: record the eager identity roster at casualty creation
    # (POLYBIUS input-interface artefact; parquet writer is an optional extra)
    enable_roster: bool = False

    def __post_init__(self) -> None:
        if self.rng_mode not in ("shared", "keyed"):
            raise ConfigurationError(
                f"rng_mode must be 'shared' or 'keyed', got {self.rng_mode!r}"
            )
        # R11-family guard: a capability toggle that is inert on the default
        # (legacy) path is the silent-toggle trap. Legacy + capability is an
        # invalid combination by design — fail at construction, not mid-run.
        if self.enable_capability_routing and not self.enable_extracted_routing:
            raise ConfigurationError(
                "enable_capability_routing requires enable_extracted_routing=True: "
                "the legacy walk is capability-blind by design."
            )
