from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import PolicyDecision, Role
from raiker.events.query import EventViewer
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, PrincipalType, RiskLevelValue
from raiker.runtime.executors import ExecutionResult, ExecutorRegistry
from raiker.storage.sqlite import SQLiteStore


class TrackingExecutor:
    capability: str
    called: bool = False
    last_action: GovernedAction | None = None
    last_principal: Principal | None = None

    def __init__(self, capability: str) -> None:
        self.capability = capability

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        self.called = True
        self.last_action = action
        self.last_principal = principal
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary="tracked execution",
        )


@dataclass
class MockPolicyEngine:
    decision: str = "allow"

    def review(self, tool_action: Any) -> PolicyDecision:
        return PolicyDecision(
            decision_id=new_id("pol_"),
            action_id=tool_action.action_id,
            decision=self.decision,
            reasons=["mock_policy"],
            requires_user_approval=False,
            risk_level=tool_action.risk_level,
        )


# ── Helpers ──


def _make_human_principal(store: SQLiteStore) -> Principal:
    now = utc_now()
    store.insert_role(Role(
        role_id="rl_user", name="user",
        description="", is_system_role=True, created_at=now,
    ))
    principal = Principal(
        principal_id="p_human",
        principal_type=PrincipalType.HUMAN,
        display_name="Human",
        role_ids=("rl_user",),
        is_active=True,
    )
    store.insert_principal(
        principal_id="p_human",
        principal_type=PrincipalType.HUMAN.value,
        display_name="Human",
        role_ids=("rl_user",),
        is_active=True,
    )
    return principal


def _make_ai_principal(store: SQLiteStore) -> Principal:
    now = utc_now()
    store.insert_role(Role(
        role_id="rl_ai", name="assistant",
        description="", is_system_role=True, created_at=now,
    ))
    principal = Principal(
        principal_id="p_ai",
        principal_type=PrincipalType.AI_AGENT,
        display_name="AI",
        role_ids=("rl_ai",),
        is_active=True,
    )
    store.insert_principal(
        principal_id="p_ai",
        principal_type=PrincipalType.AI_AGENT.value,
        display_name="AI",
        role_ids=("rl_ai",),
        is_active=True,
    )
    return principal


def _make_action(
    *,
    action_type: str = "read_file",
    tool_or_service_name: str = "read_file",
    risk_level: str = RiskLevelValue.LOW,
    requires_approval: bool = False,
    requires_risk_acceptance: bool = False,
    principal_id: str = "p_human",
) -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal_id,
        action_type=action_type,
        tool_or_service_name=tool_or_service_name,
        arguments={},
        domain_scope="",
        risk_level=risk_level,
        requires_approval=requires_approval,
        requires_risk_acceptance=requires_risk_acceptance,
    )


# ── Execution only on "allow" ──


