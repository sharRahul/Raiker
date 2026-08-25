"""Project roots live only below Raiker's managed project directory."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import raiker.control.dashboard as dashboard
from raiker.cli.principal_resolver import bootstrap_owner
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


def test_failed_row_reservation_leaves_the_legacy_root_coherent(
    tmp_path: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A guarded database race must not publish or move a stale project root."""
    old = tmp_path / "projects" / "alpha"
    old.mkdir(parents=True)
    (old / "notes.txt").write_text("alpha", encoding="utf-8")
    store.create_project("proj_a", "Alpha", "projects/alpha")
    monkeypatch.setattr(
        store,
        "publish_project_root_atomic",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("database_locked")),
    )

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


def test_destination_claim_race_never_overwrites_or_strands_the_legacy_root(
    tmp_path: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A POSIX-style rename replacement must not destroy a concurrent destination."""
    old = tmp_path / "projects" / "alpha"
    old.mkdir(parents=True)
    (old / "notes.txt").write_text("legacy", encoding="utf-8")
    destination = tmp_path / ".raiker" / "projects" / "alpha"
    store.create_project("proj_a", "Alpha", "projects/alpha")
    original_mkdir = Path.mkdir
    claimed = False

    def claim_destination(path: Path, *args: object, **kwargs: object) -> None:
        nonlocal claimed
        if path == destination and not claimed:
            claimed = True
            original_mkdir(path, *args, **kwargs)
            (path / "racer.txt").write_text("do not replace", encoding="utf-8")
            raise FileExistsError(path)
        original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", claim_destination)

    report = migrate_project_roots(tmp_path, store)

    assert report.migrated == ()
    assert report.conflicts == ("proj_a",)
    assert (old / "notes.txt").read_text(encoding="utf-8") == "legacy"
    assert (destination / "racer.txt").read_text(encoding="utf-8") == "do not replace"
    assert store.load_project("proj_a")["root_subpath"] == "projects/alpha"

    monkeypatch.undo()
    shutil.rmtree(destination)
    resumed = migrate_project_roots(tmp_path, store)
    assert resumed.migrated == ("proj_a",)
    assert (destination / "notes.txt").read_text(encoding="utf-8") == "legacy"


def test_incomplete_owned_publication_resumes_without_replacing_files(
    tmp_path: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A crash after claiming the final root must leave an owned, resumable reservation."""
    old = tmp_path / "projects" / "alpha"
    old.mkdir(parents=True)
    (old / "notes.txt").write_text("legacy", encoding="utf-8")
    store.create_project("proj_a", "Alpha", "projects/alpha")
    original_copy = dashboard._copy_project_tree_resuming

    def fail_after_copy(source: Path, destination: Path) -> None:
        original_copy(source, destination)
        raise OSError("injected_after_final_copy")

    monkeypatch.setattr(dashboard, "_copy_project_tree_resuming", fail_after_copy)

    failed = migrate_project_roots(tmp_path, store)

    assert failed.conflicts == ("proj_a",)
    assert (old / "notes.txt").read_text(encoding="utf-8") == "legacy"
    assert store.load_project("proj_a")["root_subpath"] == "projects/alpha"

    monkeypatch.undo()
    resumed = migrate_project_roots(tmp_path, store)
    assert resumed.migrated == ("proj_a",)
    assert (tmp_path / ".raiker" / "projects" / "alpha" / "notes.txt").read_text(
        encoding="utf-8"
    ) == "legacy"


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


def test_managed_container_symlink_cannot_delete_runtime_data(tmp_path: Path) -> None:
    """Resolving `.raiker/projects` through `.raiker` must not make memory deletable."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    store = SQLiteStore(workspace)
    memory = workspace / ".raiker" / "memory"
    memory.mkdir(parents=True)
    (memory / "keep.txt").write_text("keep", encoding="utf-8")
    container = workspace / ".raiker" / "projects"
    try:
        container.symlink_to(workspace / ".raiker", target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - host dependent
        pytest.skip("symlinks unavailable")
    store.create_project(
        "proj_memory", "Memory", ".raiker/projects/memory", owner_user_id="owner"
    )

    result = DashboardService(workspace).delete_project("proj_memory", "principal_owner", confirm=True)

    assert result.reason_code == "project_root_escapes_workspace"
    assert (memory / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert store.load_project("proj_memory", "owner") is not None


def test_legacy_container_symlink_cannot_migrate_runtime_data(tmp_path: Path) -> None:
    """Resolving legacy `projects` through `.raiker` must not move memory."""
    store = SQLiteStore(tmp_path)
    memory = tmp_path / ".raiker" / "memory"
    memory.mkdir(parents=True)
    (memory / "keep.txt").write_text("keep", encoding="utf-8")
    container = tmp_path / "projects"
    try:
        container.symlink_to(tmp_path / ".raiker", target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - host dependent
        pytest.skip("symlinks unavailable")
    store.create_project("proj_memory", "Memory", "projects/memory")

    report = migrate_project_roots(tmp_path, store)

    assert report.conflicts == ("proj_memory",)
    assert (memory / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert store.load_project("proj_memory")["root_subpath"] == "projects/memory"


def test_source_container_swap_before_publication_cannot_copy_runtime_data(
    tmp_path: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The source container must be revalidated after the database lock is acquired."""
    old = tmp_path / "projects" / "alpha"
    old.mkdir(parents=True)
    (old / "notes.txt").write_text("legacy", encoding="utf-8")
    runtime_source = tmp_path / ".raiker" / "alpha"
    runtime_source.mkdir(parents=True)
    (runtime_source / "secret.txt").write_text("secret", encoding="utf-8")
    store.create_project("proj_a", "Alpha", "projects/alpha")
    original_publish = store.publish_project_root_atomic

    def swap_then_publish(*args: object, **kwargs: object) -> bool:
        old.parent.rename(tmp_path / "projects-before-swap")
        try:
            (tmp_path / "projects").symlink_to(tmp_path / ".raiker", target_is_directory=True)
        except (OSError, NotImplementedError):  # pragma: no cover - host dependent
            pytest.skip("symlinks unavailable")
        return original_publish(*args, **kwargs)

    monkeypatch.setattr(store, "publish_project_root_atomic", swap_then_publish)

    report = migrate_project_roots(tmp_path, store)

    assert report.conflicts == ("proj_a",)
    assert store.load_project("proj_a")["root_subpath"] == "projects/alpha"
    assert not (tmp_path / ".raiker" / "projects" / "alpha").exists()
    assert (runtime_source / "secret.txt").read_text(encoding="utf-8") == "secret"


def test_container_symlinks_are_not_knowledge_map_roots(tmp_path: Path) -> None:
    """A container symlink must not turn Raiker memory into project knowledge."""
    runtime = tmp_path / ".raiker"
    memory = runtime / "memory"
    memory.mkdir(parents=True)
    (memory / "secret.txt").write_text("secret", encoding="utf-8")
    managed = runtime / "projects"
    legacy = tmp_path / "projects"
    try:
        managed.symlink_to(runtime, target_is_directory=True)
        legacy.symlink_to(runtime, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - host dependent
        pytest.skip("symlinks unavailable")

    roots = build_roots(
        tmp_path,
        [
            {"project_id": "managed", "name": "Managed", "root_subpath": ".raiker/projects/memory"},
            {"project_id": "legacy", "name": "Legacy", "root_subpath": "projects/memory"},
        ],
        [],
    )

    root_ids = {root.root_id for root in roots}
    assert "project-managed" not in root_ids
    assert "project-legacy" not in root_ids
