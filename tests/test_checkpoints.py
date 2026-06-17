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
