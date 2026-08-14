from __future__ import annotations

from pathlib import Path
from typing import Any

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import PolicyDecision, ToolAction
from raiker.control.service import RuntimeControlService
from raiker.events.query import EventViewer
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, PrincipalType, RiskLevelValue
from raiker.runtime.executors import (
    ApprovalExecutionRelay,
    ExecutorRegistry,
    FileWriteExecutor,
    MemoryForgetExecutor,
    MemoryWriteExecutor,
    NetworkExecutor,
    PatchApplyExecutor,
    ProcessExecutor,
    ShellExecutor,
    WebFetchExecutor,
)
from raiker.storage.sqlite import SQLiteStore

_TIER1_CAPS = ("approval_execution_relay", "file_write_execution", "patch_apply_execution",
               "memory_write_execution", "memory_forget_execution")
_TIER2_CAPS = ("shell_execution", "process_execution", "web_fetch", "network_execution")


def _enable_caps(store: SQLiteStore, svc: RuntimeControlService, caps: tuple[str, ...]) -> None:
    for cap in caps:
        with store.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) VALUES (?, ?, ?, ?)",
                (cap, "principal_owner", utc_now(), "e2e"),
            )
        svc.set_capability_state(cap, "enabled_runtime", None, "e2e")


def _force_enable_caps(store: SQLiteStore, caps: tuple[str, ...]) -> None:
    now = utc_now()
    for cap in caps:
        with store.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) VALUES (?, ?, ?, ?)",
                (cap, "principal_owner", now, "e2e"),
            )
        store.upsert_capability_gate_state({
            "capability": cap,
            "state": "enabled_runtime",
            "requested_by": "principal_owner",
            "requested_at": now,
            "activated_by": "principal_owner",
            "activated_at": now,
            "reason": "e2e",
            "created_at": now,
            "updated_at": now,
        })


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "e2e"
    ws.mkdir()
    return ws


def _setup(ws: Path) -> dict[str, Any]:
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "e2e")
    store = SQLiteStore(ws)
    now = utc_now()
    with store.connect() as connection:
        for cap in _TIER1_CAPS:
            connection.execute(
                "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) VALUES (?, ?, ?, ?)",
                (cap, "principal_owner", now, "e2e"),
            )
    for cap in _TIER1_CAPS:
        svc.set_capability_state(cap, "enabled_runtime", None, "e2e")
    # Enable gov caps needed for admin operations
    with store.connect() as connection:
        for cap in ("admin_mutation", "policy_mutation", "role_mutation"):
            connection.execute(
                "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) VALUES (?, ?, ?, ?)",
                (cap, "principal_owner", now, "e2e"),
            )
    registry = ExecutorRegistry()
    registry.register("approval_execution_relay", ApprovalExecutionRelay(ws, store))
    registry.register("file_write_execution", FileWriteExecutor(ws))
    registry.register("patch_apply_execution", PatchApplyExecutor(ws))
    registry.register("memory_write_execution", MemoryWriteExecutor(ws, store))
    registry.register("memory_forget_execution", MemoryForgetExecutor(ws))
    registry.register("shell_execution", ShellExecutor(ws))
    registry.register("process_execution", ProcessExecutor(ws))
    registry.register("web_fetch", WebFetchExecutor(ws))
    registry.register("network_execution", NetworkExecutor(ws))
    return {"store": store, "registry": registry, "ws": ws}


def _make_human(store: SQLiteStore) -> Principal:
    raw = store.get_principal("principal_owner")
    assert raw is not None, "bootstrap must have created principal_owner"
    return Principal(**raw)


# ── Happy path: file_write_execution directly ──


