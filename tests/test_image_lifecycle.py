# SPDX-License-Identifier: Apache-2.0
"""UX-DESIGN-01 — a generated picture can be exported, put away and brought back.

DEC-07 step 4 asks for export and governed delete/restore on Design's assets.
The rules pinned here:

* deleting is recoverable — the row and its bytes stay, listed apart from the
  gallery, and restoring brings the picture back with its lineage;
* removing for good is only ever the second step, and takes the row and its
  bytes in one transaction, so nothing is left orphaned;
* every one of these is owner-scoped, and another owner's id answers exactly as
  an id that was never issued;
* a picture in Recently deleted cannot be the subject of an edit;
* an export is named for what it is, with the extension of the bytes returned.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _picture(
    store: SQLiteStore,
    generation_id: str,
    *,
    owner: str = OWNER,
    media_type: str = "image/png",
    source: str | None = None,
    prompt: str = "A lighthouse at dusk, oil painting",
) -> None:
    attachment_id = f"att_{generation_id}"
    store.save_attachment(
        attachment_id=attachment_id,
        kind="generated_image",
        filename=f"{generation_id}.png",
        media_type=media_type,
        sha256="x",
        data=PNG,
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
        attachment_id=attachment_id,
        media_type=media_type,
        byte_size=len(PNG),
        source_generation_id=source,
        kind="edit" if source else "create",
    )


@pytest.fixture
def setup(tmp_path: Path) -> tuple[TestClient, SQLiteStore, dict[str, str]]:
    root = tmp_path / "images"
    root.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=root)
    token, _ = ApiSessionStore(root).create_session(OWNER)
    return (
        TestClient(create_app(root)),
        SQLiteStore(root),
        {"Authorization": f"Bearer {token}"},
    )


def _ids(rows: list[dict[str, object]]) -> list[object]:
    return [row["generation_id"] for row in rows]


def test_delete_moves_a_picture_to_recently_deleted_and_restore_brings_it_back(
    setup: tuple[TestClient, SQLiteStore, dict[str, str]],
) -> None:
    client, store, auth = setup
    _picture(store, "img_origin")
    _picture(store, "img_edit", source="img_origin")

    assert client.delete("/api/images/img_origin", headers=auth).json()["state"] == "deleted"
    gallery = client.get("/api/images", headers=auth).json()
    assert _ids(gallery["generations"]) == ["img_edit"]
    assert _ids(gallery["deleted"]) == ["img_origin"]
    assert gallery["deleted"][0]["deleted_at"]
    # The bytes stay while it is recoverable, so Recently deleted can show it.
    assert client.get("/api/images/img_origin/bytes", headers=auth).status_code == 200

    assert client.post("/api/images/img_origin/restore", headers=auth).json()["state"] == "restored"
    gallery = client.get("/api/images", headers=auth).json()
    assert set(_ids(gallery["generations"])) == {"img_origin", "img_edit"}
    assert gallery["deleted"] == []
    # Lineage survived the round trip.
    edit = next(row for row in gallery["generations"] if row["generation_id"] == "img_edit")
    assert edit["source_generation_id"] == "img_origin"


def test_removing_for_good_is_only_the_second_step_and_leaves_no_bytes(
    setup: tuple[TestClient, SQLiteStore, dict[str, str]],
) -> None:
    client, store, auth = setup
    _picture(store, "img_one")

    # Not put away first: refused, and nothing is touched.
    assert client.delete("/api/images/img_one/purge", headers=auth).status_code == 404
    assert store.load_attachment("att_img_one", owner_principal_id=OWNER) is not None

    client.delete("/api/images/img_one", headers=auth)
    assert client.delete("/api/images/img_one/purge", headers=auth).json()["state"] == "removed"
    assert store.get_image_generation("img_one", owner_principal_id=OWNER) is None
    assert store.load_attachment("att_img_one", owner_principal_id=OWNER) is None
    gallery = client.get("/api/images", headers=auth).json()
    assert gallery["generations"] == [] and gallery["deleted"] == []


def test_another_owners_picture_answers_like_one_never_issued(
    setup: tuple[TestClient, SQLiteStore, dict[str, str]],
) -> None:
    client, store, auth = setup
    _picture(store, "img_theirs", owner="principal_someone_else")
    for method, path in (
        ("DELETE", "/api/images/img_theirs"),
        ("POST", "/api/images/img_theirs/restore"),
        ("DELETE", "/api/images/img_theirs/purge"),
    ):
        mine = client.request(method, path, headers=auth)
        never = client.request(method, path.replace("img_theirs", "img_never"), headers=auth)
        assert mine.status_code == never.status_code == 404
        assert mine.json() == never.json()
    row = store.get_image_generation("img_theirs", owner_principal_id="principal_someone_else")
    assert row is not None and row["deleted_at"] is None


def test_an_export_is_named_for_the_picture_with_its_real_extension(
    setup: tuple[TestClient, SQLiteStore, dict[str, str]],
) -> None:
    client, store, auth = setup
    _picture(store, "img_jpeg_123456", media_type="image/jpeg", prompt='A "quoted"/../ name; rm -rf')
    answer = client.get("/api/images/img_jpeg_123456/bytes?download=1", headers=auth)
    assert answer.status_code == 200
    disposition = answer.headers["content-disposition"]
    assert disposition == 'attachment; filename="raiker-a-quoted-name-rm-rf-123456.jpg"'
    assert answer.headers["cache-control"] == "no-store"
    inline = client.get("/api/images/img_jpeg_123456/bytes", headers=auth)
    assert inline.headers["content-disposition"].startswith("inline;")


def test_a_deleted_picture_cannot_be_the_subject_of_an_edit(
    setup: tuple[TestClient, SQLiteStore, dict[str, str]],
) -> None:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.executors.tier2_image import ImageGenerationExecutor

    client, store, auth = setup
    _picture(store, "img_gone")
    client.delete("/api/images/img_gone", headers=auth)
    raw = store.get_principal(OWNER)
    assert raw is not None
    executor = ImageGenerationExecutor(store.paths.workspace_root, store)
    _row, _data, reason = executor._subject(Principal(**raw), "img_gone")
    assert reason == "image_source_not_found"


def test_the_gallery_returns_what_research_a_picture_was_sent_with(
    setup: tuple[TestClient, SQLiteStore, dict[str, str]],
) -> None:
    # UX-DESIGN-03 — provenance travels with the picture.
    client, store, auth = setup
    store.record_image_generation(
        generation_id="img_ref",
        owner_principal_id=OWNER,
        profile_id="openai-hosted",
        provider="openai",
        model="gpt-image-1",
        prompt="a lighthouse",
        size="1024x1024",
        status="refused",
        reason_code="image_provider_credential_missing",
        references_json='[{"name": "Colours", "text": "white and red", "sources": ["https://example.org/a"]}]',
    )
    store.record_image_generation(
        generation_id="img_bad",
        owner_principal_id=OWNER,
        profile_id="openai-hosted",
        provider="openai",
        model="gpt-image-1",
        prompt="unreadable provenance",
        size="1024x1024",
        status="refused",
        references_json="{not json",
    )
    rows = {row["generation_id"]: row for row in client.get("/api/images", headers=auth).json()["generations"]}
    assert rows["img_ref"]["references"] == [
        {"name": "Colours", "text": "white and red", "sources": ["https://example.org/a"]}
    ]
    assert rows["img_bad"]["references"] == []


def test_a_generate_request_carries_references_to_the_governed_path(
    setup: tuple[TestClient, SQLiteStore, dict[str, str]],
) -> None:
    client, store, auth = setup
    answer = client.post(
        "/api/images",
        headers=auth,
        json={
            "profile_id": "openai-hosted",
            "prompt": "a lighthouse",
            "references": [{"name": "Colours", "text": "white and red", "sources": ["https://example.org/a"]}],
        },
    )
    # The capability is off in a fresh workspace, so it is refused — but as a
    # governed refusal, not a body the route could not read.
    assert answer.status_code == 400
