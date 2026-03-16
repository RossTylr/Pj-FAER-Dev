"""Context-specific triage category distributions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from faer_dev.core.enums import OperationalContext, TriageCategory


@dataclass(frozen=True)
class TriageDistribution:
    """Triage category probabilities for a context.

    Probabilities must sum to 1.0.
    """

    t1_surgical: float
    t1_medical: float
    t2: float
    t3: float
    t4: float

    def __post_init__(self) -> None:
        total = self.t1_surgical + self.t1_medical + self.t2 + self.t3 + self.t4
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Probabilities must sum to 1.0, got {total}")

    @property
    def t1_total(self) -> float:
        """Combined T1 (immediate) proportion."""
        return self.t1_surgical + self.t1_medical

    def sample(
        self,
        n: int = 1,
        rng: Optional[np.random.Generator] = None,
    ) -> list[TriageCategory]:
        """Sample n triage categories from this distribution."""
        if rng is None:
            rng = np.random.default_rng()

        categories = [
            TriageCategory.T1_SURGICAL,
            TriageCategory.T1_MEDICAL,
            TriageCategory.T2,
            TriageCategory.T3,
            TriageCategory.T4,
        ]
        probs = [
            self.t1_surgical,
            self.t1_medical,
            self.t2,
            self.t3,
            self.t4,
        ]

        indices = rng.choice(len(categories), size=n, p=probs)
        return [categories[i] for i in indices]

    def sample_one(
        self, rng: Optional[np.random.Generator] = None
    ) -> TriageCategory:
        """Sample a single triage category."""
        return self.sample(1, rng)[0]


@dataclass(frozen=True)
class MASCALTriageShift:
    """Triage distribution shifts during MASCAL events.

    MASCAL typically increases proportion of severe injuries.
    """

    base: TriageDistribution
    mascal: TriageDistribution

    def sample(
        self,
        is_mascal: bool,
        rng: Optional[np.random.Generator] = None,
    ) -> TriageCategory:
        """Sample using appropriate distribution."""
        dist = self.mascal if is_mascal else self.base
        return dist.sample_one(rng)


# ---------------------------------------------------------------------------
# Context-specific distributions
# ---------------------------------------------------------------------------

TRIAGE_DISTRIBUTIONS: dict[OperationalContext, TriageDistribution] = {
    OperationalContext.COIN: TriageDistribution(
        t1_surgical=0.05, t1_medical=0.10, t2=0.25, t3=0.50, t4=0.10,
    ),
    OperationalContext.LSCO: TriageDistribution(
        t1_surgical=0.15, t1_medical=0.10, t2=0.30, t3=0.35, t4=0.10,
    ),
    OperationalContext.HADR: TriageDistribution(
        t1_surgical=0.03, t1_medical=0.07, t2=0.20, t3=0.60, t4=0.10,
    ),
    OperationalContext.SPECOPS: TriageDistribution(
        t1_surgical=0.20, t1_medical=0.10, t2=0.30, t3=0.30, t4=0.10,
    ),
}

MASCAL_TRIAGE_SHIFTS: dict[OperationalContext, MASCALTriageShift] = {
    OperationalContext.COIN: MASCALTriageShift(
        base=TRIAGE_DISTRIBUTIONS[OperationalContext.COIN],
        mascal=TriageDistribution(
            t1_surgical=0.10, t1_medical=0.15, t2=0.30, t3=0.35, t4=0.10,
        ),
    ),
    OperationalContext.LSCO: MASCALTriageShift(
        base=TRIAGE_DISTRIBUTIONS[OperationalContext.LSCO],
        mascal=TriageDistribution(
            t1_surgical=0.25, t1_medical=0.15, t2=0.30, t3=0.20, t4=0.10,
        ),
    ),
    OperationalContext.HADR: MASCALTriageShift(
        base=TRIAGE_DISTRIBUTIONS[OperationalContext.HADR],
        mascal=TriageDistribution(
            t1_surgical=0.08, t1_medical=0.12, t2=0.30, t3=0.40, t4=0.10,
        ),
    ),
    OperationalContext.SPECOPS: MASCALTriageShift(
        base=TRIAGE_DISTRIBUTIONS[OperationalContext.SPECOPS],
        mascal=TriageDistribution(
            t1_surgical=0.30, t1_medical=0.15, t2=0.30, t3=0.15, t4=0.10,
        ),
    ),
}


def get_triage_distribution(context: OperationalContext) -> TriageDistribution:
    """Get triage distribution for context. PEACEKEEPING falls back to COIN."""
    if context not in TRIAGE_DISTRIBUTIONS:
        context = OperationalContext.COIN
    return TRIAGE_DISTRIBUTIONS[context]


def get_mascal_shift(context: OperationalContext) -> MASCALTriageShift:
    """Get MASCAL triage shift for context. PEACEKEEPING falls back to COIN."""
    if context not in MASCAL_TRIAGE_SHIFTS:
        context = OperationalContext.COIN
    return MASCAL_TRIAGE_SHIFTS[context]
