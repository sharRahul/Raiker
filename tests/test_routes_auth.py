from __future__ import annotations

import pyotp
import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app


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
