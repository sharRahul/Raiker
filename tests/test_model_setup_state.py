from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner


def _client(tmp_path: Path) -> tuple[TestClient, dict[str, str]]:
    workspace = tmp_path / "setup-state"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    token, _ = ApiSessionStore(workspace).create_session("principal_owner")
    return TestClient(create_app(workspace)), {"Authorization": f"Bearer {token}"}


def test_first_owner_starts_setup_and_skip_is_resumable(tmp_path: Path) -> None:
    client, headers = _client(tmp_path)

    state = client.get("/api/model-setup", headers=headers).json()
    assert state["status"] == "required"
    assert state["step"] == "choose_path"

    skipped = client.put(
        "/api/model-setup",
        headers=headers,
        json={"status": "skipped", "step": "choose_path"},
    ).json()
    assert skipped["status"] == "skipped"
    assert client.get("/api/model-setup", headers=headers).json()["step"] == "choose_path"


def test_setup_progress_persists_exact_selection(tmp_path: Path) -> None:
    client, headers = _client(tmp_path)
    payload = {
        "status": "in_progress",
        "step": "review",
        "path": "provider",
        "selected_profile_id": "anthropic-hosted",
        "selected_model": "claude-sonnet-4-5-20250929",
    }

    response = client.put("/api/model-setup", headers=headers, json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"
    assert response.json()["selected_profile_id"] == payload["selected_profile_id"]
    assert client.get("/api/model-setup", headers=headers).json()["selected_model"] == payload["selected_model"]


def test_setup_rejects_unknown_status_and_step(tmp_path: Path) -> None:
    client, headers = _client(tmp_path)

    status = client.put(
        "/api/model-setup", headers=headers, json={"status": "done", "step": "ready"}
    )
    step = client.put(
        "/api/model-setup", headers=headers, json={"status": "in_progress", "step": "shell"}
    )

    assert status.status_code == 422
    assert step.status_code == 422
