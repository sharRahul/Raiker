"""BUG-88 — what the Knowledge Map may see, and what it may copy.

The source picker used to browse the workspace root, so opening it listed
everything under the Raiker installation and offered any of it for indexing.
The boundary is now three things and nothing else: Raiker's own document areas,
folders the owner explicitly granted, and — for a file chosen from the computer
— a copy the owner has separately agreed to.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from raiker.contracts.ids import utc_now
from raiker.contracts.models import User
from raiker.control.dashboard import DashboardService
from raiker.control.knowledge_scope import (
    ARTIFACTS_ROOT_ID,
    DATABASE_ROOT_ID,
    MEMORY_ROOT_ID,
    ScopeError,
    build_roots,
    resolve,
)

OWNER = "principal_owner"


def _service(tmp_path: Path) -> DashboardService:
    service = DashboardService(tmp_path)
    (tmp_path / ".raiker" / "artifacts").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".raiker" / "memory").mkdir(parents=True, exist_ok=True)
    return service


class TestBoundary:
    def test_the_picker_opens_on_named_places_not_on_a_listing(self, tmp_path: Path) -> None:
        # A stray file at the top of the workspace is exactly what used to show
        # up in the picker. Nothing about it should reach the owner now.
        (tmp_path / "unrelated-source-file.py").write_text("x = 1\n", encoding="utf-8")
        view = _service(tmp_path).browse_brain_sources("", owner_principal_id=OWNER)

        assert view["path"] == ""
        assert view["children"] == []
        root_ids = {root["root_id"] for root in view["roots"]}
        assert {ARTIFACTS_ROOT_ID, MEMORY_ROOT_ID, DATABASE_ROOT_ID} <= root_ids

    def test_the_database_is_named_rather_than_offered_as_a_folder(
        self, tmp_path: Path
    ) -> None:
        roots = _service(tmp_path).brain_source_roots(owner_principal_id=OWNER)["roots"]
        database = next(root for root in roots if root["root_id"] == DATABASE_ROOT_ID)
        assert database["browsable"] is False
        # It says what it already holds, so an owner is not left looking for a
        # way to add their chats.
        assert "Chat, Build, Tasks, Schedules" in database["detail"]
        assert database["path"] is None

    def test_the_workspace_root_is_not_addressable(self, tmp_path: Path) -> None:
        service = _service(tmp_path)
        for attempt in [".", "/", "..", "docs", "/etc"]:
            with pytest.raises(ValueError) as raised:
                service.review_brain_source(attempt, owner_principal_id=OWNER)
            assert str(raised.value) in {
                "brain_source_outside_scope",
                "invalid_brain_source_path",
            }

    def test_a_traversal_out_of_a_root_is_refused(self, tmp_path: Path) -> None:
        (tmp_path / "secret.md").write_text("private\n", encoding="utf-8")
        service = _service(tmp_path)
        with pytest.raises(ValueError) as raised:
            service.review_brain_source(
                f"{ARTIFACTS_ROOT_ID}/../../secret.md", owner_principal_id=OWNER
            )
        assert str(raised.value) == "brain_source_outside_scope"

    def test_a_symlink_out_of_a_root_is_not_listed(self, tmp_path: Path) -> None:
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "leak.md").write_text("private\n", encoding="utf-8")
        artifacts = tmp_path / ".raiker" / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        try:
            (artifacts / "escape").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):  # pragma: no cover - platform dependent
            pytest.skip("symlinks unavailable on this platform")
        view = _service(tmp_path).browse_brain_sources(
            ARTIFACTS_ROOT_ID, owner_principal_id=OWNER
        )
        assert [child["name"] for child in view["children"]] == []

    def test_a_root_inside_the_workspace_browses_normally(self, tmp_path: Path) -> None:
        artifacts = tmp_path / ".raiker" / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "notes.md").write_text("# notes\n", encoding="utf-8")
        view = _service(tmp_path).browse_brain_sources(
            ARTIFACTS_ROOT_ID, owner_principal_id=OWNER
        )
        assert [child["path"] for child in view["children"]] == [
            f"{ARTIFACTS_ROOT_ID}/notes.md"
        ]
        assert view["parent"] == ""


    def test_only_this_owners_projects_become_roots(self, tmp_path: Path) -> None:
        """A root list built from every project would offer another account's."""
        service = _service(tmp_path)
        now = utc_now()
        store = service.store
        store.insert_user(User("user_a", "A", None, True, now, now))
        store.insert_user(User("user_b", "B", None, True, now, now))
        store.insert_principal(
            OWNER, "human", "A", delegated_by_user_id="user_a"
        )
        (tmp_path / "mine").mkdir()
        (tmp_path / "theirs").mkdir()
        store.create_project("proj_mine", "Mine", "mine", owner_user_id="user_a")
        store.create_project("proj_theirs", "Theirs", "theirs", owner_user_id="user_b")

        labels = {
            root["label"]
            for root in service.brain_source_roots(owner_principal_id=OWNER)["roots"]
        }
        assert "Project files · Mine" in labels
        assert "Project files · Theirs" not in labels


