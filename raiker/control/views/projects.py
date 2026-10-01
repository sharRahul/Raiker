"""Projects, their detail, and the list the Projects page reads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from raiker.contracts.views import View
from raiker.control.views.sessions import CheckpointView, SessionView


@dataclass(frozen=True)
class ProjectView(View):
    # A project is an organizing scope, not an authority: it names a
    # workspace-contained subpath and groups sessions/checkpoints. Selecting or
    # creating one grants nothing.
    project_id: str
    name: str
    root_subpath: str
    created_at: str
    session_count: int
    selected: bool
    # Nested projects/folders: parent reference, materialized path, soft-archive state
    parent_id: str | None = None
    path: str = "/"
    is_archived: bool = False
    archived_at: str | None = None
    # Which kind of root this project has, and what to call it. Carried on the
    # list rather than fetched per card, because the delete confirmation has to
    # say whether a folder survives *before* the owner opens anything.
    root_kind: str = "managed"
    root_label: str = ""
    # UX-PROJ-09 — when work last happened here: the newest of its sessions'
    # updates, or null for a project nothing has run in. "Recently active" is
    # this, never the account-level selection above.
    last_activity_at: str | None = None


@dataclass(frozen=True)
class ProjectAttachmentView(View):
    """UX-PROJ-04 — a file shared with every chat in a project, as a person names it.

    ``available`` is false when the id no longer resolves to a file this owner
    holds; the row says so rather than disappearing, because the context still
    names it and the owner can only remove what they can see.
    """

    attachment_id: str
    filename: str
    media_type: str
    byte_size: int
    available: bool


@dataclass(frozen=True)
class ProjectDeletionPreviewView(View):
    """UX-PROJ-07 — everything a delete removes, counted before it runs.

    ``folder_files`` and ``folder_bytes`` describe the managed folder Raiker
    removes from disk; an attached folder is the owner's and is never counted,
    because nothing in it is touched. ``folder_truncated`` is true when the
    count stopped at its ceiling, so the preview reads "at least".
    """

    project_id: str
    name: str
    root_kind: str
    root_label: str
    sessions: int
    turns: int
    tasks: int
    checkpoints: int
    managed_files: int
    descendants: int
    folder_files: int
    folder_bytes: int
    folder_truncated: bool
    requires_step_up: bool


@dataclass(frozen=True)
class ProjectRootMigrationReport:
    """The safe, repeatable outcome of moving legacy project folders."""

    migrated: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    unchanged: tuple[str, ...] = ()
    retained_residues: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectsListView(View):
    projects: tuple[ProjectView, ...]
    active_project_id: str | None


@dataclass(frozen=True)
class ProjectDetailView(View):
    project: ProjectView
    sessions: tuple[SessionView, ...]
    checkpoints: tuple[CheckpointView, ...]
    context: dict[str, Any]
    attachments: tuple[ProjectAttachmentView, ...] = ()
