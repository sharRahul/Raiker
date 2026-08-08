from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from raiker.execution.container_tools import ContainerToolExecutor
from raiker.execution.profiles import ExecutionProfile
from raiker.execution.tool_bridge import execute_bridge_request

PROFILE = ExecutionProfile(
    "container-review",
    "container",
    runtime="podman",
    image="raiker-tools:approved",
    tools=("list_directory", "grep"),
    repository_access="read_only",
    writable_output=True,
)


def test_container_executor_has_a_clean_cold_import() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "from raiker.execution.container_tools import ContainerToolExecutor"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_bridge_executes_static_safe_tool_against_repository(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")

    result = execute_bridge_request(
        {
            "version": 1,
            "tool_name": "list_directory",
            "arguments": {"path": "."},
            "repository": str(tmp_path),
            "output": str(tmp_path / "out"),
        }
    )

    assert result == {"status": "success", "path": ".", "entries": ["README.md"]}


def test_bridge_refuses_tools_outside_static_registry(tmp_path: Path) -> None:
    result = execute_bridge_request(
        {
            "version": 1,
            "tool_name": "connector_read",
            "arguments": {},
            "repository": str(tmp_path),
            "output": str(tmp_path / "out"),
        }
    )

    assert result == {
        "status": "failed",
        "error": {"type": "container_profile_tool_unsupported"},
    }


def test_executor_sends_payload_on_stdin_and_cleans_scratch(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("RAIKER_CONTAINER_IMAGE_ALLOWLIST", "raiker-tools:approved")
    captured: dict[str, Any] = {}

    def runner(command: list[str], **kwargs: Any) -> dict[str, Any]:
        captured["command"] = command
        captured.update(kwargs)
        return {
            "returncode": 0,
            "stdout": '{"status":"success","path":".","entries":[]}',
            "stderr": "",
            "stdout_bytes": 43,
            "stderr_bytes": 0,
            "truncated": False,
        }

    executor = ContainerToolExecutor(tmp_path, PROFILE, runner=runner)
    result = executor.execute("list_directory", {"path": "."}, "act_1")

    assert result["status"] == "success"
    payload = json.loads(captured["stdin_text"])
    assert payload["tool_name"] == "list_directory"
    assert payload["repository"] == "/repository"
    assert "list_directory" not in captured["command"]
    command = captured["command"]
    assert "--interactive" in command
    assert command[command.index("--workdir") + 1] == "/repository"
    assert command[command.index("--env") + 1] == "PYTHONDONTWRITEBYTECODE=1"
    assert captured["allowlist"] == frozenset({"podman"})
    assert not (tmp_path / ".raiker" / "container-workspaces" / "act_1").exists()


def test_executor_refuses_malformed_bridge_response(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("RAIKER_CONTAINER_IMAGE_ALLOWLIST", "raiker-tools:approved")

    def runner(_command: list[str], **_kwargs: Any) -> dict[str, Any]:
        return {
            "returncode": 0,
            "stdout": "not json",
            "stderr": "",
            "stdout_bytes": 8,
            "stderr_bytes": 0,
            "truncated": False,
        }

    result = ContainerToolExecutor(tmp_path, PROFILE, runner=runner).execute(
        "list_directory", {"path": "."}, "act_2"
    )

    assert result == {
        "status": "failed",
        "error": {"type": "container_bridge_response_invalid"},
    }


def test_executor_refuses_disallowed_image_before_runtime(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("RAIKER_CONTAINER_IMAGE_ALLOWLIST", "different:approved")
    called = False

    def runner(_command: list[str], **_kwargs: Any) -> dict[str, Any]:
        nonlocal called
        called = True
        return {}

    result = ContainerToolExecutor(tmp_path, PROFILE, runner=runner).execute(
        "list_directory", {"path": "."}, "act_3"
    )

    assert result == {
        "status": "failed",
        "error": {"type": "container_image_not_allowed:container-review"},
    }
    assert called is False
