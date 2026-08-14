from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from raiker.execution.commands import CommandRequest
from raiker.execution.commands.backends import CommandBackendError
from raiker.execution.commands.backends.container import (
    EXPECTED_SUPERVISOR_DIGEST,
    PersistentContainerBackend,
    SubprocessContainerRuntime,
    command_container_name,
)
from raiker.execution.commands.runner import MemoryCommandSink
from raiker.execution.profiles import ExecutionProfile


class RecordingRuntime:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.counter = 0

    def run(self, command: list[str]) -> dict[str, object]:
        self.calls.append(command)
        if command[1:3] == ["create", "--name"]:
            self.counter += 1
            return {"returncode": 0, "stdout": f"container-{self.counter}\n", "stderr": ""}
        return {"returncode": 0, "stdout": "", "stderr": ""}


def test_subprocess_runtime_uses_fixed_argv_and_secret_free_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    completed = Mock(returncode=0, stdout="container-id\n", stderr="")
    launched = Mock(return_value=completed)
    monkeypatch.setattr("subprocess.run", launched)

    result = SubprocessContainerRuntime(tmp_path).run(["docker", "info"])

    assert result["stdout"] == "container-id\n"
    assert launched.call_args.args[0] == ["docker", "info"]
    assert "OPENAI_API_KEY" not in launched.call_args.kwargs["env"]


def request(tmp_path: Path, **overrides: object) -> CommandRequest:
    values: dict[str, object] = {
        "run_id": "cmd_1",
        "owner_principal_id": "owner_a",
        "acting_principal_id": "agent_a",
        "session_id": "sess_a",
        "turn_id": "turn_a",
        "action_id": "act_a",
        "repository_id": None,
        "workspace_root": tmp_path,
        "cwd": ".",
        "executable_template": "",
        "argv_template": ("printf", "%s", "hello world"),
        "safe_display": "printf hello",
        "credential_bindings": (),
        "shell": False,
        "interactive": False,
        "background": False,
        "timeout_seconds": 30.0,
        "max_output_bytes": 100_000,
        "environment_profile_id": "container_a",
        "network_policy_id": None,
    }
    values.update(overrides)
    return CommandRequest(**values)  # type: ignore[arg-type]


def profile() -> ExecutionProfile:
    return ExecutionProfile(
        "container_a",
        "container",
        runtime="docker",
        image="raiker-command-sandbox@sha256:" + ("a" * 64),
        tools=("shell",),
        repository_access="read_only",
        writable_output=True,
        credential_delivery=True,
        credential_delta_quarantine=True,
    )


def test_session_cache_is_reused_but_each_run_has_an_isolated_worker(tmp_path: Path) -> None:
    runtime = RecordingRuntime()
    backend = PersistentContainerBackend(runtime=runtime, workspace_root=tmp_path, profile=profile())
    first = backend.start(request(tmp_path))
    second = backend.start(request(tmp_path, run_id="cmd_2", action_id="act_2"))

    creates = [call for call in runtime.calls if call[1] == "create"]
    assert len(creates) == 2
    create = creates[0]
    assert create[create.index("--network") + 1] == "none"
    assert "--read-only" in create
    assert create[create.index("--cap-drop") + 1] == "ALL"
    assert create[create.index("--security-opt") + 1] == "no-new-privileges"
    assert f"raiker.supervisor.digest={EXPECTED_SUPERVISOR_DIGEST}" in create
    mounts = [create[index + 1] for index, value in enumerate(create) if value == "--mount"]
    assert any("dst=/workspace/.git,readonly" in mount for mount in mounts)
    assert any("dst=/workspace/.raiker,readonly" in mount for mount in mounts)
    assert first.backend_handle.container_id != second.backend_handle.container_id
    assert first.backend_handle.cache_base_digest == second.backend_handle.cache_base_digest
    assert first.backend_handle.private_cache_volume != second.backend_handle.private_cache_volume


