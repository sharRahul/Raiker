from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager
from raiker.tasks.scheduler import TaskScheduler, _next_daily


def test_due_task_is_claimed_and_fails_closed_without_a_valid_owner(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.create_session("sess_inbox_missing", str(tmp_path))
    task = TaskManager(store, EventLogWriter(store)).create_task(
        session_id="sess_inbox_missing", title="Daily review", objective="Review",
        scheduled_at="2020-01-01T09:00:00Z",
    )

    assert asyncio.run(TaskScheduler(tmp_path).run_due()) == 1
    saved = store.load_task(task.task_id)
    assert saved is not None and saved.status == "failed"
    assert saved.summary == "Scheduled task has no valid owner."


def test_daily_recurrence_advances_to_a_future_run() -> None:
    assert _next_daily("2020-01-01T09:00:00Z") > "2026-07-15T00:00:00Z"


def test_due_task_runs_as_its_owner(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    session_id = "sess_inbox_principal_owner"
    store.create_session(session_id, str(tmp_path))
    task = TaskManager(store, EventLogWriter(store)).create_task(
        session_id=session_id, title="Review", objective="Review now",
        scheduled_at="2020-01-01T09:00:00Z",
    )

    async def completed(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(status="completed", message="Finished safely.")

    monkeypatch.setattr("raiker.tasks.scheduler.AgentGateway.submit_prompt_async", completed)
    assert asyncio.run(TaskScheduler(tmp_path).run_due()) == 1
    saved = store.load_task(task.task_id)
    assert saved is not None and saved.status == "completed"
    assert saved.summary == "Finished safely."


def test_background_agent_runs_until_the_governed_task_completes(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    session_id = "sess_inbox_principal_owner"
    store.create_session(session_id, str(tmp_path))
    task = TaskManager(store, EventLogWriter(store)).create_task(
        session_id=session_id, title="Research", objective="Research safely",
        scheduled_at="2020-01-01T09:00:00Z", recurrence="background",
    )

    async def completed(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(status="completed", message="One research cycle complete.")

    monkeypatch.setattr("raiker.tasks.scheduler.AgentGateway.submit_prompt_async", completed)
    asyncio.run(TaskScheduler(tmp_path).run_due())
    saved = store.load_task(task.task_id)
    assert saved is not None and saved.status == "completed" and saved.recurrence == "background"
    assert saved.summary == "One research cycle complete."
