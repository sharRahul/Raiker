"""Canonical, contained filesystem paths for project roots."""

from __future__ import annotations

import os
import stat
from pathlib import Path

LEGACY_PROJECT_ROOT = "projects"
MANAGED_PROJECT_ROOT = ".raiker/projects"


def project_root_parts(root_subpath: str) -> tuple[str, tuple[str, ...]] | None:
    """Return a canonical legacy/managed root shape without traversal."""
    parts = tuple(part for part in root_subpath.replace("\\", "/").split("/") if part)
    if not parts or any(part in {".", ".."} for part in parts):
        return None
    if parts[0] == LEGACY_PROJECT_ROOT and len(parts) > 1:
        return LEGACY_PROJECT_ROOT, parts[1:]
    if parts[:2] == (".raiker", "projects") and len(parts) > 2:
        return MANAGED_PROJECT_ROOT, parts[2:]
    return None


def contained_project_root(
    workspace_root: Path, root_subpath: str
) -> tuple[str, tuple[str, ...], Path] | None:
    """Resolve a project leaf only below a canonical, non-reparse container."""
    parsed = project_root_parts(root_subpath)
    if parsed is None:
        return None
    kind, relative = parsed
    workspace = workspace_root.resolve()
    container_parts = tuple(kind.split("/"))
    container = workspace.joinpath(*container_parts)
    current = workspace
    for part in container_parts:
        current = current / part
        if not _canonical_directory(current):
            return None
    candidate = container
    for part in relative:
        candidate = candidate / part
        if _is_reparse_point(candidate):
            return None
    resolved_container = container.resolve()
    resolved_candidate = candidate.resolve()
    try:
        resolved_container.relative_to(workspace)
        resolved_candidate.relative_to(resolved_container)
    except ValueError:
        return None
    return kind, relative, candidate


def _canonical_directory(path: Path) -> bool:
    """An absent container is safe to create; an existing one must be real."""
    if _is_reparse_point(path):
        return False
    if path.exists() and not path.is_dir():
        return False
    return _normal_path(path.resolve()) == _normal_path(path)


def _is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _normal_path(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))
