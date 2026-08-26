"""Indexing a folder Raiker does not own.

The catalogue already knows how to project a managed file into chunks. What is
new is that the bytes were never imported: they are the owner's, on their disk,
changing behind Raiker's back. So the reconcile pass reads and decides, and the
two things it must never do are write into the folder and delete anything in
it — including while retiring a revision, which for a managed file *does* remove
the bytes.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService
from raiker.knowledge.reconcile import IGNORED_DIRECTORY_NAMES, reconcile_attached_root

OWNER = "principal_owner"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


class _Attached:
    def __init__(self, service: DashboardService, project_id: str, root: Path) -> None:
        self.service = service
        self.store = service.store
        self.project_id = project_id
        self.root = root

    @property
    def row(self) -> dict[str, Any]:
        row = self.store.load_project(self.project_id)
        assert row is not None
        return row


def _attach(workspace: Path, external: Path, name: str = "Alpha") -> _Attached:
    external.mkdir(parents=True, exist_ok=True)
    service = DashboardService(workspace)
    created = service.create_project(name, OWNER)
    attached = service.attach_project_folder(
        created.data["project_id"], str(external), OWNER
    )
    assert attached.ok, attached.reason_code
    return _Attached(service, created.data["project_id"], external.resolve())


@pytest.fixture
def attached(tmp_path: Path, workspace: Path) -> _Attached:
    return _attach(workspace, tmp_path / "repo")


def _paths(attached: _Attached) -> set[str]:
    return {
        str(row["relative_path"])
        for row in attached.store.list_managed_files(
            OWNER, scope_kind="project", project_id=attached.project_id
        )
    }


class TestFirstScan:
    def test_first_scan_indexes_only_readable_files(
        self, workspace: Path, attached: _Attached
    ) -> None:
        (attached.root / "handbook.md").write_text(
            "The alpha deployment checklist.", encoding="utf-8"
        )
        (attached.root / "logo.bin").write_bytes(b"\x00\x01")
        (attached.root / "node_modules").mkdir()
        (attached.root / "node_modules" / "dep.md").write_text("ignored", encoding="utf-8")

        report = reconcile_attached_root(workspace, attached.store, attached.row, OWNER)

        paths = _paths(attached)
        assert "handbook.md" in paths
        assert "node_modules/dep.md" not in paths
        assert "logo.bin" not in paths
        assert report.indexed >= 1

    def test_every_ignored_directory_stays_out_of_the_catalogue(
        self, workspace: Path, attached: _Attached
    ) -> None:
        for name in IGNORED_DIRECTORY_NAMES:
            (attached.root / name).mkdir()
            (attached.root / name / "note.md").write_text("hidden", encoding="utf-8")
        (attached.root / "kept.md").write_text("kept", encoding="utf-8")

        reconcile_attached_root(workspace, attached.store, attached.row, OWNER)

        assert _paths(attached) == {"kept.md"}

    def test_a_nested_file_keeps_its_posix_relative_path(
        self, workspace: Path, attached: _Attached
    ) -> None:
        (attached.root / "docs" / "guides").mkdir(parents=True)
        (attached.root / "docs" / "guides" / "a.md").write_text("alpha", encoding="utf-8")

        reconcile_attached_root(workspace, attached.store, attached.row, OWNER)

        assert _paths(attached) == {"docs/guides/a.md"}


class TestIncremental:
    def test_an_unchanged_file_is_not_reindexed(
        self, workspace: Path, attached: _Attached
    ) -> None:
        (attached.root / "a.md").write_text("alpha", encoding="utf-8")
        reconcile_attached_root(workspace, attached.store, attached.row, OWNER)

        second = reconcile_attached_root(workspace, attached.store, attached.row, OWNER)

        assert second.indexed == 0
        assert second.updated == 0
        assert second.retired == 0

    def test_a_modified_file_is_reindexed_and_the_old_revision_retires(
        self, workspace: Path, attached: _Attached
    ) -> None:
        target = attached.root / "a.md"
        target.write_text("alpha deployment", encoding="utf-8")
        reconcile_attached_root(workspace, attached.store, attached.row, OWNER)

        target.write_text("beta rollout", encoding="utf-8")
        stamp = time.time_ns() + 2_000_000_000
        os.utime(target, ns=(stamp, stamp))
        report = reconcile_attached_root(workspace, attached.store, attached.row, OWNER)

        assert report.updated == 1
        assert (
            attached.store.search_managed_file_chunks("deployment", owner_principal_id=OWNER)
            == []
        )
        assert attached.store.search_managed_file_chunks("rollout", owner_principal_id=OWNER)

    def test_a_deleted_file_retires_its_projections(
        self, workspace: Path, attached: _Attached
    ) -> None:
        target = attached.root / "a.md"
        target.write_text("alpha deployment", encoding="utf-8")
        reconcile_attached_root(workspace, attached.store, attached.row, OWNER)

        target.unlink()
        report = reconcile_attached_root(workspace, attached.store, attached.row, OWNER)

        assert report.retired == 1
        assert (
            attached.store.search_managed_file_chunks("deployment", owner_principal_id=OWNER)
            == []
        )


class TestReadOnly:
    def test_reconcile_never_writes_into_the_attached_folder(
        self, workspace: Path, attached: _Attached
    ) -> None:
        (attached.root / "a.md").write_text("alpha", encoding="utf-8")
        before = sorted(p.relative_to(attached.root).as_posix() for p in attached.root.rglob("*"))

        reconcile_attached_root(workspace, attached.store, attached.row, OWNER)

        after = sorted(p.relative_to(attached.root).as_posix() for p in attached.root.rglob("*"))
        assert after == before

    def test_retiring_a_revision_does_not_delete_the_owners_file(
        self, workspace: Path, attached: _Attached
    ) -> None:
        # A managed file's retirement removes its bytes, because Raiker wrote
        # them. These bytes are the owner's, and reindexing a changed file must
        # not take the file with it.
        target = attached.root / "a.md"
        target.write_text("alpha", encoding="utf-8")
        reconcile_attached_root(workspace, attached.store, attached.row, OWNER)

        target.write_text("beta", encoding="utf-8")
        stamp = time.time_ns() + 2_000_000_000
        os.utime(target, ns=(stamp, stamp))
        reconcile_attached_root(workspace, attached.store, attached.row, OWNER)

        assert target.read_text(encoding="utf-8") == "beta"

    def test_a_missing_root_reconciles_to_nothing(
        self, workspace: Path, attached: _Attached
    ) -> None:
        (attached.root / "a.md").write_text("alpha", encoding="utf-8")
        reconcile_attached_root(workspace, attached.store, attached.row, OWNER)
        attached.service.detach_project_folder(attached.project_id, OWNER)

        report = reconcile_attached_root(workspace, attached.store, attached.row, OWNER)

        assert (report.indexed, report.updated, report.retired) == (0, 0, 0)


class TestBuildBoundary:
    def test_build_reaches_its_attached_project_and_not_another(
        self, tmp_path: Path, workspace: Path
    ) -> None:
        alpha = _attach(workspace, tmp_path / "alpha-repo", name="Alpha")
        beta = _attach(workspace, tmp_path / "beta-repo", name="Beta")
        (alpha.root / "notes.md").write_text("the alpha rollout runbook", encoding="utf-8")
        (beta.root / "notes.md").write_text("the beta rollout runbook", encoding="utf-8")
        reconcile_attached_root(workspace, alpha.store, alpha.row, OWNER)
        reconcile_attached_root(workspace, beta.store, beta.row, OWNER)

        hits = alpha.store.search_managed_file_chunks(
            "rollout runbook", owner_principal_id=OWNER, project_ids=(alpha.project_id,)
        )

        assert hits
        assert {str(hit["project_id"]) for hit in hits} == {alpha.project_id}
