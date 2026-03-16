"""Core enumerations for FAER-M.

These enums define the fundamental categories and states used throughout
the simulation system.
"""

from enum import Enum, auto


class TriageCategory(Enum):
    """Military triage categories based on NATO standards.

    Attributes:
        T1_SURGICAL: Immediate surgical intervention required
        T1_MEDICAL: Immediate medical intervention required
        T2: Urgent - can wait 4-6 hours
        T3: Minor - walking wounded
        T4: Expectant - comfort care only (MASCAL conditions)
    """
    T1_SURGICAL = auto()
    T1_MEDICAL = auto()
    T2 = auto()
    T3 = auto()
    T4 = auto()


class Role(Enum):
    """Medical facility roles/echelons in the treatment chain.

    NATO standard medical treatment facility classification.

    Attributes:
        POI: Point of Injury - where casualty occurs
        R1: Role 1 - Unit level medical (Battalion Aid Station)
        R2: Role 2 - Forward surgical capability
        R3: Role 3 - Theatre hospital (Combat Support Hospital)
        R4: Role 4 - Strategic/definitive care (CONUS)
    """
    POI = 0
    R1 = 1
    R2 = 2
    R3 = 3
    R4 = 4


class OperationalContext(Enum):
    """Operational context types affecting casualty generation and flow.

    Different operational contexts have different casualty rates,
    injury patterns, and resource availability.

    Attributes:
        COIN: Counter-Insurgency - low intensity, IED threats
        LSCO: Large-Scale Combat Operations - high intensity
        HADR: Humanitarian Assistance/Disaster Relief
        SPECOPS: Special Operations - small teams, remote locations
        PEACEKEEPING: Peace support operations
    """
    COIN = auto()
    LSCO = auto()
    HADR = auto()
    SPECOPS = auto()
    PEACEKEEPING = auto()


class PatientState(Enum):
    """Patient journey states through the treatment chain.

    Tracks the current location/status of a patient in the system.

    Attributes:
        AT_POI: At point of injury, awaiting evacuation
        IN_TRANSIT: Being transported between facilities
        WAITING: In queue at a facility
        IN_TREATMENT: Actively receiving care
        POST_OP: Post-operative recovery
        HOLDING: Treated but waiting for downstream capacity
        IN_ICU: In intensive care unit
        IN_HDU: In high dependency unit
        IN_WARD: In general ward
        DISCHARGED: Released from care
        RTD: Return to Duty
        STRATEVAC: Strategic evacuation (out of theatre)
        DECEASED: Fatal outcome
    """
    AT_POI = auto()
    IN_TRANSIT = auto()
    WAITING = auto()
    IN_TREATMENT = auto()
    POST_OP = auto()
    HOLDING = auto()
    IN_ICU = auto()
    IN_HDU = auto()
    IN_WARD = auto()
    IN_PFC = auto()
    AT_CCP = auto()
    AWAITING_EVACUATION = auto()
    DISCHARGED = auto()
    RTD = auto()
    STRATEVAC = auto()
    DECEASED = auto()


class TransportMode(Enum):
    """Evacuation transport modes.

    Different transport modes have different speeds, capacities,
    and weather/threat constraints.

    Attributes:
        GROUND: Ground ambulance
        ROTARY: Helicopter (MEDEVAC/CASEVAC)
        FIXED_WING: Fixed-wing aircraft (strategic evacuation)
    """
    GROUND = auto()
    ROTARY = auto()
    FIXED_WING = auto()


class ThreatLevel(Enum):
    """Operational threat levels affecting transport and operations.

    Attributes:
        GREEN: Low threat - normal operations
        AMBER: Elevated threat - increased caution
        RED: High threat - restricted movement
        BLACK: Extreme threat - emergency only
    """
    GREEN = auto()
    AMBER = auto()
    RED = auto()
    BLACK = auto()


class MASCALLevel(Enum):
    """Mass Casualty (MASCAL) activation levels.

    Attributes:
        NORMAL: Normal operations
        LEVEL_1: Minor MASCAL - increased capacity needed
        LEVEL_2: Major MASCAL - significant resource strain
        LEVEL_3: Catastrophic - overwhelmed, expectant protocols
    """
    NORMAL = auto()
    LEVEL_1 = auto()
    LEVEL_2 = auto()
    LEVEL_3 = auto()


class InjuryMechanism(Enum):
    """Mechanism of injury classification."""
    BLAST = auto()
    GSW = auto()  # Gunshot wound
    PENETRATING = auto()
    BLUNT = auto()
    BURN = auto()
    ENVIRONMENTAL = auto()
    MEDICAL = auto()  # Disease and non-battle injury (DNBI)


class AnatomicalRegion(Enum):
    """Body regions for injury classification (AIS-based)."""
    HEAD = auto()
    FACE = auto()
    NECK = auto()
    THORAX = auto()
    ABDOMEN = auto()
    SPINE = auto()
    UPPER_EXTREMITY = auto()
    LOWER_EXTREMITY = auto()
    PELVIS = auto()
    EXTERNAL = auto()  # Skin/soft tissue


class TimeOfDay(Enum):
    """Time of day affecting operations and transport."""
    DAY = auto()
    NIGHT = auto()
    DAWN_DUSK = auto()


class WeatherCondition(Enum):
    """Weather conditions affecting air operations."""
    VMC = auto()   # Visual Meteorological Conditions
    IMC = auto()   # Instrument Meteorological Conditions
    GROUNDED = auto()  # No-fly conditions
