"""DEC-24 step 1 — a long scheduled run no longer holds up every other background pass.

The host tick awaited the scheduled-work pass, and a routine's run may last an
hour. For that hour approved work did not continue, no search index was
checked and no local model was watched — and after five minutes each of those
passes read as *not running* on the attention list. The pass now runs beside
the tick, one at a time, and while it is busy the tick says it is alive.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from raiker.api.instance_runtime import InstanceRuntime
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.storage.sqlite import SQLiteStore


class _SlowScheduler:
    def __init__(self) -> None:
        self.release = asyncio.Event()
        self.started = 0

    async def run_due(self) -> int:
        self.started += 1
        await self.release.wait()
        return 1


def _runtime(workspace: Path) -> InstanceRuntime:
    app: Any = SimpleNamespace(state=SimpleNamespace(workspace_root=workspace))
    return InstanceRuntime(app)


def test_the_pass_runs_beside_the_tick_one_at_a_time(tmp_path: Path) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    runtime = _runtime(tmp_path)
    scheduler = _SlowScheduler()

    async def scenario() -> None:
        runtime._start_due_work(scheduler)  # type: ignore[arg-type]
        await asyncio.sleep(0)
        # The tick has returned while the run is still going…
        assert scheduler.started == 1
        assert runtime._due_work is not None and not runtime._due_work.done()
        # …and the next tick neither waits for it nor starts a second.
        runtime._start_due_work(scheduler)  # type: ignore[arg-type]
        await asyncio.sleep(0)
        assert scheduler.started == 1
        scheduler.release.set()
        assert runtime._due_work is not None
        await runtime._due_work
        # Once it has finished, the next tick starts the next pass.
        scheduler.release.clear()
        runtime._start_due_work(scheduler)  # type: ignore[arg-type]
        await asyncio.sleep(0)
        assert scheduler.started == 2
        scheduler.release.set()
        await runtime._due_work

    asyncio.run(scenario())


def test_a_busy_pass_reads_as_alive_not_stale(tmp_path: Path) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    runtime = _runtime(tmp_path)
    scheduler = _SlowScheduler()
    store = SQLiteStore(tmp_path)

    async def scenario() -> None:
        runtime._start_due_work(scheduler)  # type: ignore[arg-type]
        await asyncio.sleep(0)
        runtime._start_due_work(scheduler)  # type: ignore[arg-type]
        rows = {row["pass_name"]: row for row in store.list_background_worker_health()}
        assert rows["scheduled_tasks"]["state"] == "ok"
        scheduler.release.set()
        assert runtime._due_work is not None
        await runtime._due_work

    asyncio.run(scenario())
