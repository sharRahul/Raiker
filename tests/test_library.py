"""The Library and Pin to project (Quiet UI 06, QUI-F15; 04, Block toolbar).

What these hold:

* the Library reads what already exists — a generated document, a Design image
  and document, a pinned block — owner-scoped and newest first;
* a pin is copied from the stored answer and re-validated, so prose, a refused
  block or a place past the end of the answer cannot be pinned, and nothing the
  browser sends becomes the pinned data;
* pinning the same block twice keeps one pin and moves it;
* another account's conversation, and a turn borrowed from one, answer as
  unknown.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.storage.sqlite import SQLiteStore

_FIGURES = {
    "caption": "Quarter in numbers",
    "items": [{"label": "Revenue", "value": 1200, "unit": "$"}],
    "source": "Q3 report",
}
_ANSWER = (
    "Here are the numbers.\n\n```raiker:figures\n" + json.dumps(_FIGURES) + "\n```\n\nThat is all."
)


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path))


def _register(client: TestClient, name: str = "owner") -> dict[str, str]:
    response = client.post("/api/auth/register", json={"username": name, "password": "a-long-password-1"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _store(client: TestClient) -> SQLiteStore:
    return SQLiteStore(Path(client.app.state.workspace_root))  # type: ignore[attr-defined]


def _seed(client: TestClient, h: dict[str, str]) -> tuple[str, str, str]:
    """A conversation in a project with one answer that declares key figures."""
    store = _store(client)
    principal = client.get("/api/auth/whoami", headers=h).json()["principal_id"]
    user_id = store.principal_user_id(principal)
    project = client.post("/api/projects", json={"name": "Quarterly"}, headers=h)
    assert project.status_code in (200, 201), project.text
    project_id = project.json()["project_id"]
    store.create_session("sess_lib", str(store.paths.workspace_root), title="Q3 numbers", user_id=user_id)
    store.set_session_project("sess_lib", project_id, user_id=user_id)
    store.insert_turn("sess_lib", "turn_lib", "What were the numbers?")
    store.complete_turn("turn_lib", "completed", _ANSWER)
    return "sess_lib", "turn_lib", project_id


def test_a_block_is_pinned_from_the_stored_answer_and_listed(client: TestClient) -> None:
    h = _register(client)
    session_id, turn_id, project_id = _seed(client, h)
    pinned = client.post(
        "/api/library/pins",
        json={"session_id": session_id, "turn_id": turn_id, "part_index": 1, "project_id": project_id},
        headers=h,
    )
    assert pinned.status_code == 201, pinned.text
    assert pinned.json()["project_name"] == "Quarterly"
    library = client.get("/api/library", headers=h).json()
    blocks = [item for item in library["items"] if item["kind"] == "block"]
    assert len(blocks) == 1
    block = blocks[0]
    assert block["title"] == "Quarter in numbers"
    assert block["detail"] == "Key figures"
    assert block["project_name"] == "Quarterly"
    assert block["href"] == f"#/new-chat?session={session_id}&turn={turn_id}"
    assert block["block"]["type"] == "figures"
    assert block["block"]["data"]["source"] == "Q3 report"
    in_project = client.get(f"/api/library?project_id={project_id}", headers=h).json()["items"]
    assert [item["item_id"] for item in in_project] == [block["item_id"]]
    pins = client.get(f"/api/library/pins?session_id={session_id}", headers=h).json()["pins"]
    assert [(pin["turn_id"], pin["part_index"]) for pin in pins] == [(turn_id, 1)]


def test_only_a_drawn_block_can_be_pinned(client: TestClient) -> None:
    h = _register(client)
    session_id, turn_id, _project = _seed(client, h)
    for index in (0, 2, 9):  # prose before, prose after, past the end
        refused = client.post(
            "/api/library/pins",
            json={"session_id": session_id, "turn_id": turn_id, "part_index": index},
            headers=h,
        )
        assert refused.status_code == 422, (index, refused.text)
        assert "library_pin_not_a_block" in refused.text


def test_pinning_twice_keeps_one_pin_and_moves_it(client: TestClient) -> None:
    h = _register(client)
    session_id, turn_id, project_id = _seed(client, h)
    first = client.post(
        "/api/library/pins",
        json={"session_id": session_id, "turn_id": turn_id, "part_index": 1, "project_id": project_id},
        headers=h,
    ).json()
    second = client.post(
        "/api/library/pins",
        json={"session_id": session_id, "turn_id": turn_id, "part_index": 1, "project_id": None},
        headers=h,
    ).json()
    assert second["pin_id"] == first["pin_id"]
    assert second["project_id"] is None
    assert client.get(f"/api/library?project_id={project_id}", headers=h).json()["items"] == []
    moved = client.put(f"/api/library/pins/{first['pin_id']}/project", json={"project_id": project_id}, headers=h)
    assert moved.status_code == 200, moved.text
    assert moved.json()["project_name"] == "Quarterly"
    assert len(client.get(f"/api/library?project_id={project_id}", headers=h).json()["items"]) == 1
    assert client.put(
        f"/api/library/pins/{first['pin_id']}/project", json={"project_id": "proj_nope"}, headers=h
    ).status_code == 404
    removed = client.delete(f"/api/library/pins/{first['pin_id']}", headers=h)
    assert removed.status_code == 200
    assert client.get("/api/library?kind=block", headers=h).json()["items"] == []
    assert client.delete(f"/api/library/pins/{first['pin_id']}", headers=h).status_code == 404


def test_a_generated_document_is_in_the_library_with_its_download(client: TestClient) -> None:
    from raiker.runtime.document_generation import generate_document

    h = _register(client)
    session_id, turn_id, project_id = _seed(client, h)
    principal = client.get("/api/auth/whoami", headers=h).json()["principal_id"]
    store = _store(client)
    made = generate_document(
        store.paths.workspace_root, store, path="notes/summary.md", text="# Summary",
        session_id=session_id, turn_id=turn_id, principal_id=principal,
    )
    assert made["status"] == "success"
    documents = client.get("/api/library?kind=document", headers=h).json()["items"]
    assert len(documents) == 1
    document = documents[0]
    assert document["title"] == "summary.md"
    assert document["detail"].startswith("Markdown · ")
    assert document["project_id"] == project_id
    assert document["download_url"] == (
        f"/api/sessions/{session_id}/attachments/{made['attachment_id']}/download"
    )
    assert client.get(document["download_url"], headers=h).status_code == 200


def _foreign_conversation(store: SQLiteStore) -> None:
    """A conversation that belongs to another user row, with one answer."""
    store._execute(
        "INSERT INTO users (user_id, display_name, email, is_active, created_at, updated_at) "
        "VALUES ('usr_other', 'Other', NULL, 1, '2026-10-26T00:00:00Z', '2026-10-26T00:00:00Z')"
    )
    store.create_session("sess_other", str(store.paths.workspace_root), title="Not yours", user_id="usr_other")
    store.insert_turn("sess_other", "turn_other", "Numbers?")
    store.complete_turn("turn_other", "completed", _ANSWER)


def test_a_conversation_of_another_account_answers_as_unknown(client: TestClient) -> None:
    h = _register(client)
    _foreign_conversation(_store(client))
    refused = client.post(
        "/api/library/pins",
        json={"session_id": "sess_other", "turn_id": "turn_other", "part_index": 1},
        headers=h,
    )
    assert refused.status_code == 404
    assert client.get("/api/library/pins?session_id=sess_other", headers=h).status_code == 404
    assert client.get("/api/library?project_id=proj_not_mine", headers=h).status_code == 404


def test_a_turn_from_another_conversation_cannot_be_pinned_through_this_one(client: TestClient) -> None:
    h = _register(client)
    session_id, _turn, _project = _seed(client, h)
    _foreign_conversation(_store(client))
    refused = client.post(
        "/api/library/pins",
        json={"session_id": session_id, "turn_id": "turn_other", "part_index": 1},
        headers=h,
    )
    assert refused.status_code == 404
    assert "unknown_turn" in refused.text


def test_an_unknown_kind_is_refused(client: TestClient) -> None:
    h = _register(client)
    assert client.get("/api/library?kind=secrets", headers=h).status_code == 422


def test_an_uncaptioned_block_is_named_from_its_contents() -> None:
    from raiker.control.library import block_title

    assert block_title("figures", {"items": [{"label": "Revenue"}, {"label": "Costs"}]}) == "Revenue, Costs"
    assert block_title("compare", {"items": ["Laptop A", "Laptop B"]}) == "Laptop A, Laptop B"
    assert block_title("figures", {"caption": "Q3", "items": [{"label": "Revenue"}]}) == "Q3"
    assert block_title("measure", {}) == "Measure"
