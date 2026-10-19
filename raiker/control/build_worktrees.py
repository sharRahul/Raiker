"""BR-03 — a separate worktree, on an owned branch, for each concurrent piece of Build work.

Two Build conversations writing into one checkout change each other's files,
branch and diff without either saying so. The answer BR-03 asks for is a
worktree per task: its own folder, its own branch, the same repository.

A task worktree here is:

* a new branch under ``raiker/`` — owned by the task, never an existing branch,
  never the one already checked out somewhere else;
* a folder next to the repository's own, ``<repo>.worktrees/<name>``, so it is
  inside the workspace whenever the repository is;
* connected as its own Build repository, so it has its own target fingerprint,
  its own Changes, and its own outcome.

Removing one removes only a **clean** linked worktree. Uncommitted work in it is
the owner's and is refused (``worktree_has_uncommitted_changes``); its branch
and commits are always kept, so nothing the task did is lost. The repository's
main checkout is never touched by either operation, and repository hooks never
run (the same ``core.hooksPath`` override every governed git write uses).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

WORKTREE_BRANCH_PREFIX = "raiker/"
WORKTREE_DIR_SUFFIX = ".worktrees"
_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,47}$")


def _git(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    from raiker.tools.git import _NO_HOOKS
    from raiker.tools.git import _git as git

    return git(root, [*_NO_HOOKS, *args], timeout=30)


def _failed(reason: str, **detail: Any) -> dict[str, Any]:
    return {"status": "failed", "error": {"type": reason, **detail}}


def _is_work_tree(root: Path) -> bool:
    proc = _git(root, ["rev-parse", "--is-inside-work-tree"])
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _toplevel(root: Path) -> Path | None:
    proc = _git(root, ["rev-parse", "--show-toplevel"])
    return Path(proc.stdout.strip()).resolve() if proc.returncode == 0 and proc.stdout.strip() else None


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
    """Add ``<repo>.worktrees/<name>`` on a new ``raiker/<name>`` branch from HEAD."""
    from raiker.tools.filesystem import resolve_workspace_path

    workspace = Path(workspace_root).resolve()
    clean = (name or "").strip().lower()
    if not _NAME.fullmatch(clean) or ".." in clean or clean.endswith((".", ".lock")):
        return _failed("invalid_worktree_name")
    try:
        repo = resolve_workspace_path(workspace, repo_subpath or ".")
    except Exception:  # noqa: BLE001 — outside the workspace is not a repository here
        return _failed("repo_folder_missing")
    if not repo.is_dir():
        return _failed("repo_folder_missing")
    if repo == workspace:
        # Its sibling would be outside the workspace, and a worktree inside it
        # would show up as untracked files in the very checkout it isolates.
        return _failed("worktree_needs_subfolder_repository")
    if not _is_work_tree(repo) or _toplevel(repo) != repo:
        return _failed("not_a_git_repository")
    branch = f"{WORKTREE_BRANCH_PREFIX}{clean}"
    if _git(repo, ["check-ref-format", "--branch", branch]).returncode != 0:
        return _failed("invalid_worktree_name")
    if _git(repo, ["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"]).returncode == 0:
        return _failed("branch_exists", branch=branch)
    head = _git(repo, ["rev-parse", "--short", "HEAD"])
    if head.returncode != 0:
        return _failed("repository_has_no_commits")
    target = repo.parent / f"{repo.name}{WORKTREE_DIR_SUFFIX}" / clean
    if target.exists():
        return _failed("worktree_path_exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    proc = _git(repo, ["worktree", "add", "-b", branch, str(target), "HEAD"])
    if proc.returncode != 0:
        text = (proc.stderr or proc.stdout).lower()
        if "already checked out" in text or "already used by worktree" in text:
            return _failed("branch_in_use", branch=branch)
        return _failed("git_command_failed", command="worktree add")
    return {
        "status": "success",
        "local_subpath": target.relative_to(workspace).as_posix(),
        "branch": branch,
        "base": head.stdout.strip(),
    }


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
