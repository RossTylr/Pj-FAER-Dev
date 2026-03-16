"""Built-in scenario presets for FAER-M.

Provides pre-configured scenarios for common operational contexts.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from faer_dev.config.loader import load_config
from faer_dev.core.enums import OperationalContext
from faer_dev.core.schemas import SimulationConfig


# Path to default presets
PRESETS_DIR = Path(__file__).parent / "defaults"

# Preset registry
_PRESETS: Dict[str, SimulationConfig] = {}
logger = logging.getLogger(__name__)


def _load_presets() -> None:
    """Load all preset configurations from defaults directory."""
    if _PRESETS:
        return  # Already loaded

    if not PRESETS_DIR.exists():
        return

    for yaml_file in PRESETS_DIR.glob("*.yaml"):
        try:
            config = load_config(yaml_file)
            ctx = config.get("operational_context")
            if isinstance(ctx, str):
                config["operational_context"] = OperationalContext[ctx.strip().upper()]
            preset_name = yaml_file.stem
            _PRESETS[preset_name] = SimulationConfig(**config)
        except Exception as exc:
            logger.warning("Failed to parse preset %s: %s", yaml_file, exc)


def list_presets() -> List[str]:
    """List available preset scenario names.

    Returns:
        List of preset names.
    """
    _load_presets()
    return list(_PRESETS.keys())


def get_preset(name: str) -> Optional[SimulationConfig]:
    """Get a preset scenario configuration.

    Args:
        name: Name of the preset (e.g., 'coin', 'lsco').

    Returns:
        SimulationConfig for the preset, or None if not found.
    """
    _load_presets()
    return _PRESETS.get(name)
