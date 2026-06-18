from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubagentPlan:
    parent_task_id: str
    role: str
    objective: str
    can_spawn: bool = False
    reason: str = "phase4_subagents_disabled_until_parent_policy_and_budget_controls_exist"


def plan_subagent(parent_task_id: str, role: str, objective: str) -> SubagentPlan:
    return SubagentPlan(parent_task_id=parent_task_id, role=role, objective=objective)
