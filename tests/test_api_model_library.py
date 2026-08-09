from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import raiker.api.routes_models as model_routes
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
    assert client.get("/api/model-library", headers=headers).json()["roots"][0]["path"] == str(
        library.resolve()
    )


def test_deploy_dispatches_the_managed_llama_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    library = tmp_path / "models"
    library.mkdir()
    model = library / "tiny.gguf"
    # Minimal GGUF v3 with no tensors and the required identifying metadata.
    model.write_bytes(
        b"GGUF"
        + (3).to_bytes(4, "little")
        + (0).to_bytes(8, "little")
        + (2).to_bytes(8, "little")
        + (12).to_bytes(8, "little")
        + b"general.name"
        + (8).to_bytes(4, "little")
        + (4).to_bytes(8, "little")
        + b"Tiny"
        + (20).to_bytes(8, "little")
        + b"general.architecture"
        + (8).to_bytes(4, "little")
        + (5).to_bytes(8, "little")
        + b"llama"
    )
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    token, _ = ApiSessionStore(workspace).create_session("principal_owner")
    app = create_app(workspace)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/model-library/roots", headers=headers, json={"path": str(library)})
    scanned = client.post("/api/model-library/rescan", headers=headers).json()["models"]
    assert scanned[0]["model_id"].startswith("mdl_")
    assert "/" not in scanned[0]["model_id"] and "\\" not in scanned[0]["model_id"]
    calls: list[tuple[str, str]] = []

    def fake_worker(
        _workspace: Path,
        owner: str,
        operation_id: str,
        path: Path,
        _roots: tuple[Path, ...],
        _runtime: object,
    ) -> None:
        calls.append((owner, str(path)))

    monkeypatch.setattr(model_routes, "_run_local_deployment", fake_worker)
    response = client.post(f"/api/model-library/{scanned[0]['model_id']}/deploy", headers=headers)

    assert response.status_code == 200
    assert response.json()["kind"] == "deploy"
    assert calls == [("principal_owner", str(model.resolve()))]
