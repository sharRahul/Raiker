from __future__ import annotations

from pathlib import Path

from raiker.approval_preview_registry import (
    create_fresh_graph_preview_for_workspace,
    create_fresh_memory_preview_for_workspace,
)
from raiker.rollback_plans import (
    RollbackPlan,
    create_graph_rollback_plan,
    create_memory_rollback_plan,
)


class RollbackPlanRegistry:
    """In-memory preview-only rollback registry; it never runs rollback actions."""

    def __init__(self) -> None:
        self._plans: dict[str, RollbackPlan] = {}

    def add(self, plan: RollbackPlan) -> RollbackPlan:
        self._plans[plan.rollback_plan_id] = plan
        return plan

    def list_plans(self) -> list[RollbackPlan]:
        return [self._plans[key] for key in sorted(self._plans)]


def create_workspace_rollback_plans(workspace_root: str | Path = ".") -> list[RollbackPlan]:
    plans = [create_graph_rollback_plan(create_fresh_graph_preview_for_workspace(workspace_root))]
    memory_preview = create_fresh_memory_preview_for_workspace(workspace_root)
    if memory_preview is not None:
        plans.append(create_memory_rollback_plan(memory_preview))
    return plans


def rollback_plan_summary(*, workspace_root: str | Path = ".") -> dict[str, object]:
    return {
        "graph_rollback_plan_available": True,
        "memory_rollback_plan_available": True,
        "rollback_execution_enabled": False,
        "preview_only_mode": True,
    }
