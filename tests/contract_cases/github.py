"""Settings → Connections → GitHub (ADD-27): the connection, sign-in, repositories, delegations, App.

GitHub itself is the stand-in in ``tests/github_fakes.py``, reached through the
routes' one client seam; nothing here leaves the machine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from raiker.github.http import GitHubHttp
from raiker.storage.sqlite import SQLiteStore
from tests.contract_cases.base import Call, Cases, patched, plain
from tests.github_fakes import CLIENT_ID, FakeGitHub

_TOKEN = "ghp_contractGitHubToken0000000000000000000"
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PEM = _KEY.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
).decode()


def _github(monkeypatch: Any) -> None:
    """A vault, an App client id for device sign-in, and GitHub itself, faked."""
    from raiker.api import routes_github

    fake = FakeGitHub(public_key=_KEY.public_key())
    fake.users[_TOKEN] = (101, "octo")
    fake.user_repositories = [{"id": 900, "full_name": "octo/demo", "private": True}]
    fake.installations = [{"id": 7, "account": {"id": 55, "login": "acme", "type": "Organization"},
                           "repository_selection": "selected", "permissions": {"contents": "write"}}]
    monkeypatch.setenv("RAIKER_CONNECTOR_VAULT_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("RAIKER_GITHUB_APP_CLIENT_ID", CLIENT_ID)
    monkeypatch.delenv("RAIKER_GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(routes_github, "_http", lambda: GitHubHttp(fake))


def _pat(client: TestClient, h: dict[str, str]) -> str:
    assert client.put("/api/git-credential", json={"token": _TOKEN}, headers=h).status_code == 200
    rows = client.get("/api/github", headers=h).json()["credentials"]
    return str(rows[0]["credential_id"])


def _app(ws: Path) -> None:
    from raiker.github.apps import store_secret_in_vault

    store = SQLiteStore(ws)
    store.upsert_github_app(
        "byo", updated_by=None, client_id=CLIENT_ID, app_id="4242",
        private_key_ref=__import__("json").dumps(store_secret_in_vault(store, "byo_private_key", _PEM)),
    )
    store.upsert_github_installation("7", app_ref="byo", status="active", account_login="acme")


def _added(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _app(ws)
    return "/api/github/credentials", {"method": "app_installation", "selector": "7"}


def _select(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    pat = _pat(client, h)
    _app(ws)
    assert client.post("/api/github/credentials", json={"method": "app_installation", "selector": "7"}, headers=h).status_code == 200
    return f"/api/github/credentials/{pat}/select"


def _check(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return f"/api/github/credentials/{_pat(client, h)}/check"


def _disconnect(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return f"/api/github/credentials/{_pat(client, h)}"


def _attempt(client: TestClient, h: dict[str, str]) -> str:
    started = client.post("/api/github/sign-in", json={"method": "device"}, headers=h)
    assert started.status_code == 200, started.text
    return str(started.json()["attempt_id"])


def _poll(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return f"/api/github/sign-in/{_attempt(client, h)}/poll"


def _cancel(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return f"/api/github/sign-in/{_attempt(client, h)}/cancel"


def _refresh(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _pat(client, h)
    return "/api/github/repositories/refresh"


def _repository(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    credential_id = _pat(client, h)
    assert client.post("/api/github/repositories/refresh", headers=h).status_code == 200
    return "/api/github/repositories/900", {"credential_id": credential_id, "selected": True}


_DELEGATION = {"repository": "github.com/octo/demo", "operations": ["push", "pull_request"], "branch_pattern": "raiker/*"}


def _delegate(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _pat(client, h)
    return "/api/github/delegations", _DELEGATION


def _revoke(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    _pat(client, h)
    made = client.post("/api/github/delegations", json=_DELEGATION, headers=h)
    assert made.status_code == 200, made.text
    return f"/api/github/delegations/{made.json()['delegation_id']}"


def _app_seeded(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    _app(ws)
    return "/api/github/app"


def _validate(ws: Path, _client: TestClient, _h: dict[str, str]) -> Call:
    _app(ws)
    return "/api/github/app/validate"


CASES: Cases = {
    ("GET", "/api/github"): patched(plain("/api/github"), _github),
    ("GET", "/api/github/discovery"): plain("/api/github/discovery"),
    ("POST", "/api/github/credentials"): patched(_added, _github),
    ("POST", "/api/github/credentials/{credential_id}/select"): patched(_select, _github),
    ("POST", "/api/github/credentials/{credential_id}/check"): patched(_check, _github),
    ("DELETE", "/api/github/credentials/{credential_id}"): patched(_disconnect, _github),
    ("POST", "/api/github/sign-in"): patched(plain("/api/github/sign-in", {"method": "device"}), _github),
    ("POST", "/api/github/sign-in/{attempt_id}/poll"): patched(_poll, _github),
    ("POST", "/api/github/sign-in/{attempt_id}/cancel"): patched(_cancel, _github),
    ("POST", "/api/github/repositories/refresh"): patched(_refresh, _github),
    ("PUT", "/api/github/repositories/{repository_id}"): patched(_repository, _github),
    ("POST", "/api/github/delegations"): patched(_delegate, _github),
    ("DELETE", "/api/github/delegations/{delegation_id}"): patched(_revoke, _github),
    # BUG-339 — a plan with no delegation asks GitHub nothing.
    ("POST", "/api/github/routines/issue-to-pr"): patched(
        plain("/api/github/routines/issue-to-pr", {"repository": "octo/demo", "issue_number": 7, "work_branch": "raiker/issue-7"}),
        _github,
    ),
    ("PUT", "/api/github/app"): patched(
        plain("/api/github/app", {"client_id": CLIENT_ID, "private_key": {"kind": "vault", "value": _PEM}}),
        _github,
    ),
    ("POST", "/api/github/app/validate"): patched(_validate, _github),
    ("DELETE", "/api/github/app"): patched(_app_seeded, _github),
}
