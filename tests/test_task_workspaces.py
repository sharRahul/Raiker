"""Disposable task workspaces: the original project changes only by promotion."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from raiker.execution import workspaces
from raiker.execution.workspaces import (
    WorkspaceError,
    create_task_workspace,
    diff_workspace,
    discard,
    promote,
    sweep_stale,
)


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "app.py").write_text("print('v1')\n", encoding="utf-8")
    (project / "README.md").write_text("readme\n", encoding="utf-8")
    (project / ".git").mkdir()
    (project / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    (project / ".raiker").mkdir()
    (project / ".raiker" / "state.db").write_text("secret state", encoding="utf-8")
    return project


def _link_directory(link: Path, target: Path) -> None:
    """A real directory link: a junction on Windows (no privilege), else a symlink."""
    if sys.platform == "win32":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=True,
            capture_output=True,
        )
    else:
        link.symlink_to(target, target_is_directory=True)


def test_the_copy_excludes_repository_metadata_and_raiker_state(tmp_path: Path) -> None:
    project = _project(tmp_path)
    workspace = create_task_workspace(project, tmp_path / "sandboxes", "task_1")

    assert sorted(workspace.manifest) == ["README.md", "src/app.py"]
    assert not (workspace.root / ".git").exists()
    assert not (workspace.root / ".raiker").exists()
    assert (workspace.root / "src" / "app.py").read_text(encoding="utf-8") == "print('v1')\n"
    assert workspace.root.parent == (tmp_path / "sandboxes").resolve()
    assert workspace.root.name.startswith("task_1-") and workspace.root.name != "task_1-"


def test_work_in_the_copy_leaves_the_project_unchanged_until_promotion(tmp_path: Path) -> None:
    project = _project(tmp_path)
    workspace = create_task_workspace(project, tmp_path / "sandboxes", "task")
    (workspace.root / "src" / "app.py").write_text("print('v2')\n", encoding="utf-8")
    (workspace.root / "README.md").unlink()
    (workspace.root / "src" / "new.py").write_text("x = 1\n", encoding="utf-8")

    diff = diff_workspace(workspace)

    assert diff.created == ("src/new.py",)
    assert diff.modified == ("src/app.py",)
    assert diff.deleted == ("README.md",)
    assert (project / "src" / "app.py").read_text(encoding="utf-8") == "print('v1')\n"
    assert (project / "README.md").exists()
    assert not (project / "src" / "new.py").exists()

    result = promote(workspace, diff)

    assert result.modified == ("src/app.py",)
    assert (project / "src" / "app.py").read_text(encoding="utf-8") == "print('v2')\n"
    assert (project / "src" / "new.py").read_text(encoding="utf-8") == "x = 1\n"
    assert not (project / "README.md").exists()
    assert (project / ".raiker" / "state.db").read_text(encoding="utf-8") == "secret state"


def test_a_directory_link_in_the_project_is_skipped_not_followed(tmp_path: Path) -> None:
    project = _project(tmp_path)
    private = tmp_path / "private"
    private.mkdir()
    (private / "id_ed25519").write_text("PRIVATE KEY", encoding="utf-8")
    _link_directory(project / "keys", private)

    workspace = create_task_workspace(project, tmp_path / "sandboxes", "task")

    assert "keys" in workspace.skipped
    assert not (workspace.root / "keys").exists()
    assert all(not name.startswith("keys/") for name in workspace.manifest)


def test_a_hard_link_is_copied_so_the_original_inode_is_never_written(tmp_path: Path) -> None:
    project = _project(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("owner data", encoding="utf-8")
    os.link(outside, project / "linked.txt")

    workspace = create_task_workspace(project, tmp_path / "sandboxes", "task")
    (workspace.root / "linked.txt").write_text("overwritten by task", encoding="utf-8")

    assert outside.read_text(encoding="utf-8") == "owner data"


def test_links_and_protected_names_the_task_creates_are_never_promotable(tmp_path: Path) -> None:
    project = _project(tmp_path)
    workspace = create_task_workspace(project, tmp_path / "sandboxes", "task")
    _link_directory(workspace.root / "escape", tmp_path)
    (workspace.root / ".git").mkdir()
    (workspace.root / ".git" / "hooks").mkdir()
    (workspace.root / ".git" / "hooks" / "pre-commit").write_text("evil", encoding="utf-8")

    diff = diff_workspace(workspace)

    assert ("escape", "link") in diff.rejected
    assert (".git", "protected_path") in diff.rejected
    assert diff.created == ()
    promote(workspace, diff)
    assert not (project / "escape").exists()
    assert not (project / ".git" / "hooks").exists()


def test_an_owner_edit_after_the_snapshot_stops_the_whole_promotion(tmp_path: Path) -> None:
    project = _project(tmp_path)
    workspace = create_task_workspace(project, tmp_path / "sandboxes", "task")
    (workspace.root / "src" / "app.py").write_text("task version\n", encoding="utf-8")
    (workspace.root / "src" / "new.py").write_text("new\n", encoding="utf-8")
    (project / "src" / "app.py").write_text("owner version\n", encoding="utf-8")

    with pytest.raises(WorkspaceError) as refused:
        promote(workspace, diff_workspace(workspace))

    assert refused.value.reason_code == "workspace_promotion_conflict"
    assert (project / "src" / "app.py").read_text(encoding="utf-8") == "owner version\n"
    assert not (project / "src" / "new.py").exists()


def test_a_path_the_owner_created_meanwhile_is_a_conflict_not_an_overwrite(tmp_path: Path) -> None:
    project = _project(tmp_path)
    workspace = create_task_workspace(project, tmp_path / "sandboxes", "task")
    (workspace.root / "notes.md").write_text("task\n", encoding="utf-8")
    (project / "notes.md").write_text("owner\n", encoding="utf-8")

    with pytest.raises(WorkspaceError, match="workspace_promotion_conflict"):
        promote(workspace, diff_workspace(workspace))
    assert (project / "notes.md").read_text(encoding="utf-8") == "owner\n"


def test_a_failure_part_way_restores_every_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path)
    workspace = create_task_workspace(project, tmp_path / "sandboxes", "task")
    (workspace.root / "README.md").write_text("changed\n", encoding="utf-8")
    (workspace.root / "src" / "app.py").write_text("changed\n", encoding="utf-8")
    (workspace.root / "zz" / "deep").mkdir(parents=True)
    (workspace.root / "zz" / "deep" / "created.txt").write_text("new\n", encoding="utf-8")
    real_replace = os.replace
    calls = {"count": 0}

    def failing_replace(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        calls["count"] += 1
        if calls["count"] == 3:
            raise OSError("disk full")
        real_replace(source, target)

    monkeypatch.setattr(workspaces.os, "replace", failing_replace)
    with pytest.raises(OSError, match="disk full"):
        promote(workspace, diff_workspace(workspace))

    assert (project / "README.md").read_text(encoding="utf-8") == "readme\n"
    assert (project / "src" / "app.py").read_text(encoding="utf-8") == "print('v1')\n"
    assert not (project / "zz").exists()
    assert not list(project.rglob("*.raiker-promote"))


def test_the_effective_authority_can_refuse_a_path_before_anything_is_written(tmp_path: Path) -> None:
    project = _project(tmp_path)
    workspace = create_task_workspace(project, tmp_path / "sandboxes", "task")
    (workspace.root / "README.md").write_text("changed\n", encoding="utf-8")
    (workspace.root / "ci.yml").write_text("new\n", encoding="utf-8")

    with pytest.raises(WorkspaceError, match="workspace_promotion_not_permitted:ci.yml"):
        promote(workspace, diff_workspace(workspace), allowed=lambda path: path != "ci.yml")
    assert (project / "README.md").read_text(encoding="utf-8") == "readme\n"


def test_promotion_never_writes_through_a_link_in_the_project(tmp_path: Path) -> None:
    project = _project(tmp_path)
    workspace = create_task_workspace(project, tmp_path / "sandboxes", "task")
    (workspace.root / "out").mkdir()
    (workspace.root / "out" / "file.txt").write_text("task\n", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _link_directory(project / "out", elsewhere)

    with pytest.raises(WorkspaceError, match="workspace_path_unsafe"):
        promote(workspace, diff_workspace(workspace))
    assert not (elsewhere / "file.txt").exists()


def test_quotas_refuse_and_leave_no_partial_copy(tmp_path: Path) -> None:
    project = _project(tmp_path)
    base = tmp_path / "sandboxes"

    with pytest.raises(WorkspaceError, match="workspace_file_quota_exceeded"):
        create_task_workspace(project, base, "task", max_files=1)
    with pytest.raises(WorkspaceError, match="workspace_storage_quota_exceeded"):
        create_task_workspace(project, base, "task", max_bytes=5)
    assert list(base.iterdir()) == []


def test_the_base_may_not_be_inside_the_project(tmp_path: Path) -> None:
    project = _project(tmp_path)
    with pytest.raises(WorkspaceError, match="workspace_base_inside_source"):
        create_task_workspace(project, project / "sandboxes", "task")


def test_discard_and_crash_sweep_remove_only_task_copies(tmp_path: Path) -> None:
    project = _project(tmp_path)
    base = tmp_path / "sandboxes"
    kept = create_task_workspace(project, base, "fresh")
    stale = create_task_workspace(project, base, "stale")
    (stale.root / "src" / "app.py").chmod(0o444)
    old = 1_000_000_000
    os.utime(stale.root, (old, old))

    removed = sweep_stale(base, older_than_seconds=3600)

    assert removed == [stale.root]
    assert kept.root.exists()
    discard(kept)
    assert not kept.root.exists()
    assert (project / "src" / "app.py").exists()
