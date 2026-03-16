"""Build a PolyhybridEngine from YAML preset or raw dict.

This is the glue between YAML configuration and the simulation engine.
"""

from __future__ import annotations

from copy import deepcopy
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from faer_dev.config.loader import load_config
from faer_dev.core.enums import OperationalContext, Role
from faer_dev.core.exceptions import ConfigurationError
from faer_dev.core.schemas import Facility
from faer_dev.decisions.mode import SimulationToggles
from faer_dev.simulation.arrivals import ArrivalConfig, get_arrival_config
from faer_dev.simulation.engine import PolyhybridEngine

logger = logging.getLogger(__name__)

# Path to default presets
PRESETS_DIR = Path(__file__).parent / "defaults"

# Map YAML role strings/ints to Role enum
_ROLE_MAP = {
    0: Role.POI, 1: Role.R1, 2: Role.R2, 3: Role.R3, 4: Role.R4,
    "POI": Role.POI, "R1": Role.R1, "R2": Role.R2, "R3": Role.R3, "R4": Role.R4,
}


def _parse_role(value: Any) -> Role:
    """Convert YAML role value (int or string) to Role enum."""
    if isinstance(value, Role):
        return value
    mapped = _ROLE_MAP.get(value)
    if mapped is not None:
        return mapped
    raise ValueError(f"Unknown role: {value!r}")


def _parse_context(value: Any) -> OperationalContext:
    """Convert context/scenario value to OperationalContext enum."""
    if isinstance(value, OperationalContext):
        return value
    if value is None:
        return OperationalContext.COIN
    if isinstance(value, str):
        key = value.strip().upper()
        try:
            return OperationalContext[key]
        except KeyError as exc:
            raise ConfigurationError(
                f"Unknown operational context: {value!r}"
            ) from exc
    raise ConfigurationError(f"Invalid operational context value: {value!r}")


def _first_non_none(*values: Any) -> Any:
    """Return the first value that is not None."""
    for value in values:
        if value is not None:
            return value
    return None


