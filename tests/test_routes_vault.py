from __future__ import annotations

import json

import pyotp
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture()
def ctx(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.delenv("RAIKER_CONNECTOR_VAULT_KEY", raising=False)
    client = TestClient(create_app(tmp_path))
    reg = client.post(
        "/api/auth/register", json={"username": "alice", "password": "right-pass-123"}
    ).json()
    return client, reg["token"], tmp_path


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _elevate(client: TestClient, token: str, password: str = "right-pass-123") -> str:
    resp = client.post("/api/auth/elevate", json={"password": password}, headers=_h(token))
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def test_status_missing_then_valid(ctx) -> None:  # type: ignore[no-untyped-def]
    client, token, _ = ctx
    assert client.get("/api/vault/status", headers=_h(token)).json()["state"] == "missing"
    elevated = _elevate(client, token)
    key = Fernet.generate_key().decode("ascii")
    put = client.put("/api/vault/key", json={"key": key}, headers=_h(elevated))
    assert put.status_code == 200
    assert put.json()["state"] == "configured_valid"
    assert client.get("/api/vault/status", headers=_h(token)).json()["state"] == "configured_valid"


def test_put_requires_elevated(ctx) -> None:  # type: ignore[no-untyped-def]
    client, token, _ = ctx
    key = Fernet.generate_key().decode("ascii")
    resp = client.put("/api/vault/key", json={"key": key}, headers=_h(token))
    assert resp.status_code == 403


def test_put_rejects_invalid_key(ctx) -> None:  # type: ignore[no-untyped-def]
    client, token, _ = ctx
    elevated = _elevate(client, token)
    resp = client.put("/api/vault/key", json={"key": "not-a-key"}, headers=_h(elevated))
    assert resp.status_code == 400


def test_delete_clears(ctx) -> None:  # type: ignore[no-untyped-def]
    client, token, _ = ctx
    elevated = _elevate(client, token)
    client.put(
        "/api/vault/key",
        json={"key": Fernet.generate_key().decode("ascii")},
        headers=_h(elevated),
    )
    elevated2 = _elevate(client, token)
    resp = client.request("DELETE", "/api/vault/key", headers=_h(elevated2))
    assert resp.status_code == 200
    assert resp.json()["state"] == "missing"


def test_require_mfa_for_vault_policy(ctx) -> None:  # type: ignore[no-untyped-def]
    client, token, ws = ctx
    # enroll + activate MFA
    enroll = client.post("/api/auth/mfa/enroll", headers=_h(token)).json()
    secret = enroll["secret"]
    client.post("/api/auth/mfa/activate", json={"code": pyotp.TOTP(secret).now()}, headers=_h(token))
    # opt in to require-MFA-for-vault
    store = SQLiteStore(ws)
    account = store.get_account_by_username("alice")
    assert account is not None
    pid = account["principal_id"]
    store.put_user_settings(
        pid, json.dumps({"security.require_mfa_for_vault": True}), "t0"
    )
    elevated = _elevate(client, token)
    key = Fernet.generate_key().decode("ascii")
    # without MFA code -> blocked
    blocked = client.put("/api/vault/key", json={"key": key}, headers=_h(elevated))
    assert blocked.status_code == 403
    # with MFA code -> allowed
    ok = client.put(
        "/api/vault/key",
        json={"key": key, "mfa_code": pyotp.TOTP(secret).now()},
        headers=_h(elevated),
    )
    assert ok.status_code == 200