def test_container_name_is_stable_safe_and_run_specific() -> None:
    one = command_container_name("owner a", "session/a", "container", "cmd_1")
    two = command_container_name("owner a", "session/a", "container", "cmd_2")
    assert one.startswith("raiker-cmd-") and len(one) == 35
    assert one != two


def test_unproved_interactive_network_and_credential_features_fail_closed(tmp_path: Path) -> None:
    runtime = RecordingRuntime()
    backend = PersistentContainerBackend(runtime=runtime, workspace_root=tmp_path, profile=profile())
    with pytest.raises(CommandBackendError, match="selected_environment_background_unsupported"):
        backend.start(request(tmp_path, background=True))
    with pytest.raises(CommandBackendError, match="selected_environment_pty_unsupported"):
        backend.start(request(tmp_path, interactive=True))
    with pytest.raises(CommandBackendError, match="selected_environment_network_unsupported"):
        backend.start(request(tmp_path, network_policy_id="filtered"))
    with pytest.raises(CommandBackendError, match="selected_environment_credential_unsupported"):
        backend.start(
            request(
                tmp_path,
                credential_bindings=({"credential_id": "cred_1", "environment_name": "TOKEN"},),
            )
        )


def test_unresolved_delta_blocks_later_worker_until_discard(tmp_path: Path) -> None:
    runtime = RecordingRuntime()
    backend = PersistentContainerBackend(runtime=runtime, workspace_root=tmp_path, profile=profile())
    backend.block_for_delta("owner_a", "container_a", "cmd_secret")
    with pytest.raises(CommandBackendError, match="credential_delta_resolution_required"):
        backend.start(request(tmp_path))
    backend.discard_delta("owner_a", "cmd_secret", decision_id="decision_1")
    assert backend.start(request(tmp_path)).backend_handle.container_id


def test_reset_processes_keeps_cache_and_recreate_removes_it(tmp_path: Path) -> None:
    runtime = RecordingRuntime()
    backend = PersistentContainerBackend(runtime=runtime, workspace_root=tmp_path, profile=profile())
    backend.start(request(tmp_path))
    backend.reset("owner_a", "sess_a", "container_a", recreate=False)
    assert any(call[1] == "rm" and "--force" in call for call in runtime.calls)
    assert not any(call[1] == "volume" and call[2] == "rm" for call in runtime.calls)

    backend.start(request(tmp_path, run_id="cmd_2", action_id="act_2"))
    backend.reset("owner_a", "sess_a", "container_a", recreate=True)
    assert any(call[1:3] == ["volume", "rm"] for call in runtime.calls)


def test_identity_mismatch_is_never_removed(tmp_path: Path) -> None:
    runtime = RecordingRuntime()
    backend = PersistentContainerBackend(runtime=runtime, workspace_root=tmp_path, profile=profile())
    handle = backend.start(request(tmp_path)).backend_handle
    with pytest.raises(CommandBackendError, match="container_identity_mismatch"):
        backend.attach(handle.with_request_digest("wrong"))
    assert not any(call[1] == "rm" for call in runtime.calls)


def test_foreground_command_preserves_exact_argv_and_stop_removes_worker(tmp_path: Path) -> None:
    runtime = RecordingRuntime()
    process = Mock()
    process.poll.return_value = None
    runner = Mock(return_value=process)
    backend = PersistentContainerBackend(
        runtime=runtime,
        workspace_root=tmp_path,
        profile=profile(),
        runner=runner,
    )
    command = request(tmp_path, background=False)

    handle = backend.start(command, MemoryCommandSink())

    exec_argv = runner.call_args.args[1]
    assert exec_argv[:3] == ["docker", "exec", "-i"]
    assert exec_argv[-3:] == ["printf", "%s", "hello world"]
    handle.terminate()
    process.terminate.assert_called_once()
    assert any(call[1:3] == ["rm", "--force"] for call in runtime.calls)
