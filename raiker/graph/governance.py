from __future__ import annotations

from dataclasses import dataclass

from raiker.contracts.views import View

GRAPH_RUNTIME_DISABLED_REASON = (
    "phase3_graph_codemap_runtime_indexing_disabled; dry_run_planning_only_until_policy_approval"
)


@dataclass(frozen=True)
class GraphGovernanceStatus(View):
    graph_indexing_enabled: bool = False
    planning_available: bool = True
    background_indexing_enabled: bool = False
    runtime_indexing_enabled: bool = False
    last_plan_summary: str = "none"
    disabled_reason: str = GRAPH_RUNTIME_DISABLED_REASON


def graph_governance_status() -> dict[str, object]:
    return GraphGovernanceStatus().to_dict()
