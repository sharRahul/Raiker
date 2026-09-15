"""BUG-299 — a task's attempts have an address, and the address is its own events.

Three things had to become true. A cycle has to record that it *started*, or a
history is a list of endings. A routine's cycle has to record how it *settled*,
or every cycle of a daily agent reads as still running forever. And the grouping
has to be a read of the governed events rather than a second store, so the
timeline and the audit log cannot drift apart.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.contracts.models import User
from raiker.control.dashboard import DashboardService
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.history import derive_attempts, event_detail
from raiker.tasks.manager import TaskManager
from raiker.tasks.scheduler import TaskScheduler


def _event(event_type: str, timestamp: str, **payload: object) -> dict[str, object]:
    return {
        "event_id": f"evt_{event_type}_{timestamp}",
        "event_type": event_type,
        "timestamp": timestamp,
        "actor": "task_manager",
        "turn_id": None,
        "session_id": "sess_inbox_owner",
        "payload": payload,
    }


# ── grouping ────────────────────────────────────────────────────────────────


def test_filing_is_its_own_segment_and_the_first_run_is_attempt_one() -> None:
    attempts = derive_attempts(
        [
            _event("task_created", "2026-09-15T09:00:00Z", task_id="t", title="Nightly"),
            _event("task_started", "2026-09-15T09:05:00Z", task_id="t", trigger="schedule"),
            _event("task_completed", "2026-09-15T09:06:00Z", task_id="t", summary="Done."),
        ]
    )

    assert [(a.index, a.kind, a.outcome) for a in attempts] == [
        (0, "record", "recorded"),
        (1, "run", "completed"),
    ]
    assert attempts[1].summary == "Done."
    assert attempts[1].ended_at == "2026-09-15T09:06:00Z"


def test_a_parked_run_and_the_continuation_that_followed_are_separate_attempts() -> None:
    attempts = derive_attempts(
        [
            _event("task_started", "2026-09-15T09:00:00Z", task_id="t"),
            _event("task_blocked", "2026-09-15T09:01:00Z", task_id="t", reason="Waiting on you."),
            _event(
                "task_resume_started",
                "2026-09-15T09:10:00Z",
                task_id="t",
                tool_name="run_command",
                approval_id="apr_1",
            ),
            _event("task_completed", "2026-09-15T09:11:00Z", task_id="t", summary="Finished."),
        ]
    )

    assert [(a.index, a.kind, a.outcome) for a in attempts] == [
        (1, "run", "waiting_for_approval"),
        (2, "continuation", "completed"),
    ]
    # The decision that released the continuation is named on it, which is the
    # half of "what happened" a status line could never carry.
    assert attempts[1].approval_id == "apr_1"


def test_a_run_with_no_recorded_settlement_is_reported_as_still_running() -> None:
    """The honest answer, and the one `outcome_unknown` asked for a place to see."""
    attempts = derive_attempts(
        [
            _event("task_started", "2026-09-15T09:00:00Z", task_id="t"),
            _event("task_progress", "2026-09-15T09:02:00Z", task_id="t", current_step="Reading"),
        ]
    )

    assert attempts[0].outcome == "in_progress"
    assert attempts[0].ended_at is None
    assert attempts[0].summary == "Reading"


def test_a_cycle_landing_carries_its_own_outcome_and_never_the_tasks() -> None:
    attempts = derive_attempts(
        [
            _event("task_started", "2026-09-15T09:00:00Z", task_id="t"),
            _event(
                "task_cycle_landed",
                "2026-09-15T09:03:00Z",
                task_id="t",
                outcome="failed",
                summary="The provider refused.",
                next_run_at="2026-09-16T09:00:00Z",
            ),
        ]
    )

    assert attempts[0].outcome == "failed"
    assert attempts[0].summary == "The provider refused."


def test_an_unrecognised_cycle_outcome_is_recorded_rather_than_guessed() -> None:
    attempts = derive_attempts(
        [
            _event("task_started", "2026-09-15T09:00:00Z", task_id="t"),
            _event("task_cycle_landed", "2026-09-15T09:03:00Z", task_id="t", outcome="???"),
        ]
    )

    assert attempts[0].outcome == "recorded"


def test_an_owner_act_after_a_run_settled_is_not_folded_into_that_run() -> None:
    attempts = derive_attempts(
        [
            _event("task_started", "2026-09-15T09:00:00Z", task_id="t"),
            _event("task_blocked", "2026-09-15T09:01:00Z", task_id="t", reason="Waiting."),
            _event("task_cancelled", "2026-09-15T10:00:00Z", task_id="t", reason="You stopped it."),
        ]
    )

    assert [(a.index, a.kind, a.outcome) for a in attempts] == [
        (1, "run", "waiting_for_approval"),
        (0, "record", "cancelled"),
    ]


def test_a_transition_whose_payload_could_not_be_read_still_has_a_sentence() -> None:
    attempts = derive_attempts([_event("task_failed", "2026-09-15T09:00:00Z")])

    assert attempts[0].events[0].detail == "Did not complete."


def test_event_detail_prefers_what_the_runtime_stated() -> None:
    assert event_detail("task_failed", {"reason": "No route to the provider."}) == (
        "No route to the provider."
    )
    assert event_detail("task_waiting_for_children", {"unfinished_children": 1}) == (
        "Its own run finished. Waiting on 1 delegated task."
    )
    assert event_detail("task_progress", {"progress_percent": 40}) == "40% through its objective."


# ── the events the runtime now writes ───────────────────────────────────────


def _owner_workspace(tmp_path: Path) -> tuple[SQLiteStore, str]:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    session_id = "sess_inbox_principal_owner"
    store.create_session(session_id, str(tmp_path))
    return store, session_id


def test_a_scheduled_cycle_records_where_it_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, session_id = _owner_workspace(tmp_path)
    task = TaskManager(store, EventLogWriter(store)).create_task(
        session_id=session_id,
        title="Review",
        objective="Review now",
        scheduled_at="2020-01-01T09:00:00Z",
    )

    async def completed(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(status="completed", message="Finished safely.")

    monkeypatch.setattr("raiker.tasks.scheduler.AgentGateway.submit_prompt_async", completed)
    assert asyncio.run(TaskScheduler(tmp_path).run_due()) == 1

    types = [
        row["event_type"] for row in store.list_event_index(task_id=task.task_id, limit=50)
    ]
    assert "task_started" in types

    detail = DashboardService(tmp_path).get_task_detail(task.task_id)
    assert detail is not None
    runs = [attempt for attempt in detail.attempts if attempt.kind == "run"]
    assert [attempt.outcome for attempt in runs] == ["completed"]
    assert runs[0].summary == "Finished safely."


def test_a_routine_records_each_cycle_and_stays_armed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, session_id = _owner_workspace(tmp_path)
    task = TaskManager(store, EventLogWriter(store)).create_task(
        session_id=session_id,
        title="Nightly digest",
        objective="Summarise the day",
        scheduled_at="2020-01-01T09:00:00Z",
        recurrence="daily",
    )

    async def completed(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(status="completed", message="Digest sent.")

    monkeypatch.setattr("raiker.tasks.scheduler.AgentGateway.submit_prompt_async", completed)
    assert asyncio.run(TaskScheduler(tmp_path).run_due()) == 1

    saved = store.load_task(task.task_id)
    assert saved is not None and saved.status == "queued"  # armed, not completed

    detail = DashboardService(tmp_path).get_task_detail(task.task_id)
    assert detail is not None
    runs = [attempt for attempt in detail.attempts if attempt.kind == "run"]
    assert [attempt.outcome for attempt in runs] == ["completed"]
    assert runs[0].summary == "Digest sent."


def test_a_task_belonging_to_another_account_has_no_address(tmp_path: Path) -> None:
    """The address obeys the board's own visibility rule, never a second one."""
    store = SQLiteStore(tmp_path)
    now = utc_now()
    store.insert_user(User("user_mine", "Mine", None, True, now, now))
    store.insert_user(User("user_other", "Other", None, True, now, now))
    store.create_session("sess_mine", str(tmp_path), user_id="user_mine")
    store.create_session("sess_other", str(tmp_path), user_id="user_other")
    manager = TaskManager(store, EventLogWriter(store))
    theirs = manager.create_task(
        session_id="sess_other", title="Theirs", objective="Not yours"
    )
    mine = manager.create_task(session_id="sess_mine", title="Mine", objective="Mine")

    service = DashboardService(tmp_path)
    assert service.get_task_detail(theirs.task_id, user_id="user_mine") is None
    assert service.get_task_detail(mine.task_id, user_id="user_mine") is not None
