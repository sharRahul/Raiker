# SPDX-License-Identifier: Apache-2.0
"""Projects: creation and selection, the tree, the folder behind one, and its files."""

from __future__ import annotations

from typing import Any, Literal, NotRequired

from typing_extensions import TypedDict

ProjectRootKind = Literal["managed", "attached"]
ManagedFileScope = Literal["memory", "project"]
ManagedFileIndexState = Literal["queued", "indexing", "ready", "metadata_only", "failed", "retired"]


class ProjectCreated(TypedDict):
    """A new project; an attached one also names its root and the grant behind it."""

    ok: bool
    project_id: str
    name: str
    root_subpath: str
    parent_id: str | None
    root_kind: NotRequired[Literal["attached"]]
    root_id: NotRequired[str | None]


class ProjectSelected(TypedDict):
    ok: bool
    active_project_id: str | None


class ProjectTreeNode(TypedDict):
    """One active project and the active projects filed under it."""

    project_id: str
    name: str
    parent_id: str | None
    root_subpath: str
    created_at: str
    children: list[ProjectTreeNode]


def project_tree(rows: list[dict[str, Any]]) -> list[ProjectTreeNode]:
    """The tree as the page reads it — never the stored row it was built from."""
    return [
        {
            "project_id": str(row["project_id"]),
            "name": str(row["name"]),
            "parent_id": row.get("parent_id"),
            "root_subpath": str(row.get("root_subpath") or ""),
            "created_at": str(row.get("created_at") or ""),
            "children": project_tree(list(row.get("children") or [])),
        }
        for row in rows
    ]


class ProjectContextSaved(TypedDict):
    ok: bool
    instructions: str
    attachment_ids: list[str]
    memory_enabled: bool
    memory_mode: Literal["inherit", "enabled", "disabled"]


class ProjectDeleted(TypedDict):
    ok: bool
    project_id: str
    root_kind: ProjectRootKind


class ProjectMoved(TypedDict):
    ok: bool
    project_id: str
    new_parent_id: str | None


class ProjectArchived(TypedDict):
    ok: bool
    project_id: str
    archived: bool


class ProjectFolderAttached(TypedDict):
    ok: bool
    project_id: str
    root_id: str


class ProjectFolderDetached(TypedDict):
    ok: bool
    project_id: str


class ProjectBrowseEntry(TypedDict):
    """One child of the folder being browsed; ``index_state`` is null for a file Raiker cannot read."""

    name: str
    relative_path: str
    is_directory: bool
    size_bytes: int
    media_type: str
    index_state: ManagedFileIndexState | None


class ProjectBrowseView(TypedDict):
    """One directory of a project's folder; ``root_missing`` when there is no folder to show."""

    path: str
    parent: str | None
    entries: list[ProjectBrowseEntry]
    truncated: bool
    root_kind: ProjectRootKind
    root_label: str
    root_missing: bool


class ProjectRootStatus(TypedDict):
    """Where a project's files are, and whether Raiker is watching them."""

    ok: bool
    project_id: str
    root_kind: ProjectRootKind
    root_label: str
    root_path: str | None
    root_missing: bool
    writable: bool
    watching: bool
    watch_reason: str
    last_scanned_at: str
    indexed_files: int


class ProjectRootIndexResult(TypedDict):
    """One reconcile of an attached folder against the index."""

    ok: bool
    project_id: str
    indexed: int
    updated: int
    retired: int
    skipped: int
    truncated: bool
    scanned_at: str


class ManagedFile(TypedDict):
    """A file in Raiker's catalogue, and how far its index has got."""

    file_id: str
    scope_kind: ManagedFileScope
    project_id: str | None
    relative_path: str
    media_type: str
    size_bytes: int
    content_hash: str
    index_state: ManagedFileIndexState
    index_error: str | None
    created_at: str
    updated_at: str


class ManagedFileChanged(ManagedFile):
    ok: bool


class ManagedFileList(TypedDict):
    ok: bool
    scope_kind: ManagedFileScope
    project_id: str | None
    files: list[ManagedFile]


class ImportedFile(ManagedFile):
    ok: Literal[True]


class ImportRefused(TypedDict):
    """One file of a batch that was not stored, and why — its siblings still were."""

    ok: Literal[False]
    relative_path: str
    reason_code: str


class ManagedFileImport(TypedDict):
    ok: bool
    scope_kind: ManagedFileScope
    project_id: str | None
    results: list[ImportedFile | ImportRefused]
