from __future__ import annotations

import threading
import weakref
from collections.abc import Callable
from pathlib import Path
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.execution.commands.backends.base import CommandBackendError, UnavailableBackend
from raiker.execution.commands.backends.container import (
    PersistentContainerBackend,
    SubprocessContainerRuntime,
)
from raiker.execution.commands.backends.local import LocalStrictBackend
from raiker.execution.commands.models import (
    TERMINAL_COMMAND_STATES,
    CommandChunk,
    CommandReceipt,
    CommandRequest,
    CommandState,
    StoredCommandRun,
)
from raiker.execution.commands.store import (
    CommandStore,
    OutputQuotaExceeded,
    SecretMaterialRejected,
)
from raiker.execution.profiles import ExecutionProfile, resolve_command_environment
from raiker.storage.sqlite import SQLiteStore


class CommandServiceError(RuntimeError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


class _StoreSink:
    def __init__(self, store: CommandStore, request: CommandRequest, on_complete: Any) -> None:
        self.store = store
        self.request = request
        self.on_complete = on_complete
        self.max_output_bytes = request.max_output_bytes
        self.stdout_bytes = 0
        self.stderr_bytes = 0
        self.captured_bytes = 0
        self.truncated = False
        self.redaction_count = 0
        self.sequence = 0
        self._lock = threading.Lock()

    def configure_limit(self, limit: int) -> None:
        self.max_output_bytes = limit

    def record_raw(self, stream: str, byte_count: int) -> None:
        if stream == "stderr":
            self.stderr_bytes += byte_count
        else:
            self.stdout_bytes += byte_count

    def append_safe(self, stream: str, data: bytes) -> None:
        with self._lock:
            remaining = max(0, self.max_output_bytes - self.captured_bytes)
            selected = data[:remaining]
            if len(selected) < len(data):
                self.truncated = True
            if not selected:
                return
            # The capture boundary may land in a multi-byte code point. Drop only
            # that incomplete suffix so the persisted byte count never exceeds
            # the owner's hard cap.
            text = selected.decode("utf-8", errors="ignore")
            byte_count = len(text.encode("utf-8"))
            self.sequence += 1
            try:
                self.store.append_chunk(
                    self.request.owner_principal_id,
                    CommandChunk(
                        run_id=self.request.run_id,
                        sequence=self.sequence,
                        stream=stream,
                        text=text,
                        byte_count=byte_count,
                        emitted_at=utc_now(),
                    ),
                )
                self.captured_bytes += byte_count
            except OutputQuotaExceeded:
                self.truncated = True

    def mark_redactions(self, count: int) -> None:
        self.redaction_count += count

    def record_input(self, byte_count: int) -> None:
        del byte_count

    def complete(self, state: CommandState, returncode: int | None) -> None:
        self.store.update_runtime_summary(
            self.request.owner_principal_id,
            self.request.run_id,
            stdout_bytes=self.stdout_bytes,
            stderr_bytes=self.stderr_bytes,
            truncated=self.truncated,
            redaction_count=self.redaction_count,
        )
        self.on_complete(state, returncode, self)


class CommandService:
    """Owner-scoped lifecycle facade over the governed command runner."""

    _instances: weakref.WeakValueDictionary[str, CommandService] = (
        weakref.WeakValueDictionary()
    )
    _instances_lock = threading.Lock()

    @classmethod
    def for_workspace(cls, workspace_root: str | Path) -> CommandService:
        key = str(Path(workspace_root).resolve())
        with cls._instances_lock:
            service = cls._instances.get(key)
            if service is None:
                service = cls(key)
                cls._instances[key] = service
            return service

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        profile_probe: Callable[[ExecutionProfile], Any] | None = None,
        backend_factory: Callable[[ExecutionProfile], Any] | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.sqlite = SQLiteStore(self.workspace_root)
        self.store = CommandStore(self.sqlite)
        self._profile_probe = profile_probe
        self._backend_factory = backend_factory
        self._active: dict[str, Any] = {}
        self._lock = threading.Lock()

    def start(
        self,
        *,
        owner_principal_id: str,
        acting_principal_id: str,
        session_id: str,
        turn_id: str,
        action_id: str,
        authority_kind: str,
        authority_id: str,
        command: str,
        argv: list[str],
        cwd: str = ".",
        timeout_seconds: float = 30.0,
        max_output_bytes: int = 100_000,
    ) -> StoredCommandRun:
        resolution = (
            resolve_command_environment(
                self.sqlite,
                owner_principal_id,
                "shell",
                probe=self._profile_probe,
            )
            if self._profile_probe is not None
            else resolve_command_environment(self.sqlite, owner_principal_id, "shell")
        )
        if not resolution.available or resolution.profile is None:
            raise CommandServiceError(resolution.reason_code or "selected_environment_unavailable")
        profile = resolution.profile
        if not argv:
            raise CommandServiceError("command_argv_required")
        display = command.strip()
        if not display or any(char in display for char in "\r\n\0"):
            raise CommandServiceError("command_safe_display_invalid")
        shell = profile.kind == "container"
        request = CommandRequest(
            run_id=new_id("cmd_"),
            owner_principal_id=owner_principal_id,
            acting_principal_id=acting_principal_id,
            session_id=session_id,
            turn_id=turn_id,
            action_id=action_id,
            repository_id=None,
            workspace_root=self.workspace_root,
            cwd=cwd,
            executable_template=display if shell else "",
            argv_template=() if shell else tuple(argv),
            safe_display=display,
            credential_bindings=(),
            shell=shell,
            interactive=False,
            background=False,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
            environment_profile_id=profile.profile_id,
            network_policy_id=None,
            authority_kind=authority_kind,
            authority_id=authority_id,
        )
        try:
            self.store.create(request)
        except SecretMaterialRejected as exc:
            raise CommandServiceError(str(exc)) from None
        self.store.transition(owner_principal_id, request.run_id, CommandState.QUEUED, CommandState.STARTING)

        def complete(state: CommandState, returncode: int | None, sink: _StoreSink) -> None:
            self._finalize(request, state, returncode, sink, backend_name)

        sink = _StoreSink(self.store, request, complete)
        backend_name = "local_strict" if profile.kind == "local" else profile.kind
        try:
            backend = (
                self._backend_factory(profile)
                if self._backend_factory is not None
                else self._default_backend(profile)
            )
            handle = backend.start(request, sink)
        except CommandBackendError as exc:
            self._contain_start_failure(request, exc.reason_code, backend_name)
            raise CommandServiceError(exc.reason_code) from None
        except OSError:
            self._contain_start_failure(request, "command_launch_failed", backend_name)
            raise CommandServiceError("command_launch_failed") from None
        self.store.transition(owner_principal_id, request.run_id, CommandState.STARTING, CommandState.RUNNING)
        with self._lock:
            self._active[request.run_id] = handle
            if handle.poll() is not None:
                self._active.pop(request.run_id, None)
        return self.store.load(owner_principal_id, request.run_id)  # type: ignore[return-value]

    def _default_backend(self, profile: ExecutionProfile) -> Any:
        if profile.kind == "local":
            return LocalStrictBackend()
        if profile.kind == "container":
            return PersistentContainerBackend(
                runtime=SubprocessContainerRuntime(self.workspace_root),
                workspace_root=self.workspace_root,
                profile=profile,
            )
        return UnavailableBackend(f"{profile.kind}_command_supervisor_unavailable")

    def run_foreground(self, **kwargs: Any) -> dict[str, Any]:
        run = self.start(**kwargs)
        with self._lock:
            handle = self._active.get(run.run_id)
        if handle is not None:
            handle.wait(float(kwargs.get("timeout_seconds", 30.0)) + 5.0)
        owner = str(kwargs["owner_principal_id"])
        current = self.store.load(owner, run.run_id)
        if current is None:
            raise CommandServiceError("command_run_not_found")
        chunks = self.store.read_output(owner, run.run_id)
        receipt = self.store.get_receipt(owner, run.run_id)
        return {
            "run_id": run.run_id,
            "returncode": current.exit_code,
            "stdout": "".join(chunk.text for chunk in chunks if chunk.stream == "stdout"),
            "stderr": "".join(chunk.text for chunk in chunks if chunk.stream == "stderr"),
            "stdout_bytes": current.stdout_bytes,
            "stderr_bytes": current.stderr_bytes,
            "truncated": current.truncated,
            "state": current.state.value,
            "receipt_digest": receipt.digest if receipt else None,
        }

    def _contain_start_failure(
        self, request: CommandRequest, reason: str, backend_name: str
    ) -> None:
        self.store.transition(
            request.owner_principal_id, request.run_id, CommandState.STARTING, CommandState.FINALIZING
        )
        receipt = CommandReceipt.create(
            run_id=request.run_id,
            state=CommandState.CONTAINED,
            exit_code=None,
            termination_reason=reason,
            completed_at=utc_now(),
            evidence={"backend": backend_name, "profile_id": request.environment_profile_id},
        )
        self.store.finalize_with_receipt(
            request.owner_principal_id, request.run_id, CommandState.CONTAINED, receipt
        )

    def _finalize(
        self,
        request: CommandRequest,
        state: CommandState,
        returncode: int | None,
        sink: _StoreSink,
        backend_name: str,
    ) -> None:
        run = self.store.load(request.owner_principal_id, request.run_id)
        if run is None or run.state in TERMINAL_COMMAND_STATES:
            return
        if run.state is CommandState.STARTING:
            self.store.transition(request.owner_principal_id, request.run_id, CommandState.STARTING, CommandState.FINALIZING)
        elif run.state is CommandState.RUNNING:
            self.store.transition(request.owner_principal_id, request.run_id, CommandState.RUNNING, CommandState.FINALIZING)
        receipt = CommandReceipt.create(
            run_id=request.run_id,
            state=state,
            exit_code=returncode,
            termination_reason=state.value,
            completed_at=utc_now(),
            evidence={
                "backend": backend_name,
                "profile_id": request.environment_profile_id,
                "template_digest": request.template_digest,
                "authority": {
                    "kind": request.authority_kind,
                    "id": request.authority_id,
                },
                "output_truncated": sink.truncated,
                "redaction_count": sink.redaction_count,
            },
        )
        self.store.finalize_with_receipt(request.owner_principal_id, request.run_id, state, receipt)
        with self._lock:
            self._active.pop(request.run_id, None)

    def stop(self, owner_principal_id: str, run_id: str) -> StoredCommandRun:
        run = self.store.load(owner_principal_id, run_id)
        if run is None:
            raise CommandServiceError("command_run_not_found")
        if run.state in TERMINAL_COMMAND_STATES:
            return run
        with self._lock:
            handle = self._active.get(run_id)
        if handle is None:
            self._recover_run(run)
        else:
            handle.terminate()
        return self.store.load(owner_principal_id, run_id) or run

    def recover_owner(self, owner_principal_id: str) -> None:
        for run in self.store.list_recoverable(owner_principal_id):
            with self._lock:
                active = run.run_id in self._active
            if not active:
                self._recover_run(run)

    def _recover_run(self, run: StoredCommandRun) -> None:
        current = run.state
        if current is CommandState.QUEUED:
            self.store.transition(run.owner_principal_id, run.run_id, current, CommandState.STARTING)
            current = CommandState.STARTING
        if current is CommandState.STARTING or current is CommandState.RUNNING:
            self.store.transition(run.owner_principal_id, run.run_id, current, CommandState.FINALIZING)
        receipt = CommandReceipt.create(
            run_id=run.run_id,
            state=CommandState.LOST,
            exit_code=None,
            termination_reason="command_backend_handle_unavailable_after_restart",
            completed_at=utc_now(),
            evidence={"backend": run.backend or "unknown", "recovered": True},
        )
        self.store.finalize_with_receipt(run.owner_principal_id, run.run_id, CommandState.LOST, receipt)

    def shutdown(self) -> None:
        with self._lock:
            handles = list(self._active.values())
        for handle in handles:
            handle.terminate()
