from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from raiker.contracts.ids import new_id
from raiker.storage.sqlite import SQLiteStore


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    project_root: str
    status: str
    title: str | None = None


class SessionManager:
    def __init__(self, store: SQLiteStore, workspace_root: str | Path) -> None:
        self.store = store
        self.workspace_root = str(Path(workspace_root).resolve())

    def create_session(
        self,
        session_id: str | None = None,
        *,
        title: str | None = None,
        user_id: str | None = None,
        origin: str = "chat",
    ) -> SessionRecord:
        session_id = session_id or new_id("sess_")
        self.store.create_session(
            session_id, self.workspace_root, title=title, user_id=user_id, origin=origin
        )
        return SessionRecord(
            session_id=session_id, project_root=self.workspace_root, status="open", title=title
        )

    def get_or_create(
        self, session_id: str | None = None, *, user_id: str | None = None
    ) -> SessionRecord:
        if session_id:
            loaded = self.load_session(session_id)
            if loaded is not None:
                return loaded
            return self.create_session(session_id, user_id=user_id)
        return self.create_session(user_id=user_id)

    def load_session(self, session_id: str) -> SessionRecord | None:
        row = self.store.load_session(session_id)
        if row is None:
            return None
        return SessionRecord(
            session_id=str(row["session_id"]),
            project_root=str(row["project_root"]),
            status=str(row["status"]),
            title=row.get("title"),
        )

    def track_turn(self, session_id: str, turn_id: str, prompt_text: str) -> None:
        self.store.insert_turn(session_id, turn_id, prompt_text)

    def close_turn(self, turn_id: str, status: str, summary: str) -> None:
        self.store.complete_turn(turn_id, status, summary)
