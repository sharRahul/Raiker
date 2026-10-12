"""ADD-27 GH-19 — the GitHub routes keep their promises over HTTP.

Nothing secret comes back; sign-in attempts belong to the API session that
started them; the webhook is the one unauthenticated route and its signature is
its authentication; delegations are a person's to make.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.github.apps import store_secret_in_vault
from raiker.github.credentials import reset_verification_cache
from raiker.storage.sqlite import SQLiteStore
from tests.contract_cases.github import _PEM, _TOKEN, _github
from tests.github_fakes import CLIENT_ID


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, offline_default_model: None) -> tuple[TestClient, dict[str, str], Path]:
    reset_verification_cache()
    _github(monkeypatch)
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    client = TestClient(create_app(tmp_path))
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    return client, {"Authorization": f"Bearer {token}"}, tmp_path


def _second_session(client: TestClient) -> dict[str, str]:
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_the_connection_shows_six_states_and_never_a_secret(api: tuple[TestClient, dict[str, str], Path]) -> None:
    client, h, ws = api
    before = client.get("/api/github", headers=h).json()
    assert set(before["states"]) == {
        "connected_account", "application_installed", "repository_authorised",
        "credential_available", "capability_enabled", "operation_approved",
    }
    assert not any(before["states"].values())
    client.put("/api/git-credential", json={"token": _TOKEN}, headers=h)
    pat = client.get("/api/github", headers=h).json()["credentials"][0]["credential_id"]
    checked = client.post(f"/api/github/credentials/{pat}/check", headers=h).json()
    assert checked["states"]["connected_account"] and checked["states"]["credential_available"]
    assert checked["selected"]["account_login"] == "octo"
    client.put("/api/github/app", json={"client_id": CLIENT_ID, "private_key": {"kind": "vault", "value": _PEM}}, headers=h)
    everything = json.dumps([client.get("/api/github", headers=h).json(), checked])
    assert _TOKEN not in everything and "PRIVATE KEY" not in everything


def test_a_sign_in_attempt_belongs_to_the_session_that_started_it(api: tuple[TestClient, dict[str, str], Path]) -> None:
    client, h, _ws = api
    started = client.post("/api/github/sign-in", json={"method": "device"}, headers=h).json()
    assert started["user_code"] == "WDJB-MJHT" and started["outcome"] == "pending"
    other = _second_session(client)
    refused = client.post(f"/api/github/sign-in/{started['attempt_id']}/poll", headers=other)
    assert refused.status_code == 409 and refused.json()["detail"]["reason_code"] == "github_sign_in_other_session"
    cancelled = client.post(f"/api/github/sign-in/{started['attempt_id']}/cancel", headers=h).json()
    assert cancelled["outcome"] == "cancelled"


def test_browser_sign_in_is_unavailable_without_a_client_secret(api: tuple[TestClient, dict[str, str], Path]) -> None:
    client, h, _ws = api
    refused = client.post("/api/github/sign-in", json={"method": "browser"}, headers=h)
    assert refused.status_code == 409


def test_a_callback_with_a_state_raiker_never_issued_connects_nothing(api: tuple[TestClient, dict[str, str], Path]) -> None:
    client, h, _ws = api
    page = client.get("/api/github/callback?state=forged&code=abc", headers=h)
    assert page.status_code == 400 and "not one Raiker started" in page.text
    assert client.get("/api/github", headers=h).json()["credentials"] == []


def test_a_delegation_refuses_merge_and_is_listed(api: tuple[TestClient, dict[str, str], Path]) -> None:
    client, h, _ws = api
    client.put("/api/git-credential", json={"token": _TOKEN}, headers=h)
    refused = client.post(
        "/api/github/delegations",
        json={"repository": "github.com/octo/demo", "operations": ["merge"], "branch_pattern": "raiker/*"},
        headers=h,
    )
    assert refused.status_code == 422 and refused.json()["detail"]["reason_code"] == "delegation_operation_not_delegable:merge"
    made = client.post(
        "/api/github/delegations",
        json={"repository": "github.com/octo/demo", "operations": ["push"], "branch_pattern": "raiker/*", "max_actions": 3},
        headers=h,
    ).json()
    listed = client.get("/api/github", headers=h).json()
    assert [d["delegation_id"] for d in listed["delegations"]] == [made["delegation_id"]]
    assert listed["states"]["operation_approved"] is True
    revoked = client.delete(f"/api/github/delegations/{made['delegation_id']}", headers=h).json()
    assert revoked["delegations"] == []


def _signed(body: dict[str, Any], secret: str, event: str = "ping", delivery: str = "d-1") -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(body).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return raw, {
        "X-Hub-Signature-256": signature, "X-GitHub-Event": event,
        "X-GitHub-Delivery": delivery, "Content-Type": "application/json",
    }


def test_the_webhook_answers_only_a_signed_delivery(api: tuple[TestClient, dict[str, str], Path]) -> None:
    client, _h, ws = api
    store = SQLiteStore(ws)
    assert client.post("/api/github/webhook", content=b"{}").status_code == 404  # off until configured
    store.upsert_github_app(
        "byo", updated_by=None, client_id=CLIENT_ID, webhooks_enabled=1,
        webhook_secret_ref=json.dumps(store_secret_in_vault(store, "byo_webhook_secret", "s3cret-hook")),
    )
    raw, headers = _signed({"zen": "hi"}, "wrong")
    assert client.post("/api/github/webhook", content=raw, headers=headers).status_code == 401
    raw, headers = _signed({"zen": "hi"}, "s3cret-hook")
    accepted = client.post("/api/github/webhook", content=raw, headers=headers)
    assert accepted.status_code == 200 and accepted.json() == {"outcome": "pong"}
    assert client.post("/api/github/webhook", content=raw, headers=headers).json() == {"outcome": "duplicate"}
