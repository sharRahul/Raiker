"""§13.2 item 6 — a creating request sent twice creates once.

Owner-scoped and payload-bound: the same owner, key and body get the first
answer again; the same key on a different body is refused; another owner's key
is a different key; a refused request releases its key; and a request without a
key behaves as it always did.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.idempotency import payload_digest


def _owner(client: TestClient, username: str = "alice") -> dict[str, str]:
    token = client.post(
        "/api/auth/register", json={"username": username, "password": "right-pass-123"}
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, offline_default_model: None) -> TestClient:
    monkeypatch.delenv("RAIKER_CONNECTOR_VAULT_KEY", raising=False)
    return TestClient(create_app(tmp_path))


def _count(client: TestClient, headers: dict[str, str]) -> int:
    return len(client.get("/api/tasks", headers=headers).json())


def test_the_digest_ignores_key_order() -> None:
    assert payload_digest({"a": 1, "b": [1, 2]}) == payload_digest({"b": [1, 2], "a": 1})
    assert payload_digest({"a": 1}) != payload_digest({"a": 2})


def test_the_same_draft_sent_twice_files_one_task(client: TestClient) -> None:
    h = _owner(client)
    before = _count(client, h)
    keyed = {**h, "Idempotency-Key": "draft-0001-aaaa"}
    first = client.post("/api/tasks", json={"title": "Water the plants", "description": "Do it"}, headers=keyed)
    again = client.post("/api/tasks", json={"title": "Water the plants", "description": "Do it"}, headers=keyed)
    assert first.status_code == 201 and again.status_code == 201
    assert again.json()["task_id"] == first.json()["task_id"]
    assert _count(client, h) == before + 1


def test_a_reused_key_on_a_changed_draft_is_refused(client: TestClient) -> None:
    h = {**_owner(client), "Idempotency-Key": "draft-0002-bbbb"}
    assert client.post("/api/tasks", json={"title": "One", "description": "Do it"}, headers=h).status_code == 201
    changed = client.post("/api/tasks", json={"title": "Two", "description": "Do it"}, headers=h)
    assert changed.status_code == 409
    assert changed.json()["detail"]["reason_code"] == "idempotency_key_reused"


def test_a_refused_request_releases_its_key(client: TestClient) -> None:
    h = {**_owner(client), "Idempotency-Key": "draft-0003-cccc"}
    refused = client.post("/api/tasks", json={"title": "   ", "description": "Do it"}, headers=h)
    assert refused.status_code == 422
    # The corrected draft, same key, goes through.
    assert client.post("/api/tasks", json={"title": "Fixed", "description": "Do it"}, headers=h).status_code == 201


def test_keys_are_scoped_to_their_owner(client: TestClient) -> None:
    alice = _owner(client, "alice")
    from raiker.storage.sqlite import SQLiteStore

    store = SQLiteStore(client.app.state.workspace_root)  # type: ignore[attr-defined]
    first = client.post(
        "/api/tasks", json={"title": "Alice's", "description": "Do it"}, headers={**alice, "Idempotency-Key": "draft-shared-key"}
    )
    assert first.status_code == 201
    # The same key under another principal is another key: it reserves fresh.
    from raiker.api.idempotency import IdempotencyGuard

    guard = IdempotencyGuard(store, "principal_someone_else", "create_task", "draft-shared-key")
    assert guard.begin({"title": "Alice's", "description": "Do it"}) is None
    guard.abandon()


def test_a_malformed_key_is_refused_and_no_key_is_unchanged(client: TestClient) -> None:
    h = _owner(client)
    bad = client.post("/api/tasks", json={"title": "x", "description": "Do it"}, headers={**h, "Idempotency-Key": "short"})
    assert bad.status_code == 422
    before = _count(client, h)
    client.post("/api/tasks", json={"title": "No key", "description": "Do it"}, headers=h)
    client.post("/api/tasks", json={"title": "No key", "description": "Do it"}, headers=h)
    assert _count(client, h) == before + 2
