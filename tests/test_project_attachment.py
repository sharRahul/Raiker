"""Attaching a folder the owner already has as a project's root.

The grant is the record of "a folder the owner allowed", so attaching is a
grant plus a pointer, not a second permission system. What this suite defends
is the difference the pointer makes: a folder already reachable inside the
workspace cannot be attached (one file would get two names), one folder serves
one project, revoking the grant takes the root away, and deleting an attached
project deletes nothing on disk.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.control.knowledge_scope import grant_root_id
from raiker.control.project_roots import authority_for_project, resolve_project_root
from raiker.tools.filesystem import FilesystemSafetyError

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


def _root_of(service: DashboardService, project_id: str):
    return resolve_project_root(
        service.store.load_project(project_id),
        service.store.list_brain_source_grants(OWNER),
        service.workspace_root,
    )


class TestAttach:
    def test_attaching_an_existing_folder_makes_it_the_root(
        self, tmp_path: Path, service: DashboardService
    ) -> None:
        external = tmp_path / "repo"
        (external / "src").mkdir(parents=True)
        created = service.create_project("Alpha", OWNER)

        result = service.attach_project_folder(created.data["project_id"], str(external), OWNER)

        assert result.ok, result.reason_code
        root = _root_of(service, created.data["project_id"])
        assert root.kind == "attached"
        assert root.path == external.resolve()
        assert root.writable is True
        assert root.missing is False

    def test_attaching_read_only_leaves_the_folder_unwritable(
        self, tmp_path: Path, service: DashboardService
    ) -> None:
        external = tmp_path / "repo"
        external.mkdir()
        created = service.create_project("Alpha", OWNER)

        result = service.attach_project_folder(
            created.data["project_id"], str(external), OWNER, writable=False
        )

        assert result.ok, result.reason_code
        root = _root_of(service, created.data["project_id"])
        assert root.writable is False

    def test_attaching_a_folder_inside_the_workspace_is_refused(
        self, workspace: Path, service: DashboardService
    ) -> None:
        inside = workspace / "inside"
        inside.mkdir()
        created = service.create_project("Alpha", OWNER)

        result = service.attach_project_folder(created.data["project_id"], str(inside), OWNER)

        assert result.ok is False
        assert result.reason_code == "attach_path_inside_workspace"

    def test_attaching_a_folder_already_attached_is_refused(
        self, tmp_path: Path, service: DashboardService
    ) -> None:
        external = tmp_path / "repo"
        external.mkdir()
        first = service.create_project("Alpha", OWNER)
        second = service.create_project("Beta", OWNER)
        service.attach_project_folder(first.data["project_id"], str(external), OWNER)

        result = service.attach_project_folder(second.data["project_id"], str(external), OWNER)

        assert result.ok is False
        assert result.reason_code == "attach_root_already_used"

    def test_reattaching_the_same_folder_to_the_same_project_is_allowed(
        self, tmp_path: Path, service: DashboardService
    ) -> None:
        external = tmp_path / "repo"
        external.mkdir()
        created = service.create_project("Alpha", OWNER)
        service.attach_project_folder(created.data["project_id"], str(external), OWNER)

        result = service.attach_project_folder(
            created.data["project_id"], str(external), OWNER, writable=False
        )

        assert result.ok, result.reason_code
        assert _root_of(service, created.data["project_id"]).writable is False

    def test_attaching_a_missing_folder_is_refused(
        self, tmp_path: Path, service: DashboardService
    ) -> None:
        created = service.create_project("Alpha", OWNER)

        result = service.attach_project_folder(
            created.data["project_id"], str(tmp_path / "nope"), OWNER
        )

        assert result.ok is False
        assert result.reason_code == "brain_grant_not_found"

    def test_attaching_is_human_only(self, tmp_path: Path, service: DashboardService) -> None:
        external = tmp_path / "repo"
        external.mkdir()
        created = service.create_project("Alpha", OWNER)
        service.store.insert_principal("principal_agent", "ai_agent", "Agent")

        result = service.attach_project_folder(
            created.data["project_id"], str(external), "principal_agent"
        )

        assert result.ok is False
        assert result.reason_code == "not_authorized_human"


class TestCreateWithAttachment:
    def test_creating_with_a_folder_attaches_it(
        self, tmp_path: Path, service: DashboardService
    ) -> None:
        external = tmp_path / "repo"
        external.mkdir()

        created = service.create_project("Alpha", OWNER, attach_path=str(external))

        assert created.ok, created.reason_code
        assert _root_of(service, created.data["project_id"]).path == external.resolve()

    def test_creating_with_a_refused_folder_fails_identically(
        self, workspace: Path, service: DashboardService
    ) -> None:
        inside = workspace / "inside"
        inside.mkdir()

        created = service.create_project("Alpha", OWNER, attach_path=str(inside))

        assert created.ok is False
        assert created.reason_code == "attach_path_inside_workspace"
        assert list(service.list_projects().projects) == []


class TestDetach:
    def test_detaching_leaves_the_grant_alone(
        self, tmp_path: Path, service: DashboardService
    ) -> None:
        external = tmp_path / "repo"
        external.mkdir()
        created = service.create_project("Alpha", OWNER)
        service.attach_project_folder(created.data["project_id"], str(external), OWNER)

        result = service.detach_project_folder(created.data["project_id"], OWNER)

        assert result.ok, result.reason_code
        assert _root_of(service, created.data["project_id"]).missing is True
        assert [g["root_id"] for g in service.store.list_brain_source_grants(OWNER)] == [
            grant_root_id(external.resolve())
        ]


class TestDeletion:
    def test_deleting_an_attached_project_removes_no_file(
        self, tmp_path: Path, service: DashboardService
    ) -> None:
        external = tmp_path / "repo"
        external.mkdir()
        (external / "keep.txt").write_text("keep", encoding="utf-8")
        created = service.create_project("Alpha", OWNER)
        service.attach_project_folder(created.data["project_id"], str(external), OWNER)

        assert service.delete_project(created.data["project_id"], OWNER, confirm=True).ok

        assert (external / "keep.txt").read_text(encoding="utf-8") == "keep"
        assert external.is_dir()

    def test_deleting_a_managed_project_still_removes_its_root(
        self, workspace: Path, service: DashboardService
    ) -> None:
        created = service.create_project("Alpha", OWNER)
        root = workspace / ".raiker" / "projects" / "alpha"
        (root / "gone.txt").write_text("gone", encoding="utf-8")

        assert service.delete_project(created.data["project_id"], OWNER, confirm=True).ok

        assert not root.exists()


class TestRevocation:
    def test_revoking_a_grant_detaches_its_project(
        self, tmp_path: Path, service: DashboardService
    ) -> None:
        external = tmp_path / "repo"
        external.mkdir()
        created = service.create_project("Alpha", OWNER)
        service.attach_project_folder(created.data["project_id"], str(external), OWNER)

        service.revoke_brain_source_folder(
            grant_root_id(external.resolve()), owner_principal_id=OWNER
        )

        assert _root_of(service, created.data["project_id"]).missing is True

    def test_a_deleted_folder_reads_as_missing(
        self, tmp_path: Path, service: DashboardService
    ) -> None:
        external = tmp_path / "repo"
        external.mkdir()
        created = service.create_project("Alpha", OWNER)
        service.attach_project_folder(created.data["project_id"], str(external), OWNER)

        external.rmdir()

        root = _root_of(service, created.data["project_id"])
        assert root.missing is True
        assert root.path == external.resolve()


class TestAuthorityForProject:
    def test_a_writable_attachment_permits_writing_there(
        self, tmp_path: Path, service: DashboardService
    ) -> None:
        external = tmp_path / "repo"
        external.mkdir()
        created = service.create_project("Alpha", OWNER)
        service.attach_project_folder(created.data["project_id"], str(external), OWNER)

        authority = authority_for_project(
            service.store.load_project(created.data["project_id"]),
            service.store.list_brain_source_grants(OWNER),
            service.workspace_root,
        )

        assert authority.resolve_write(external / "src/main.py").writable is True

    def test_a_read_only_attachment_refuses_writing_there(
        self, tmp_path: Path, service: DashboardService
    ) -> None:
        external = tmp_path / "repo"
        external.mkdir()
        created = service.create_project("Alpha", OWNER)
        service.attach_project_folder(
            created.data["project_id"], str(external), OWNER, writable=False
        )

        authority = authority_for_project(
            service.store.load_project(created.data["project_id"]),
            service.store.list_brain_source_grants(OWNER),
            service.workspace_root,
        )

        assert authority.resolve_read(external / "a.md").root_id != "workspace"
        with pytest.raises(FilesystemSafetyError, match="root_not_writable"):
            authority.resolve_write(external / "a.md")

    def test_a_managed_project_keeps_workspace_only_confinement(
        self, tmp_path: Path, service: DashboardService
    ) -> None:
        created = service.create_project("Alpha", OWNER)

        authority = authority_for_project(
            service.store.load_project(created.data["project_id"]),
            service.store.list_brain_source_grants(OWNER),
            service.workspace_root,
        )

        with pytest.raises(FilesystemSafetyError, match="outside_workspace"):
            authority.resolve_read(tmp_path / "elsewhere.md")