class TestGrants:
    def test_a_granted_folder_is_readable_where_it_is(self, tmp_path: Path) -> None:
        elsewhere = tmp_path.parent / f"{tmp_path.name}-elsewhere"
        elsewhere.mkdir(exist_ok=True)
        (elsewhere / "research.md").write_text("# research\n", encoding="utf-8")
        service = _service(tmp_path)

        granted = service.grant_brain_source_folder(
            str(elsewhere), owner_principal_id=OWNER
        )
        root_id = granted["root_id"]

        view = service.browse_brain_sources(root_id, owner_principal_id=OWNER)
        assert [child["name"] for child in view["children"]] == ["research.md"]

        review = service.review_brain_source(
            f"{root_id}/research.md", owner_principal_id=OWNER
        )
        assert review["supported_files"] == 1

        service.add_brain_source(f"{root_id}/research.md", owner_principal_id=OWNER)
        # Read where it is: nothing was copied into the workspace.
        assert not (tmp_path / "research.md").exists()
        assert not list((tmp_path / ".raiker" / "artifacts").rglob("research.md"))

    def test_revoking_a_grant_removes_what_was_indexed_under_it(
        self, tmp_path: Path
    ) -> None:
        elsewhere = tmp_path.parent / f"{tmp_path.name}-revoked"
        elsewhere.mkdir(exist_ok=True)
        (elsewhere / "notes.md").write_text("# notes\n", encoding="utf-8")
        service = _service(tmp_path)
        root_id = service.grant_brain_source_folder(
            str(elsewhere), owner_principal_id=OWNER
        )["root_id"]
        service.add_brain_source(f"{root_id}/notes.md", owner_principal_id=OWNER)
        assert service.store.list_brain_sources(OWNER) == [f"{root_id}/notes.md"]

        service.revoke_brain_source_folder(root_id, owner_principal_id=OWNER)

        assert service.store.list_brain_sources(OWNER) == []
        with pytest.raises(ValueError):
            service.browse_brain_sources(root_id, owner_principal_id=OWNER)

    def test_granting_and_revoking_are_in_the_audit_log(self, tmp_path: Path) -> None:
        """Opening a folder to the graph is a governed step, so it is recorded."""
        elsewhere = tmp_path.parent / f"{tmp_path.name}-audited"
        elsewhere.mkdir(exist_ok=True)
        service = _service(tmp_path)
        root_id = service.grant_brain_source_folder(
            str(elsewhere), owner_principal_id=OWNER
        )["root_id"]
        service.revoke_brain_source_folder(root_id, owner_principal_id=OWNER)

        recorded = service.store.list_event_index(limit=50)
        by_type = {str(row["event_type"]): row for row in recorded}
        assert "brain_source_folder_granted" in by_type
        assert "brain_source_folder_revoked" in by_type
        # The audit log is account-scoped, so these reach the page an owner
        # opens to confirm exactly this (FIXED-151).
        visible = {event.event_type for event in service.list_events(user_id="user_a")}
        assert {"brain_source_folder_granted", "brain_source_folder_revoked"} <= visible

    def test_a_relative_or_missing_folder_is_refused_by_name(self, tmp_path: Path) -> None:
        service = _service(tmp_path)
        with pytest.raises(ValueError) as relative:
            service.grant_brain_source_folder("documents", owner_principal_id=OWNER)
        assert str(relative.value) == "brain_grant_requires_absolute_path"
        with pytest.raises(ValueError) as missing:
            service.grant_brain_source_folder(
                str(tmp_path / "nowhere"), owner_principal_id=OWNER
            )
        assert str(missing.value) == "brain_grant_not_found"

    def test_the_runtime_directory_cannot_be_granted(self, tmp_path: Path) -> None:
        service = _service(tmp_path)
        with pytest.raises(ValueError) as raised:
            service.grant_brain_source_folder(
                str(tmp_path / ".raiker"), owner_principal_id=OWNER
            )
        assert str(raised.value) == "brain_grant_is_runtime_directory"

    def test_one_owners_grant_is_not_another_owners_root(self, tmp_path: Path) -> None:
        elsewhere = tmp_path.parent / f"{tmp_path.name}-private"
        elsewhere.mkdir(exist_ok=True)
        service = _service(tmp_path)
        root_id = service.grant_brain_source_folder(
            str(elsewhere), owner_principal_id=OWNER
        )["root_id"]
        with pytest.raises(ValueError):
            service.browse_brain_sources(root_id, owner_principal_id="principal_other")


