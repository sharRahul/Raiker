from __future__ import annotations

from pathlib import Path

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, PrincipalType, RiskLevelValue
from raiker.runtime.executors import (
    REAL_EXECUTOR_CAPABILITIES,
    build_default_executor_registry,
)
from raiker.storage.sqlite import SQLiteStore

_ORCH_CAPS = ("subagents", "multi_agent_teams")


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "orch"
    ws.mkdir()
    (ws / "hello.txt").write_text("hi", encoding="utf-8")
    return ws


def _enable(ws: Path, capability: str) -> RuntimeControlService:
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    store = SQLiteStore(ws)
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) VALUES (?, ?, ?, ?)",
            (capability, "principal_rahul", utc_now(), "docs/threat-models/subagents.md"),
        )
    result = svc.set_capability_state(capability, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is True, result.reason_code
    return svc


def _authority(ws: Path) -> tuple[RuntimeAuthority, Principal]:
    store = SQLiteStore(ws)
    writer = EventLogWriter(store)
    registry = build_default_executor_registry(ws, store)
    authority = RuntimeAuthority(store, writer, executor_registry=registry)
    raw = store.get_principal("principal_rahul")
    assert raw is not None
    return authority, Principal(**raw)


def _subagent_action(principal_id: str, **arg_overrides: object) -> GovernedAction:
    arguments: dict[str, object] = {
        "parent_task_id": "task_1",
        "name": "scout",
        "steps": [{"tool_name": "read_file", "arguments": {"path": "hello.txt"}}],
    }
    arguments.update(arg_overrides)
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal_id,
        action_type="subagents",
        tool_or_service_name="subagents",
        arguments=arguments,
        risk_level=RiskLevelValue.MEDIUM,
    )


# ── Registry / promotion ──


def test_orchestration_caps_are_real_executors(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    registry = build_default_executor_registry(ws, store)
    for cap in _ORCH_CAPS:
        assert cap in REAL_EXECUTOR_CAPABILITIES
        assert registry.has(cap)


# ── Fail-closed when the gate is off ──


def test_subagents_fail_closed_when_gate_disabled(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    authority, principal = _authority(ws)
    result = authority.route_action(_subagent_action(principal.principal_id), principal)
    assert result.decision == "disabled_by_capability_gate"


# ── Happy path: governed, bounded, read-only ──


def test_subagent_runs_readonly_steps_when_enabled(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws, "subagents")
    authority, principal = _authority(ws)
    result = authority.route_action(_subagent_action(principal.principal_id), principal)
    assert result.decision == "allow"
    assert result.message == "executed"
    store = SQLiteStore(ws)
    contracts = store.list_subagent_contracts()
    assert contracts and contracts[0]["status"] == "completed"


def test_subagent_rejects_mutating_tool(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws, "subagents")
    authority, principal = _authority(ws)
    action = _subagent_action(
        principal.principal_id,
        steps=[{"tool_name": "write_file", "arguments": {"path": "x.txt", "text": "nope"}}],
    )
    result = authority.route_action(action, principal)
    # Reached the executor (allowed by gate/policy for the human owner) but the
    # subagent itself fails closed on a non-delegable tool.
    assert result.decision == "allow"
    assert result.error is not None and result.error.startswith("subagent_tool_not_allowed")
    assert not (ws / "x.txt").exists()


def test_subagent_step_budget_enforced(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws, "subagents")
    authority, principal = _authority(ws)
    steps = [{"tool_name": "read_file", "arguments": {"path": "hello.txt"}}] * 3
    action = _subagent_action(principal.principal_id, max_steps=2, steps=steps)
    result = authority.route_action(action, principal)
    assert result.error == "subagent_step_budget_exceeded"


def test_subagent_depth_enforced(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws, "subagents")
    authority, principal = _authority(ws)
    action = _subagent_action(principal.principal_id, depth=2, max_depth=2)
    result = authority.route_action(action, principal)
    assert result.error == "subagent_depth_exceeded"


# ── AI principals can never run or enable orchestration ──


def test_ai_principal_blocked_from_subagents(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws, "subagents")
    authority, owner = _authority(ws)
    ai = Principal(
        principal_id="ai_1",
        principal_type=PrincipalType.AI_AGENT,
        display_name="assistant",
        domain_scopes=owner.domain_scopes,
        is_active=True,
    )
    result = authority.route_action(_subagent_action(ai.principal_id), ai)
    assert result.decision == "needs_approval"


# ── Multi-agent team ──


def test_multi_agent_team_runs_members(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws, "multi_agent_teams")
    authority, principal = _authority(ws)
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal.principal_id,
        action_type="multi_agent_teams",
        tool_or_service_name="multi_agent_teams",
        arguments={
            "name": "recon",
            "members": [
                {"name": "a", "steps": [{"tool_name": "list_directory", "arguments": {"path": "."}}]},
                {"name": "b", "steps": [{"tool_name": "read_file", "arguments": {"path": "hello.txt"}}]},
            ],
        },
        risk_level=RiskLevelValue.MEDIUM,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "allow"
    assert result.message == "executed"
    store = SQLiteStore(ws)
    ledgers = store.list_team_ledgers()
    assert ledgers and ledgers[0]["status"] == "completed"


def test_team_member_budget_enforced(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws, "multi_agent_teams")
    authority, principal = _authority(ws)
    members = [
        {"name": f"m{i}", "steps": [{"tool_name": "read_file", "arguments": {"path": "hello.txt"}}]}
        for i in range(6)
    ]
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal.principal_id,
        action_type="multi_agent_teams",
        tool_or_service_name="multi_agent_teams",
        arguments={"name": "toobig", "members": members},
        risk_level=RiskLevelValue.MEDIUM,
    )
    result = authority.route_action(action, principal)
    assert result.error == "team_member_budget_exceeded"
