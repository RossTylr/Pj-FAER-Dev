"""FAER-M: Forecast of Accident and Emergency Resources - Military.

A high-fidelity discrete-event simulation of the military medical treatment chain
using a Balanced Tribrid Architecture:
- SimPy: Discrete-event queuing (The Muscles)
- NetworkX: Graph-based routing (The Skeleton)
- Behavior Trees: Clinical decision logic (The Brain)
"""

__version__ = "0.1.0"
__author__ = "FAER-M Team"

from faer_dev.core.enums import (
    TriageCategory,
    Role,
    OperationalContext,
    PatientState,
    TransportMode,
)

__all__ = [
    "TriageCategory",
    "Role",
    "OperationalContext",
    "PatientState",
    "TransportMode",
    "__version__",
]
