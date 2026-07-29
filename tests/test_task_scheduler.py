from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager
from raiker.tasks.scheduler import TaskScheduler, _next_daily, run_outcome


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


def test_immediate_task_uses_its_pair_while_schedule_uses_global(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    session_id = "sess_inbox_principal_owner"
    store.create_session(session_id, str(tmp_path))
    manager = TaskManager(store, EventLogWriter(store))
    manager.create_task(
        session_id=session_id,
        title="Immediate",
        objective="Run now",
        scheduled_at="2020-01-01T09:00:00Z",
        model_profile="ollama-local-openai-compatible",
        model="gemma4:31b-cloud",
    )
    captured = []

    async def completed(_gateway, envelope):  # type: ignore[no-untyped-def]
        captured.append(envelope.options)
        return SimpleNamespace(status="completed", message="Finished safely.")

    monkeypatch.setattr("raiker.tasks.scheduler.AgentGateway.submit_prompt_async", completed)
    assert asyncio.run(TaskScheduler(tmp_path).run_due()) == 1
    assert captured[0].model_profile == "ollama-local-openai-compatible"
    assert captured[0].model == "gemma4:31b-cloud"

    manager.create_task(
        session_id=session_id,
        title="Scheduled",
        objective="Run later",
        scheduled_at="2020-01-02T09:00:00Z",
    )
    assert asyncio.run(TaskScheduler(tmp_path).run_due()) == 1
    assert captured[1].model_profile == ""
    assert captured[1].model == ""


# BUG-09 — a run must never end on a state the owner cannot account for. Every
# terminal status maps to a task status *and* a stated reason, and a turn that
# said nothing still leaves the owner something to read.
class TestRunOutcomeAlwaysStatesWhatHappened:
    def test_completed_keeps_the_turn_message(self) -> None:
        assert run_outcome("completed", "Filed the report.") == ("completed", "Filed the report.")

    def test_approval_is_not_a_failure(self) -> None:
        status, summary = run_outcome("needs_approval", "Approval required for local action.")
        assert status == "waiting_for_approval"
        assert summary == "Approval required for local action."

    def test_denied_is_a_failure_with_a_reason(self) -> None:
        assert run_outcome("denied", "")[0] == "failed"
        assert run_outcome("denied", "")[1] == "Policy denied an action this run needed."

    def test_a_silent_failure_still_states_something(self) -> None:
        assert run_outcome("failed", "   ") == ("failed", "The run failed without a stated reason.")

    def test_an_unrecognised_status_fails_closed_and_names_itself(self) -> None:
        status, summary = run_outcome("weird", "")
        assert status == "failed"
        assert "weird" in summary

    def test_a_long_message_is_bounded(self) -> None:
        assert len(run_outcome("completed", "x" * 900)[1]) == 500


def test_a_run_parked_on_an_approval_is_blocked_not_failed(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    session_id = "sess_inbox_principal_owner"
    store.create_session(session_id, str(tmp_path))
    task = TaskManager(store, EventLogWriter(store)).create_task(
        session_id=session_id, title="Publish", objective="Publish the note",
        scheduled_at="2020-01-01T09:00:00Z",
    )

    async def needs_approval(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(
            status="needs_approval",
            message="Approval required for local action. No command was executed.",
        )

    monkeypatch.setattr("raiker.tasks.scheduler.AgentGateway.submit_prompt_async", needs_approval)
    assert asyncio.run(TaskScheduler(tmp_path).run_due()) == 1

    saved = store.load_task(task.task_id)
    assert saved is not None and saved.status == "waiting_for_approval"
    assert saved.summary is not None and "Approval required" in saved.summary
    # The work is unfinished, so it is not stamped as having ended.
    assert saved.completed_at is None
    types = [row["event_type"] for row in store.list_event_index(session_id=session_id)]
    assert "task_blocked" in types and "task_failed" not in types


def test_a_failed_run_records_a_reason_even_when_the_turn_said_nothing(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    session_id = "sess_inbox_principal_owner"
    store.create_session(session_id, str(tmp_path))
    task = TaskManager(store, EventLogWriter(store)).create_task(
        session_id=session_id, title="Research", objective="Research",
        scheduled_at="2020-01-01T09:00:00Z",
    )

    async def silent_failure(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(status="failed", message="")

    monkeypatch.setattr("raiker.tasks.scheduler.AgentGateway.submit_prompt_async", silent_failure)
    assert asyncio.run(TaskScheduler(tmp_path).run_due()) == 1

    saved = store.load_task(task.task_id)
    assert saved is not None and saved.status == "failed"
    assert saved.summary == "The run failed without a stated reason."
    failures = [
        row for row in store.list_event_index(session_id=session_id)
        if row["event_type"] == "task_failed"
    ]
    assert len(failures) == 1


def test_a_recurring_cycle_that_did_not_complete_says_so(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    session_id = "sess_inbox_principal_owner"
    store.create_session(session_id, str(tmp_path))
    task = TaskManager(store, EventLogWriter(store)).create_task(
        session_id=session_id, title="Watch the build", objective="Watch it",
        scheduled_at="2020-01-01T09:00:00Z", recurrence="daily",
    )

    async def failed(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(status="failed", message="The model was unreachable.")

    monkeypatch.setattr("raiker.tasks.scheduler.AgentGateway.submit_prompt_async", failed)
    assert asyncio.run(TaskScheduler(tmp_path).run_due()) == 1

    saved = store.load_task(task.task_id)
    assert saved is not None and saved.status == "queued"
    assert saved.summary == "Last run did not complete: The model was unreachable."


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
