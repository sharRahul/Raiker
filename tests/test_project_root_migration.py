"""Project roots live only below Raiker's managed project directory."""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.control.dashboard import DashboardService, migrate_project_roots
from raiker.control.knowledge_scope import build_roots
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path)


def test_existing_project_root_moves_without_overwrite(tmp_path: Path, store: SQLiteStore) -> None:
    """Removing the file move would leave a legacy project's files behind."""
    old = tmp_path / "projects" / "alpha"
    old.mkdir(parents=True)
    (old / "notes.txt").write_text("alpha", encoding="utf-8")
    store.create_project("proj_a", "Alpha", "projects/alpha")

    report = migrate_project_roots(tmp_path, store)

    assert report.migrated == ("proj_a",)
    assert (tmp_path / ".raiker" / "projects" / "alpha" / "notes.txt").read_text(
        encoding="utf-8"
    ) == "alpha"
    assert store.load_project("proj_a")["root_subpath"] == ".raiker/projects/alpha"


def test_dashboard_startup_migrates_existing_legacy_project_roots(
    tmp_path: Path, store: SQLiteStore
) -> None:
    """Leaving migration uncalled would strand legacy projects indefinitely."""
    old = tmp_path / "projects" / "alpha"
    old.mkdir(parents=True)
    (old / "notes.txt").write_text("alpha", encoding="utf-8")
    store.create_project("proj_a", "Alpha", "projects/alpha")

    DashboardService(tmp_path)

    assert store.load_project("proj_a")["root_subpath"] == ".raiker/projects/alpha"
    assert (tmp_path / ".raiker" / "projects" / "alpha" / "notes.txt").read_text(
        encoding="utf-8"
    ) == "alpha"


def test_failed_row_update_rolls_back_the_folder_move(
    tmp_path: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A guarded update race must not leave a row pointing at a vanished source."""
    old = tmp_path / "projects" / "alpha"
    old.mkdir(parents=True)
    (old / "notes.txt").write_text("alpha", encoding="utf-8")
    store.create_project("proj_a", "Alpha", "projects/alpha")
    monkeypatch.setattr(store, "update_project_root", lambda *_args, **_kwargs: False)

    report = migrate_project_roots(tmp_path, store)

    assert report.migrated == ()
    assert report.conflicts == ("proj_a",)
    assert (old / "notes.txt").read_text(encoding="utf-8") == "alpha"
    assert not (tmp_path / ".raiker" / "projects" / "alpha").exists()
    assert store.load_project("proj_a")["root_subpath"] == "projects/alpha"


def test_existing_destination_conflict_preserves_legacy_project(tmp_path: Path, store: SQLiteStore) -> None:
    """Replacing an existing managed directory would silently destroy its files."""
    old = tmp_path / "projects" / "alpha"
    old.mkdir(parents=True)
    (old / "notes.txt").write_text("legacy", encoding="utf-8")
    destination = tmp_path / ".raiker" / "projects" / "alpha"
    destination.mkdir(parents=True)
    (destination / "notes.txt").write_text("managed", encoding="utf-8")
    store.create_project("proj_a", "Alpha", "projects/alpha")

    report = migrate_project_roots(tmp_path, store)

    assert report.migrated == ()
    assert report.conflicts == ("proj_a",)
    assert (old / "notes.txt").read_text(encoding="utf-8") == "legacy"
    assert (destination / "notes.txt").read_text(encoding="utf-8") == "managed"
    assert store.load_project("proj_a")["root_subpath"] == "projects/alpha"


def test_migration_is_idempotent_after_a_successful_move(tmp_path: Path, store: SQLiteStore) -> None:
    """Repeating startup migration must not rename an already migrated project."""
    old = tmp_path / "projects" / "alpha"
    old.mkdir(parents=True)
    store.create_project("proj_a", "Alpha", "projects/alpha")

    migrate_project_roots(tmp_path, store)
    report = migrate_project_roots(tmp_path, store)

    assert report.migrated == ()
    assert report.conflicts == ()
    assert report.unchanged == ("proj_a",)


def test_migration_keeps_nested_project_rows_with_their_moved_parent(
    tmp_path: Path, store: SQLiteStore
) -> None:
    """Migrating a child first would make its parent's destination conflict."""
    old = tmp_path / "projects" / "alpha" / "child"
    old.mkdir(parents=True)
    (old / "notes.txt").write_text("child", encoding="utf-8")
    store.create_project("proj_parent", "Alpha", "projects/alpha")
    store.create_project("proj_child", "Child", "projects/alpha/child", parent_id="proj_parent")

    report = migrate_project_roots(tmp_path, store)

    assert set(report.migrated) == {"proj_parent", "proj_child"}
    assert report.conflicts == ()
    assert store.load_project("proj_parent")["root_subpath"] == ".raiker/projects/alpha"
    assert store.load_project("proj_child")["root_subpath"] == ".raiker/projects/alpha/child"
    assert (tmp_path / ".raiker" / "projects" / "alpha" / "child" / "notes.txt").read_text(
        encoding="utf-8"
    ) == "child"


def test_migration_refuses_a_legacy_root_that_escapes_the_workspace(
    tmp_path: Path, store: SQLiteStore
) -> None:
    """Accepting traversal in an old row would move or expose files outside Raiker."""
    store.create_project("proj_bad", "Bad", "projects/../../outside")

    report = migrate_project_roots(tmp_path, store)

    assert report.conflicts == ("proj_bad",)
    assert store.load_project("proj_bad")["root_subpath"] == "projects/../../outside"


def test_knowledge_roots_offer_only_the_stored_managed_project_path(
    tmp_path: Path, store: SQLiteStore
) -> None:
    """Using `.raiker` itself as a root would expose Raiker internals."""
    root = tmp_path / ".raiker" / "projects" / "alpha"
    root.mkdir(parents=True)
    (tmp_path / ".raiker" / "secrets.txt").write_text("not a project file", encoding="utf-8")
    store.create_project("proj_a", "Alpha", ".raiker/projects/alpha")

    roots = build_roots(tmp_path, store.list_projects(), [])

    project_root = next(item for item in roots if item.root_id == "project-proj_a")
    assert project_root.path == root.resolve()
    assert project_root.path != (tmp_path / ".raiker").resolve()

    store.create_project("proj_bad", "Not files", ".raiker/memory")
    store.create_project("proj_container", "All projects", ".raiker/projects")
    store.create_project("proj_legacy_container", "All legacy projects", "projects")
    root_ids = {item.root_id for item in build_roots(tmp_path, store.list_projects(), [])}
    assert "project-proj_bad" not in root_ids
    assert "project-proj_container" not in root_ids
    assert "project-proj_legacy_container" not in root_ids
