# SPDX-License-Identifier: Apache-2.0
"""Deterministic attacks between Apply's validation and filesystem effects."""
from __future__ import annotations

import errno
import os
import sys
from pathlib import Path

import pytest

from raiker.execution import workspaces
from tests.test_task_workspaces import _project

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux pinned directory handles")


@pytest.mark.parametrize("side", ["copy", "project"])
def test_swapped_parent_cannot_redirect_apply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, side: str,
) -> None:
    project = _project(tmp_path)
    workspace = workspaces.create_task_workspace(project, tmp_path / "copies", "task")
    (workspace.root / "src/app.py").write_text("reviewed edit")
    diff = workspaces.diff_workspace(workspace)
    outside = tmp_path / "private"
    outside.mkdir()
    (outside / "app.py").write_text("private bytes")
    root = workspace.root if side == "copy" else project
    original = workspaces._conflicts

    def swap(*args, **kwargs):  # type: ignore[no-untyped-def]
        conflicts = original(*args, **kwargs)
        (root / "src").rename(root / "held")
        (root / "src").symlink_to(outside, target_is_directory=True)
        return conflicts

    monkeypatch.setattr(workspaces, "_conflicts", swap)
    workspaces.promote(workspace, diff)
    assert (outside / "app.py").read_text() == "private bytes"
    applied = project / ("src" if side == "copy" else "held") / "app.py"
    assert applied.read_text() == "reviewed edit"


@pytest.mark.parametrize("link", ["symlink", "hardlink"])
def test_rollback_replaces_a_planted_leaf_without_truncating_its_referent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, link: str,
) -> None:
    project = _project(tmp_path)
    workspace = workspaces.create_task_workspace(project, tmp_path / "copies", "task")
    (workspace.root / "README.md").write_text("edit")
    (workspace.root / "src/app.py").write_text("edit")
    diff = workspaces.diff_workspace(workspace)
    outside = tmp_path / "private"
    outside.write_text("private bytes")
    original = os.replace
    attacked = False

    def attack(source, target):  # type: ignore[no-untyped-def]
        nonlocal attacked
        if not attacked and str(source).endswith(".raiker-promote"):
            attacked = True
            leaf = project / "README.md"
            leaf.unlink()
            if link == "symlink":
                leaf.symlink_to(outside)
            else:
                os.link(outside, leaf)
            raise OSError("injected storage failure")
        return original(source, target)

    monkeypatch.setattr(workspaces.os, "replace", attack)
    with pytest.raises(OSError, match="injected storage failure"):
        workspaces.promote(workspace, diff)
    assert outside.read_text() == "private bytes"
    assert (project / "README.md").read_text() == "readme\n"
    assert not (project / "README.md").is_symlink()


def test_fifo_substitution_is_refused_without_waiting_for_a_writer(tmp_path: Path) -> None:
    if sys.platform != "linux":
        pytest.skip("Linux FIFO substitution")
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(workspaces.WorkspaceError, match="workspace_path_unsafe"):
        workspaces._copy_file(fifo, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_persistent_enospc_retains_journal_and_recovers_after_space_returns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _project(tmp_path)
    workspace = workspaces.create_task_workspace(project, tmp_path / "copies", "task")
    (workspace.root / "README.md").write_text("first edit")
    (workspace.root / "src/app.py").write_text("second edit")
    diff = workspaces.diff_workspace(workspace)
    journal = tmp_path / "journals"
    original = workspaces._copy_file

    def full_disk(source: Path, target: Path, *, single_link: bool = False) -> str:
        if target.name == ".app.py.raiker-promote" or target.name.endswith(".raiker-restore"):
            raise OSError(errno.ENOSPC, "No space left on device")
        return original(source, target, single_link=single_link)

    with monkeypatch.context() as patch:
        patch.setattr(workspaces, "_copy_file", full_disk)
        with pytest.raises(workspaces.WorkspaceError, match="workspace_rollback_incomplete"):
            workspaces.promote(workspace, diff, journal_dir=journal)
    pending = list(journal.iterdir())
    assert len(pending) == 1
    assert workspaces._read_journal(pending[0])["state"] == "applying"
    assert workspaces.recover_promotions(journal) == [pending[0].name]
    assert (project / "README.md").read_text() == "readme\n"
    assert (project / "src/app.py").read_text() == "print('v1')\n"
