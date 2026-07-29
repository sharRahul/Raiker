from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.contracts.models import User
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


@pytest.fixture
def bootstrapped_workspace(temp_workspace: Path) -> Path:
    bootstrap_owner("owner", "Owner", workspace_root=temp_workspace)
    return temp_workspace


@pytest.fixture
def app(bootstrapped_workspace: Path) -> FastAPI:
    return create_app(bootstrapped_workspace)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _mint(client: TestClient) -> Any:
    return client.post("/api/auth/session", json={"as_principal": None})


def _token(client: TestClient) -> str:
    resp = _mint(client)
    assert resp.status_code == 200, resp.text
    return str(resp.json()["token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _load(store: SQLiteStore, session_id: str) -> dict[str, object]:
    row = store.load_session(session_id)
    assert row is not None
    return row


def _seed_owned_session(workspace_root: Path, session_id: str) -> None:
    """A session owned by the bootstrapped owner ('owner')."""
    SQLiteStore(workspace_root).create_session(session_id, str(workspace_root), title="Original", user_id="owner")


def _seed_foreign_session(workspace_root: Path, session_id: str) -> None:
    """A session owned by a *different* account than the bootstrapped owner."""
    store = SQLiteStore(workspace_root)
    store.insert_user(
        User(
            user_id="intruder",
            display_name="intruder",
            email=None,
            is_active=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
    )
    store.create_session(session_id, str(workspace_root), title="Foreign", user_id="intruder")


class TestArchiveLifecycle:
    def test_archive_hides_session_from_default_list(
        self, bootstrapped_workspace: Path, client: TestClient
    ) -> None:
        _seed_owned_session(bootstrapped_workspace, "sess_a")
        token = _token(client)

        response = client.put("/api/sessions/sess_a/archive", headers=_auth(token))
        assert response.status_code == 200, response.text
        assert response.json() == {"ok": True, "session_id": "sess_a", "archived": True}

        listed = client.get("/api/sessions", headers=_auth(token)).json()
        assert "sess_a" not in [item["session_id"] for item in listed]

    def test_archived_session_visible_with_include_archived(
        self, bootstrapped_workspace: Path, client: TestClient
    ) -> None:
        _seed_owned_session(bootstrapped_workspace, "sess_a")
        token = _token(client)
        client.put("/api/sessions/sess_a/archive", headers=_auth(token))

        listed = client.get(
            "/api/sessions?include_archived=true", headers=_auth(token)
        ).json()
        row = next(item for item in listed if item["session_id"] == "sess_a")
        assert row["archived"] is True
        assert row["archived_at"]

    def test_archive_is_reversible(
        self, bootstrapped_workspace: Path, client: TestClient
    ) -> None:
        _seed_owned_session(bootstrapped_workspace, "sess_a")
        token = _token(client)
        client.put("/api/sessions/sess_a/archive", headers=_auth(token))

        response = client.put("/api/sessions/sess_a/unarchive", headers=_auth(token))
        assert response.status_code == 200, response.text
        assert response.json() == {"ok": True, "session_id": "sess_a", "archived": False}

        listed = client.get("/api/sessions", headers=_auth(token)).json()
        assert "sess_a" in [item["session_id"] for item in listed]

    def test_archive_does_not_delete_turns(
        self, bootstrapped_workspace: Path, client: TestClient
    ) -> None:
        store = SQLiteStore(bootstrapped_workspace)
        store.create_session("sess_a", str(bootstrapped_workspace), title="Keep", user_id="owner")
        store.insert_turn("sess_a", "turn_a", "hello")
        token = _token(client)

        client.put("/api/sessions/sess_a/archive", headers=_auth(token))

        detail = client.get("/api/sessions/sess_a", headers=_auth(token)).json()
        assert [t["turn_id"] for t in detail["turns"]] == ["turn_a"]

    def test_archive_emits_audit_event(
        self, bootstrapped_workspace: Path, client: TestClient
    ) -> None:
        _seed_owned_session(bootstrapped_workspace, "sess_a")
        token = _token(client)
        client.put("/api/sessions/sess_a/archive", headers=_auth(token))

        events = client.get(
            "/api/events?session_id=sess_a", headers=_auth(token)
        ).json()
        assert any(e["event_type"] == "session_archived" for e in events)


class TestRename:
    def test_rename_updates_title(
        self, bootstrapped_workspace: Path, client: TestClient
    ) -> None:
        _seed_owned_session(bootstrapped_workspace, "sess_a")
        token = _token(client)

        response = client.put(
            "/api/sessions/sess_a/rename",
            headers=_auth(token),
            json={"title": "Renamed chat"},
        )
        assert response.status_code == 200, response.text
        assert response.json() == {
            "ok": True,
            "session_id": "sess_a",
            "title": "Renamed chat",
        }

        detail = client.get("/api/sessions/sess_a", headers=_auth(token)).json()
        assert detail["session"]["title"] == "Renamed chat"

    def test_rename_normalizes_whitespace(
        self, bootstrapped_workspace: Path, client: TestClient
    ) -> None:
        _seed_owned_session(bootstrapped_workspace, "sess_a")
        token = _token(client)

        response = client.put(
            "/api/sessions/sess_a/rename",
            headers=_auth(token),
            json={"title": "  spaced\t\nout   name  "},
        )
        assert response.status_code == 200, response.text
        assert response.json()["title"] == "spaced out name"

    def test_rename_rejects_empty_title(
        self, bootstrapped_workspace: Path, client: TestClient
    ) -> None:
        _seed_owned_session(bootstrapped_workspace, "sess_a")
        token = _token(client)

        response = client.put(
            "/api/sessions/sess_a/rename",
            headers=_auth(token),
            json={"title": "   "},
        )
        assert response.status_code == 422
        assert response.json()["detail"]["reason_code"].startswith("invalid_title")

    def test_rename_rejects_overlong_title(
        self, bootstrapped_workspace: Path, client: TestClient
    ) -> None:
        _seed_owned_session(bootstrapped_workspace, "sess_a")
        token = _token(client)

        response = client.put(
            "/api/sessions/sess_a/rename",
            headers=_auth(token),
            json={"title": "x" * 5000},
        )
        assert response.status_code == 422
        assert response.json()["detail"]["reason_code"].startswith("invalid_title")


class TestCrossAccountRefusal:
    def test_cannot_archive_another_accounts_session(
        self, bootstrapped_workspace: Path, client: TestClient
    ) -> None:
        _seed_foreign_session(bootstrapped_workspace, "sess_foreign")
        token = _token(client)

        response = client.put(
            "/api/sessions/sess_foreign/archive", headers=_auth(token)
        )
        assert response.status_code == 403
        # The foreign session is untouched and still active in its owner's scope.
        assert _load(SQLiteStore(bootstrapped_workspace), "sess_foreign")["archived"] == 0

    def test_cannot_rename_another_accounts_session(
        self, bootstrapped_workspace: Path, client: TestClient
    ) -> None:
        _seed_foreign_session(bootstrapped_workspace, "sess_foreign")
        token = _token(client)

        response = client.put(
            "/api/sessions/sess_foreign/rename",
            headers=_auth(token),
            json={"title": "hijacked"},
        )
        assert response.status_code == 403
        assert _load(SQLiteStore(bootstrapped_workspace), "sess_foreign")["title"] == "Foreign"

    def test_unknown_session_is_refused(
        self, bootstrapped_workspace: Path, client: TestClient
    ) -> None:
        token = _token(client)
        assert (
            client.put("/api/sessions/nope/archive", headers=_auth(token)).status_code
            == 403
        )
        assert (
            client.put(
                "/api/sessions/nope/rename",
                headers=_auth(token),
                json={"title": "x"},
            ).status_code
            == 403
        )


class TestStorageIsolation:
    def test_list_sessions_include_archived_is_owner_scoped(
        self, tmp_path: Path
    ) -> None:
        store = SQLiteStore(tmp_path)
        for user_id in ("user_a", "user_b"):
            store.insert_user(
                User(
                    user_id=user_id,
                    display_name=user_id,
                    email=None,
                    is_active=True,
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
            )
        store.create_session("s_a", str(tmp_path), user_id="user_a")
        store.create_session("s_b", str(tmp_path), user_id="user_b")

        assert store.set_session_archived("s_a", True, user_id="user_a") is True
        # user_b cannot archive user_a's session.
        assert store.set_session_archived("s_a", True, user_id="user_b") is False

        active = {s["session_id"] for s in store.list_sessions(user_id="user_a")}
        assert "s_a" not in active
        with_archived = {
            s["session_id"]
            for s in store.list_sessions(user_id="user_a", include_archived=True)
        }
        assert "s_a" in with_archived
        # user_a never sees user_b's session, archived or not.
        assert "s_b" not in with_archived

    def test_rename_session_owner_scoped(self, tmp_path: Path) -> None:
        store = SQLiteStore(tmp_path)
        for user_id in ("user_a", "user_b"):
            store.insert_user(
                User(
                    user_id=user_id,
                    display_name=user_id,
                    email=None,
                    is_active=True,
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
            )
        store.create_session("s_a", str(tmp_path), title="A", user_id="user_a")

        assert store.rename_session("s_a", "A2", user_id="user_b") is False
        assert _load(store, "s_a")["title"] == "A"
        assert store.rename_session("s_a", "A2", user_id="user_a") is True
        assert _load(store, "s_a")["title"] == "A2"
