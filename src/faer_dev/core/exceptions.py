"""Custom exceptions for FAER-M.

Provides a hierarchy of exceptions for different error categories
to enable precise error handling throughout the system.
"""


class FAERMError(Exception):
    """Base exception for all FAER-M errors."""
    pass


class ConfigurationError(FAERMError):
    """Raised when configuration is invalid or missing.

    Examples:
        - Invalid YAML syntax
        - Missing required configuration fields
        - Invalid parameter values
    """
    pass


class SimulationError(FAERMError):
    """Raised when simulation encounters an error during execution.

    Examples:
        - Invalid state transition
        - Resource allocation failure
        - Process timeout
    """
    pass


class ValidationError(FAERMError):
    """Raised when data validation fails.

    Examples:
        - Invalid triage category
        - Patient data inconsistency
        - Schema validation failure
    """
    pass


class NetworkError(FAERMError):
    """Raised when network/routing operations fail.

    Examples:
        - No path exists between facilities
        - Invalid facility reference
        - Graph structure error
    """
    pass


class ResourceError(FAERMError):
    """Raised when resource operations fail.

    Examples:
        - Insufficient capacity
        - Invalid resource type
        - Resource not found
    """
    pass


class DecisionTreeError(FAERMError):
    """Raised when behavior tree execution fails.

    Examples:
        - Invalid tree structure
        - Missing blackboard data
        - Node execution failure
    """
    pass


class ResourceExhaustedError(SimulationError):
    """Raised when a required resource is not available."""
    pass


class InvalidTransitionError(SimulationError):
    """Raised when an invalid patient state transition is attempted."""
    pass


class NoPathError(NetworkError):
    """Raised when no valid path exists between two nodes."""
    pass
