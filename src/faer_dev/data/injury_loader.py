"""Load and serve injury reference data from YAML.

Usage:
    loader = InjuryDataLoader()  # loads default bundled YAML
    mechs = loader.get_mechanism_distribution('LSCO')
    mean, std = loader.get_treatment_time('FST', 'BLAST', 'THORAX')
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_YAML = Path(__file__).parent / "injury_reference.yaml"

# Known YAML top-level sections (VOP may add more — warn, don't error)
_KNOWN_SECTIONS = {
    "version", "last_updated", "source", "notes",
    "mechanisms", "regions", "severity", "treatment_times",
    "deterioration", "vitals_baselines", "triage_thresholds",
    "pfc",  # Phase 4 Iter 4
    "transport_platforms",  # reserved for VOP
}


class InjuryDataLoader:
    """Load and serve injury reference data from YAML.

    Args:
        path: Path to YAML file. Defaults to bundled injury_reference.yaml.
    """

    def __init__(self, path: Optional[Path] = None):
        self._path = Path(path) if path else _DEFAULT_YAML
        with open(self._path) as f:
            self.data: dict = yaml.safe_load(f)
        self._issues = self._validate()
        self.version: str = self.data.get("version", "unknown")
        logger.info(
            "InjuryDataLoader v%s: %d mechanisms, %d regions",
            self.version,
            len(self.data.get("mechanisms", {})),
            len(self.data.get("regions", {})),
        )

    # ── Validation ──────────────────────────────────────────────

    def _validate(self) -> list[str]:
        issues: list[str] = []

        # Warn on unknown sections (VOP may add transport_platforms, par_units, etc.)
        unknown = set(self.data.keys()) - _KNOWN_SECTIONS
        if unknown:
            issues.append(f"WARN: Unknown sections (ignored): {unknown}")

        # Mechanism prevalence per context should sum to ~1.0
        for ctx in ("LSCO", "COIN", "HADR", "SPECOPS"):
            total = sum(
                m["context_prevalence"].get(ctx, 0)
                for m in self.data.get("mechanisms", {}).values()
            )
            if abs(total - 1.0) > 0.01:
                issues.append(
                    f"WARN: Mechanism prevalence for {ctx} sums to {total:.3f}"
                )

        # Region probabilities per mechanism should sum to ~1.0
        for mech_name, mech_data in self.data.get("mechanisms", {}).items():
            total = sum(mech_data.get("region_probabilities", {}).values())
            if abs(total - 1.0) > 0.01:
                issues.append(
                    f"WARN: Region probs for {mech_name} sum to {total:.3f}"
                )

        # Every department in treatment_times must have a 'default'
        for dept, times in self.data.get("treatment_times", {}).items():
            if "default" not in times:
                issues.append(f"ERROR: {dept} missing default treatment time")

        for issue in issues:
            if issue.startswith("ERROR"):
                logger.error(issue)
            else:
                logger.warning(issue)
        return issues

    @property
    def validation_issues(self) -> list[str]:
        return list(self._issues)

    # ── Properties (derived from YAML keys, not hardcoded) ──────

    @property
    def mechanisms(self) -> list[str]:
        return list(self.data.get("mechanisms", {}).keys())

    @property
    def regions(self) -> list[str]:
        return list(self.data.get("regions", {}).keys())

    @property
    def contexts(self) -> list[str]:
        return list(self.data.get("severity", {}).keys())

    # ── Distribution getters (all normalize to sum=1.0) ─────────

    def get_mechanism_distribution(self, context: str) -> dict[str, float]:
        """Mechanism probabilities for a context, normalized to sum=1.0."""
        dist = {
            m: d["context_prevalence"].get(context, 0)
            for m, d in self.data.get("mechanisms", {}).items()
        }
        total = sum(dist.values())
        if total > 0:
            return {k: v / total for k, v in dist.items()}
        return dist

    def get_region_distribution(self, mechanism: str) -> dict[str, float]:
        """Region probabilities for a mechanism, normalized to sum=1.0."""
        probs = (
            self.data.get("mechanisms", {})
            .get(mechanism, {})
            .get("region_probabilities", {})
        )
        total = sum(probs.values())
        if total > 0:
            return {k: v / total for k, v in probs.items()}
        return dict(probs)

    # ── Severity ────────────────────────────────────────────────

    def get_severity_params(self, context: str) -> tuple[float, float]:
        """Beta distribution (alpha, beta) for a context."""
        sev = self.data.get("severity", {}).get(
            context, {"alpha": 2.0, "beta": 3.0}
        )
        return sev["alpha"], sev["beta"]

    # ── Mechanism modifiers ─────────────────────────────────────

    def get_mechanism_modifiers(self, mechanism: str) -> dict[str, float]:
        """All modifiers for a mechanism as a dict."""
        d = self.data.get("mechanisms", {}).get(mechanism, {})
        return {
            "severity": d.get("severity_modifier", 1.0),
            "polytrauma_prob": d.get("polytrauma_probability", 0.15),
            "treatment_time": d.get("treatment_time_modifier", 1.0),
            "deterioration": d.get("deterioration_modifier", 1.0),
        }

    # ── Region info ─────────────────────────────────────────────

    def get_region_info(self, region: str) -> dict:
        """Region metadata (surgical, treatment_time_modifier, gcs_modifier)."""
        return self.data.get("regions", {}).get(
            region,
            {"surgical": False, "treatment_time_modifier": 1.0, "gcs_modifier": 0},
        )

    def is_surgical_region(self, region: str) -> bool:
        """Whether a region is classified as surgical."""
        return self.get_region_info(region).get("surgical", False)

    def get_polytrauma_probability(self, mechanism: str) -> float:
        """Polytrauma probability for a mechanism."""
        return (
            self.data.get("mechanisms", {})
            .get(mechanism, {})
            .get("polytrauma_probability", 0.15)
        )

    # ── Treatment times (3-tier fallback) ───────────────────────

    def get_treatment_time(
        self,
        department: str,
        mechanism: Optional[str] = None,
        region: Optional[str] = None,
    ) -> tuple[float, float]:
        """Hierarchical lookup: (dept,mech.region) -> (dept,mech) -> (dept,default).

        Returns:
            (mean_minutes, std_minutes)
        """
        dept_times = self.data.get("treatment_times", {}).get(department, {})

        # Tier 1: mechanism.region
        if mechanism and region:
            key = f"{mechanism}.{region}"
            if key in dept_times:
                t = dept_times[key]
                return t["mean"], t["std"]

        # Tier 2: mechanism only
        if mechanism and mechanism in dept_times:
            t = dept_times[mechanism]
            return t["mean"], t["std"]

        # Tier 3: department default
        default = dept_times.get("default", {"mean": 60, "std": 20})
        return default["mean"], default["std"]

    # ── Deterioration ───────────────────────────────────────────

    def get_deterioration_rate(
        self,
        triage: str,
        mechanism: Optional[str] = None,
        with_pfc: bool = False,
    ) -> float:
        """Deterioration rate per 5-minute interval."""
        base = (
            self.data.get("deterioration", {})
            .get("base_rates_per_5min", {})
            .get(triage, {"without_pfc": 0.005, "with_pfc": 0.0015})
        )
        rate = base["with_pfc"] if with_pfc else base["without_pfc"]
        if mechanism:
            mod = (
                self.data.get("deterioration", {})
                .get("mechanism_modifiers", {})
                .get(mechanism, 1.0)
            )
            rate *= mod
        return rate

    # ── Vitals baselines ────────────────────────────────────────

    def get_vitals_baseline(self, triage: str) -> dict:
        """Vital signs baseline parameters for a triage category."""
        return self.data.get("vitals_baselines", {}).get(
            triage,
            {
                "gcs": {"mean": 14, "std": 1, "min": 3, "max": 15},
                "heart_rate": {"mean": 90, "std": 10, "min": 40, "max": 180},
                "systolic_bp": {"mean": 120, "std": 12, "min": 40, "max": 200},
                "respiratory_rate": {"mean": 16, "std": 4, "min": 8, "max": 40},
                "spo2": {"mean": 97, "std": 2, "min": 70, "max": 100},
            },
        )

    # ── Triage thresholds (for BT trees) ────────────────────────

    def get_triage_thresholds(self) -> dict:
        """Raw triage threshold config for BT tree builders."""
        return dict(self.data.get("triage_thresholds", {}))

    # ── PFC (Prolonged Field Care) — Phase 4 Iter 4 ──────────

    def get_max_pfc_hours(self, triage: str) -> float:
        """Max PFC hours for a triage category. PRD v7.0 §7.4."""
        return (
            self.data.get("pfc", {})
            .get("max_pfc_hours", {})
            .get(triage, 24.0)
        )

    def get_retriage_interval(self) -> float:
        """PFC re-triage interval in minutes."""
        return self.data.get("pfc", {}).get("retriage_interval_min", 30.0)

    def get_pfc_interventions(self) -> dict:
        """PFC intervention definitions."""
        return dict(self.data.get("pfc", {}).get("interventions", {}))

    def get_retriage_thresholds(self) -> dict:
        """Vitals thresholds that trigger re-triage during PFC."""
        return dict(self.data.get("pfc", {}).get("retriage_thresholds", {}))

    def get_pfc_deterioration_multiplier(self, cmt_available: bool = True) -> float:
        """PFC deterioration multiplier. 0.3 with CMT (70% reduction), 0.6 without (40%)."""
        key = "with_cmt" if cmt_available else "without_cmt"
        return (
            self.data.get("pfc", {})
            .get("pfc_deterioration_reduction", {})
            .get(key, 0.3)
        )
