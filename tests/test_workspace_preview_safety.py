"""Untrusted task-copy entries must not make previews read host files."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from raiker.execution import workspaces
from tests.test_task_workspaces import _link_directory, _project


def test_copy_hardlink_is_rejected_by_diff_preview_and_apply(tmp_path: Path) -> None:
    project = _project(tmp_path)
    copy = workspaces.create_task_workspace(project, tmp_path / "copies", "task")
    secret = tmp_path / "private.txt"
    secret.write_text("PRIVATE_SENTINEL")
    leaf = copy.root / "src/app.py"
    leaf.unlink()
    os.link(secret, leaf)
    diff = workspaces.diff_workspace(copy)
    assert ("src/app.py", "hardlink") in diff.rejected
    assert "src/app.py" not in diff.modified
    forged = workspaces.WorkspaceDiff((), ("src/app.py",), (), ())
    with pytest.raises(workspaces.WorkspaceError, match="workspace_path_unsafe"):
        workspaces.file_diff(copy, forged, "src/app.py")
    with pytest.raises(workspaces.WorkspaceError, match="workspace_path_unsafe"):
        workspaces.promote(copy, forged)
    assert secret.read_text() == "PRIVATE_SENTINEL"
    assert (project / "src/app.py").read_text() == "print('v1')\n"


@pytest.mark.parametrize("operation", ["scan", "preview"])
def test_copy_parent_swap_cannot_leak_private_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str,
) -> None:
    project = _project(tmp_path)
    copy = workspaces.create_task_workspace(project, tmp_path / "copies", "task")
    (copy.root / "src/app.py").write_text("reviewed task text")
    secret = tmp_path / "private"
    secret.mkdir()
    (secret / "app.py").write_text("PRIVATE_SENTINEL")
    original = workspaces._regular_reader
    attacked = False

    def trigger(path: Path) -> None:
        nonlocal attacked
        if not attacked and path.name == "app.py" and path != project / "src/app.py":
            attacked = True
            try:
                (copy.root / "src").rename(copy.root / "held")
            except OSError:
                assert sys.platform == "win32"
            else:
                _link_directory(copy.root / "src", secret)

    def attack(path: Path, **kwargs):  # type: ignore[no-untyped-def]
        if kwargs.get("single_link"):
            trigger(path)
        return original(path, **kwargs)

    monkeypatch.setattr(workspaces, "_regular_reader", attack)
    original_side = workspaces._diff_side

    def diff_side(path: Path, **kwargs):  # type: ignore[no-untyped-def]
        if kwargs.get("single_link"):
            trigger(path)
        return original_side(path, **kwargs)

    monkeypatch.setattr(workspaces, "_diff_side", diff_side)
    if operation == "scan":
        diff = workspaces.diff_workspace(copy)
        assert diff.modified == ("src/app.py",)
    else:
        diff = workspaces.WorkspaceDiff((), ("src/app.py",), (), ())
        preview = workspaces.file_diff(copy, diff, "src/app.py")
        assert preview is not None
        assert "PRIVATE_SENTINEL" not in preview.text
        assert "reviewed task text" in preview.text
    assert attacked


def test_copy_bytes_changed_after_diff_cannot_be_promoted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _project(tmp_path)
    copy = workspaces.create_task_workspace(project, tmp_path / "copies", "task")
    (copy.root / "README.md").write_text("reviewed first edit")
    (copy.root / "src/app.py").write_text("reviewed code")
    diff = workspaces.diff_workspace(copy)
    original = workspaces._copy_file

    def changed_after_check(source: Path, target: Path, *, single_link: bool = False) -> str:
        if target.name == ".app.py.raiker-promote":
            (copy.root / "src/app.py").write_text("unseen code")
        return original(source, target, single_link=single_link)

    monkeypatch.setattr(workspaces, "_copy_file", changed_after_check)
    with pytest.raises(workspaces.WorkspaceError, match="workspace_review_stale"):
        workspaces.promote(copy, diff)
    assert (project / "README.md").read_text() == "readme\n"
    assert (project / "src/app.py").read_text() == "print('v1')\n"


def test_hardlink_swapped_in_after_review_is_never_copied_into_the_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _project(tmp_path)
    copy = workspaces.create_task_workspace(project, tmp_path / "copies", "task")
    (copy.root / "src/app.py").write_text("reviewed code")
    diff = workspaces.diff_workspace(copy)
    secret = tmp_path / "private.txt"
    secret.write_text("PRIVATE_SENTINEL")
    original = workspaces._copy_file

    def swap(source: Path, target: Path, *, single_link: bool = False) -> str:
        if target.name == ".app.py.raiker-promote":
            leaf = copy.root / "src/app.py"
            leaf.unlink()
            try:
                os.link(secret, leaf)
            except OSError as exc:
                # A strict Windows copy-parent pin can block the hardlink
                # insertion itself. Leave the removed copy entry absent, as
                # the sandbox would, and let the actual reader refuse it.
                assert sys.platform == "win32" and exc.winerror == 32
        return original(source, target, single_link=single_link)

    monkeypatch.setattr(workspaces, "_copy_file", swap)
    with pytest.raises(workspaces.WorkspaceError, match="workspace_path_unsafe|workspace_review_stale"):
        workspaces.promote(copy, diff)
    assert (project / "src/app.py").read_text() == "print('v1')\n"
    assert secret.read_text() == "PRIVATE_SENTINEL"
    assert not list(project.rglob("*.raiker-promote"))


def test_promotion_cannot_silently_skip_a_missing_copy_digest(tmp_path: Path) -> None:
    project = _project(tmp_path)
    copy = workspaces.create_task_workspace(project, tmp_path / "copies", "task")
    (copy.root / "src/app.py").write_text("not bound to a review")
    unbound = workspaces.WorkspaceDiff((), ("src/app.py",), (), ())
    with pytest.raises(workspaces.WorkspaceError, match="workspace_review_required"):
        workspaces.promote(copy, unbound)
    assert (project / "src/app.py").read_text() == "print('v1')\n"
