from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner


def _client(tmp_path: Path) -> tuple[TestClient, dict[str, str]]:
    workspace = tmp_path / "operations-api"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    token, _ = ApiSessionStore(workspace).create_session("principal_owner")
    return TestClient(create_app(workspace)), {"Authorization": f"Bearer {token}"}


def test_owner_can_preview_and_start_confirmed_install(tmp_path: Path) -> None:
    client, headers = _client(tmp_path)
    preview = client.post("/api/model-operations/preview", headers=headers, json={"kind": "install", "target": "ollama", "confirmed": False})
    started = client.post("/api/model-operations", headers=headers, json={"kind": "install", "target": "ollama", "confirmed": True})

    assert preview.status_code == 200
    assert preview.json()["source_url"].startswith("https://")
    assert started.status_code == 200
    assert started.json()["state"] == "queued"
    assert client.get("/api/model-operations", headers=headers).json()["items"][0]["target"] == "ollama"


def test_start_requires_explicit_confirmation(tmp_path: Path) -> None:
    client, headers = _client(tmp_path)
    response = client.post("/api/model-operations", headers=headers, json={"kind": "install", "target": "ollama", "confirmed": False})
    assert response.status_code == 409
    assert response.json()["detail"]["reason_code"] == "confirmation_required"
