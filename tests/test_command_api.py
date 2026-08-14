from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.execution.commands.service import CommandService, CommandServiceError
from raiker.storage.sqlite import SQLiteStore


def _owner(workspace: Path, name: str) -> tuple[str, str]:
    if name == "owner":
        bootstrap_owner(name, name.title(), workspace_root=workspace)
    else:
        with SQLiteStore(workspace).connect() as connection:
            connection.execute(
                """INSERT INTO principals
                   (principal_id, principal_type, display_name, role_ids, domain_scopes,
                    max_runtime_mode, created_at, is_active)
                   VALUES (?, 'human', ?, '[]', '[]', 'development_preview', ?, 1)""",
                (f"principal_{name}", name.title(), utc_now()),
            )
    token, session = ApiSessionStore(workspace).create_session(f"principal_{name}")
    return token, session.principal_id


def test_governed_command_lifecycle_is_authenticated_durable_and_receipted(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    token, _ = _owner(workspace, "owner")
    app = create_app(workspace)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/command-runs").status_code == 401
    assert client.post(
        "/api/command-runs",
        headers=headers,
        json={"session_id": "sess_build", "command": "git status --short"},
    ).status_code == 405
    started = CommandService.for_workspace(workspace).start(
        owner_principal_id="principal_owner",
        acting_principal_id="principal_owner",
        session_id="sess_build",
        turn_id="turn_build",
        action_id="act_approved_shell",
        authority_kind="approval",
        authority_id="approval_shell",
        command="git status --short",
        argv=["git", "status", "--short"],
    )
    run_id = started.run_id
    assert run_id.startswith("cmd_")

    for _ in range(100):
        run = client.get(f"/api/command-runs/{run_id}", headers=headers).json()["run"]
        if run["receipt_digest"]:
            break
        time.sleep(0.02)
    assert run["state"] in {"succeeded", "failed"}
    receipt = client.get(f"/api/command-runs/{run_id}/receipt", headers=headers).json()["receipt"]
    assert receipt["digest"] == run["receipt_digest"]
    assert receipt["evidence"]["backend"] == "local_strict"
    assert receipt["evidence"]["authority"] == {
        "kind": "approval",
        "id": "approval_shell",
    }


def test_command_runs_are_owner_scoped_and_unsafe_shell_source_is_contained(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    owner_token, _ = _owner(workspace, "owner")
    other_token, _ = _owner(workspace, "other")
    client = TestClient(create_app(workspace))
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    other_headers = {"Authorization": f"Bearer {other_token}"}

    with pytest.raises(CommandServiceError, match="command_chaining_denied:&&"):
        CommandService.for_workspace(workspace).start(
            owner_principal_id="principal_owner",
            acting_principal_id="principal_owner",
            session_id="sess_build",
            turn_id="turn_build",
            action_id="act_approved_shell",
            authority_kind="approval",
            authority_id="approval_shell",
            command="git status && echo unsafe",
            argv=["git", "status", "&&", "echo", "unsafe"],
        )

    runs = client.get("/api/command-runs", headers=owner_headers).json()["runs"]
    assert runs[0]["state"] == "contained"
    run_id = runs[0]["run_id"]
    assert client.get(f"/api/command-runs/{run_id}", headers=other_headers).status_code == 404
    assert client.get("/api/command-runs", headers=other_headers).json()["runs"] == []
