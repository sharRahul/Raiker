"""Projects: creation, selection, the tree, the folder behind one, and managed files."""

from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from tests.contract_cases.base import Call, Cases, Seed, plain

FILES = {
    "files": [
        {
            "relative_path": "notes/plan.md",
            "media_type": "text/markdown",
            "data_base64": base64.b64encode(b"# Plan\n\nShip it.").decode(),
        }
    ]
}


def _project(client: TestClient, h: dict[str, str], name: str = "Alpha") -> str:
    created = client.post("/api/projects", json={"name": name}, headers=h)
    assert created.status_code == 200, created.text
    return str(created.json()["project_id"])


def _attached(ws: Path, client: TestClient, h: dict[str, str]) -> str:
    """A project over a folder the owner attached."""
    folder = ws.parent / "attached-folder"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "readme.md").write_bytes(b"# Readme\n")
    created = client.post(
        "/api/projects",
        json={"name": "Attached", "attach_path": str(folder), "attach_writable": True},
        headers=h,
    )
    assert created.status_code == 200, created.text
    return str(created.json()["project_id"])


def _on_project(suffix: str, body: object = None) -> Seed:
    def seed(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        path = f"/api/projects/{_project(client, h)}{suffix}"
        return path if body is None else (path, body)

    return seed


def _on_attached(suffix: str, body: object = None) -> Seed:
    def seed(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        path = f"/api/projects/{_attached(ws, client, h)}{suffix}"
        return path if body is None else (path, body)

    return seed


def _restored(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    project_id = _project(client, h)
    client.put(f"/api/projects/{project_id}/archive", headers=h)
    return f"/api/projects/{project_id}/restore"


def _attach(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    folder = ws.parent / "later-folder"
    folder.mkdir(parents=True, exist_ok=True)
    return f"/api/projects/{_project(client, h)}/root/attach", {"path": str(folder), "writable": True}


def _imported(client: TestClient, h: dict[str, str]) -> str:
    project_id = _project(client, h)
    imported = client.post(f"/api/projects/{project_id}/managed-files", json=FILES, headers=h)
    assert imported.status_code == 200, imported.text
    return project_id


def _project_files_listed(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return f"/api/projects/{_imported(client, h)}/managed-files"


def _managed_file(suffix: str) -> Seed:
    def seed(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
        project_id = _imported(client, h)
        rows = client.get(f"/api/projects/{project_id}/managed-files", headers=h).json()["files"]
        return f"/api/managed-files/{rows[0]['file_id']}{suffix}"

    return seed


def _memory_files(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    client.post("/api/memory/files", json=FILES, headers=h)
    return "/api/memory/files"


def _tree(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    parent = _project(client, h, "Parent")
    child = _project(client, h, "Child")
    client.put(f"/api/projects/{child}/move", json={"parent_id": parent}, headers=h)
    return "/api/projects/tree"


def _move(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    parent = _project(client, h, "Parent")
    child = _project(client, h, "Child")
    return f"/api/projects/{child}/move", {"parent_id": parent}


def _select(_ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    return "/api/projects/selection", {"project_id": _project(client, h)}


def _delete_attached(ws: Path, client: TestClient, h: dict[str, str]) -> Call:
    """An attached project: its folder is the owner's, so no step-up is needed."""
    project_id = _attached(ws, client, h)
    return f"/api/projects/{project_id}", None, {**h, "X-Project-Delete-Confirm": project_id}


CONTEXT = {"instructions": "Be brief.", "attachment_ids": [], "memory_enabled": False, "memory_mode": "inherit"}

CASES: Cases = {
    ("POST", "/api/projects"): plain("/api/projects", {"name": "Alpha"}),
    ("PUT", "/api/projects/selection"): _select,
    ("GET", "/api/projects/tree"): _tree,
    ("PUT", "/api/projects/{project_id}/context"): _on_project("/context", CONTEXT),
    ("GET", "/api/projects/{project_id}/deletion-preview"): _on_project("/deletion-preview"),
    ("DELETE", "/api/projects/{project_id}"): _delete_attached,
    ("PUT", "/api/projects/{project_id}/move"): _move,
    ("PUT", "/api/projects/{project_id}/archive"): _on_project("/archive"),
    ("PUT", "/api/projects/{project_id}/restore"): _restored,
    ("GET", "/api/projects/{project_id}/files"): _on_project("/files"),
    ("GET", "/api/projects/{project_id}/browse"): _on_attached("/browse"),
    ("GET", "/api/projects/{project_id}/root/status"): _on_attached("/root/status"),
    ("POST", "/api/projects/{project_id}/root/index"): _on_attached("/root/index"),
    ("POST", "/api/projects/{project_id}/root/attach"): _attach,
    ("DELETE", "/api/projects/{project_id}/root"): _on_attached("/root"),
    ("GET", "/api/projects/{project_id}/managed-files"): _project_files_listed,
    ("POST", "/api/projects/{project_id}/managed-files"): _on_project("/managed-files", FILES),
    ("GET", "/api/memory/files"): _memory_files,
    ("POST", "/api/memory/files"): plain("/api/memory/files", FILES),
    ("DELETE", "/api/managed-files/{file_id}"): _managed_file(""),
    ("POST", "/api/managed-files/{file_id}/retry"): _managed_file("/retry"),
}
