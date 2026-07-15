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
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES, build_default_executor_registry
from raiker.runtime.executors.containers import ContainerExecutionExecutor
from raiker.storage.sqlite import SQLiteStore

_CAP = "container_execution_cap"


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "cont"
    ws.mkdir()
    return ws


def _enable(ws: Path) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    store = SQLiteStore(ws)
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) VALUES (?, ?, ?, ?)",
            (_CAP, "principal_owner", utc_now(), "docs/threat-models/container.md"),
        )
    result = svc.set_capability_state(_CAP, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is True, result.reason_code


def _authority(ws: Path) -> tuple[RuntimeAuthority, Principal]:
    store = SQLiteStore(ws)
    registry = build_default_executor_registry(ws, store)
    authority = RuntimeAuthority(store, EventLogWriter(store), executor_registry=registry)
    raw = store.get_principal("principal_owner")
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
    )


def test_container_cap_is_real_executor(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    registry = build_default_executor_registry(ws, SQLiteStore(ws))
    assert _CAP in REAL_EXECUTOR_CAPABILITIES
    assert registry.has(_CAP)


def test_container_fail_closed_when_gate_disabled(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    # Default gates are enabled for integrated capabilities; disable this one to test the fail-closed path.
    RuntimeControlService(ws).disable_capability("container_execution_cap", None, "test")
    authority, principal = _authority(ws)
    result = authority.route_action(_action(principal.principal_id, image="alpine", command=["true"]), principal)
    assert result.decision == "disabled_by_capability_gate"


def test_container_image_not_allowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    monkeypatch.delenv("RAIKER_CONTAINER_IMAGE_ALLOWLIST", raising=False)
    authority, principal = _authority(ws)
    # Governed (human owner, gate on) but the image isn't allowlisted -> fail closed.
    result = authority.route_action(_action(principal.principal_id, image="alpine", command=["true"]), principal)
    assert result.decision == "allow"
    assert result.error == "image_not_allowed"


def test_container_missing_image(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(_action(principal.principal_id, command=["true"]), principal)
    assert result.error == "missing_argument:image"


# ── Execute path with an injected runner (deterministic, no live daemon) ──


def _fake_action(image: str, command: list[str]) -> Any:
    return SimpleNamespace(action_id="act_x", arguments={"image": image, "command": command})


def test_container_executes_with_hardened_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAIKER_CONTAINER_IMAGE_ALLOWLIST", "alpine")
    captured: dict[str, Any] = {}

    def fake_runner(command: list[str], **kwargs: Any) -> dict[str, Any]:
        captured["command"] = command
        captured["allowlist"] = kwargs.get("allowlist")
        return {"returncode": 0, "stdout_bytes": 3, "stderr_bytes": 0, "truncated": False}

    executor = ContainerExecutionExecutor(tmp_path, runner=fake_runner)
    result = executor.execute(_fake_action("alpine", ["echo", "hi"]), SimpleNamespace(principal_id="p"))  # type: ignore[arg-type]
    assert result.ok is True
    cmd = captured["command"]
    assert cmd[:3] == ["docker", "run", "--rm"]
    assert "--network" in cmd and cmd[cmd.index("--network") + 1] == "none"
    assert "--cap-drop" in cmd and "--read-only" in cmd and "--security-opt" in cmd
    assert "alpine" in cmd
    assert captured["allowlist"] == frozenset({"docker"})
    # No stdout/stderr content leaks into artifacts.
    assert set(result.artifacts) == {"image", "returncode", "stdout_bytes", "stderr_bytes", "truncated"}


def test_container_maps_missing_docker_to_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from raiker.runtime.executors.sandbox import SandboxError

    monkeypatch.setenv("RAIKER_CONTAINER_IMAGE_ALLOWLIST", "alpine")

    def fake_runner(command: list[str], **kwargs: Any) -> dict[str, Any]:
        raise SandboxError("command_not_found:docker")

    executor = ContainerExecutionExecutor(tmp_path, runner=fake_runner)
    result = executor.execute(_fake_action("alpine", ["true"]), SimpleNamespace(principal_id="p"))  # type: ignore[arg-type]
    assert result.ok is False
    assert result.reason_code == "docker_unavailable"


def test_container_nonzero_exit_is_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAIKER_CONTAINER_IMAGE_ALLOWLIST", "alpine")

    def fake_runner(command: list[str], **kwargs: Any) -> dict[str, Any]:
        return {"returncode": 2, "stdout_bytes": 0, "stderr_bytes": 5, "truncated": False}

    executor = ContainerExecutionExecutor(tmp_path, runner=fake_runner)
    result = executor.execute(_fake_action("alpine", ["false"]), SimpleNamespace(principal_id="p"))  # type: ignore[arg-type]
    assert result.ok is False
    assert result.reason_code == "exit_code:2"
