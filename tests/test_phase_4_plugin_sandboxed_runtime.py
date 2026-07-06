from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.plugins.registry import record_plugin_install
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES, build_default_executor_registry
from raiker.runtime.executors.sandbox import SandboxError
from raiker.runtime.executors.tier4_plugins import PluginSandboxedRuntimeExecutor
from raiker.storage.sqlite import SQLiteStore

_CAP = "plugin_sandboxed_runtime_cap"
_DOC = "docs/threat-models/plugin-sandboxed-runtime.md"
_PLUGIN = "local.runner"
_ALLOWLIST_ENV = "RAIKER_PLUGIN_RUNTIME_ALLOWLIST"
_IMAGE_ENV = "RAIKER_PLUGIN_RUNTIME_IMAGE"
_IMAGE_ALLOWLIST_ENV = "RAIKER_CONTAINER_IMAGE_ALLOWLIST"
_IMAGE = "raiker-plugin-sandbox:latest"


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "plugin-sandbox"
    ws.mkdir()
    return ws


def _install(store: SQLiteStore, *, plugin_id: str = _PLUGIN) -> None:
    record_plugin_install(
        store,
        plugin_id=plugin_id,
        version="1.0.0",
        trust_level="local_dev",
        permissions_json='["tool:read_file"]',
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
        session_id="sess_plugin_sandbox",
    )


def _full_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_ALLOWLIST_ENV, _PLUGIN)
    monkeypatch.setenv(_IMAGE_ENV, _IMAGE)
    monkeypatch.setenv(_IMAGE_ALLOWLIST_ENV, _IMAGE)


# ── Registration + governed fail-closed cases (no daemon needed) ──


def test_sandboxed_cap_is_real_executor(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    registry = build_default_executor_registry(ws, SQLiteStore(ws))
    assert _CAP in REAL_EXECUTOR_CAPABILITIES
    assert registry.has(_CAP)


def test_sandboxed_gate_disabled_blocks(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    # Default gates are enabled for integrated capabilities; disable this one to test the fail-closed path.
    RuntimeControlService(ws).disable_capability("plugin_sandboxed_runtime_cap", None, "test")
    _install(SQLiteStore(ws))
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, plugin_id=_PLUGIN, entrypoint="entry.py"), principal
    )
    assert result.decision == "disabled_by_capability_gate"


def test_sandboxed_requires_threat_model_ack(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    result = svc.set_capability_state(_CAP, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is False
    assert "no_threat_model_ack" in (result.reason_code or "")


def test_sandboxed_requires_installed_plugin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    _full_env(monkeypatch)
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, plugin_id="missing.plugin", entrypoint="entry.py"), principal
    )
    assert result.error == "plugin_not_installed"


def test_sandboxed_requires_owner_allowlist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.delenv(_ALLOWLIST_ENV, raising=False)
    monkeypatch.setenv(_IMAGE_ENV, _IMAGE)
    monkeypatch.setenv(_IMAGE_ALLOWLIST_ENV, _IMAGE)
    _install(SQLiteStore(ws))
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, plugin_id=_PLUGIN, entrypoint="entry.py"), principal
    )
    assert result.error == "plugin_runtime_not_allowlisted"


def test_sandboxed_requires_image_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv(_ALLOWLIST_ENV, _PLUGIN)
    monkeypatch.delenv(_IMAGE_ENV, raising=False)
    _install(SQLiteStore(ws))
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, plugin_id=_PLUGIN, entrypoint="entry.py"), principal
    )
    assert result.error == "plugin_runtime_image_unset"


def test_sandboxed_image_not_allowlisted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv(_ALLOWLIST_ENV, _PLUGIN)
    monkeypatch.setenv(_IMAGE_ENV, _IMAGE)
    monkeypatch.delenv(_IMAGE_ALLOWLIST_ENV, raising=False)
    _install(SQLiteStore(ws))
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, plugin_id=_PLUGIN, entrypoint="entry.py"), principal
    )
    assert result.error == "image_not_allowed"


# ── Execute path with an injected runner (deterministic, no live daemon) ──


def _prepared_executor(
    ws: Path, monkeypatch: pytest.MonkeyPatch, runner: Any
) -> tuple[PluginSandboxedRuntimeExecutor, Any, GovernedAction]:
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    _full_env(monkeypatch)
    store = SQLiteStore(ws)
    _install(store)
    (ws / "entry.py").write_text("print('hi')\n", encoding="utf-8")
    executor = PluginSandboxedRuntimeExecutor(ws, store, runner=runner)
    raw = store.get_principal("principal_rahul")
    assert raw is not None
    principal = Principal(**raw)
    action = _action(principal.principal_id, plugin_id=_PLUGIN, entrypoint="entry.py")
    return executor, principal, action


def test_sandboxed_executes_with_no_network_and_single_mount(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)
    captured: dict[str, Any] = {}

    def fake_runner(command: list[str], **kwargs: Any) -> dict[str, Any]:
        captured["command"] = command
        captured["allowlist"] = kwargs.get("allowlist")
        return {"returncode": 0, "stdout_bytes": 3, "stderr_bytes": 0, "truncated": False}

    executor, principal, action = _prepared_executor(ws, monkeypatch, fake_runner)
    result = executor.execute(action, principal)
    assert result.ok is True

    cmd = captured["command"]
    assert cmd[:3] == ["docker", "run", "--rm"]
    assert cmd[cmd.index("--network") + 1] == "none"
    assert "--read-only" in cmd and "--cap-drop" in cmd and "--security-opt" in cmd
    # Only the single entrypoint file is bind-mounted, read-only.
    mount = cmd[cmd.index("-v") + 1]
    assert mount.endswith("/plugin/entry.py:ro")
    assert str(ws) in mount  # host side is the real script path
    assert _IMAGE in cmd
    assert cmd[-2:] == ["python3", "/plugin/entry.py"]
    assert captured["allowlist"] == frozenset({"docker"})

    assert result.artifacts["network_isolated"] is True
    assert result.artifacts["output_redacted"] is True
    assert "stdout" not in result.artifacts and "stderr" not in result.artifacts
    store = SQLiteStore(ws)
    assert store.list_plugin_execution_records()[0]["status"] == "succeeded"


def test_sandboxed_maps_missing_docker_to_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)

    def fake_runner(command: list[str], **kwargs: Any) -> dict[str, Any]:
        raise SandboxError("command_not_found:docker")

    executor, principal, action = _prepared_executor(ws, monkeypatch, fake_runner)
    result = executor.execute(action, principal)
    assert result.ok is False
    assert result.reason_code == "plugin_sandbox:docker_unavailable"


def test_sandboxed_nonzero_exit_is_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)

    def fake_runner(command: list[str], **kwargs: Any) -> dict[str, Any]:
        return {"returncode": 2, "stdout_bytes": 0, "stderr_bytes": 5, "truncated": False}

    executor, principal, action = _prepared_executor(ws, monkeypatch, fake_runner)
    result = executor.execute(action, principal)
    assert result.ok is False
    assert result.reason_code == "plugin_sandbox_exit:2"
    assert SQLiteStore(ws).list_plugin_execution_records()[0]["status"] == "failed"
