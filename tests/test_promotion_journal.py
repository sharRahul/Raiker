# SPDX-License-Identifier: Apache-2.0
"""SB-5 (beta plan) — an Apply can be undone, and a crash part-way is rolled back.

The kill test runs the Apply in a child process that exits hard (``os._exit``:
no ``finally``, no ``except``, exactly what ``SIGKILL`` or a power cut leaves)
after it has written some of the files. The next start's recovery must put the
project back byte for byte.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from raiker.execution.workspaces import (
    WorkspaceError,
    create_task_workspace,
    diff_workspace,
    promote,
    recover_promotions,
    undo_promotion,
)


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "pkg").mkdir(parents=True)
    for index in range(6):
        (project / "pkg" / f"m{index}.py").write_text(f"VALUE = {index}\n", encoding="utf-8")
    (project / "keep.txt").write_text("the owner's file\n", encoding="utf-8")
    (project / "remove_me.txt").write_text("deleted by the change\n", encoding="utf-8")
    return project


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _change(workspace_root: Path) -> None:
    for index in range(6):
        (workspace_root / "pkg" / f"m{index}.py").write_text(f"VALUE = {index * 100}\n", encoding="utf-8")
    (workspace_root / "pkg" / "new_module.py").write_text("NEW = True\n", encoding="utf-8")
    (workspace_root / "new_dir").mkdir()
    (workspace_root / "new_dir" / "added.txt").write_text("added\n", encoding="utf-8")
    (workspace_root / "remove_me.txt").unlink()


def test_a_finished_apply_can_be_undone_exactly(tmp_path: Path) -> None:
    project = _project(tmp_path)
    before = _snapshot(project)
    workspace = create_task_workspace(project, tmp_path / "copies", "task")
    _change(workspace.root)
    journal = tmp_path / "state" / "promotions"
    result = promote(workspace, diff_workspace(workspace), journal_dir=journal, owner="principal_owner")
    assert result.promotion_id.startswith("prm_")
    assert (project / "pkg" / "new_module.py").is_file()
    assert not (project / "remove_me.txt").exists()

    undone = undo_promotion(journal, result.promotion_id, owner="principal_owner")
    assert undone.promotion_id == result.promotion_id
    assert _snapshot(project) == before
    assert not (project / "new_dir").exists(), "a folder the Apply made is removed with it"
    with pytest.raises(WorkspaceError, match="workspace_promotion_not_undoable"):
        undo_promotion(journal, result.promotion_id, owner="principal_owner")


def test_undo_refuses_when_the_owner_changed_a_file_since(tmp_path: Path) -> None:
    project = _project(tmp_path)
    workspace = create_task_workspace(project, tmp_path / "copies", "task")
    _change(workspace.root)
    journal = tmp_path / "state" / "promotions"
    result = promote(workspace, diff_workspace(workspace), journal_dir=journal, owner="principal_owner")
    (project / "pkg" / "m2.py").write_text("VALUE = 'the owner edited this after Apply'\n", encoding="utf-8")
    edited = _snapshot(project)
    with pytest.raises(WorkspaceError, match="workspace_undo_conflict"):
        undo_promotion(journal, result.promotion_id, owner="principal_owner")
    assert _snapshot(project) == edited, "a refused undo touches nothing"


_CHILD = textwrap.dedent(
    """
    import os, sys
    from pathlib import Path
    from raiker.execution import workspaces

    project, copies, journal = (Path(arg) for arg in sys.argv[1:4])
    workspace = workspaces.create_task_workspace(project, copies, "task")
    for index in range(6):
        (workspace.root / "pkg" / f"m{index}.py").write_text(f"VALUE = {index * 100}\\n", encoding="utf-8")
    (workspace.root / "pkg" / "new_module.py").write_text("NEW = True\\n", encoding="utf-8")
    (workspace.root / "remove_me.txt").unlink()

    real_copy = workspaces._copy_file
    copied = {"n": 0}

    def dying_copy(source, target):
        if str(target).endswith(".raiker-promote"):
            copied["n"] += 1
            if copied["n"] == 4:
                os._exit(9)  # after project writes, never during backup
        return real_copy(source, target)

    workspaces._copy_file = dying_copy
    workspaces.promote(workspace, workspaces.diff_workspace(workspace), journal_dir=journal)
    sys.exit(0)
    """
)


def test_a_host_killed_mid_apply_is_rolled_back_on_the_next_start(tmp_path: Path) -> None:
    project = _project(tmp_path)
    before = _snapshot(project)
    journal = tmp_path / "state" / "promotions"
    child = subprocess.run(  # noqa: S603 - this interpreter, a fixed script
        [sys.executable, "-c", _CHILD, str(project), str(tmp_path / "copies"), str(journal)],
        capture_output=True, text=True, timeout=120, cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
    )
    assert child.returncode == 9, child.stderr
    assert _snapshot(project) != before, "the kill must land after some files were written"

    recovered = recover_promotions(journal)
    assert len(recovered) == 1
    assert _snapshot(project) == before, "the project is exactly as it was before the Apply"
    # Recovery is idempotent: a second start finds nothing left to do.
    assert recover_promotions(journal) == []


def test_only_the_owner_who_applied_can_undo_and_ids_cannot_climb_out(tmp_path: Path) -> None:
    project = _project(tmp_path)
    workspace = create_task_workspace(project, tmp_path / "copies", "task")
    _change(workspace.root)
    journal = tmp_path / "state" / "promotions"
    result = promote(workspace, diff_workspace(workspace), journal_dir=journal, owner="principal_owner")
    applied = _snapshot(project)
    with pytest.raises(WorkspaceError, match="workspace_promotion_unknown"):
        undo_promotion(journal, result.promotion_id, owner="principal_someone_else")
    for crafted in ("prm_../../etc", "prm_" + "0" * 23, "../" + result.promotion_id, result.promotion_id + "/.."):
        with pytest.raises(WorkspaceError, match="workspace_promotion_unknown"):
            undo_promotion(journal, crafted, owner="principal_owner")
    assert _snapshot(project) == applied, "a refused undo touches nothing"
    undo_promotion(journal, result.promotion_id, owner="principal_owner")