def test_file_write_executor_happy(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    ctx = _setup(ws)
    store = ctx["store"]
    writer = EventLogWriter(store)
    registry = ExecutorRegistry()
    registry.register("file_write_execution", FileWriteExecutor(ws))
    registry.register("patch_apply_execution", PatchApplyExecutor(ws))
    registry.register("approval_execution_relay", ApprovalExecutionRelay(ws, store))
    authority = RuntimeAuthority(store, writer, executor_registry=registry)

    principal = _make_human(store)
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type="write_file",
        tool_or_service_name="write_file",
        arguments={"path": "hello.txt", "text": "Hello, World!"},
        risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "allow"
    assert result.error is None
    assert result.message == "executed"

    target = ws / "hello.txt"
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "Hello, World!"


# ── Happy path: approval_execution_relay ──


def test_approval_relay_executor_happy(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    ctx = _setup(ws)
    store = ctx["store"]
    writer = EventLogWriter(store)
    registry = ExecutorRegistry()
    registry.register("file_write_execution", FileWriteExecutor(ws))
    registry.register("patch_apply_execution", PatchApplyExecutor(ws))
    registry.register("approval_execution_relay", ApprovalExecutionRelay(ws, store))
    authority = RuntimeAuthority(store, writer, executor_registry=registry)

    # Create a pending tool action with its approval
    action_id = new_id("act_")
    store.insert_tool_action(
        ToolAction(
            action_id=action_id,
            tool_name="write_file",
            arguments={"path": "approved_hello.txt", "text": "Approved Content"},
            risk_level="low",
            requires_approval=True,
            proposed_by="principal_owner",
        ),
        session_id="e2e", turn_id=None, status="approval_required",
    )
    approval_id = new_id("appr_")
    store.insert_approval(approval_id, action_id)

    # Route the relay action
    principal = _make_human(store)
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type="approval_execution_relay",
        tool_or_service_name="approval_execution_relay",
        arguments={"approval_id": approval_id},
        risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "allow"
    assert result.error is None
    assert result.message == "executed"

    target = ws / "approved_hello.txt"
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "Approved Content"


# ── Negative: execution blocked on non-allow decisions ──


def test_executor_not_called_on_deny(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    ctx = _setup(ws)
    store = ctx["store"]
    writer = EventLogWriter(store)
    registry = ExecutorRegistry()
    registry.register("file_write_execution", FileWriteExecutor(ws))
    registry.register("patch_apply_execution", PatchApplyExecutor(ws))
    registry.register("approval_execution_relay", ApprovalExecutionRelay(ws, store))

    class DenyEngine:
        def review(self, tool_action: Any) -> PolicyDecision:
            return PolicyDecision(
                decision_id=new_id("pol_"), action_id=tool_action.action_id,
                decision="deny", reasons=["mock_deny"], requires_user_approval=False,
            )

    authority = RuntimeAuthority(store, writer, policy_engine=DenyEngine(), executor_registry=registry)  # type: ignore[arg-type]

    principal = _make_human(store)
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type="write_file",
        tool_or_service_name="write_file",
        arguments={"path": "no_write.txt", "text": "should not appear"},
        risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "deny"
    assert not (ws / "no_write.txt").exists()


# ── Negative: disabled gate blocks execution ──


def test_disabled_gate_blocks_execution(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    ctx = _setup(ws)
    store = ctx["store"]
    writer = EventLogWriter(store)
    registry = ExecutorRegistry()
    registry.register("file_write_execution", FileWriteExecutor(ws))
    registry.register("patch_apply_execution", PatchApplyExecutor(ws))
    registry.register("approval_execution_relay", ApprovalExecutionRelay(ws, store))
    authority = RuntimeAuthority(store, writer, executor_registry=registry)

    # Disable the file_write_execution gate
    svc = RuntimeControlService(ws)
    svc.set_capability_state("file_write_execution", "disabled", None, "disable for test")

    principal = _make_human(store)
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type="write_file",
        tool_or_service_name="write_file",
        arguments={"path": "blocked.txt", "text": "should not appear"},
        risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "disabled_by_capability_gate"
    assert not (ws / "blocked.txt").exists()


# ── Negative: missing executor fails closed ──


def test_missing_executor_fails_closed(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    ctx = _setup(ws)
    store = ctx["store"]
    writer = EventLogWriter(store)
    authority = RuntimeAuthority(store, writer)  # No executor registry

    principal = _make_human(store)
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type="write_file",
        tool_or_service_name="write_file",
        arguments={"path": "unavailable.txt", "text": "should not appear"},
        risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "allow"
    assert result.error == "execution_unavailable:no_executor"
    assert not (ws / "unavailable.txt").exists()


# ── Negative: approval_execution_relay with unknown approval_id ──


def test_approval_relay_unknown_approval(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    ctx = _setup(ws)
    store = ctx["store"]
    writer = EventLogWriter(store)
    registry = ExecutorRegistry()
    registry.register("approval_execution_relay", ApprovalExecutionRelay(ws, store))
    authority = RuntimeAuthority(store, writer, executor_registry=registry)

    principal = _make_human(store)
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type="approval_execution_relay",
        tool_or_service_name="approval_execution_relay",
        arguments={"approval_id": "nonexistent"},
        risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "allow"
    assert result.error is not None
    assert "approval_not_found" in result.error


# ── action_executed event is present (redacted) ──


def test_action_executed_event_present(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    ctx = _setup(ws)
    store = ctx["store"]
    writer = EventLogWriter(store)
    viewer = EventViewer(store)
    registry = ExecutorRegistry()
    registry.register("file_write_execution", FileWriteExecutor(ws))
    registry.register("patch_apply_execution", PatchApplyExecutor(ws))
    registry.register("approval_execution_relay", ApprovalExecutionRelay(ws, store))
    authority = RuntimeAuthority(store, writer, executor_registry=registry)

    principal = _make_human(store)
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type="write_file",
        tool_or_service_name="write_file",
        arguments={"path": "event_test.txt", "text": "event content"},
        risk_level=RiskLevelValue.LOW,
    )
    authority.route_action(action, principal)

    events = viewer.list_events(event_type="action_executed")
    assert len(events) == 1
    payload = viewer.read_event_payload(events[0]["event_id"])
    assert payload is not None
    inner = payload.get("payload", {})
    assert inner["action_id"] == action.action_id
    assert inner["capability"] == "file_write_execution"
    assert inner["ok"] is True
    # Verify redaction: no file contents in summary or artifacts
    assert "event content" not in inner["summary"]
    assert "event content" not in str(inner.get("artifacts", {}))


# ── Negative: AI principal denied ──


def test_ai_principal_denied(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    ctx = _setup(ws)
    store = ctx["store"]
    writer = EventLogWriter(store)
    registry = ExecutorRegistry()
    registry.register("file_write_execution", FileWriteExecutor(ws))
    registry.register("patch_apply_execution", PatchApplyExecutor(ws))
    registry.register("approval_execution_relay", ApprovalExecutionRelay(ws, store))
    authority = RuntimeAuthority(store, writer, executor_registry=registry)

    from raiker.contracts.models import Role
    now = utc_now()
    store.insert_role(Role(role_id="rl_ai", name="assistant", description="", is_system_role=True, created_at=now))
    ai = Principal(
        principal_id="p_ai",
        principal_type=PrincipalType.AI_AGENT,
        display_name="AI",
        role_ids=("rl_ai",),
        is_active=True,
    )
    store.insert_principal(principal_id="p_ai", principal_type="ai_agent", display_name="AI", role_ids=("rl_ai",), is_active=True)

    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="p_ai",
        action_type="write_file",
        tool_or_service_name="write_file",
        arguments={"path": "ai_write.txt", "text": "should not appear"},
        risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, ai)
    assert result.decision != "allow"
    assert not (ws / "ai_write.txt").exists()


# ── Tier 1: Memory executors ──


def test_memory_write_executor_happy(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    ctx = _setup(ws)
    store = ctx["store"]
    registry = ctx["registry"]

    writer = EventLogWriter(store)
    authority = RuntimeAuthority(store, writer, executor_registry=registry)

    principal = _make_human(store)
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type="memory_write",
        tool_or_service_name="memory_write",
        arguments={
            "text": "Test memory content for executor",
            "scope": "project",
            "confidence": "0.9",
            "trust_score": "0.8",
        },
        risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "allow"
    assert result.error is None
    assert result.message == "executed"

    viewer = EventViewer(store)
    events = viewer.list_events(event_type="action_executed")
    executed = [e for e in events if e["actor"] == "executor"]
    assert len(executed) >= 1
    payload = viewer.read_event_payload(executed[-1]["event_id"])
    assert payload is not None
    inner = payload.get("payload", {})
    assert inner["capability"] == "memory_write_execution"
    assert inner["ok"] is True
    # Redacted: no raw text in summary
    assert "Test memory content" not in inner["summary"]


def test_memory_forget_executor(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    ctx = _setup(ws)
    store = ctx["store"]
    registry = ctx["registry"]
    writer = EventLogWriter(store)

    # Write a memory first so we have something to forget
    from raiker.memory.store import MemoryGovernance, write_memory
    entry = write_memory(
        "Content to forget",
        workspace_root=ws,
        governance=MemoryGovernance(
            source_event_id=new_id("evt_"),
            source_session_id="e2e",
            source_turn_id=None,
            source_type="test",
            confidence=0.5,
            trust_score=0.5,
            retention="until_forget",
            approval_state="policy_allowed",
            created_by="test",
        ),
    )

    authority = RuntimeAuthority(store, writer, executor_registry=registry)
    principal = _make_human(store)
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type="memory_forget",
        tool_or_service_name="memory_forget",
        arguments={"memory_id": entry.memory_id},
        risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "allow"
    assert result.error is None
    assert result.message == "executed"

    # Verify the memory is gone
    from raiker.memory.store import get_memory
    assert get_memory(entry.memory_id, workspace_root=ws) is None


def test_memory_write_denied_no_text(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    ctx = _setup(ws)
    store = ctx["store"]
    registry = ctx["registry"]
    writer = EventLogWriter(store)
    authority = RuntimeAuthority(store, writer, executor_registry=registry)

    principal = _make_human(store)
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type="memory_write",
        tool_or_service_name="memory_write",
        arguments={},
        risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "allow"
    assert result.error is not None
    assert "missing_argument:text" in result.error


def test_memory_write_disabled_gate(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    ctx = _setup(ws)
    store = ctx["store"]
    registry = ctx["registry"]
    writer = EventLogWriter(store)
    svc = RuntimeControlService(ws)
    svc.set_capability_state("memory_write_execution", "disabled", None, "disable test")
    authority = RuntimeAuthority(store, writer, executor_registry=registry)

    principal = _make_human(store)
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_owner",
        action_type="memory_write",
        tool_or_service_name="memory_write",
        arguments={"text": "should not be written"},
        risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "disabled_by_capability_gate"


# ── Tier 2: Shell + Process + Web + Network executors ──


def test_shell_executor_denied_no_command(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    ctx = _setup(ws)
    store = ctx["store"]
    registry = ctx["registry"]
    _force_enable_caps(store, _TIER2_CAPS)
    writer = EventLogWriter(store)
    authority = RuntimeAuthority(store, writer, executor_registry=registry)
    principal = _make_human(store)
    action = GovernedAction(
        action_id=new_id("act_"), principal_id="principal_owner",
        action_type="shell", tool_or_service_name="shell",
        arguments={}, risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "allow"
    assert result.error is not None
    assert "missing_argument:command" in result.error


def test_shell_executor_blocked_not_allowed(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    ctx = _setup(ws)
    store = ctx["store"]
    registry = ctx["registry"]
    _force_enable_caps(store, _TIER2_CAPS)
    writer = EventLogWriter(store)
    authority = RuntimeAuthority(store, writer, executor_registry=registry)
    principal = _make_human(store)
    action = GovernedAction(
        action_id=new_id("act_"), principal_id="principal_owner",
        action_type="shell", tool_or_service_name="shell",
        arguments={"command": "rm -rf /"}, risk_level=RiskLevelValue.LOW,
        authority_kind="approval", authority_id="approval_shell_denial",
        session_id="sess_shell_denial", turn_id="turn_shell_denial",
    )
    result = authority.route_action(action, principal)
    assert result.decision == "allow"
    assert result.error is not None
    assert "command_not_allowed" in result.error


def test_process_executor_denied_no_executable(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    ctx = _setup(ws)
    store = ctx["store"]
    registry = ctx["registry"]
    _force_enable_caps(store, _TIER2_CAPS)
    writer = EventLogWriter(store)
    authority = RuntimeAuthority(store, writer, executor_registry=registry)
    principal = _make_human(store)
    action = GovernedAction(
        action_id=new_id("act_"), principal_id="principal_owner",
        action_type="process", tool_or_service_name="process",
        arguments={}, risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "allow"
    assert result.error is not None
    assert "missing_argument:executable" in result.error


def test_web_fetch_denied_no_url(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    ctx = _setup(ws)
    store = ctx["store"]
    registry = ctx["registry"]
    _force_enable_caps(store, _TIER2_CAPS)
    writer = EventLogWriter(store)
    authority = RuntimeAuthority(store, writer, executor_registry=registry)
    principal = _make_human(store)
    action = GovernedAction(
        action_id=new_id("act_"), principal_id="principal_owner",
        action_type="web_fetch", tool_or_service_name="web_fetch",
        arguments={}, risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "allow"
    assert result.error is not None
    assert "missing_argument:url" in result.error


def test_web_fetch_egress_denied(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    ctx = _setup(ws)
    store = ctx["store"]
    registry = ctx["registry"]
    _force_enable_caps(store, _TIER2_CAPS)
    writer = EventLogWriter(store)
    authority = RuntimeAuthority(store, writer, executor_registry=registry)
    principal = _make_human(store)
    action = GovernedAction(
        action_id=new_id("act_"), principal_id="principal_owner",
        action_type="web_fetch", tool_or_service_name="web_fetch",
        arguments={"url": "http://malicious.example.com/data"},
        risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "allow"
    assert result.error is not None
    assert "egress_denied" in result.error


def test_network_execution_egress_denied(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    ctx = _setup(ws)
    store = ctx["store"]
    registry = ctx["registry"]
    _force_enable_caps(store, _TIER2_CAPS)
    writer = EventLogWriter(store)
    authority = RuntimeAuthority(store, writer, executor_registry=registry)
    principal = _make_human(store)
    action = GovernedAction(
        action_id=new_id("act_"), principal_id="principal_owner",
        action_type="network", tool_or_service_name="network",
        arguments={"url": "http://evil.com/hack"},
        risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "allow"
    assert result.error is not None
    assert "egress_denied" in result.error


def test_tier2_disabled_gate_blocks_execution(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    ctx = _setup(ws)
    store = ctx["store"]
    registry = ctx["registry"]
    _force_enable_caps(store, _TIER2_CAPS)
    svc = RuntimeControlService(ws)
    svc.set_capability_state("shell_execution", "disabled", None, "disable")
    writer = EventLogWriter(store)
    authority = RuntimeAuthority(store, writer, executor_registry=registry)
    principal = _make_human(store)
    action = GovernedAction(
        action_id=new_id("act_"), principal_id="principal_owner",
        action_type="shell", tool_or_service_name="shell",
        arguments={"command": "echo test"}, risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "disabled_by_capability_gate"
