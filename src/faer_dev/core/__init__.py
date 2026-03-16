"""Core domain models and enumerations for FAER-M."""

from faer_dev.core.enums import (
    AnatomicalRegion,
    InjuryMechanism,
    MASCALLevel,
    OperationalContext,
    PatientState,
    Role,
    ThreatLevel,
    TimeOfDay,
    TransportMode,
    TriageCategory,
    WeatherCondition,
)
from faer_dev.core.exceptions import (
    ConfigurationError,
    DecisionTreeError,
    FAERMError,
    InvalidTransitionError,
    NetworkError,
    NoPathError,
    ResourceError,
    ResourceExhaustedError,
    SimulationError,
    ValidationError,
)
from faer_dev.core.schemas import (
    Casualty,
    Facility,
    SimulationConfig,
    TransportRoute,
)

__all__ = [
    # Enums
    "AnatomicalRegion",
    "InjuryMechanism",
    "MASCALLevel",
    "OperationalContext",
    "PatientState",
    "Role",
    "ThreatLevel",
    "TimeOfDay",
    "TransportMode",
    "TriageCategory",
    "WeatherCondition",
    # Schemas
    "Casualty",
    "Facility",
    "SimulationConfig",
    "TransportRoute",
    # Exceptions
    "ConfigurationError",
    "DecisionTreeError",
    "FAERMError",
    "InvalidTransitionError",
    "NetworkError",
    "NoPathError",
    "ResourceError",
    "ResourceExhaustedError",
    "SimulationError",
    "ValidationError",
]
