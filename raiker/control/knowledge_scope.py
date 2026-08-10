"""What the Knowledge Map is allowed to see.

The graph's source picker used to browse the workspace root, so opening it
listed everything under the Raiker installation — its own source tree included —
and invited an owner to index any of it. That is not a boundary; it is the
absence of one.

The boundary this module defines has three parts, and nothing else is
browsable:

* **Raiker's own data** — the places Raiker itself keeps an owner's work:
  each project's files, the files turns generated, and approved memory. Chat,
  Build, Tasks, Schedules and uploaded user files live inside the encrypted
  database rather than as loose files; they are already nodes in the graph, so
  the picker names the database and says so instead of pretending it is a
  folder to walk.
* **Folders the owner explicitly granted** — any directory on the machine,
  named by the owner in the grant dialog. A grant is a decision, recorded with
  the moment it was made, and revocable.
* **Nothing else.** A path that resolves outside every root is refused by name.

The addressing scheme follows from that: a source path is
``<root_id>/<relative path within that root>``. There is no path that means
"the workspace", so no request can ask for one.

Copying is a separate decision from reading. A granted folder is read where it
is — Raiker never duplicates it into the workspace — and a file uploaded from
the owner's computer is stored only when the owner has said, in that dialog,
that it may be.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Never walked, wherever they appear: version-control internals, dependency
# trees, and build output are noise in a knowledge graph and are large enough to
# make an incremental review meaningless.
SKIPPED_DIRECTORY_NAMES: frozenset[str] = frozenset(
    {".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache",
     ".pytest_cache", ".ruff_cache", "dist", "build", ".next", ".svelte-kit"}
)

# The runtime directory is Raiker's own machinery. Two subtrees inside it hold
# owner-facing documents and are offered as roots; the rest — the encrypted
# database, the event log, checkpoints, key material — is not browsable, and
# saying so is the point of `DATABASE_ROOT_ID`.
RUNTIME_DIR_NAME = ".raiker"
ARTIFACTS_ROOT_ID = "generated-files"
MEMORY_ROOT_ID = "approved-memory"
DATABASE_ROOT_ID = "raiker-database"
PROJECT_ROOT_PREFIX = "project-"
GRANT_ROOT_PREFIX = "granted-"

MAX_SOURCE_PATH_CHARS = 512

# Where a file copied from the owner's computer lands, and the largest one
# Raiker will accept. One named directory, so an owner can find every copy the
# Knowledge Map holds and delete it.
KNOWLEDGE_UPLOAD_DIR = "knowledge-uploads"
MAX_KNOWLEDGE_UPLOAD_BYTES = 5 * 1024 * 1024

# What the indexer can read as text. Anything else is counted and skipped, and
# the review says how many were skipped rather than silently dropping them.
KNOWLEDGE_SOURCE_EXTENSIONS: frozenset[str] = frozenset(
    {".md", ".txt", ".rst", ".py", ".ts", ".tsx", ".js", ".jsx", ".json",
     ".toml", ".yaml", ".yml", ".html", ".css", ".scss", ".sql", ".go",
     ".rs", ".java", ".cs", ".cpp", ".c", ".h", ".sh", ".ps1"}
)


class ScopeError(ValueError):
    """A request named something outside the boundary. ``reason`` is stable."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ScopeRoot:
    """One place the Knowledge Map may look, and what to call it."""

    root_id: str
    label: str
    detail: str
    kind: str  # "raiker" | "granted" | "database"
    path: Path | None
    browsable: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_id": self.root_id,
            "label": self.label,
            "detail": self.detail,
            "kind": self.kind,
            "browsable": self.browsable,
            # The absolute path is shown only for a folder the owner granted
            # themselves: they typed it, and they need to recognise it again to
            # revoke it. Raiker's own locations stay described, not disclosed.
            "path": str(self.path) if self.browsable and self.kind == "granted" else None,
        }


def grant_root_id(path: str | Path) -> str:
    """A stable id for a granted folder, derived from the path itself."""
    digest = hashlib.sha256(str(Path(path)).encode("utf-8")).hexdigest()[:12]
    return f"{GRANT_ROOT_PREFIX}{digest}"


