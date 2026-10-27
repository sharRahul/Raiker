"""Manage existing Build worktrees; creation awaits a sandboxed checkout.

Git checkout can run repository-configured smudge filters. Creation is
refused until those filters can be contained. Clean worktree removal retains
its existing checks and never deletes a dirty worktree.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _git(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    from raiker.tools.git import _NO_HOOKS
    from raiker.tools.git import _git as git

    return git(root, [*_NO_HOOKS, *args], timeout=30)


def _failed(reason: str, **detail: Any) -> dict[str, Any]:
    return {"status": "failed", "error": {"type": reason, **detail}}


def _is_work_tree(root: Path) -> bool:
    proc = _git(root, ["rev-parse", "--is-inside-work-tree"])
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def is_linked_worktree(root: Path) -> bool:
    """Whether *root* is a linked worktree rather than a repository's main checkout."""
    git_dir = _git(root, ["rev-parse", "--absolute-git-dir"])
    common = _git(root, ["rev-parse", "--path-format=absolute", "--git-common-dir"])
    if git_dir.returncode != 0 or common.returncode != 0:
        return False
    return Path(git_dir.stdout.strip()).resolve() != Path(common.stdout.strip()).resolve()


def _main_worktree(root: Path) -> Path | None:
    proc = _git(root, ["worktree", "list", "--porcelain"])
    if proc.returncode != 0:
        return None
    for line in proc.stdout.splitlines():
        if line.startswith("worktree "):
            return Path(line[len("worktree ") :].strip()).resolve()
    return None


def create_worktree(workspace_root: str | Path, repo_subpath: str, name: str) -> dict[str, Any]:
    """Refuse checkout until Git filters can run in a native sandbox."""
    return _failed("git_worktree_native_sandbox_required")


def remove_worktree(workspace_root: str | Path, subpath: str) -> dict[str, Any]:
    """Remove a clean linked worktree. Its branch and commits stay; dirty is refused."""
    from raiker.tools.filesystem import resolve_workspace_path
    from raiker.tools.git import current_branch

    workspace = Path(workspace_root).resolve()
    try:
        root = resolve_workspace_path(workspace, subpath or ".")
    except Exception:  # noqa: BLE001
        return _failed("repo_folder_missing")
    if not root.is_dir():
        return _failed("repo_folder_missing")
    if not _is_work_tree(root) or not is_linked_worktree(root):
        return _failed("not_a_task_worktree")
    status = _git(root, ["status", "--porcelain", "--untracked-files=all"])
    if status.returncode != 0:
        return _failed("git_command_failed", command="status")
    if status.stdout.strip():
        return _failed("worktree_has_uncommitted_changes")
    branch = current_branch(root)
    main = _main_worktree(root)
    if main is None:
        return _failed("git_command_failed", command="worktree list")
    proc = _git(main, ["worktree", "remove", str(root)])
    if proc.returncode != 0:
        return _failed("git_command_failed", command="worktree remove")
    return {"status": "success", "branch": branch}
