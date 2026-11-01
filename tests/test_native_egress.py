"""The native backend gives a run its own download proxy only when the owner allows it."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from raiker.execution.commands.backends import native as native_backend
from raiker.execution.commands.egress_runtime import EgressSink, save_settings
from raiker.execution.commands.runner import MemoryCommandSink
from raiker.execution.workspaces import TaskWorkspaceRegistry
from tests.test_command_backends import _installed_runner, _probe_reply, request


def _backend(tmp_path: Path, workspace: Path, launched: list[dict[str, Any]], *, account: bool = True) -> Any:
    driver = native_backend.NativeSandboxDriver(
        workspace, helper_root=_installed_runner(tmp_path), run_probe=_probe_reply()
    )
    driver.account_base = lambda: tmp_path / "base" if account else None  # type: ignore[method-assign]

    def fake_runner(req: Any, argv: list[str], cwd: Path, env: dict[str, str], sink: Any, **_k: Any) -> Any:
        launched.append(
            {"policy": json.loads(Path(argv[2]).read_text(encoding="utf-8")), "env": env, "sink": sink}
        )
        return object()

    return native_backend.NativeSandboxBackend(
        driver=driver,
        proof=driver.probe(),
        workspaces=TaskWorkspaceRegistry(tmp_path / "copies"),
        runner=fake_runner,
    )


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "ws"
    (workspace / ".raiker").mkdir(parents=True)
    return workspace


def test_without_the_owners_switch_the_run_has_no_network(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    launched: list[dict[str, Any]] = []
    _backend(tmp_path, workspace, launched).start(request(workspace))
    assert launched[0]["policy"]["network"] == "none"
    assert "HTTPS_PROXY" not in launched[0]["env"]
    assert not isinstance(launched[0]["sink"], EgressSink)


def test_allowed_downloads_route_the_run_through_its_own_proxy(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    save_settings(workspace, True, ["pypi.org"])
    launched: list[dict[str, Any]] = []
    _backend(tmp_path, workspace, launched).start(request(workspace))

    [run] = launched
    assert run["policy"]["network"].startswith("proxy:127.0.0.1:")
    assert ("proxy_socket" in run["policy"]) is sys.platform.startswith("linux")
    assert run["env"]["HTTPS_PROXY"].startswith("http://cmd_backend:")
    sink = run["sink"]
    assert isinstance(sink, EgressSink)
    inner = MemoryCommandSink()
    sink._sink = inner
    sink.complete("succeeded", 0)
    assert inner.returncode == 0


@pytest.mark.skipif(sys.platform != "win32", reason="the AppContainer case is Windows only")
def test_windows_without_the_restricted_account_keeps_the_run_offline(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    save_settings(workspace, True, ["pypi.org"])
    launched: list[dict[str, Any]] = []
    _backend(tmp_path, workspace, launched, account=False).start(request(workspace))
    assert launched[0]["policy"]["network"] == "none"
