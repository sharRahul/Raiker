"""Descriptor-bound task-copy I/O survives changes after path authorization."""
from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

import pytest

from raiker.tools import filesystem
from tests.test_task_tree import OWNER, SESSION, _link_directory, _tree, _workspace


@pytest.mark.parametrize("operation", ["read", "write", "scan"])
def test_task_copy_parent_swap_after_resolution_cannot_reach_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str,
) -> None:
    workspace = _workspace(tmp_path)
    authority = _tree(tmp_path, workspace)
    _, copy = authority.tree.registry.acquire(OWNER, SESSION, workspace / "proj")
    outside = workspace / "outside"
    outside.mkdir()
    sentinel = outside / "app.py"
    sentinel.write_text("PRIVATE_SENTINEL", encoding="utf-8")
    name = "resolve_writable_workspace_path" if operation == "write" else "resolve_workspace_path"
    original = getattr(filesystem, name)
    swapped = False

    def resolve_then_swap(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal swapped
        resolved = original(*args, **kwargs)
        if not swapped:
            swapped = True
            (copy.root / "src").rename(copy.root / "old_src")
            _link_directory(copy.root / "src", outside)
        return resolved

    monkeypatch.setattr(filesystem, name, resolve_then_swap)
    try:
        if operation == "read":
            result = filesystem.read_file(workspace, "proj/src/app.py", authority=authority)
        elif operation == "write":
            result = filesystem.write_file_content(workspace, "proj/src/app.py", "changed", authority=authority)
        else:
            result = filesystem.grep_files(workspace, "PRIVATE_SENTINEL", "proj/src", authority=authority)
        assert "PRIVATE_SENTINEL" not in str(result)
    except (filesystem.FilesystemSafetyError, OSError):
        pass
    assert swapped
    assert sentinel.read_text(encoding="utf-8") == "PRIVATE_SENTINEL"


@pytest.mark.parametrize("operation", ["write", "edit", "patch", "read"])
def test_task_copy_hardlink_never_reads_or_truncates_host_inode(tmp_path: Path, operation: str) -> None:
    workspace = _workspace(tmp_path)
    authority = _tree(tmp_path, workspace)
    _, copy = authority.tree.registry.acquire(OWNER, SESSION, workspace / "proj")
    sentinel = tmp_path / "host.txt"
    sentinel.write_text("PRIVATE_SENTINEL\n", encoding="utf-8")
    leaf = copy.root / "src" / "app.py"
    leaf.unlink()
    os.link(sentinel, leaf)
    try:
        if operation == "write":
            result = filesystem.write_file_content(workspace, "proj/src/app.py", "changed", authority=authority)
        elif operation == "edit":
            result = filesystem.replace_text_content(workspace, "proj/src/app.py", "PRIVATE_SENTINEL", "changed", authority=authority)
        elif operation == "patch":
            patch = "--- a/proj/src/app.py\n+++ b/proj/src/app.py\n@@ -1 +1 @@\n-PRIVATE_SENTINEL\n+changed\n"
            result = filesystem.apply_patch_content(workspace, "proj/src/app.py", patch, authority=authority)
        else:
            result = filesystem.read_file(workspace, "proj/src/app.py", authority=authority)
        assert result["status"] == "failed"
        assert "PRIVATE_SENTINEL" not in str(result)
    except (filesystem.FilesystemSafetyError, OSError):
        pass
    assert sentinel.read_text(encoding="utf-8") == "PRIVATE_SENTINEL\n"


@pytest.mark.parametrize("operation", ["write", "edit", "patch"])
def test_late_hardlink_swap_before_commit_never_mutates_host_inode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str,
) -> None:
    from raiker.tools import task_tree_io

    workspace = _workspace(tmp_path)
    authority = _tree(tmp_path, workspace)
    _, copy = authority.tree.registry.acquire(OWNER, SESSION, workspace / "proj")
    sentinel = tmp_path / "host.txt"
    sentinel.write_text("PRIVATE_SENTINEL", encoding="utf-8")
    leaf = copy.root / "src" / "app.py"
    replace = os.replace
    swapped = False

    def swap_then_commit(source, destination, *args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal swapped
        if not swapped and Path(destination).name == "app.py":
            swapped = True
            leaf.unlink()
            os.link(sentinel, leaf)
        return replace(source, destination, *args, **kwargs)

    monkeypatch.setattr(task_tree_io.os, "replace", swap_then_commit)
    if operation == "write":
        result = filesystem.write_file_content(workspace, "proj/src/app.py", "changed\n", authority=authority)
    elif operation == "edit":
        result = filesystem.replace_text_content(workspace, "proj/src/app.py", "print('v1')", "changed", authority=authority)
    else:
        patch = "--- a/proj/src/app.py\n+++ b/proj/src/app.py\n@@ -1 +1 @@\n-print('v1')\n+changed\n"
        result = filesystem.apply_patch_content(workspace, "proj/src/app.py", patch, authority=authority)
    assert result["status"] == "success", result
    assert swapped
    assert sentinel.read_text(encoding="utf-8") == "PRIVATE_SENTINEL"
    assert leaf.read_text(encoding="utf-8") == "changed\n"


def test_task_copy_patch_update_create_delete_preserves_project(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    authority = _tree(tmp_path, workspace)
    patch = (
        "--- a/proj/src/app.py\n+++ b/proj/src/app.py\n@@ -1 +1 @@\n-print('v1')\n+changed\n"
        "--- /dev/null\n+++ b/proj/src/new.py\n@@ -0,0 +1 @@\n+created\n"
    )
    result = filesystem.apply_patch_content(workspace, None, patch, authority=authority)
    assert result["status"] == "success", result
    assert result["paths"] == ["proj/src/app.py", "proj/src/new.py"]
    deletion = "--- a/proj/src/new.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-created\n"
    result = filesystem.apply_patch_content(workspace, None, deletion, authority=authority)
    assert result["status"] == "success", result
    assert (workspace / "proj/src/app.py").read_text(encoding="utf-8") == "print('v1')\n"
    assert not (workspace / "proj/src/new.py").exists()


def test_task_copy_checkpoint_capture_refuses_parent_swap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from raiker.checkpoints.capture import CheckpointCaptureService
    from raiker.storage.sqlite import SQLiteStore

    workspace = _workspace(tmp_path)
    authority = _tree(tmp_path, workspace)
    _, copy = authority.tree.registry.acquire(OWNER, SESSION, workspace / "proj")
    outside = workspace / "outside"
    outside.mkdir()
    (outside / "app.py").write_bytes(b"PRIVATE_SENTINEL")
    resolve = authority.resolve_read

    def swap(*args, **kwargs):  # type: ignore[no-untyped-def]
        answer = resolve(*args, **kwargs)
        (copy.root / "src").rename(copy.root / "old_src")
        _link_directory(copy.root / "src", outside)
        return answer

    monkeypatch.setattr(authority, "resolve_read", swap)
    capture = CheckpointCaptureService(SQLiteStore(workspace), authority=authority)
    try:
        pre = capture.snapshot_path("proj/src/app.py", "file_write_execution")
        assert pre is None or pre.data != b"PRIVATE_SENTINEL"
    except (filesystem.FilesystemSafetyError, OSError):
        pass


@pytest.mark.parametrize("operation", ["read", "write", "scan"])
def test_parent_swap_after_pinning_is_blocked_or_descriptor_anchored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str,
) -> None:
    from raiker.tools import task_tree_io

    workspace = _workspace(tmp_path)
    authority = _tree(tmp_path, workspace)
    _, copy = authority.tree.registry.acquire(OWNER, SESSION, workspace / "proj")
    outside = workspace / "outside"
    outside.mkdir()
    sentinel = outside / "app.py"
    sentinel.write_bytes(b"PRIVATE_SENTINEL")
    pin_parent = task_tree_io._parent
    attempted = False
    blocked = False

    @contextlib.contextmanager
    def pin_then_swap(path, root, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal attempted, blocked
        with pin_parent(path, root, **kwargs) as pinned:
            if not attempted and path.parent == copy.root / "src":
                attempted = True
                try:
                    path.parent.rename(copy.root / "old_src")
                except PermissionError:
                    blocked = True
                else:
                    _link_directory(path.parent, outside)
            yield pinned

    monkeypatch.setattr(task_tree_io, "_parent", pin_then_swap)
    try:
        if operation == "read":
            result = filesystem.read_file(workspace, "proj/src/app.py", authority=authority)
        elif operation == "write":
            result = filesystem.write_file_content(workspace, "proj/src/app.py", "changed", authority=authority)
        else:
            result = filesystem.grep_files(workspace, "PRIVATE_SENTINEL", "proj/src", authority=authority)
        assert "PRIVATE_SENTINEL" not in str(result)
    except (filesystem.FilesystemSafetyError, OSError):
        pass
    assert attempted
    if sys.platform == "win32":
        assert blocked
    assert sentinel.read_bytes() == b"PRIVATE_SENTINEL"


def test_scoped_binary_write_and_checkpoint_capture_are_byte_exact(tmp_path: Path) -> None:
    from raiker.checkpoints.capture import CheckpointCaptureService
    from raiker.storage.sqlite import SQLiteStore
    from raiker.tools import task_tree_io

    workspace = _workspace(tmp_path)
    authority = _tree(tmp_path, workspace)
    resolved = authority.resolve_write("proj/src/binary.dat").path
    data = b"\x00\xff\r\n\n\rbyte-exact\x00"
    assert task_tree_io.write_bytes(resolved, data, authority) == len(data)
    capture = CheckpointCaptureService(SQLiteStore(workspace), authority=authority)
    pre = capture.snapshot_path("proj/src/binary.dat", "file_write_execution")
    assert pre is not None
    assert pre.data == data
    assert pre.size == len(data)
    assert not (workspace / "proj/src/binary.dat").exists()


@pytest.mark.parametrize("host_link", [False, True])
def test_scoped_checkpoint_restore_is_exact_or_refuses_host_hardlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, host_link: bool,
) -> None:
    from types import SimpleNamespace

    from raiker.checkpoints.capture import CheckpointCaptureService
    from raiker.checkpoints.service import CheckpointService
    from raiker.contracts.ids import new_id
    from raiker.execution.commands.backends import native
    from raiker.runtime.executors.tier1_checkpoint import CheckpointRestoreExecutor
    from raiker.storage.sqlite import SQLiteStore
    from raiker.tools import task_tree_io
    from tests.factories import governed_action

    workspace = _workspace(tmp_path)
    payload = b"\x00\xff\r\n\n\rbyte-exact"
    (workspace / "proj/src/blob.dat").write_bytes(payload)
    authority = _tree(tmp_path, workspace)
    monkeypatch.setattr(native, "task_workspace_registry", lambda *_args: authority.tree.registry)
    store = SQLiteStore(workspace)
    store.create_session(SESSION, str(workspace))
    service = CheckpointService(store)
    checkpoint, _ = service.write_turn_checkpoint(session_id=SESSION, turn_id=new_id("turn_"), runtime_state="CLOSED", summary="before", last_event_id=new_id("evt_"))
    with store.connect() as connection:
        connection.execute("UPDATE checkpoints SET created_at = ? WHERE checkpoint_id = ?", ("2000-01-01T00:00:00Z", checkpoint.checkpoint_id))
    resolved = authority.resolve_write("proj/src/blob.dat").path
    capture = CheckpointCaptureService(store, authority=authority)
    pre = capture.snapshot_path("proj/src/blob.dat", "file_write_execution")
    assert pre is not None
    capture.commit(pre, session_id=SESSION, turn_id=new_id("turn_"), action_id=new_id("act_"), principal_id=OWNER)
    task_tree_io.write_bytes(resolved, b"changed", authority)
    sentinel = tmp_path / "sentinel"
    sentinel.write_bytes(b"PRIVATE_SENTINEL")
    if host_link:
        resolved.unlink()
        os.link(sentinel, resolved)
    action = governed_action("checkpoint_restore", principal_id=OWNER, risk_level="medium", arguments={"checkpoint_id": checkpoint.checkpoint_id}, session_id=SESSION)
    result = CheckpointRestoreExecutor(workspace, store, authority).execute(action, SimpleNamespace(principal_id=OWNER))  # type: ignore[arg-type]
    if host_link:
        assert not result.ok
        assert result.reason_code == "restore_file_unsafe"
    else:
        assert result.ok, result
        assert result.artifacts["restored"] == 1
        assert resolved.read_bytes() == payload
    assert sentinel.read_bytes() == b"PRIVATE_SENTINEL"
    assert (workspace / "proj/src/blob.dat").read_bytes() == payload


def test_task_copy_long_paths_keep_scoped_io_and_display_names(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    authority = _tree(tmp_path, workspace)
    relative = "proj/" + "/".join("long_component" for _ in range(18)) + "/new.txt"
    result = filesystem.write_file_content(workspace, relative, "long path content", authority=authority)
    assert result["status"] == "success"
    assert result["path"].replace("\\", "/") == relative
    assert filesystem.read_file(workspace, relative, authority=authority)["text"] == "long path content"
    assert filesystem.grep_files(workspace, "long path content", "proj", authority=authority)["matches"][0]["path"].replace("\\", "/") == relative
