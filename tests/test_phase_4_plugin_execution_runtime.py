from __future__ import annotations

import json
from pathlib import Path

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.control.service import RuntimeControlService
from raiker.events.query import EventViewer
from raiker.events.writer import EventLogWriter
from raiker.plugins.registry import record_plugin_install
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES, build_default_executor_registry
from raiker.storage.sqlite import SQLiteStore

_CAP = "plugin_execution_cap"
_DOC = "docs/threat-models/plugin-execution.md"


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "plugin-exec"
    ws.mkdir()
    return ws


def _install(
    store: SQLiteStore,
    *,
    plugin_id: str = "local.readonly",
    permissions: list[str] | None = None,
) -> None:
    record_plugin_install(
        store,
        plugin_id=plugin_id,
        version="1.0.0",
        trust_level="local_dev",
        permissions_json=json.dumps(permissions or ["tool:read_file"]),
        checksum="checksum",
        signature="signature-marker",
        status="installed",
        installed_by="principal_rahul",
    )


def _enable(ws: Path) -> None:
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    store = SQLiteStore(ws)
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) VALUES (?, ?, ?, ?)",
            (_CAP, "principal_rahul", utc_now(), _DOC),
        )
    result = svc.set_capability_state(_CAP, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is True, result.reason_code


def _authority(ws: Path) -> tuple[RuntimeAuthority, Principal]:
    store = SQLiteStore(ws)
    authority = RuntimeAuthority(
        store, EventLogWriter(store), executor_registry=build_default_executor_registry(ws, store)
    )
    raw = store.get_principal("principal_rahul")
    assert raw is not None
    return authority, Principal(**raw)


def _action(principal_id: str, **args: object) -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal_id,
        action_type=_CAP,
        tool_or_service_name=_CAP,
        arguments=dict(args),
        risk_level=RiskLevelValue.MEDIUM,
        session_id="sess_plugin_exec",
    )


def test_plugin_execution_cap_is_real_executor(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    registry = build_default_executor_registry(ws, SQLiteStore(ws))
    assert _CAP in REAL_EXECUTOR_CAPABILITIES
    assert registry.has(_CAP)


def test_plugin_execution_gate_disabled_blocks_before_recording(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    store = SQLiteStore(ws)
    _install(store, permissions=["tool:list_directory"])
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(
            principal.principal_id,
            plugin_id="local.readonly",
            tool_name="list_directory",
            tool_args={"path": "."},
        ),
        principal,
    )
    assert result.decision == "disabled_by_capability_gate"
    assert store.list_plugin_execution_records() == []


def test_plugin_execution_requires_threat_model_ack(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    result = svc.set_capability_state(_CAP, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is False
    assert "no_threat_model_ack" in (result.reason_code or "")


def test_installed_plugin_invokes_allowed_read_only_tool_without_output_artifact(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    (ws / "secret.txt").write_text("TOPSECRET", encoding="utf-8")
    _enable(ws)
    store = SQLiteStore(ws)
    _install(store, permissions=["tool:read_file"])
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(
            principal.principal_id,
            plugin_id="local.readonly",
            tool_name="read_file",
            tool_args={"path": "secret.txt"},
        ),
        principal,
    )
    assert result.decision == "allow"
    assert result.message == "executed"

    executions = store.list_plugin_execution_records()
    assert len(executions) == 1
    assert executions[0]["plugin_id"] == "local.readonly"
    assert executions[0]["entrypoint"] == "tool:read_file"
    assert executions[0]["status"] == "succeeded"

    events = EventViewer(store).list_events(event_type="action_executed")
    assert len(events) == 1
    payload = EventViewer(store).read_event_payload(events[0]["event_id"])
    assert payload is not None
    assert "TOPSECRET" not in json.dumps(payload)
    assert payload["payload"]["artifacts"]["output_redacted"] is True


def test_plugin_execution_requires_installed_plugin(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(
            principal.principal_id,
            plugin_id="missing.plugin",
            tool_name="read_file",
            tool_args={"path": "x.txt"},
        ),
        principal,
    )
    assert result.error == "plugin_not_installed"
    assert SQLiteStore(ws).list_plugin_execution_records()[0]["status"] == "denied"


def test_plugin_execution_requires_granted_tool_permission(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    store = SQLiteStore(ws)
    _install(store, permissions=["tool:list_directory"])
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(
            principal.principal_id,
            plugin_id="local.readonly",
            tool_name="read_file",
            tool_args={"path": "x.txt"},
        ),
        principal,
    )
    assert result.error == "plugin_permission_not_granted:tool:read_file"
    assert store.list_plugin_execution_records()[0]["status"] == "denied"


def test_plugin_execution_never_brokers_write_tools(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    store = SQLiteStore(ws)
    _install(store, permissions=["tool:write_file"])
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(
            principal.principal_id,
            plugin_id="local.readonly",
            tool_name="write_file",
            tool_args={"path": "owned.txt", "text": "no"},
        ),
        principal,
    )
    assert result.error == "plugin_tool_not_brokered:write_file"
    assert not (ws / "owned.txt").exists()


def test_plugin_execution_preserves_workspace_policy(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    store = SQLiteStore(ws)
    _install(store, permissions=["tool:read_file"])
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(
            principal.principal_id,
            plugin_id="local.readonly",
            tool_name="read_file",
            tool_args={"path": str(outside)},
        ),
        principal,
    )
    assert result.error == "plugin_tool_policy_denied"
    assert store.list_plugin_execution_records()[0]["status"] == "denied"
