from __future__ import annotations

from pathlib import Path

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import Role
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, PrincipalType, RiskLevelValue
from raiker.runtime.executors import build_default_executor_registry
from raiker.storage.sqlite import SQLiteStore

_CAP = "file_write_execution"  # real Tier-1 executor, enabled without threat ack


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "decision-modes"
    ws.mkdir()
    return ws


def _owner_service(ws: Path) -> RuntimeControlService:
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    return svc


def _enable_filewrite(svc: RuntimeControlService) -> None:
    result = svc.set_capability_state(_CAP, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is True, result.reason_code


def _authority(ws: Path) -> RuntimeAuthority:
    store = SQLiteStore(ws)
    return RuntimeAuthority(
        store, EventLogWriter(store), executor_registry=build_default_executor_registry(ws, store)
    )


def _ai_principal(ws: Path) -> Principal:
    store = SQLiteStore(ws)
    now = utc_now()
    store.insert_role(Role(role_id="rl_ai", name="assistant", description="", is_system_role=True, created_at=now))
    store.insert_principal(
        principal_id="p_ai", principal_type=PrincipalType.AI_AGENT.value,
        display_name="AI", role_ids=("rl_ai",), is_active=True,
    )
    return Principal(
        principal_id="p_ai", principal_type=PrincipalType.AI_AGENT, display_name="AI",
        role_ids=("rl_ai",), is_active=True,
    )


def _write_action(principal_id: str, *, risk: str = RiskLevelValue.LOW, name: str = "out.txt") -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal_id,
        action_type="write_file",
        tool_or_service_name="write_file",
        arguments={"path": name, "text": "hello"},
        risk_level=risk,
    )


# ── Governance of the setter ─────────────────────────────────────────────────


def test_default_mode_is_ask(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    authority = _authority(ws)
    assert authority.get_capability_decision_mode(_CAP) == "ask"


def test_owner_can_set_mode_ai_cannot(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    svc = RuntimeControlService(ws)
    # "always_allow" is accepted as a legacy alias; it normalizes to canonical "allow".
    ok = svc.set_capability_decision_mode(_CAP, "always_allow", None, "test")
    assert ok.ok is True, ok.reason_code
    assert _authority(ws).get_capability_decision_mode(_CAP) == "allow"

    # An AI principal cannot change decision modes.
    authority = _authority(ws)
    denial = authority.set_capability_decision_mode(_CAP, "deny", _ai_principal(ws), "x")
    assert denial == "ai_cannot_manage_runtime_gates"


def test_permissive_mode_requires_executor(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    svc = RuntimeControlService(ws)
    # medical_runtime has no real executor -> cannot be relaxed to always_allow/auto.
    blocked = svc.set_capability_decision_mode("medical_runtime", "auto", None, "x")
    assert blocked.ok is False
    assert blocked.reason_code == "decision_mode_requires_executor:medical_runtime"
    # ...but 'deny' (only tightens) is always allowed.
    tightened = svc.set_capability_decision_mode("medical_runtime", "deny", None, "x")
    assert tightened.ok is True, tightened.reason_code


def test_invalid_mode_and_unknown_capability(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    svc = RuntimeControlService(ws)
    assert svc.set_capability_decision_mode(_CAP, "bogus", None, "x").reason_code == "invalid_decision_mode:bogus"
    assert svc.set_capability_decision_mode("nope_cap", "ask", None, "x").reason_code == "unknown_capability:nope_cap"


# ── Router behavior per mode (AI-proposed actions) ───────────────────────────


def test_ask_default_requires_approval_for_ai(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    svc = _owner_service(ws)
    _enable_filewrite(svc)
    authority = _authority(ws)
    result = authority.route_action(_write_action("p_ai"), _ai_principal(ws))
    assert result.decision == "needs_approval"
    assert not (ws / "out.txt").exists()


def test_always_allow_executes_for_ai(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    svc = _owner_service(ws)
    _enable_filewrite(svc)
    svc.set_capability_decision_mode(_CAP, "always_allow", None, "test")
    authority = _authority(ws)
    result = authority.route_action(_write_action("p_ai"), _ai_principal(ws))
    assert result.decision == "allow"
    assert result.message == "executed"
    assert (ws / "out.txt").read_text(encoding="utf-8") == "hello"


def test_deny_mode_blocks(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    svc = _owner_service(ws)
    _enable_filewrite(svc)
    svc.set_capability_decision_mode(_CAP, "deny", None, "test")
    authority = _authority(ws)
    result = authority.route_action(_write_action("p_ai"), _ai_principal(ws))
    assert result.decision == "deny"
    assert result.message == "denied_by_decision_mode"


def test_auto_runs_low_asks_high(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    svc = _owner_service(ws)
    _enable_filewrite(svc)
    svc.set_capability_decision_mode(_CAP, "auto", None, "test")
    authority = _authority(ws)
    low = authority.route_action(_write_action("p_ai", risk=RiskLevelValue.LOW, name="low.txt"), _ai_principal(ws))
    assert low.message == "executed"
    assert (ws / "low.txt").exists()
    high = authority.route_action(_write_action("p_ai", risk=RiskLevelValue.HIGH, name="high.txt"), _ai_principal(ws))
    assert high.decision == "needs_approval"
    assert not (ws / "high.txt").exists()


def test_always_allow_cannot_bypass_critical_floor(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    svc = _owner_service(ws)
    _enable_filewrite(svc)
    svc.set_capability_decision_mode(_CAP, "always_allow", None, "test")
    authority = _authority(ws)
    result = authority.route_action(
        _write_action("p_ai", risk=RiskLevelValue.CRITICAL, name="crit.txt"), _ai_principal(ws)
    )
    assert result.decision == "deny"
    assert result.message == "critical_action_requires_human_confirmation"
    assert not (ws / "crit.txt").exists()
