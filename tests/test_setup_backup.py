from __future__ import annotations

import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner


def test_setup_backup_is_real_and_marks_state_only_after_success(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    target = tmp_path / "backups"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    token, _ = ApiSessionStore(workspace).create_session("principal_owner")
    client = TestClient(create_app(workspace))
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post("/api/setup/backup/create", headers=headers, json={"target": str(target)})

    assert response.status_code == 200
    backup = Path(response.json()["path"])
    assert backup.is_file()
    with zipfile.ZipFile(backup) as archive:
        assert set(archive.namelist()) == {"raiker.db", "manifest.enc"}
        assert b"principal_owner" not in archive.read("manifest.enc")
    state = client.get("/api/setup", headers=headers).json()
    assert state["backup_mode"] == "local"
    assert state["backup_verified_at"]

