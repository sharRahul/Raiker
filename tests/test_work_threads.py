"""GAP-CHAT C18 — the cross-chat surface.

Chat search covered titles and message text, which answers *"where did I say
that"*. It could not answer *"what am I working on"*: there was no view across
projects, and no way to reach — let alone resume — the threads a routine is
advancing. Those threads did not exist as threads until C11 gave each task a
conversation.

`GET /api/work-threads` is the join nothing was performing. Every field it
returns is read from a row that already existed; it records nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture
def owner_token(workspace: Path) -> str:
    token, _session = ApiSessionStore(workspace).create_session(OWNER)
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _chat(store: SQLiteStore, workspace: Path, session_id: str, title: str) -> None:
    store.create_session(session_id, str(workspace), title=title, origin="chat")
    store.set_session_origin(session_id, "chat")
    store.insert_turn(session_id, f"turn_{session_id}", title)


class TestTheBoard:
    def test_it_requires_authentication(self, client: TestClient) -> None:
        assert client.get("/api/work-threads").status_code == 401

    def test_it_lists_the_owners_conversations(
        self, client: TestClient, owner_token: str, workspace: Path
    ) -> None:
        _chat(SQLiteStore(workspace), workspace, "sess_chat", "Release planning")
        body = client.get("/api/work-threads", headers=_auth(owner_token)).json()
        assert [(row["title"], row["kind"]) for row in body] == [
            ("Release planning", "chat")
        ]

    def test_a_routine_thread_appears_once_it_has_run(
        self, client: TestClient, owner_token: str, workspace: Path
    ) -> None:
        """The half that had no reader at all before C11."""
        service = DashboardService(workspace)
        view = service.create_task(
            title="Overnight research",
            objective="Summarise what changed",
            recurrence="daily",
            principal_id=OWNER,
            user_id=None,
        )
        store = SQLiteStore(workspace)
        store.insert_turn(str(view.thread_session_id), "turn_cycle", "Summarise")
        body = client.get("/api/work-threads", headers=_auth(owner_token)).json()
        routine = next(row for row in body if row["kind"] == "routine")
        assert routine["title"] == "Overnight research"
        assert routine["session_id"] == view.thread_session_id
        assert routine["cadence"] == "daily"
        assert routine["task_id"] == view.task_id

    def test_a_routine_that_has_not_run_is_not_offered(
        self, client: TestClient, owner_token: str, workspace: Path
    ) -> None:
        """Every row on this board is somewhere to continue; an empty thread is not."""
        DashboardService(workspace).create_task(
            title="Overnight research",
            objective="Summarise",
            recurrence="daily",
            principal_id=OWNER,
            user_id=None,
        )
        body = client.get("/api/work-threads", headers=_auth(owner_token)).json()
        assert body == []

    def test_the_inbox_is_never_a_thread(
        self, client: TestClient, owner_token: str, workspace: Path
    ) -> None:
        """The server-owned session task bookkeeping lands in is not resumable work."""
        service = DashboardService(workspace)
        service.create_task(
            title="Nightly", objective="Run", principal_id=OWNER, user_id=None
        )
        store = SQLiteStore(workspace)
        store.insert_turn(f"sess_inbox_{OWNER}", "turn_inbox", "bookkeeping")
        body = client.get("/api/work-threads", headers=_auth(owner_token)).json()
        assert all(row["session_id"] != f"sess_inbox_{OWNER}" for row in body)

    def test_newest_first_across_both_kinds(
        self, client: TestClient, owner_token: str, workspace: Path
    ) -> None:
        """One head, one list: the ordering cannot depend on which kind a row is."""
        store = SQLiteStore(workspace)
        _chat(store, workspace, "sess_chat", "Release planning")
        service = DashboardService(workspace)
        view = service.create_task(
            title="Overnight research", objective="Summarise", principal_id=OWNER, user_id=None
        )
        store.insert_turn(str(view.thread_session_id), "turn_cycle", "Summarise")
        body = client.get("/api/work-threads", headers=_auth(owner_token)).json()
        stamps = [row["updated_at"] for row in body]
        assert stamps == sorted(stamps, reverse=True)

    def test_it_names_the_project_a_thread_sits_in(
        self, client: TestClient, owner_token: str, workspace: Path
    ) -> None:
        """The cross-project view the gap named. Nothing joined these two before."""
        store = SQLiteStore(workspace)
        # The project and the chat have to belong to the same account, which is
        # exactly what `set_session_project` refuses to cross.
        owner_user_id = store.principal_user_id(OWNER)
        store.create_session(
            "sess_chat",
            str(workspace),
            title="Release planning",
            user_id=owner_user_id,
            origin="chat",
        )
        store.set_session_origin("sess_chat", "chat")
        store.insert_turn("sess_chat", "turn_chat", "Release planning")
        store.create_project(
            "proj_alpha", "Alpha", "projects/alpha", owner_user_id=owner_user_id
        )
        assert store.set_session_project("sess_chat", "proj_alpha") is True
        body = client.get("/api/work-threads", headers=_auth(owner_token)).json()
        assert [row["project_name"] for row in body] == ["Alpha"]

    def test_a_blocked_routine_says_what_it_is_waiting_on(
        self, client: TestClient, owner_token: str, workspace: Path
    ) -> None:
        service = DashboardService(workspace)
        view = service.create_task(
            title="Overnight research", objective="Summarise", principal_id=OWNER, user_id=None
        )
        store = SQLiteStore(workspace)
        store.insert_turn(str(view.thread_session_id), "turn_cycle", "Summarise")
        store.update_task_status(view.task_id, "waiting_for_approval")
        body = client.get("/api/work-threads", headers=_auth(owner_token)).json()
        routine = next(row for row in body if row["kind"] == "routine")
        assert routine["waiting_on"] == "Waiting for your approval"

    def test_a_thread_nobody_is_waiting_on_says_nothing(
        self, client: TestClient, owner_token: str, workspace: Path
    ) -> None:
        """No staleness heuristic. It states a blocker the runtime holds, or none."""
        _chat(SQLiteStore(workspace), workspace, "sess_chat", "Release planning")
        body = client.get("/api/work-threads", headers=_auth(owner_token)).json()
        assert body[0]["waiting_on"] is None
