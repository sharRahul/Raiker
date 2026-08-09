from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner


def test_owner_adds_and_rescans_an_approved_library(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    library = tmp_path / "models"
    library.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    token, _ = ApiSessionStore(workspace).create_session("principal_owner")
    client = TestClient(create_app(workspace))
    headers = {"Authorization": f"Bearer {token}"}
    added = client.post("/api/model-library/roots", headers=headers, json={"path": str(library)})
    scanned = client.post("/api/model-library/rescan", headers=headers)
    assert added.status_code == 200
    assert scanned.status_code == 200
    assert client.get("/api/model-library", headers=headers).json()["roots"][0]["path"] == str(library.resolve())
