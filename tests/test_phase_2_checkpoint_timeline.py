from __future__ import annotations

from pathlib import Path

import pytest

from raiker.checkpoints.service import CheckpointService
from raiker.contracts.ids import new_id
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path)


@pytest.fixture
def service(store: SQLiteStore) -> CheckpointService:
    return CheckpointService(store)


class TestCheckpointTimeline:
    def test_list_checkpoints_empty(self, service: CheckpointService) -> None:
        cps = service.list_checkpoints()
        assert cps == []

    def test_list_checkpoints_with_data(self, service: CheckpointService) -> None:
        sid = new_id("sess_")
        service.write_turn_checkpoint(
            session_id=sid,
            turn_id=new_id("turn_"),
            runtime_state="CLOSED",
            summary="Test checkpoint",
            last_event_id=new_id("evt_"),
        )
        cps = service.list_checkpoints(session_id=sid)
        assert len(cps) >= 1

    def test_get_checkpoint(self, service: CheckpointService) -> None:
        sid = new_id("sess_")
        ckpt, _ = service.write_turn_checkpoint(
            session_id=sid,
            turn_id=new_id("turn_"),
            runtime_state="CLOSED",
            summary="Individual check",
            last_event_id=new_id("evt_"),
        )
        loaded = service.get_checkpoint(ckpt.checkpoint_id)
        assert loaded is not None
        assert loaded["checkpoint_id"] == ckpt.checkpoint_id

    def test_get_checkpoint_missing(self, service: CheckpointService) -> None:
        assert service.get_checkpoint("ckpt_nonexistent") is None

    def test_list_checkpoints_multiple(self, service: CheckpointService) -> None:
        sid = new_id("sess_")
        for i in range(3):
            service.write_turn_checkpoint(
                session_id=sid,
                turn_id=new_id("turn_"),
                runtime_state="CLOSED",
                summary=f"Checkpoint {i}",
                last_event_id=new_id("evt_"),
            )
        cps = service.list_checkpoints(session_id=sid)
        assert len(cps) == 3