"""DEC-07 step 4 — going back to an earlier picture is a new version.

Nothing in a picture's history is rewritten or removed by a revert: the new
version's parent is the head the owner was looking at, it carries the earlier
version's picture, and it says which version that was. The picture's bytes are
shared, so removing either version for good keeps them for the other.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _version(
    store: SQLiteStore,
    generation_id: str,
    *,
    parent: str | None = None,
    owner: str = OWNER,
    prompt: str = "a cat",
) -> None:
    attachment = f"att_{generation_id}"
    store.save_attachment(
        attachment_id=attachment,
        kind="generated_image",
        filename=f"{generation_id}.png",
        media_type="image/png",
        sha256=generation_id,
        data=PNG + generation_id.encode(),
        owner_principal_id=owner,
    )
    store.record_image_generation(
        generation_id=generation_id,
        owner_principal_id=owner,
        profile_id="openai-hosted",
        provider="openai",
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024",
        status="ok",
        attachment_id=attachment,
        media_type="image/png",
        byte_size=len(PNG),
        source_generation_id=parent,
        kind="edit" if parent else "create",
    )


@pytest.fixture
def lineage(workspace: Path) -> SQLiteStore:
    """original → edit → head."""
    store = SQLiteStore(workspace)
    _version(store, "img_original")
    _version(store, "img_edit", parent="img_original", prompt="a cat in a hat")
    _version(store, "img_head", parent="img_edit", prompt="a cat in a red hat")
    return store


def test_revert_is_a_new_version_on_top_of_the_head(
    client: TestClient, headers: dict[str, str], lineage: SQLiteStore
) -> None:
    response = client.post(
        "/api/images/img_head/revert", json={"to": "img_original"}, headers=headers
    )
    assert response.status_code == 200, response.text
    made = response.json()["generation"]
    assert made["kind"] == "revert"
    assert made["source_generation_id"] == "img_head"
    assert made["restored_generation_id"] == "img_original"
    assert made["prompt"] == "a cat"
    assert made["has_image"] is True
    # History is intact: every earlier version is still in the gallery.
    gallery = {row["generation_id"] for row in client.get("/api/images", headers=headers).json()["generations"]}
    assert {"img_original", "img_edit", "img_head", made["generation_id"]} <= gallery
    # And the new version serves the original's picture.
    picture = client.get(f"/api/images/{made['generation_id']}/bytes", headers=headers)
    original = client.get("/api/images/img_original/bytes", headers=headers)
    assert picture.content == original.content


def test_revert_reaches_back_along_its_own_history_only(
    client: TestClient, headers: dict[str, str], lineage: SQLiteStore
) -> None:
    _version(lineage, "img_unrelated")
    sideways = client.post(
        "/api/images/img_head/revert", json={"to": "img_unrelated"}, headers=headers
    )
    assert sideways.status_code == 404
    forwards = client.post(
        "/api/images/img_original/revert", json={"to": "img_head"}, headers=headers
    )
    assert forwards.status_code == 404
    itself = client.post("/api/images/img_head/revert", json={"to": "img_head"}, headers=headers)
    assert itself.status_code == 404


def test_another_owners_version_cannot_be_reverted_to(
    client: TestClient, headers: dict[str, str], lineage: SQLiteStore
) -> None:
    _version(lineage, "img_theirs", owner="principal_other")
    _version(lineage, "img_their_edit", parent="img_theirs", owner="principal_other")
    refused = client.post(
        "/api/images/img_their_edit/revert", json={"to": "img_theirs"}, headers=headers
    )
    assert refused.status_code == 404


def test_a_deleted_version_cannot_be_brought_back_by_revert(
    client: TestClient, headers: dict[str, str], lineage: SQLiteStore
) -> None:
    lineage.set_image_generation_deleted("img_original", owner_principal_id=OWNER, deleted=True)
    refused = client.post(
        "/api/images/img_head/revert", json={"to": "img_original"}, headers=headers
    )
    assert refused.status_code == 404


def test_removing_the_original_for_good_keeps_the_reverted_picture(
    client: TestClient, headers: dict[str, str], lineage: SQLiteStore
) -> None:
    made = client.post(
        "/api/images/img_head/revert", json={"to": "img_original"}, headers=headers
    ).json()["generation"]
    lineage.set_image_generation_deleted("img_original", owner_principal_id=OWNER, deleted=True)
    assert lineage.purge_image_generation("img_original", owner_principal_id=OWNER)
    still = client.get(f"/api/images/{made['generation_id']}/bytes", headers=headers)
    assert still.status_code == 200
    assert still.content.startswith(PNG)
    # Removing the last version that points at the bytes takes them with it.
    lineage.set_image_generation_deleted(made["generation_id"], owner_principal_id=OWNER, deleted=True)
    assert lineage.purge_image_generation(made["generation_id"], owner_principal_id=OWNER)
    assert lineage.load_attachment("att_img_original", owner_principal_id=OWNER) is None


def test_revert_takes_no_unknown_fields(
    client: TestClient, headers: dict[str, str], lineage: SQLiteStore
) -> None:
    response = client.post(
        "/api/images/img_head/revert",
        json={"to": "img_original", "provider": "openai"},
        headers=headers,
    )
    assert response.status_code == 422
