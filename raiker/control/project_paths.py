"""Canonical, contained filesystem paths for project roots."""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

LEGACY_PROJECT_ROOT = "projects"
MANAGED_PROJECT_ROOT = ".raiker/projects"
#: Where a project made for Build gets its own folder (RU-21).
PROJECTS_HOME_ENV = "RAIKER_PROJECTS_HOME"
PROJECTS_HOME_NAME = "Raiker Projects"
_UNSAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{n}" for n in range(1, 10)), *(f"lpt{n}" for n in range(1, 10))}


def projects_home() -> Path:
    """``~/Raiker Projects``, or the folder ``RAIKER_PROJECTS_HOME`` names."""
    configured = os.environ.get(PROJECTS_HOME_ENV, "").strip()
    return Path(configured).expanduser() if configured else Path.home() / PROJECTS_HOME_NAME


def folder_name(name: str) -> str:
    """A project's name as a folder name every desktop can hold."""
    cleaned = _UNSAFE_NAME.sub("-", name).strip().strip(". ")
    cleaned = re.sub(r"\s+", " ", cleaned)[:80].strip()
    if not cleaned or cleaned.casefold() in _RESERVED:
        cleaned = f"Project {cleaned}".strip()
    return cleaned


def make_project_folder(name: str, home: Path | None = None) -> Path | None:
    """A new, empty folder for *name* under the projects home.

    ``Pricing``, then ``Pricing 2``, … — an existing folder is never adopted.
    ``None`` when no folder could be made.
    """
    base = home if home is not None else projects_home()
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    stem = folder_name(name)
    for index in range(1, 100):
        candidate = base / (stem if index == 1 else f"{stem} {index}")
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        except OSError:
            return None
        return candidate
    return None


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
