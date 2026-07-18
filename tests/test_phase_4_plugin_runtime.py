from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.control.service import RuntimeControlService
from raiker.events.query import EventViewer
from raiker.events.writer import EventLogWriter
from raiker.plugins.registry import record_plugin_install
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors import (
    REAL_EXECUTOR_CAPABILITIES,
    PluginRuntimeExecutor,
    build_default_executor_registry,
)
from raiker.storage.sqlite import SQLiteStore

_CAP = "plugin_runtime_cap"
_DOC = "docs/threat-models/plugin-runtime.md"
_REVOKE_CAP = "plugin_revocation_cap"
_REVOKE_DOC = "docs/threat-models/plugin-revocation.md"
_PLUGIN = "local.runner"
_ALLOWLIST_ENV = "RAIKER_PLUGIN_RUNTIME_ALLOWLIST"
_SCOPES_ENV = "RAIKER_PLUGIN_RUNTIME_SCOPES"


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "plugin-runtime"
    ws.mkdir()
    return ws


def _install(store: SQLiteStore, *, plugin_id: str = _PLUGIN) -> None:
    record_plugin_install(
        store,
        plugin_id=plugin_id,
        version="1.0.0",
        trust_level="local_dev",
        permissions_json=json.dumps(["tool:read_file"]),
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


def _enable(ws: Path, *, also_revocation: bool = False) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    store = SQLiteStore(ws)
    _ack(store, _CAP, _DOC)
    result = svc.set_capability_state(_CAP, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is True, result.reason_code
    if also_revocation:
        _ack(store, _REVOKE_CAP, _REVOKE_DOC)
        rev = svc.set_capability_state(
            _REVOKE_CAP, "enabled_runtime", None, "test", confirmation_token="confirm"
        )
        assert rev.ok is True, rev.reason_code


def _authority(ws: Path) -> tuple[RuntimeAuthority, Principal]:
    store = SQLiteStore(ws)
    authority = RuntimeAuthority(
        store, EventLogWriter(store), executor_registry=build_default_executor_registry(ws, store)
    )
    raw = store.get_principal("principal_owner")
    assert raw is not None
    return authority, Principal(**raw)


def _run_action(principal_id: str, *, action_type: str = _CAP, **args: object) -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal_id,
        action_type=action_type,
        tool_or_service_name=action_type,
        arguments=dict(args),
        risk_level=RiskLevelValue.MEDIUM,
        session_id="sess_plugin_runtime",
    )


def _write_entry(ws: Path, name: str, body: str) -> str:
    (ws / name).write_text(body, encoding="utf-8")
    return name


def test_plugin_runtime_cap_is_real_executor(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    registry = build_default_executor_registry(ws, SQLiteStore(ws))
    assert _CAP in REAL_EXECUTOR_CAPABILITIES
    assert registry.has(_CAP)


def test_runtime_gate_disabled_blocks(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    # Default gates are enabled for integrated capabilities; disable this one to test the fail-closed path.
    RuntimeControlService(ws).disable_capability("plugin_runtime_cap", None, "test")
    store = SQLiteStore(ws)
    _install(store)
    authority, principal = _authority(ws)
    result = authority.route_action(
        _run_action(principal.principal_id, plugin_id=_PLUGIN, entrypoint="entry.py"),
        principal,
    )
    assert result.decision == "disabled_by_capability_gate"
    # Nothing ran: no execution record was written while the gate is disabled.
    assert store.list_plugin_execution_records() == []


def test_runtime_requires_threat_model_ack(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    result = svc.set_capability_state(_CAP, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is False
    assert "no_threat_model_ack" in (result.reason_code or "")


def test_runtime_requires_installed_plugin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv(_ALLOWLIST_ENV, _PLUGIN)
    authority, principal = _authority(ws)
    _write_entry(ws, "entry.py", "print('hi')\n")
    result = authority.route_action(
        _run_action(principal.principal_id, plugin_id=_PLUGIN, entrypoint="entry.py"),
        principal,
    )
    assert result.error == "plugin_not_installed"


def test_runtime_requires_owner_allowlist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.delenv(_ALLOWLIST_ENV, raising=False)  # empty allowlist = fail closed
    store = SQLiteStore(ws)
    _install(store)
    _write_entry(ws, "entry.py", "print('hi')\n")
    authority, principal = _authority(ws)
    result = authority.route_action(
        _run_action(principal.principal_id, plugin_id=_PLUGIN, entrypoint="entry.py"),
        principal,
    )
    assert result.error == "plugin_runtime_not_allowlisted"
    # It fails closed *before* running anything, but still records the denial.
    records = store.list_plugin_execution_records()
    assert len(records) == 1
    assert records[0]["status"] == "denied"


def test_runtime_rejects_disallowed_interpreter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv(_ALLOWLIST_ENV, _PLUGIN)
    store = SQLiteStore(ws)
    _install(store)
    authority, principal = _authority(ws)
    result = authority.route_action(
        _run_action(principal.principal_id, plugin_id=_PLUGIN, entrypoint="entry.py", interpreter="bash"),
        principal,
    )
    assert result.error == "interpreter_not_allowed:bash"


def test_runtime_rejects_workspace_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv(_ALLOWLIST_ENV, _PLUGIN)
    store = SQLiteStore(ws)
    _install(store)
    authority, principal = _authority(ws)
    result = authority.route_action(
        _run_action(principal.principal_id, plugin_id=_PLUGIN, entrypoint="../escape.py"),
        principal,
    )
    assert result.error == "outside_workspace:entrypoint"


def test_runtime_executes_installed_allowlisted_plugin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv(_ALLOWLIST_ENV, _PLUGIN)
    store = SQLiteStore(ws)
    _install(store)
    _write_entry(ws, "entry.py", "import sys\nprint('SECRETOUTPUT')\nsys.exit(0)\n")
    authority, principal = _authority(ws)
    result = authority.route_action(
        _run_action(principal.principal_id, plugin_id=_PLUGIN, entrypoint="entry.py"),
        principal,
    )
    assert result.decision == "allow"
    assert result.message == "executed"

    records = store.list_plugin_execution_records()
    assert len(records) == 1
    assert records[0]["status"] == "succeeded"

    # Plugin stdout must never leak into runtime events/artifacts.
    events = EventViewer(store).list_events(event_type="action_executed")
    assert len(events) == 1
    payload = EventViewer(store).read_event_payload(events[0]["event_id"])
    assert payload is not None
    dumped = json.dumps(payload)
    assert "SECRETOUTPUT" not in dumped
    assert payload["payload"]["artifacts"]["output_redacted"] is True
    assert payload["payload"]["artifacts"]["returncode"] == 0


@pytest.mark.skipif(os.name != "nt", reason="Windows interpreter selection")
def test_runtime_defaults_to_direct_python_on_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv(_ALLOWLIST_ENV, _PLUGIN)
    store = SQLiteStore(ws)
    _install(store)
    _write_entry(ws, "entry.py", "print('ok')\n")
    _, principal = _authority(ws)
    commands: list[list[str]] = []

    def runner(command: list[str], **_: object) -> dict[str, object]:
        commands.append(command)
        return {"returncode": 0, "stdout_bytes": 0, "stderr_bytes": 0, "truncated": False}

    result = PluginRuntimeExecutor(ws, store, runner=runner).execute(
        _run_action(principal.principal_id, plugin_id=_PLUGIN, entrypoint="entry.py"), principal
    )

    assert result.ok is True
    assert commands == [["python", str(ws / "entry.py")]]


def test_runtime_reports_nonzero_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv(_ALLOWLIST_ENV, _PLUGIN)
    store = SQLiteStore(ws)
    _install(store)
    _write_entry(ws, "entry.py", "import sys\nsys.exit(3)\n")
    authority, principal = _authority(ws)
    result = authority.route_action(
        _run_action(principal.principal_id, plugin_id=_PLUGIN, entrypoint="entry.py"),
        principal,
    )
    assert result.error == "plugin_runtime_exit:3"
    assert store.list_plugin_execution_records()[0]["status"] == "failed"


def test_runtime_allows_entrypoint_within_plugin_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv(_ALLOWLIST_ENV, _PLUGIN)
    monkeypatch.setenv(_SCOPES_ENV, f"{_PLUGIN}:plugins/runner")
    store = SQLiteStore(ws)
    _install(store)
    (ws / "plugins" / "runner").mkdir(parents=True)
    _write_entry(ws, "plugins/runner/entry.py", "print('ok')\n")
    authority, principal = _authority(ws)
    result = authority.route_action(
        _run_action(principal.principal_id, plugin_id=_PLUGIN, entrypoint="plugins/runner/entry.py"),
        principal,
    )
    assert result.decision == "allow"
    assert result.message == "executed"
    assert store.list_plugin_execution_records()[0]["status"] == "succeeded"


def test_runtime_denies_entrypoint_outside_plugin_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv(_ALLOWLIST_ENV, _PLUGIN)
    monkeypatch.setenv(_SCOPES_ENV, f"{_PLUGIN}:plugins/runner")
    store = SQLiteStore(ws)
    _install(store)
    # In the workspace but outside the plugin's scoped subdirectory.
    _write_entry(ws, "elsewhere.py", "print('nope')\n")
    authority, principal = _authority(ws)
    result = authority.route_action(
        _run_action(principal.principal_id, plugin_id=_PLUGIN, entrypoint="elsewhere.py"),
        principal,
    )
    assert result.error == "entrypoint_outside_plugin_scope"
    assert store.list_plugin_execution_records()[0]["status"] == "denied"


def test_runtime_scope_that_escapes_workspace_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv(_ALLOWLIST_ENV, _PLUGIN)
    monkeypatch.setenv(_SCOPES_ENV, f"{_PLUGIN}:../outside")
    store = SQLiteStore(ws)
    _install(store)
    _write_entry(ws, "entry.py", "print('hi')\n")
    authority, principal = _authority(ws)
    result = authority.route_action(
        _run_action(principal.principal_id, plugin_id=_PLUGIN, entrypoint="entry.py"),
        principal,
    )
    assert result.error == "plugin_scope_invalid"


def test_runtime_fails_closed_after_revocation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)
    _enable(ws, also_revocation=True)
    monkeypatch.setenv(_ALLOWLIST_ENV, _PLUGIN)
    store = SQLiteStore(ws)
    _install(store)
    _write_entry(ws, "entry.py", "print('hi')\n")
    authority, principal = _authority(ws)

    authority.route_action(
        _run_action(principal.principal_id, action_type=_REVOKE_CAP, plugin_id=_PLUGIN),
        principal,
    )
    result = authority.route_action(
        _run_action(principal.principal_id, plugin_id=_PLUGIN, entrypoint="entry.py"),
        principal,
    )
    assert result.error == "plugin_revoked"
