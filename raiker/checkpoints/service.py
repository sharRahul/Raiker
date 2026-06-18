from __future__ import annotations

import json
from pathlib import Path

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import Checkpoint
from raiker.storage.sqlite import SQLiteStore


class CheckpointService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.root = store.paths.checkpoints_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, session_id: str, checkpoint_id: str) -> Path:
        return self.root / session_id / f"{checkpoint_id}.json"

    def write_turn_checkpoint(
        self,
        *,
        session_id: str,
        turn_id: str,
        runtime_state: str,
        summary: str,
        last_event_id: str,
    ) -> tuple[Checkpoint, Path]:
        checkpoint = Checkpoint(
            checkpoint_id=new_id("ckpt_"),
            session_id=session_id,
            turn_id=turn_id,
            created_at=utc_now(),
            runtime_state=runtime_state,
            summary=summary,
            last_event_id=last_event_id,
            memory_candidates=[],
        )
        path = self.path_for(session_id, checkpoint.checkpoint_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(checkpoint.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.store.insert_checkpoint(checkpoint, str(path))
        return checkpoint, path

    def read(self, path: str | Path) -> Checkpoint:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return Checkpoint(**data)

    def list_checkpoints(self, session_id: str | None = None, limit: int = 50) -> list[dict]:
        return self.store.list_checkpoints(session_id=session_id, limit=limit)

    def get_checkpoint(self, checkpoint_id: str) -> dict | None:
        return self.store.load_checkpoint_by_id(checkpoint_id)

    def plan_restore(self, checkpoint_id: str) -> dict[str, object]:
        checkpoint = self.get_checkpoint(checkpoint_id)
        if checkpoint is None:
            raise ValueError("checkpoint_not_found")
        return {
            "status": "restore_plan",
            "checkpoint_id": checkpoint_id,
            "can_execute": False,
            "requires_approval": True,
            "reason": "Phase 2 plans restore only; file/state mutation remains disabled.",
        }

    def plan_fork(self, checkpoint_id: str) -> dict[str, object]:
        checkpoint = self.get_checkpoint(checkpoint_id)
        if checkpoint is None:
            raise ValueError("checkpoint_not_found")
        return {
            "status": "fork_plan",
            "checkpoint_id": checkpoint_id,
            "can_execute": False,
            "requires_approval": True,
            "reason": "Phase 2 plans fork only; execution is not active.",
        }
