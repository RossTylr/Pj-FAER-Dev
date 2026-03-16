"""Canonical test fixtures for Pj-FAER-Dev.

All test modules import fixtures from here. Ensures consistent
seed, topology, and casualty generation across all test runs.
"""
import pytest
import numpy as np

SEED = 42

# NB32 canonical 3-node contested topology
NB32_TOPOLOGY = [
    {
        "id": "POI", "role": "POI", "capacity": 50,
        "routes_to": [{"to": "R1", "time": 30.0, "contested": True, "denial_prob": 0.2}],
    },
    {
        "id": "R1", "role": "R1", "capacity": 4,
        "routes_to": [{"to": "R2", "time": 45.0}],
    },
    {
        "id": "R2", "role": "R2", "capacity": 8,
    },
]

NB32_CASUALTY_COUNT = 20
NB32_SIM_DURATION = 600.0


@pytest.fixture
def seed():
    """Canonical seed for deterministic tests (HC-2)."""
    return SEED


@pytest.fixture
def rng():
    """Seeded random generator."""
    return np.random.default_rng(SEED)


@pytest.fixture
def nb32_topology():
    """NB32 3-node contested chain topology."""
    return NB32_TOPOLOGY


@pytest.fixture
def nb32_config():
    """Full NB32 acceptance test configuration."""
    return {
        "topology": NB32_TOPOLOGY,
        "n_casualties": NB32_CASUALTY_COUNT,
        "duration": NB32_SIM_DURATION,
        "seed": SEED,
    }