def test_executor_called_on_allow(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    executor = TrackingExecutor("read_file")
    registry = ExecutorRegistry()
    registry.register("read_file", executor)
    authority = RuntimeAuthority(
        store, writer, policy_engine=MockPolicyEngine(decision="allow"),  # type: ignore[arg-type]
        executor_registry=registry,
    )
    principal = _make_human_principal(store)
    action = _make_action(principal_id=principal.principal_id)
    result = authority.route_action(action, principal)
    assert result.decision == "allow"
    assert result.error is None
    assert result.message == "executed"
    assert executor.called is True


def test_executor_not_called_on_deny(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    executor = TrackingExecutor("read_file")
    registry = ExecutorRegistry()
    registry.register("read_file", executor)
    authority = RuntimeAuthority(
        store, writer, policy_engine=MockPolicyEngine(decision="deny"),  # type: ignore[arg-type]
        executor_registry=registry,
    )
    principal = _make_human_principal(store)
    action = _make_action(principal_id=principal.principal_id)
    result = authority.route_action(action, principal)
    assert result.decision == "deny"
    assert executor.called is False


def test_executor_not_called_on_needs_approval(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    executor = TrackingExecutor("read_file")
    registry = ExecutorRegistry()
    registry.register("read_file", executor)
    authority = RuntimeAuthority(
        store, writer, policy_engine=MockPolicyEngine(decision="needs_approval"),  # type: ignore[arg-type]
        executor_registry=registry,
    )
    principal = _make_ai_principal(store)
    action = _make_action(
        principal_id=principal.principal_id,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "needs_approval"
    assert executor.called is False


def test_executor_not_called_on_needs_risk_acceptance(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    executor = TrackingExecutor("read_file")
    registry = ExecutorRegistry()
    registry.register("read_file", executor)
    authority = RuntimeAuthority(
        store, writer, policy_engine=MockPolicyEngine(decision="allow"),  # type: ignore[arg-type]
        executor_registry=registry,
    )
    principal = _make_human_principal(store)
    action = _make_action(
        principal_id=principal.principal_id,
        requires_risk_acceptance=True,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "needs_risk_acceptance"
    assert executor.called is False


def test_executor_not_called_on_needs_human_confirmation(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    executor = TrackingExecutor("read_file")
    registry = ExecutorRegistry()
    registry.register("read_file", executor)
    authority = RuntimeAuthority(
        store, writer, policy_engine=MockPolicyEngine(decision="allow"),  # type: ignore[arg-type]
        executor_registry=registry,
    )
    principal = _make_human_principal(store)
    action = _make_action(
        principal_id=principal.principal_id,
        risk_level=RiskLevelValue.CRITICAL,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "needs_human_confirmation"
    assert executor.called is False


def test_executor_not_called_on_disabled_by_capability_gate(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    executor = TrackingExecutor("file_write_execution")
    registry = ExecutorRegistry()
    registry.register("file_write_execution", executor)
    authority = RuntimeAuthority(
        store, writer, executor_registry=registry,
    )
    principal = _make_human_principal(store)
    # file_write_execution is integrated, so it ships enabled by default; disable it
    # here to exercise the disabled-gate path.
    store.upsert_capability_gate_state({
        "capability": "file_write_execution",
        "state": "disabled",
        "created_at": utc_now(),
        "updated_at": utc_now(),
    })
    action = _make_action(
        principal_id=principal.principal_id,
        action_type="write_file",
        tool_or_service_name="write_file",
    )
    result = authority.route_action(action, principal)
    assert result.decision == "disabled_by_capability_gate"
    assert executor.called is False


# ── Missing executor fails closed ──


def test_missing_executor_fails_closed(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    registry = ExecutorRegistry()
    authority = RuntimeAuthority(
        store, writer, policy_engine=MockPolicyEngine(decision="allow"),  # type: ignore[arg-type]
        executor_registry=registry,
    )
    principal = _make_human_principal(store)
    action = _make_action(principal_id=principal.principal_id)
    result = authority.route_action(action, principal)
    assert result.decision == "allow"
    assert result.error == "execution_unavailable:no_executor"
    assert result.message == "allowed"


def test_executor_for_different_capability_not_called(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    executor = TrackingExecutor("file_write_execution")
    registry = ExecutorRegistry()
    registry.register("file_write_execution", executor)
    authority = RuntimeAuthority(
        store, writer, policy_engine=MockPolicyEngine(decision="allow"),  # type: ignore[arg-type]
        executor_registry=registry,
    )
    principal = _make_human_principal(store)
    action = _make_action(principal_id=principal.principal_id)
    result = authority.route_action(action, principal)
    assert result.decision == "allow"
    assert result.error == "execution_unavailable:no_executor"
    assert executor.called is False


# ── action_executed / action_failed events ──


def test_action_executed_event_emitted(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    viewer = EventViewer(store)
    executor = TrackingExecutor("read_file")
    registry = ExecutorRegistry()
    registry.register("read_file", executor)
    authority = RuntimeAuthority(
        store, writer, policy_engine=MockPolicyEngine(decision="allow"),  # type: ignore[arg-type]
        executor_registry=registry,
    )
    principal = _make_human_principal(store)
    action = _make_action(principal_id=principal.principal_id)
    authority.route_action(action, principal)
    events = viewer.list_events(event_type="action_executed")
    assert len(events) == 1
    assert events[0]["actor"] == "executor"
    payload = viewer.read_event_payload(events[0]["event_id"])
    assert payload is not None
    inner = payload.get("payload", {})
    assert inner["action_id"] == action.action_id
    assert inner["capability"] == "read_file"
    assert inner["ok"] is True
    assert inner["summary"] == "tracked execution"


def test_action_executed_not_emitted_on_non_allow(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    viewer = EventViewer(store)
    executor = TrackingExecutor("read_file")
    registry = ExecutorRegistry()
    registry.register("read_file", executor)
    authority = RuntimeAuthority(
        store, writer, policy_engine=MockPolicyEngine(decision="deny"),  # type: ignore[arg-type]
        executor_registry=registry,
    )
    principal = _make_human_principal(store)
    action = _make_action(principal_id=principal.principal_id)
    authority.route_action(action, principal)
    events = viewer.list_events(event_type="action_executed")
    assert len(events) == 0
    events2 = viewer.list_events(event_type="action_failed")
    assert len(events2) == 0


# ── ExecutorRegistry — standalone ──


class TestExecutorRegistryStandalone:
    def test_register_and_get(self) -> None:
        registry = ExecutorRegistry()
        assert registry.has("read_file") is False
        executor = TrackingExecutor("read_file")
        registry.register("read_file", executor)
        assert registry.has("read_file") is True
        assert registry.get("read_file") is executor

    def test_get_returns_none_for_unregistered(self) -> None:
        registry = ExecutorRegistry()
        assert registry.get("nonexistent") is None

    def test_register_overwrites(self) -> None:
        registry = ExecutorRegistry()
        e1 = TrackingExecutor("cap")
        e2 = TrackingExecutor("cap")
        registry.register("cap", e1)
        registry.register("cap", e2)
        assert registry.get("cap") is e2
