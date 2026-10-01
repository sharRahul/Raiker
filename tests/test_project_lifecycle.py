"""Projects §3.12 of the release-readiness review: the lifecycle around a project.

UX-PROJ-04 resolves a project's shared attachments to files. UX-PROJ-05 gives
an archive a way back. UX-PROJ-06 names every move the server refuses, a cycle
among them. UX-PROJ-07 counts what a delete removes and holds a managed
project's delete — which removes a folder from disk — behind a step-up.
UX-PROJ-09 says when work last happened in a project.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.control.dashboard import DashboardService
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def service(workspace: Path) -> DashboardService:
    return DashboardService(workspace)


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace_root=workspace))


def _token(client: TestClient) -> str:
    resp = client.post("/api/auth/session", json={"as_principal": None})
    assert resp.status_code == 200, resp.text
    return str(resp.json()["token"])


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _elevated(workspace: Path, control_token: str) -> str:
    session = ApiSessionStore(workspace).get_by_token(control_token)
    assert session is not None
    token, _ = ApiSessionStore(workspace).create_session(
        session.principal_id, scope="elevated", expires_in_seconds=60
    )
    return token


def _file(store: SQLiteStore, session_id: str, project_id: str) -> None:
    """File a session under a project directly: ownership is not under test here."""
    with store.connect() as connection:
        connection.execute(
            "UPDATE sessions SET project_id = ? WHERE session_id = ?", (project_id, session_id)
        )


def _tree(store: SQLiteStore) -> None:
    """root → child → grandchild, and a sibling of root."""
    store.create_project("p_root", "Root", ".raiker/projects/root")
    store.create_project("p_child", "Child", ".raiker/projects/child", parent_id="p_root")
    store.create_project("p_grand", "Grand", ".raiker/projects/grand", parent_id="p_child")
    store.create_project("p_other", "Other", ".raiker/projects/other")


class TestMoveRefusals:
    def test_a_project_cannot_be_its_own_parent(self, service: DashboardService) -> None:
        _tree(service.store)
        result = service.move_project("p_root", "p_root", OWNER)
        assert not result.ok
        assert result.reason_code == "project_move_into_itself"

    def test_a_project_cannot_move_into_its_own_descendant(self, service: DashboardService) -> None:
        _tree(service.store)
        for descendant in ("p_child", "p_grand"):
            result = service.move_project("p_root", descendant, OWNER)
            assert not result.ok
            assert result.reason_code == "project_move_into_descendant"
        root = service.store.load_project("p_root")
        assert root is not None and root["parent_id"] is None and root["path"] == "/p_root/"

    def test_an_archived_folder_is_not_a_destination(self, service: DashboardService) -> None:
        _tree(service.store)
        service.store.archive_project("p_other")
        result = service.move_project("p_child", "p_other", OWNER)
        assert result.reason_code == "project_move_into_archived"

    def test_a_valid_move_carries_the_subtree(self, service: DashboardService) -> None:
        _tree(service.store)
        assert service.move_project("p_child", "p_other", OWNER).ok
        grand = service.store.load_project("p_grand")
        assert grand is not None and grand["path"] == "/p_other/p_child/p_grand/"

    def test_the_store_refuses_a_cycle_even_without_the_service(self, workspace: Path) -> None:
        store = SQLiteStore(workspace)
        _tree(store)
        assert not store.move_project("p_root", "p_grand")
        assert not store.move_project("p_root", "p_root")

    def test_an_underscore_in_an_id_is_not_a_wildcard(self, workspace: Path) -> None:
        # `LIKE '/p_a/%'` matches `/pXa/...`; the prefix comparison must not.
        store = SQLiteStore(workspace)
        store.create_project("p_a", "A", ".raiker/projects/a")
        store.create_project("pXa", "Lookalike", ".raiker/projects/lookalike")
        store.archive_project("p_a")
        lookalike = store.load_project("pXa")
        assert lookalike is not None and lookalike["is_archived"] == 0
        assert store.subtree_project_ids("p_a") == ["p_a"]

    def test_route_answers_a_cycle_with_409(self, client: TestClient, workspace: Path) -> None:
        headers = _headers(_token(client))
        _tree(SQLiteStore(workspace))
        resp = client.put("/api/projects/p_root/move", json={"parent_id": "p_grand"}, headers=headers)
        assert resp.status_code == 409
        assert resp.json()["detail"]["reason_code"] == "project_move_into_descendant"
        missing = client.put("/api/projects/p_root/move", json={"parent_id": "p_none"}, headers=headers)
        assert missing.status_code == 404


class TestArchiveAndRestore:
    def test_restore_brings_back_what_the_archive_took(self, service: DashboardService) -> None:
        _tree(service.store)
        service.archive_project("p_root", OWNER)
        assert all(service.store.load_project(p)["is_archived"] for p in ("p_root", "p_child", "p_grand"))  # type: ignore[index]
        result = service.restore_project("p_root", OWNER)
        assert result.ok, result.reason_code
        for project_id in ("p_root", "p_child", "p_grand"):
            row = service.store.load_project(project_id)
            assert row is not None and row["is_archived"] == 0 and row["archived_at"] is None

    def test_restore_leaves_a_child_archived_on_its_own(self, service: DashboardService) -> None:
        _tree(service.store)
        service.store.archive_project("p_grand")
        # A different instant, so the two archives are distinguishable.
        with service.store.connect() as connection:
            connection.execute(
                "UPDATE projects SET archived_at = '2000-01-01T00:00:00Z' WHERE project_id = 'p_grand'"
            )
        service.store.archive_project("p_root")
        assert service.restore_project("p_root", OWNER).ok
        grand = service.store.load_project("p_grand")
        child = service.store.load_project("p_child")
        assert child is not None and child["is_archived"] == 0
        assert grand is not None and grand["is_archived"] == 1

    def test_restore_under_an_archived_parent_is_refused_by_name(self, service: DashboardService) -> None:
        _tree(service.store)
        service.store.archive_project("p_root")
        result = service.restore_project("p_child", OWNER)
        assert not result.ok
        assert result.reason_code == "project_parent_archived"

    def test_restore_is_human_only(self, service: DashboardService) -> None:
        _tree(service.store)
        service.store.archive_project("p_root")
        assert service.restore_project("p_root", "ai_principal").reason_code == "principal_not_resolved"

    def test_archiving_the_account_selection_clears_it(self, service: DashboardService) -> None:
        _tree(service.store)
        service.select_project("p_child", OWNER)
        service.archive_project("p_root", OWNER)
        assert service.store.get_active_project() is None

    def test_restore_route(self, client: TestClient, workspace: Path) -> None:
        headers = _headers(_token(client))
        _tree(SQLiteStore(workspace))
        assert client.put("/api/projects/p_root/archive", headers=headers).status_code == 200
        listed = {p["project_id"]: p for p in client.get("/api/projects", headers=headers).json()["projects"]}
        assert listed["p_root"]["is_archived"] is True
        resp = client.put("/api/projects/p_root/restore", headers=headers)
        assert resp.status_code == 200, resp.text
        listed = {p["project_id"]: p for p in client.get("/api/projects", headers=headers).json()["projects"]}
        assert listed["p_root"]["is_archived"] is False
        assert client.put("/api/projects/p_nope/restore", headers=headers).status_code == 404


class TestDeletion:
    def test_preview_counts_what_the_delete_removes(
        self, service: DashboardService, workspace: Path
    ) -> None:
        project_id = service.create_project("Alpha", OWNER).data["project_id"]
        folder = workspace / ".raiker" / "projects" / "alpha"
        (folder / "notes.md").write_text("hello\n", encoding="utf-8")
        (folder / "sub").mkdir()
        (folder / "sub" / "data.bin").write_bytes(b"\x00" * 10)
        service.store.create_session("sess_a", str(workspace))
        _file(service.store, "sess_a", project_id)
        service.store.create_project("p_kid", "Kid", ".raiker/projects/kid", parent_id=project_id)

        result = service.project_deletion_preview(project_id, OWNER)
        assert result.ok, result.reason_code
        preview = result.data["preview"]
        assert preview.root_kind == "managed"
        assert preview.requires_step_up is True
        assert preview.sessions == 1
        assert preview.descendants == 1
        assert preview.folder_files == 2
        assert preview.folder_bytes == len(b"hello\n") + 10
        assert preview.folder_truncated is False

    def test_preview_never_counts_an_attached_folder(
        self, service: DashboardService, tmp_path: Path
    ) -> None:
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_text("mine", encoding="utf-8")
        created = service.create_project("Mine", OWNER, attach_path=str(outside))
        assert created.ok, created.reason_code
        preview = service.project_deletion_preview(created.data["project_id"], OWNER).data["preview"]
        assert preview.root_kind == "attached"
        assert preview.requires_step_up is False
        assert preview.folder_files == 0

    def test_managed_delete_requires_a_step_up(self, client: TestClient, workspace: Path) -> None:
        token = _token(client)
        headers = _headers(token)
        project_id = client.post("/api/projects", json={"name": "Alpha"}, headers=headers).json()["project_id"]
        confirm = {"X-Project-Delete-Confirm": project_id}

        refused = client.delete(f"/api/projects/{project_id}", headers={**headers, **confirm})
        assert refused.status_code == 403
        assert refused.json()["detail"]["reason_code"] == "project_delete_requires_step_up"
        assert (workspace / ".raiker" / "projects" / "alpha").is_dir()

        elevated = _headers(_elevated(workspace, token))
        preview = client.get(f"/api/projects/{project_id}/deletion-preview", headers=elevated)
        assert preview.status_code == 200 and preview.json()["requires_step_up"] is True
        deleted = client.delete(f"/api/projects/{project_id}", headers={**elevated, **confirm})
        assert deleted.status_code == 200, deleted.text
        assert not (workspace / ".raiker" / "projects" / "alpha").exists()

    def test_attached_delete_keeps_the_ordinary_session(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        headers = _headers(_token(client))
        outside = tmp_path / "outside"
        outside.mkdir()
        created = client.post(
            "/api/projects", json={"name": "Mine", "attach_path": str(outside)}, headers=headers
        )
        assert created.status_code == 200, created.text
        project_id = created.json()["project_id"]
        deleted = client.delete(
            f"/api/projects/{project_id}", headers={**headers, "X-Project-Delete-Confirm": project_id}
        )
        assert deleted.status_code == 200, deleted.text
        assert outside.is_dir()


class TestDetailReadModel:
    def test_attachments_resolve_to_files_and_say_when_they_do_not(
        self, service: DashboardService, workspace: Path
    ) -> None:
        project_id = service.create_project("Alpha", OWNER).data["project_id"]
        service.store.save_attachment(
            attachment_id="att_1",
            kind="file",
            filename="brief.pdf",
            media_type="application/pdf",
            sha256="0" * 64,
            data=b"\x00" * 2048,
            owner_principal_id=OWNER,
        )
        with service.store.connect() as connection:
            connection.execute(
                "INSERT INTO project_contexts (project_id, instructions, attachment_ids_json, memory_enabled, memory_mode, updated_at) "
                "VALUES (?, '', '[\"att_1\", \"att_gone\"]', 0, 'inherit', ?)",
                (project_id, utc_now()),
            )
        detail = service.get_project(project_id, owner_principal_id=OWNER)
        assert detail is not None
        by_id = {a.attachment_id: a for a in detail.attachments}
        assert by_id["att_1"].filename == "brief.pdf"
        assert by_id["att_1"].byte_size == 2048
        assert by_id["att_1"].available is True
        assert by_id["att_gone"].available is False
        # Another owner's reading resolves nothing.
        other = service.get_project(project_id, owner_principal_id="principal_someone_else")
        assert other is not None and not any(a.available for a in other.attachments)

    def test_last_activity_is_the_newest_session_update(
        self, service: DashboardService, workspace: Path
    ) -> None:
        project_id = service.create_project("Alpha", OWNER).data["project_id"]
        listed = service.list_projects().projects[0]
        assert listed.last_activity_at is None
        service.store.create_session("sess_a", str(workspace))
        _file(service.store, "sess_a", project_id)
        row = service.store.load_session("sess_a")
        assert row is not None
        listed = service.list_projects().projects[0]
        assert listed.last_activity_at == row["updated_at"]
        detail = service.get_project(project_id)
        assert detail is not None and detail.project.last_activity_at == row["updated_at"]
