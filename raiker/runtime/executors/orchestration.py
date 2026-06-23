from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.agents.orchestration import (
    OrchestrationOutcome,
    SubagentRunner,
    SubagentSpecError,
    TeamCoordinator,
    parse_subagent_spec,
)
from raiker.runtime.executors.base import ExecutionResult
from raiker.storage.sqlite import SQLiteStore

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction


def _to_result(capability: str, action_id: str, outcome: OrchestrationOutcome) -> ExecutionResult:
    return ExecutionResult(
        ok=outcome.ok,
        capability=capability,
        action_id=action_id,
        reason_code=outcome.reason_code,
        summary=outcome.summary,
        artifacts=outcome.artifacts,
    )


class SubagentExecutor:
    """Real executor for the ``subagents`` capability (bounded, governed, in-process)."""

    capability = "subagents"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._runner = SubagentRunner(workspace_root, store)

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        try:
            spec = parse_subagent_spec(action.arguments)
        except SubagentSpecError as exc:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"invalid_subagent_spec:{exc}",
                summary="Subagent spec invalid; failing closed.",
            )
        outcome = self._runner.run(
            spec,
            principal_id=principal.principal_id,
            session_id=action.session_id,
            turn_id=action.turn_id,
        )
        return _to_result(self.capability, action.action_id, outcome)


class MultiAgentTeamExecutor:
    """Real executor for the ``multi_agent_teams`` capability (bounded, governed, in-process)."""

    capability = "multi_agent_teams"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._coordinator = TeamCoordinator(workspace_root, store)

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        try:
            outcome = self._coordinator.run(
                action.arguments,
                principal_id=principal.principal_id,
                session_id=action.session_id,
                turn_id=action.turn_id,
            )
        except SubagentSpecError as exc:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"invalid_team_spec:{exc}",
                summary="Team spec invalid; failing closed.",
            )
        return _to_result(self.capability, action.action_id, outcome)
