from __future__ import annotations

import json
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import SubagentContract, TeamLedger, ToolAction
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker

# Subagents may only be delegated read-only / inspection tools. Mutating and
# egress tools are intentionally excluded: a subagent must never widen the
# parent's authority, and any such step would still be policy- and
# approval-gated per action regardless. Keeping the delegable set read-only is
# what makes this in-process orchestration bounded and reviewable.
DELEGABLE_TOOLS: frozenset[str] = frozenset({
    "read_file", "list_directory", "glob", "grep", "stat_path", "diff_files",
    "git_status", "git_diff", "git_log", "memory_search", "memory_list", "memory_get",
    "vector_get",
})

# Hard caps independent of any caller-supplied budget. Caller budgets may only
# shrink these, never grow them.
MAX_SUBAGENT_DEPTH = 3
MAX_SUBAGENT_STEPS = 25
MAX_TEAM_MEMBERS = 5


class SubagentSpecError(ValueError):
    """Raised when a subagent/team spec is malformed. Treated as fail-closed."""


@dataclass(frozen=True)
class SubagentStep:
    tool_name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class SubagentSpec:
    parent_task_id: str
    name: str
    objective: str
    depth: int
    max_depth: int
    max_steps: int
    max_runtime_seconds: int
    allowed_tools: frozenset[str]
    steps: tuple[SubagentStep, ...]


@dataclass(frozen=True)
class OrchestrationOutcome:
    """Metadata-only result of a subagent or team run.

    Carries counts, tool names, and statuses only — never file contents, raw
    tool output, secrets, or reasoning — so it is safe to place in a redacted
    ``action_executed`` event payload.
    """

    ok: bool
    ref_id: str
    reason_code: str | None
    summary: str
    artifacts: dict[str, Any]


def parse_subagent_spec(args: dict[str, Any]) -> SubagentSpec:
    parent_task_id = str(args.get("parent_task_id", "")).strip()
    if not parent_task_id:
        raise SubagentSpecError("missing:parent_task_id")
    name = str(args.get("name", "subagent")).strip() or "subagent"
    objective = str(args.get("objective", "")).strip()
    try:
        depth = int(args.get("depth", 0))
        max_depth = int(args.get("max_depth", MAX_SUBAGENT_DEPTH))
        max_steps = int(args.get("max_steps", MAX_SUBAGENT_STEPS))
        max_runtime_seconds = int(args.get("max_runtime_seconds", 30))
    except (TypeError, ValueError) as exc:
        raise SubagentSpecError(f"invalid:numeric_budget:{exc}") from None
    raw_allowed = args.get("allowed_tools")
    if raw_allowed is None:
        allowed_tools = frozenset(DELEGABLE_TOOLS)
    elif isinstance(raw_allowed, (list, tuple)):
        allowed_tools = frozenset(str(tool) for tool in raw_allowed)
    else:
        raise SubagentSpecError("invalid:allowed_tools")
    raw_steps = args.get("steps") or []
    if not isinstance(raw_steps, (list, tuple)):
        raise SubagentSpecError("invalid:steps")
    steps: list[SubagentStep] = []
    for entry in raw_steps:
        if not isinstance(entry, dict):
            raise SubagentSpecError("invalid:step")
        tool_name = str(entry.get("tool_name", "")).strip()
        if not tool_name:
            raise SubagentSpecError("missing:step.tool_name")
        step_args = entry.get("arguments") or {}
        if not isinstance(step_args, dict):
            raise SubagentSpecError("invalid:step.arguments")
        steps.append(SubagentStep(tool_name=tool_name, arguments=dict(step_args)))
    return SubagentSpec(
        parent_task_id=parent_task_id,
        name=name,
        objective=objective,
        depth=depth,
        max_depth=max_depth,
        max_steps=max_steps,
        max_runtime_seconds=max_runtime_seconds,
        allowed_tools=allowed_tools,
        steps=tuple(steps),
    )


