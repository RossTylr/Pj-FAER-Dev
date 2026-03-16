"""BTObserver — observes BT ticks and records decision metrics.

Provides per-node activation rates, timing, and a structured
decision log for dashboard visualisation and regression analysis.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import py_trees
from py_trees import common


@dataclass
class NodeMetrics:
    """Per-node tick statistics."""

    name: str
    success_count: int = 0
    failure_count: int = 0
    running_count: int = 0
    total_ticks: int = 0
    total_duration_ms: float = 0.0

    @property
    def activation_rate(self) -> float:
        """Fraction of ticks where this node returned SUCCESS."""
        return self.success_count / self.total_ticks if self.total_ticks > 0 else 0.0

    @property
    def mean_tick_ms(self) -> float:
        return self.total_duration_ms / self.total_ticks if self.total_ticks > 0 else 0.0


@dataclass
class DecisionRecord:
    """Single patient decision record for logging/replay."""

    patient_id: str
    tree_name: str
    decision: str
    node_path: list[str] = field(default_factory=list)
    bb_snapshot: dict = field(default_factory=dict)
    timestamp: float = 0.0


class BTObserver:
    """Observes py-trees BT ticks and records metrics + decisions.

    Usage::

        observer = BTObserver("triage")
        # Before tick:
        observer.pre_tick(tree)
        tree.tick_once()
        observer.post_tick(tree)
        # Record decision:
        observer.record_decision("CAS-001", "T1_SURGICAL", bb.snapshot())
    """

    def __init__(self, tree_name: str):
        self.tree_name = tree_name
        self._metrics: dict[str, NodeMetrics] = {}
        self._decisions: list[DecisionRecord] = []
        self._tick_start: float = 0.0
        self._tick_count: int = 0

    def pre_tick(self, tree) -> None:
        """Call before tree.tick_once()."""
        self._tick_start = time.perf_counter()

    def post_tick(self, tree) -> None:
        """Call after tree.tick_once(). Walks tree to update metrics."""
        elapsed_ms = (time.perf_counter() - self._tick_start) * 1000.0
        self._tick_count += 1
        self._observe_tree(tree.root, elapsed_ms)

    def _observe_tree(self, node, elapsed_ms: float) -> None:
        """Recursively walk the tree and update node metrics."""
        name = node.name
        if name not in self._metrics:
            self._metrics[name] = NodeMetrics(name=name)
        m = self._metrics[name]
        m.total_ticks += 1
        m.total_duration_ms += elapsed_ms / max(1, len(self._metrics))

        status = node.status
        if status == common.Status.SUCCESS:
            m.success_count += 1
        elif status == common.Status.FAILURE:
            m.failure_count += 1
        elif status == common.Status.RUNNING:
            m.running_count += 1

        if hasattr(node, "children"):
            for child in node.children:
                self._observe_tree(child, elapsed_ms)

    def record_decision(
        self,
        patient_id: str,
        decision: str,
        bb_snapshot: dict,
        sim_time: float = 0.0,
    ) -> DecisionRecord:
        """Record a completed decision for a patient."""
        record = DecisionRecord(
            patient_id=patient_id,
            tree_name=self.tree_name,
            decision=decision,
            node_path=list(bb_snapshot.get("decision_path", [])),
            bb_snapshot=bb_snapshot,
            timestamp=sim_time,
        )
        self._decisions.append(record)
        return record

    def get_metrics(self) -> dict[str, NodeMetrics]:
        """Return per-node metrics dict."""
        return dict(self._metrics)

    def get_node_statuses(self) -> dict[str, str]:
        """Return {node_name: last_status_string} for dashboard display."""
        return {
            name: _status_label(m) for name, m in self._metrics.items()
        }

    @property
    def decisions(self) -> list[DecisionRecord]:
        """All recorded decisions."""
        return list(self._decisions)

    @property
    def tick_count(self) -> int:
        return self._tick_count

    def reset(self) -> None:
        """Clear all metrics and decisions."""
        self._metrics.clear()
        self._decisions.clear()
        self._tick_count = 0

    def reset_tick_counts(self) -> None:
        """Zero out counts but keep node entries."""
        for m in self._metrics.values():
            m.success_count = 0
            m.failure_count = 0
            m.running_count = 0
            m.total_ticks = 0
            m.total_duration_ms = 0.0
        self._tick_count = 0


def _status_label(m: NodeMetrics) -> str:
    """Human-readable status from latest counts."""
    if m.total_ticks == 0:
        return "IDLE"
    rate = m.activation_rate
    if rate > 0.8:
        return "[RED] HIGH"
    if rate > 0.5:
        return "[AMB] MODERATE"
    if rate > 0.2:
        return "[GRN] LOW"
    return "[LOW] RARE"
