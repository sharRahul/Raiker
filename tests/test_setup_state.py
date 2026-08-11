from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner


def _client(tmp_path: Path) -> tuple[TestClient, dict[str, str]]:
    workspace = tmp_path / "setup"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    token, _ = ApiSessionStore(workspace).create_session("principal_owner")
    return TestClient(create_app(workspace)), {"Authorization": f"Bearer {token}"}


def test_full_setup_state_is_owner_scoped_and_resumable(tmp_path: Path) -> None:
    client, headers = _client(tmp_path)
    initial = client.get("/api/setup", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["stage"] == "model"
    assert initial.json()["status"] == "required"

    saved = client.put(
        "/api/setup",
        headers=headers,
        json={"status": "in_progress", "stage": "privacy", "privacy_mode": "local_first"},
    )
    assert saved.status_code == 200
    assert client.get("/api/setup", headers=headers).json()["privacy_mode"] == "local_first"


def test_setup_rejects_unknown_stages_and_backup_modes(tmp_path: Path) -> None:
    client, headers = _client(tmp_path)
    assert client.put(
        "/api/setup", headers=headers, json={"status": "in_progress", "stage": "shell"}
    ).status_code == 422
    assert client.put(
        "/api/setup",
        headers=headers,
        json={"status": "in_progress", "stage": "backup", "backup_mode": "cloud"},
    ).status_code == 422

