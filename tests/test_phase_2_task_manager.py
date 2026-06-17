from __future__ import annotations

from pathlib import Path

import pytest

from raiker.contracts.ids import new_id
from raiker.contracts.models import TaskRecord
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path)


@pytest.fixture
def manager(store: SQLiteStore) -> TaskManager:
    writer = EventLogWriter(store)
    return TaskManager(store, writer)


class TestTaskManager:
    def _create_session(self, store: SQLiteStore) -> str:
        sid = new_id("sess_")
        store.create_session(sid, str(store.paths.workspace_root))
        return sid

    def test_create_task(self, manager: TaskManager, store: SQLiteStore) -> None:
        sid = self._create_session(store)
        task = manager.create_task(
            session_id=sid,
            title="Test task",
            objective="Verify task creation works",
        )
        assert task.task_id.startswith("task_")
        assert task.title == "Test task"
        assert task.status == "queued"

    def test_get_task(self, manager: TaskManager, store: SQLiteStore) -> None:
        sid = self._create_session(store)
        task = manager.create_task(session_id=sid, title="Get test", objective="Check retrieval")
        loaded = manager.get_task(task.task_id)
        assert loaded is not None
        assert loaded.title == "Get test"
        assert loaded.objective == "Check retrieval"

    def test_get_task_missing(self, manager: TaskManager) -> None:
        assert manager.get_task("task_nonexistent") is None

    def test_list_tasks(self, manager: TaskManager, store: SQLiteStore) -> None:
        sid = self._create_session(store)
        manager.create_task(session_id=sid, title="Task A", objective="First")
        manager.create_task(session_id=sid, title="Task B", objective="Second")
        tasks = manager.list_tasks(session_id=sid)
        assert len(tasks) == 2

    def test_list_tasks_empty(self, manager: TaskManager) -> None:
        assert manager.list_tasks() == []

    def test_update_progress(self, manager: TaskManager, store: SQLiteStore) -> None:
        sid = self._create_session(store)
        task = manager.create_task(session_id=sid, title="Progress", objective="Check progress")
        updated = manager.update_progress(task.task_id, current_step="Step 1", progress_percent=25)
        assert updated is not None
        reloaded = manager.get_task(task.task_id)
        assert reloaded is not None
        assert reloaded.current_step == "Step 1"
        assert reloaded.progress_percent == 25

    def test_complete_task(self, manager: TaskManager, store: SQLiteStore) -> None:
        sid = self._create_session(store)
        task = manager.create_task(session_id=sid, title="Complete", objective="Check completion")
        completed = manager.complete_task(task.task_id, summary="Done")
        assert completed is not None
        reloaded = manager.get_task(task.task_id)
        assert reloaded is not None
        assert reloaded.status == "completed"
        assert reloaded.summary == "Done"

    def test_fail_task(self, manager: TaskManager, store: SQLiteStore) -> None:
        sid = self._create_session(store)
        task = manager.create_task(session_id=sid, title="Fail", objective="Check failure")
        failed = manager.fail_task(task.task_id, reason="Something broke")
        assert failed is not None
        reloaded = manager.get_task(task.task_id)
        assert reloaded is not None
        assert reloaded.status == "failed"

    def test_cancel_task(self, manager: TaskManager, store: SQLiteStore) -> None:
        sid = self._create_session(store)
        task = manager.create_task(session_id=sid, title="Cancel", objective="Check cancellation")
        cancelled = manager.cancel_task(task.task_id, reason="No longer needed")
        assert cancelled is not None
        reloaded = manager.get_task(task.task_id)
        assert reloaded is not None
        assert reloaded.status == "cancelled"

    def test_task_record_contract(self) -> None:
        task = TaskRecord(
            task_id=new_id("task_"),
            session_id=new_id("sess_"),
            title="Contract test",
            objective="Validate dataclass",
            status="queued",
            created_at="2026-06-17T12:00:00Z",
            updated_at="2026-06-17T12:00:00Z",
        )
        assert task.task_id.startswith("task_")
        assert task.status == "queued"

    def test_task_record_invalid_status(self) -> None:

        with pytest.raises(ValueError):
            TaskRecord(
                task_id=new_id("task_"),
                session_id=new_id("sess_"),
                title="Bad status",
                objective="Check invalid",
                status="unknown_status",
                created_at="2026-06-17T12:00:00Z",
                updated_at="2026-06-17T12:00:00Z",
            )