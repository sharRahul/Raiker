# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models.codex_app_server import CodexAccountStatus, CodexLogin


class FakeCodexSessions:
    """A local Codex client that is already signed in to somebody's ChatGPT."""

    def __init__(self, signed_in: bool = True) -> None:
        self.signed_in = signed_in
        self.pending = False
        self.status_calls = 0

    async def status(self, principal_id: str) -> CodexAccountStatus:
        assert principal_id == "principal_owner"
        self.status_calls += 1
        return CodexAccountStatus(signed_in=self.signed_in, plan_type="plus")

    async def passive_status(self, principal_id: str) -> CodexAccountStatus | None:
        return await self.status(principal_id) if self.pending else None

    async def start_login(self, principal_id: str, method: str = "browser") -> CodexLogin:
        assert principal_id == "principal_owner"
        self.pending = True
        self.method = method
        if method == "device_code":
            return CodexLogin(
                login_id="login_2",
                method="device_code",
                url="https://auth.example.test/device",
                user_code="ABCD-1234",
            )
        return CodexLogin(login_id="login_1", url="https://auth.example.test/authorize")

    async def cancel_login(self, principal_id: str) -> None:
        assert principal_id == "principal_owner"
        self.pending = False

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

    # BUG-259 — Codex is signed in, and nobody here has said to use that
    # account. Those are different facts, and the read reports the second one
    # honestly instead of quietly adopting the first.
    status = client.get("/api/models/chatgpt-codex/status", headers=_headers(workspace))
    assert status.status_code == 200, status.text
    assert status.json() == {"connection_status": "not_connected", "plan_type": None}
    assert sessions.status_calls == 0
    assert "email" not in status.text.casefold()

    login = client.post("/api/models/chatgpt-codex/login", headers=_headers(workspace))
    assert login.status_code == 200, login.text
    # FIXED-1390 — the owner's browser opens the page, so the route hands it over.
    assert login.json() == {
        "ok": True,
        "connection_status": "login_pending",
        "method": "browser",
        "url": "https://auth.example.test/authorize",
        "user_code": None,
    }
    polled = client.get("/api/models/chatgpt-codex/status", headers=_headers(workspace))
    assert polled.json()["connection_status"] == "available"

    connect = client.post("/api/models/chatgpt-codex/connection", headers=_headers(workspace))
    assert connect.status_code == 200, connect.text
    assert connect.json()["connection_status"] == "connected"

    after = client.get("/api/models/chatgpt-codex/status", headers=_headers(workspace))
    assert after.json()["connection_status"] == "connected"

    disconnect = client.delete("/api/models/chatgpt-codex/connection", headers=_headers(workspace))
    assert disconnect.status_code == 200, disconnect.text
    assert disconnect.json() == {"ok": True, "connection_configured": False}


def test_reading_the_status_never_connects_the_subscription(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BUG-259 — the defect: a fresh Raiker adopted whoever Codex was signed in as.

    Opening the setup page on a machine where somebody had once signed Codex in
    connected that ChatGPT account, listed its models, and reported it as
    connected — without anybody choosing it. A read must not do that however
    many times it is called.
    """
    workspace = tmp_path / "subscription"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    client = TestClient(create_app(workspace))

    import raiker.api.routes_dashboard as routes

    sessions = FakeCodexSessions()
    monkeypatch.setattr(routes, "_codex_sessions", lambda request: sessions)

    for _ in range(3):
        body = client.get("/api/models/chatgpt-codex/status", headers=_headers(workspace)).json()
        assert body["connection_status"] == "not_connected"
    assert sessions.status_calls == 0

    from raiker.models.connections import get_model_connection
    from raiker.storage.sqlite import SQLiteStore

    assert (
        get_model_connection(SQLiteStore(workspace), "principal_owner", "chatgpt-codex")
        is None
    ), "reading the status must not record a connection"


def test_a_signed_out_codex_cannot_be_connected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Recording a connection to an account that does not exist offers nothing."""
    workspace = tmp_path / "subscription"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    client = TestClient(create_app(workspace))

    import raiker.api.routes_dashboard as routes

    monkeypatch.setattr(
        routes, "_codex_sessions", lambda request: FakeCodexSessions(signed_in=False)
    )

    status = client.get("/api/models/chatgpt-codex/status", headers=_headers(workspace))
    assert status.json()["connection_status"] == "not_connected"

    refused = client.post("/api/models/chatgpt-codex/connection", headers=_headers(workspace))
    assert refused.status_code == 409
    assert refused.json()["detail"]["reason_code"] == "chatgpt_subscription_signed_out"


def test_subscription_routes_require_auth(tmp_path: Path) -> None:
    workspace = tmp_path / "subscription"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    client = TestClient(create_app(workspace))

    assert client.get("/api/models/chatgpt-codex/status").status_code == 401
    assert client.post("/api/models/chatgpt-codex/login").status_code == 401
    assert client.post("/api/models/chatgpt-codex/connection").status_code == 401


def test_device_code_sign_in_and_cancel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "subscription"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    client = TestClient(create_app(workspace))

    import raiker.api.routes_dashboard as routes

    sessions = FakeCodexSessions()
    monkeypatch.setattr(routes, "_codex_sessions", lambda request: sessions)

    login = client.post(
        "/api/models/chatgpt-codex/login", headers=_headers(workspace), json={"method": "device_code"}
    )
    assert login.status_code == 200, login.text
    assert login.json()["user_code"] == "ABCD-1234"
    assert sessions.method == "device_code"
    refused = client.post(
        "/api/models/chatgpt-codex/login", headers=_headers(workspace), json={"method": "token"}
    )
    assert refused.status_code == 422
    cancel = client.delete("/api/models/chatgpt-codex/login", headers=_headers(workspace))
    assert cancel.status_code == 200, cancel.text
    assert sessions.pending is False


def test_a_missing_codex_is_a_conflict_with_its_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from raiker.models.exceptions import ProviderConfigurationError

    workspace = tmp_path / "subscription"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    client = TestClient(create_app(workspace))

    import raiker.api.routes_dashboard as routes

    class Missing(FakeCodexSessions):
        async def start_login(self, principal_id: str, method: str = "browser") -> CodexLogin:
            raise ProviderConfigurationError("codex_app_server_not_installed")

    monkeypatch.setattr(routes, "_codex_sessions", lambda request: Missing())
    login = client.post("/api/models/chatgpt-codex/login", headers=_headers(workspace))
    assert login.status_code == 409
    assert "codex_app_server_not_installed" in login.text
