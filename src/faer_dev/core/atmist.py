"""ATMIST handover reports and 9-Line MEDEVAC requests.

Military medical handover documentation:
- ATMIST: Age, Time, Mechanism, Injury, Signs, Treatment
- 9-Liner: Standard MEDEVAC request format
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from faer_dev.core.schemas import VitalSigns, TreatmentRecord
from faer_dev.core.vitals import VitalsGenerator


@dataclass
class ATMIST:
    """Complete ATMIST handover report. Cumulative across handovers."""

    casualty_id: str = ""
    age_category: str = "MILITARY_ADULT"
    nationality: str = "UK"
    zap_number: str = ""
    time_of_injury_minutes: float = 0.0
    time_of_handover_minutes: float = 0.0
    mechanism: str = ""
    mechanism_detail: str = ""
    primary_region: str = ""
    secondary_regions: List[str] = field(default_factory=list)
    severity_score: float = 0.5
    is_polytrauma: bool = False
    triage_category: str = ""
    injury_description: str = ""
    vitals: Optional[VitalSigns] = None
    treatments: List[TreatmentRecord] = field(default_factory=list)
    handover_from: str = ""
    handover_to: str = ""
    handover_number: int = 1
    mascal: bool = False
    dcs_performed: bool = False

    def to_handover_string(self) -> str:
        elapsed = self.time_of_handover_minutes - self.time_of_injury_minutes
        lines = [
            f"{'=' * 50}",
            f"ATMIST HANDOVER #{self.handover_number}",
            f"{self.handover_from} -> {self.handover_to}",
            f"{'=' * 50}",
            f"A - {self.age_category}, {self.nationality}, ID: {self.casualty_id}",
            (
                f"T - Injury t={self.time_of_injury_minutes:.0f}min, "
                f"handover t={self.time_of_handover_minutes:.0f}min "
                f"({elapsed:.0f}min elapsed)"
            ),
            f"M - {self.mechanism}"
            + (f" ({self.mechanism_detail})" if self.mechanism_detail else ""),
            f"I - [{self.triage_category}] {self.injury_description}",
        ]
        if self.vitals:
            lines.append(f"S - {self.vitals.to_string()}")
        lines.append(f"T - Treatment ({len(self.treatments)} actions):")
        for t in self.treatments:
            lines.append(f"     {t.to_string()}")
        if self.dcs_performed:
            lines.append("*** DCS PERFORMED - REQUIRES DEFINITIVE SURGERY ***")
        if self.mascal:
            lines.append("*** MASCAL CASUALTY ***")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "casualty_id": self.casualty_id,
            "age_category": self.age_category,
            "nationality": self.nationality,
            "time_of_injury": self.time_of_injury_minutes,
            "time_of_handover": self.time_of_handover_minutes,
            "mechanism": self.mechanism,
            "triage": self.triage_category,
            "primary_region": self.primary_region,
            "secondary_regions": self.secondary_regions,
            "severity": self.severity_score,
            "is_polytrauma": self.is_polytrauma,
            "vitals": self.vitals.to_dict() if self.vitals else None,
            "treatments": [
                {"time": t.time_minutes, "location": t.location, "action": t.action}
                for t in self.treatments
            ],
            "handover_from": self.handover_from,
            "handover_to": self.handover_to,
            "handover_number": self.handover_number,
            "dcs_performed": self.dcs_performed,
            "mascal": self.mascal,
        }


@dataclass
class NineLiner:
    """9-Line MEDEVAC Request."""

    line1_location: str = ""
    line2_callsign: str = ""
    line3_patients: str = ""
    line4_equipment: str = "N"
    line5_patients_type: str = "L"
    line6_security: str = "N"
    line7_marking: str = "C"
    line8_nationality: str = "A"
    line9_nbc: str = "N"

    def to_string(self) -> str:
        return "\n".join([
            f"LINE 1 - Location: {self.line1_location}",
            f"LINE 2 - Callsign: {self.line2_callsign}",
            f"LINE 3 - Patients: {self.line3_patients}",
            f"LINE 4 - Equipment: {self.line4_equipment}",
            f"LINE 5 - Type: {self.line5_patients_type}",
            f"LINE 6 - Security: {self.line6_security}",
            f"LINE 7 - Marking: {self.line7_marking}",
            f"LINE 8 - Nationality: {self.line8_nationality}",
            f"LINE 9 - NBC: {self.line9_nbc}",
        ])


# ── Generators ──────────────────────────────────────────────────

# Treatment event patterns -> description mapping
_TREATMENT_MAP = {
    "R1_DEPT=DCR": "DCR: IV access, haemostatic dressing, splinting",
    "R1_DEPT=WARD": "R1 Ward: observation, analgesia",
    "R2_ED_DONE": "ED: primary survey, stabilisation, bloods",
    "R2_DEPT=FST": "FST: surgical intervention",
    "R2_DEPT=ITU": "ITU: ventilation, vasopressors, monitoring",
    "R2_DEPT=WARD": "R2 Ward: recovery, observation",
    "DCS=True": "DCS: damage control surgery -- abbreviated procedure",
    "HELD_AT_R1": "Held at R1 -- awaiting R2 capacity",
}

# Skip patterns (no treatment description)
_SKIP_PATTERNS = {"R1_DCR_DONE", "R1_WARD_DONE", "TRIAGE"}


class ATMISTFormatter:
    """Generate ATMIST handover reports from simulation data."""

    def __init__(self, injury_data, vitals_gen: VitalsGenerator):
        self.data = injury_data
        self.vitals_gen = vitals_gen

    def _build_injury_description(self, casualty: dict) -> str:
        region = casualty.get("primary_region", "unknown region")
        mechanism = casualty.get("mechanism", "unknown mechanism")
        severity = casualty.get("severity_score", casualty.get("severity", 0.5))
        secondary = casualty.get("secondary_regions", [])

        if severity < 0.35:
            sev_text = "minor"
        elif severity < 0.65:
            sev_text = "moderate"
        elif severity < 0.9:
            sev_text = "severe"
        else:
            sev_text = "critical"

        desc = (
            f"{sev_text.title()} {mechanism.lower()} injury to "
            f"{region.lower().replace('_', ' ')}"
        )
        if secondary:
            sec_text = ", ".join(r.lower().replace("_", " ") for r in secondary[:2])
            desc += f" with secondary injuries to {sec_text}"
        if casualty.get("is_polytrauma", False):
            desc += " (polytrauma)"
        return desc

    def _extract_treatments(
        self, events: list[dict], up_to_time: float
    ) -> list[TreatmentRecord]:
        treatments = []
        for ev in events:
            if ev["time"] > up_to_time:
                break
            event_name = ev["event"]
            for pattern, description in _TREATMENT_MAP.items():
                if pattern in event_name:
                    treatments.append(TreatmentRecord(
                        time_minutes=ev["time"],
                        location=ev.get("loc", ""),
                        action=description,
                    ))
                    break
        return treatments

    def generate(
        self,
        casualty: dict,
        events: list[dict],
        handover_time: float,
        from_facility: str,
        to_facility: str,
        handover_number: int = 1,
    ) -> ATMIST:
        """Generate a single ATMIST handover report."""
        injury_time = casualty.get(
            "arrival_time", events[0]["time"] if events else 0
        )
        triage = casualty.get("triage", casualty.get("triage_category", "T2"))
        severity = casualty.get("severity_score", casualty.get("severity", 0.5))
        region = casualty.get("primary_region", "")
        mechanism = casualty.get("mechanism", "")

        initial_vitals = self.vitals_gen.generate_initial(triage, severity, region)

        had_definitive = any(
            "FST" in e.get("event", "") or "DCS" in e.get("event", "")
            for e in events
            if e["time"] <= handover_time
        )
        had_dcr = any(
            "DCR" in e.get("event", "")
            for e in events
            if e["time"] <= handover_time
        )

        elapsed = handover_time - injury_time
        if had_definitive:
            vitals = self.vitals_gen.post_treatment(initial_vitals, "FST")
        elif had_dcr:
            dcr_time = next(
                (e["time"] for e in events if "DCR" in e.get("event", "")),
                injury_time,
            )
            pre_dcr = self.vitals_gen.deteriorate(
                initial_vitals, dcr_time - injury_time, triage, mechanism,
            )
            post_dcr = self.vitals_gen.post_treatment(pre_dcr, "DCR")
            vitals = self.vitals_gen.deteriorate(
                post_dcr, handover_time - dcr_time, triage, mechanism,
                with_pfc=True,
            )
        else:
            vitals = self.vitals_gen.deteriorate(
                initial_vitals, elapsed, triage, mechanism,
            )

        return ATMIST(
            casualty_id=casualty.get("id", casualty.get("pid", "UNKNOWN")),
            time_of_injury_minutes=injury_time,
            time_of_handover_minutes=handover_time,
            mechanism=mechanism,
            mechanism_detail=casualty.get("mechanism_detail", ""),
            primary_region=region,
            secondary_regions=casualty.get("secondary_regions", []),
            severity_score=severity,
            is_polytrauma=casualty.get("is_polytrauma", False),
            triage_category=triage,
            injury_description=self._build_injury_description(casualty),
            vitals=vitals,
            treatments=self._extract_treatments(events, handover_time),
            handover_from=from_facility,
            handover_to=to_facility,
            handover_number=handover_number,
            mascal=casualty.get("is_mascal_casualty", False),
            dcs_performed=any(
                "DCS=True" in e.get("event", "")
                for e in events
                if e["time"] <= handover_time
            ),
        )


class NineLinerGenerator:
    """Generate 9-line MEDEVAC requests."""

    _PRECEDENCE = {
        "T1_SURGICAL": "A", "T1_MEDICAL": "A",
        "T2": "B", "T3": "C", "T4": "D",
    }

    def generate(
        self,
        casualty: dict,
        from_facility: str,
        to_facility: str,
        callsign: str = "DUSTOFF",
    ) -> NineLiner:
        triage = casualty.get("triage", "T2")
        precedence = self._PRECEDENCE.get(triage, "B")
        severity = casualty.get("severity_score", casualty.get("severity", 0.5))
        litter = "L" if severity > 0.5 or triage in ("T1_SURGICAL", "T1_MEDICAL") else "A"
        equipment = "D" if triage in ("T1_SURGICAL", "T1_MEDICAL") else "N"

        return NineLiner(
            line1_location=from_facility,
            line2_callsign=callsign,
            line3_patients=f"1x {precedence}",
            line4_equipment=equipment,
            line5_patients_type=litter,
            line6_security="N",
            line7_marking="C",
            line8_nationality="A",
            line9_nbc="N",
        )
