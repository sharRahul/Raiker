"""Real Windows sharing-mode regressions, using only disposable test folders."""
from __future__ import annotations

import errno
import os
import sys
from pathlib import Path

import pytest

from raiker.execution import workspaces
from tests.test_task_workspaces import _link_directory, _project


@pytest.mark.skipif(sys.platform != "win32", reason="Windows directory sharing modes")
@pytest.mark.parametrize("side", ["copy", "project", "ancestor"])
def test_apply_pins_directories_against_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, side: str,
) -> None:
    project = _project(tmp_path)
    copy = workspaces.create_task_workspace(project, tmp_path / "copies", "task")
    (copy.root / "src/app.py").write_text("reviewed edit")
    diff = workspaces.diff_workspace(copy)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "app.py").write_text("private bytes")
    victim = (copy.root if side == "copy" else project) / "src"
    if side == "ancestor":
        victim = tmp_path
    original = workspaces._conflicts

    def attack(*args, **kwargs):  # type: ignore[no-untyped-def]
        conflicts = original(*args, **kwargs)
        with pytest.raises(OSError):
            victim.rename(victim.with_name(victim.name + "-moved"))
        return conflicts

    monkeypatch.setattr(workspaces, "_conflicts", attack)
    workspaces.promote(copy, diff)
    assert (outside / "app.py").read_text() == "private bytes"
    assert (project / "src/app.py").read_text() == "reviewed edit"
    # Handles must be closed after Apply; rename works again.
    (project / "src").rename(project / "released")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows reparse reader")
def test_regular_reader_refuses_a_junction_leaf(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    leaf = tmp_path / "leaf"
    _link_directory(leaf, outside)
    with pytest.raises(workspaces.WorkspaceError, match="workspace_path_unsafe"):
        workspaces._regular_reader(leaf)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows reparse-in-place IOCTL")
def test_guarded_empty_parent_cannot_become_a_reparse_point(tmp_path: Path) -> None:
    import ctypes
    from ctypes import wintypes

    from raiker.execution.windows_file_handles import DirectoryPins, _kernel

    outside = tmp_path / "outside"
    outside.mkdir()
    junction = tmp_path / "junction"
    _link_directory(junction, outside)
    parent = tmp_path / "parent"
    parent.mkdir()
    kernel = _kernel()
    kernel.DeviceIoControl.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
    ]
    kernel.DeviceIoControl.restype = wintypes.BOOL
    template = kernel.CreateFileW(str(junction), 0, 7, None, 3, 0x02200000, None)
    buffer = ctypes.create_string_buffer(16_384)
    count = wintypes.DWORD()
    try:
        assert kernel.DeviceIoControl(template, 0x900A8, None, 0, buffer, len(buffer),
                                      ctypes.byref(count), None)
    finally:
        kernel.CloseHandle(template)
    size = count.value
    with DirectoryPins() as pins:
        pins.pin(parent)
        pins.allow_children(parent)
        [guard] = list(parent.glob(".raiker-pin-*"))
        with pytest.raises(OSError):
            guard.unlink()
        with pytest.raises(OSError):
            parent.rename(tmp_path / "moved")
        attacker = kernel.CreateFileW(str(parent), 0x40000000, 7, None, 3, 0x02200000, None)
        assert attacker != ctypes.c_void_p(-1).value
        try:
            assert not kernel.DeviceIoControl(attacker, 0x900A4, buffer, size, None, 0,
                                              ctypes.byref(count), None)
            assert ctypes.get_last_error() == 145  # type: ignore[attr-defined]  # ERROR_DIR_NOT_EMPTY
        finally:
            kernel.CloseHandle(attacker)
        (parent / "old").write_text("old")
        (parent / "stage").write_text("new")
        os.replace(parent / "stage", parent / "old")
        assert (parent / "old").read_text() == "new"
        (parent / "old").unlink()
    assert list(parent.iterdir()) == []  # guards delete on close
    assert list(outside.iterdir()) == []


