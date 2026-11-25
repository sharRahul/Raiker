"""RU-21 — a project made for Build is its own folder, never Raiker's data folder."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.control.project_paths import folder_name, make_project_folder


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    ws = tmp_path / "ws"
    ws.mkdir()
    return TestClient(create_app(ws), client=("127.0.0.1", 50000))


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    body = client.post(
        "/api/auth/register", json={"username": "owner", "password": "correct horse battery staple 1"}
    ).json()
    return {"Authorization": f"Bearer {body['token']}", "X-CSRF-Token": body.get("csrf_token") or ""}


def test_a_folder_name_is_safe_on_every_desktop() -> None:
    assert folder_name("Pricing") == "Pricing"
    assert folder_name("a/b:c") == "a-b-c"
    assert folder_name("con") == "Project con"


def test_an_existing_folder_is_never_adopted(tmp_path: Path) -> None:
    (tmp_path / "Pricing").mkdir()
    (tmp_path / "Pricing" / "secret.txt").write_text("not ours", encoding="utf-8")
    made = make_project_folder("Pricing", tmp_path)
    assert made == tmp_path / "Pricing 2"
    assert made is not None and not any(made.iterdir())


def test_create_folder_makes_and_attaches_a_folder_outside_raiker(
    tmp_path: Path, client: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home" / "Raiker Projects"
    monkeypatch.setenv("RAIKER_PROJECTS_HOME", str(home))
    resp = client.post("/api/projects", json={"name": "Pricing", "create_folder": True}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["root_kind"] == "attached"
    assert (home / "Pricing").is_dir()
    # Nothing was made under Raiker's own data folder.
    assert not (tmp_path / "ws" / ".raiker" / "projects" / "pricing").exists()


def test_without_create_folder_the_managed_root_is_unchanged(
    tmp_path: Path, client: TestClient, headers: dict[str, str]
) -> None:
    resp = client.post("/api/projects", json={"name": "Notes"}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["root_subpath"] == ".raiker/projects/notes"
