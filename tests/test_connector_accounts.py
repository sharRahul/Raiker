"""Named accounts per service (Quiet UI 06, QUI-F07; 02, QUI-P04).

What these hold:

* an installed connector has its default account, which the owner may name;
  further accounts have their own credential slot, so two credentials never
  overwrite each other;
* a write names the account it uses: the approval card's arguments carry the
  owner's name for it, and the approved send runs with exactly that account's
  credential;
* an account the owner did not create is refused, never mapped to the default;
* removing an account, or uninstalling the connector, removes its credential.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.runtime.connector_accounts import credential_key
from raiker.runtime.connector_ecosystem import ConnectorVault
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture(autouse=True)
def vault_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAIKER_CONNECTOR_VAULT_KEY", Fernet.generate_key().decode())


def _auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/session", json={"as_principal": None})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


_MANIFEST = {
    "openapi": "3.0.0",
    "servers": [{"url": "https://api.github.com"}],
    "paths": {"/repos/{owner}": {"post": {"operationId": "postRepo", "summary": "Write"}}},
}


def _installed(client: TestClient, auth: dict[str, str]) -> None:
    assert client.post("/api/connector-store/github/install", headers=auth).status_code == 200
    assert client.put(
        "/api/connector-store/github/credentials", headers=auth, json={"values": {"access_token": "work-token"}}
    ).status_code == 200
    assert client.post("/api/connector-store/github/manifest", headers=auth, json={"manifest": _MANIFEST}).status_code == 200
    assert client.put("/api/connector-store/github/enabled?enabled=true", headers=auth).status_code == 200


def _principal(client: TestClient, auth: dict[str, str]) -> str:
    return str(client.get("/api/auth/whoami", headers=auth).json()["principal_id"])


def test_accounts_are_named_and_each_has_its_own_credential(client: TestClient, workspace: Path) -> None:
    auth = _auth(client)
    _installed(client, auth)
    named = client.put("/api/connector-store/github/accounts/default", headers=auth, json={"label": "Work GitHub"})
    assert named.status_code == 200, named.text
    added = client.post("/api/connector-store/github/accounts", headers=auth, json={"label": " Personal   GitHub "})
    assert added.status_code == 201, added.text
    personal = added.json()["account_id"]
    assert added.json()["label"] == "Personal GitHub"
    saved = client.put(
        f"/api/connector-store/github/accounts/{personal}/credentials",
        headers=auth,
        json={"values": {"access_token": "personal-token"}},
    )
    assert saved.status_code == 200, saved.text

    listed = client.get("/api/connector-store/github/accounts", headers=auth).json()["accounts"]
    assert [(a["label"], a["is_default"], a["auth_status"]) for a in listed] == [
        ("Work GitHub", True, "connected"),
        ("Personal GitHub", False, "connected"),
    ]
    store_view = client.get("/api/connector-store", headers=auth).json()["connectors"]
    github = next(item for item in store_view if item["connector_id"] == "github")
    assert [a["label"] for a in github["accounts"]] == ["Work GitHub", "Personal GitHub"]
    assert "token" not in str(listed)

    vault = ConnectorVault(SQLiteStore(workspace))
    owner = _principal(client, auth)
    assert vault.get(owner, "github") == {"access_token": "work-token"}
    assert vault.get(owner, credential_key("github", personal)) == {"access_token": "personal-token"}

    taken = client.post("/api/connector-store/github/accounts", headers=auth, json={"label": "work github"})
    assert taken.status_code == 409
    assert "connector_account_label_taken" in taken.text


def test_a_write_names_its_account_and_runs_with_exactly_that_one(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth = _auth(client)
    _installed(client, auth)
    personal = client.post("/api/connector-store/github/accounts", headers=auth, json={"label": "Personal GitHub"}).json()["account_id"]
    invoke = AsyncMock(return_value={"connector_id": "github", "operation_id": "postRepo", "method": "POST", "status_code": 200, "data": {}})
    monkeypatch.setattr("raiker.runtime.connector_ecosystem.ConnectorInvoker.invoke", invoke)

    proposed = client.post(
        "/api/connector-store/github/actions",
        headers=auth,
        json={"operation_id": "postRepo", "arguments": {"path": {"owner": "me"}}, "account_id": personal},
    )
    assert proposed.status_code == 200, proposed.text
    assert proposed.json()["account_label"] == "Personal GitHub"
    approval_id = proposed.json()["approval_id"]
    detail = client.get(f"/api/approvals/{approval_id}", headers=auth).json()
    assert detail["arguments"]["account"] == "Personal GitHub"
    assert "(Personal GitHub)" in str(detail.get("diff_path") or detail)

    approved = client.post(f"/api/approvals/{approval_id}/resolve", headers=auth, json={"approve": True, "reason": "ok"})
    assert approved.status_code == 200, approved.text
    args: Any = invoke.await_args
    assert args.args[-1] == personal


def test_an_account_the_owner_did_not_create_is_refused(client: TestClient) -> None:
    auth = _auth(client)
    _installed(client, auth)
    refused = client.post(
        "/api/connector-store/github/actions",
        headers=auth,
        json={"operation_id": "postRepo", "arguments": {}, "account_id": "cacct_not_mine"},
    )
    assert refused.status_code == 404
    assert "connector_account_unknown" in refused.text
    assert client.delete("/api/connector-store/github/accounts/default", headers=auth).status_code == 409


def test_removing_an_account_or_the_connector_removes_its_credential(client: TestClient, workspace: Path) -> None:
    auth = _auth(client)
    _installed(client, auth)
    owner = _principal(client, auth)
    store = SQLiteStore(workspace)
    vault = ConnectorVault(store)
    first = client.post("/api/connector-store/github/accounts", headers=auth, json={"label": "One"}).json()["account_id"]
    second = client.post("/api/connector-store/github/accounts", headers=auth, json={"label": "Two"}).json()["account_id"]
    for account in (first, second):
        client.put(
            f"/api/connector-store/github/accounts/{account}/credentials", headers=auth, json={"values": {"api_key": "k"}}
        )
    assert client.delete(f"/api/connector-store/github/accounts/{first}", headers=auth).status_code == 200
    assert vault.get(owner, credential_key("github", first)) is None
    assert vault.get(owner, credential_key("github", second)) is not None
    assert client.delete("/api/connector-store/github", headers=auth).status_code == 200
    assert vault.get(owner, credential_key("github", second)) is None
    assert store._rows("SELECT * FROM connector_accounts") == []
