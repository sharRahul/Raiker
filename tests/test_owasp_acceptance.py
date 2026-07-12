"""OWASP acceptance mapping for the local lock screen (spec §5.1).

Each test maps to a criterion: A01/A07 (broken access / session), A03 (injection),
A04 (brute force), A05 (enumeration). Also asserts the MFA/Vault independence
guarantees from the design.
"""

from __future__ import annotations

import pyotp
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.auth.accounts import AccountService


@pytest.fixture()
def client(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.delenv("RAIKER_CONNECTOR_VAULT_KEY", raising=False)
    return TestClient(create_app(tmp_path))


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, user: str = "alice", pw: str = "right-pass-123") -> dict:
    return client.post("/api/auth/register", json={"username": user, "password": pw}).json()


# ── A01 / A07: broken access control, MFA cannot be bypassed ────────────────
def test_a01_mfa_pending_cannot_reach_governed_routes(client: TestClient) -> None:
    token = _register(client)["token"]
    secret = client.post("/api/auth/mfa/enroll", headers=_h(token)).json()["secret"]
    client.post("/api/auth/mfa/activate", json={"code": pyotp.TOTP(secret).now()}, headers=_h(token))
    ticket = client.post(
        "/api/auth/login", json={"username": "alice", "password": "right-pass-123"}
    ).json()["ticket"]
    # every governed surface refuses the pre-MFA ticket
    for route in ("/api/sessions", "/api/settings", "/api/vault/status", "/api/tasks"):
        assert client.get(route, headers=_h(ticket)).status_code == 403


def test_a07_password_change_revokes_other_sessions(client: TestClient, tmp_path) -> None:  # type: ignore[no-untyped-def]
    token = _register(client)["token"]
    sessions = ApiSessionStore(tmp_path)
    pid = AccountService(tmp_path)._store.get_account_by_username("alice")["principal_id"]  # noqa: SLF001
    stale, _ = sessions.create_session(pid, scope="control")
    assert client.get("/api/sessions", headers=_h(stale)).status_code == 200
    client.post(
        "/api/auth/password",
        json={"old_password": "right-pass-123", "new_password": "brand-new-pass"},
        headers=_h(token),
    )
    assert client.get("/api/sessions", headers=_h(stale)).status_code == 401


# ── A03: injection ──────────────────────────────────────────────────────────
def test_a03_sql_injection_in_credentials_is_inert(client: TestClient) -> None:
    evil = "alice'; DROP TABLE account_credentials;--"
    assert client.post("/api/auth/register", json={"username": evil, "password": "p"}).status_code == 200
    # table still works; the injection string is just a literal username
    assert client.post("/api/auth/login", json={"username": evil, "password": "p"}).json()["stage"] == "session"
    assert (
        client.post("/api/auth/login", json={"username": "alice", "password": "x"}).status_code
        == 401
    )


# ── A04: brute-force lockout ────────────────────────────────────────────────
def test_a04_lockout_after_five(client: TestClient) -> None:
    _register(client)
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "alice", "password": "bad"})
    assert (
        client.post("/api/auth/login", json={"username": "alice", "password": "right-pass-123"}).status_code
        == 401
    )


# ── A05: no username enumeration ────────────────────────────────────────────
def test_a05_generic_error_no_enumeration(client: TestClient) -> None:
    _register(client)
    unknown = client.post("/api/auth/login", json={"username": "ghost", "password": "x"})
    wrong = client.post("/api/auth/login", json={"username": "alice", "password": "x"})
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"] == "Invalid username or password"


# ── Independence guarantees ─────────────────────────────────────────────────
def test_mfa_works_without_vault(client: TestClient) -> None:
    token = _register(client)["token"]
    enroll = client.post("/api/auth/mfa/enroll", headers=_h(token))
    assert enroll.status_code == 200  # no vault configured, still succeeds
    secret = enroll.json()["secret"]
    assert (
        client.post(
            "/api/auth/mfa/activate", json={"code": pyotp.TOTP(secret).now()}, headers=_h(token)
        ).status_code
        == 200
    )


def test_vault_works_without_mfa(client: TestClient) -> None:
    token = _register(client)["token"]  # no MFA enrolled
    elevated = client.post(
        "/api/auth/elevate", json={"password": "right-pass-123"}, headers=_h(token)
    ).json()["token"]
    put = client.put(
        "/api/vault/key",
        json={"key": Fernet.generate_key().decode("ascii")},
        headers=_h(elevated),
    )
    assert put.status_code == 200
    assert put.json()["state"] == "configured_valid"
