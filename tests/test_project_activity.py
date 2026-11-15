"""QUI-L11 — a project's activity: the events of its own conversations."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.contracts.models import AgentEvent
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path))


def _register(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/register", json={"username": "owner", "password": "a-long-password-1"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _event(store: SQLiteStore, event_id: str, session_id: str, event_type: str) -> None:
    store.index_event(
        AgentEvent(
            event_id=event_id, timestamp=f"2026-11-18T10:00:0{event_id[-1]}Z", session_id=session_id,
            turn_id=None, event_type=event_type, actor="raiker", payload={},
        ),
        "events.jsonl", 0, "0" * 64,
    )


def test_only_the_projects_own_conversations_are_listed(client: TestClient) -> None:
    h = _register(client)
    store = SQLiteStore(Path(client.app.state.workspace_root))  # type: ignore[attr-defined]
    principal = client.get("/api/auth/whoami", headers=h).json()["principal_id"]
    user_id = store.principal_user_id(principal)
    project_id = client.post("/api/projects", json={"name": "Trip"}, headers=h).json()["project_id"]
    root = str(store.paths.workspace_root)
    store.create_session("sess_in", root, title="Flights", user_id=user_id)
    store.set_session_project("sess_in", project_id, user_id=user_id)
    store.create_session("sess_out", root, title="Elsewhere", user_id=user_id)
    _event(store, "evt_1", "sess_in", "policy_decision")
    _event(store, "evt_2", "sess_out", "policy_decision")

    response = client.get(f"/api/events?project_id={project_id}", headers=h)
    assert response.status_code == 200, response.text
    assert [event["session_id"] for event in response.json()] == ["sess_in"]


def test_an_unknown_project_is_refused(client: TestClient) -> None:
    h = _register(client)
    assert client.get("/api/events?project_id=proj_nope", headers=h).status_code == 404
