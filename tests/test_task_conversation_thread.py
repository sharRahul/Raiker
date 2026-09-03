"""GAP-CHAT C11 — background work becomes conversational.

Scheduled and background tasks ran as isolated turns whose output landed in a
task record. Worse, every task belonging to a principal ran in one
``sess_inbox_<principal>`` session, which Chat deliberately hides from RECENT
CHATS — so the overnight research routine and the hourly build check interleaved
their turns in a single transcript nobody could open. *"What did the overnight
run find?"* had no thread to be asked in, and a reply had nowhere to land.

Each task now carries its own durable conversation. The two properties that make
it more than a rename:

* **Every cycle runs in that thread**, so a recurring routine accumulates a
  readable history rather than overwriting a status line.
* **The owner's reply is in the conversation the next cycle runs in**, which is
  what makes replying *steer* the routine rather than merely annotate it.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager
from raiker.tasks.scheduler import TaskScheduler

OWNER = "principal_owner"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


class TestTheThreadExists:
    def test_a_new_task_gets_a_conversation_of_its_own(self, workspace: Path) -> None:
        view = DashboardService(workspace).create_task(
            title="Overnight research",
            objective="Summarise what changed",
            principal_id=OWNER,
            user_id=None,
        )
        assert view.thread_session_id
        assert view.thread_session_id != view.session_id

    def test_the_thread_is_titled_after_the_task(self, workspace: Path) -> None:
        """Otherwise every routine's thread is called "Inbox"."""
        service = DashboardService(workspace)
        view = service.create_task(
            title="Overnight research",
            objective="Summarise what changed",
            principal_id=OWNER,
            user_id=None,
        )
        session = SQLiteStore(workspace).load_session(str(view.thread_session_id))
        assert session is not None
        assert session["title"] == "Overnight research"

    def test_two_tasks_do_not_share_a_thread(self, workspace: Path) -> None:
        """The defect in one line: the hourly check and the nightly run were one transcript."""
        service = DashboardService(workspace)
        first = service.create_task(
            title="Hourly check", objective="Check", principal_id=OWNER, user_id=None
        )
        second = service.create_task(
            title="Nightly run", objective="Run", principal_id=OWNER, user_id=None
        )
        assert first.thread_session_id != second.thread_session_id

    def test_the_thread_stays_out_of_recent_chats(self, workspace: Path) -> None:
        """These are threads an owner opens *from their work*, not chats they started."""
        service = DashboardService(workspace)
        view = service.create_task(
            title="Overnight research", objective="Summarise", principal_id=OWNER, user_id=None
        )
        chats = service.list_sessions(origin="chat")
        assert all(session.session_id != view.thread_session_id for session in chats)


class TestEveryCycleRunsInIt:
    def test_a_due_cycle_runs_in_the_task_thread(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = SQLiteStore(workspace)
        store.create_session(f"sess_inbox_{OWNER}", str(workspace))
        task = TaskManager(store, EventLogWriter(store)).create_task(
            session_id=f"sess_inbox_{OWNER}",
            thread_session_id="sess_thread_one",
            title="Nightly",
            objective="Run",
            scheduled_at="2020-01-01T09:00:00Z",
        )
        store.create_session("sess_thread_one", str(workspace), title="Nightly")
        seen: list[str] = []

        async def completed(_self, envelope):  # type: ignore[no-untyped-def]
            seen.append(envelope.session_id)
            return SimpleNamespace(status="completed", message="Done.")

        monkeypatch.setattr(
            "raiker.tasks.scheduler.AgentGateway.submit_prompt_async", completed
        )
        assert asyncio.run(TaskScheduler(workspace).run_due()) == 1
        assert seen == ["sess_thread_one"]
        assert store.load_task(task.task_id) is not None

    def test_a_task_created_before_threads_existed_still_runs(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`thread_session_id` is null on every task that predates this, and those must not break."""
        store = SQLiteStore(workspace)
        store.create_session(f"sess_inbox_{OWNER}", str(workspace))
        TaskManager(store, EventLogWriter(store)).create_task(
            session_id=f"sess_inbox_{OWNER}",
            title="Legacy",
            objective="Run",
            scheduled_at="2020-01-01T09:00:00Z",
        )
        seen: list[str] = []

        async def completed(_self, envelope):  # type: ignore[no-untyped-def]
            seen.append(envelope.session_id)
            return SimpleNamespace(status="completed", message="Done.")

        monkeypatch.setattr(
            "raiker.tasks.scheduler.AgentGateway.submit_prompt_async", completed
        )
        assert asyncio.run(TaskScheduler(workspace).run_due()) == 1
        assert seen == [f"sess_inbox_{OWNER}"]

    def test_the_owner_is_still_read_from_the_inbox_not_the_thread(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The thread is a conversation; the Inbox is where whose task it is lives.

        Deriving the principal from the run session would have made a task with a
        thread ownerless, which fails closed and would have looked like a
        scheduler bug rather than a lost field.
        """
        store = SQLiteStore(workspace)
        store.create_session(f"sess_inbox_{OWNER}", str(workspace))
        task = TaskManager(store, EventLogWriter(store)).create_task(
            session_id=f"sess_inbox_{OWNER}",
            thread_session_id="sess_thread_two",
            title="Nightly",
            objective="Run",
            scheduled_at="2020-01-01T09:00:00Z",
        )
        store.create_session("sess_thread_two", str(workspace), title="Nightly")

        async def completed(_self, _envelope):  # type: ignore[no-untyped-def]
            return SimpleNamespace(status="completed", message="Done.")

        monkeypatch.setattr(
            "raiker.tasks.scheduler.AgentGateway.submit_prompt_async", completed
        )
        asyncio.run(TaskScheduler(workspace).run_due())
        saved = store.load_task(task.task_id)
        assert saved is not None
        assert saved.status == "completed"
        assert saved.summary == "Done."


class TestTheCardCanOfferIt:
    def test_a_task_with_no_turns_yet_reports_an_empty_thread(self, workspace: Path) -> None:
        """A link to an empty transcript is a dead end, so the card is told not to offer one."""
        service = DashboardService(workspace)
        service.create_task(
            title="Nightly", objective="Run", principal_id=OWNER, user_id=None
        )
        listed = service.list_tasks()
        assert [task.thread_turns for task in listed] == [0]

    def test_the_count_follows_the_cycles_that_have_run(self, workspace: Path) -> None:
        service = DashboardService(workspace)
        view = service.create_task(
            title="Nightly", objective="Run", principal_id=OWNER, user_id=None
        )
        store = SQLiteStore(workspace)
        store.insert_turn(str(view.thread_session_id), "turn_a", "Run")
        store.insert_turn(str(view.thread_session_id), "turn_b", "Run")
        listed = service.list_tasks()
        assert [task.thread_turns for task in listed] == [2]
