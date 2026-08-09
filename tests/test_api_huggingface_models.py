from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner


def _client(tmp_path: Path) -> tuple[TestClient, dict[str, str], Path]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    token, _ = ApiSessionStore(workspace).create_session("principal_owner")
    app = create_app(workspace)
    return TestClient(app), {"Authorization": f"Bearer {token}"}, workspace


def test_hugging_face_routes_are_owner_authenticated(tmp_path: Path) -> None:
    client, headers, _workspace = _client(tmp_path)

    assert client.get("/api/hugging-face/search", params={"query": "gguf"}).status_code == 401
    assert (
        client.get("/api/hugging-face/search", headers=headers, params={"query": ""}).status_code
        == 422
    )


def test_hugging_face_token_is_saved_but_never_returned(tmp_path: Path) -> None:
    client, headers, workspace = _client(tmp_path)
    secret = "hf_this_must_never_be_returned"

    response = client.put("/api/hugging-face/credential", headers=headers, json={"token": secret})

    assert response.status_code == 200
    assert response.json() == {"configured": True}
    assert secret not in response.text
    database = workspace / ".raiker" / "raiker.db"
    assert secret.encode() not in database.read_bytes()
