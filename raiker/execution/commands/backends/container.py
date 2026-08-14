from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Lock
from typing import Any, Protocol

from raiker.execution.commands.backends.base import CommandBackendError
from raiker.execution.commands.models import CommandFeatures, CommandRequest
from raiker.execution.commands.runner import CommandSink, MemoryCommandSink, StreamingCommandRunner
from raiker.execution.profiles import ExecutionProfile
from raiker.runtime.command_policy import sandbox_environment

EXPECTED_SUPERVISOR_DIGEST = "sha256:" + ("b" * 64)


def command_container_name(owner: str, session: str, profile: str, run_id: str) -> str:
    digest = hashlib.sha256(f"{owner}\0{session}\0{profile}\0{run_id}".encode()).hexdigest()[:24]
    return f"raiker-cmd-{digest}"


class ContainerRuntime(Protocol):
    def run(self, command: list[str]) -> dict[str, object]: ...


class SubprocessContainerRuntime:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()

    def run(self, command: list[str]) -> dict[str, object]:
        try:
            completed = subprocess.run(  # noqa: S603 - argv is backend-constructed
                command,
                cwd=self.workspace_root,
                env=sandbox_environment(workspace_root=self.workspace_root),
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise CommandBackendError("container_runtime_timeout") from exc
        except OSError as exc:
            raise CommandBackendError("container_runtime_unavailable") from exc
        return {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }


@dataclass(frozen=True)
class ContainerBackendHandle:
    run_id: str
    container_id: str
    container_name: str
    request_digest: str
    supervisor_digest: str
    cache_base_digest: str
    private_cache_volume: str
    owner_principal_id: str
    session_id: str
    profile_id: str

    def with_request_digest(self, value: str) -> ContainerBackendHandle:
        return replace(self, request_digest=value)


class ContainerCommandHandle:
    def __init__(
        self,
        backend_handle: ContainerBackendHandle,
        process: Any,
        runtime: ContainerRuntime,
        runtime_name: str,
    ) -> None:
        self.backend_handle = backend_handle
        self._process = process
        self._runtime = runtime
        self._runtime_name = runtime_name
        self._cleaned = False
        self._lock = Lock()

    def _cleanup(self) -> None:
        with self._lock:
            if self._cleaned:
                return
            self._runtime.run(
                [self._runtime_name, "rm", "--force", self.backend_handle.container_id]
            )
            self._cleaned = True

    def poll(self) -> Any:
        state = self._process.poll()
        if state is not None:
            self._cleanup()
        return state

    def wait(self, timeout: float | None = None) -> Any:
        state = self._process.wait(timeout)
        self._cleanup()
        return state

    def write(self, value: str | bytes) -> None:
        del value
        raise CommandBackendError("selected_environment_pty_unsupported")

    def terminate(self) -> None:
        self._process.terminate()
        self._cleanup()


class PersistentContainerBackend:
    features = CommandFeatures(
        shell=True,
        process_tree_stop=True,
    )

    def __init__(
        self,
        *,
        runtime: ContainerRuntime,
        workspace_root: Path,
        profile: ExecutionProfile,
        runner: Callable[..., Any] | None = None,
    ) -> None:
        self.runtime = runtime
        self.workspace_root = workspace_root.resolve()
        self.profile = profile
        self._runner = runner or StreamingCommandRunner().start
        self._handles: dict[str, ContainerBackendHandle] = {}
        self._credential_lease: tuple[str, str] | None = None
        self._blocked_deltas: set[tuple[str, str, str]] = set()
        self._preflight_workspace()
        self.mask_dir = self.workspace_root / ".raiker" / "command-empty-mask"
        self.mask_dir.mkdir(parents=True, exist_ok=True)
        with __import__("contextlib").suppress(OSError):
            self.mask_dir.chmod(0)

    def _preflight_workspace(self) -> None:
        for protected in (self.workspace_root / ".raiker", self.workspace_root / ".git"):
            if protected.is_symlink():
                raise CommandBackendError("container_protected_path_unsafe")

    def start(
        self, request: CommandRequest, sink: CommandSink | None = None
    ) -> ContainerCommandHandle:
        if request.environment_profile_id != self.profile.profile_id:
            raise CommandBackendError("selected_environment_mismatch")
        if request.shell or not request.argv_template:
            raise CommandBackendError("container_argv_required")
        if request.background:
            raise CommandBackendError("selected_environment_background_unsupported")
        if request.interactive:
            raise CommandBackendError("selected_environment_pty_unsupported")
        if request.network_policy_id:
            raise CommandBackendError("selected_environment_network_unsupported")
        if request.credential_bindings:
            raise CommandBackendError("selected_environment_credential_unsupported")
        if any(
            owner == request.owner_principal_id and profile == self.profile.profile_id
            for owner, profile, _run in self._blocked_deltas
        ):
            raise CommandBackendError("credential_delta_resolution_required")
        if self._credential_lease is not None:
            raise CommandBackendError("credential_environment_busy")
        if request.credential_bindings:
            self._credential_lease = (request.owner_principal_id, request.run_id)
        runtime = self.profile.runtime
        image = self.profile.image
        if runtime is None or image is None or "@sha256:" not in image:
            raise CommandBackendError("container_supervisor_image_unpinned")
        name = command_container_name(
            request.owner_principal_id,
            request.session_id,
            self.profile.profile_id,
            request.run_id,
        )
        private_cache = f"{name}-cache"
        cache_digest = hashlib.sha256(
            f"{request.owner_principal_id}\0{request.session_id}\0{self.profile.profile_id}".encode()
        ).hexdigest()
        command = self._create_command(request, name, private_cache, runtime, image)
        result = self.runtime.run(command)
        if int(str(result.get("returncode", 1))) != 0:
            self._release_credential_lease(request.run_id)
            raise CommandBackendError("container_create_failed")
        container_id = str(result.get("stdout") or "").strip()
        if not container_id:
            self._release_credential_lease(request.run_id)
            raise CommandBackendError("container_identity_missing")
        self.runtime.run([runtime, "start", container_id])
        handle = ContainerBackendHandle(
            request.run_id,
            container_id,
            name,
            request.template_digest,
            EXPECTED_SUPERVISOR_DIGEST,
            cache_digest,
            private_cache,
            request.owner_principal_id,
            request.session_id,
            self.profile.profile_id,
        )
        self._handles[request.run_id] = handle
        process = self._runner(
            request,
            [
                runtime,
                "exec",
                "-i",
                container_id,
                *request.argv_template,
            ],
            self.workspace_root,
            sandbox_environment(workspace_root=self.workspace_root),
            sink or MemoryCommandSink(),
            pty=False,
        )
        return ContainerCommandHandle(handle, process, self.runtime, runtime)

    def _create_command(
        self,
        request: CommandRequest,
        name: str,
        cache: str,
        runtime: str,
        image: str,
    ) -> list[str]:
        labels = {
            "raiker.owner": request.owner_principal_id,
            "raiker.session": request.session_id,
            "raiker.profile": self.profile.profile_id,
            "raiker.run": request.run_id,
            "raiker.request.digest": request.template_digest,
            "raiker.supervisor.digest": EXPECTED_SUPERVISOR_DIGEST,
        }
        command = [
            runtime,
            "create",
            "--name",
            name,
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            "1g",
            "--cpus",
            "2",
            "--pids-limit",
            "256",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=256m",
        ]
        for key, value in labels.items():
            command.extend(["--label", f"{key}={value}"])
        command.extend(
            [
                "--mount",
                f"type=bind,src={self.workspace_root},dst=/workspace",
                "--mount",
                f"type=bind,src={self.workspace_root / '.git'},dst=/workspace/.git,readonly",
                "--mount",
                f"type=bind,src={self.mask_dir},dst=/workspace/.raiker,readonly",
                "--mount",
                f"type=volume,src={cache},dst=/home/raiker/.cache",
                "--workdir",
                f"/workspace/{request.cwd}".rstrip("/"),
                image,
                "-c",
                "trap 'exit 0' TERM INT; while :; do sleep 3600; done",
            ]
        )
        entrypoint_index = command.index(image)
        command[entrypoint_index:entrypoint_index] = ["--entrypoint", "/bin/sh"]
        return command

    def attach(self, handle: ContainerBackendHandle) -> ContainerCommandHandle:
        expected = self._handles.get(handle.run_id)
        if expected != handle:
            raise CommandBackendError("container_identity_mismatch")
        raise CommandBackendError("container_reattach_unavailable")

    def complete(self, run_id: str) -> None:
        self._release_credential_lease(run_id)

    def _release_credential_lease(self, run_id: str) -> None:
        if self._credential_lease and self._credential_lease[1] == run_id:
            self._credential_lease = None

    def block_for_delta(self, owner: str, profile: str, run_id: str) -> None:
        self._blocked_deltas.add((owner, profile, run_id))

    def discard_delta(self, owner: str, run_id: str, *, decision_id: str) -> None:
        if not decision_id:
            raise CommandBackendError("credential_delta_decision_required")
        self._blocked_deltas = {
            item for item in self._blocked_deltas if not (item[0] == owner and item[2] == run_id)
        }
        self._release_credential_lease(run_id)

    def reset(self, owner: str, session: str, profile: str, *, recreate: bool) -> None:
        selected = [
            handle
            for handle in self._handles.values()
            if (handle.owner_principal_id, handle.session_id, handle.profile_id)
            == (owner, session, profile)
        ]
        runtime = self.profile.runtime or "docker"
        for handle in selected:
            self.runtime.run([runtime, "rm", "--force", handle.container_id])
            if recreate:
                self.runtime.run([runtime, "volume", "rm", handle.private_cache_volume])
            self._handles.pop(handle.run_id, None)
            self._release_credential_lease(handle.run_id)
