from __future__ import annotations

from raiker.checkpoints.service import CheckpointService
from raiker.contracts.ids import new_id
from raiker.storage.sqlite import SQLiteStore


def test_checkpoint_write_and_read(tmp_path) -> None:  # type: ignore[no-untyped-def]
    service = CheckpointService(SQLiteStore(tmp_path))
    checkpoint, path = service.write_turn_checkpoint(
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        runtime_state="CLOSED",
        summary="done",
        last_event_id=new_id("evt_"),
    )
    assert path.exists()
    loaded = service.read(path)
    assert loaded.checkpoint_id == checkpoint.checkpoint_id


def test_plan_restore_is_executable_metadata_plan(tmp_path) -> None:  # type: ignore[no-untyped-def]
    # B2 upgraded plan_restore from a can_execute=False stub into a real,
    # metadata-only dry-run plan for an approval-required governed restore.
    service = CheckpointService(SQLiteStore(tmp_path))
    checkpoint, _ = service.write_turn_checkpoint(
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        runtime_state="CLOSED",
        summary="done",
        last_event_id=new_id("evt_"),
    )
    plan = service.plan_restore(checkpoint.checkpoint_id)
    assert plan["status"] == "restore_plan"
    assert plan["can_execute"] is True
    assert plan["requires_approval"] is True
    # No files were mutated after this checkpoint, so the plan is empty.
    assert plan["files"] == []
