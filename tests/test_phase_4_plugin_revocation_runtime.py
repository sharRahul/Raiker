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

_CAP = "plugin_revocation_cap"
_DOC = "docs/threat-models/plugin-revocation.md"
_EXEC_CAP = "plugin_execution_cap"
_EXEC_DOC = "docs/threat-models/plugin-execution.md"


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "plugin-revoke"
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
        installed_by="principal_owner",
    )


def _ack(store: SQLiteStore, capability: str, doc: str) -> None:
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) VALUES (?, ?, ?, ?)",
            (capability, "principal_owner", utc_now(), doc),
        )


def _enable(ws: Path, *, also_execution: bool = False) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    store = SQLiteStore(ws)
    _ack(store, _CAP, _DOC)
    result = svc.set_capability_state(_CAP, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is True, result.reason_code
    if also_execution:
        _ack(store, _EXEC_CAP, _EXEC_DOC)
        exec_result = svc.set_capability_state(
            _EXEC_CAP, "enabled_runtime", None, "test", confirmation_token="confirm"
        )
        assert exec_result.ok is True, exec_result.reason_code


def _authority(ws: Path) -> tuple[RuntimeAuthority, Principal]:
    store = SQLiteStore(ws)
    authority = RuntimeAuthority(
        store, EventLogWriter(store), executor_registry=build_default_executor_registry(ws, store)
    )
    raw = store.get_principal("principal_owner")
    assert raw is not None
    return authority, Principal(**raw)


def _revoke_action(principal_id: str, **args: object) -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal_id,
        action_type=_CAP,
        tool_or_service_name=_CAP,
        arguments=dict(args),
        risk_level=RiskLevelValue.MEDIUM,
        session_id="sess_plugin_revoke",
    )


def _exec_action(principal_id: str, **args: object) -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal_id,
        action_type=_EXEC_CAP,
        tool_or_service_name=_EXEC_CAP,
        arguments=dict(args),
        risk_level=RiskLevelValue.MEDIUM,
        session_id="sess_plugin_exec",
    )


def test_plugin_revocation_cap_is_real_executor(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    registry = build_default_executor_registry(ws, SQLiteStore(ws))
    assert _CAP in REAL_EXECUTOR_CAPABILITIES
    assert registry.has(_CAP)


def test_revocation_gate_disabled_blocks(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    # Default gates are enabled for integrated capabilities; disable this one to test the fail-closed path.
    RuntimeControlService(ws).disable_capability("plugin_revocation_cap", None, "test")
    store = SQLiteStore(ws)
    _install(store)
    authority, principal = _authority(ws)
    result = authority.route_action(
        _revoke_action(principal.principal_id, plugin_id="local.readonly"),
        principal,
    )
    assert result.decision == "disabled_by_capability_gate"
    # The install record is untouched while the gate is disabled.
    assert store.list_plugin_install_records(status="installed")[0]["plugin_id"] == "local.readonly"


def test_revocation_requires_threat_model_ack(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    result = svc.set_capability_state(_CAP, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is False
    assert "no_threat_model_ack" in (result.reason_code or "")


def test_revocation_requires_installed_plugin(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(
        _revoke_action(principal.principal_id, plugin_id="missing.plugin"),
        principal,
    )
    assert result.error == "plugin_not_installed"


def test_revocation_marks_record_revoked_without_leaking_contents(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    store = SQLiteStore(ws)
    _install(store, permissions=["tool:read_file"])
    authority, principal = _authority(ws)
    result = authority.route_action(
        _revoke_action(principal.principal_id, plugin_id="local.readonly", reason="over-permissioned"),
        principal,
    )
    assert result.decision == "allow"
    assert result.message == "executed"

    assert store.list_plugin_install_records(status="installed") == []
    revoked = store.list_plugin_install_records(status="revoked")
    assert len(revoked) == 1
    assert revoked[0]["plugin_id"] == "local.readonly"

    events = EventViewer(store).list_events(event_type="action_executed")
    assert len(events) == 1
    payload = EventViewer(store).read_event_payload(events[0]["event_id"])
    assert payload is not None
    # The audit reason label and permission payload are never emitted.
    dumped = json.dumps(payload)
    assert "over-permissioned" not in dumped
    assert "tool:read_file" not in dumped
    assert payload["payload"]["artifacts"]["new_status"] == "revoked"
    assert payload["payload"]["artifacts"]["execution_enabled"] is False


def test_second_revocation_is_idempotent_no_op(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    store = SQLiteStore(ws)
    _install(store)
    authority, principal = _authority(ws)
    first = authority.route_action(
        _revoke_action(principal.principal_id, plugin_id="local.readonly"),
        principal,
    )
    assert first.decision == "allow"
    second = authority.route_action(
        _revoke_action(principal.principal_id, plugin_id="local.readonly"),
        principal,
    )
    assert second.error == "plugin_already_revoked"
    # Still exactly one revoked record; no duplicate mutation.
    assert len(store.list_plugin_install_records(status="revoked")) == 1


def test_execution_fails_closed_after_revocation(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    (ws / "secret.txt").write_text("TOPSECRET", encoding="utf-8")
    _enable(ws, also_execution=True)
    store = SQLiteStore(ws)
    _install(store, permissions=["tool:read_file"])
    authority, principal = _authority(ws)

    # Revoke the plugin, then attempt a brokered read-only tool call.
    authority.route_action(
        _revoke_action(principal.principal_id, plugin_id="local.readonly"),
        principal,
    )
    result = authority.route_action(
        _exec_action(
            principal.principal_id,
            plugin_id="local.readonly",
            tool_name="read_file",
            tool_args={"path": "secret.txt"},
        ),
        principal,
    )
    assert result.error == "plugin_revoked"
    executions = store.list_plugin_execution_records()
    assert executions[0]["status"] == "denied"
