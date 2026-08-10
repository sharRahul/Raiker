from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "test_ws"
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
def owner_token(bootstrapped_workspace: Path) -> str:
    store = ApiSessionStore(bootstrapped_workspace)
    raw, _ = store.create_session("principal_owner")
    return raw


@pytest.fixture
def client(app: FastAPI, bootstrapped_workspace: Path) -> TestClient:
    return TestClient(app)


class TestHealth:
    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        # BUG-86 — "ok" now means the server answers *and* its encrypted store
        # opens, so the lock screen cannot call the runtime operational while
        # every sign-in fails on a store that will not open.
        assert body["status"] == "ok"
        assert body["store"] == "ok"
        assert body["cipher_memory_security"] in {"on", "off"}


class TestUnauthenticated:
    def test_no_auth_header_returns_401(self, client: TestClient) -> None:
        resp = client.get("/api/capability-gates")
        assert resp.status_code == 401

    def test_bad_token_returns_401(self, client: TestClient) -> None:
        resp = client.get(
            "/api/capability-gates",
            headers={"Authorization": "Bearer invalidtoken123"},
        )
        assert resp.status_code == 401


class TestOwnerAuthenticated:
    def test_get_capability_gates_200(self, client: TestClient, owner_token: str) -> None:
        resp = client.get(
            "/api/capability-gates",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]["capability"]
        assert data[0]["state"]
        assert data[0]["source"]

    def test_get_runtime_mode_200(self, client: TestClient, owner_token: str) -> None:
        resp = client.get(
            "/api/runtime-mode",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode_name"]
        assert data["status"]

    def test_get_runtime_readiness_200(self, client: TestClient, owner_token: str) -> None:
        resp = client.get(
            "/api/runtime-readiness",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"]
        assert data["summary"]


class TestAiPrincipalDenied:
    def test_ai_principal_cannot_flip_gate_403(
        self, temp_workspace: Path, app: FastAPI,
    ) -> None:
        bootstrap_owner("owner", "Owner", workspace_root=temp_workspace)
        _create_ai_principal(temp_workspace)
        store = ApiSessionStore(temp_workspace)
        raw, _ = store.create_session("principal_ai_assistant")
        client = TestClient(app)
        resp = client.post(
            "/api/capability-gates/admin_mutation/set",
            json={"target_state": "enabled_policy_gated", "reason": "ai-try"},
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert resp.status_code == 403
        body = resp.json()
        detail = body.get("detail", body)
        assert not detail.get("ok", True)


def _create_ai_principal(workspace_root: Path) -> None:
    from raiker.contracts.ids import utc_now
    from raiker.storage.sqlite import SQLiteStore

    store = SQLiteStore(workspace_root)
    now = utc_now()
    with store.connect() as connection:
        connection.execute(
            """INSERT OR IGNORE INTO principals
               (principal_id, principal_type, display_name, role_ids, domain_scopes,
                max_runtime_mode, created_at, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "principal_ai_assistant",
                "ai_agent",
                "AI Assistant",
                '["assistant"]',
                "[]",
                "development_preview",
                now,
                1,
            ),
        )
