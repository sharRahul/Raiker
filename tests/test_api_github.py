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


def test_the_issue_to_pr_routine_drafts_a_task_and_starts_nothing(
    api: tuple[TestClient, dict[str, str], Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """BUG-339 — the template becomes a Build task's instructions; its authority stays with the router."""
    import raiker.api.routes_github as routes

    client, h, _ws = api
    client.put("/api/git-credential", json={"token": _TOKEN}, headers=h)
    made = client.post(
        "/api/github/delegations",
        json={"repository": "github.com/octo/demo", "operations": ["fetch", "branch", "commit", "push", "pull_request"],
              "branch_pattern": "raiker/*"},
        headers=h,
    ).json()
    payload = {"repository": "octo/demo", "issue_number": 7, "work_branch": "raiker/issue-7",
               "delegation_id": made["delegation_id"]}
    # GitHub is asked whether the repository is still the delegated one; when it
    # cannot answer, the preview says the routine would park rather than run.
    unavailable = client.post("/api/github/routines/issue-to-pr", json=payload, headers=h).json()
    assert unavailable["blocked_needs_owner"] is True and unavailable["delegation_problems"]
    monkeypatch.setattr(routes, "_routine_http", lambda: None)
    tasks_before = client.get("/api/tasks", headers=h).json()
    routine = client.post(
        "/api/github/routines/issue-to-pr",
        json=payload,
        headers=h,
    )
    assert routine.status_code == 200, routine.text
    body = routine.json()
    assert body["delegation_problems"] == [], body["delegation_problems"]
    assert body["repository"] == "github.com/octo/demo" and body["blocked_needs_owner"] is False
    assert {s["decision"] for s in body["steps"] if s["operation"] != "read"} == {"runs_under_delegation"}
    assert body["title"] == "Issue #7 → pull request (octo/demo)"
    assert "raiker/issue-7" in body["description"] and "untrusted data" in body["description"]
    assert "Never delete branch, merge" in body["description"]
    # A preview: no task, no delegation spent.
    assert client.get("/api/tasks", headers=h).json() == tasks_before
    assert client.get("/api/github", headers=h).json()["delegations"][0]["actions_used"] == 0

    undelegated = client.post(
        "/api/github/routines/issue-to-pr",
        json={"repository": "octo/demo", "issue_number": 7, "work_branch": "raiker/issue-7"},
        headers=h,
    ).json()
    assert {s["decision"] for s in undelegated["steps"] if s["operation"] != "read"} == {"asks"}
    assert "asks the owner first" in undelegated["description"]


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
