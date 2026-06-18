from __future__ import annotations

import json
from pathlib import Path

from raiker.storage.sqlite import SQLiteStore


class EventViewer:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def list_events(
        self,
        session_id: str | None = None,
        turn_id: str | None = None,
        task_id: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        return self.store.list_event_index(
            session_id=session_id,
            turn_id=turn_id,
            task_id=task_id,
            event_type=event_type,
            limit=limit,
        )

    def get_event_index(self, event_id: str) -> dict | None:
        return self.store.load_event_index(event_id)

    def read_event_payload(self, event_id: str) -> dict | None:
        row = self.get_event_index(event_id)
        if row is None:
            return None
        jsonl_path = row.get("jsonl_path")
        if jsonl_path is None:
            return None
        path = Path(jsonl_path)
        if not path.exists():
            return None
        offset = row.get("jsonl_offset")

        with path.open("r", encoding="utf-8") as f:
            if offset is not None:
                f.seek(int(offset))
            line = f.readline()
        if not line:
            return None
        try:
            return json.loads(line.strip())
        except json.JSONDecodeError:
            return None
