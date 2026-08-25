"""Owner-scoped managed knowledge file endpoints."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.storage.sqlite import SQLiteStore


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
    response = client.post("/api/auth/session", json={"as_principal": None})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _owner_principal(workspace: Path) -> str:
    store = SQLiteStore(workspace)
    with store.connect() as connection:
        row = connection.execute(
            "SELECT principal_id FROM principals WHERE principal_type = 'human' LIMIT 1"
        ).fetchone()
    assert row is not None
    return str(row["principal_id"])


def _project(workspace: Path, name: str) -> str:
    service = DashboardService(workspace)
    result = service.create_project(name, _owner_principal(workspace))
    assert result.ok, result.data
    return str(result.data["project_id"])


def _file(relative_path: str, text: str, media_type: str = "text/markdown") -> dict[str, Any]:
    return {
        "relative_path": relative_path,
        "media_type": media_type,
        "data_base64": base64.b64encode(text.encode("utf-8")).decode("ascii"),
    }


def test_import_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/memory/files").status_code == 401
    assert client.post("/api/memory/files", json={"files": []}).status_code == 401


def test_memory_import_stores_and_indexes_a_readable_file(
    workspace: Path, client: TestClient, headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/memory/files",
        json={"files": [_file("notes/handbook.md", "# Handbook\n\nDeployment checklist.\n")]},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    result = body["results"][0]
    assert result["relative_path"] == "notes/handbook.md"
    assert result["index_state"] == "ready"
    stored = workspace / ".raiker/memory-files/notes/handbook.md"
    assert stored.read_text(encoding="utf-8").startswith("# Handbook")


def test_unreadable_types_are_stored_as_metadata_only(
    workspace: Path, client: TestClient, headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/memory/files",
        json={
            "files": [
                {
                    "relative_path": "archive/data.custom",
                    "media_type": "application/x-custom",
                    "data_base64": base64.b64encode(b"\x00\x01payload").decode("ascii"),
                }
            ]
        },
        headers=headers,
    )

    result = response.json()["results"][0]
    assert result["ok"] is True
    assert result["index_state"] == "metadata_only"
    assert (workspace / ".raiker/memory-files/archive/data.custom").read_bytes() == b"\x00\x01payload"


def test_folder_import_preserves_hierarchy_and_reports_per_file(
    workspace: Path, client: TestClient, headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/memory/files",
        json={
            "files": [
                _file("book/ch1/intro.md", "Intro text about alpha."),
                _file("book/ch2/body.md", "Body text about beta."),
                _file("../escape.md", "nope"),
            ]
        },
        headers=headers,
    )

    body = response.json()
    assert body["ok"] is False
    assert [entry["ok"] for entry in body["results"]] == [True, True, False]
    assert body["results"][2]["reason_code"] == "managed_file_path_outside_scope"
    assert (workspace / ".raiker/memory-files/book/ch1/intro.md").exists()
    assert (workspace / ".raiker/memory-files/book/ch2/body.md").exists()
    assert not (workspace.parent / "escape.md").exists()


def test_duplicate_relative_path_is_reported_not_overwritten(
    workspace: Path, client: TestClient, headers: dict[str, str]
) -> None:
    client.post("/api/memory/files", json={"files": [_file("a.md", "first")]}, headers=headers)

    response = client.post(
        "/api/memory/files", json={"files": [_file("a.md", "second")]}, headers=headers
    )

    assert response.json()["results"][0]["reason_code"] == "managed_file_already_exists"
    assert (workspace / ".raiker/memory-files/a.md").read_text(encoding="utf-8") == "first"


def test_project_files_land_under_the_managed_project_root(
    workspace: Path, client: TestClient, headers: dict[str, str]
) -> None:
    project_id = _project(workspace, "Alpha")

    response = client.post(
        f"/api/projects/{project_id}/managed-files",
        json={"files": [_file("spec.md", "Alpha spec.")]},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["project_id"] == project_id
    assert (workspace / ".raiker/projects/alpha/spec.md").read_text(encoding="utf-8") == "Alpha spec."


def test_unknown_project_is_not_disclosed(client: TestClient, headers: dict[str, str]) -> None:
    response = client.get("/api/projects/proj_absent/managed-files", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"]["reason_code"] == "project_not_found"


def test_list_returns_only_the_requested_scope(
    workspace: Path, client: TestClient, headers: dict[str, str]
) -> None:
    project_id = _project(workspace, "Alpha")
    client.post("/api/memory/files", json={"files": [_file("m.md", "memory file")]}, headers=headers)
    client.post(
        f"/api/projects/{project_id}/managed-files",
        json={"files": [_file("p.md", "project file")]},
        headers=headers,
    )

    memory_files = client.get("/api/memory/files", headers=headers).json()["files"]
    project_files = client.get(
        f"/api/projects/{project_id}/managed-files", headers=headers
    ).json()["files"]

    assert [entry["relative_path"] for entry in memory_files] == ["m.md"]
    assert [entry["relative_path"] for entry in project_files] == ["p.md"]


def test_delete_retires_the_row_and_removes_the_bytes(
    workspace: Path, client: TestClient, headers: dict[str, str]
) -> None:
    imported = client.post(
        "/api/memory/files", json={"files": [_file("gone.md", "temporary")]}, headers=headers
    ).json()["results"][0]

    response = client.delete(f"/api/managed-files/{imported['file_id']}", headers=headers)

    assert response.status_code == 200, response.text
    assert not (workspace / ".raiker/memory-files/gone.md").exists()
    assert client.get("/api/memory/files", headers=headers).json()["files"] == []


def test_delete_of_an_unknown_file_is_a_404(client: TestClient, headers: dict[str, str]) -> None:
    response = client.delete("/api/managed-files/mfile_absent", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"]["reason_code"] == "managed_file_not_found"


def test_retry_reindexes_a_repaired_file(
    workspace: Path, client: TestClient, headers: dict[str, str]
) -> None:
    imported = client.post(
        "/api/memory/files", json={"files": [_file("retry.md", "alpha content")]}, headers=headers
    ).json()["results"][0]
    (workspace / ".raiker/memory-files/retry.md").unlink()
    failed = client.post(
        f"/api/managed-files/{imported['file_id']}/retry", headers=headers
    ).json()
    assert failed["index_state"] == "failed"

    (workspace / ".raiker/memory-files/retry.md").write_text("alpha content", encoding="utf-8")
    repaired = client.post(
        f"/api/managed-files/{imported['file_id']}/retry", headers=headers
    ).json()

    assert repaired["index_state"] == "ready"


def test_an_empty_request_is_rejected(client: TestClient, headers: dict[str, str]) -> None:
    response = client.post("/api/memory/files", json={"files": []}, headers=headers)

    assert response.status_code == 400
    assert response.json()["detail"]["reason_code"] == "no_files"


def test_invalid_base64_is_reported_per_file(client: TestClient, headers: dict[str, str]) -> None:
    response = client.post(
        "/api/memory/files",
        json={"files": [{"relative_path": "bad.md", "media_type": "text/markdown", "data_base64": "!!!"}]},
        headers=headers,
    )

    assert response.json()["results"][0]["reason_code"] == "invalid_base64"
