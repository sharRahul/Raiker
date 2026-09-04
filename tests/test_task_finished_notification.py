"""GAP-CHAT C10 — background work finished and nobody was told.

`channel-connectors.json` declares ten surfaces and `external_channels_enabled`
is hardcoded `False`, so a scheduled routine ran, ended, and left nothing but a
card the owner had to think to go and look at. The plan calls the notification
path the cheapest half of C10 and the one that makes routines useful, and this
is it — over what already exists rather than a new channel: the owner-scoped
`notifications` table, the browser notice BUG-255 built, and the owner's
optional OS hook.

The rule that keeps it from being noise is the one pinned hardest here. Every
Chat turn is a task and every Chat turn completes; a notice for one of those
would put a banner behind a message the owner has just finished reading. Only
work nobody was watching notifies.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.events.writer import EventLogWriter
from raiker.notify.task_notifier import TASK_FINISHED_KIND
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    return tmp_path


@pytest.fixture
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


@pytest.fixture
def manager(store: SQLiteStore) -> TaskManager:
    return TaskManager(store, EventLogWriter(store))


@pytest.fixture
def session_id(store: SQLiteStore) -> str:
    sid = f"sess_inbox_{'principal_owner'}"
    store.create_session(sid, str(store.paths.workspace_root))
    return sid


def _notices(store: SQLiteStore) -> list[dict[str, object]]:
    return [
        item
        for item in store.list_notifications("principal_owner")
        if item["kind"] == TASK_FINISHED_KIND
    ]


class TestOnlyWorkNobodyWasWatching:
    def test_a_scheduled_run_tells_the_owner_it_finished(
        self, manager: TaskManager, store: SQLiteStore, session_id: str
    ) -> None:
        task = manager.create_task(
            session_id=session_id,
            title="Overnight dependency review",
            objective="Read the lockfile and report.",
            scheduled_at="2026-09-04T02:00:00Z",
        )
        manager.complete_task(task.task_id, "Found two upgrades.")

        notices = _notices(store)
        assert len(notices) == 1
        assert notices[0]["title"] == "Background task finished"
        assert "Overnight dependency review" in str(notices[0]["body"])
        assert notices[0]["subject_id"] == task.task_id

    def test_a_recurring_run_does_too(
        self, manager: TaskManager, store: SQLiteStore, session_id: str
    ) -> None:
        task = manager.create_task(
            session_id=session_id,
            title="Daily digest",
            objective="Summarise the day.",
            recurrence="daily",
        )
        manager.complete_task(task.task_id, "Sent.")
        assert len(_notices(store)) == 1

    def test_an_ordinary_chat_turn_does_not(
        self, manager: TaskManager, store: SQLiteStore, session_id: str
    ) -> None:
        """The owner is looking at the answer; a banner behind it is noise."""
        task = manager.create_task(
            session_id=session_id,
            title="Explain this function",
            objective="Answer the question.",
        )
        manager.complete_task(task.task_id, "Here is what it does.")
        assert _notices(store) == []

    def test_a_parent_that_outlived_its_turn_does(
        self, manager: TaskManager, store: SQLiteStore, session_id: str
    ) -> None:
        """It parked for its children, so the owner had already moved on."""
        parent = manager.create_task(
            session_id=session_id, title="Ship the release", objective="Delegate."
        )
        child = manager.create_task(
            session_id=session_id,
            title="Child",
            objective="One part.",
            parent_task_id=parent.task_id,
        )
        manager.complete_task(parent.task_id, "Delegated.")
        parked = manager.get_task(parent.task_id)
        assert parked is not None and parked.status == "waiting_for_children"
        assert _notices(store) == []

        manager.complete_task(child.task_id, "Done.")

        # The child was watched work; the parent, settling later, was not.
        notices = _notices(store)
        assert len(notices) == 1
        assert "Ship the release" in str(notices[0]["body"])


class TestWhatTheNoticeSays:
    def test_a_failure_reads_as_one(
        self, manager: TaskManager, store: SQLiteStore, session_id: str
    ) -> None:
        task = manager.create_task(
            session_id=session_id,
            title="Nightly build",
            objective="Build it.",
            recurrence="daily",
        )
        manager.fail_task(task.task_id, "The compiler ran out of memory.")

        notices = _notices(store)
        assert len(notices) == 1
        assert notices[0]["title"] == "Background task did not finish"

    def test_the_run_s_own_words_stay_in_the_thread(
        self, manager: TaskManager, store: SQLiteStore, session_id: str
    ) -> None:
        """A summary is model output about the owner's material.

        The operating system may render this on a lock screen, so it carries the
        title and the outcome and nothing the run produced.
        """
        task = manager.create_task(
            session_id=session_id,
            title="Inbox triage",
            objective="Read the mail.",
            recurrence="hourly",
        )
        manager.complete_task(task.task_id, "Dr Chen confirmed the biopsy result.")

        body = str(_notices(store)[0]["body"])
        assert "biopsy" not in body
        assert "Inbox triage" in body

    def test_a_very_long_title_is_bounded(
        self, manager: TaskManager, store: SQLiteStore, session_id: str
    ) -> None:
        task = manager.create_task(
            session_id=session_id,
            title="x" * 400,
            objective="Long.",
            recurrence="daily",
        )
        manager.complete_task(task.task_id, "Done.")
        assert len(str(_notices(store)[0]["body"])) < 140


class TestANoticeNeverFailsTheTask:
    def test_a_store_that_refuses_the_write_leaves_the_task_completed(
        self, manager: TaskManager, store: SQLiteStore, session_id: str
    ) -> None:
        task = manager.create_task(
            session_id=session_id,
            title="Fragile",
            objective="Run.",
            recurrence="daily",
        )

        def explode(**_: object) -> str:
            raise RuntimeError("notifications table is gone")

        store.insert_notification = explode  # type: ignore[method-assign]
        finished = manager.complete_task(task.task_id, "Done.")

        assert finished is not None
        assert finished.status == "completed"
