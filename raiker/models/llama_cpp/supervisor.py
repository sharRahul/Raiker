"""Keeping the owner's local models served: start, watch, recover, restore, stop.

:class:`raiker.models.local_runtime.ManagedLlamaRuntime` knows how to start and
stop a process in a slot. This module decides *what* to start and keeps it
honest afterwards:

* **Planned starts.** Every launch is sized by :mod:`.planner` against the
  memory free right now and the models already being served. A plan that does
  not fit is refused with ``local_runtime_insufficient_memory`` before a
  process exists, unless the owner allowed overcommit for that model.
* **Readiness.** A start is not "deployed" until ``/health`` answers and
  ``/v1/models`` names the slot's alias. A process that exits while loading is
  explained from its log (:func:`.process.classify_failure`).
* **Out-of-memory recovery.** A start that fails for memory is retried with
  fewer GPU layers, then a shorter context (:func:`.planner.reduced_for_retry`),
  up to :data:`MAX_OOM_RETRIES` times, and the owner is told what it ran with.
* **Crash recovery.** A server that dies after it was ready is restarted with
  exponential backoff; more than :data:`MAX_RESTARTS` crashes inside
  :data:`RESTART_WINDOW_SECONDS` marks the slot ``failed`` rather than looping.
  A server that stops answering health checks is restarted the same way.
* **Startup and shutdown.** Deployments are recorded per owner, so the servers
  the owner deployed come back when Raiker starts (:meth:`restore`); shutdown
  stops every server but keeps the records.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import httpx

from raiker.contracts.views import View
from raiker.models.llama_cpp import hardware, installer
from raiker.models.llama_cpp.planner import (
    LaunchPlan,
    MemoryBudget,
    ModelShape,
    RuntimeSettings,
    inspect_model,
    plan_launch,
    reduced_for_retry,
)
from raiker.models.llama_cpp.process import classify_failure, read_log_tail, reap_orphans
from raiker.models.local_runtime import ManagedLlamaRuntime

LOGGER = logging.getLogger(__name__)

MAX_RESTARTS = 3
RESTART_WINDOW_SECONDS = 600.0
MAX_OOM_RETRIES = 3
#: Consecutive failed health checks before a ready slot is called unhealthy,
#: and before it is restarted.
UNHEALTHY_AFTER = 3
RESTART_AFTER = 10
OUT_OF_MEMORY = "local_runtime_out_of_memory"


class LaunchRefused(RuntimeError):
    """A start that did not happen or did not become ready; ``str()`` is a code."""

    bounded_reason = True


def ready_budget_seconds(weights_bytes: int) -> float:
    """How long a model may take to load: a minute plus 20 s per GiB, at most 15 min."""
    return min(900.0, 60.0 + 20.0 * weights_bytes / hardware.GIB)


def probe_health(port: int, alias: str, *, timeout: float = 2.0) -> str:
    """``ready``, ``loading`` (503 while weights load) or ``down``."""
    origin = f"http://127.0.0.1:{port}"
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            health = client.get(f"{origin}/health")
            if health.status_code == 503:
                return "loading"
            if not health.is_success:
                return "down"
            models = client.get(f"{origin}/v1/models")
            ids = {str(item.get("id")) for item in models.json().get("data", [])}
            return "ready" if models.is_success and alias in ids else "loading"
    except (httpx.HTTPError, ValueError, AttributeError):
        return "down"


def default_budget(workspace_root: Path, backend: str, committed: int) -> MemoryBudget:
    """This machine's memory for ``backend``, preferring the engine's own device report."""
    profile = hardware.detect()
    free: int | None = None
    unified = backend == "metal"
    installed = installer.current(workspace_root)
    if installed is not None and installed.backend == backend and installed.devices:
        free = max(device.memory_free_bytes or 0 for device in installed.devices) or None
    if free is None:
        gpu = profile.gpu_for(backend)
        if gpu is not None:
            free = gpu.memory_free_bytes or (
                gpu.memory_total_bytes if gpu.unified_memory else None
            )
    return MemoryBudget(
        backend=backend,
        gpu_free_bytes=free if backend != "cpu" else None,
        unified=unified,
        available_memory_bytes=hardware.available_memory_bytes(),
        total_memory_bytes=profile.total_memory_bytes,
        committed_bytes=committed,
        cpu_cores=profile.cpu_cores,
    )


@dataclass
class _Deployment:
    owner: str
    slot: str
    model_id: str
    model_path: Path
    approved_roots: tuple[Path, ...]
    executable: Path
    backend: str
    shape: ModelShape
    settings: RuntimeSettings
    plan: LaunchPlan
    state: str = "starting"
    started_at: float = 0.0
    ready_at: float | None = None
    ready_deadline: float = 0.0
    crashes: list[float] = field(default_factory=list)
    restarts: int = 0
    health_failures: int = 0
    last_error: str | None = None
    retry_at: float | None = None
    oom_retries: int = 0
    #: A deploy request is waiting on this start itself; the monitor leaves it.
    waiting: bool = False


@dataclass(frozen=True)
class SlotHealth(View):
    slot_profile_id: str
    model_id: str
    model_path: str
    #: starting, ready, unhealthy, restarting, failed
    state: str
    endpoint: str | None
    pid: int | None
    restarts: int
    last_error: str | None
    backend: str
    plan: LaunchPlan
    log_path: str | None


class LlamaSupervisor:
    def __init__(
        self,
        runtime: ManagedLlamaRuntime,
        workspace_root: Path,
        *,
        budget_for: Callable[[str, int], MemoryBudget] | None = None,
        health: Callable[[int, str], str] = probe_health,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        interval: float = 2.0,
        persist: bool = True,
    ) -> None:
        self.runtime = runtime
        self.workspace_root = Path(workspace_root)
        self._budget_for = budget_for or (
            lambda backend, committed: default_budget(self.workspace_root, backend, committed)
        )
        self._health = health
        self._clock = clock
        self._sleep = sleep
        self._interval = interval
        self._persist = persist
        self._lock = threading.RLock()
        self._deployments: dict[str, _Deployment] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        #: Slots that could not be brought back at startup: model, path, reason.
        self._restore_failures: dict[str, tuple[str, str, str]] = {}

    # ── planning ──────────────────────────────────────────────────────

    def committed_bytes(self, *, excluding: str | None = None, model_path: Path | None = None) -> int:
        """Memory already promised to served models, other than the one named."""
        with self._lock:
            # Only the weights: they are memory-mapped, so "available memory"
            # still counts them as reclaimable cache. A server's KV cache and
            # buffers are ordinary allocations the measurement already excludes.
            return sum(
                deployment.plan.system_weights_bytes
                for deployment in self._deployments.values()
                if deployment.slot != excluding
                and (model_path is None or deployment.model_path != model_path)
                and deployment.state not in {"failed"}
            )

    def plan(
        self,
        model_path: Path,
        settings: RuntimeSettings,
        *,
        backend: str | None = None,
        slot: str | None = None,
        shape: ModelShape | None = None,
    ) -> LaunchPlan:
        resolved = backend or self.backend()
        committed = self.committed_bytes(excluding=slot, model_path=model_path.resolve())
        return plan_launch(
            shape or inspect_model(model_path), self._budget_for(resolved, committed), settings
        )

    def backend(self) -> str:
        """The backend the engine Raiker would start actually has."""
        resolved = installer.resolve_executable(self.workspace_root)
        if resolved.backend is not None:
            return resolved.backend
        # A llama-server the owner installed: its build is unknown, so plan for
        # the machine's best backend. Offload flags are ignored by a CPU build.
        return hardware.detect().recommended_backend

    # ── starting ──────────────────────────────────────────────────────

    def launch(
        self,
        *,
        owner: str,
        model_id: str,
        model_path: Path,
        settings: RuntimeSettings,
        approved_roots: tuple[Path, ...],
        profile_id: str | None = None,
        wait: bool = True,
        check_cancelled: Callable[[], None] | None = None,
    ) -> SlotHealth:
        resolved = installer.resolve_executable(self.workspace_root)
        if resolved.path is None:
            raise LaunchRefused("llama_server_missing")
        model = model_path.resolve()
        backend = resolved.backend or hardware.detect().recommended_backend
        shape = inspect_model(model)
        plan = self.plan(model, settings, backend=backend, slot=profile_id, shape=shape)
        if not plan.allowed:
            raise LaunchRefused("local_runtime_insufficient_memory")
        with self._lock:
            status = self.runtime.start(
                model,
                executable=Path(resolved.path),
                approved_roots=approved_roots,
                profile_id=profile_id,
                extra_args=plan.args,
            )
            now = self._clock()
            previous = self._deployments.get(status.slot)
            deployment = _Deployment(
                owner=owner,
                slot=status.slot,
                model_id=model_id,
                model_path=model,
                approved_roots=approved_roots,
                executable=Path(resolved.path),
                backend=backend,
                shape=shape,
                settings=settings,
                plan=plan,
                started_at=now,
                ready_deadline=now + ready_budget_seconds(shape.weights_bytes),
                waiting=wait,
                crashes=list(previous.crashes) if previous and previous.model_path == model else [],
            )
            self._deployments[status.slot] = deployment
        if not wait:
            return self.health(status.slot)
        try:
            self._wait_ready(deployment, check_cancelled)
        except BaseException:
            with self._lock:
                if self._deployments.get(deployment.slot) is deployment:
                    self._deployments.pop(deployment.slot, None)
            self.runtime.stop(deployment.slot)
            raise
        if self._persist:
            self._save_deployment(deployment)
        with self._lock:
            self._restore_failures.pop(deployment.slot, None)
        return self.health(deployment.slot)

    def _relaunch(self, deployment: _Deployment) -> None:
        """Start ``deployment`` again in its own slot, with its current settings."""
        deployment.plan = plan_launch(
            deployment.shape,
            self._budget_for(
                deployment.backend,
                self.committed_bytes(excluding=deployment.slot),
            ),
            deployment.settings,
        )
        self.runtime.start(
            deployment.model_path,
            executable=deployment.executable,
            approved_roots=deployment.approved_roots,
            profile_id=deployment.slot,
            extra_args=deployment.plan.args,
        )
        now = self._clock()
        deployment.state = "starting"
        deployment.started_at = now
        deployment.ready_at = None
        deployment.ready_deadline = now + ready_budget_seconds(deployment.shape.weights_bytes)
        deployment.health_failures = 0
        deployment.retry_at = None
        deployment.restarts += 1

    def _exit_reason(self, deployment: _Deployment) -> str:
        log_path = self.runtime.log_path(deployment.slot)
        return classify_failure(read_log_tail(log_path)) if log_path else "local_runtime_exited"

    def _step_down(self, deployment: _Deployment) -> bool:
        """Smaller settings after an out-of-memory start; False when none are left."""
        if deployment.oom_retries >= MAX_OOM_RETRIES:
            return False
        smaller = reduced_for_retry(deployment.settings, deployment.plan)
        if smaller is None:
            return False
        deployment.oom_retries += 1
        # Recovery may cross the overcommit line the owner did not open.
        deployment.settings = replace(smaller, allow_overcommit=deployment.settings.allow_overcommit)
        return True

    def _wait_ready(
        self, deployment: _Deployment, check_cancelled: Callable[[], None] | None
    ) -> None:
        slot = self.runtime.slot(deployment.slot)
        alias = slot.alias if slot else "local-gguf"
        while True:
            if check_cancelled is not None:
                check_cancelled()
            if not self.runtime.alive(deployment.slot):
                reason = self._exit_reason(deployment)
                deployment.last_error = reason
                if reason == OUT_OF_MEMORY and self._step_down(deployment):
                    LOGGER.info("llama.cpp slot %s ran out of memory; retrying smaller", deployment.slot)
                    with self._lock:
                        self._relaunch(deployment)
                    continue
                raise LaunchRefused(reason)
            if self._clock() > deployment.ready_deadline:
                raise LaunchRefused("local_server_not_ready")
            port = self._port(deployment.slot)
            if port is not None and self._health(port, alias) == "ready":
                with self._lock:
                    deployment.state = "ready"
                    deployment.ready_at = self._clock()
                    deployment.waiting = False
                    deployment.health_failures = 0
                return
            self._sleep(0.25)

    def _port(self, slot_id: str) -> int | None:
        status = self.runtime.status(slot_id)
        if not status.endpoint:
            return None
        return int(status.endpoint.rsplit(":", 1)[1].split("/", 1)[0])

    # ── watching ──────────────────────────────────────────────────────

    def tick(self) -> None:
        """One pass over every deployment. The monitor thread calls this."""
        with self._lock:
            deployments = list(self._deployments.values())
        for deployment in deployments:
            if deployment.waiting or deployment.state == "failed":
                continue
            try:
                self._check(deployment)
            except Exception:  # noqa: BLE001 - one slot's trouble must not stop the watch
                LOGGER.exception("llama.cpp supervision of %s failed", deployment.slot)

    def _check(self, deployment: _Deployment) -> None:
        now = self._clock()
        with self._lock:
            if self._deployments.get(deployment.slot) is not deployment:
                return
            if deployment.state == "restarting":
                if deployment.retry_at is not None and now >= deployment.retry_at:
                    self._relaunch(deployment)
                return
            if not self.runtime.alive(deployment.slot):
                self._on_crash(deployment, self._exit_reason(deployment), now)
                return
        port = self._port(deployment.slot)
        slot = self.runtime.slot(deployment.slot)
        answer = self._health(port, slot.alias if slot else "local-gguf") if port else "down"
        with self._lock:
            if answer == "ready":
                if deployment.state != "ready":
                    deployment.ready_at = now
                deployment.state = "ready"
                deployment.health_failures = 0
                return
            if deployment.state == "starting":
                if now > deployment.ready_deadline:
                    self.runtime.stop(deployment.slot)
                    self._on_crash(deployment, "local_server_not_ready", now)
                return
            deployment.health_failures += 1
            if deployment.health_failures >= RESTART_AFTER:
                self.runtime.stop(deployment.slot)
                self._on_crash(deployment, "local_runtime_unresponsive", now)
            elif deployment.health_failures >= UNHEALTHY_AFTER:
                deployment.state = "unhealthy"

    def _on_crash(self, deployment: _Deployment, reason: str, now: float) -> None:
        deployment.last_error = reason
        deployment.crashes = [at for at in deployment.crashes if now - at < RESTART_WINDOW_SECONDS]
        if reason == OUT_OF_MEMORY and self._step_down(deployment):
            deployment.state = "restarting"
            deployment.retry_at = now + 1.0
            return
        if len(deployment.crashes) >= MAX_RESTARTS:
            deployment.state = "failed"
            LOGGER.warning("llama.cpp slot %s failed repeatedly (%s); not restarting", deployment.slot, reason)
            return
        deployment.crashes.append(now)
        deployment.state = "restarting"
        deployment.retry_at = now + 2.0 ** len(deployment.crashes)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="llama-supervisor", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            self.tick()

    # ── stopping ──────────────────────────────────────────────────────

    def stop_slot(self, slot_id: str, *, forget: bool = True) -> None:
        """Stop one slot because the owner asked; it will not be restored."""
        with self._lock:
            deployment = self._deployments.pop(slot_id, None)
            self.runtime.stop(slot_id)
        if forget and deployment is not None and self._persist:
            with contextlib.suppress(Exception):
                self._store().delete_local_runtime_deployment(deployment.owner, slot_id)

    def restart_slot(self, slot_id: str) -> SlotHealth:
        with self._lock:
            deployment = self._deployments.get(slot_id)
            if deployment is None:
                raise LaunchRefused("local_runtime_slot_not_deployed")
            deployment.crashes = []
            deployment.oom_retries = 0
            deployment.waiting = False
            self.runtime.stop(slot_id)
            self._relaunch(deployment)
        return self.health(slot_id)

    def shutdown(self) -> None:
        """Stop watching and stop every server; deployments stay recorded."""
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=10)
        with self._lock:
            self._deployments.clear()
            self.runtime.stop()

    # ── persistence and restore ───────────────────────────────────────

    def _store(self) -> Any:
        from raiker.storage.sqlite import SQLiteStore

        return SQLiteStore(self.workspace_root)

    def _save_deployment(self, deployment: _Deployment) -> None:
        with contextlib.suppress(Exception):
            self._store().save_local_runtime_deployment(
                deployment.owner, deployment.slot, deployment.model_id, str(deployment.model_path)
            )

    def restore(self, *, background: bool = True) -> threading.Thread | None:
        """Start again every model the owner had deployed when Raiker last ran."""
        with contextlib.suppress(Exception):
            reap_orphans(self.workspace_root)

        def work() -> None:
            from raiker.models.library import ModelLibraryService

            store = self._store()
            try:
                records = store.list_local_runtime_deployments()
            except Exception:  # noqa: BLE001 - a store that cannot be read restores nothing
                LOGGER.exception("llama.cpp deployments could not be read")
                return
            for record in records:
                if self._stop.is_set():
                    return
                owner = record["owner_principal_id"]
                path = Path(record["model_path"])
                try:
                    roots = tuple(Path(root) for root in ModelLibraryService(store).roots(owner))
                    settings = RuntimeSettings.from_mapping(
                        store.load_local_runtime_settings(owner, record["model_id"])
                    )
                    self.launch(
                        owner=owner,
                        model_id=record["model_id"],
                        model_path=path,
                        settings=settings,
                        approved_roots=roots,
                        profile_id=record["slot_profile_id"],
                    )
                    store.invalidate_model_readiness(
                        owner, record["slot_profile_id"], reason_code="local_runtime_restored"
                    )
                except Exception as exc:  # noqa: BLE001 - reported per slot, never raised
                    LOGGER.warning(
                        "llama.cpp slot %s was not restored: %s", record["slot_profile_id"], exc
                    )
                    with self._lock:
                        self._restore_failures[record["slot_profile_id"]] = (
                            record["model_id"],
                            str(path),
                            str(exc)
                            if isinstance(exc, (LaunchRefused, ValueError))
                            else "local_runtime_restore_failed",
                        )

        if not background:
            work()
            return None
        thread = threading.Thread(target=work, name="llama-restore", daemon=True)
        thread.start()
        return thread

    # ── reading ───────────────────────────────────────────────────────

    def health(self, slot_id: str) -> SlotHealth:
        with self._lock:
            deployment = self._deployments.get(slot_id)
            if deployment is None:
                raise LaunchRefused("local_runtime_slot_not_deployed")
            status = self.runtime.status(slot_id)
            log_path = self.runtime.log_path(slot_id)
            return SlotHealth(
                slot_profile_id=slot_id,
                model_id=deployment.model_id,
                model_path=str(deployment.model_path),
                state=deployment.state,
                endpoint=status.endpoint,
                pid=status.pid,
                restarts=deployment.restarts,
                last_error=deployment.last_error,
                backend=deployment.backend,
                plan=deployment.plan,
                log_path=str(log_path) if log_path else None,
            )

    def slots(self, owner: str | None = None) -> list[SlotHealth]:
        with self._lock:
            ids = [
                slot for slot, deployment in self._deployments.items()
                if owner is None or deployment.owner == owner
            ]
        return [self.health(slot) for slot in ids]

    def restore_failures(self) -> dict[str, tuple[str, str, str]]:
        with self._lock:
            return dict(self._restore_failures)
