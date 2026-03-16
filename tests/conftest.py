"""Pytest configuration and shared fixtures for FAER-M tests.

Test layout:
  tests/unit/          — Phase 1/2 unit tests
  tests/integration/   — Phase 1 integration tests
  tests/validation/    — Analytical validation (Erlang-C)
  tests/*.py           — Phase 3/4 tests (flat, discovered by pytest)
"""

import pytest
import numpy as np
from pathlib import Path

import py_trees

from faer_dev.core.enums import InjuryMechanism, TriageCategory, Role, PatientState
from faer_dev.core.schemas import Casualty, Facility, SimulationConfig


# ============================================================================
# BT Global Blackboard Cleanup (prevents cross-test pollution)
# ============================================================================

@pytest.fixture(autouse=True)
def _bt_blackboard_cleanup():
    """Reset py-trees global blackboard before and after each test."""
    py_trees.blackboard.Blackboard.storage = {}
    py_trees.blackboard.Blackboard.metadata = {}
    py_trees.blackboard.Blackboard.enable_activity_stream(False)
    yield
    py_trees.blackboard.Blackboard.storage = {}
    py_trees.blackboard.Blackboard.metadata = {}
    py_trees.blackboard.Blackboard.enable_activity_stream(False)


# ============================================================================
# Path Fixtures
# ============================================================================

@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def test_data_dir(project_root: Path) -> Path:
    """Return the test data directory."""
    return project_root / "tests" / "data"


@pytest.fixture
def notebooks_dir(project_root: Path) -> Path:
    """Return the notebooks directory."""
    return project_root / "notebooks"


# ============================================================================
# Random Seed Fixtures
# ============================================================================

@pytest.fixture
def fixed_seed():
    """Set numpy random seed for reproducibility."""
    np.random.seed(42)
    yield 42
    # Reset after test
    np.random.seed(None)


# ============================================================================
# Domain Object Fixtures
# ============================================================================

@pytest.fixture
def sample_casualty() -> Casualty:
    """Create a sample casualty for testing."""
    return Casualty(
        id="TEST-001",
        triage=TriageCategory.T2,
        initial_triage=TriageCategory.T2,
        created_at=0.0,
        state_changed_at=0.0,
    )


@pytest.fixture
def t1_surgical_casualty() -> Casualty:
    """Create a T1 Surgical casualty for testing."""
    return Casualty(
        id="TEST-T1S",
        triage=TriageCategory.T1_SURGICAL,
        initial_triage=TriageCategory.T1_SURGICAL,
        mechanism=InjuryMechanism.PENETRATING,
        created_at=0.0,
        state_changed_at=0.0,
        requires_dcs=True,
        bypass_role1=True,
    )


@pytest.fixture
def sample_facility() -> Facility:
    """Create a sample Role 2 facility for testing."""
    return Facility(
        id="R2-TEST",
        name="Test FST",
        role=Role.R2,
        beds=8,
        or_tables=2,
        has_surgery=True,
        has_blood=True,
    )


@pytest.fixture
def role1_facility() -> Facility:
    """Create a Role 1 facility for testing."""
    return Facility(
        id="R1-TEST",
        name="Test BAS",
        role=Role.R1,
        beds=4,
    )


@pytest.fixture
def sample_config() -> SimulationConfig:
    """Create a sample simulation configuration for testing."""
    return SimulationConfig(
        name="test_scenario",
        description="Test scenario for unit tests",
        duration_hours=8.0,
        warmup_hours=1.0,
        arrival_rate_per_hour=2.0,
        seed=42,
    )


# ============================================================================
# Collection Fixtures
# ============================================================================

@pytest.fixture
def triage_categories() -> list[TriageCategory]:
    """Return all triage categories."""
    return list(TriageCategory)


@pytest.fixture
def facility_roles() -> list[Role]:
    """Return all facility roles."""
    return list(Role)


# ============================================================================
# Parametrize Helpers
# ============================================================================

def pytest_generate_tests(metafunc):
    """Generate parameterized tests for common patterns."""
    # Parameterize over all triage categories
    if "triage_category" in metafunc.fixturenames:
        metafunc.parametrize("triage_category", list(TriageCategory))

    # Parameterize over all roles
    if "facility_role" in metafunc.fixturenames:
        metafunc.parametrize("facility_role", list(Role))
