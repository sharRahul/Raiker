"""RAIKER.md — reviewed global and project-root instruction files.

The design is docs/architecture/RAIKER_MD_INSTRUCTIONS.md. These regressions
cover the safe read (links, hard links, devices, size, encoding), discovery
(only the two files; subdirectories ignored; exact name), review binding
(digest, projection, root identity, account), disable without reactivation,
the turn refusal, and the subordinate prompt block.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.routes_prompts import _instruction_files_refusal
from raiker.context import raiker_md
from raiker.runtime.orchestrator import RuntimeOrchestrator as Orchestrator
from raiker.storage.sqlite import SQLiteStore

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX link and FIFO semantics")


# --- the pinned read ----------------------------------------------------------------


def test_a_plain_file_is_read_whole_with_its_digest(tmp_path: Path) -> None:
    (tmp_path / "RAIKER.md").write_bytes("﻿Use tabs.\n".encode())
    read = raiker_md.read_instruction_file(tmp_path)
    assert read.state == "read"
    assert read.text == "Use tabs.\n"
    assert len(read.digest) == 64


@pytest.mark.parametrize(
    ("content", "state"),
    [
        (b"", "empty"),
        (b"   \n", "empty"),
        (b"bad \x00 byte", "invalid"),
        (b"\xff\xfe not utf-8", "invalid"),
        (b"x" * (raiker_md.MAX_FILE_BYTES + 1), "oversized"),
        (("é" * (raiker_md.MAX_FILE_CHARS + 1)).encode()[: raiker_md.MAX_FILE_BYTES], "oversized"),
    ],
)
def test_a_file_that_cannot_be_used_whole_adds_nothing(tmp_path: Path, content: bytes, state: str) -> None:
    (tmp_path / "RAIKER.md").write_bytes(content)
    read = raiker_md.read_instruction_file(tmp_path)
    assert read.state == state
    assert read.text == ""


def test_only_the_exact_name_counts(tmp_path: Path) -> None:
    (tmp_path / "raiker.md").write_text("lower case", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("no alias", encoding="utf-8")
    assert raiker_md.read_instruction_file(tmp_path).state == "absent"

def test_a_project_root_falls_back_to_agents_md_then_claude_md(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("Claude rules", encoding="utf-8")
    read = raiker_md.read_instruction_file(tmp_path, raiker_md.PROJECT_FILENAMES)
    assert (read.state, read.name, read.text) == ("read", "CLAUDE.md", "Claude rules")
    (tmp_path / "AGENTS.md").write_text("Agent rules", encoding="utf-8")
    read = raiker_md.read_instruction_file(tmp_path, raiker_md.PROJECT_FILENAMES)
    assert (read.name, read.text) == ("AGENTS.md", "Agent rules")
    (tmp_path / "RAIKER.md").write_text("Raiker rules", encoding="utf-8")
    read = raiker_md.read_instruction_file(tmp_path, raiker_md.PROJECT_FILENAMES)
    assert (read.name, read.text) == ("RAIKER.md", "Raiker rules")


def test_cursorrules_is_the_last_fallback(tmp_path: Path) -> None:
    (tmp_path / ".cursorrules").write_text("Cursor rules", encoding="utf-8")
    read = raiker_md.read_instruction_file(tmp_path, raiker_md.PROJECT_FILENAMES)
    assert (read.name, read.text) == (".cursorrules", "Cursor rules")
    (tmp_path / "CLAUDE.md").write_text("Claude rules", encoding="utf-8")
    assert raiker_md.read_instruction_file(tmp_path, raiker_md.PROJECT_FILENAMES).name == "CLAUDE.md"


def test_the_global_file_never_reads_another_agents_name(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("Agent rules", encoding="utf-8")
    assert raiker_md.read_instruction_file(tmp_path).state == "absent"



@posix_only
def test_a_symlink_is_refused_not_followed(tmp_path: Path) -> None:
    secret = tmp_path / "elsewhere.md"
    secret.write_text("outside the project", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    os.symlink(secret, project / "RAIKER.md")
    assert raiker_md.read_instruction_file(project).state == "unsafe"


@posix_only
def test_a_symlinked_project_folder_is_refused(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (real / "RAIKER.md").write_text("rules", encoding="utf-8")
    os.symlink(real, tmp_path / "link")
    assert raiker_md.read_instruction_file(tmp_path / "link").state == "unsafe"


@posix_only
def test_a_second_hard_link_is_refused(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "RAIKER.md").write_text("rules", encoding="utf-8")
    os.link(project / "RAIKER.md", tmp_path / "other-name.md")
    assert raiker_md.read_instruction_file(project).state == "unsafe"


@posix_only
def test_a_fifo_is_refused_without_hanging(tmp_path: Path) -> None:
    os.mkfifo(tmp_path / "RAIKER.md")
    assert raiker_md.read_instruction_file(tmp_path).state == "unsafe"


def test_a_directory_named_raiker_md_is_refused(tmp_path: Path) -> None:
    (tmp_path / "RAIKER.md").mkdir()
    assert raiker_md.read_instruction_file(tmp_path).state == "unsafe"


def test_the_projection_redacts_secrets() -> None:
    shown = raiker_md.projection("Deploy with key sk-ant-api03-" + "a" * 90 + " please")
    assert "sk-ant-api03" not in shown


def test_the_global_folder_is_per_account_and_refuses_odd_ids(tmp_path: Path) -> None:
    one = raiker_md.global_directory(tmp_path, "usr_one")
    two = raiker_md.global_directory(tmp_path, "usr_two")
    assert one != two and one.parent == two.parent
    with pytest.raises(raiker_md.InstructionFileError):
        raiker_md.global_directory(tmp_path, "../usr_one")


# --- the owner's review, through the API -------------------------------------------------


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path / "ws"))


def _owner(client: TestClient, name: str = "owner") -> dict[str, str]:
    response = client.post("/api/auth/register", json={"username": name, "password": "a-long-password-1"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _attached_project(client: TestClient, h: dict[str, str], folder: Path) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    created = client.post(
        "/api/projects",
        json={"name": "Site", "attach_path": str(folder), "attach_writable": True},
        headers=h,
    )
    assert created.status_code == 200, created.text
    return str(created.json()["project_id"])


def _sources(view: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {source["scope"]: source for source in view["sources"]}


def test_review_binds_the_exact_revision_and_a_change_needs_a_new_one(client: TestClient, tmp_path: Path) -> None:
    h = _owner(client)
    folder = tmp_path / "site"
    project_id = _attached_project(client, h, folder)
    (folder / "RAIKER.md").write_text("Run the linter before you finish.\n", encoding="utf-8")
    (folder / "sub").mkdir()
    (folder / "sub" / "RAIKER.md").write_text("never read", encoding="utf-8")

    view = client.get(f"/api/projects/{project_id}/instruction-files", headers=h).json()
    assert view["enabled"] is False and view["needs_review"] is False
    project = _sources(view)["project"]
    assert project["state"] == "unreviewed"
    assert project["preview"] == "Run the linter before you finish."
    assert "never read" not in str(view)

    on = client.put(f"/api/projects/{project_id}/instruction-files", json={"enabled": True}, headers=h).json()
    assert on["enabled"] is True and on["needs_review"] is True  # turning on approves nothing

    stale = client.post(
        f"/api/projects/{project_id}/instruction-files/review",
        json={"scope": "project", "digest": "0" * 64},
        headers=h,
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["reason_code"] == "instruction_file_changed_since_preview"

    reviewed = client.post(
        f"/api/projects/{project_id}/instruction-files/review",
        json={"scope": "project", "digest": project["digest"]},
        headers=h,
    ).json()
    assert _sources(reviewed)["project"]["state"] == "approved"
    assert reviewed["needs_review"] is False

    (folder / "RAIKER.md").write_text("Run the linter and the tests.\n", encoding="utf-8")
    changed = client.get(f"/api/projects/{project_id}/instruction-files", headers=h).json()
    assert _sources(changed)["project"]["state"] == "changed"
    assert changed["needs_review"] is True


def test_disable_does_not_come_back_when_the_same_bytes_return(client: TestClient, tmp_path: Path) -> None:
    h = _owner(client)
    folder = tmp_path / "site"
    project_id = _attached_project(client, h, folder)
    (folder / "RAIKER.md").write_text("Rules.\n", encoding="utf-8")
    digest = _sources(client.get(f"/api/projects/{project_id}/instruction-files", headers=h).json())["project"]["digest"]
    client.post(f"/api/projects/{project_id}/instruction-files/review", json={"digest": digest}, headers=h)
    off = client.post(f"/api/projects/{project_id}/instruction-files/disable", json={"scope": "project"}, headers=h).json()
    assert _sources(off)["project"]["state"] == "disabled"
    (folder / "RAIKER.md").unlink()
    (folder / "RAIKER.md").write_text("Rules.\n", encoding="utf-8")
    again = client.get(f"/api/projects/{project_id}/instruction-files", headers=h).json()
    assert _sources(again)["project"]["state"] == "disabled"


def test_the_global_file_is_the_accounts_own(client: TestClient, tmp_path: Path) -> None:
    first = _owner(client)
    created = client.post("/api/instruction-files/global/starter", headers=first).json()["source"]
    assert created["state"] == "unreviewed"
    assert created["path"].endswith(os.path.join("user-instructions", Path(created["path"]).parent.name, "RAIKER.md"))
    reviewed = client.post(
        "/api/instruction-files/global/review", json={"scope": "global", "digest": created["digest"]}, headers=first
    ).json()["source"]
    assert reviewed["state"] == "approved"
    # Creating it again never overwrites the owner's edits.
    Path(created["path"]).write_text("My own rules.\n", encoding="utf-8")
    again = client.post("/api/instruction-files/global/starter", headers=first).json()["source"]
    assert again["preview"] == "My own rules."
    assert again["state"] == "changed"


def test_routes_refuse_a_stranger_and_a_missing_project(client: TestClient, tmp_path: Path) -> None:
    h = _owner(client)
    assert client.get("/api/projects/proj_nope/instruction-files", headers=h).status_code == 404
    stranger = TestClient(create_app(tmp_path / "ws"))
    assert stranger.get("/api/instruction-files/global").status_code == 401


# --- the turn ------------------------------------------------------------------------


def _store_project(tmp_path: Path) -> tuple[SQLiteStore, str, str, Path]:
    client = TestClient(create_app(tmp_path / "ws"))
    h = _owner(client)
    folder = tmp_path / "site"
    project_id = _attached_project(client, h, folder)
    store = SQLiteStore(tmp_path / "ws")
    project = store.load_project(project_id)
    assert project is not None
    user_id = str(project["owner_user_id"])
    row = store._row(
        "SELECT principal_id FROM principals WHERE delegated_by_user_id = ? AND principal_type = 'human' LIMIT 1",
        (user_id,),
    )
    owner = str(row["principal_id"]) if row is not None else f"principal_{user_id}"
    assert store.principal_user_id(owner) == user_id
    return store, project_id, owner, folder


def test_a_build_turn_waits_for_review_only_when_the_project_uses_files(tmp_path: Path) -> None:
    store, project_id, owner, folder = _store_project(tmp_path)
    workspace = tmp_path / "ws"
    (folder / "RAIKER.md").write_text("Rules.\n", encoding="utf-8")
    assert _instruction_files_refusal(workspace, owner, project_id) is None  # not turned on
    user_id = str(store.principal_user_id(owner))
    raiker_md.set_project_enabled(store, user_id, project_id, True)
    refused = _instruction_files_refusal(workspace, owner, project_id)
    assert refused is not None
    assert refused["reason_code"] == "instruction_files_need_review"
    assert refused["settings_route"] == f"#/projects?project={project_id}"
    project = store.load_project(project_id)
    assert project is not None
    digest = raiker_md.project_source(store, workspace, user_id, owner, project).digest
    raiker_md.review(store, workspace, user_id, owner, project=project, digest=digest)
    assert _instruction_files_refusal(workspace, owner, project_id) is None


def test_the_prompt_block_is_labelled_ordered_and_only_approved(tmp_path: Path) -> None:
    store, project_id, owner, folder = _store_project(tmp_path)
    workspace = tmp_path / "ws"
    user_id = str(store.principal_user_id(owner))
    project = store.load_project(project_id)
    assert project is not None
    path = raiker_md.create_global_starter(workspace, user_id)
    path.write_text("Global: answer in British English.\n", encoding="utf-8")
    (folder / "RAIKER.md").write_text("Project: use pnpm, not npm.\n", encoding="utf-8")
    raiker_md.set_project_enabled(store, user_id, project_id, True)
    raiker_md.review(store, workspace, user_id, owner, project=None, digest=raiker_md.global_source(store, workspace, user_id).digest)

    fake = SimpleNamespace(tool_broker=SimpleNamespace(store=store), workspace_root=workspace)
    envelope = SimpleNamespace(
        user=SimpleNamespace(id=owner),
        prompt=SimpleNamespace(metadata={"surface": "build", "project_id": project_id}),
    )
    result = Orchestrator._instruction_files_prompt(fake, envelope)  # type: ignore[arg-type]
    assert result is not None
    text, metadata = result
    assert "Global: answer in British English." in text
    assert "use pnpm" not in text  # the project file is not reviewed yet
    assert "cannot grant a tool" in text
    assert all("text" not in source and "path" not in source for source in metadata["sources"])

    raiker_md.review(
        store, workspace, user_id, owner, project=project,
        digest=raiker_md.project_source(store, workspace, user_id, owner, project).digest,
    )
    text, _ = Orchestrator._instruction_files_prompt(fake, envelope)  # type: ignore[arg-type,misc]
    assert text.index("Global RAIKER.md") < text.index("[RAIKER.md")
    # Chat never reads a project's files.
    envelope.prompt.metadata["surface"] = "chat"
    assert Orchestrator._instruction_files_prompt(fake, envelope) is None  # type: ignore[arg-type]


def test_another_account_inherits_no_review(tmp_path: Path) -> None:
    store, project_id, owner, folder = _store_project(tmp_path)
    workspace = tmp_path / "ws"
    user_id = str(store.principal_user_id(owner))
    project = store.load_project(project_id)
    assert project is not None
    (folder / "RAIKER.md").write_text("Rules.\n", encoding="utf-8")
    digest = raiker_md.project_source(store, workspace, user_id, owner, project).digest
    raiker_md.review(store, workspace, user_id, owner, project=project, digest=digest)
    assert raiker_md.project_source(store, workspace, user_id, owner, project).state == "approved"
    assert raiker_md.project_source(store, workspace, "usr_other", owner, project).state == "unreviewed"


def test_forgetting_a_project_keeps_the_global_review(tmp_path: Path) -> None:
    store, project_id, owner, _folder = _store_project(tmp_path)
    workspace = tmp_path / "ws"
    user_id = str(store.principal_user_id(owner))
    raiker_md.create_global_starter(workspace, user_id)
    raiker_md.review(store, workspace, user_id, owner, project=None, digest=raiker_md.global_source(store, workspace, user_id).digest)
    raiker_md.set_project_enabled(store, user_id, project_id, True)
    raiker_md.forget_project(store, user_id, project_id)
    assert raiker_md.project_enabled(store, user_id, project_id) is False
    assert raiker_md.global_source(store, workspace, user_id).state == "approved"


def test_the_loaded_event_is_a_catalogued_event_type() -> None:
    """Found live (RT-1116-01): an uncatalogued event type ended the Build turn's stream."""
    from raiker.contracts.models import EVENT_TYPES

    assert "instruction_files_loaded" in EVENT_TYPES
