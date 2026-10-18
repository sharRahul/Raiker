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
        json={"status": "in_progress", "stage": "privacy", "privacy_mode": "balanced"},
    )
    assert saved.status_code == 200
    assert client.get("/api/setup", headers=headers).json()["privacy_mode"] == "balanced"


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



def test_local_only_is_no_longer_a_setup_answer(tmp_path: Path) -> None:
    """BUG-345 — *Local only* was stored and enforced nowhere; the owner removed it."""
    client, headers = _client(tmp_path)
    refused = client.put(
        "/api/setup",
        headers=headers,
        json={"status": "in_progress", "stage": "permissions", "privacy_mode": "local_first"},
    )
    assert refused.status_code == 422


def test_a_stored_local_only_answer_is_rewritten_to_what_it_always_did(tmp_path: Path) -> None:
    from raiker.storage.migrations import SETUP_PRIVACY_MODE_SQL
    from raiker.storage.sqlite import SQLiteStore

    client, headers = _client(tmp_path)
    assert client.put(
        "/api/setup",
        headers=headers,
        json={"status": "in_progress", "stage": "permissions", "privacy_mode": "balanced"},
    ).status_code == 200
    store = SQLiteStore(tmp_path / "setup")
    store._execute("UPDATE setup_state SET privacy_mode = 'local_first'")
    store._execute(SETUP_PRIVACY_MODE_SQL)
    assert client.get("/api/setup", headers=headers).json()["privacy_mode"] == "balanced"
