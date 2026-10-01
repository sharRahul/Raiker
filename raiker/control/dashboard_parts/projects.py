# mypy: disable-error-code="misc"
"""Projects: creation, folders, selection, context, hierarchy and deletion
(GCR-43).

One part of :class:`raiker.control.dashboard.DashboardService`, which inherits it. Every method
is typed against the whole store (``self: DashboardService``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import new_id
from raiker.control.dtos import ControlResult
from raiker.control.project_migration import _default_root_label
from raiker.control.project_paths import MANAGED_PROJECT_ROOT as _MANAGED_PROJECT_ROOT
from raiker.control.project_paths import contained_project_root as _contained_project_root
from raiker.control.project_paths import project_root_parts as _project_root_parts
from raiker.control.project_roots import resolve_project_root
from raiker.control.views.projects import (
    ProjectAttachmentView,
    ProjectDeletionPreviewView,
    ProjectDetailView,
    ProjectsListView,
    ProjectView,
)
from raiker.events.export import generate_export
from raiker.runtime.authority.models import PrincipalType

if TYPE_CHECKING:
    from raiker.control.dashboard import DashboardService


class ProjectService:

    # A project is a named organizing scope: a workspace-contained subpath plus
    # the sessions (and their checkpoints) created while it is active. It is
    # deliberately governance-neutral — creating or selecting a project grants
    # no capability, and every path stays inside the workspace, fail-closed.

    _PROJECT_NAME_MAX = 100

    def list_projects(self: DashboardService, user_id: str | None = None) -> ProjectsListView:
        active = self.store.get_active_project(user_id)
        return ProjectsListView(
            projects=tuple(
                self._project_view(row, active) for row in self.store.list_projects(user_id)
            ),
            active_project_id=active,
        )

    def get_project(
        self: DashboardService,
        project_id: str,
        user_id: str | None = None,
        owner_principal_id: str | None = None,
    ) -> ProjectDetailView | None:
        row = self.store.load_project(project_id, user_id)
        if row is None:
            return None
        active = self.store.get_active_project(user_id)
        sessions = tuple(
            self._session_view(s)
            for s in self.store.list_sessions(limit=200, project_id=project_id, user_id=user_id)
        )
        checkpoints = tuple(
            self._checkpoint_view(c) for c in self.store.list_checkpoints(project_id=project_id)
        )
        row["session_count"] = len(sessions)
        row["last_activity_at"] = max((s.updated_at for s in sessions if s.updated_at), default=None)
        context = self.store.load_project_context(project_id)
        return ProjectDetailView(
            project=self._project_view(row, active),
            sessions=sessions,
            checkpoints=checkpoints,
            context=context,
            attachments=self._project_attachments(context.get("attachment_ids", []), owner_principal_id),
        )

    def _project_attachments(
        self: DashboardService, attachment_ids: list[str], owner_principal_id: str | None
    ) -> tuple[ProjectAttachmentView, ...]:
        """UX-PROJ-04 — resolve the context's attachment ids to what a person reads.

        Scoped to the owner who is reading, so an id that names another
        account's file resolves exactly like one that names nothing.
        """
        resolved: list[ProjectAttachmentView] = []
        for attachment_id in attachment_ids:
            meta = self.store.load_attachment_metadata(
                attachment_id, owner_principal_id=owner_principal_id
            )
            resolved.append(
                ProjectAttachmentView(
                    attachment_id=attachment_id,
                    filename=str(meta.get("filename") or "") if meta else "",
                    media_type=str(meta.get("media_type") or "") if meta else "",
                    byte_size=int(meta.get("byte_size") or 0) if meta else 0,
                    available=meta is not None,
                )
            )
        return tuple(resolved)

    def export_project(self: DashboardService, project_id: str, acting_principal_id: str | None) -> ControlResult:
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        if self.store.load_project(project_id, principal.delegated_by_user_id) is None:
            return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
        manifest = generate_export(
            self.store,
            project_id=project_id,
            user_id=principal.delegated_by_user_id,
            apply_user_visibility_filter=True,
        )
        return ControlResult(ok=True, data={"export_path": manifest.export_path})

    def create_project(
        self: DashboardService,
        name: str,
        acting_principal_id: str | None,
        parent_id: str | None = None,
        attach_path: str | None = None,
        attach_writable: bool = True,
    ) -> ControlResult:
        """Create a named project folder (human gate-manager only).

        The root subpath is derived server-side from the name (slug under
        ``.raiker/projects/``) and verified to stay inside the workspace — a
        name can never place a project root outside it (fail closed). When
        ``parent_id`` is supplied the project is created as a nested child of
        that parent folder.

        ``attach_path`` makes the new project's root a folder the owner already
        has, by the same route as attaching one afterwards. A refusal takes the
        half-made project with it, so a rejected path leaves nothing behind for
        the owner to clean up.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        cleaned = (name or "").strip()
        if not cleaned or len(cleaned) > self._PROJECT_NAME_MAX:
            return ControlResult(ok=False, reason_code="invalid_project_name")
        slug = re.sub(r"[^a-z0-9]+", "-", cleaned.lower()).strip("-")
        if not slug:
            return ControlResult(ok=False, reason_code="invalid_project_name")
        if self.store.load_project_by_name(cleaned) is not None:
            return ControlResult(ok=False, reason_code="duplicate_project_name")
        if (
            parent_id is not None
            and self.store.load_project(parent_id, principal.delegated_by_user_id) is None
        ):
            return ControlResult(ok=False, reason_code=f"unknown_parent:{parent_id}")
        if any(
            (parsed := _project_root_parts(str(project.get("root_subpath") or "")))
            and parsed[1] == (slug,)
            for project in self.store.list_projects()
        ):
            return ControlResult(ok=False, reason_code="duplicate_project_root")
        project_id = new_id("proj_")
        if attach_path is not None:
            # No managed folder is made: the owner's folder is the root, and
            # creating a second one under `.raiker/projects/` would leave an
            # empty directory that nothing ever uses.
            self.store.create_project(
                project_id,
                cleaned,
                "",
                parent_id=parent_id,
                owner_user_id=principal.delegated_by_user_id,
            )
            attached = self.attach_project_folder(
                project_id, attach_path, acting_principal_id, writable=attach_writable
            )
            if not attached.ok:
                self.store.delete_project_with_orphanage(project_id)
                return attached
            return ControlResult(
                ok=True,
                data={
                    "project_id": project_id,
                    "name": cleaned,
                    "root_subpath": "",
                    "parent_id": parent_id,
                    "root_kind": "attached",
                    "root_id": attached.data.get("root_id"),
                },
            )
        root_subpath = f"{_MANAGED_PROJECT_ROOT}/{slug}"
        contained_root = _contained_project_root(self.workspace_root, root_subpath)
        if contained_root is None:
            return ControlResult(ok=False, reason_code="project_root_escapes_workspace")
        resolved = contained_root[2]
        resolved.mkdir(parents=True, exist_ok=True)
        self.store.create_project(
            project_id,
            cleaned,
            root_subpath,
            parent_id=parent_id,
            owner_user_id=principal.delegated_by_user_id,
        )
        return ControlResult(
            ok=True,
            data={
                "project_id": project_id,
                "name": cleaned,
                "root_subpath": root_subpath,
                "parent_id": parent_id,
            },
        )

    def attach_project_folder(
        self: DashboardService,
        project_id: str,
        raw_path: str,
        acting_principal_id: str | None,
        writable: bool = True,
    ) -> ControlResult:
        """Make a folder the owner already has this project's root.

        Human-only, like every other project mutation. Validation goes through
        the existing grant path so an attached folder is recorded exactly as a
        Knowledge Map folder is — one record of "a folder the owner allowed" —
        and then adds the one refusal a grant alone does not make.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        if self.store.load_project(project_id, principal.delegated_by_user_id) is None:
            return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
        candidate = (raw_path or "").strip()
        if not candidate:
            return ControlResult(ok=False, reason_code="invalid_brain_source_path")
        expanded = Path(candidate).expanduser()
        if expanded.is_absolute():
            try:
                probe = expanded.resolve(strict=True)
            except OSError:
                probe = None
            if probe is not None and self._inside_workspace(probe):
                # Refused *before* granting: a folder already reachable inside
                # the workspace would gain a second name and a second boundary
                # from being attached, and the grant record would outlive the
                # refusal.
                return ControlResult(ok=False, reason_code="attach_path_inside_workspace")
        try:
            granted = self.grant_brain_source_folder(
                candidate, owner_principal_id=str(acting_principal_id)
            )
        except ValueError as exc:
            return ControlResult(ok=False, reason_code=str(exc))
        root_id = str(granted["root_id"])
        if self._inside_workspace(Path(str(granted["path"])).resolve()):
            return ControlResult(ok=False, reason_code="attach_path_inside_workspace")
        existing = self.store.project_for_grant(str(acting_principal_id), root_id)
        if existing is not None and str(existing["project_id"]) != project_id:
            return ControlResult(ok=False, reason_code="attach_root_already_used")
        self.store.set_grant_write_enabled(str(acting_principal_id), root_id, writable)
        if not self.store.attach_project_root(
            project_id, root_id, user_id=principal.delegated_by_user_id
        ):
            return ControlResult(ok=False, reason_code="attach_failed")
        return ControlResult(ok=True, data={"project_id": project_id, "root_id": root_id})

    def detach_project_folder(
        self: DashboardService, project_id: str, acting_principal_id: str | None
    ) -> ControlResult:
        """Release the folder a project was attached to.

        The grant stays. Detaching a project is not revoking the owner's
        folder, and conflating the two would silently close a Knowledge Map
        source the owner granted for its own sake.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        if self.store.load_project(project_id, principal.delegated_by_user_id) is None:
            return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
        if not self.store.detach_project_root(project_id, user_id=principal.delegated_by_user_id):
            return ControlResult(ok=False, reason_code="detach_failed")
        return ControlResult(ok=True, data={"project_id": project_id})

    def _inside_workspace(self: DashboardService, resolved: Path) -> bool:
        try:
            resolved.relative_to(self.workspace_root.resolve())
        except ValueError:
            return False
        return True

    def select_project(
        self: DashboardService, project_id: str | None, acting_principal_id: str | None
    ) -> ControlResult:
        """Set (or clear, with null/empty) the active project (human gate-manager only).

        New sessions are stamped with the active project. Selecting grants
        nothing — it is an organizing scope only.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        cleaned = (project_id or "").strip()
        if not cleaned:
            self.store.save_active_project(None, principal.delegated_by_user_id)
            return ControlResult(ok=True, data={"active_project_id": None})
        if self.store.load_project(cleaned, principal.delegated_by_user_id) is None:
            return ControlResult(ok=False, reason_code=f"unknown_project:{cleaned}")
        self.store.save_active_project(cleaned, principal.delegated_by_user_id)
        return ControlResult(ok=True, data={"active_project_id": cleaned})

    def delete_project(
        self: DashboardService, project_id: str, acting_principal_id: str | None, confirm: bool = False
    ) -> ControlResult:
        """Human-only hard delete with orphanage cascade. Requires confirmed=True."""
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        if not confirm:
            return ControlResult(ok=False, reason_code="project_delete_confirmation_required")
        project = self.store.load_project(project_id, principal.delegated_by_user_id)
        if project is None:
            return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
        # Branch on the resolver, never on the path string: an attached root is
        # the owner's own folder, and deleting the project must not touch a
        # single byte of it.
        root = resolve_project_root(
            project,
            self.store.list_brain_source_grants(str(acting_principal_id)),
            self.workspace_root,
        )
        if root.kind == "managed" and root.missing:
            return ControlResult(ok=False, reason_code="project_root_escapes_workspace")
        if not self.store.delete_project_with_orphanage(project_id):
            return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
        if root.kind == "managed" and root.path is not None:
            try:
                shutil.rmtree(root.path)
            except FileNotFoundError:
                pass
            except OSError:
                return ControlResult(ok=False, reason_code="project_folder_delete_failed")
        return ControlResult(ok=True, data={"project_id": project_id, "root_kind": root.kind})

    def save_project_context(
        self: DashboardService,
        project_id: str,
        *,
        instructions: str,
        attachment_ids: list[str],
        memory_enabled: bool | None = None,
        memory_mode: str | None = None,
        acting_principal_id: str | None,
    ) -> ControlResult:
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        if self.store.load_project(project_id, principal.delegated_by_user_id) is None:
            return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
        cleaned = instructions.strip()
        if len(cleaned) > 4000:
            return ControlResult(ok=False, reason_code="project_instructions_too_long")
        unique_ids = list(dict.fromkeys(item.strip() for item in attachment_ids if item.strip()))
        if len(unique_ids) > 20:
            return ControlResult(ok=False, reason_code="too_many_project_attachments")
        if any(
            self.store.load_attachment_metadata(
                attachment_id, owner_principal_id=principal.principal_id
            )
            is None
            for attachment_id in unique_ids
        ):
            return ControlResult(ok=False, reason_code="unknown_project_attachment")
        self.store.save_project_context(
            project_id,
            instructions=cleaned,
            attachment_ids=unique_ids,
            memory_enabled=memory_enabled,
            memory_mode=memory_mode,
            owner_principal_id=principal.principal_id,
        )
        context = self.store.load_project_context(project_id)
        return ControlResult(
            ok=True,
            data=context,
        )

    # Organizing scopes only — like all project operations, they grant nothing
    # and change no gate, policy, or authority.

    def list_project_tree(self: DashboardService, user_id: str | None = None) -> list[dict]:
        """Return the full project tree (active, non-archived only)."""
        return self.store.list_project_tree(user_id=user_id)

    def archive_project(self: DashboardService, project_id: str, acting_principal_id: str | None) -> ControlResult:
        """AI-autonomous soft-archive of a project subtree. No confirmation required."""
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if self.store.load_project(project_id, principal.delegated_by_user_id) is None:
            return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
        self.store.archive_project(project_id)
        return ControlResult(ok=True, data={"project_id": project_id, "archived": True})

    def restore_project(
        self: DashboardService, project_id: str, acting_principal_id: str | None
    ) -> ControlResult:
        """UX-PROJ-05 — bring an archived project back, with what was archived with it.

        Human-only: archiving is reversible precisely because a person can undo
        it. A project whose parent is still archived would come back into a
        tree that does not show it, so that is refused by name rather than
        restored somewhere the owner cannot find.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        project = self.store.load_project(project_id, principal.delegated_by_user_id)
        if project is None:
            return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
        parent_id = project.get("parent_id")
        if parent_id:
            parent = self.store.load_project(str(parent_id), principal.delegated_by_user_id)
            if parent is not None and parent.get("is_archived"):
                return ControlResult(ok=False, reason_code="project_parent_archived")
        self.store.restore_project(project_id)
        return ControlResult(ok=True, data={"project_id": project_id, "archived": False})

    def move_project(
        self: DashboardService, project_id: str, new_parent_id: str | None, acting_principal_id: str | None
    ) -> ControlResult:
        """Move a project to a new parent (human-only).

        UX-PROJ-06 — every refusal has its own name, so the page can say which
        destination was wrong: the project itself, one of its own descendants,
        an archived folder, or one that is not there.
        """
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        user_id = principal.delegated_by_user_id
        if self.store.load_project(project_id, user_id) is None:
            return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
        if new_parent_id is not None:
            if new_parent_id == project_id:
                return ControlResult(ok=False, reason_code="project_move_into_itself")
            parent = self.store.load_project(new_parent_id, user_id)
            if parent is None:
                return ControlResult(ok=False, reason_code=f"unknown_parent:{new_parent_id}")
            if new_parent_id in self.store.subtree_project_ids(project_id):
                return ControlResult(ok=False, reason_code="project_move_into_descendant")
            if parent.get("is_archived"):
                return ControlResult(ok=False, reason_code="project_move_into_archived")
        if not self.store.move_project(project_id, new_parent_id):
            return ControlResult(ok=False, reason_code="project_move_into_descendant")
        return ControlResult(
            ok=True, data={"project_id": project_id, "new_parent_id": new_parent_id}
        )

    #: How many entries the deletion preview walks before it says "at least".
    _DELETION_PREVIEW_ENTRY_LIMIT = 20_000

    def project_deletion_preview(
        self: DashboardService, project_id: str, acting_principal_id: str | None
    ) -> ControlResult:
        """UX-PROJ-07 — what deleting this project removes, before anything is removed."""
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        if principal is None:
            return ControlResult(ok=False, reason_code="principal_not_resolved")
        if principal.principal_type != PrincipalType.HUMAN:
            return ControlResult(ok=False, reason_code="not_authorized_human")
        project = self.store.load_project(project_id, principal.delegated_by_user_id)
        if project is None:
            return ControlResult(ok=False, reason_code=f"unknown_project:{project_id}")
        root = resolve_project_root(
            project,
            self.store.list_brain_source_grants(str(acting_principal_id)),
            self.workspace_root,
        )
        files = folder_bytes = 0
        truncated = False
        if root.kind == "managed" and root.path is not None and root.path.is_dir():
            # A symlink inside the folder is removed as a link, never followed,
            # so it is not counted as what it points at.
            for directory, _subdirs, names in os.walk(root.path, followlinks=False):
                for name in names:
                    if files >= self._DELETION_PREVIEW_ENTRY_LIMIT:
                        truncated = True
                        break
                    entry = Path(directory) / name
                    try:
                        if entry.is_symlink() or not entry.is_file():
                            continue
                        folder_bytes += entry.stat().st_size
                        files += 1
                    except OSError:
                        continue
                if truncated:
                    break
        counts = self.store.project_deletion_counts(project_id)
        view = ProjectDeletionPreviewView(
            project_id=project_id,
            name=str(project["name"]),
            root_kind=root.kind,
            root_label=str(project.get("root_label") or "") or _default_root_label(project),
            sessions=counts.get("sessions", 0),
            turns=counts.get("turns", 0),
            tasks=counts.get("tasks", 0),
            checkpoints=counts.get("checkpoints", 0),
            managed_files=counts.get("managed_files", 0),
            descendants=counts.get("descendants", 0),
            folder_files=files,
            folder_bytes=folder_bytes,
            folder_truncated=truncated,
            requires_step_up=root.kind == "managed",
        )
        return ControlResult(ok=True, data={"preview": view})

    def _project_view(self: DashboardService, row: dict[str, Any], active_project_id: str | None) -> ProjectView:
        return ProjectView(
            project_id=str(row["project_id"]),
            name=str(row["name"]),
            root_subpath=str(row["root_subpath"]),
            created_at=str(row.get("created_at", "")),
            session_count=int(row.get("session_count", 0) or 0),
            selected=(str(row["project_id"]) == active_project_id),
            parent_id=row.get("parent_id"),
            path=str(row.get("path", "/")),
            is_archived=bool(row.get("is_archived", 0)),
            archived_at=row.get("archived_at"),
            root_kind=str(row.get("root_kind") or "managed"),
            root_label=str(row.get("root_label") or "") or _default_root_label(row),
            last_activity_at=row.get("last_activity_at") or None,
        )
