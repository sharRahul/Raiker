from __future__ import annotations

from dataclasses import dataclass

GRAPH_RUNTIME_DISABLED_REASON = (
    "phase3_graph_codemap_runtime_indexing_disabled; dry_run_planning_only_until_policy_approval"
)


@dataclass(frozen=True)
class GraphGovernanceStatus:
    graph_indexing_enabled: bool = False
    planning_available: bool = True
    background_indexing_enabled: bool = False
    runtime_indexing_enabled: bool = False
    last_plan_summary: str = "none"
    disabled_reason: str = GRAPH_RUNTIME_DISABLED_REASON

    def to_dict(self) -> dict[str, object]:
        return {
            "graph_indexing_enabled": self.graph_indexing_enabled,
            "planning_available": self.planning_available,
            "background_indexing_enabled": self.background_indexing_enabled,
            "runtime_indexing_enabled": self.runtime_indexing_enabled,
            "last_plan_summary": self.last_plan_summary,
            "disabled_reason": self.disabled_reason,
        }


def graph_governance_status() -> dict[str, object]:
    return GraphGovernanceStatus().to_dict()
