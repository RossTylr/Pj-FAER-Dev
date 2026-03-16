"""Pydantic schemas for FAER-M domain models.

These schemas define the core data structures used throughout the simulation,
providing validation, serialization, and type safety.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, computed_field, field_validator

from faer_dev.core.enums import (
    AnatomicalRegion,
    InjuryMechanism,
    TriageCategory,
    Role,
    PatientState,
    TransportMode,
    OperationalContext,
    ThreatLevel,
)


# ── Value objects (dataclasses, not Pydantic) ───────────────────


@dataclass
class VitalSigns:
    """Vital signs snapshot at a point in time."""

    gcs: int = 15
    heart_rate: int = 80
    systolic_bp: int = 120
    respiratory_rate: int = 16
    spo2: int = 98
    avpu: str = "A"

    def to_string(self) -> str:
        return (
            f"GCS {self.gcs}, HR {self.heart_rate}, BP {self.systolic_bp}, "
            f"RR {self.respiratory_rate}, SpO2 {self.spo2}%, AVPU={self.avpu}"
        )

    def to_dict(self) -> dict:
        return {
            "gcs": self.gcs,
            "heart_rate": self.heart_rate,
            "systolic_bp": self.systolic_bp,
            "respiratory_rate": self.respiratory_rate,
            "spo2": self.spo2,
            "avpu": self.avpu,
        }


@dataclass
class TreatmentRecord:
    """Single treatment action at a facility."""

    time_minutes: float = 0.0
    location: str = ""
    action: str = ""
    provider: str = ""
    notes: str = ""

    def to_string(self) -> str:
        return f"[t={self.time_minutes:.0f}min @ {self.location}] {self.action}"


class Casualty(BaseModel):
    """A patient/casualty in the simulation.

    Tracks all attributes of a casualty from point of injury
    through the treatment chain to final disposition.
    """

    id: str = Field(..., description="Unique casualty identifier")

    # Clinical attributes
    triage: TriageCategory = Field(..., description="Current triage category")
    initial_triage: TriageCategory = Field(..., description="Triage at POI")
    mechanism: Optional[InjuryMechanism] = Field(default=None, description="Mechanism of injury")
    primary_region: Optional[AnatomicalRegion] = Field(default=None, description="Primary anatomical region")
    secondary_regions: List[AnatomicalRegion] = Field(default_factory=list, description="Secondary injury regions")
    severity_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Severity score 0-1")
    treatment_time_modifier: float = Field(default=1.0, ge=0.1, le=5.0, description="Multiplier for treatment duration")

    # MASCAL tracking
    is_mascal_casualty: bool = Field(default=False, description="Generated during a MASCAL event")
    mascal_event_id: Optional[int] = Field(default=None, description="MASCAL event identifier")

    # Arrival / priority
    arrival_time: float = Field(default=0.0, description="Simulation time of arrival at first facility")
    priority_value: int = Field(default=500, description="Scheduling priority (lower = higher priority)")

    # State tracking
    state: PatientState = Field(default=PatientState.AT_POI)
    current_facility: Optional[str] = Field(default=None, description="Current facility ID")
    destination_facility: Optional[str] = Field(default=None, description="Next facility ID")

    # Timeline
    created_at: float = Field(..., description="Simulation time of injury")
    state_changed_at: float = Field(..., description="Last state change time")
    treatment_started_at: Optional[float] = Field(default=None)

    # Journey tracking
    facilities_visited: List[str] = Field(default_factory=list)
    total_wait_time: float = Field(default=0.0)
    total_treatment_time: float = Field(default=0.0)
    total_transit_time: float = Field(default=0.0)

    # Clinical decisions
    bypass_role1: bool = Field(default=False, description="Skip R1 for critical cases")
    requires_dcs: bool = Field(default=False, description="Needs damage control surgery")
    requires_blood: bool = Field(default=False, description="Requires blood products")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Phase 3 optional fields
    vitals: Optional[Any] = Field(default=None, description="Current VitalSigns snapshot")
    treatment_history: List[Any] = Field(default_factory=list, description="List of TreatmentRecord")
    age_category: str = Field(default="MILITARY_ADULT", description="Age category for ATMIST")
    sex: str = Field(default="M", description="Sex for clinical modelling")
    origin_position: Optional[tuple] = Field(default=None, description="(lat, lon) from VOP PAR unit")

    model_config = {"use_enum_values": False}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def n_injury_regions(self) -> int:
        """Total number of injured regions (primary + secondary)."""
        count = len(self.secondary_regions)
        if self.primary_region is not None:
            count += 1
        return count

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_polytrauma(self) -> bool:
        """Patient has injuries in 2+ anatomical regions."""
        return self.n_injury_regions >= 2


class Facility(BaseModel):
    """A medical treatment facility in the treatment chain."""

    id: str = Field(..., description="Unique facility identifier")
    name: str = Field(..., description="Human-readable name")
    role: Role = Field(..., description="Facility role/echelon")

    # Capacity
    beds: int = Field(default=4, ge=0, description="Total treatment beds")
    or_tables: int = Field(default=0, ge=0, description="Operating tables")
    icu_beds: int = Field(default=0, ge=0, description="ICU beds")
    ventilators: int = Field(default=0, ge=0, description="Ventilators")

    # Location
    coordinates: tuple[float, float] = Field(default=(0.0, 0.0))

    # Capabilities
    has_surgery: bool = Field(default=False)
    has_blood: bool = Field(default=False)
    has_imaging: bool = Field(default=False)
    has_lab: bool = Field(default=False)

    # Status
    is_operational: bool = Field(default=True)
    current_occupancy: int = Field(default=0, ge=0)

    model_config = {"use_enum_values": False}

    @property
    def utilization(self) -> float:
        """Calculate current bed utilization."""
        if self.beds == 0:
            return 0.0
        return self.current_occupancy / self.beds


class TransportRoute(BaseModel):
    """A transport route between two facilities."""

    from_facility: str = Field(..., description="Source facility ID")
    to_facility: str = Field(..., description="Destination facility ID")

    # Transport characteristics
    mode: TransportMode = Field(default=TransportMode.GROUND)
    base_time_minutes: float = Field(..., ge=0, description="Base transit time")
    distance_km: float = Field(default=0.0, ge=0)

    # Modifiers
    threat_multiplier: float = Field(default=1.0, ge=0)
    terrain_multiplier: float = Field(default=1.0, ge=0)

    # Constraints
    min_ceiling_feet: int = Field(default=0, ge=0, description="Min weather ceiling for rotary")
    max_threat_level: ThreatLevel = Field(default=ThreatLevel.RED)

    model_config = {"use_enum_values": False}

    @property
    def effective_time(self) -> float:
        """Calculate effective transit time with modifiers."""
        return self.base_time_minutes * self.threat_multiplier * self.terrain_multiplier


class SimulationConfig(BaseModel):
    """Configuration for a simulation run."""

    name: str = Field(..., description="Scenario name")
    description: str = Field(default="", description="Scenario description")

    # Context
    operational_context: OperationalContext = Field(default=OperationalContext.COIN)

    # Duration
    duration_hours: float = Field(default=24.0, ge=0)
    warmup_hours: float = Field(default=2.0, ge=0)

    # Arrivals
    arrival_rate_per_hour: float = Field(default=2.0, ge=0)
    enable_mascal: bool = Field(default=False)
    mascal_rate_per_hour: float = Field(default=0.1, ge=0)
    mascal_cluster_size: int = Field(default=10, ge=1)

    # Triage distribution
    triage_distribution: Dict[str, float] = Field(
        default_factory=lambda: {
            "T1_SURGICAL": 0.10,
            "T1_MEDICAL": 0.10,
            "T2": 0.25,
            "T3": 0.45,
            "T4": 0.10,
        }
    )

    # Random seed
    seed: int = Field(default=42)

    model_config = {"use_enum_values": False}

    @field_validator("triage_distribution")
    @classmethod
    def validate_distribution(cls, v: Dict[str, float]) -> Dict[str, float]:
        """Ensure triage distribution sums to 1.0."""
        total = sum(v.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Triage distribution must sum to 1.0, got {total}")
        return v
