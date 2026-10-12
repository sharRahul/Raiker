"""ADD-27 GH-40…GH-44 — a configured GitHub App: its key, its tokens, its webhooks.

Against a stand-in GitHub (``tests/github_fakes.py``) that checks the App JWT's
signature with the public half of a key generated here.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.github.app_service import (
    AppServiceError,
    GitHubAppService,
    forget_installation_tokens,
    sign_jwt,
)
from raiker.github.apps import AppConfigError, read_secret, store_secret_in_vault
from raiker.github.credentials import (
    METHOD_APP_INSTALLATION,
    CredentialMethodError,
    reset_verification_cache,
)
from raiker.github.http import GitHubHttp
from raiker.github.webhooks import receive
from raiker.runtime.git_credential import RUNTIME_TOKEN_VAR, GitCredentialBroker, GitCredentialError
from raiker.storage.sqlite import SQLiteStore
from tests.github_fakes import CLIENT_ID, FakeGitHub

OWNER = "principal_owner"
WEBHOOK_SECRET = "webhook-secret-for-tests"


@pytest.fixture(scope="module")
def key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def pem(key: rsa.RSAPrivateKey) -> str:
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()


@pytest.fixture
def github(key: rsa.RSAPrivateKey) -> FakeGitHub:
    fake = FakeGitHub(public_key=key.public_key())
    fake.installations = [{"id": 7, "account": {"id": 55, "login": "acme", "type": "Organization"},
                           "repository_selection": "selected", "permissions": {"contents": "write"}}]
    fake.installation_repositories[7] = [{"id": 900, "full_name": "acme/demo", "private": True}]
    return fake


@pytest.fixture
def ws(tmp_path: Path, pem: str, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv("RAIKER_GITHUB_TOKEN", raising=False)
    reset_verification_cache()
    forget_installation_tokens()
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    store.upsert_github_app(
        "byo", updated_by=OWNER, client_id=CLIENT_ID, app_id="4242",
        private_key_ref=json.dumps(store_secret_in_vault(store, "byo_private_key", pem)),
        webhook_secret_ref=json.dumps(store_secret_in_vault(store, "byo_webhook_secret", WEBHOOK_SECRET)),
        webhooks_enabled=1,
    )
    return tmp_path


def _service(ws: Path, github: FakeGitHub) -> GitHubAppService:
    return GitHubAppService(SQLiteStore(ws), "byo", http=GitHubHttp(github))


def test_the_jwt_is_rs256_short_lived_and_issued_by_the_client_id(pem: str) -> None:
    token = sign_jwt(pem, CLIENT_ID, now=1_000_000)
    header, payload, _signature = token.split(".")
    pad = lambda part: base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))  # noqa: E731
    assert json.loads(pad(header)) == {"alg": "RS256", "typ": "JWT"}
    claims = json.loads(pad(payload))
    assert claims == {"iat": 1_000_000 - 60, "exp": 1_000_000 + 540, "iss": CLIENT_ID}


def test_a_key_that_is_not_an_rsa_private_key_is_refused() -> None:
    with pytest.raises(AppServiceError) as caught:
        sign_jwt("not a key", CLIENT_ID)
    assert caught.value.reason == "github_app_private_key_invalid"


def test_validation_names_excess_permissions_and_records_installations(ws: Path, github: FakeGitHub) -> None:
    github.app["permissions"]["administration"] = "write"
    result = _service(ws, github).validate()
    assert result["ok"] is True
    assert result["excess_permissions"] == ["administration:write"]
    assert (SQLiteStore(ws).load_github_installation("7") or {})["account_login"] == "acme"


def test_validation_fails_when_the_key_does_not_belong_to_the_app(ws: Path, github: FakeGitHub) -> None:
    github.public_key = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key()
    result = _service(ws, github).validate()
    assert result["ok"] is False
    assert {"check": "private_key", "result": "github_app_jwt_rejected"} in result["checks"]


def test_an_installation_token_is_narrowed_cached_and_never_stored(ws: Path, github: FakeGitHub) -> None:
    service = _service(ws, github)
    service.sync_installations()
    token, _expires = service.installation_token("7", repository_ids=["900"], operation="push")
    again, _ = service.installation_token("7", repository_ids=["900"], operation="push")
    assert token == again
    minted = [r for r in github.requests if r["url"].endswith("/access_tokens")]
    assert len(minted) == 1
    assert minted[0]["json"] == {"repository_ids": [900], "permissions": {"contents": "write", "metadata": "read"}}
    with SQLiteStore(ws).connect() as connection:
        dump = json.dumps([list(row) for table in ("git_credentials", "github_installations", "github_apps")
                           for row in connection.execute(f"SELECT * FROM {table}")], default=str)  # noqa: S608
    assert token not in dump


def test_a_removed_installation_mints_nothing(ws: Path, github: FakeGitHub) -> None:
    service = _service(ws, github)
    service.sync_installations()
    github.removed_installations.add(7)
    with pytest.raises(AppServiceError) as caught:
        service.installation_token("7", repository_ids=["900"], operation="fetch")
    assert caught.value.reason == "github_installation_removed"
    assert (SQLiteStore(ws).load_github_installation("7") or {})["status"] == "removed"


def test_the_installation_credential_lends_for_its_own_repository_only(ws: Path, github: FakeGitHub) -> None:
    from raiker.github.auth import discover_repositories

    store = SQLiteStore(ws)
    _service(ws, github).sync_installations()
    broker = GitCredentialBroker(store, OWNER, http=GitHubHttp(github))
    row = broker.methods.add_app_installation("7")
    assert row["method"] == METHOD_APP_INSTALLATION
    discover_repositories(store, OWNER, row["credential_id"], http=GitHubHttp(github))
    broker.grant("once", operation="push", repository="github.com/acme/demo")
    with broker.lend(operation="push", repository="github.com/acme/demo") as environment:
        assert environment[RUNTIME_TOKEN_VAR].startswith("ghs_")
    broker.grant("once", operation="push", repository="github.com/acme/other")
    with pytest.raises(GitCredentialError) as caught, broker.lend(
        operation="push", repository="github.com/acme/other"
    ):
        pass
    assert caught.value.reason == "github_repository_not_authorised"


def test_a_key_file_other_users_can_read_is_refused(ws: Path, pem: str, tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("POSIX file modes")
    path = tmp_path / "app.pem"
    path.write_text(pem, encoding="utf-8")
    path.chmod(0o644)
    with pytest.raises(AppConfigError) as caught:
        read_secret(SQLiteStore(ws), {"kind": "file", "value": str(path)})
    assert caught.value.reason == "github_app_secret_file_too_open"
    path.chmod(0o600)
    assert read_secret(SQLiteStore(ws), {"kind": "file", "value": str(path)}).startswith("-----BEGIN")


# ── webhooks ────────────────────────────────────────────────────────────


def _delivery(event: str, payload: dict, delivery: str = "d-1", secret: str = WEBHOOK_SECRET) -> tuple[dict, bytes]:
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": signature, "X-GitHub-Event": event, "X-GitHub-Delivery": delivery}, body


def test_a_spoofed_or_replayed_delivery_changes_nothing(ws: Path, github: FakeGitHub) -> None:
    store = SQLiteStore(ws)
    _service(ws, github).sync_installations()
    payload = {"action": "deleted", "installation": {"id": 7, "account": {"id": 55, "login": "acme"}}}
    headers, body = _delivery("installation", payload, secret="wrong-secret")
    assert receive(store, headers, body).outcome == "signature_invalid"
    assert (store.load_github_installation("7") or {})["status"] == "active"
    headers, body = _delivery("installation", payload)
    assert receive(store, headers, body).outcome == "installation_removed"
    assert receive(store, headers, body).outcome == "duplicate"


def test_a_user_revoking_the_app_ends_their_credentials_and_grants(ws: Path, github: FakeGitHub, monkeypatch: pytest.MonkeyPatch) -> None:
    from raiker.github.auth import GitHubSignIn

    monkeypatch.setenv("RAIKER_GITHUB_APP_CLIENT_ID", CLIENT_ID)
    store = SQLiteStore(ws)
    sign_in = GitHubSignIn(store, OWNER, http=GitHubHttp(github))
    attempt = sign_in.start_device("sess_ui")
    github.device_answers.append(github.issue((101, "octo")))
    store.set_github_auth_poll(attempt["attempt_id"], interval=5, next_poll_at="2000-01-01T00:00:00Z")
    sign_in.poll_device(attempt["attempt_id"], "sess_ui")
    broker = GitCredentialBroker(store, OWNER, http=GitHubHttp(github))
    broker.grant("once")
    headers, body = _delivery("github_app_authorization", {"action": "revoked", "sender": {"id": 101, "login": "octo"}})
    assert receive(store, headers, body).outcome == "revoked"
    assert broker.live_grant() is None and broker.token_configured() is False


def test_webhooks_are_off_unless_enabled_with_a_secret(ws: Path) -> None:
    store = SQLiteStore(ws)
    store.upsert_github_app("byo", updated_by=OWNER, webhooks_enabled=0)
    headers, body = _delivery("ping", {"zen": "hi"})
    assert receive(store, headers, body).status == 404


def test_an_unhandled_event_is_acknowledged_and_ignored(ws: Path) -> None:
    headers, body = _delivery("push", {"ref": "refs/heads/main"})
    outcome = receive(SQLiteStore(ws), headers, body)
    assert outcome.status == 202 and outcome.outcome == "event_ignored"


def test_isolation_two_owners_never_share_a_credential(ws: Path, github: FakeGitHub, monkeypatch: pytest.MonkeyPatch) -> None:
    """GH-44 — one owner's connection is invisible to and unusable by another."""
    from raiker.github.auth import GitHubSignIn, SignInError

    monkeypatch.setenv("RAIKER_GITHUB_APP_CLIENT_ID", CLIENT_ID)
    store = SQLiteStore(ws)
    sign_in = GitHubSignIn(store, OWNER, http=GitHubHttp(github))
    attempt = sign_in.start_device("sess_ui")
    github.device_answers.append(github.issue((101, "octo")))
    store.set_github_auth_poll(attempt["attempt_id"], interval=5, next_poll_at="2000-01-01T00:00:00Z")
    credential_id = str(sign_in.poll_device(attempt["attempt_id"], "sess_ui")["credential_id"])
    other = GitCredentialBroker(store, "principal_other", http=GitHubHttp(github))
    assert other.token_configured() is False and other.methods.list() == []
    with pytest.raises(CredentialMethodError) as caught:
        other.methods.get(credential_id)
    assert getattr(caught.value, "reason", "") == "git_credential_unknown"
    with pytest.raises(SignInError):
        GitHubSignIn(store, "principal_other", http=GitHubHttp(github)).poll_device(attempt["attempt_id"], "sess_ui")
