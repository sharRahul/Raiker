from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors import (
    REAL_EXECUTOR_CAPABILITIES,
    build_default_executor_registry,
)
from raiker.runtime.executors.tier5_network import RemoteExecutionExecutor
from raiker.runtime.executors.tier6_domains import FinanceRuntimeExecutor, MedicalRuntimeExecutor
from raiker.storage.sqlite import SQLiteStore

_SENSITIVE = (
    "medical_runtime", "finance_runtime", "investment_runtime", "cctv_runtime",
    "home_security_runtime", "hardware_operator_runtime", "remote_execution_cap",
    "cloud_execution_cap",
    "vector_embedding_runtime", "model_provider_runtime",
)


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "reg"
    ws.mkdir()
    return ws


def test_default_registry_matches_real_set(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    registry = build_default_executor_registry(ws, store)
    assert registry.capabilities() == REAL_EXECUTOR_CAPABILITIES


def test_sensitive_caps_not_registered(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    registry = build_default_executor_registry(ws, store)
    for cap in _SENSITIVE:
        assert not registry.has(cap), f"{cap} must not have a default executor"
        assert cap not in REAL_EXECUTOR_CAPABILITIES


def test_plugin_caps_are_real_but_bounded(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    registry = build_default_executor_registry(ws, store)
    assert registry.has("plugin_install")
    assert "plugin_install" in REAL_EXECUTOR_CAPABILITIES
    assert registry.has("plugin_execution_cap")
    assert "plugin_execution_cap" in REAL_EXECUTOR_CAPABILITIES
    assert registry.has("plugin_revocation_cap")
    assert "plugin_revocation_cap" in REAL_EXECUTOR_CAPABILITIES
    assert registry.has("plugin_runtime_cap")
    assert "plugin_runtime_cap" in REAL_EXECUTOR_CAPABILITIES
    assert registry.has("plugin_sandboxed_runtime_cap")
    assert "plugin_sandboxed_runtime_cap" in REAL_EXECUTOR_CAPABILITIES


def test_stub_executors_fail_closed(tmp_path: Path) -> None:
    """Sensitive-domain executors must fail closed, never fake success."""
    ws = _ws(tmp_path)
    action = SimpleNamespace(action_id="act_x", arguments={})
    principal = SimpleNamespace(principal_id="p")
    for executor in (MedicalRuntimeExecutor(ws), FinanceRuntimeExecutor(ws), RemoteExecutionExecutor(ws)):
        result = executor.execute(action, principal)  # type: ignore[arg-type]
        assert result.ok is False
        assert result.reason_code is not None
        assert result.reason_code.startswith("not_implemented:")


def test_activation_blocks_capability_without_executor(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    # medical_runtime has no real executor -> cannot be flipped on.
    result = svc.set_capability_state("medical_runtime", "enabled_runtime", None, "test")
    assert result.ok is False
    assert result.reason_code is not None
    assert "no_executor" in result.reason_code or "human_confirmation" in result.reason_code


def test_real_capability_enables_and_executes(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    enable = svc.set_capability_state("file_write_execution", "enabled_runtime", None, "test")
    assert enable.ok is True, enable.reason_code

    store = SQLiteStore(ws)
    writer = EventLogWriter(store)
    registry = build_default_executor_registry(ws, store)
    authority = RuntimeAuthority(store, writer, executor_registry=registry)
    raw = store.get_principal("principal_rahul")
    assert raw is not None
    principal = Principal(**raw)
    action = GovernedAction(
        action_id=new_id("act_"),
        principal_id="principal_rahul",
        action_type="write_file",
        tool_or_service_name="write_file",
        arguments={"path": "out.txt", "text": "real work"},
        risk_level=RiskLevelValue.LOW,
    )
    result = authority.route_action(action, principal)
    assert result.decision == "allow"
    assert result.message == "executed"
    assert (ws / "out.txt").read_text(encoding="utf-8") == "real work"
