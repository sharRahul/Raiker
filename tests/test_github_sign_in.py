"""ADD-27 GH-31…GH-37 — signing in with a GitHub App, against a stand-in GitHub.

Covers the specification's §20 authentication list: first connection, cancel,
deny, invalid state, PKCE mismatch, expiry, device polling limits, account
switching, refresh and its failure, repository discovery by id, and disconnect.
"""

from __future__ import annotations

import base64
import hashlib
import json
import urllib.parse
from pathlib import Path
from typing import Any

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.github.apps import store_secret_in_vault
from raiker.github.auth import GitHubSignIn, SignInError, discover_repositories
from raiker.github.credentials import METHOD_APP_USER, app_user_vault_keys, reset_verification_cache
from raiker.github.http import GitHubHttp
from raiker.runtime.git_credential import RUNTIME_TOKEN_VAR, GitCredentialBroker, GitCredentialError
from raiker.storage.deletion_journal import read_deletions
from raiker.storage.sqlite import SQLiteStore
from tests.github_fakes import CLIENT_ID, CLIENT_SECRET, FakeGitHub

OWNER = "principal_owner"


@pytest.fixture
def ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv("RAIKER_GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("RAIKER_GITHUB_APP_CLIENT_ID", CLIENT_ID)
    reset_verification_cache()
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    return tmp_path


@pytest.fixture
def github() -> FakeGitHub:
    return FakeGitHub()


def _sign_in(ws: Path, github: FakeGitHub) -> GitHubSignIn:
    return GitHubSignIn(SQLiteStore(ws), OWNER, http=GitHubHttp(github))


def _make_due(ws: Path, attempt_id: str) -> None:
    SQLiteStore(ws).set_github_auth_poll(attempt_id, interval=5, next_poll_at="2000-01-01T00:00:00Z")


def _byo_app(ws: Path) -> None:
    store = SQLiteStore(ws)
    store.upsert_github_app(
        "byo", updated_by=OWNER, client_id=CLIENT_ID, app_id="4242",
        client_secret_ref=json.dumps(store_secret_in_vault(store, "byo_client_secret", CLIENT_SECRET)),
        callback_url="https://raiker.example.org/github/callback",
    )


# ── device flow ─────────────────────────────────────────────────────────


def test_without_a_published_client_id_sign_in_is_not_available(
    ws: Path, github: FakeGitHub, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("RAIKER_GITHUB_APP_CLIENT_ID")
    with pytest.raises(SignInError) as caught:
        _sign_in(ws, github).start_device("sess_ui")
    assert caught.value.reason == "github_app_not_available"
    assert github.requests == []


def test_a_device_sign_in_connects_a_verified_selected_account(ws: Path, github: FakeGitHub) -> None:
    sign_in = _sign_in(ws, github)
    attempt = sign_in.start_device("sess_ui")
    assert attempt["user_code"] == "WDJB-MJHT" and attempt["outcome"] == "pending"
    # The device code is a secret: never on the attempt row.
    assert "device-code-secret" not in json.dumps(attempt)

    _make_due(ws, attempt["attempt_id"])
    assert sign_in.poll_device(attempt["attempt_id"], "sess_ui")["outcome"] == "pending"
    github.device_answers.append(github.issue((101, "octo")))
    _make_due(ws, attempt["attempt_id"])
    done = sign_in.poll_device(attempt["attempt_id"], "sess_ui")

    assert done["outcome"] == "connected"
    broker = GitCredentialBroker(SQLiteStore(ws), OWNER, http=GitHubHttp(github))
    selected = broker.selected_credential()
    assert selected is not None and selected["method"] == METHOD_APP_USER
    assert selected["account_login"] == "octo" and selected["selector"] == "device"
    assert "ghu_" not in json.dumps(selected)
    # Connecting granted nothing.
    with pytest.raises(GitCredentialError) as caught, broker.lend(operation="push"):
        pass
    assert caught.value.reason == "git_grant_required"


def test_polling_respects_the_interval_and_slows_down(ws: Path, github: FakeGitHub) -> None:
    sign_in = _sign_in(ws, github)
    attempt = sign_in.start_device("sess_ui")
    before = len(github.requests)
    # Not yet due: no request is made.
    sign_in.poll_device(attempt["attempt_id"], "sess_ui")
    assert len(github.requests) == before
    github.device_answers.append({"error": "slow_down"})
    _make_due(ws, attempt["attempt_id"])
    slowed = sign_in.poll_device(attempt["attempt_id"], "sess_ui")
    assert slowed["poll_interval"] == 10 and slowed["outcome"] == "pending"


@pytest.mark.parametrize(("error", "outcome"), [("access_denied", "denied"), ("expired_token", "expired")])
def test_a_denied_or_expired_device_sign_in_connects_nothing(
    ws: Path, github: FakeGitHub, error: str, outcome: str
) -> None:
    sign_in = _sign_in(ws, github)
    attempt = sign_in.start_device("sess_ui")
    github.device_answers.append({"error": error})
    _make_due(ws, attempt["attempt_id"])
    assert sign_in.poll_device(attempt["attempt_id"], "sess_ui")["outcome"] == outcome
    assert SQLiteStore(ws).list_git_credentials(OWNER) == []


def test_an_attempt_answers_only_the_session_that_started_it(ws: Path, github: FakeGitHub) -> None:
    sign_in = _sign_in(ws, github)
    attempt = sign_in.start_device("sess_ui")
    with pytest.raises(SignInError) as caught:
        sign_in.poll_device(attempt["attempt_id"], "sess_other")
    assert caught.value.reason == "github_sign_in_other_session"
    assert sign_in.cancel(attempt["attempt_id"], "sess_ui")["outcome"] == "cancelled"


# ── browser flow ────────────────────────────────────────────────────────


def _start_browser(ws: Path, github: FakeGitHub) -> tuple[GitHubSignIn, dict[str, str]]:
    _byo_app(ws)
    sign_in = _sign_in(ws, github)
    _attempt, url = sign_in.start_browser("sess_ui", "byo")
    query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
    return sign_in, query


def test_browser_sign_in_uses_state_and_s256_pkce(ws: Path, github: FakeGitHub) -> None:
    sign_in, query = _start_browser(ws, github)
    assert query["code_challenge_method"] == "S256" and len(query["code_challenge"]) == 43
    assert query["redirect_uri"] == "https://raiker.example.org/github/callback"
    github.code_verifiers["code-1"] = query["code_challenge"]
    done = sign_in.complete_browser("sess_ui", state=query["state"], code="code-1")
    assert done["outcome"] == "connected"
    # The code is redeemed once.
    with pytest.raises(SignInError) as caught:
        sign_in.complete_browser("sess_ui", state=query["state"], code="code-1")
    assert caught.value.reason == "github_sign_in_already_used"


def test_an_invalid_state_or_another_session_is_refused(ws: Path, github: FakeGitHub) -> None:
    sign_in, query = _start_browser(ws, github)
    with pytest.raises(SignInError) as invalid:
        sign_in.complete_browser("sess_ui", state="forged-state", code="code-1")
    assert invalid.value.reason == "github_sign_in_state_invalid"
    with pytest.raises(SignInError) as other:
        sign_in.complete_browser("sess_other", state=query["state"], code="code-1")
    assert other.value.reason == "github_sign_in_other_session"


def test_a_verifier_that_does_not_match_the_challenge_is_refused(ws: Path, github: FakeGitHub) -> None:
    sign_in, query = _start_browser(ws, github)
    github.code_verifiers["code-1"] = "a-different-challenge-entirely-000000000000"
    with pytest.raises(SignInError) as caught:
        sign_in.complete_browser("sess_ui", state=query["state"], code="code-1")
    assert caught.value.reason == "bad_verification_code"
    assert SQLiteStore(ws).list_git_credentials(OWNER) == []


def test_a_cancelled_browser_sign_in_connects_nothing(ws: Path, github: FakeGitHub) -> None:
    sign_in, query = _start_browser(ws, github)
    done = sign_in.complete_browser("sess_ui", state=query["state"], code=None, error="access_denied")
    assert done["outcome"] == "denied"


def test_an_expired_browser_attempt_is_refused(ws: Path, github: FakeGitHub) -> None:
    sign_in, query = _start_browser(ws, github)
    store = SQLiteStore(ws)
    with store.connect() as connection:
        connection.execute("UPDATE github_auth_attempts SET expires_at = '2000-01-01T00:00:00Z'")
    with pytest.raises(SignInError) as caught:
        sign_in.complete_browser("sess_ui", state=query["state"], code="code-1")
    assert caught.value.reason == "github_sign_in_expired"


def test_browser_sign_in_needs_a_secret_this_host_holds(ws: Path, github: FakeGitHub) -> None:
    with pytest.raises(SignInError) as caught:
        _sign_in(ws, github).start_browser("sess_ui", "official")
    assert caught.value.reason == "github_browser_sign_in_unavailable"


# ── refresh, switching, repositories, disconnect ────────────────────────


def _connected(ws: Path, github: FakeGitHub, account: tuple[int, str] = (101, "octo")) -> str:
    sign_in = _sign_in(ws, github)
    attempt = sign_in.start_device("sess_ui")
    github.device_answers.append(github.issue(account))
    _make_due(ws, attempt["attempt_id"])
    return str(sign_in.poll_device(attempt["attempt_id"], "sess_ui")["credential_id"])


def test_an_expired_sign_in_is_refreshed_without_a_secret_and_rotated(ws: Path, github: FakeGitHub) -> None:
    credential_id = _connected(ws, github)
    store = SQLiteStore(ws)
    store.update_git_credential(credential_id, expires_at="2000-01-01T00:00:00Z")
    broker = GitCredentialBroker(store, OWNER, http=GitHubHttp(github))
    broker.grant("once")
    with broker.lend(operation="push") as environment:
        token = environment[RUNTIME_TOKEN_VAR]
    refresh = [r for r in github.requests if r["form"].get("grant_type") == "refresh_token"]
    assert len(refresh) == 1 and "client_secret" not in refresh[0]["form"]
    _access, refresh_key = app_user_vault_keys(credential_id)
    stored = broker.methods.vault_get(refresh_key) or {}
    assert stored["refresh_token"] not in {r["form"]["refresh_token"] for r in refresh}
    assert github.users[token] == (101, "octo")


def test_a_failed_refresh_asks_for_sign_in_and_lends_nothing(ws: Path, github: FakeGitHub) -> None:
    credential_id = _connected(ws, github)
    store = SQLiteStore(ws)
    store.update_git_credential(credential_id, expires_at="2000-01-01T00:00:00Z")
    github.refresh_tokens.clear()
    broker = GitCredentialBroker(store, OWNER, http=GitHubHttp(github))
    broker.grant("once")
    with pytest.raises(GitCredentialError) as caught, broker.lend(operation="push"):
        pass
    assert caught.value.reason == "github_sign_in_expired"
    assert (store.load_git_credential(credential_id) or {})["status"] == "expired"


def test_signing_in_as_another_account_withdraws_every_grant(ws: Path, github: FakeGitHub) -> None:
    _connected(ws, github, (101, "octo"))
    broker = GitCredentialBroker(SQLiteStore(ws), OWNER, http=GitHubHttp(github))
    broker.grant("once")
    _connected(ws, github, (202, "hubot"))
    assert broker.live_grant() is None
    assert (broker.selected_credential() or {})["account_login"] == "hubot"


def test_repositories_are_recorded_by_id_and_a_removal_is_noticed(ws: Path, github: FakeGitHub) -> None:
    credential_id = _connected(ws, github)
    github.installations = [{"id": 7, "account": {"id": 101, "login": "octo", "type": "User"},
                             "repository_selection": "selected", "permissions": {"contents": "write"}}]
    github.installation_repositories[7] = [
        {"id": 900, "full_name": "octo/demo", "private": True, "permissions": {"push": True}},
        {"id": 901, "full_name": "octo/tools", "private": False},
    ]
    store = SQLiteStore(ws)
    counts = discover_repositories(store, OWNER, credential_id, http=GitHubHttp(github))
    assert counts["available"] == 2
    assert store.set_github_repository_selected(OWNER, credential_id, "900", True)
    # A rename keeps the id and the selection; a repository that left is marked.
    github.installation_repositories[7] = [{"id": 900, "full_name": "octo/demo-renamed", "private": True}]
    counts = discover_repositories(store, OWNER, credential_id, http=GitHubHttp(github))
    assert counts == {"credential_id": credential_id, "available": 1, "removed": 1}
    rows = {row["repository_id"]: row for row in store.list_github_repositories(OWNER)}
    assert rows["900"]["full_name"] == "octo/demo-renamed" and rows["900"]["selected"] == 1
    assert rows["901"]["status"] == "removed"
    assert (store.load_github_installation("7") or {})["status"] == "active"


def test_disconnect_ends_lending_and_says_what_github_confirmed(ws: Path, github: FakeGitHub) -> None:
    _byo_app(ws)
    sign_in, query = _start_browser(ws, github)
    github.code_verifiers["code-1"] = query["code_challenge"]
    sign_in.complete_browser("sess_ui", state=query["state"], code="code-1")
    store = SQLiteStore(ws)
    broker = GitCredentialBroker(store, OWNER, http=GitHubHttp(github))
    credential_id = str((broker.selected_credential() or {})["credential_id"])
    broker.grant("once")

    outcome = _sign_in(ws, github).disconnect(credential_id)

    assert outcome["github"] == "revoked" and len(github.revoked) == 1
    assert broker.live_grant() is None and broker.token_configured() is False
    access_key, refresh_key = app_user_vault_keys(credential_id)
    assert broker.methods.vault_get(access_key) is None and broker.methods.vault_get(refresh_key) is None
    assert any(entry.object_id == credential_id for entry in read_deletions(ws))


def test_disconnect_without_the_secret_does_not_claim_revocation(ws: Path, github: FakeGitHub) -> None:
    credential_id = _connected(ws, github)  # device flow on the official App: no secret here
    outcome = _sign_in(ws, github).disconnect(credential_id)
    assert outcome["github"] == "could_not_confirm"
    assert github.revoked == []


def test_pkce_challenge_is_the_s256_of_the_verifier() -> None:
    from raiker.github.auth import pkce_pair

    verifier, challenge = pkce_pair()
    assert 43 <= len(verifier) <= 128
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    assert challenge == expected


def test_nothing_secret_reaches_an_attempt_or_credential_row(ws: Path, github: FakeGitHub) -> None:
    credential_id = _connected(ws, github)
    store = SQLiteStore(ws)
    rows: list[Any] = [store.load_git_credential(credential_id)]
    with store.connect() as connection:
        rows += [dict(row) for row in connection.execute("SELECT * FROM github_auth_attempts")]
    text = json.dumps(rows, default=str)
    assert "ghu_" not in text and "ghr_" not in text and "device-code-secret" not in text
