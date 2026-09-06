from __future__ import annotations

import json
from pathlib import Path

import pytest
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


def test_failed_conversion_cleanup_leaves_unrelated_models_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GCR-19, end to end: the P0 the third-pass review found.

    A conversion writes into the model-library output directory the owner chose.
    That directory holds the models earlier conversions succeeded at. The
    operation recorded that *directory* as its cleanup destination, and
    ``Delete partial files`` ran ``shutil.rmtree`` on it — so cleaning up one
    failure deleted every unrelated model beside it.

    The scenario the review asked for, run against the real routes: an output
    directory that already contains a successful model, a second conversion into
    it that fails, then the confirmed cleanup. The unrelated model must still be
    there, byte for byte.
    """
    import raiker.api.routes_models as model_routes
    from raiker.models.conversion import ConversionRefused

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = tmp_path / "snapshot"
    source.mkdir()
    (source / "config.json").write_text(
        json.dumps({"architectures": ["LlamaForCausalLM"]}), encoding="utf-8"
    )
    (source / "model.safetensors").write_bytes(b"safe")
    output = tmp_path / "converted"
    output.mkdir()
    unrelated = output / "gemma-2b.Q4_K_M.gguf"
    unrelated.write_bytes(b"an earlier conversion that worked")
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

    # The conversion runs and fails, exactly as a real toolchain failure would.
    def refuse(_self: object, _preview: object) -> None:
        raise ConversionRefused("isolated_conversion_failed")

    monkeypatch.setattr(model_routes.ModelConversionService, "convert", refuse)
    started = client.post(
        "/api/model-conversion",
        headers=headers,
        json={
            "source": str(source),
            "output": str(output),
            "revision": "d" * 40,
            "quantization": "Q4_K_M",
            "confirmed": True,
        },
    )
    assert started.status_code == 200
    operation_id = started.json()["operation_id"]
    # A leftover intermediate from the failed run, in the shared directory.
    intermediate = output / f"snapshot-{'d' * 12}.bf16.gguf"
    intermediate.write_bytes(b"half a conversion")

    summary = client.get(
        f"/api/model-operations/{operation_id}/partial-files", headers=headers
    ).json()
    assert summary["paths"] == [str(intermediate)]
    assert str(output) not in summary["paths"]

    deleted = client.post(
        f"/api/model-operations/{operation_id}/delete-partial-files?confirmed=true",
        headers=headers,
    )

    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True
    assert not intermediate.exists()
    # The whole point of the finding.
    assert output.is_dir()
    assert unrelated.read_bytes() == b"an earlier conversion that worked"


def test_cleanup_refuses_a_path_that_is_an_approved_root_itself(tmp_path: Path) -> None:
    """A root is the boundary of the containment check, never a thing it permits.

    The check was ``target == root or root in target.parents``, so a recorded
    destination equal to an approved model-library root passed it and the whole
    library could be removed.
    """
    from raiker.models.local_operations import ModelOperationRequest, ModelOperationService
    from raiker.storage.sqlite import SQLiteStore

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    library = tmp_path / "library"
    library.mkdir()
    (library / "model.gguf").write_bytes(b"a model the owner has")
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    token, _ = ApiSessionStore(workspace).create_session("principal_owner")
    client = TestClient(create_app(workspace))
    headers = {"Authorization": f"Bearer {token}"}
    assert (
        client.post(
            "/api/model-library/roots", headers=headers, json={"path": str(library)}
        ).status_code
        == 200
    )
    service = ModelOperationService(SQLiteStore(workspace))
    operation = service.start(
        "principal_owner",
        ModelOperationRequest(
            kind="download", target="repo/model", confirmed=True, destination=str(library)
        ),
        payload={"destination": str(library)},
    )
    service.fail("principal_owner", operation.operation_id, code="hugging_face_download_failed")

    refused = client.post(
        f"/api/model-operations/{operation.operation_id}/delete-partial-files?confirmed=true",
        headers=headers,
    )

    assert refused.status_code == 422
    assert refused.json()["detail"]["reason_code"] == "destination_not_in_model_library"
    assert (library / "model.gguf").exists()


def test_a_conversion_row_names_its_revision_instead_of_being_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Found live 2026-09-05, in the Activity panel.

    The conversion row's label was `<snapshot>@<40-hex revision>` — 49 URL-safe
    characters in one unbroken run, which is exactly what the API redactor's
    high-entropy fallback exists to catch. So every conversion appeared as
    `snapshot@[REDACTED_SECRET]`, and two conversions of the same snapshot at
    different revisions were indistinguishable. The same shape as FIXED-361,
    where an ordinary folder path came back redacted: an immutable Hub revision
    is public, and the download row beside it had already settled on the short
    form.
    """
    import raiker.api.routes_models as model_routes
    from raiker.models.conversion import ConversionRefused

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = tmp_path / "snapshot"
    source.mkdir()
    (source / "config.json").write_text(
        json.dumps({"architectures": ["LlamaForCausalLM"]}), encoding="utf-8"
    )
    (source / "model.safetensors").write_bytes(b"safe")
    output = tmp_path / "converted"
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
    def refuse(_self: object, _preview: object) -> None:
        raise ConversionRefused("isolated_conversion_failed")

    monkeypatch.setattr(model_routes.ModelConversionService, "convert", refuse)
    revision = "d" * 40
    client.post(
        "/api/model-conversion",
        headers=headers,
        json={
            "source": str(source),
            "output": str(output),
            "revision": revision,
            "quantization": "Q4_K_M",
            "confirmed": True,
        },
    )

    listed = client.get("/api/model-operations", headers=headers).json()["items"]

    assert listed[0]["target"] == f"snapshot@{revision[:12]}"
    assert "REDACTED" not in listed[0]["target"]
