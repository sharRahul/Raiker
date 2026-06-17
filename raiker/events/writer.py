from __future__ import annotations

import hashlib
import json
from pathlib import Path

from raiker.contracts.models import AgentEvent
from raiker.storage.sqlite import SQLiteStore


class EventLogWriter:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store
        self.events_dir = store.paths.events_dir
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.last_event_id: str | None = None

    def path_for_session(self, session_id: str) -> Path:
        return self.events_dir / f"{session_id}.jsonl"

    def append(self, event: AgentEvent) -> tuple[Path, int]:
        AgentEvent(**event.to_dict())
        path = self.path_for_session(event.session_id)
        serialised = json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(serialised.encode("utf-8")).hexdigest()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            offset = handle.tell()
            handle.write(serialised + "\n")
        self.store.index_event(event, str(path), offset, digest)
        self.last_event_id = event.event_id
        return path, offset
