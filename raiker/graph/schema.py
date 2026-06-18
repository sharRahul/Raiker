from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GraphNodePlan:
    node_type: str
    external_id: str
    label: str
    source: str


@dataclass(frozen=True)
class GraphEdgePlan:
    source_external_id: str
    target_external_id: str
    relationship: str
    source: str


def plan_codemap_record(
    nodes: list[GraphNodePlan], edges: list[GraphEdgePlan]
) -> dict[str, object]:
    known = {node.external_id for node in nodes}
    dangling = [
        edge
        for edge in edges
        if edge.source_external_id not in known or edge.target_external_id not in known
    ]
    return {
        "can_index": False,
        "reason": "phase3_graph_codemap_indexing_disabled_until_policy_complete",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "dangling_edge_count": len(dangling),
    }
