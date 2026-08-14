from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.execution.commands.backends.base import CommandBackendError
from raiker.execution.commands.backends.local import LocalStrictBackend
from raiker.execution.commands.models import (
    TERMINAL_COMMAND_STATES,
    CommandChunk,
    CommandReceipt,
    CommandRequest,
    CommandState,
    StoredCommandRun,
)
from raiker.execution.commands.store import CommandStore, OutputQuotaExceeded
from raiker.execution.profiles import resolve_command_environment
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

    def __init__(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.sqlite = SQLiteStore(self.workspace_root)
        self.store = CommandStore(self.sqlite)
        self._active: dict[str, Any] = {}
        self._lock = threading.Lock()

    def start(
        self,
        *,
        owner_principal_id: str,
        acting_principal_id: str,
        session_id: str,
        command: str,
        argv: list[str],
        cwd: str = ".",
        timeout_seconds: float = 30.0,
        max_output_bytes: int = 100_000,
    ) -> StoredCommandRun:
        resolution = resolve_command_environment(
            self.sqlite, owner_principal_id, "shell"
        )
        if not resolution.available or resolution.profile is None:
            raise CommandServiceError(resolution.reason_code or "selected_environment_unavailable")
        profile = resolution.profile
        if profile.kind != "local":
            raise CommandServiceError(f"{profile.kind}_command_supervisor_unavailable")
        if not argv:
            raise CommandServiceError("command_argv_required")
        display = command.strip()
        if not display or any(char in display for char in "\r\n\0"):
            raise CommandServiceError("command_safe_display_invalid")
        request = CommandRequest(
            run_id=new_id("cmd_"),
            owner_principal_id=owner_principal_id,
            acting_principal_id=acting_principal_id,
            session_id=session_id,
            turn_id=new_id("turn_"),
            action_id=new_id("act_"),
            repository_id=None,
            workspace_root=self.workspace_root,
            cwd=cwd,
            executable_template="",
            argv_template=tuple(argv),
            safe_display=display,
            credential_bindings=(),
            shell=False,
            interactive=False,
            background=False,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
            environment_profile_id=profile.profile_id,
            network_policy_id=None,
        )
        self.store.create(request)
        self.store.transition(owner_principal_id, request.run_id, CommandState.QUEUED, CommandState.STARTING)

        def complete(state: CommandState, returncode: int | None, sink: _StoreSink) -> None:
            self._finalize(request, state, returncode, sink)

        sink = _StoreSink(self.store, request, complete)
        try:
            handle = LocalStrictBackend().start(request, sink)
        except CommandBackendError as exc:
            self._contain_start_failure(request, exc.reason_code)
            raise CommandServiceError(exc.reason_code) from None
        except OSError:
            self._contain_start_failure(request, "command_launch_failed")
            raise CommandServiceError("command_launch_failed") from None
        self.store.transition(owner_principal_id, request.run_id, CommandState.STARTING, CommandState.RUNNING)
        with self._lock:
            self._active[request.run_id] = handle
            if handle.poll() is not None:
                self._active.pop(request.run_id, None)
        return self.store.load(owner_principal_id, request.run_id)  # type: ignore[return-value]

    def _contain_start_failure(self, request: CommandRequest, reason: str) -> None:
        self.store.transition(
            request.owner_principal_id, request.run_id, CommandState.STARTING, CommandState.FINALIZING
        )
        receipt = CommandReceipt.create(
            run_id=request.run_id,
            state=CommandState.CONTAINED,
            exit_code=None,
            termination_reason=reason,
            completed_at=utc_now(),
            evidence={"backend": "local_strict", "profile_id": request.environment_profile_id},
        )
        self.store.finalize_with_receipt(
            request.owner_principal_id, request.run_id, CommandState.CONTAINED, receipt
        )

    def _finalize(
        self, request: CommandRequest, state: CommandState, returncode: int | None, sink: _StoreSink
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
                "backend": "local_strict",
                "profile_id": request.environment_profile_id,
                "template_digest": request.template_digest,
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
