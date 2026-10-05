"""13.2 #6 — a settings save from a stale read neither overwrites nor is lost.

Settings was a whole-document write: a page opened before another tab (or the
composer's approval posture, or a quiet-hours change) saved its own key would
put the old value back on its next Save. Now a save carries the revision it read
and what each key it changed held then. A stale save whose keys nobody else
touched is merged onto what is stored now; one that would overwrite a newer
value of the same key is refused 409 ``settings_conflict`` and nothing is written.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app


@pytest.fixture()
def owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, dict[str, str]]:
    monkeypatch.delenv("RAIKER_CONNECTOR_VAULT_KEY", raising=False)
    client = TestClient(create_app(tmp_path))
    token = client.post(
        "/api/auth/register", json={"username": "alice", "password": "right-pass-123"}
    ).json()["token"]
    return client, {"Authorization": f"Bearer {token}"}


def test_the_revision_changes_exactly_when_the_document_does(owner: tuple[TestClient, dict[str, str]]) -> None:
    client, h = owner
    first = client.get("/api/settings", headers=h).json()["revision"]
    saved = client.put("/api/settings", json={"settings": {"a": 1}}, headers=h).json()
    assert saved["revision"] != first
    assert client.get("/api/settings", headers=h).json()["revision"] == saved["revision"]


def test_a_stale_save_of_other_keys_is_merged_not_overwritten(owner: tuple[TestClient, dict[str, str]]) -> None:
    client, h = owner
    client.put("/api/settings", json={"settings": {"a": 1, "b": 1}}, headers=h)
    page_one = client.get("/api/settings", headers=h).json()
    # Another tab changes `b`.
    client.put("/api/settings", json={"settings": {"a": 1, "b": 2}}, headers=h)
    # The first page changes `a` from what it read, still holding the old `b`.
    saved = client.put(
        "/api/settings",
        json={"settings": {"a": 5, "b": 1}, "expected_revision": page_one["revision"], "base": {"a": 1}},
        headers=h,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["settings"] == {"a": 5, "b": 2}
    assert saved.json()["merged_keys"] == ["b"]


def test_a_stale_save_of_the_same_key_is_refused_and_writes_nothing(owner: tuple[TestClient, dict[str, str]]) -> None:
    client, h = owner
    client.put("/api/settings", json={"settings": {"a": 1}}, headers=h)
    page_one = client.get("/api/settings", headers=h).json()
    client.put("/api/settings", json={"settings": {"a": 2}}, headers=h)
    refused = client.put(
        "/api/settings",
        json={"settings": {"a": 3}, "expected_revision": page_one["revision"], "base": {"a": 1}},
        headers=h,
    )
    assert refused.status_code == 409
    assert refused.json()["detail"] == {"reason_code": "settings_conflict", "keys": ["a"]}
    assert client.get("/api/settings", headers=h).json()["settings"] == {"a": 2}


def test_a_current_save_is_the_whole_document_as_before(owner: tuple[TestClient, dict[str, str]]) -> None:
    client, h = owner
    client.put("/api/settings", json={"settings": {"a": 1, "b": 1}}, headers=h)
    current = client.get("/api/settings", headers=h).json()["revision"]
    saved = client.put(
        "/api/settings",
        json={"settings": {"a": 1}, "expected_revision": current, "base": {"b": 1}},
        headers=h,
    )
    assert saved.json()["settings"] == {"a": 1}
    assert saved.json()["merged_keys"] == []


def test_two_pages_arriving_at_the_same_value_is_not_a_conflict(owner: tuple[TestClient, dict[str, str]]) -> None:
    client, h = owner
    client.put("/api/settings", json={"settings": {"a": 1}}, headers=h)
    page_one = client.get("/api/settings", headers=h).json()
    client.put("/api/settings", json={"settings": {"a": 2}}, headers=h)
    agreed = client.put(
        "/api/settings",
        json={"settings": {"a": 2}, "expected_revision": page_one["revision"], "base": {"a": 1}},
        headers=h,
    )
    assert agreed.status_code == 200
    assert agreed.json()["settings"] == {"a": 2}
