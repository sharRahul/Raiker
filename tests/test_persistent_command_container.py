from __future__ import annotations

from pathlib import Path

import pytest

from raiker.execution.commands import CommandRequest
from raiker.execution.commands.backends import CommandBackendError
from raiker.execution.commands.backends.container import (
    EXPECTED_SUPERVISOR_DIGEST,
    PersistentContainerBackend,
    command_container_name,
)
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
        "executable_template": "printf hello",
        "argv_template": (),
        "safe_display": "printf hello",
        "credential_bindings": (),
        "shell": True,
        "interactive": False,
        "background": True,
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


def test_credential_worker_holds_exclusive_environment_lease(tmp_path: Path) -> None:
    runtime = RecordingRuntime()
    backend = PersistentContainerBackend(runtime=runtime, workspace_root=tmp_path, profile=profile())
    credentialed = request(
        tmp_path,
        credential_bindings=({"credential_id": "cred_1", "environment_name": "TOKEN"},),
    )
    backend.start(credentialed)
    with pytest.raises(CommandBackendError, match="credential_environment_busy"):
        backend.start(request(tmp_path, run_id="cmd_2", action_id="act_2"))


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
