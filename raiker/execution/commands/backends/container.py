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


def command_container_name(owner: str, session: str, profile: str, run_id: str = "") -> str:
    """The container's name, derived from what it belongs to.

    BUG-194 — `run_id` is now optional, and leaving it out is what makes the
    boundary *persistent*: a name that is a function of owner, session and
    profile addresses one container for the whole session, so a second command
    in the same session lands in the environment the first one left behind
    rather than in a fresh one. Passing a `run_id` still produces a per-run
    name, which is what a run that must not share state asks for.

    The name is a digest rather than a readable label deliberately. It is not a
    secret — `docker ps` shows it — but it is not guessable either: producing it
    requires already knowing the owner and session ids, so a name cannot be used
    to *find* another owner's environment.
    """
    material = f"{owner}\0{session}\0{profile}" + (f"\0{run_id}" if run_id else "")
    digest = hashlib.sha256(material.encode()).hexdigest()[:24]
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
    """One command inside a container, without owning the container's life.

    BUG-194 — a handle used to remove the container the moment its command
    ended, which is what made the boundary per-run: nothing an installer, a
    build, or a `cd` did could survive into the next command, because there was
    nothing left for it to survive into. `persistent=True` keeps the container
    standing, so a session has one environment rather than a sequence of
    identical fresh ones. The container is still removed — by
    :meth:`PersistentContainerBackend.reset`, by the session ending, and by the
    owner asking — but never as a side effect of one command finishing.
    """

    def __init__(
        self,
        backend_handle: ContainerBackendHandle,
        process: Any,
        runtime: ContainerRuntime,
        runtime_name: str,
        *,
        persistent: bool = False,
    ) -> None:
        self.backend_handle = backend_handle
        self._process = process
        self._runtime = runtime
        self._runtime_name = runtime_name
        self._persistent = persistent
        self._cleaned = False
        self._lock = Lock()

    def _cleanup(self) -> None:
        if self._persistent:
            return
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
    # BUG-194 — `persistent_environment` is now a measured property of this
    # backend rather than an unbuilt row. A session gets one container, and the
    # state a command leaves in it is there for the next one. It is claimed only
    # here: the native sandbox still creates and deletes a profile around each
    # command, and says so.
    features = CommandFeatures(
        shell=True,
        process_tree_stop=True,
        persistent_environment=True,
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
        #: The session's standing boundary, keyed by what it belongs to. This is
        #: the whole of the persistence change: everything else follows from a
        #: second run finding an entry here instead of creating a container.
        self._sessions: dict[tuple[str, str, str], ContainerBackendHandle] = {}
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
        # BUG-194 — the session's boundary, reused. The name no longer carries
        # the run id, so the second command of a session addresses the container
        # the first one ran in; what that command installed, wrote to /tmp, or
        # left in the private cache is still there. That *is* the persistent
        # environment the entry asked for, and it is a container-session change
        # exactly as the entry said it would have to be.
        name = command_container_name(
            request.owner_principal_id, request.session_id, self.profile.profile_id
        )
        private_cache = f"{name}-cache"
        cache_digest = hashlib.sha256(
            f"{request.owner_principal_id}\0{request.session_id}\0{self.profile.profile_id}".encode()
        ).hexdigest()
        session_key = (
            request.owner_principal_id, request.session_id, self.profile.profile_id
        )
        existing = self._sessions.get(session_key)
        if existing is not None and not self._is_running(runtime, existing.container_id):
            # A container the owner or the host removed underneath us is not a
            # boundary any more. Forgetting it here is what stops the next run
            # from `exec`-ing into an id that no longer resolves and reporting
            # the resulting failure as the command's.
            self._sessions.pop(session_key, None)
            existing = None
        if existing is None:
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
            existing = ContainerBackendHandle(
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
            self._sessions[session_key] = existing
        handle = existing.with_request_digest(request.template_digest)
        self._handles[request.run_id] = handle
        process = self._runner(
            request,
            [
                runtime,
                "exec",
                "-i",
                existing.container_id,
                *request.argv_template,
            ],
            self.workspace_root,
            sandbox_environment(workspace_root=self.workspace_root),
            sink or MemoryCommandSink(),
            pty=False,
        )
        return ContainerCommandHandle(
            handle, process, self.runtime, runtime, persistent=True
        )

    def _is_running(self, runtime: str, container_id: str) -> bool:
        """Ask the runtime, rather than assume the map is the truth.

        The map records what Raiker created; whether it is still standing is a
        fact about the host, and the two diverge the moment anyone runs
        `docker rm`.
        """
        result = self.runtime.run(
            [runtime, "inspect", "--format", "{{.State.Running}}", container_id]
        )
        if int(str(result.get("returncode", 1))) != 0:
            return False
        return str(result.get("stdout") or "").strip().lower() == "true"

    def session_environment(
        self, owner: str, session: str
    ) -> dict[str, Any] | None:
        """What the owner is told about the boundary this session is reusing."""
        handle = self._sessions.get((owner, session, self.profile.profile_id))
        if handle is None:
            return None
        return {
            "profile_id": self.profile.profile_id,
            "container_name": handle.container_name,
            "cache_volume": handle.private_cache_volume,
            "running": self._is_running(self.profile.runtime or "docker", handle.container_id),
        }

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
        """Take a session's standing boundary away, on the owner's word.

        BUG-194 — persistence and reset are one control, not two features: an
        environment that accumulates state and can never be cleared is worse
        than one that never persists, because the owner has no way back to a
        known state. `recreate` additionally discards the private cache volume,
        which is the difference between "start this session's environment again"
        and "start it again from nothing".
        """
        runtime = self.profile.runtime or "docker"
        key = (owner, session, profile)
        standing = self._sessions.pop(key, None)
        selected = [
            handle
            for handle in self._handles.values()
            if (handle.owner_principal_id, handle.session_id, handle.profile_id) == key
        ]
        removed: set[str] = set()
        for handle in [*( [standing] if standing is not None else [] ), *selected]:
            if handle.container_id not in removed:
                self.runtime.run([runtime, "rm", "--force", handle.container_id])
                if recreate:
                    self.runtime.run([runtime, "volume", "rm", handle.private_cache_volume])
                removed.add(handle.container_id)
            self._handles.pop(handle.run_id, None)
            self._release_credential_lease(handle.run_id)