def build_roots(
    workspace_root: Path,
    projects: Sequence[Mapping[str, Any]],
    grants: Iterable[Mapping[str, Any]],
) -> list[ScopeRoot]:
    """Every root this owner may browse, in the order the picker shows them.

    Missing directories are still listed: a project whose folder has not been
    created yet is a real project, and hiding it would read as Raiker having
    lost it. Browsing one that does not exist fails by name.
    """
    runtime_dir = workspace_root / RUNTIME_DIR_NAME
    roots: list[ScopeRoot] = []
    for project in projects:
        subpath = str(project.get("root_subpath") or "").strip().strip("/")
        name = str(project.get("name") or "Project")
        project_id = str(project.get("project_id") or "")
        if not project_id:
            continue
        roots.append(
            ScopeRoot(
                root_id=f"{PROJECT_ROOT_PREFIX}{project_id}",
                label=f"Project files · {name}",
                detail="The files this project keeps in your Raiker workspace.",
                kind="raiker",
                path=(workspace_root / subpath).resolve() if subpath else workspace_root,
                browsable=True,
            )
        )
    roots.append(
        ScopeRoot(
            root_id=ARTIFACTS_ROOT_ID,
            label="Generated files",
            detail="Documents and files Raiker produced during your turns.",
            kind="raiker",
            path=(runtime_dir / "artifacts").resolve(),
            browsable=True,
        )
    )
    roots.append(
        ScopeRoot(
            root_id=MEMORY_ROOT_ID,
            label="Approved memory",
            detail="Memories you approved, stored as documents.",
            kind="raiker",
            path=(runtime_dir / "memory").resolve(),
            browsable=True,
        )
    )
    roots.append(
        ScopeRoot(
            root_id=DATABASE_ROOT_ID,
            label="Raiker database",
            detail=(
                "Chat, Build, Tasks, Schedules and the files you uploaded are held "
                "in the encrypted workspace database and are already in this graph. "
                "There is nothing to add here."
            ),
            kind="database",
            path=None,
            browsable=False,
        )
    )
    for grant in grants:
        raw = str(grant.get("path") or "").strip()
        if not raw:
            continue
        path = Path(raw)
        roots.append(
            ScopeRoot(
                root_id=str(grant.get("root_id") or grant_root_id(path)),
                label=str(grant.get("label") or path.name or raw),
                detail=f"Granted folder · read where it is, never copied into Raiker · {raw}",
                kind="granted",
                path=path,
                browsable=True,
            )
        )
    return roots


def resolve(roots: Sequence[ScopeRoot], raw_path: str) -> tuple[ScopeRoot, str, Path]:
    """Turn ``<root_id>/<relative>`` into the root, its relative path, and a Path.

    Raises :class:`ScopeError` for anything that is not inside a browsable root.
    Resolution happens **before** the containment check, so a symlink or a
    ``..`` segment cannot point out of the root it claims to be in.
    """
    candidate = (raw_path or "").strip().replace("\\", "/").lstrip("/")
    if not candidate or len(candidate) > MAX_SOURCE_PATH_CHARS:
        raise ScopeError("invalid_brain_source_path")
    head, _, tail = candidate.partition("/")
    root = next((item for item in roots if item.root_id == head), None)
    if root is None:
        raise ScopeError("brain_source_outside_scope")
    if not root.browsable or root.path is None:
        raise ScopeError("brain_source_root_not_browsable")
    base = root.path.resolve()
    target = (base / tail).resolve() if tail else base
    if target != base and base not in target.parents:
        raise ScopeError("brain_source_outside_scope")
    relative = "" if target == base else target.relative_to(base).as_posix()
    if any(part in SKIPPED_DIRECTORY_NAMES for part in Path(relative).parts):
        raise ScopeError("brain_source_protected_path")
    if not target.exists():
        raise ScopeError("brain_source_not_found")
    return root, relative, target


def scope_path(root: ScopeRoot, relative: str) -> str:
    """The addressable path for a resolved location, as the picker stores it."""
    return f"{root.root_id}/{relative}" if relative else root.root_id


def parent_scope_path(root: ScopeRoot, relative: str) -> str:
    """One level up, stopping at the root — never at the filesystem above it.

    Above a root's own top is the list of places, addressed as the empty path.
    There is no level above that, which is the whole point of the boundary.
    """
    if not relative:
        return ""
    parent = Path(relative).parent.as_posix()
    return scope_path(root, "" if parent in {"", "."} else parent)
