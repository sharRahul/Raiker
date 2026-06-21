from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.commands import (
    handle_checkpoints,
    handle_events,
    handle_slash_command,
    handle_status,
    handle_tasks,
)
from raiker.contracts.ids import new_id
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path)


class TestTerminalCommands:
    def test_handle_status_empty(self, tmp_path: Path) -> None:
        result = handle_status(workspace_root=str(tmp_path))
        assert "workspace:" in result
        assert "database:" in result
        assert "events:" in result
        assert "checkpoints:" in result
        assert "pending_approvals:" in result
        assert "phase_3_status: implemented_verified" in result
        assert "phase_4_status: memory_mvp_implemented" in result
        assert "runtime_execution_enabled: False" in result
        assert "0" in result

    def test_handle_status_with_sessions(self, store: SQLiteStore) -> None:
        sid = new_id("sess_")
        store.create_session(sid, str(store.paths.workspace_root))
        result = handle_status(workspace_root=str(store.paths.workspace_root))
        assert sid in result

    def test_handle_tasks_empty(self, tmp_path: Path) -> None:
        result = handle_tasks(workspace_root=str(tmp_path))
        assert result == "No tasks."

    def test_handle_tasks_with_data(self, store: SQLiteStore) -> None:
        sid = new_id("sess_")
        store.create_session(sid, str(store.paths.workspace_root))
        writer = EventLogWriter(store)
        manager = TaskManager(store, writer)
        manager.create_task(session_id=sid, title="Test Task", objective="Check rendering")
        result = handle_tasks(workspace_root=str(store.paths.workspace_root))
        assert "Test Task" in result
        assert "queued" in result

    def test_handle_events_empty(self, tmp_path: Path) -> None:
        result = handle_events(workspace_root=str(tmp_path))
        assert result == "No events."

    def test_handle_events_with_data(self, store: SQLiteStore) -> None:
        sid = new_id("sess_")
        writer = EventLogWriter(store)
        writer.append(
            make_event(session_id=sid, turn_id=None, event_type="prompt_received", actor="test")
        )
        result = handle_events(workspace_root=str(store.paths.workspace_root))
        assert "prompt_received" in result

    def test_handle_checkpoints_empty(self, tmp_path: Path) -> None:
        result = handle_checkpoints(workspace_root=str(tmp_path))
        assert result == "No checkpoints."

    def test_handle_checkpoints_with_data(self, store: SQLiteStore) -> None:
        from raiker.checkpoints.service import CheckpointService

        sid = new_id("sess_")
        service = CheckpointService(store)
        service.write_turn_checkpoint(
            session_id=sid,
            turn_id=new_id("turn_"),
            runtime_state="CLOSED",
            summary="Test",
            last_event_id=new_id("evt_"),
        )
        result = handle_checkpoints(workspace_root=str(store.paths.workspace_root))
        assert "Test" in result

    def test_slash_help(self, tmp_path: Path) -> None:
        result = handle_slash_command("/help", workspace_root=str(tmp_path))
        assert "/help" in result
        assert "/status" in result
        assert "/tasks" in result
        assert "/events" in result
        assert "/checkpoints" in result
        assert "Phase 3 is complete" in result
        assert "Phase 4 is blocked" in result
        assert "runtime execution remains disabled" in result

    def test_slash_unknown(self, tmp_path: Path) -> None:
        result = handle_slash_command("/bogus", workspace_root=str(tmp_path))
        assert "Unknown command" in result

    def test_slash_status(self, tmp_path: Path) -> None:
        result = handle_slash_command("/status", workspace_root=str(tmp_path))
        assert "workspace:" in result
        assert "pending_approvals:" in result
        assert "phase_3_status: implemented_verified" in result
        assert "phase_4_status: memory_mvp_implemented" in result

    def test_slash_tasks(self, tmp_path: Path) -> None:
        result = handle_slash_command("/tasks", workspace_root=str(tmp_path))
        assert result == "No tasks." or "Tasks:" in result

    def test_slash_events(self, tmp_path: Path) -> None:
        result = handle_slash_command("/events", workspace_root=str(tmp_path))
        assert result == "No events." or "Recent events:" in result

    def test_slash_checkpoints(self, tmp_path: Path) -> None:
        result = handle_slash_command("/checkpoints", workspace_root=str(tmp_path))
        assert result == "No checkpoints." or "Checkpoints:" in result

    def test_memory_mutation_commands_are_approval_only(self, tmp_path: Path) -> None:
        store_output = handle_slash_command(
            '/memory-store "project note"', workspace_root=str(tmp_path)
        )
        assert "status: approval_required" in store_output
        assert "does not execute the action" in store_output
        assert handle_slash_command("/memory-forget mem_missing", workspace_root=str(tmp_path)).startswith(
            "Memory forget:\n  status: approval_required"
        )