class SubagentRunner:
    """Runs a bounded, governed, in-process subagent.

    A subagent executes a fixed, caller-supplied list of read-only tool steps,
    each routed through the same :class:`ToolBroker` -> :class:`PolicyEngine`
    path as any other action. Depth, step count, runtime, and the allowed-tool
    set are all bounded; any breach stops the subagent and fails closed (it
    never fabricates success). This is bounded delegated execution, not
    autonomous model-driven recursion — that remains gated.
    """

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._ws = Path(workspace_root).resolve()
        self._store = store
        self._broker = ToolBroker(
            workspace_root=self._ws,
            policy_engine=PolicyEngine(StaticPolicyConfig(self._ws), store=store),
            store=store,
            writer=None,
        )

    def run(
        self,
        spec: SubagentSpec,
        *,
        principal_id: str,
        session_id: str = "",
        turn_id: str | None = None,
    ) -> OrchestrationOutcome:
        subagent_id = new_id("sba_")
        now = utc_now()
        eff_depth = min(spec.max_depth, MAX_SUBAGENT_DEPTH)
        eff_steps = min(spec.max_steps, MAX_SUBAGENT_STEPS)
        effective_allowed = spec.allowed_tools & DELEGABLE_TOOLS

        contract = SubagentContract(
            subagent_id=subagent_id,
            parent_task_id=spec.parent_task_id,
            name=spec.name,
            mode="bounded_delegated_readonly",
            allowed_tools_json=json.dumps(sorted(effective_allowed)),
            max_depth=eff_depth,
            max_runtime_seconds=spec.max_runtime_seconds,
            max_cost=0.0,
            created_by=principal_id,
            created_at=now,
            status="running",
        )
        self._store.insert_subagent_contract(contract)

        tools_used: list[str] = []

        def finish(status: str, ok: bool, reason_code: str | None, summary: str, executed: int) -> OrchestrationOutcome:
            self._store.insert_subagent_contract(replace(contract, status=status))
            return OrchestrationOutcome(
                ok=ok,
                ref_id=subagent_id,
                reason_code=reason_code,
                summary=summary,
                artifacts={
                    "subagent_id": subagent_id,
                    "parent_task_id": spec.parent_task_id,
                    "name": spec.name,
                    "steps_total": len(spec.steps),
                    "steps_executed": executed,
                    "tools_used": sorted(set(tools_used)),
                    "status": status,
                },
            )

        if spec.depth >= eff_depth:
            return finish("failed", False, "subagent_depth_exceeded",
                          f"Subagent depth {spec.depth} reached the max of {eff_depth}.", 0)
        if len(spec.steps) > eff_steps:
            return finish("failed", False, "subagent_step_budget_exceeded",
                          f"{len(spec.steps)} steps exceeds the budget of {eff_steps}.", 0)
        disallowed = [step.tool_name for step in spec.steps if step.tool_name not in effective_allowed]
        if disallowed:
            return finish("failed", False, f"subagent_tool_not_allowed:{disallowed[0]}",
                          "A subagent step used a tool outside its read-only allowlist.", 0)

        start = time.monotonic()
        executed = 0
        for step in spec.steps:
            if time.monotonic() - start > spec.max_runtime_seconds:
                return finish("failed", False, "subagent_time_budget_exceeded",
                              f"Subagent exceeded its {spec.max_runtime_seconds}s budget.", executed)
            action = ToolAction(
                action_id=new_id("act_"),
                tool_name=step.tool_name,
                arguments=step.arguments,
                risk_level="low",
                requires_approval=False,
                proposed_by=principal_id,
            )
            result, decision = self._broker.execute(action, session_id=session_id, turn_id=turn_id)
            tools_used.append(step.tool_name)
            if decision.decision != "allow":
                return finish("failed", False,
                              f"subagent_step_blocked:{step.tool_name}:{decision.decision}",
                              "A subagent step was not allowed by policy; the subagent stopped.",
                              executed)
            if result.status != "success":
                return finish("failed", False,
                              f"subagent_step_failed:{step.tool_name}",
                              "A subagent step failed safely; the subagent stopped.", executed)
            executed += 1
        return finish("completed", True, None,
                      f"Subagent '{spec.name}' completed {executed} read-only step(s).", executed)


class TeamCoordinator:
    """Runs a bounded multi-agent team: several subagents in sequence.

    The team is the same bounded, governed primitive as a single subagent,
    repeated for up to :data:`MAX_TEAM_MEMBERS` members. Each member is an
    independent :class:`SubagentRunner` run; the team aggregates their
    metadata-only outcomes and fails closed if any member fails.
    """

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._ws = Path(workspace_root).resolve()
        self._store = store
        self._runner = SubagentRunner(self._ws, store)

    def run(
        self,
        args: dict[str, Any],
        *,
        principal_id: str,
        session_id: str = "",
        turn_id: str | None = None,
    ) -> OrchestrationOutcome:
        team_id = new_id("team_")
        now = utc_now()
        name = str(args.get("name", "team")).strip() or "team"
        raw_members = args.get("members") or []
        if not isinstance(raw_members, (list, tuple)):
            raise SubagentSpecError("invalid:members")
        member_specs = [
            parse_subagent_spec({"parent_task_id": team_id, **member})
            if isinstance(member, dict)
            else _raise_member()
            for member in raw_members
        ]

        ledger = TeamLedger(
            team_id=team_id,
            name=name,
            mode="bounded_delegated_readonly",
            members_json=json.dumps([spec.name for spec in member_specs]),
            max_depth=MAX_SUBAGENT_DEPTH,
            max_cost=0.0,
            created_by=principal_id,
            created_at=now,
            status="created",
        )
        self._store.insert_team_ledger(ledger)

        if len(member_specs) > MAX_TEAM_MEMBERS:
            self._store.insert_team_ledger(replace(ledger, status="cancelled"))
            return OrchestrationOutcome(
                ok=False, ref_id=team_id, reason_code="team_member_budget_exceeded",
                summary=f"{len(member_specs)} members exceeds the max of {MAX_TEAM_MEMBERS}.",
                artifacts={"team_id": team_id, "members_total": len(member_specs)},
            )

        self._store.insert_team_ledger(replace(ledger, status="active"))
        member_results: list[dict[str, Any]] = []
        ok_all = True
        first_failure: str | None = None
        for spec in member_specs:
            outcome = self._runner.run(
                spec, principal_id=principal_id, session_id=session_id, turn_id=turn_id,
            )
            member_results.append({"name": spec.name, "ok": outcome.ok, "reason_code": outcome.reason_code})
            if not outcome.ok:
                ok_all = False
                first_failure = first_failure or outcome.reason_code
        self._store.insert_team_ledger(replace(ledger, status="completed" if ok_all else "cancelled"))
        return OrchestrationOutcome(
            ok=ok_all,
            ref_id=team_id,
            reason_code=None if ok_all else (first_failure or "team_member_failed"),
            summary=f"Team '{name}' ran {len(member_results)} member(s); all_ok={ok_all}.",
            artifacts={
                "team_id": team_id,
                "members_total": len(member_specs),
                "member_results": member_results,
            },
        )


def _raise_member() -> SubagentSpec:
    raise SubagentSpecError("invalid:member")
