"""Phase 4 event sourcing package.

Typed event models, pub/sub EventBus, append-only store, serialization, run logging.
"""

from faer_dev.events.models import (
    SimEvent,
    CasualtyCreated,
    TriageAssigned,
    OutcomeRecorded,
    TransitStarted,
    TransitCompleted,
    FacilityArrival,
    TreatmentStarted,
    TreatmentCompleted,
    DepartmentAssigned,
    QueueEntered,
    HoldStarted,
    HoldRetried,
    HoldTimedOut,
    HoldReleased,
    PFCStarted,
    PFCEnded,
    PFCCeilingExceeded,
    MASCALDeclared,
    MASCALCleared,
    DCSActivated,
    ATMISTGenerated,
    NineLinerGenerated,
    BTDecisionLogged,
    EVENT_REGISTRY,
    create_event,
)
from faer_dev.events.bus import EventBus
from faer_dev.events.store import EventStore, EventStoreProtocol
from faer_dev.events.serialization import EventSerializer
from faer_dev.events.run_logger import RunLogger, RunLogEntry
from faer_dev.events.replay import (
    ReplayEngine,
    SimulationStateSnapshot,
    FacilitySnapshot,
    PatientSnapshot,
)
from faer_dev.events.queries import TemporalQuery

# NOTE: EnsembleBuilder, EnsembleSnapshot, AggStat are NOT re-exported here
# because ensemble.py imports config.builder which imports simulation.engine
# which imports events — creating a circular import. Import directly:
#   from faer_dev.events.ensemble import EnsembleBuilder, EnsembleSnapshot, AggStat
