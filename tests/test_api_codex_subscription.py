from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models.codex_app_server import CodexAccountStatus, CodexLogin


class FakeCodexSessions:
    async def status(self, principal_id: str) -> CodexAccountStatus:
        assert principal_id == "principal_owner"
        return CodexAccountStatus(signed_in=True, plan_type="plus")

    async def start_login(self, principal_id: str) -> CodexLogin:
        assert principal_id == "principal_owner"
        return CodexLogin(login_id="login_1")

    async def disconnect(self, principal_id: str) -> None:
        assert principal_id == "principal_owner"


def _headers(workspace: Path) -> dict[str, str]:
    token, _ = ApiSessionStore(workspace).create_session("principal_owner")
    return {"Authorization": f"Bearer {token}"}


def test_subscription_routes_expose_safe_status_and_start_local_login(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "subscription"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    app = create_app(workspace)
    client = TestClient(app)

    import raiker.api.routes_dashboard as routes

    sessions = FakeCodexSessions()
    monkeypatch.setattr(routes, "_codex_sessions", lambda request: sessions)

    status = client.get("/api/models/chatgpt-codex/status", headers=_headers(workspace))
    assert status.status_code == 200, status.text
    assert status.json() == {"connection_status": "connected", "plan_type": "plus"}
    assert "email" not in status.text.casefold()

    login = client.post("/api/models/chatgpt-codex/login", headers=_headers(workspace))
    assert login.status_code == 200, login.text
    assert login.json() == {"ok": True, "connection_status": "login_pending"}

    disconnect = client.delete("/api/models/chatgpt-codex/connection", headers=_headers(workspace))
    assert disconnect.status_code == 200, disconnect.text
    assert disconnect.json() == {"ok": True, "connection_configured": False}


def test_subscription_routes_require_auth(tmp_path: Path) -> None:
    workspace = tmp_path / "subscription"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    client = TestClient(create_app(workspace))

    assert client.get("/api/models/chatgpt-codex/status").status_code == 401
    assert client.post("/api/models/chatgpt-codex/login").status_code == 401
