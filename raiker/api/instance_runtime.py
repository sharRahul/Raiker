"""Every background service one workspace needs, and whoever owns it starts it.

GCR-07. A second Raiker user on the same host is a second workspace: its own
``create_app()`` result, mounted at ``/instances/<name>`` with a Starlette
``Mount``. The background work that workspace needs — the fifteen-second task
tick, the approval-continuation worker, the model-capacity refresh, the
telemetry cadence and the attached-root watcher — all lived in that child app's
FastAPI ``lifespan``.

**Starlette runs a lifespan for the top-level application only.** A mounted
sub-application is routing, not a lifecycle: its lifespan is never entered. So a
secondary instance answered requests while none of its background work was
running. Its scheduled tasks never became due, an approval granted in its
browser waited for a sweep that did not exist, its telemetry never left, and a
folder attached to one of its projects was never re-read.

The services themselves were never the problem, so this module does not change
any of them. It gives them an owner: one object per workspace that starts them
and stops them, held by the root application for itself *and* for every instance
it mounts. Routing stays routing.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from raiker.storage.sqlite import SQLiteStore

if TYPE_CHECKING:  # pragma: no cover - import cycle only matters to the checker
    from fastapi import FastAPI

    from raiker.tasks.scheduler import TaskScheduler
    from raiker.tasks.wakeup import SchedulerWakeup

_LOG = logging.getLogger(__name__)

#: How long a host-tick pass waits before sweeping again, in seconds.
TICK_SECONDS = 15.0


class InstanceRuntime:
    """The background services of one workspace, started and stopped together.

    Constructed against the application that carries the workspace — the root
    app for the owner's own workspace, and the mounted child app for each
    instance beside it. :meth:`start` is idempotent and :meth:`aclose` is safe to
    call on a runtime that never started, because the root lifespan has to be
    able to unwind a partially started set.
    """

    def __init__(self, app: FastAPI, *, name: str = "") -> None:
        self.app = app
        #: The instance this runtime belongs to, for log lines. Empty for the
        #: owner's own workspace, which is the one an operator reads as "Raiker".
        self.name = name
        self.workspace_root = app.state.workspace_root
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []
        self._started = False
        self._resuming = asyncio.Lock()

    # ── the passes ──────────────────────────────────────────────────────────

    async def _contained(self, pass_name: str, work: Awaitable[Any]) -> None:
        """Run one host-tick pass, isolated from the others and *recorded*.

        GCR-38 — every pass used to be `with suppress(Exception)`. The
        isolation is right: a telemetry collector that is down must not stop
        due work from starting. Suppressing in silence was not: a pass could
        throw every fifteen seconds for days while the product reported a
        healthy host, because nothing counted it, nothing logged it, and no
        surface could show it. The exception is still swallowed — the tick
        must not die — and now it leaves a row and a log line behind.
        """
        store = SQLiteStore(self.workspace_root)
        try:
            await work
        except Exception as exc:  # noqa: BLE001 — the record below is the report
            _LOG.warning("background pass %s failed: %s", pass_name, type(exc).__name__)
            with suppress(Exception):
                store.record_background_pass(pass_name, error_class=type(exc).__name__)
            return
        with suppress(Exception):
            store.record_background_pass(pass_name)

    async def _resume_approved(self, scheduler: TaskScheduler) -> None:
        # One pass at a time, whichever worker asked for it. Exactly-once
        # resumption is enforced in the store by `claim_suspended_turn`, so this
        # is not a correctness lock — it keeps a nudge and a tick from doing the
        # same sweep twice and writing two identical "continuing" cards.
        async with self._resuming:
            await scheduler.resume_approved()

    async def _tick(self) -> None:
        from raiker.tasks.scheduler import TaskScheduler

        scheduler = TaskScheduler(self.workspace_root)
        while not self._stop.is_set():
            await self._contained("scheduled_tasks", scheduler.run_due())
            # Continuing approved work is a separate pass from starting due
            # work, and it is contained separately: a continuation that
            # throws must not stop the next tick from starting due runs, and
            # a failed due run must not stop approved work from finishing
            # (BUG-25).
            await self._contained("approved_continuations", self._resume_approved(scheduler))
            await self._contained("model_capacity_refresh", scheduler.refresh_model_capacities())
            # BUG-276 — the governed record leaves on the cadence its
            # destination carries, not only when somebody presses a button.
            # Contained on its own like every pass above it: a collector
            # that is down must not stop due work from starting.
            await self._contained("telemetry_delivery", scheduler.deliver_due_telemetry())
            with suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=TICK_SECONDS)

    async def _continuations(self) -> None:
        """Start explicitly requested work or a continuation without delay.

        The tick above still sweeps every 15 seconds and is what recovers a
        decision this worker never heard about (one made through another
        process, or while this pass was already running). This worker exists
        so the ordinary case — the owner grants an approval in the browser —
        does not wait for that sweep.
        """
        from raiker.tasks.scheduler import TaskScheduler

        wakeup: SchedulerWakeup = self.app.state.scheduler_wakeup
        scheduler = TaskScheduler(self.workspace_root)
        while not self._stop.is_set():
            if not await wakeup.wait(timeout=TICK_SECONDS):
                continue
            if self._stop.is_set():
                return
            # BUG-64 — the Run now route only records intent atomically;
            # this resident worker claims it through the ordinary scheduler.
            with suppress(Exception):
                await scheduler.run_due()
            with suppress(Exception):
                await self._resume_approved(scheduler)

    def _recover_abandoned_operations(self) -> None:
        """Settle durable rows whose in-process worker a restart took with it.

        GCR-25 — model pulls, conversions and deploys are durable rows driven
        by in-process workers. A host that stopped mid-download left the row
        behind and the worker with it, so the product came back showing
        `running` work nothing was advancing and a progress bar that would
        never move again. Settle them before the first request is served:
        each becomes a failed operation naming `host_restarted`, which is a
        state Retry can start from. Contained like every other pass — a
        recovery sweep that throws must not stop the host from booting.
        """
        from raiker.models.local_operations import ModelOperationService

        try:
            recovered = ModelOperationService(SQLiteStore(self.workspace_root)).recover_abandoned()
            if recovered:
                _LOG.info("recovered %d model operation(s) abandoned by a host restart", recovered)
        except Exception as exc:  # noqa: BLE001 — boot must not depend on this
            _LOG.warning("model-operation recovery failed: %s", type(exc).__name__)

    # ── lifecycle ───────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start this workspace's background work. Calling it twice is a no-op."""
        if self._started:
            return
        self._started = True
        self._recover_abandoned_operations()
        self._tasks = [
            asyncio.create_task(self._tick()),
            asyncio.create_task(self._continuations()),
        ]
        # A folder attached to a project is edited by whatever the owner uses,
        # and none of it tells Raiker anything. This worker is why an edit
        # reaches recall in seconds; the reconcile pass behind it is why recall
        # is still correct when watching fails.
        from raiker.knowledge.watcher import AttachedRootWatcher

        watcher = AttachedRootWatcher(self.workspace_root)
        self.app.state.attached_root_watcher = watcher
        self._tasks.append(asyncio.create_task(watcher.run(self._stop)))
        if self.name:
            _LOG.info("instance %s: background services started", self.name)

    async def aclose(self) -> None:
        """Stop the background work and release everything this workspace holds."""
        self._stop.set()
        with suppress(Exception):
            self.app.state.scheduler_wakeup.request()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with suppress(asyncio.CancelledError):
                await task
        self._tasks = []
        from raiker.storage.sqlite import invalidate_workspace_connections

        with suppress(Exception):
            self.app.state.managed_llama_runtime.stop()
        with suppress(Exception):
            self.app.state.managed_mlx_runtime.stop()

        command_service = getattr(self.app.state, "command_service", None)
        if command_service is not None:
            command_service.shutdown()

        invalidate_workspace_connections(self.workspace_root)
        self._started = False
