"""Data-driven injury sampling from InjuryDataLoader.

Drop-in replacement for the Phase 2 InjuryProfileSampler, but
uses external YAML data instead of hardcoded distributions.

Usage:
    loader = InjuryDataLoader()
    sampler = DataDrivenInjurySampler('LSCO', loader, rng)
    profile = sampler.sample()  # returns dict
"""

from __future__ import annotations

import numpy as np

from faer_dev.data.injury_loader import InjuryDataLoader


class DataDrivenInjurySampler:
    """Context-aware injury sampler backed by InjuryDataLoader.

    Args:
        context: Operational context (LSCO, COIN, HADR, SPECOPS).
        injury_data: Loaded injury reference data.
        rng: NumPy random generator.
        unit_role: VOP unit role — stored but unused in Phase 3.
    """

    def __init__(
        self,
        context: str,
        injury_data: InjuryDataLoader,
        rng: np.random.Generator,
        unit_role: str = "DISMOUNTED",
    ):
        self.context = context
        self.data = injury_data
        self.rng = rng
        self.unit_role = unit_role
        self.mechanism_dist = injury_data.get_mechanism_distribution(context)
        self.alpha, self.beta_param = injury_data.get_severity_params(context)

    def sample(self) -> dict:
        """Sample a single injury profile.

        Returns:
            dict with keys: mechanism, primary_region, secondary_regions,
            severity, is_polytrauma, is_surgical_region.
        """
        # Sample mechanism
        mechs = list(self.mechanism_dist.keys())
        probs = np.array([self.mechanism_dist[m] for m in mechs])
        mechanism = mechs[self.rng.choice(len(mechs), p=probs)]

        # Sample primary region
        region_dist = self.data.get_region_distribution(mechanism)
        regions = list(region_dist.keys())
        reg_probs = np.array([region_dist[r] for r in regions])
        primary_region = regions[self.rng.choice(len(regions), p=reg_probs)]

        # Sample severity (Beta distribution, modified by mechanism)
        base_severity = float(self.rng.beta(self.alpha, self.beta_param))
        mech_mods = self.data.get_mechanism_modifiers(mechanism)
        severity = min(1.0, base_severity * mech_mods["severity"])

        # Polytrauma
        poly_prob = self.data.get_polytrauma_probability(mechanism)
        is_polytrauma = bool(self.rng.random() < poly_prob)

        # Secondary regions
        secondary_regions: list[str] = []
        if is_polytrauma:
            available = [r for r in regions if r != primary_region]
            n = int(self.rng.integers(1, min(4, len(available) + 1)))
            secondary_regions = list(
                self.rng.choice(available, size=n, replace=False)
            )

        return {
            "mechanism": mechanism,
            "primary_region": primary_region,
            "secondary_regions": secondary_regions,
            "severity": float(np.clip(severity, 0.0, 1.0)),
            "is_polytrauma": is_polytrauma,
            "is_surgical_region": self.data.is_surgical_region(primary_region),
        }
