from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.storage.sqlite import SQLiteStore

PROTECTED_GET_ROUTES = [
    "/api/sessions",
    "/api/turns/turn_x",
    "/api/events",
    "/api/checkpoints",
    "/api/tasks",
    "/api/models",
    "/api/diagnostics",
]


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


@pytest.fixture
def bootstrapped_workspace(temp_workspace: Path) -> Path:
    bootstrap_owner("rahul", "Rahul", workspace_root=temp_workspace)
    return temp_workspace


@pytest.fixture
def app(bootstrapped_workspace: Path) -> FastAPI:
    return create_app(bootstrapped_workspace)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _mint(client: TestClient, as_principal: str | None = None) -> httpx.Response:
    return client.post("/api/auth/session", json={"as_principal": as_principal})


def _token(client: TestClient) -> str:
    resp = _mint(client)
    assert resp.status_code == 200, resp.text
    return str(resp.json()["token"])


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_ai_principal(workspace_root: Path) -> str:
    store = SQLiteStore(workspace_root)
    with store.connect() as connection:
        connection.execute(
            """INSERT OR IGNORE INTO principals
               (principal_id, principal_type, display_name, role_ids, domain_scopes,
                max_runtime_mode, created_at, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("principal_ai", "ai_agent", "AI", "[]", "[]", "development_preview", utc_now(), 1),
        )
    return "principal_ai"


class TestAuthMint:
    def test_owner_can_mint_a_token(self, client: TestClient) -> None:
        resp = _mint(client)
        assert resp.status_code == 200
        body = resp.json()
        assert body["token"]
        assert body["principal_id"] == "principal_rahul"
        assert "session_id" in body

    def test_no_owner_is_rejected(self, temp_workspace: Path) -> None:
        # Workspace without bootstrap → no local owner.
        client = TestClient(create_app(temp_workspace))
        resp = _mint(client)
        assert resp.status_code == 403
        assert resp.json()["detail"]["reason_code"] == "no_local_owner"

    def test_ai_principal_cannot_mint(self, bootstrapped_workspace: Path, client: TestClient) -> None:
        ai = _create_ai_principal(bootstrapped_workspace)
        resp = _mint(client, as_principal=ai)
        assert resp.status_code == 403
        # resolve_local_principal refuses AI principals before we even check the type.
        assert not resp.json()["detail"]["ok"]


class TestAuthRequired:
    @pytest.mark.parametrize("route", PROTECTED_GET_ROUTES)
    def test_requires_bearer(self, client: TestClient, route: str) -> None:
        assert client.get(route).status_code == 401

    @pytest.mark.parametrize("route", PROTECTED_GET_ROUTES)
    def test_bad_token_rejected(self, client: TestClient, route: str) -> None:
        assert client.get(route, headers=_auth_headers("nope")).status_code == 401


class TestReads:
    def test_models_lists_profiles_without_silent_hosted_fallback(self, client: TestClient) -> None:
        resp = client.get("/api/models", headers=_auth_headers(_token(client)))
        assert resp.status_code == 200
        body = resp.json()
        assert body["no_silent_hosted_fallback"] is True
        ids = [p["profile_id"] for p in body["profiles"]]
        assert "raiker-local-llama-cpp" in ids
        assert all("selected" in p and "provider" in p for p in body["profiles"])

    def test_diagnostics_reports_disabled_capabilities_and_scope(self, client: TestClient) -> None:
        resp = client.get("/api/diagnostics", headers=_auth_headers(_token(client)))
        assert resp.status_code == 200
        body = resp.json()
        assert "local single-user runtime" in body["scope_note"]
        # Tier 2–6 / governance capabilities ship disabled by default.
        assert len(body["disabled_capabilities"]) > 0
        assert "counts" in body and "events" in body["counts"]

    def test_empty_lists_are_ok(self, client: TestClient) -> None:
        token = _token(client)
        for route in ["/api/sessions", "/api/events", "/api/checkpoints", "/api/tasks"]:
            resp = client.get(route, headers=_auth_headers(token))
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)

    def test_unknown_ids_404(self, client: TestClient) -> None:
        token = _token(client)
        assert client.get("/api/sessions/nope", headers=_auth_headers(token)).status_code == 404
        assert client.get("/api/turns/nope", headers=_auth_headers(token)).status_code == 404
        assert client.get("/api/checkpoints/nope", headers=_auth_headers(token)).status_code == 404

    def test_seeded_session_and_turn_are_readable(
        self, bootstrapped_workspace: Path, client: TestClient
    ) -> None:
        store = SQLiteStore(bootstrapped_workspace)
        store.create_session("sess_t", str(bootstrapped_workspace), title="Demo")
        store.insert_turn("sess_t", "turn_t", "hello")
        EventLogWriter(store).append(
            make_event(
                session_id="sess_t",
                turn_id="turn_t",
                event_type="prompt_received",
                actor="test",
                payload={"k": "v"},
            )
        )
        token = _token(client)

        sessions = client.get("/api/sessions", headers=_auth_headers(token)).json()
        assert any(s["session_id"] == "sess_t" and s["turn_count"] == 1 for s in sessions)

        detail = client.get("/api/sessions/sess_t", headers=_auth_headers(token)).json()
        assert detail["session"]["session_id"] == "sess_t"
        assert [t["turn_id"] for t in detail["turns"]] == ["turn_t"]

        turn = client.get("/api/turns/turn_t", headers=_auth_headers(token)).json()
        assert turn["turn"]["turn_id"] == "turn_t"
        assert any(e["event_type"] == "prompt_received" for e in turn["events"])


class TestReadsDoNotMutate:
    def test_listing_events_does_not_write_events(
        self, bootstrapped_workspace: Path, client: TestClient
    ) -> None:
        store = SQLiteStore(bootstrapped_workspace)
        token = _token(client)  # minting resolves a principal (an audited event); do it first
        before = store.count_events()
        # Pure list reads write nothing. (Diagnostics is excluded: it audits principal resolution,
        # the same governed behavior as the CLI — an audit log entry, not a state mutation.)
        client.get("/api/events", headers=_auth_headers(token))
        client.get("/api/sessions", headers=_auth_headers(token))
        client.get("/api/models", headers=_auth_headers(token))
        assert store.count_events() == before
