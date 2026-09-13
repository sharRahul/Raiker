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
    # FIRST-03 — first launch opens on what Raiker is, not on a provider matrix.
    assert initial.json()["stage"] == "welcome"
    assert initial.json()["status"] == "required"

    saved = client.put(
        "/api/setup",
        headers=headers,
        json={"status": "in_progress", "stage": "privacy", "privacy_mode": "local_first"},
    )
    assert saved.status_code == 200
    assert client.get("/api/setup", headers=headers).json()["privacy_mode"] == "local_first"


def test_a_row_stored_under_a_retired_stage_still_round_trips(tmp_path: Path) -> None:
    """An instance part-way through the previous wizard has one of these stored.

    The stages the *screen* shows are `welcome → model → privacy → finish`, but
    refusing `account` or `backup` on the wire would make an in-progress setup
    unsavable rather than merely differently drawn.
    """
    client, headers = _client(tmp_path)

    for stage in ("account", "backup"):
        saved = client.put(
            "/api/setup", headers=headers, json={"status": "in_progress", "stage": stage}
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["stage"] == stage


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

