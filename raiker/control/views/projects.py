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