def _parse_bool(value: Any) -> bool:
    """Parse booleans from config values, including common strings."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", ""}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return bool(value)


def build_engine_from_dict(
    scenario: Dict[str, Any],
    toggles: Optional[SimulationToggles] = None,
    seed: Optional[int] = None,
) -> PolyhybridEngine:
    """Build a PolyhybridEngine from a raw scenario dictionary.

    Args:
        scenario: Parsed YAML dict with facilities, edges, arrivals, etc.
        toggles: Optional SimulationToggles override. If None, uses defaults.
        seed: Optional seed override. If None, uses scenario["seed"] or 42.

    Returns:
        Configured PolyhybridEngine ready to run.
    """
    context = _parse_context(
        _first_non_none(
            scenario.get("operational_context"),
            scenario.get("context"),
            scenario.get("scenario"),
        )
    )

    arrivals_dict = scenario.get("arrivals", {}) or {}
    arrival_defaults = get_arrival_config(context)
    rate = _first_non_none(
        arrivals_dict.get("base_rate_per_hour"),
        arrivals_dict.get("base_rate"),
        arrival_defaults.base_rate_per_hour,
    )
    mascal_enabled = _first_non_none(
        arrivals_dict.get("enable_mascal"),
        arrivals_dict.get("mascal_enabled"),
        arrival_defaults.mascal_enabled,
    )
    mascal_rate = _first_non_none(
        arrivals_dict.get("mascal_rate_per_hour"),
        arrival_defaults.mascal_rate_per_hour,
    )
    mascal_size_mean = _first_non_none(
        arrivals_dict.get("mascal_size_mean"),
        arrivals_dict.get("mascal_cluster_mean"),
        arrival_defaults.mascal_size_mean,
    )
    mascal_size_std = _first_non_none(
        arrivals_dict.get("mascal_size_std"),
        arrival_defaults.mascal_size_std,
    )
    mascal_size_min = _first_non_none(
        arrivals_dict.get("mascal_size_min"),
        arrival_defaults.mascal_size_min,
    )
    mascal_size_max = _first_non_none(
        arrivals_dict.get("mascal_size_max"),
        arrival_defaults.mascal_size_max,
    )
    mascal_duration = _first_non_none(
        arrivals_dict.get("mascal_duration_minutes"),
        arrivals_dict.get("mascal_cluster_spread_minutes"),
        arrival_defaults.mascal_duration_minutes,
    )
    resolved_seed = seed if seed is not None else scenario.get("seed", 42)
    arrival_config = ArrivalConfig(
        base_rate_per_hour=rate,
        mascal_enabled=_parse_bool(mascal_enabled),
        mascal_rate_per_hour=mascal_rate,
        mascal_size_mean=mascal_size_mean,
        mascal_size_std=mascal_size_std,
        mascal_size_min=mascal_size_min,
        mascal_size_max=mascal_size_max,
        mascal_duration_minutes=mascal_duration,
    )
    engine = PolyhybridEngine(
        context=context,
        arrival_config=arrival_config,
        seed=resolved_seed,
        config=deepcopy(scenario),
        toggles=toggles,
    )

    edges = scenario.get("edges", [])
    facilities = scenario.get("facilities", [])
    facility_ids = {f["id"] for f in facilities}
    poi_sources: set[str] = set()
    for edge in edges:
        from_id = edge.get("from")
        to_id = edge.get("to")
        if not from_id or not to_id:
            raise ConfigurationError(
                f"Invalid edge definition: {edge!r}. 'from' and 'to' are required."
            )
        if from_id not in facility_ids:
            if str(from_id).upper().startswith("POI"):
                poi_sources.add(str(from_id))
            else:
                raise ConfigurationError(
                    f"Edge references unknown source facility '{from_id}'."
                )
        if to_id not in facility_ids:
            raise ConfigurationError(
                f"Edge references unknown destination facility '{to_id}'."
            )

    for poi_id in sorted(poi_sources):
        poi = Facility(id=poi_id, name="Point of Injury", role=Role.POI, beds=0)
        engine.add_facility(poi)

    for fac_config in facilities:
        coords = fac_config.get("coordinates", fac_config.get("position", [0, 0]))
        beds = fac_config.get("beds")
        if beds is None:
            beds = 4
        facility = Facility(
            id=fac_config["id"],
            name=fac_config.get("name", fac_config["id"]),
            role=_parse_role(fac_config["role"]),
            beds=beds,
            coordinates=tuple(coords),
            has_surgery=_parse_bool(fac_config.get("has_surgery", False)),
            has_blood=_parse_bool(fac_config.get("has_blood", False)),
            has_imaging=_parse_bool(fac_config.get("has_imaging", False)),
        )
        engine.add_facility(facility)

    for edge in edges:
        travel_time = edge.get("travel_time_minutes")
        if travel_time is None:
            travel_time = edge.get("time_minutes")
        if travel_time is None:
            travel_time = 30
        transport = edge.get("transport")
        if transport is None:
            transport = edge.get("mode")
        if transport is None:
            transport = "ground"
        engine.add_route(edge["from"], edge["to"], travel_time, transport)

    return engine


def build_engine_from_config(
    scenario: Dict[str, Any],
    toggles: Optional[SimulationToggles] = None,
    seed: Optional[int] = None,
) -> PolyhybridEngine:
    """Backward-compatible alias for build_engine_from_dict()."""
    return build_engine_from_dict(scenario, toggles=toggles, seed=seed)


def build_engine_from_preset(
    name: str,
    toggles: Optional[SimulationToggles] = None,
    seed: Optional[int] = None,
) -> PolyhybridEngine:
    """Build a PolyhybridEngine from a named preset.

    Loads the raw YAML (not SimulationConfig, which drops facilities/edges)
    and constructs a fully wired engine.

    Args:
        name: Preset name (e.g. 'coin', 'lsco', 'hadr', 'specops').
        toggles: Optional SimulationToggles override. If None, uses defaults.
        seed: Optional seed override. If None, uses preset YAML seed or 42.

    Returns:
        Configured PolyhybridEngine ready to run.

    Raises:
        FileNotFoundError: If preset YAML doesn't exist.
    """
    yaml_path = PRESETS_DIR / f"{name}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Preset not found: {yaml_path}")

    raw = load_config(yaml_path)
    return build_engine_from_dict(raw, toggles=toggles, seed=seed)


def get_preset_raw(name: str) -> Dict[str, Any]:
    """Load a preset as a raw dict (for dashboard editing).

    Args:
        name: Preset name.

    Returns:
        Raw YAML dict with all fields including facilities and edges.
    """
    yaml_path = PRESETS_DIR / f"{name}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Preset not found: {yaml_path}")
    return load_config(yaml_path)


def list_preset_names() -> list[str]:
    """List available preset names."""
    if not PRESETS_DIR.exists():
        return []
    return sorted(p.stem for p in PRESETS_DIR.glob("*.yaml"))
