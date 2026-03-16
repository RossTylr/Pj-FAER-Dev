"""Unified casualty generation.

Creates complete Casualty objects with linked attributes:
- Legacy: Triage -> Injury (Phase 2 flow)
- Inverted: Injury -> BT Triage (Phase 3 flow)

Use ``create_factory(mode, ...)`` to get the right factory.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np

from faer_dev.core.enums import (
    AnatomicalRegion,
    InjuryMechanism,
    OperationalContext,
    PatientState,
    TriageCategory,
)
from faer_dev.core.injury import InjuryProfile, InjuryProfileSampler
from faer_dev.core.schemas import Casualty
from faer_dev.core.triage import MASCALTriageShift, get_mascal_shift
from faer_dev.simulation.arrivals import ArrivalRecord

logger = logging.getLogger(__name__)


class LegacyCasualtyFactory:
    """Factory for creating complete Casualty objects.

    Ensures all attributes are properly linked:
    - Triage determines injury severity expectations
    - Injury profile affects treatment time modifier
    - MASCAL status shifts triage distribution
    """

    def __init__(
        self,
        context: OperationalContext,
        rng: Optional[np.random.Generator] = None,
        id_prefix: str = "",
    ) -> None:
        self.context = context
        self.rng = rng or np.random.default_rng()
        self.id_prefix = id_prefix

        self.triage_shift = get_mascal_shift(context)
        self.injury_sampler = InjuryProfileSampler(context, self.rng)

        self._counter = 0

    @property
    def count(self) -> int:
        """Number of casualties created."""
        return self._counter

    def create(
        self,
        arrival: ArrivalRecord,
        override_triage: Optional[TriageCategory] = None,
    ) -> Casualty:
        """Create a complete Casualty from an arrival record."""
        self._counter += 1

        casualty_id = self._generate_id()

        if override_triage is not None:
            triage = override_triage
        else:
            triage = self.triage_shift.sample(
                is_mascal=arrival.is_mascal, rng=self.rng
            )

        injury = self.injury_sampler.sample(triage)
        priority = self._calculate_priority(triage, injury)
        treatment_modifier = injury.get_treatment_time_modifier()

        return Casualty(
            id=casualty_id,
            triage=triage,
            initial_triage=triage,
            state=PatientState.AT_POI,
            mechanism=injury.mechanism,
            primary_region=injury.primary_region,
            secondary_regions=injury.secondary_regions,
            severity_score=injury.severity_score,
            priority_value=priority,
            treatment_time_modifier=treatment_modifier,
            is_mascal_casualty=arrival.is_mascal,
            mascal_event_id=arrival.mascal_id,
            arrival_time=arrival.time,
            created_at=arrival.time,
            state_changed_at=arrival.time,
        )

    def create_batch(self, arrivals: list[ArrivalRecord]) -> list[Casualty]:
        """Create casualties for a batch of arrivals."""
        return [self.create(a) for a in arrivals]

    def _generate_id(self) -> str:
        """Generate unique casualty ID."""
        if self.id_prefix:
            return f"{self.id_prefix}-{self._counter:04d}"
        return f"CAS-{self._counter:04d}"

    def _calculate_priority(
        self, triage: TriageCategory, injury: InjuryProfile
    ) -> int:
        """Calculate priority value for queuing (lower = higher priority)."""
        base_priority = {
            TriageCategory.T1_SURGICAL: 100,
            TriageCategory.T1_MEDICAL: 150,
            TriageCategory.T2: 300,
            TriageCategory.T3: 500,
            TriageCategory.T4: 900,
        }.get(triage, 500)

        severity_adjustment = int((1.0 - injury.severity_score) * 50)
        polytrauma_adjustment = -20 if injury.is_polytrauma else 0

        return base_priority + severity_adjustment + polytrauma_adjustment


# Backward-compat alias (Issue #9) — all existing imports still work
CasualtyFactory = LegacyCasualtyFactory


# ═══════════════════════════════════════════════════════════════
# INVERTED FACTORY — Phase 3 injury-first flow
# ═══════════════════════════════════════════════════════════════

# String -> Enum mappings for the 3 fields that need conversion
_MECHANISM_MAP = {m.name: m for m in InjuryMechanism}
_REGION_MAP = {r.name: r for r in AnatomicalRegion}
_TRIAGE_MAP = {t.name: t for t in TriageCategory}


def _to_mechanism(s: str) -> InjuryMechanism:
    return _MECHANISM_MAP.get(s.upper(), InjuryMechanism.BLUNT)


def _to_region(s: str) -> AnatomicalRegion:
    return _REGION_MAP.get(s.upper(), AnatomicalRegion.EXTERNAL)


def _to_triage(s: str) -> TriageCategory:
    return _TRIAGE_MAP.get(s.upper(), TriageCategory.T2)


class InvertedCasualtyFactory:
    """Phase 3 factory: injury sampled FIRST, then BT assigns triage.

    The caller provides a triage BT + SimBlackboard. This factory:
    1. Samples injury via DataDrivenInjurySampler
    2. Populates blackboard with patient context
    3. Ticks the triage BT
    4. Reads decision_triage from blackboard
    5. Creates Casualty with enum-converted fields

    String->enum conversion covers ONLY 3 fields:
    - mechanism (str) -> InjuryMechanism
    - primary_region / secondary_regions (str) -> AnatomicalRegion
    - triage (str from BT) -> TriageCategory
    Float/bool fields pass through unchanged.

    Args:
        context_name: Operational context string (LSCO, COIN, etc.).
        injury_sampler: DataDrivenInjurySampler instance.
        triage_bt: Built triage BehaviourTree.
        blackboard: SimBlackboard instance.
        rng: NumPy random generator.
        id_prefix: Optional casualty ID prefix.
        source_id: VOP source identifier for per-unit tracing.
    """

    def __init__(
        self,
        context_name: str,
        injury_sampler: Any,
        triage_bt: Any,
        blackboard: Any,
        rng: Optional[np.random.Generator] = None,
        id_prefix: str = "",
        source_id: str = "default",
    ):
        self.context_name = context_name
        self.injury_sampler = injury_sampler
        self.triage_bt = triage_bt
        self.bb = blackboard
        self.rng = rng or np.random.default_rng()
        self.id_prefix = id_prefix
        self.source_id = source_id
        self._counter = 0

    @property
    def count(self) -> int:
        return self._counter

    def create(
        self,
        arrival: ArrivalRecord,
        override_triage: Optional[TriageCategory] = None,
    ) -> Casualty:
        """Create a Casualty using the inverted (injury-first) flow."""
        self._counter += 1
        casualty_id = self._generate_id()

        # 1. Sample injury
        profile = self.injury_sampler.sample()

        # 2. Populate blackboard
        self.bb.reset_patient_context()
        self.bb.set_patient_context(
            severity=profile["severity"],
            primary_region=profile["primary_region"],
            mechanism=profile["mechanism"],
            is_polytrauma=profile["is_polytrauma"],
            is_surgical=profile["is_surgical_region"],
            patient_id=casualty_id,
        )
        self.bb.set("mascal_active", arrival.is_mascal)

        # 3. Tick triage BT (or use override)
        if override_triage is not None:
            triage = override_triage
        else:
            self.triage_bt.tick()
            triage = _to_triage(self.bb.decision_triage)

        # 4. Calculate priority
        priority = self._calculate_priority(triage, profile["severity"])

        # 5. Build Casualty with enum-converted fields
        cas = Casualty(
            id=casualty_id,
            triage=triage,
            initial_triage=triage,
            state=PatientState.AT_POI,
            mechanism=_to_mechanism(profile["mechanism"]),
            primary_region=_to_region(profile["primary_region"]),
            secondary_regions=[
                _to_region(r) for r in profile["secondary_regions"]
            ],
            severity_score=profile["severity"],
            priority_value=priority,
            treatment_time_modifier=1.0,
            is_mascal_casualty=arrival.is_mascal,
            mascal_event_id=arrival.mascal_id,
            arrival_time=arrival.time,
            created_at=arrival.time,
            state_changed_at=arrival.time,
        )
        # VOP: link casualty to originating source
        cas.metadata["source_id"] = self.source_id
        cas.metadata["factory_mode"] = "inverted"
        return cas

    def _generate_id(self) -> str:
        if self.id_prefix:
            return f"{self.id_prefix}-{self._counter:04d}"
        return f"CAS-{self._counter:04d}"

    @staticmethod
    def _calculate_priority(triage: TriageCategory, severity: float) -> int:
        base = {
            TriageCategory.T1_SURGICAL: 100,
            TriageCategory.T1_MEDICAL: 150,
            TriageCategory.T2: 300,
            TriageCategory.T3: 500,
            TriageCategory.T4: 900,
        }.get(triage, 500)
        return base + int((1.0 - severity) * 50)


# ═══════════════════════════════════════════════════════════════
# FACTORY SELECTOR
# ═══════════════════════════════════════════════════════════════


def create_factory(
    mode: str = "legacy",
    context: Optional[OperationalContext] = None,
    rng: Optional[np.random.Generator] = None,
    **kwargs: Any,
) -> LegacyCasualtyFactory | InvertedCasualtyFactory:
    """Create the appropriate factory based on mode.

    Args:
        mode: "legacy" (Phase 2) or "inverted" (Phase 3).
        context: Operational context enum.
        rng: NumPy random generator.
        **kwargs: Additional args passed to the factory constructor.
            For "inverted": injury_sampler, triage_bt, blackboard required.
    """
    ctx = context or OperationalContext.COIN

    if mode == "legacy":
        return LegacyCasualtyFactory(
            context=ctx, rng=rng, id_prefix=kwargs.get("id_prefix", ""),
        )

    if mode == "inverted":
        required = ["injury_sampler", "triage_bt", "blackboard"]
        missing = [k for k in required if k not in kwargs]
        if missing:
            raise ValueError(
                f"InvertedCasualtyFactory requires: {missing}"
            )
        return InvertedCasualtyFactory(
            context_name=ctx.name,
            injury_sampler=kwargs["injury_sampler"],
            triage_bt=kwargs["triage_bt"],
            blackboard=kwargs["blackboard"],
            rng=rng,
            id_prefix=kwargs.get("id_prefix", ""),
            source_id=kwargs.get("source_id", "default"),
        )

    raise ValueError(f"Unknown factory mode: {mode}")
