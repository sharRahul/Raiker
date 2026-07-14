from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, PrincipalType, RiskLevelValue
from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES, build_default_executor_registry
from raiker.runtime.executors.sandbox import SandboxError
from raiker.runtime.executors.tier4_plugins import PluginSandboxImagePullExecutor
from raiker.storage.sqlite import SQLiteStore

_CAP = "plugin_sandbox_image_pull_cap"
_DOC = "docs/threat-models/plugin-sandbox-image-pull.md"
_IMAGE = "registry.example/raiker-plugin:1"
_IMAGE_ALLOWLIST_ENV = "RAIKER_CONTAINER_IMAGE_ALLOWLIST"
_REGISTRY_ALLOWLIST_ENV = "RAIKER_PLUGIN_IMAGE_REGISTRY_ALLOWLIST"


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "plugin-image-pull"
    ws.mkdir()
    return ws


def _enable(ws: Path) -> None:
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    service = RuntimeControlService(ws)
    service.activate_runtime_mode("local_single_user_runtime", None, "test")
    store = SQLiteStore(ws)
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) VALUES (?, ?, ?, ?)",
            (_CAP, "principal_rahul", utc_now(), _DOC),
        )
    result = service.set_capability_state(_CAP, "enabled_runtime", None, "test", confirmation_token="confirm")
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
        risk_level=RiskLevelValue.HIGH,
        session_id="sess_plugin_image_pull",
    )


def _full_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_IMAGE_ALLOWLIST_ENV, _IMAGE)
    monkeypatch.setenv(_REGISTRY_ALLOWLIST_ENV, "registry.example")


def test_image_pull_cap_is_real_executor(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    registry = build_default_executor_registry(ws, SQLiteStore(ws))
    assert _CAP in REAL_EXECUTOR_CAPABILITIES
    assert registry.has(_CAP)


def test_image_pull_gate_disabled_blocks(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    RuntimeControlService(ws).disable_capability(_CAP, None, "test")
    authority, principal = _authority(ws)
    result = authority.route_action(_action(principal.principal_id, image=_IMAGE), principal)
    assert result.decision == "disabled_by_capability_gate"


def test_image_pull_requires_image_and_registry_allowlists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(_action(principal.principal_id, image=_IMAGE), principal)
    assert result.error == "image_not_allowed"
    monkeypatch.setenv(_IMAGE_ALLOWLIST_ENV, _IMAGE)
    result = authority.route_action(_action(principal.principal_id, image=_IMAGE), principal)
    assert result.error == "image_registry_not_allowed"


def test_image_pull_rejects_registry_not_matching_image_reference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.setenv(_IMAGE_ALLOWLIST_ENV, _IMAGE)
    monkeypatch.setenv(_REGISTRY_ALLOWLIST_ENV, "other-registry.example")
    authority, principal = _authority(ws)
    result = authority.route_action(_action(principal.principal_id, image=_IMAGE), principal)
    assert result.error == "image_registry_not_allowed"


def _fake_action(image: object) -> Any:
    return SimpleNamespace(action_id="act_image", arguments={"image": image})


def _principal() -> Principal:
    return Principal(
        principal_id="principal_rahul",
        principal_type=PrincipalType.HUMAN,
        display_name="Rahul",
    )


def test_image_pull_uses_only_docker_pull_and_redacts_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _full_env(monkeypatch)
    captured: dict[str, Any] = {}

    def fake_runner(command: list[str], **kwargs: Any) -> dict[str, Any]:
        captured["command"] = command
        captured["allowlist"] = kwargs["allowlist"]
        return {"returncode": 0, "stdout_bytes": 23, "stderr_bytes": 0, "truncated": False}

    result = PluginSandboxImagePullExecutor(tmp_path, runner=fake_runner).execute(
        _fake_action(_IMAGE), _principal()
    )
    assert result.ok is True
    assert captured["command"] == ["docker", "pull", _IMAGE]
    assert captured["allowlist"] == frozenset({"docker"})
    assert result.artifacts == {
        "image": _IMAGE,
        "registry": "registry.example",
        "returncode": 0,
        "stdout_bytes": 23,
        "stderr_bytes": 0,
        "truncated": False,
        "output_redacted": True,
    }


def test_image_pull_maps_missing_docker_to_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _full_env(monkeypatch)

    def fake_runner(command: list[str], **kwargs: Any) -> dict[str, Any]:
        raise SandboxError("command_not_found:docker")

    result = PluginSandboxImagePullExecutor(tmp_path, runner=fake_runner).execute(
        _fake_action(_IMAGE), _principal()
    )
    assert result.ok is False
    assert result.reason_code == "docker_unavailable"


def test_image_pull_nonzero_exit_is_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _full_env(monkeypatch)

    def fake_runner(command: list[str], **kwargs: Any) -> dict[str, Any]:
        return {"returncode": 2, "stdout_bytes": 0, "stderr_bytes": 10, "truncated": False}

    result = PluginSandboxImagePullExecutor(tmp_path, runner=fake_runner).execute(
        _fake_action(_IMAGE), _principal()
    )
    assert result.ok is False
    assert result.reason_code == "plugin_image_pull_exit:2"
