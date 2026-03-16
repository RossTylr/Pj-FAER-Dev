"""YAML configuration loader for FAER-M.

Provides functions to load and validate simulation configurations
from YAML files.
"""

from pathlib import Path
from typing import Any, Dict, Union

import yaml

from faer_dev.core.exceptions import ConfigurationError
from faer_dev.core.schemas import SimulationConfig


def load_config(path: Union[str, Path]) -> Dict[str, Any]:
    """Load raw configuration from a YAML file.

    Args:
        path: Path to the YAML configuration file.

    Returns:
        Dictionary containing the parsed configuration.

    Raises:
        ConfigurationError: If the file cannot be read or parsed.
    """
    path = Path(path)

    if not path.exists():
        raise ConfigurationError(f"Configuration file not found: {path}")

    try:
        with open(path, "r") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in {path}: {e}")

    if config is None:
        raise ConfigurationError(f"Empty configuration file: {path}")

    return config


def load_scenario(path: Union[str, Path]) -> SimulationConfig:
    """Load and validate a simulation scenario from YAML.

    Args:
        path: Path to the scenario YAML file.

    Returns:
        Validated SimulationConfig object.

    Raises:
        ConfigurationError: If validation fails.
    """
    raw_config = load_config(path)

    try:
        return SimulationConfig(**raw_config)
    except Exception as e:
        raise ConfigurationError(f"Invalid scenario configuration: {e}")
