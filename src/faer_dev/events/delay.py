"""Delay propagation analysis for FAER-M event store.

Phase 4 Iter 5. PRD section 7.5.

Traces delay chains through the evacuation chain (R3->R2->R1),
computes amplification factors, and detects cascade effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from faer_dev.events.queries import TemporalQuery
from faer_dev.events.store import EventStore


@dataclass
class DelayNode:
    """A single step in a delay chain."""

    facility_id: str = ""
    delay_min: float = 0.0
    event_type: str = ""
    sim_time: float = 0.0


@dataclass
class DelayChain:
    """A complete delay chain for one casualty."""

    casualty_id: str = ""
    total_delay_min: float = 0.0
    root_cause: str = ""
    chain: List[DelayNode] = field(default_factory=list)
    amplification_factor: float = 1.0  # downstream delay / root cause duration

    def to_text(self) -> str:
        """Human-readable summary of the delay chain."""
        lines = [
            f"Patient {self.casualty_id}: total delay {self.total_delay_min:.0f} min "
            f"(amplification {self.amplification_factor:.1f}x)",
            f"  Root cause: {self.root_cause}",
        ]
        for node in self.chain:
            lines.append(
                f"  {node.facility_id}: {node.delay_min:.0f} min "
                f"({node.event_type} at t={node.sim_time:.0f})"
            )
        return "\n".join(lines)


class DelayPropagator:
    """Trace delay chains through evacuation chain.

    Identifies patients who experienced significant delays and traces
    the propagation through facilities.

    Usage::

        propagator = DelayPropagator(engine.event_store)
        chains = propagator.trace_all_delays(threshold_min=60.0)
        for chain in chains:
            print(chain.to_text())
    """

    def __init__(self, store: EventStore) -> None:
        self._store = store
        self._query = TemporalQuery(store)

    def trace_delay(self, casualty_id: str) -> Optional[DelayChain]:
        """Trace delay chain for a single patient.

        Looks for HOLD_START, HOLD_RETRY, HOLD_TIMEOUT, PFC_START events
        to build the delay chain.
        """
        journey = self._query.patient_journey(casualty_id)
        if not journey:
            return None

        nodes: List[DelayNode] = []
        root_cause = ""
        root_delay = 0.0

        for event in journey:
            etype = event.event_type
            fid = event.facility_id or ""

            if etype == "HOLD_START":
                reason = getattr(event, "reason", "capacity")
                if not root_cause:
                    root_cause = f"hold_at_{fid}" if fid else reason
                nodes.append(DelayNode(
                    facility_id=fid,
                    delay_min=0.0,  # updated by retry/timeout
                    event_type=etype,
                    sim_time=event.sim_time,
                ))

            elif etype in ("HOLD_RETRY", "HOLD_TIMEOUT"):
                duration = getattr(event, "hold_duration_min", 0.0)
                if nodes and nodes[-1].facility_id == fid:
                    nodes[-1].delay_min = duration
                else:
                    nodes.append(DelayNode(
                        facility_id=fid,
                        delay_min=duration,
                        event_type=etype,
                        sim_time=event.sim_time,
                    ))

            elif etype == "PFC_START":
                # PFC_START marks a state transition within an existing hold
                # episode. Counting hold_duration_at_trigger again double-counts
                # the same elapsed hold interval.
                nodes.append(DelayNode(
                    facility_id=fid,
                    delay_min=0.0,
                    event_type=etype,
                    sim_time=event.sim_time,
                ))

        if not nodes:
            return None

        total_delay = sum(n.delay_min for n in nodes)
        root_delay = next((n.delay_min for n in nodes if n.delay_min > 0), 0.0)

        chain = DelayChain(
            casualty_id=casualty_id,
            total_delay_min=total_delay,
            root_cause=root_cause or "unknown",
            chain=nodes,
        )

        if root_delay > 0:
            chain.amplification_factor = total_delay / root_delay

        return chain

    def trace_all_delays(self, threshold_min: float = 60.0) -> List[DelayChain]:
        """Trace delay chains for all patients above threshold.

        Args:
            threshold_min: Minimum total delay to include in results.

        Returns:
            List of DelayChain, sorted by total_delay descending.
        """
        chains: List[DelayChain] = []

        for cid in self._query.patient_ids():
            chain = self.trace_delay(cid)
            if chain and chain.total_delay_min >= threshold_min:
                chains.append(chain)

        chains.sort(key=lambda c: c.total_delay_min, reverse=True)
        return chains

    def cascade_chains(self, threshold_min: float = 60.0) -> List[DelayChain]:
        """Find multi-facility cascade chains.

        CP4 gate #9: detect R3->R2->R1 cascades.
        Returns chains that span 2+ facilities.
        """
        all_chains = self.trace_all_delays(threshold_min)
        cascades: List[DelayChain] = []

        for chain in all_chains:
            unique_facilities = {n.facility_id for n in chain.chain if n.facility_id}
            if len(unique_facilities) >= 2:
                cascades.append(chain)

        return cascades
