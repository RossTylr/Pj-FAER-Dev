"""Vital signs generation and evolution.

Usage:
    gen = VitalsGenerator(injury_data_loader, rng)
    vitals = gen.generate_initial('T1_SURGICAL', severity=0.78, region='THORAX')
    vitals_later = gen.deteriorate(vitals, 30, 'T1_SURGICAL', 'BLAST')
    vitals_post = gen.post_treatment(vitals_later, 'FST')
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from faer_dev.core.schemas import VitalSigns
from faer_dev.data.injury_loader import InjuryDataLoader


def _avpu_from_gcs(gcs: int) -> str:
    if gcs >= 14:
        return "A"
    if gcs >= 10:
        return "V"
    if gcs >= 7:
        return "P"
    return "U"


class VitalsGenerator:
    """Generate and evolve vital signs for a casualty."""

    def __init__(self, injury_data: InjuryDataLoader, rng: np.random.Generator):
        self.data = injury_data
        self.rng = rng

    def generate_initial(
        self,
        triage: str,
        severity: float = 0.5,
        region: Optional[str] = None,
    ) -> VitalSigns:
        """Sample initial vital signs from triage-dependent baselines."""
        baseline = self.data.get_vitals_baseline(triage)

        def sample_vital(params: dict) -> int:
            val = self.rng.normal(params["mean"], params["std"])
            return int(np.clip(val, params["min"], params["max"]))

        gcs = sample_vital(baseline["gcs"])
        if region:
            gcs_mod = self.data.get_region_info(region).get("gcs_modifier", 0)
            gcs = int(np.clip(gcs + gcs_mod, 3, 15))

        severity_shift = (severity - 0.5) * 2
        hr = int(np.clip(
            sample_vital(baseline["heart_rate"]) + severity_shift * 15, 40, 180
        ))
        sbp = int(np.clip(
            sample_vital(baseline["systolic_bp"]) - severity_shift * 15, 40, 200
        ))
        rr = int(np.clip(
            sample_vital(baseline["respiratory_rate"]) + severity_shift * 4, 8, 40
        ))
        spo2 = int(np.clip(
            sample_vital(baseline["spo2"]) - severity_shift * 3, 70, 100
        ))

        return VitalSigns(
            gcs=gcs, heart_rate=hr, systolic_bp=sbp,
            respiratory_rate=rr, spo2=spo2, avpu=_avpu_from_gcs(gcs),
        )

    def deteriorate(
        self,
        vitals: VitalSigns,
        elapsed_minutes: float,
        triage: str,
        mechanism: Optional[str] = None,
        with_pfc: bool = False,
    ) -> VitalSigns:
        """Apply time-based deterioration to vital signs."""
        rate = self.data.get_deterioration_rate(triage, mechanism, with_pfc)
        intervals = elapsed_minutes / 5.0
        factor = rate * intervals

        new_gcs = int(np.clip(vitals.gcs - factor * 3, 3, 15))
        new_hr = int(np.clip(vitals.heart_rate + factor * 20, 40, 180))
        new_sbp = int(np.clip(vitals.systolic_bp - factor * 25, 40, 200))
        new_rr = int(np.clip(vitals.respiratory_rate + factor * 5, 8, 40))
        new_spo2 = int(np.clip(vitals.spo2 - factor * 5, 70, 100))

        return VitalSigns(
            gcs=new_gcs, heart_rate=new_hr, systolic_bp=new_sbp,
            respiratory_rate=new_rr, spo2=new_spo2, avpu=_avpu_from_gcs(new_gcs),
        )

    def post_treatment(
        self, vitals: VitalSigns, treatment_type: str = "DCR"
    ) -> VitalSigns:
        """Apply post-treatment improvement to vital signs."""
        improvement = {
            "DCR": 0.3, "FST": 0.6, "ITU": 0.4, "ED": 0.2, "WARD": 0.1,
        }.get(treatment_type, 0.2)

        new_gcs = int(np.clip(vitals.gcs + improvement * 3, 3, 15))
        new_hr = int(np.clip(vitals.heart_rate - improvement * 15, 40, 180))
        new_sbp = int(np.clip(vitals.systolic_bp + improvement * 20, 40, 200))
        new_spo2 = int(np.clip(vitals.spo2 + improvement * 4, 70, 100))

        return VitalSigns(
            gcs=new_gcs, heart_rate=new_hr, systolic_bp=new_sbp,
            respiratory_rate=vitals.respiratory_rate, spo2=new_spo2,
            avpu=_avpu_from_gcs(new_gcs),
        )
