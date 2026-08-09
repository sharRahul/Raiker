from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner


def test_owner_previews_conversion_without_starting_a_process(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = tmp_path / "snapshot"
    source.mkdir()
    (source / "config.json").write_text(
        json.dumps({"architectures": ["LlamaForCausalLM"]}), encoding="utf-8"
    )
    (source / "model.safetensors").write_bytes(b"safe")
    output = tmp_path / "output"
    output.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    token, _ = ApiSessionStore(workspace).create_session("principal_owner")
    client = TestClient(create_app(workspace))
    headers = {"Authorization": f"Bearer {token}"}
    assert (
        client.post(
            "/api/model-library/roots", headers=headers, json={"path": str(tmp_path)}
        ).status_code
        == 200
    )

    response = client.post(
        "/api/model-conversion/preview",
        headers=headers,
        json={
            "source": str(source),
            "output": str(output),
            "revision": "d" * 40,
            "quantization": "Q4_K_M",
        },
    )

    assert response.status_code == 200
    assert response.json()["isolation"]["network"] is False
    assert response.json()["revision"] == "d" * 40


def test_conversion_requires_explicit_confirmation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    token, _ = ApiSessionStore(workspace).create_session("principal_owner")
    client = TestClient(create_app(workspace))

    response = client.post(
        "/api/model-conversion",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "source": str(tmp_path),
            "output": str(tmp_path),
            "revision": "d" * 40,
            "quantization": "Q4_K_M",
            "confirmed": False,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["reason_code"] == "confirmation_required"
