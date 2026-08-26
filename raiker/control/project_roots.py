"""Where a project's files actually live, and what a turn may do there.

A project now has one of two roots: the managed subpath under the workspace it
has always had, or a folder the owner already had and granted. Everything that
needs a project's root — indexing, browsing, writing — asks here, so the two
kinds are told apart in exactly one place.

The grant is the record, not the path. An attached project reads its root out
of the owner's live grants rather than out of its own row, which is what makes
revoking a grant take the root away without any cascade: the next resolution
simply finds nothing to resolve.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from raiker.control.project_paths import contained_project_root
from raiker.tools.path_authority import WORKSPACE_ROOT_ID, AuthorityRoot, PathAuthority

MANAGED_ROOT_KIND = "managed"
ATTACHED_ROOT_KIND = "attached"


@dataclass(frozen=True)
class ProjectRoot:
    """One project's root, as it stands right now.

    ``missing`` is not an error state to be raised past: a revoked grant or a
    folder the owner moved is an ordinary condition the interface has to show,
    and turning it into an exception would make every caller invent the same
    handling.
    """

    kind: str
    path: Path | None
    writable: bool
    root_id: str
    missing: bool


def resolve_project_root(
    project: Mapping[str, Any] | None,
    grants: Iterable[Mapping[str, Any]],
    workspace_root: str | Path,
) -> ProjectRoot:
    """A project's root, from its own row plus the owner's grants.

    Never reads ``root_subpath`` for an attached project: the grant is the
    record, and a revoked grant must read as missing rather than as a path that
    happens to still be on disk.
    """
    if project is None:
        return ProjectRoot(MANAGED_ROOT_KIND, None, False, WORKSPACE_ROOT_ID, missing=True)
    workspace = Path(workspace_root)
    if str(project.get("root_kind") or MANAGED_ROOT_KIND) != ATTACHED_ROOT_KIND:
        contained = contained_project_root(workspace, str(project.get("root_subpath") or ""))
        path = contained[2] if contained else None
        return ProjectRoot(
            MANAGED_ROOT_KIND, path, path is not None, WORKSPACE_ROOT_ID, missing=path is None
        )
    grant_id = str(project.get("root_grant_id") or "")
    grant = next(
        (item for item in grants if str(item.get("root_id")) == grant_id), None
    ) if grant_id else None
    if grant is None:
        # Detached, or the owner revoked the folder. Either way the project has
        # no root until they say otherwise, and inventing one would be worse
        # than saying so.
        return ProjectRoot(ATTACHED_ROOT_KIND, None, False, grant_id, missing=True)
    path = Path(str(grant["path"]))
    return ProjectRoot(
        ATTACHED_ROOT_KIND,
        path,
        bool(grant.get("write_enabled")),
        grant_id,
        missing=not path.is_dir(),
    )


def authority_for_project(
    project: Mapping[str, Any] | None,
    grants: Iterable[Mapping[str, Any]],
    workspace_root: str | Path,
) -> PathAuthority:
    """The roots a turn on this project may touch.

    A managed project gets the workspace-only authority that predates roots, so
    nothing about an ordinary project changes. An attached one gets the
    workspace *and* its own folder — the workspace stays reachable because
    Raiker's own runtime files live there and a turn still needs them.
    """
    root = resolve_project_root(project, grants, workspace_root)
    if root.kind != ATTACHED_ROOT_KIND or root.path is None:
        return PathAuthority(workspace_root)
    return PathAuthority(
        workspace_root,
        roots=(
            AuthorityRoot(root.root_id, root.path, root.writable, root.path.name or root.root_id),
        ),
    )
