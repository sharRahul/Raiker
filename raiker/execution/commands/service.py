from __future__ import annotations

import contextlib
import shlex
import threading
import weakref
from collections.abc import Callable
from pathlib import Path
from typing import Any

from raiker.contracts.ids import new_id, utc_now, utc_plus_seconds
from raiker.execution.commands.backends.base import CommandBackendError, UnavailableBackend
from raiker.execution.commands.backends.container import (
    PersistentContainerBackend,
    SubprocessContainerRuntime,
)
from raiker.execution.commands.backends.local import LocalStrictBackend
from raiker.execution.commands.backends.native import NativeSandboxBackend, NativeSandboxDriver
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
from raiker.execution.commands.supervisor_client import (
    SupervisorHandle,
    SupervisorUnavailable,
)
from raiker.execution.commands.supervisor_client import attach as attach_supervised
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
        #: Backends that hold state between runs, kept for the life of the
        #: service. See `_backend_for` for why this is exactly the container
        #: backends and nothing else.
        self._backends: dict[str, Any] = {}
        self._lock = threading.Lock()
        #: Set on shutdown so lease holders stop renewing immediately rather
        #: than sleeping out their interval while the runtime is going away.
        self._lease_stop = threading.Event()

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
        background: bool = False,
        interactive: bool = False,
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
        del command
        display = shlex.join(argv)
        if not display or any(char in display for char in "\r\n\0"):
            raise CommandServiceError("command_safe_display_invalid")
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
            executable_template="",
            argv_template=tuple(argv),
            safe_display=display,
            credential_bindings=(),
            shell=False,
            interactive=interactive,
            background=background,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
            environment_profile_id=profile.profile_id,
            network_policy_id=None,
            authority_kind=authority_kind,
            authority_id=authority_id,
        )
        backend_name = "local_strict" if profile.kind == "local" else profile.kind
        try:
            self.store.create(request)
        except SecretMaterialRejected as exc:
            raise CommandServiceError(str(exc)) from None
        # BUG-197 — name the backend on the row before anything is started, so a
        # run in flight already says what is running it. The receipt has always
        # carried this; the list the owner browses read an empty column, and two
        # surfaces describing the same run disagreed.
        self.store.record_backend(owner_principal_id, request.run_id, backend_name)
        self.store.transition(owner_principal_id, request.run_id, CommandState.QUEUED, CommandState.STARTING)

        def complete(state: CommandState, returncode: int | None, sink: _StoreSink) -> None:
            self._finalize(request, state, returncode, sink, backend_name)

        sink = _StoreSink(self.store, request, complete)
        isolation: dict[str, Any] = {}
        try:
            backend = self._backend_for(profile)
            # Optional per backend, and validated rather than trusted: a
            # backend that answers with something other than a mapping has not
            # produced evidence, and recording a placeholder would be worse than
            # recording nothing.
            produced = getattr(backend, "isolation_evidence", None)
            produced = produced(request) if callable(produced) else None
            if isinstance(produced, dict):
                isolation = dict(produced)
                self.store.record_isolation(owner_principal_id, request.run_id, isolation)
            handle = backend.start(request, sink)
        except CommandBackendError as exc:
            self._contain_start_failure(request, exc.reason_code, backend_name)
            raise CommandServiceError(exc.reason_code) from None
        except OSError:
            self._contain_start_failure(request, "command_launch_failed", backend_name)
            raise CommandServiceError("command_launch_failed") from None
        self.store.transition(owner_principal_id, request.run_id, CommandState.STARTING, CommandState.RUNNING)
        # BUG-194 — the restart-safe handle, written before the run is
        # observable. A supervised run whose handle landed after a crash would
        # be a live process this runtime could never prove was its own.
        supervisor_handle = getattr(handle, "handle", None)
        if isinstance(supervisor_handle, SupervisorHandle):
            self.store.record_backend_handle(
                owner_principal_id, request.run_id, supervisor_handle.to_dict()
            )
        with self._lock:
            self._active[request.run_id] = handle
            if handle.poll() is not None:
                self._active.pop(request.run_id, None)
        if background:
            self._hold_lease(request)
        return self.store.load(owner_principal_id, request.run_id)  # type: ignore[return-value]

    # ── Background lifecycle (BUG-194) ───────────────────────────────────────

    #: How long a background run's lease is good for, and how often the holder
    #: renews it. Renewing at a third of the term means two consecutive missed
    #: renewals still leave the run inside its lease, so a momentarily busy
    #: writer does not get a live command reaped out from under it.
    LEASE_SECONDS = 30.0

    def _hold_lease(self, request: CommandRequest) -> None:
        """Renew this run's lease for as long as it is really running.

        The thread is the *evidence*, not the mechanism: it can only renew while
        the process it is watching is alive and this runtime is up, so a lease
        that keeps moving forward is a live run and a lease that stops is not —
        including on a hard kill, where no handler of ours gets to run at all.
        """
        deadline = utc_plus_seconds(self.LEASE_SECONDS)
        self.store.renew_lease(request.owner_principal_id, request.run_id, deadline)

        def renew() -> None:
            while True:
                with self._lock:
                    handle = self._active.get(request.run_id)
                if handle is None or handle.poll() is not None:
                    return
                self.store.renew_lease(
                    request.owner_principal_id,
                    request.run_id,
                    utc_plus_seconds(self.LEASE_SECONDS),
                )
                if self._lease_stop.wait(self.LEASE_SECONDS / 3.0):
                    return

        thread = threading.Thread(target=renew, name=f"lease-{request.run_id}", daemon=True)
        thread.start()

    def poll(self, owner_principal_id: str, run_id: str) -> dict[str, Any]:
        """The current state of one run, without waiting for it.

        Reads the durable row rather than the in-memory handle, so a run that
        this process no longer supervises reports what it really is instead of
        "not found".
        """
        run = self.store.load(owner_principal_id, run_id)
        if run is None:
            raise CommandServiceError("command_run_not_found")
        receipt = self.store.get_receipt(owner_principal_id, run_id)
        with self._lock:
            supervised = run_id in self._active
        # A live run this process is not watching may still be reattachable —
        # that is what a restart looks like from here. Ask, once, before
        # reporting it unsupervised: "not supervised" and "not recoverable" were
        # the same answer before this change and are two different facts.
        if not supervised and run.state not in TERMINAL_COMMAND_STATES:
            supervised = self.reattach(run) is not None
        with self._lock:
            reattached = bool(getattr(self._active.get(run_id), "reattached", False))
        return {
            "run_id": run.run_id,
            "state": run.state.value,
            "running": run.state not in TERMINAL_COMMAND_STATES,
            "supervised": supervised,
            "reattached": reattached,
            "backend": run.backend,
            "safe_display": run.safe_display,
            "exit_code": run.exit_code,
            "termination_reason": run.termination_reason,
            "stdout_bytes": run.stdout_bytes,
            "stderr_bytes": run.stderr_bytes,
            "truncated": run.truncated,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "lease_expires_at": run.lease_expires_at,
            "receipt_digest": receipt.digest if receipt else None,
        }

    def read_log(
        self, owner_principal_id: str, run_id: str, *, after: int = 0, limit: int = 500
    ) -> dict[str, Any]:
        """A page of already-redacted output, resumable by sequence.

        `after` is the last sequence the caller has seen, which is what makes
        polling a long run cheap: each call returns only what is new, and
        `next_after` is what to pass next time.
        """
        if self.store.load(owner_principal_id, run_id) is None:
            raise CommandServiceError("command_run_not_found")
        chunks = self.store.read_output(owner_principal_id, run_id, after=after, limit=limit)
        return {
            "run_id": run_id,
            "after": after,
            "next_after": chunks[-1].sequence if chunks else after,
            "complete": len(chunks) < limit,
            "chunks": [
                {"sequence": chunk.sequence, "stream": chunk.stream, "text": chunk.text}
                for chunk in chunks
            ],
        }

    def wait(
        self, owner_principal_id: str, run_id: str, *, timeout_seconds: float = 30.0
    ) -> dict[str, Any]:
        """Block until this run is terminal, or say plainly that it is not yet.

        A timeout is not an error: the run is still going, and the caller is told
        so through `state` rather than through an exception it would have to
        distinguish from a real failure.
        """
        if timeout_seconds <= 0:
            raise CommandServiceError("command_wait_timeout_invalid")
        with self._lock:
            handle = self._active.get(run_id)
        if handle is not None:
            with contextlib.suppress(TimeoutError):
                handle.wait(timeout_seconds)
        return self.poll(owner_principal_id, run_id)

    def send_input(self, owner_principal_id: str, run_id: str, data: str) -> dict[str, Any]:
        """Type into a run that has a terminal (BUG-194).

        Refused for a run without a PTY rather than written to a pipe: a program
        that is not on a terminal is not reading line-by-line, so "input
        delivered" would be true of the bytes and false of the effect.
        """
        run = self.store.load(owner_principal_id, run_id)
        if run is None:
            raise CommandServiceError("command_run_not_found")
        if run.state in TERMINAL_COMMAND_STATES:
            raise CommandServiceError("command_run_already_complete")
        with self._lock:
            handle = self._active.get(run_id)
        if handle is None:
            # Typing into a run this runtime restarted away from is exactly the
            # case reattachment exists for.
            handle = self.reattach(run)
        if handle is None:
            raise CommandServiceError("command_backend_handle_unavailable")
        try:
            handle.write(data)
        except RuntimeError as exc:
            raise CommandServiceError(str(exc)) from None
        return {"run_id": run_id, "byte_count": len(data.encode("utf-8"))}

    def reconcile_leases(self, owner_principal_id: str) -> list[str]:
        """Reclaim every background run whose lease lapsed. Returns their ids.

        This is the half of background execution that makes it safe to offer at
        all: without it, a run whose supervisor died holds a sandbox grant that
        nothing ever takes back. A lapsed lease is treated as a lost run and gets
        the same honest receipt a restart produces — never a silent success.
        """
        reclaimed: list[str] = []
        for run in self.store.list_expired_leases(owner_principal_id):
            with self._lock:
                supervised = run.run_id in self._active
            # A lapsed lease is evidence that *this runtime* stopped watching,
            # not that the run stopped. If the run's supervisor still answers,
            # the right move is to take it back over — reclaiming a live run
            # because the runtime that was watching it restarted would kill work
            # this change exists to preserve.
            if not supervised and self.reattach(run) is not None:
                continue
            with self._lock:
                handle = self._active.pop(run.run_id, None)
            if handle is not None:
                with contextlib.suppress(Exception):
                    handle.terminate()
            current = self.store.load(owner_principal_id, run.run_id)
            if current is None or current.state in TERMINAL_COMMAND_STATES:
                continue
            self._recover_run(current, reason="command_background_lease_expired")
            reclaimed.append(run.run_id)
        return reclaimed

    def _backend_for(self, profile: ExecutionProfile) -> Any:
        """The backend for a profile, kept where keeping it is what makes the
        capability real.

        BUG-194 — a container backend holds the session's standing boundary in
        its own map, so building a fresh one per run would mean every run
        created a new container no matter what the naming said. Only container
        backends are held: a local backend has no cross-run state to keep, and a
        native one must *not* be kept, because its capability set comes from a
        probe whose answer can change between commands (see `_default_backend`).
        """
        if profile.kind != "container":
            return (
                self._backend_factory(profile)
                if self._backend_factory is not None
                else self._default_backend(profile)
            )
        with self._lock:
            backend = self._backends.get(profile.profile_id)
            if backend is None:
                backend = (
                    self._backend_factory(profile)
                    if self._backend_factory is not None
                    else self._default_backend(profile)
                )
                self._backends[profile.profile_id] = backend
            return backend

    def _default_backend(self, profile: ExecutionProfile) -> Any:
        if profile.kind == "local":
            return LocalStrictBackend()
        if profile.kind == "native":
            # The probe runs here rather than being cached from the environment
            # list: a receipt must not assert "network denied" from a
            # measurement taken before the firewall service was stopped.
            driver = NativeSandboxDriver(self.workspace_root)
            return NativeSandboxBackend(driver=driver, proof=driver.probe())
        if profile.kind == "container":
            return PersistentContainerBackend(
                runtime=SubprocessContainerRuntime(self.workspace_root),
                workspace_root=self.workspace_root,
                profile=profile,
            )
        return UnavailableBackend(f"{profile.kind}_command_supervisor_unavailable")

    def reset_environment(
        self, owner_principal_id: str, session_id: str, profile_id: str, *, recreate: bool
    ) -> bool:
        """Discard a session's persistent boundary (BUG-194).

        Returns whether a backend actually took the instruction. `False` means
        the selected profile has no boundary to reset — which the caller reports
        as a named refusal rather than as a reset that quietly did nothing.
        """
        resolution = (
            resolve_command_environment(
                self.sqlite, owner_principal_id, "shell", probe=self._profile_probe
            )
            if self._profile_probe is not None
            else resolve_command_environment(self.sqlite, owner_principal_id, "shell")
        )
        profile = resolution.profile
        if profile is None or profile.profile_id != profile_id:
            return False
        backend = self._backend_for(profile)
        reset = getattr(backend, "reset", None)
        if not callable(reset):
            return False
        reset(owner_principal_id, session_id, profile_id, recreate=recreate)
        return True

    def session_environment(
        self, owner_principal_id: str, session_id: str
    ) -> dict[str, Any] | None:
        """What persistent boundary this session is reusing, if any."""
        resolution = (
            resolve_command_environment(
                self.sqlite, owner_principal_id, "shell", probe=self._profile_probe
            )
            if self._profile_probe is not None
            else resolve_command_environment(self.sqlite, owner_principal_id, "shell")
        )
        profile = resolution.profile
        if profile is None:
            return None
        backend = self._backend_for(profile)
        describe = getattr(backend, "session_environment", None)
        if not callable(describe):
            return None
        described = describe(owner_principal_id, session_id)
        return dict(described) if isinstance(described, dict) else None

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
            evidence={
                "backend": backend_name,
                "profile_id": request.environment_profile_id,
                "template_digest": request.template_digest,
                "authority": {
                    "kind": request.authority_kind,
                    "id": request.authority_id,
                },
                **self.store.load_isolation(request.owner_principal_id, request.run_id),
            },
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
                # Two different claims, kept apart. `boundary_constructed` is
                # what this run's runner actually built; `probe_observations` is
                # what the host was measured to enforce, and when. Blending them
                # would let a receipt assert something about this command on the
                # strength of an earlier measurement of a different process.
                **self.store.load_isolation(request.owner_principal_id, request.run_id),
            },
        )
        self.store.finalize_with_receipt(request.owner_principal_id, request.run_id, state, receipt)
        # The handle authenticates to a channel that is about to stop existing.
        # Keeping it would be storage of a secret with no remaining purpose.
        self.store.clear_backend_handle(request.owner_principal_id, request.run_id)
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
            handle = self.reattach(run)
        if handle is None:
            self._recover_run(run)
        else:
            handle.terminate()
        return self.store.load(owner_principal_id, run_id) or run

    def recover_owner(self, owner_principal_id: str) -> None:
        """Pick up where a restart left off (BUG-194).

        Reattachment is attempted *before* recovery, and the order is the whole
        change: a run whose supervisor still answers is not lost, and declaring
        it lost first and asking afterwards would make the honest receipt into a
        wrong one.
        """
        for run in self.store.list_recoverable(owner_principal_id):
            with self._lock:
                active = run.run_id in self._active
            if active:
                continue
            if self.reattach(run) is not None:
                continue
            self._recover_run(run)

    # ── Restart reattachment (BUG-194) ───────────────────────────────────────

    def reattach(self, run: StoredCommandRun) -> Any | None:
        """Take a live supervised run back over, or return ``None``.

        ``None`` is the answer for every case where this runtime cannot *prove*
        the run is still its own: no stored handle, a locked vault it cannot
        read the instance key out of, a socket that is gone, or a socket that
        answered with a frame the key did not authenticate. Each of those ends
        in the same honest `lost` receipt a restart has always produced. What
        changed is that it is now the answer to a question that was asked,
        rather than the only answer available.
        """
        stored = self.store.load_backend_handle(run.owner_principal_id, run.run_id)
        if not stored:
            return None
        try:
            handle = SupervisorHandle.from_dict(stored)
        except SupervisorUnavailable:
            return None
        request = self._rebuild_request(run)
        if request is None:
            return None
        chunks = self.store.read_output(run.owner_principal_id, run.run_id, limit=5_000)
        sink = _StoreSink(
            self.store,
            request,
            lambda state, returncode, produced: self._finalize(
                request, state, returncode, produced, run.backend or "local_strict"
            ),
        )
        # Resume rather than replay. The sink's counters start where the store
        # already is, so a reattached run's totals are the run's totals and not
        # the second half's.
        sink.sequence = chunks[-1].sequence if chunks else 0
        sink.captured_bytes = chunks[-1].end_byte_offset if chunks else 0
        sink.stdout_bytes = run.stdout_bytes
        sink.stderr_bytes = run.stderr_bytes
        sink.truncated = run.truncated
        sink.redaction_count = run.redaction_count
        try:
            supervised = attach_supervised(
                handle,
                sink,
                max_output_bytes=request.max_output_bytes,
                after=sink.sequence,
            )
        except SupervisorUnavailable:
            return None
        with self._lock:
            self._active[run.run_id] = supervised
        self._hold_lease(request)
        return supervised

    def _rebuild_request(self, run: StoredCommandRun) -> CommandRequest | None:
        """Reconstruct the request a stored run was started from.

        Everything needed is already durable: the row carries the identity and
        the encrypted material carries the command. A row this cannot rebuild is
        one this runtime should not pretend to supervise.
        """
        try:
            material = self.store.execution_material(run.owner_principal_id, run.run_id)
        except Exception:  # noqa: BLE001 — a locked or unreadable vault is "no"
            return None
        try:
            return CommandRequest(
                run_id=run.run_id,
                owner_principal_id=run.owner_principal_id,
                acting_principal_id=run.acting_principal_id,
                session_id=run.session_id,
                turn_id=run.turn_id,
                action_id=run.action_id,
                repository_id=None,
                workspace_root=Path(str(material.get("workspace_root", self.workspace_root))),
                cwd=str(material.get("cwd", ".")),
                executable_template=str(material.get("executable_template", "")),
                argv_template=tuple(str(item) for item in material.get("argv_template", [])),
                safe_display=run.safe_display,
                credential_bindings=(),
                shell=bool(material.get("shell", False)),
                interactive=bool(material.get("interactive", False)),
                background=bool(material.get("background", False)),
                timeout_seconds=float(material.get("timeout_seconds", 30.0)),
                max_output_bytes=int(material.get("max_output_bytes", 100_000)),
                environment_profile_id=run.profile_id,
                network_policy_id=material.get("network_policy_id") or None,
                authority_kind=run.authority_kind,
                authority_id=run.authority_id,
            )
        except ValueError:
            return None

    def _recover_run(
        self,
        run: StoredCommandRun,
        *,
        reason: str = "command_backend_handle_unavailable_after_restart",
    ) -> None:
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
            termination_reason=reason,
            completed_at=utc_now(),
            evidence={
                "backend": run.backend or "unknown",
                "profile_id": run.profile_id,
                "template_digest": run.template_digest,
                "authority": {
                    "kind": run.authority_kind,
                    "id": run.authority_id,
                },
                "recovered": True,
            },
        )
        self.store.finalize_with_receipt(run.owner_principal_id, run.run_id, CommandState.LOST, receipt)

    def shutdown(self) -> None:
        self._lease_stop.set()
        with self._lock:
            handles = list(self._active.values())
        for handle in handles:
            handle.terminate()
            # A supervised run's process is not ours to leave standing. Killing
            # its child stops the work; releasing tells the supervisor nobody is
            # coming back, so it exits now rather than holding its linger window
            # open for a restart that is not happening.
            release = getattr(handle, "release", None)
            if callable(release):
                with contextlib.suppress(Exception):
                    release()
