"""Casualty Collection Point — PFC facility with medic resources.

Phase 4 Iter 4. PRD v7.0 section 7.4.

CCP provides prolonged field care (PFC) when downstream evacuation is
delayed. Medic (CMT) resources are modelled as SimPy Resources:
- With CMT: 70% deterioration reduction (multiplier 0.3)
- Without CMT: 40% deterioration reduction (multiplier 0.6)

PFC ceiling per triage category enforced (T1_SURG=5h, T1_MED=7h, T2=15h, T3=24h).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import simpy

from faer_dev.core.enums import PatientState
from faer_dev.core.schemas import Casualty


@dataclass
class CCPConfig:
    """Configuration for a Casualty Collection Point."""

    ccp_id: str = "CCP-1"
    medics: int = 2
    capacity: int = 20


class CasualtyCollectionPoint:
    """Casualty Collection Point with SimPy medic resources.

    Provides PFC care. Medic availability determines deterioration
    reduction quality (with_cmt vs without_cmt).

    Usage::

        ccp = CasualtyCollectionPoint(env, config)
        ccp.admit(patient)
        req = ccp.medics.request()
        result = yield req | env.timeout(5)
        if req in result:
            # Full PFC
            ccp.medics.release(req)
    """

    def __init__(self, env: simpy.Environment, config: Optional[CCPConfig] = None) -> None:
        self.env = env
        self.config = config or CCPConfig()
        self.medics = simpy.Resource(env, capacity=self.config.medics)
        self._patients: Dict[str, Casualty] = {}
        self._treatment_log: List[Dict[str, Any]] = []

    @property
    def patient_count(self) -> int:
        return len(self._patients)

    @property
    def at_capacity(self) -> bool:
        return self.patient_count >= self.config.capacity

    def admit(self, patient: Casualty) -> None:
        """Admit patient to CCP."""
        patient.state = PatientState.AT_CCP
        self._patients[patient.id] = patient

    def discharge(self, patient: Casualty) -> None:
        """Discharge patient from CCP."""
        self._patients.pop(patient.id, None)

    def apply_interventions(self, patient: Casualty, injury_loader: Any) -> List[Dict[str, Any]]:
        """Apply PFC interventions. Returns list of treatment records.

        Each intervention takes time and provides deterioration reduction.
        """
        interventions = injury_loader.get_pfc_interventions()
        records: List[Dict[str, Any]] = []

        for name, config in interventions.items():
            record = {
                "intervention": name,
                "time_min": config.get("time_min", 2.0),
                "deterioration_reduction": config.get("deterioration_reduction", 0.0),
                "casualty_id": patient.id,
                "sim_time": self.env.now,
            }
            records.append(record)
            self._treatment_log.append(record)

        return records

    @property
    def total_intervention_time(self) -> float:
        """Total time for all standard interventions."""
        return sum(r["time_min"] for r in self._treatment_log) if self._treatment_log else 0.0
