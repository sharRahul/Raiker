from __future__ import annotations

import pytest

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


def test_plan_fork_is_executable_preview(tmp_path) -> None:  # type: ignore[no-untyped-def]
    # B3 upgraded plan_fork from a can_execute=False stub into a real,
    # metadata-only preview: a fork mutates no workspace files, so it is not an
    # approval-required governed mutation.
    service = CheckpointService(SQLiteStore(tmp_path))
    checkpoint, _ = service.write_turn_checkpoint(
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        runtime_state="CLOSED",
        summary="ship it",
        last_event_id=new_id("evt_"),
    )
    plan = service.plan_fork(checkpoint.checkpoint_id)
    assert plan["status"] == "fork_plan"
    assert plan["can_execute"] is True
    assert plan["requires_approval"] is False
    assert plan["source_session_id"] == checkpoint.session_id
    assert plan["summary"] == "ship it"
    assert plan["memory_candidate_count"] == 0


def test_execute_fork_materializes_new_seeded_session(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SQLiteStore(tmp_path)
    service = CheckpointService(store)
    source_session = new_id("sess_")
    checkpoint, _ = service.write_turn_checkpoint(
        session_id=source_session,
        turn_id=new_id("turn_"),
        runtime_state="CLOSED",
        summary="ready to branch",
        last_event_id=new_id("evt_"),
    )

    result = service.execute_fork(checkpoint.checkpoint_id)

    # A new session distinct from the source is materialized and persisted.
    new_session_id = str(result["session_id"])
    assert result["status"] == "forked"
    assert new_session_id != source_session
    loaded = store.load_session(new_session_id)
    assert loaded is not None
    assert loaded["status"] == "open"

    # The fork is seeded from the checkpoint's summary + memory candidates.
    seed = service.load_fork_seed(new_session_id)
    assert seed is not None
    assert seed["forked_from_checkpoint_id"] == checkpoint.checkpoint_id
    assert seed["source_session_id"] == source_session
    assert seed["summary"] == "ready to branch"

    # No workspace files were created or mutated by the fork.
    assert list(store.paths.workspace_root.glob("*.txt")) == []


def test_execute_fork_unknown_checkpoint_raises(tmp_path) -> None:  # type: ignore[no-untyped-def]
    service = CheckpointService(SQLiteStore(tmp_path))
    with pytest.raises(ValueError):
        service.execute_fork("ckpt_does_not_exist")
