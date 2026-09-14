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


def test_an_unreachable_hub_is_a_200_with_the_reason_on_the_trending_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BUG-296 — the probe nobody asked for must not report itself as an error.

    `trending` runs on every visit to Models so the panel opens with somewhere
    to start. On a host with no route to `huggingface.co` it answered 503, and
    the browser wrote `GET /api/hugging-face/trending — 503` into the console
    every time. The panel itself was already correct — it says the Hub could not
    be reached, where the results would have been, with a Try again.

    The cost was to the evidence rather than to the owner: the live manual test
    plan requires a round to end with zero uncaught console errors and several
    live specs assert it, so one expected outage was spending the budget that
    exists to catch real ones.
    """
    from raiker.models.huggingface import HuggingFaceAccessError

    client, headers, _workspace = _client(tmp_path)

    class UnreachableService:
        def trending(self, **_kwargs: object) -> list[object]:
            raise HuggingFaceAccessError("hugging_face_unavailable", "")

    monkeypatch.setattr(
        model_routes, "_hugging_face_service", lambda _request: UnreachableService()
    )

    response = client.get("/api/hugging-face/trending", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    # The reason travels in the body, so the panel states the outage rather than
    # inferring it from a throw — and an empty Hub stays distinguishable from an
    # unreachable one.
    assert body["unreachable"]["reason_code"] == "hugging_face_unavailable"


def test_an_owner_driven_hugging_face_read_still_fails_loudly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half of BUG-296, and the reason it is not a blanket change.

    Search is something the owner asked for. A failed request there *is* a
    failed request, and turning every Hub route into a 200 would be how the next
    real outage becomes invisible. Only the unrequested probe changed.
    """
    from raiker.models.huggingface import HuggingFaceAccessError

    client, headers, _workspace = _client(tmp_path)

    class UnreachableService:
        def search(self, *_args: object, **_kwargs: object) -> list[object]:
            raise HuggingFaceAccessError("hugging_face_unavailable", "")

    monkeypatch.setattr(
        model_routes, "_hugging_face_service", lambda _request: UnreachableService()
    )

    response = client.get(
        "/api/hugging-face/search", headers=headers, params={"query": "gguf"}
    )

    assert response.status_code == 503
