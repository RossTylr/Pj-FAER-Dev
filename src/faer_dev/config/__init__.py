"""Configuration management for FAER-M.

Provides YAML configuration loading, validation, preset scenarios,
and engine construction from presets.
"""

from faer_dev.config.builder import (
    build_engine_from_config,
    build_engine_from_dict,
    build_engine_from_preset,
    get_preset_raw,
    list_preset_names,
)
from faer_dev.config.loader import load_config, load_scenario
from faer_dev.config.presets import get_preset, list_presets

__all__ = [
    "build_engine_from_dict",
    "build_engine_from_config",
    "build_engine_from_preset",
    "get_preset_raw",
    "list_preset_names",
    "load_config",
    "load_scenario",
    "get_preset",
    "list_presets",
]
