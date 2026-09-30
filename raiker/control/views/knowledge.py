"""The brain graph: nodes, edges and the read that holds them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from raiker.contracts.views import View


@dataclass(frozen=True)
class BrainNodeView(View):
    node_id: str
    node_type: str
    label: str
    status: str
    detail: str | None = None
    progress_percent: int | None = None
    is_real: bool = True


@dataclass(frozen=True)
class BrainEdgeView(View):
    source: str
    target: str
    relationship: str
    is_active: bool = False
    relationship_id: str | None = None
    evidence_memory_id: str | None = None
    owner_can_reject: bool = False


@dataclass(frozen=True)
class BrainView:
    generated_at: str
    nodes: tuple[BrainNodeView, ...]
    edges: tuple[BrainEdgeView, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "illustrative_motion_notice": (
                "Animated pulses indicate visual activity only; every node and connection is stored runtime data."
            ),
        }