class TestUploads:
    def test_a_file_is_not_stored_without_consent(self, tmp_path: Path) -> None:
        service = _service(tmp_path)
        content = base64.b64encode(b"# notes\n").decode("ascii")
        with pytest.raises(ValueError) as raised:
            service.upload_brain_source_file(
                "notes.md", content, False, owner_principal_id=OWNER
            )
        assert str(raised.value) == "brain_upload_copy_not_authorised"
        assert not list((tmp_path / ".raiker" / "artifacts").rglob("notes.md"))
        assert service.store.list_brain_sources(OWNER) == []

    def test_consent_stores_one_copy_in_a_place_the_owner_can_find(
        self, tmp_path: Path
    ) -> None:
        service = _service(tmp_path)
        content = base64.b64encode(b"# notes\n").decode("ascii")
        result = service.upload_brain_source_file(
            "notes.md", content, True, owner_principal_id=OWNER
        )
        assert result["stored_copy"] is True
        stored = tmp_path / ".raiker" / "artifacts" / "knowledge-uploads" / "notes.md"
        assert stored.read_text(encoding="utf-8") == "# notes\n"
        assert service.store.list_brain_sources(OWNER) == [result["path"]]
        assert result["path"].startswith(f"{ARTIFACTS_ROOT_ID}/knowledge-uploads/")

    def test_a_second_upload_of_the_same_name_does_not_overwrite_the_first(
        self, tmp_path: Path
    ) -> None:
        service = _service(tmp_path)
        first = service.upload_brain_source_file(
            "notes.md", base64.b64encode(b"first\n").decode("ascii"), True,
            owner_principal_id=OWNER,
        )
        second = service.upload_brain_source_file(
            "notes.md", base64.b64encode(b"second\n").decode("ascii"), True,
            owner_principal_id=OWNER,
        )
        assert first["path"] != second["path"]

    def test_an_unsupported_or_traversing_name_is_refused(self, tmp_path: Path) -> None:
        service = _service(tmp_path)
        content = base64.b64encode(b"data").decode("ascii")
        with pytest.raises(ValueError) as unsupported:
            service.upload_brain_source_file(
                "payload.exe", content, True, owner_principal_id=OWNER
            )
        assert str(unsupported.value) == "brain_upload_unsupported_file_type"
        # A traversing name is neutralised rather than refused: only the base
        # name is used, so the copy lands in the one directory uploads live in.
        escaped = service.upload_brain_source_file(
            "../../escape.md", content, True, owner_principal_id=OWNER
        )
        assert escaped["path"] == f"{ARTIFACTS_ROOT_ID}/knowledge-uploads/escape.md"
        assert not (tmp_path.parent / "escape.md").exists()
        assert (
            tmp_path / ".raiker" / "artifacts" / "knowledge-uploads" / "escape.md"
        ).is_file()


class TestResolveUnit:
    def test_resolution_precedes_containment(self, tmp_path: Path) -> None:
        roots = build_roots(tmp_path.resolve(), [], [])
        with pytest.raises(ScopeError) as raised:
            resolve(roots, f"{ARTIFACTS_ROOT_ID}/../../..")
        assert raised.value.reason == "brain_source_outside_scope"

    def test_an_unknown_root_is_refused_rather_than_guessed(self, tmp_path: Path) -> None:
        roots = build_roots(tmp_path.resolve(), [], [])
        with pytest.raises(ScopeError) as raised:
            resolve(roots, "some-other-place/file.md")
        assert raised.value.reason == "brain_source_outside_scope"
