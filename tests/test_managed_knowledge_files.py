from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from raiker.contracts.ids import utc_now
from raiker.contracts.models import User
from raiker.knowledge.files import ManagedFileError, ManagedFileScope, ManagedFileService
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"


@pytest.fixture()
def owner_store(tmp_path: Path) -> SQLiteStore:
    store = SQLiteStore(tmp_path)
    now = utc_now()
    store.insert_user(User("user_owner", "Owner", None, True, now, now))
    store.insert_principal(OWNER, "human", "Owner", delegated_by_user_id="user_owner")
    return store


def test_memory_accepts_unknown_binary_type(tmp_path: Path, owner_store: SQLiteStore) -> None:
    record = ManagedFileService(tmp_path, owner_store).import_file(
        ManagedFileScope("memory"),
        "archive/data.custom",
        b"\x00\x01payload",
        "application/x-custom",
        OWNER,
    )

    assert record.relative_path == "archive/data.custom"
    assert record.media_type == "application/x-custom"
    assert record.size_bytes == 9
    assert record.content_hash == hashlib.sha256(b"\x00\x01payload").hexdigest()
    assert (tmp_path / ".raiker/memory-files/archive/data.custom").read_bytes() == b"\x00\x01payload"


@pytest.mark.parametrize("path", ["../escape.txt", "/absolute.txt", "folder/../../escape.txt"])
def test_import_rejects_paths_outside_managed_root(
    tmp_path: Path, owner_store: SQLiteStore, path: str
) -> None:
    with pytest.raises(ManagedFileError, match="managed_file_path_outside_scope"):
        ManagedFileService(tmp_path, owner_store).import_file(
            ManagedFileScope("memory"), path, b"x", "text/plain", OWNER
        )


def test_import_rejects_symlink_escape_from_managed_root(
    tmp_path: Path, owner_store: SQLiteStore
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    managed_root = tmp_path / ".raiker/memory-files"
    managed_root.mkdir(parents=True)
    try:
        (managed_root / "escape").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - platform dependent
        pytest.skip("symlinks unavailable on this platform")

    with pytest.raises(ManagedFileError, match="managed_file_path_outside_scope"):
        ManagedFileService(tmp_path, owner_store).import_file(
            ManagedFileScope("memory"), "escape/private.bin", b"x", "application/octet-stream", OWNER
        )


def test_project_file_uses_the_projects_managed_root(
    tmp_path: Path, owner_store: SQLiteStore
) -> None:
    owner_store.create_project(
        "project_alpha", "Alpha", ".raiker/projects/alpha", owner_user_id="user_owner"
    )

    record = ManagedFileService(tmp_path, owner_store).import_file(
        ManagedFileScope("project", "project_alpha"), "notes/plan.txt", b"alpha", "text/plain", OWNER
    )

    assert record.project_id == "project_alpha"
    assert (tmp_path / ".raiker/projects/alpha/notes/plan.txt").read_bytes() == b"alpha"


def test_project_import_requires_an_owner_with_access_to_the_project(
    tmp_path: Path, owner_store: SQLiteStore
) -> None:
    owner_store.create_project(
        "project_alpha", "Alpha", ".raiker/projects/alpha", owner_user_id="user_owner"
    )

    with pytest.raises(ManagedFileError, match="managed_file_scope_not_found"):
        ManagedFileService(tmp_path, owner_store).import_file(
            ManagedFileScope("project", "project_alpha"),
            "notes/private.txt",
            b"private",
            "text/plain",
            "principal_unknown",
        )


def test_catalogue_lifecycle_is_owner_scoped(tmp_path: Path, owner_store: SQLiteStore) -> None:
    service = ManagedFileService(tmp_path, owner_store)
    imported = service.import_file(
        ManagedFileScope("memory"), "notes.txt", b"first", "text/plain", OWNER
    )

    assert owner_store.get_managed_file(imported.file_id, OWNER)["index_state"] == "queued"
    assert owner_store.get_managed_file(imported.file_id, "principal_other") is None
    assert owner_store.set_managed_file_index_state(imported.file_id, OWNER, "ready") is True
    assert owner_store.get_managed_file(imported.file_id, OWNER)["index_state"] == "ready"
    assert owner_store.retire_managed_file(imported.file_id, OWNER) is True
    assert owner_store.list_managed_files(OWNER) == []
    assert owner_store.get_managed_file(imported.file_id, OWNER)["retired_at"] is not None
