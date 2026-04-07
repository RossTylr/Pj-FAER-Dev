"""Treatment chain network topology using NetworkX.

Extracted from notebooks/06_tribrid_integration.ipynb (cell-8).
Manages the medical treatment chain graph with routing and congestion.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import networkx as nx

from faer_dev.core.enums import Role
from faer_dev.core.exceptions import NoPathError
from faer_dev.core.schemas import Casualty, Facility

logger = logging.getLogger(__name__)


class TreatmentNetwork:
    """Manages the treatment chain topology.

    NetworkX DiGraph wrapper with pathfinding, dynamic weight updates,
    and bypass logic for critical patients.
    """

    def __init__(self) -> None:
        self.graph: nx.DiGraph = nx.DiGraph()
        self.facilities: Dict[str, Facility] = {}

    def add_facility(self, facility: Facility) -> None:
        """Add a facility node to the network."""
        self.graph.add_node(
            facility.id,
            role=facility.role,
            beds=facility.beds,
            pos=facility.coordinates,
        )
        self.facilities[facility.id] = facility

    def add_route(
        self,
        from_id: str,
        to_id: str,
        base_time: float,
        transport: str = "ground",
    ) -> None:
        """Add a transport route between facilities."""
        self.graph.add_edge(
            from_id,
            to_id,
            base_time=base_time,
            weight=base_time,
            transport=transport,
        )

    def get_route(
        self, patient: Casualty, from_id: str, to_id: str
    ) -> List[str]:
        """Get optimal route, with bypass logic for critical patients."""
        try:
            if patient.bypass_role1:

                def weight_func(u: str, v: str, d: dict) -> float:
                    if self.graph.nodes[v].get("role") == Role.R1:
                        return float("inf")
                    return d.get("weight", 1)

                return nx.dijkstra_path(
                    self.graph, from_id, to_id, weight=weight_func
                )
            else:
                return nx.dijkstra_path(
                    self.graph, from_id, to_id, weight="weight"
                )
        except nx.NetworkXNoPath as exc:
            raise NoPathError(
                f"No path from {from_id} to {to_id}"
            ) from exc

    def get_travel_time(self, from_id: str, to_id: str) -> float:
        """Get base travel time between adjacent facilities.

        Returns base_time (not congestion-adjusted weight) so that actual
        transit duration is unaffected by dynamic routing weights.
        """
        if self.graph.has_edge(from_id, to_id):
            return self.graph[from_id][to_id]["base_time"]
        return float("inf")

    def get_edge(self, from_id: str, to_id: str) -> dict:
        """Get edge attributes between two facilities."""
        if self.graph.has_edge(from_id, to_id):
            return dict(self.graph[from_id][to_id])
        return {}

    def update_congestion(
        self, facility_id: str, congestion_factor: float
    ) -> None:
        """Update weights for routes into a congested facility."""
        for u, v in self.graph.in_edges(facility_id):
            base = self.graph[u][v]["base_time"]
            self.graph[u][v]["weight"] = base * (1 + congestion_factor)
