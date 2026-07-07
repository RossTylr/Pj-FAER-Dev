"""Injury mechanism and anatomical region sampling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from faer_dev.core.enums import (
    AnatomicalRegion,
    InjuryMechanism,
    OperationalContext,
    TriageCategory,
)
from faer_dev.core.rng import RNGPurpose


@dataclass
class InjuryProfile:
    """Complete injury profile for a casualty."""

    mechanism: InjuryMechanism
    primary_region: AnatomicalRegion
    secondary_regions: list[AnatomicalRegion] = field(default_factory=list)
    severity_score: float = 0.5

    @property
    def all_regions(self) -> list[AnatomicalRegion]:
        """All affected regions (primary + secondary)."""
        return [self.primary_region] + self.secondary_regions

    @property
    def n_regions(self) -> int:
        """Number of affected regions."""
        return 1 + len(self.secondary_regions)

    @property
    def is_polytrauma(self) -> bool:
        """Multiple regions affected (3+ per clinical definition)."""
        return self.n_regions >= 3

    def get_treatment_time_modifier(self) -> float:
        """Calculate treatment time modifier based on injury profile.

        Returns:
            Multiplier (1.0 = baseline, >1 = longer, <1 = shorter).
        """
        modifier = 1.0

        mechanism_mods = {
            InjuryMechanism.BLAST: 1.3,
            InjuryMechanism.GSW: 1.1,
            InjuryMechanism.PENETRATING: 1.2,
            InjuryMechanism.BLUNT: 1.0,
            InjuryMechanism.BURN: 1.5,
            InjuryMechanism.ENVIRONMENTAL: 0.8,
            InjuryMechanism.MEDICAL: 0.7,
        }
        modifier *= mechanism_mods.get(self.mechanism, 1.0)

        region_mods = {
            AnatomicalRegion.HEAD: 1.4,
            AnatomicalRegion.THORAX: 1.3,
            AnatomicalRegion.ABDOMEN: 1.2,
            AnatomicalRegion.SPINE: 1.5,
            AnatomicalRegion.PELVIS: 1.3,
            AnatomicalRegion.NECK: 1.2,
        }
        modifier *= region_mods.get(self.primary_region, 1.0)

        modifier *= 1.0 + 0.1 * len(self.secondary_regions)
        modifier *= 0.8 + 0.4 * self.severity_score

        return modifier


# ---------------------------------------------------------------------------
# Context-specific mechanism probabilities
# ---------------------------------------------------------------------------

MECHANISM_PROBABILITIES: dict[OperationalContext, dict[InjuryMechanism, float]] = {
    OperationalContext.COIN: {
        InjuryMechanism.BLAST: 0.35,
        InjuryMechanism.GSW: 0.40,
        InjuryMechanism.BLUNT: 0.10,
        InjuryMechanism.PENETRATING: 0.10,
        InjuryMechanism.BURN: 0.03,
        InjuryMechanism.ENVIRONMENTAL: 0.02,
    },
    OperationalContext.LSCO: {
        InjuryMechanism.BLAST: 0.50,
        InjuryMechanism.GSW: 0.25,
        InjuryMechanism.BLUNT: 0.10,
        InjuryMechanism.PENETRATING: 0.10,
        InjuryMechanism.BURN: 0.03,
        InjuryMechanism.ENVIRONMENTAL: 0.02,
    },
    OperationalContext.HADR: {
        InjuryMechanism.BLAST: 0.05,
        InjuryMechanism.GSW: 0.05,
        InjuryMechanism.BLUNT: 0.50,
        InjuryMechanism.PENETRATING: 0.10,
        InjuryMechanism.BURN: 0.15,
        InjuryMechanism.ENVIRONMENTAL: 0.15,
    },
    OperationalContext.SPECOPS: {
        InjuryMechanism.BLAST: 0.30,
        InjuryMechanism.GSW: 0.50,
        InjuryMechanism.BLUNT: 0.05,
        InjuryMechanism.PENETRATING: 0.10,
        InjuryMechanism.BURN: 0.03,
        InjuryMechanism.ENVIRONMENTAL: 0.02,
    },
}

# Anatomical region probabilities (context-independent)
REGION_PROBABILITIES: dict[AnatomicalRegion, float] = {
    AnatomicalRegion.HEAD: 0.10,
    AnatomicalRegion.FACE: 0.05,
    AnatomicalRegion.NECK: 0.03,
    AnatomicalRegion.THORAX: 0.15,
    AnatomicalRegion.ABDOMEN: 0.12,
    AnatomicalRegion.PELVIS: 0.05,
    AnatomicalRegion.UPPER_EXTREMITY: 0.20,
    AnatomicalRegion.LOWER_EXTREMITY: 0.25,
    AnatomicalRegion.SPINE: 0.03,
    AnatomicalRegion.EXTERNAL: 0.02,
}

# Number of secondary regions by triage severity (min, max for randint)
SECONDARY_REGION_COUNTS: dict[TriageCategory, tuple[int, int]] = {
    TriageCategory.T1_SURGICAL: (1, 4),
    TriageCategory.T1_MEDICAL: (1, 3),
    TriageCategory.T2: (0, 2),
    TriageCategory.T3: (0, 1),
    TriageCategory.T4: (2, 5),
}

# Severity score base by triage
SEVERITY_BASE: dict[TriageCategory, float] = {
    TriageCategory.T1_SURGICAL: 0.80,
    TriageCategory.T1_MEDICAL: 0.70,
    TriageCategory.T2: 0.40,
    TriageCategory.T3: 0.20,
    TriageCategory.T4: 0.95,
}


class InjuryProfileSampler:
    """Sample injury profiles conditioned on context and triage.

    Triage category influences number of secondary regions and severity.
    Context influences injury mechanism distribution.
    """

    def __init__(
        self,
        context: OperationalContext,
        rng: Optional[np.random.Generator] = None,
    ) -> None:
        self.context = context
        self.rng = rng or np.random.default_rng()
        self.mechanism_probs = MECHANISM_PROBABILITIES.get(
            context, MECHANISM_PROBABILITIES[OperationalContext.COIN]
        )

    def sample(
        self,
        triage: TriageCategory,
        draws: Optional[Callable[[RNGPurpose], np.random.Generator]] = None,
    ) -> InjuryProfile:
        """Sample a complete injury profile for the given triage category.

        ``draws`` is the keyed-mode hook (S2 slice 0c): a callable mapping an
        RNGPurpose to the Generator for this casualty's draw of that purpose.
        When omitted, every purpose resolves to the shared stream ``self.rng``
        — the legacy behaviour, byte-identical.
        """
        g = draws if draws is not None else (lambda purpose: self.rng)
        mechanism = self._sample_mechanism(g(RNGPurpose.MECHANISM))
        primary_region = self._sample_region(g(RNGPurpose.PRIMARY_REGION))
        secondary_regions = self._sample_secondary_regions(
            triage,
            primary_region,
            g(RNGPurpose.SECONDARY_COUNT),
            g(RNGPurpose.SECONDARY_REGIONS),
        )
        severity = self._sample_severity(triage, g(RNGPurpose.SEVERITY))

        return InjuryProfile(
            mechanism=mechanism,
            primary_region=primary_region,
            secondary_regions=secondary_regions,
            severity_score=severity,
        )

    def _sample_mechanism(self, rng: np.random.Generator) -> InjuryMechanism:
        """Sample injury mechanism based on context."""
        mechanisms = list(self.mechanism_probs.keys())
        probs = [self.mechanism_probs[m] for m in mechanisms]
        idx = rng.choice(len(mechanisms), p=probs)
        return mechanisms[idx]

    def _sample_region(self, rng: np.random.Generator) -> AnatomicalRegion:
        """Sample primary anatomical region."""
        regions = list(REGION_PROBABILITIES.keys())
        probs = [REGION_PROBABILITIES[r] for r in regions]
        idx = rng.choice(len(regions), p=probs)
        return regions[idx]

    def _sample_secondary_regions(
        self,
        triage: TriageCategory,
        primary: AnatomicalRegion,
        count_rng: np.random.Generator,
        regions_rng: np.random.Generator,
    ) -> list[AnatomicalRegion]:
        """Sample secondary regions based on triage severity.

        The region set is one logical draw-event (keyed as an array draw);
        the count is its own purpose so a doctrine-varying count cannot
        shift the set's stream position.
        """
        min_count, max_count = SECONDARY_REGION_COUNTS.get(triage, (0, 1))
        n_secondary = int(count_rng.integers(min_count, max_count))

        if n_secondary == 0:
            return []

        available = [r for r in REGION_PROBABILITIES if r != primary]
        probs = np.array([REGION_PROBABILITIES[r] for r in available])
        probs = probs / probs.sum()

        n_to_sample = min(n_secondary, len(available))
        indices = regions_rng.choice(
            len(available), size=n_to_sample, replace=False, p=probs,
        )

        return [available[i] for i in indices]

    def _sample_severity(
        self, triage: TriageCategory, rng: np.random.Generator
    ) -> float:
        """Sample severity score based on triage."""
        base = SEVERITY_BASE.get(triage, 0.5)
        severity = rng.normal(base, 0.10)
        return float(np.clip(severity, 0.0, 1.0))
