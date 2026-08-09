from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import raiker.api.routes_models as model_routes
from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models.huggingface import HfVariant


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


def test_download_uses_a_collision_free_revision_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, headers, _workspace = _client(tmp_path)
    root = tmp_path / "models"
    root.mkdir()
    revision = "a" * 40
    variant = HfVariant(
        "org/model",
        revision,
        ("config.json", "model.safetensors"),
        "safetensors",
        None,
        10,
        0,
        False,
        "apache-2.0",
        True,
    )

    class FakeService:
        def variants(self, repo_id: str, **_kwargs: object) -> list[HfVariant]:
            return [variant]

        def download(
            self,
            repo_id: str,
            selected: HfVariant,
            destination: Path,
            **_kwargs: object,
        ) -> Path:
            destination.mkdir(parents=True)
            (destination / "config.json").write_text("{}", encoding="utf-8")
            (destination / "model.safetensors").write_bytes(b"safe")
            return destination

    monkeypatch.setattr(model_routes, "_hugging_face_service", lambda _request: FakeService())
    assert (
        client.post(
            "/api/model-library/roots", headers=headers, json={"path": str(root)}
        ).status_code
        == 200
    )

    response = client.post(
        "/api/hugging-face/download",
        headers=headers,
        json={
            "repo_id": "org/model",
            "revision": revision,
            "files": list(variant.files),
            "destination": str(root),
            "confirmed": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert ".raiker-hf" in body["snapshot_path"]
    assert body["snapshot_path"] != body["conversion_output_path"]
    assert Path(body["snapshot_path"]).is_dir()
