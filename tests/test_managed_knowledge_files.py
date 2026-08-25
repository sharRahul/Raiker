from __future__ import annotations

import hashlib
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from typing import Any

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.contracts.models import User
from raiker.control.dashboard import DashboardService
from raiker.knowledge.files import (
    ManagedFileError,
    ManagedFileRecord,
    ManagedFileScope,
    ManagedFileService,
)
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"


def _import_from_separate_process(
    workspace: str, payload: bytes, start: Any, results: Any
) -> None:
    store = SQLiteStore(workspace)
    try:
        start.wait()
        record = ManagedFileService(workspace, store).import_file(
            ManagedFileScope("memory"), "shared.bin", payload, "application/octet-stream", OWNER
        )
    except Exception as exc:
        results.put(("error", type(exc).__name__, str(exc)))
    else:
        results.put(("ok", record.content_hash, ""))


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


def test_dashboard_created_project_imports_under_the_managed_projects_root(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    dashboard = DashboardService(workspace)
    created = dashboard.create_project("Alpha", OWNER)

    assert created.ok, created.reason_code
    record = ManagedFileService(workspace, dashboard.store).import_file(
        ManagedFileScope("project", str(created.data["project_id"])),
        "notes/plan.txt",
        b"alpha",
        "text/plain",
        OWNER,
    )

    assert record.project_id == created.data["project_id"]
    assert (workspace / ".raiker/projects/alpha/notes/plan.txt").read_bytes() == b"alpha"
    assert not (workspace / "projects/alpha/notes/plan.txt").exists()


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


def test_memory_import_requires_an_existing_owner(tmp_path: Path, owner_store: SQLiteStore) -> None:
    with pytest.raises(ManagedFileError, match="managed_file_scope_not_found"):
        ManagedFileService(tmp_path, owner_store).import_file(
            ManagedFileScope("memory"), "notes/private.txt", b"private", "text/plain", "unknown"
        )


def test_rejects_a_runtime_root_symlink_that_leaves_the_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    try:
        (workspace / ".raiker").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - platform dependent
        pytest.skip("symlinks unavailable on this platform")
    store = SQLiteStore(workspace)
    now = utc_now()
    store.insert_user(User("user_owner", "Owner", None, True, now, now))
    store.insert_principal(OWNER, "human", "Owner", delegated_by_user_id="user_owner")

    with pytest.raises(ManagedFileError, match="managed_file_path_outside_scope"):
        ManagedFileService(workspace, store).import_file(
            ManagedFileScope("memory"), "notes/private.txt", b"private", "text/plain", OWNER
        )
    assert not (outside / "memory-files/notes/private.txt").exists()


def test_rejects_a_projects_root_symlink_that_leaves_the_workspace(
    tmp_path: Path, owner_store: SQLiteStore
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    projects_root = tmp_path / ".raiker/projects"
    try:
        projects_root.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - platform dependent
        pytest.skip("symlinks unavailable on this platform")
    owner_store.create_project(
        "project_alpha", "Alpha", ".raiker/projects/alpha", owner_user_id="user_owner"
    )

    with pytest.raises(ManagedFileError, match="managed_file_path_outside_scope"):
        ManagedFileService(tmp_path, owner_store).import_file(
            ManagedFileScope("project", "project_alpha"), "notes/private.txt", b"private", "text/plain", OWNER
        )
    assert not (outside / "alpha/notes/private.txt").exists()


def test_concurrent_imports_leave_one_active_record_with_matching_bytes(
    tmp_path: Path, owner_store: SQLiteStore
) -> None:
    service = ManagedFileService(tmp_path, owner_store)
    start = Barrier(3)
    payloads = (b"first" * 400_000, b"second" * 400_000)

    def import_one(payload: bytes) -> ManagedFileRecord | ManagedFileError:
        start.wait()
        try:
            return service.import_file(ManagedFileScope("memory"), "same.bin", payload, "application/octet-stream", OWNER)
        except ManagedFileError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(import_one, payload) for payload in payloads]
        start.wait()
    results = [future.result() for future in futures]

    records = owner_store.list_managed_files(OWNER)
    assert len(records) == 1
    stored = (tmp_path / ".raiker/memory-files/same.bin").read_bytes()
    assert hashlib.sha256(stored).hexdigest() == records[0]["content_hash"]
    assert sum(not isinstance(result, ManagedFileError) for result in results) == 1


def test_multiprocess_imports_leave_one_active_record_with_matching_bytes(
    tmp_path: Path, owner_store: SQLiteStore
) -> None:
    context = multiprocessing.get_context("spawn")
    start = context.Barrier(3)
    results = context.Queue()
    payloads = (b"first" * 400_000, b"second" * 400_000)
    workers = [
        context.Process(
            target=_import_from_separate_process,
            args=(str(tmp_path), payload, start, results),
        )
        for payload in payloads
    ]
    for worker in workers:
        worker.start()
    start.wait()
    outcomes = [results.get(timeout=20) for _ in workers]
    for worker in workers:
        worker.join(timeout=20)
        assert worker.exitcode == 0

    records = owner_store.list_managed_files(OWNER)
    assert len(records) == 1
    stored = (tmp_path / ".raiker/memory-files/shared.bin").read_bytes()
    assert hashlib.sha256(stored).hexdigest() == records[0]["content_hash"]
    assert sum(outcome[0] == "ok" for outcome in outcomes) == 1
    assert all(outcome[0] == "ok" or outcome[1] == "ManagedFileError" for outcome in outcomes)


def test_failed_catalogue_insert_leaves_a_recoverable_destination(
    tmp_path: Path, owner_store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = ManagedFileService(tmp_path, owner_store)
    original_insert = owner_store.insert_managed_file

    def reject_insert(**_kwargs: object) -> None:
        raise RuntimeError("simulated_catalogue_failure")

    monkeypatch.setattr(owner_store, "insert_managed_file", reject_insert)
    with pytest.raises(RuntimeError, match="simulated_catalogue_failure"):
        service.import_file(ManagedFileScope("memory"), "retry.bin", b"first", "application/octet-stream", OWNER)
    assert not (tmp_path / ".raiker/memory-files/retry.bin").exists()

    monkeypatch.setattr(owner_store, "insert_managed_file", original_insert)
    retried = service.import_file(
        ManagedFileScope("memory"), "retry.bin", b"second", "application/octet-stream", OWNER
    )

    assert owner_store.list_managed_files(OWNER) == [owner_store.get_managed_file(retried.file_id, OWNER)]
    assert (tmp_path / ".raiker/memory-files/retry.bin").read_bytes() == b"second"


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


def test_reimport_after_retirement_replaces_the_retired_original(
    tmp_path: Path, owner_store: SQLiteStore
) -> None:
    service = ManagedFileService(tmp_path, owner_store)
    first = service.import_file(ManagedFileScope("memory"), "notes.txt", b"first", "text/plain", OWNER)
    assert owner_store.retire_managed_file(first.file_id, OWNER) is True

    second = service.import_file(ManagedFileScope("memory"), "notes.txt", b"second", "text/plain", OWNER)

    assert second.file_id != first.file_id
    assert second.content_hash == hashlib.sha256(b"second").hexdigest()
    assert owner_store.get_managed_file(first.file_id, OWNER)["content_hash"] == hashlib.sha256(b"first").hexdigest()
    assert (tmp_path / ".raiker/memory-files/notes.txt").read_bytes() == b"second"
