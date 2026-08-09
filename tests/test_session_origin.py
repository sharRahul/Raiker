"""BUG-10 — a task run is not a conversation.

Creating a task stores a server-owned "Inbox" session for the run to execute
in. That session appeared in the sidebar's RECENT CHATS beside real
conversations, so a work queue looked like chat history. Origin is a provenance
label: it changes no gate, no policy, and no visibility — a task session is
still fully readable in Sessions and reachable from Tasks. It only lets a list
of *conversations* mean conversations.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "origin"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


class TestOriginIsStored:
    def _origin(self, store: SQLiteStore, session_id: str) -> str:
        row = store.load_session(session_id)
        assert row is not None
        return str(row["origin"])

    def test_a_session_defaults_to_chat(self, store: SQLiteStore, workspace: Path) -> None:
        store.create_session("sess_typed", str(workspace))
        assert self._origin(store, "sess_typed") == "chat"

    def test_a_task_run_session_is_tagged(self, store: SQLiteStore, workspace: Path) -> None:
        DashboardService(workspace).create_task(
            title="Nightly sweep",
            objective="Sweep",
            user_id=None,
            principal_id="principal_owner",
        )
        inbox = store.load_session("sess_inbox_principal_owner")
        assert inbox is not None and inbox["origin"] == "task"

    def test_an_inbox_created_before_the_fix_is_restamped(
        self, store: SQLiteStore, workspace: Path
    ) -> None:
        # A workspace that already had an Inbox row keeps it; creating a task
        # must correct its provenance rather than leave it reading as a chat.
        store.create_session("sess_inbox_principal_owner", str(workspace), title="Inbox")
        assert self._origin(store, "sess_inbox_principal_owner") == "chat"
        DashboardService(workspace).create_task(
            title="Nightly sweep", objective="Sweep", user_id=None, principal_id="principal_owner"
        )
        assert self._origin(store, "sess_inbox_principal_owner") == "task"


class TestOriginFilters:
    def test_the_store_filters_by_origin(self, store: SQLiteStore, workspace: Path) -> None:
        store.create_session("sess_typed", str(workspace), title="Real chat")
        store.create_session("sess_run", str(workspace), title="Inbox", origin="task")

        chats = {row["session_id"] for row in store.list_sessions(limit=50, origin="chat")}
        assert chats == {"sess_typed"}
        everything = {row["session_id"] for row in store.list_sessions(limit=50)}
        assert everything == {"sess_typed", "sess_run"}

    def test_the_dashboard_passes_the_filter_through(
        self, store: SQLiteStore, workspace: Path
    ) -> None:
        store.create_session("sess_typed", str(workspace), title="Real chat")
        store.create_session("sess_run", str(workspace), title="Inbox", origin="task")
        service = DashboardService(workspace)

        assert [view.session_id for view in service.list_sessions(origin="chat")] == ["sess_typed"]
        assert len(service.list_sessions()) == 2
        assert {view.origin for view in service.list_sessions()} == {"chat", "task"}


class TestOriginOverTheApi:
    def _client(self, workspace: Path) -> TestClient:
        app: FastAPI = create_app(workspace)
        client = TestClient(app)
        token = client.post("/api/auth/session", json={}).json()["token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        return client

    def test_a_task_session_is_listed_but_not_as_a_chat(
        self, workspace: Path, mark_model_ready: Callable[..., None]
    ) -> None:
        mark_model_ready(workspace)
        client = self._client(workspace)
        created = client.post("/api/tasks", json={"title": "Nightly sweep", "description": "Sweep"})
        assert created.status_code == 201, created.text

        everything = client.get("/api/sessions").json()
        assert any(row["origin"] == "task" for row in everything), everything

        chats = client.get("/api/sessions", params={"origin": "chat"}).json()
        assert all(row["origin"] == "chat" for row in chats)
        assert not any(row["title"] == "Inbox" for row in chats)
