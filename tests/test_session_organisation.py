"""Conversation organisation (backlog item 2): session pin/bookmark + delete.

Pinning and deleting sessions are organizing actions, governance-neutral like
projects: they grant nothing and change no gate, policy, or authority. Deletion
is human-only and respects the same user/session visibility boundary as every
governed read — an account cannot pin or delete another account's session,
and legacy unattributed sessions remain visible/deletable by any authenticated
human.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_rahul"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    return ws


@pytest.fixture
def service(workspace: Path) -> DashboardService:
    return DashboardService(workspace)


def _seed_session(store: SQLiteStore, session_id: str, workspace: Path, *, user_id: str | None = None) -> None:
    store.create_session(session_id, str(workspace), user_id=user_id)


class TestPinSession:
    def test_pin_surfaces_in_the_session_view_and_round_trips(
        self, service: DashboardService, workspace: Path
    ) -> None:
        store = service.store
        _seed_session(store, "sess_a", workspace)

        result = service.set_session_pinned("sess_a", True, OWNER)
        assert result.ok, result.reason_code
        assert result.data == {"session_id": "sess_a", "pinned": True}

        sessions = service.list_sessions()
        assert sessions[0].session_id == "sess_a"
        assert sessions[0].pinned is True

        # Unpin round-trips back to False.
        cleared = service.set_session_pinned("sess_a", False, OWNER)
        assert cleared.ok
        assert service.list_sessions()[0].pinned is False

    def test_unknown_session_fails_closed(self, service: DashboardService) -> None:
        result = service.set_session_pinned("sess_missing", True, OWNER)
        assert not result.ok
        assert result.reason_code == "unknown_session:sess_missing"

    def test_ai_principal_cannot_pin(self, service: DashboardService, workspace: Path) -> None:
        from raiker.contracts.ids import utc_now

        with service.store.connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO principals
                   (principal_id, principal_type, display_name, role_ids, domain_scopes,
                    max_runtime_mode, created_at, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("principal_ai", "ai_agent", "AI", "[]", "[]", "development_preview", utc_now(), 1),
            )
        _seed_session(service.store, "sess_a", workspace)
        result = service.set_session_pinned("sess_a", True, "principal_ai")
        assert not result.ok
        assert result.reason_code == "not_authorized_human"


class TestDeleteSession:
    def test_delete_removes_session_and_cascaded_rows(
        self, service: DashboardService, workspace: Path
    ) -> None:
        store = service.store
        _seed_session(store, "sess_a", workspace)
        store.insert_turn("sess_a", "turn_a", "hello")
        # Seed an event so the per-session JSONL transcript file exists.
        from raiker.events.types import make_event
        from raiker.events.writer import EventLogWriter

        EventLogWriter(store).append(
            make_event(session_id="sess_a", turn_id="turn_a", event_type="prompt_received", actor="test")
        )
        transcript = store.paths.events_dir / "sess_a.jsonl"
        assert transcript.exists()

        result = service.delete_session("sess_a", OWNER)
        assert result.ok, result.reason_code

        assert store.load_session("sess_a") is None
        assert store.list_turns("sess_a") == []
        assert store.list_event_index(session_id="sess_a") == []
        # The per-session transcript file is removed, not orphaned.
        assert not transcript.exists()

    def test_unknown_session_fails_closed(self, service: DashboardService) -> None:
        result = service.delete_session("sess_missing", OWNER)
        assert not result.ok
        assert result.reason_code == "unknown_session:sess_missing"

    def test_ai_principal_cannot_delete(self, service: DashboardService, workspace: Path) -> None:
        from raiker.contracts.ids import utc_now

        with service.store.connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO principals
                   (principal_id, principal_type, display_name, role_ids, domain_scopes,
                    max_runtime_mode, created_at, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("principal_ai", "ai_agent", "AI", "[]", "[]", "development_preview", utc_now(), 1),
            )
        _seed_session(service.store, "sess_a", workspace)
        result = service.delete_session("sess_a", "principal_ai")
        assert not result.ok
        assert result.reason_code == "not_authorized_human"


class TestSessionOrganisationApi:
    @pytest.fixture
    def app(self, workspace: Path) -> FastAPI:
        return create_app(workspace)

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        return TestClient(app)

    def _headers(self, client: TestClient) -> dict[str, str]:
        resp = client.post("/api/auth/session", json={"as_principal": None})
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['token']}"}

    def test_pin_unpin_round_trip_through_the_api(self, client: TestClient, workspace: Path) -> None:
        headers = self._headers(client)
        SQLiteStore(workspace).create_session("sess_a", str(workspace))

        pinned = client.put("/api/sessions/sess_a/pin", json={"pinned": True}, headers=headers)
        assert pinned.status_code == 200, pinned.text
        assert pinned.json()["pinned"] is True

        listing = client.get("/api/sessions", headers=headers).json()
        assert listing[0]["pinned"] is True

        cleared = client.put("/api/sessions/sess_a/pin", json={"pinned": False}, headers=headers)
        assert cleared.status_code == 200
        assert client.get("/api/sessions", headers=headers).json()[0]["pinned"] is False

    def test_pin_routes_require_auth(self, client: TestClient) -> None:
        assert client.put("/api/sessions/sess_a/pin", json={"pinned": True}).status_code == 401

    def test_unknown_session_pin_is_a_403(self, client: TestClient) -> None:
        headers = self._headers(client)
        resp = client.put("/api/sessions/sess_missing/pin", json={"pinned": True}, headers=headers)
        assert resp.status_code == 403
        assert resp.json()["detail"]["reason_code"] == "unknown_session:sess_missing"

    def test_delete_requires_an_explicit_confirmation(self, client: TestClient, workspace: Path) -> None:
        headers = self._headers(client)
        SQLiteStore(workspace).create_session("sess_a", str(workspace))

        resp = client.delete("/api/sessions/sess_a", headers=headers)
        assert resp.status_code == 409
        assert resp.json()["detail"]["reason_code"] == "session_delete_confirmation_required"
        # The session is still present — confirmation is mandatory.
        assert SQLiteStore(workspace).load_session("sess_a") is not None

    def test_delete_with_confirmation_removes_the_session(self, client: TestClient, workspace: Path) -> None:
        headers = self._headers(client)
        SQLiteStore(workspace).create_session("sess_a", str(workspace))

        resp = client.delete(
            "/api/sessions/sess_a",
            headers={**headers, "X-Session-Delete-Confirm": "sess_a"},
        )
        assert resp.status_code == 200, resp.text
        assert SQLiteStore(workspace).load_session("sess_a") is None

    def test_delete_routes_require_auth(self, client: TestClient) -> None:
        assert client.delete("/api/sessions/sess_a").status_code == 401


class TestSessionIsolation:
    """An account cannot pin or delete another account's session."""

    @pytest.fixture
    def app(self, workspace: Path) -> FastAPI:
        return create_app(workspace)

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        return TestClient(app)

    def test_account_cannot_delete_another_accounts_session(
        self, client: TestClient, workspace: Path
    ) -> None:
        # Bob registers and owns sess_bob.
        bob_token = client.post(
            "/api/auth/register", json={"username": "bob", "password": "right-pass-123"}
        ).json()["token"]
        bob_headers = {"Authorization": f"Bearer {bob_token}"}
        store = SQLiteStore(workspace)
        bob_account = store.get_account_by_username("bob")
        assert bob_account is not None
        bob_principal = store.get_principal(str(bob_account["principal_id"]))
        assert bob_principal is not None
        bob_user_id = str(bob_principal["delegated_by_user_id"])
        store.create_session("sess_bob", str(workspace), user_id=bob_user_id)

        # Alex registers as a separate account.
        registered = client.post(
            "/api/auth/register", json={"username": "alex", "password": "right-pass-123"}
        )
        assert registered.status_code == 200, registered.text
        alex_headers = {"Authorization": f"Bearer {registered.json()['token']}"}

        # Alex cannot see Bob's session at all (list isolation).
        listed = client.get("/api/sessions", headers=alex_headers).json()
        assert all(s["session_id"] != "sess_bob" for s in listed)

        # Alex cannot delete Bob's session even with the confirmation header —
        # the service refuses with unknown_session because of user isolation.
        resp = client.delete(
            "/api/sessions/sess_bob",
            headers={**alex_headers, "X-Session-Delete-Confirm": "sess_bob"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["reason_code"] == "unknown_session:sess_bob"
        # Bob's session is still present and Bob can still open it.
        assert store.load_session("sess_bob") is not None
        assert (
            client.get("/api/sessions/sess_bob", headers=bob_headers).status_code == 200
        )