@pytest.mark.skipif(sys.platform != "win32", reason="Windows exclusive leaf handles")
def test_staging_writer_exclusively_creates_without_touching_an_existing_leaf(tmp_path: Path) -> None:
    from raiker.execution.windows_file_handles import fresh_writer

    leaf = tmp_path / "leaf"
    leaf.write_text("old")
    with pytest.raises(OSError):
        fresh_writer(leaf)
    assert leaf.read_text() == "old"
    with fresh_writer(tmp_path / "stage") as writer:
        writer.write(b"new")
    assert (tmp_path / "stage").read_text() == "new"
    assert leaf.read_text() == "old"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Undo/recovery directory pins")
@pytest.mark.parametrize("operation", ["undo", "recover"])
def test_restoration_keeps_parent_pinned_until_original_is_restored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str,
) -> None:
    project = _project(tmp_path)
    copy = workspaces.create_task_workspace(project, tmp_path / "copies", "task")
    (copy.root / "src/app.py").write_text("edit")
    journal_dir = tmp_path / "journals"
    applied = workspaces.promote(copy, workspaces.diff_workspace(copy),
                                 journal_dir=journal_dir, owner="owner")
    if operation == "recover":
        directory = journal_dir / applied.promotion_id
        record = workspaces._read_journal(directory)
        record["state"] = "applying"
        workspaces._write_journal(directory, record)
    original = workspaces._restore_file

    def attack(backup: Path, target: Path) -> None:
        with pytest.raises(OSError):
            (project / "src").rename(project / "moved")
        original(backup, target)

    monkeypatch.setattr(workspaces, "_restore_file", attack)
    if operation == "undo":
        workspaces.undo_promotion(journal_dir, applied.promotion_id, owner="owner")
    else:
        assert workspaces.recover_promotions(journal_dir) == [applied.promotion_id]
    assert (project / "src/app.py").read_text() == "print('v1')\n"
    assert not list(project.rglob(".raiker-pin-*"))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows rollback under persistent ENOSPC")
def test_failed_windows_rollback_retains_backups_until_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _project(tmp_path)
    copy = workspaces.create_task_workspace(project, tmp_path / "copies", "task")
    (copy.root / "README.md").write_text("first")
    (copy.root / "src/app.py").write_text("second")
    diff = workspaces.diff_workspace(copy)
    journal_dir = tmp_path / "journals"
    original = workspaces._copy_file

    def full_disk(source: Path, target: Path, *, single_link: bool = False) -> str:
        if target.name == ".app.py.raiker-promote" or target.name.endswith(".raiker-restore"):
            raise OSError(errno.ENOSPC, "No space left on device")
        return original(source, target, single_link=single_link)

    with monkeypatch.context() as patch:
        patch.setattr(workspaces, "_copy_file", full_disk)
        with pytest.raises(workspaces.WorkspaceError, match="workspace_rollback_incomplete"):
            workspaces.promote(copy, diff, journal_dir=journal_dir)
    [directory] = list(journal_dir.iterdir())
    assert workspaces._read_journal(directory)["state"] == "applying"
    assert workspaces.recover_promotions(journal_dir) == [directory.name]
    assert (project / "README.md").read_text() == "readme\n"
    assert (project / "src/app.py").read_text() == "print('v1')\n"


@pytest.mark.parametrize("platform", ["darwin", "unsupported"])
def test_unpinned_platform_refuses_promotion_before_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str,
) -> None:
    project = _project(tmp_path)
    copy = workspaces.create_task_workspace(project, tmp_path / "copies", "task")
    (copy.root / "src/app.py").write_text("edit")
    diff = workspaces.diff_workspace(copy)
    monkeypatch.setattr(workspaces.sys, "platform", platform)
    with pytest.raises(workspaces.WorkspaceError, match="workspace_promotion_handles_unavailable"):
        workspaces.promote(copy, diff)
    assert (project / "src/app.py").read_text() == "print('v1')\n"
    assert not list(project.rglob("*.raiker-promote"))
