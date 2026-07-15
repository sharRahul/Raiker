from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


def _token(client: TestClient) -> str:
    resp = client.post("/api/auth/session", json={"as_principal": None})
    assert resp.status_code == 200, resp.text
    return str(resp.json()["token"])


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestPrompts:
    def test_requires_auth(self, client: TestClient) -> None:
        assert client.post("/api/prompts", json={"text": "hi"}).status_code == 401

    def test_prompt_runs_a_governed_turn(self, workspace: Path, client: TestClient) -> None:
        token = _token(client)
        resp = client.post("/api/prompts", json={"text": "hello"}, headers=_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] in {"completed", "failed", "needs_approval", "denied"}
        # The full governed turn lifecycle is recorded in the durable event log.
        events = SQLiteStore(workspace).list_event_index(session_id=body["session_id"], limit=200)
        types = {e["event_type"] for e in events}
        assert "prompt_received" in types
        assert "turn_closed" in types

    def test_invalid_prompt_returns_failed(self, client: TestClient) -> None:
        token = _token(client)
        resp = client.post("/api/prompts", json={"text": ""}, headers=_headers(token))
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"

    def test_stream_emits_sse_with_final(self, client: TestClient) -> None:
        token = _token(client)
        resp = client.post("/api/prompts/stream", json={"text": "hello"}, headers=_headers(token))
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert "data:" in resp.text
        assert '"kind": "final"' in resp.text


class TestInterrupts:
    def test_stop_cancels_active_tasks_at_safe_boundary(self, workspace: Path, client: TestClient) -> None:
        store = SQLiteStore(workspace)
        store.create_session("sess_i", str(workspace))
        manager = TaskManager(store, EventLogWriter(store))
        task = manager.create_task(session_id="sess_i", title="demo", objective="do x")
        token = _token(client)

        resp = client.post(
            "/api/interrupts",
            json={"session_id": "sess_i", "all": True, "action_type": "cancel", "reason": "stop"},
            headers=_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["safe_boundary"] is True
        assert any(a["task_id"] == task.task_id and a["result"] == "cancelled" for a in body["applied"])

        assert store.load_task(task.task_id).status == "cancelled"  # type: ignore[union-attr]
        types = {e["event_type"] for e in store.list_event_index(session_id="sess_i", limit=200)}
        assert {"interrupt_received", "safe_boundary_reached", "task_cancelled"} <= types

    def test_ai_principal_cannot_interrupt(self, workspace: Path, client: TestClient) -> None:
        store = SQLiteStore(workspace)
        with store.connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO principals
                   (principal_id, principal_type, display_name, role_ids, domain_scopes,
                    max_runtime_mode, created_at, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("principal_ai", "ai_agent", "AI", "[]", "[]", "development_preview", utc_now(), 1),
            )
        raw, _ = ApiSessionStore(workspace).create_session("principal_ai")
        resp = client.post(
            "/api/interrupts",
            json={"session_id": "sess_i", "all": True},
            headers=_headers(raw),
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["reason_code"] == "human_principal_required"
