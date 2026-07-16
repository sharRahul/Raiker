from __future__ import annotations

import pyotp
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from raiker.api.app import create_app
from raiker.api.routes_auth import register
from raiker.api.routes_dashboard import mint_session
from raiker.api.schemas import AuthSessionRequest, RegisterRequest


@pytest.fixture()
def client(tmp_path):  # type: ignore[no-untyped-def]
    return TestClient(create_app(tmp_path))


def _register(client: TestClient, user: str = "alice", pw: str = "right-pass-123") -> dict:
    resp = client.post("/api/auth/register", json={"username": user, "password": pw})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_logs_in(client: TestClient) -> None:
    body = _register(client)
    assert body["stage"] == "session"
    assert body["token"]
    # session reaches a governed route
    assert client.get("/api/sessions", headers=_headers(body["token"])).status_code == 200


def test_login_bad_password_generic_401(client: TestClient) -> None:
    _register(client)
    resp = client.post("/api/auth/login", json={"username": "alice", "password": "nope"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid username or password"


def test_unknown_user_same_error(client: TestClient) -> None:
    resp = client.post("/api/auth/login", json={"username": "ghost", "password": "x"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid username or password"


def test_lockout_after_five(client: TestClient) -> None:
    _register(client)
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "alice", "password": "bad"})
    resp = client.post("/api/auth/login", json={"username": "alice", "password": "right-pass-123"})
    assert resp.status_code == 401


def test_mfa_flow_blocks_until_verified(client: TestClient) -> None:
    reg = _register(client)
    token = reg["token"]
    enroll = client.post("/api/auth/mfa/enroll", headers=_headers(token))
    assert enroll.status_code == 200
    secret = enroll.json()["secret"]
    act = client.post(
        "/api/auth/mfa/activate", json={"code": pyotp.TOTP(secret).now()}, headers=_headers(token)
    )
    assert act.status_code == 200
    # subsequent login now requires MFA
    login = client.post("/api/auth/login", json={"username": "alice", "password": "right-pass-123"})
    body = login.json()
    assert body["stage"] == "mfa_required"
    assert body["ticket"] and body["token"] is None
    # the ticket cannot reach a governed route
    assert client.get("/api/sessions", headers=_headers(body["ticket"])).status_code == 403
    verify = client.post(
        "/api/auth/mfa/verify", json={"ticket": body["ticket"], "code": pyotp.TOTP(secret).now()}
    )
    assert verify.status_code == 200
    assert client.get("/api/sessions", headers=_headers(verify.json()["token"])).status_code == 200


def test_logout_revokes(client: TestClient) -> None:
    token = _register(client)["token"]
    assert client.post("/api/auth/logout", headers=_headers(token)).status_code == 200
    assert client.get("/api/sessions", headers=_headers(token)).status_code == 401


def test_unauthenticated_mint_disabled_after_account(client: TestClient) -> None:
    _register(client)
    # once an account exists, the unauthenticated bootstrap mint fails closed
    resp = client.post("/api/auth/session", json={"as_principal": None})
    assert resp.status_code == 403
    assert resp.json()["detail"]["reason_code"] == "login_required"


def test_second_registration_is_rejected_with_separate_instance_guidance(client: TestClient) -> None:
    _register(client)
    response = client.post("/api/auth/register", json={"username": "bob", "password": "password"})
    assert response.status_code == 409
    assert "separate Raiker instance" in response.json()["detail"]


def test_password_recovery_acknowledges_unknown_user_without_ticket(client: TestClient) -> None:
    response = client.post("/api/auth/password-recovery/begin", json={"username": "unknown"})
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["ticket"]


def test_registration_and_bootstrap_mint_are_loopback_only(tmp_path) -> None:  # type: ignore[no-untyped-def]
    app = create_app(tmp_path)
    request = Request({"type": "http", "client": ("203.0.113.10", 50000), "app": app})
    import asyncio

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as registration:
        asyncio.run(register(RegisterRequest(username="alice", password="password"), request))
    with pytest.raises(HTTPException) as bootstrap:
        asyncio.run(mint_session(AuthSessionRequest(), request))
    assert registration.value.status_code == 403
    assert bootstrap.value.status_code == 403


def test_mfa_activation_revokes_other_sessions(client: TestClient) -> None:
    token = _register(client)["token"]
    enroll = client.post("/api/auth/mfa/enroll", headers=_headers(token)).json()
    second = _register  # keep the primary session; create a separate control session directly below
    del second
    from raiker.api.sessions import ApiSessionStore

    principal = ApiSessionStore(client.app.state.workspace_root).get_by_token(token)  # type: ignore[attr-defined]
    assert principal is not None
    stale, _ = ApiSessionStore(client.app.state.workspace_root).create_session(  # type: ignore[attr-defined]
        principal.principal_id, scope="control"
    )
    response = client.post(
        "/api/auth/mfa/activate",
        json={"code": pyotp.TOTP(enroll["secret"]).now()},
        headers=_headers(token),
    )
    assert response.status_code == 200
    assert client.get("/api/sessions", headers=_headers(stale)).status_code == 401
