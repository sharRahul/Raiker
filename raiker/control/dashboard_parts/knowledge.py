# mypy: disable-error-code="misc"
"""Knowledge Map reads and the owner's source and folder grants (GCR-43).

One part of :class:`raiker.control.dashboard.DashboardService`, which inherits it. Every method
is typed against the whole store (``self: DashboardService``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import base64
import contextlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from raiker.contracts.ids import utc_now
from raiker.control.knowledge_scope import (
    ARTIFACTS_ROOT_ID,
    KNOWLEDGE_SOURCE_EXTENSIONS,
    KNOWLEDGE_UPLOAD_DIR,
    MAX_KNOWLEDGE_UPLOAD_BYTES,
    MAX_SOURCE_PATH_CHARS,
    REVIEW_ACCEPTED_FILE_BUDGET,
    REVIEW_DEPTH_BUDGET,
    REVIEW_TIME_BUDGET_SECONDS,
    REVIEW_TRUNCATION_REASONS,
    REVIEW_VISITED_ENTRY_BUDGET,
    RUNTIME_DIR_NAME,
    SKIPPED_DIRECTORY_NAMES,
    ScopeError,
    ScopeRoot,
    build_roots,
    grant_root_id,
    parent_scope_path,
    resolve,
    scope_path,
)
from raiker.control.views.knowledge import BrainEdgeView, BrainNodeView, BrainView
from raiker.control.views.tasks import _task_detail
from raiker.events.writer import EventLogWriter
from raiker.memory.store import list_memory
from raiker.models.tool_registry import TOOL_LABEL_BY_TOOL
from raiker.storage.internal_paths import internal_io_path
from raiker.tools.graph_tools import reference_resolution

if TYPE_CHECKING:
    from raiker.control.dashboard import DashboardService


@dataclass(frozen=True)
class _SourceReviewWalk:
    """What one bounded review walk found, and what it cost to find it."""

    supported: int
    unsupported: int
    total_bytes: int
    examples: tuple[str, ...]
    #: Every entry looked at, accepted or skipped. The number the old cap was
    #: mistaken for.
    visited: int
    truncated_reason: str | None


def _walk_source_for_review(path: Path, base: Path) -> _SourceReviewWalk:
    """Walk *path* for an indexing plan, under four budgets that actually bind.

    NEW-MAP-03. The previous walk was ``path.rglob("*")`` with a counter that
    only advanced on entries it accepted, so everything it skipped was free:
    every directory, every hidden path, every name under ``node_modules``, every
    file it could not ``stat``. A cap of 5,000 therefore bounded the *answer*
    and not the *work*, and a folder with a large dependency tree beside it was
    walked in full to report the six files an owner cared about.

    Three things change:

    * **Excluded directories are pruned before descent** rather than after
      every entry inside them has been produced. ``os.walk`` lets the walker
      edit the directory list in place, which is the difference between not
      entering ``node_modules`` and enumerating it and discarding the result.
    * **Every entry visited is counted**, whatever happens to it, so the visit
      budget is a bound on the work and the file budget stays a bound on the
      answer.
    * **Depth and elapsed time are their own budgets.** A pathological tree is
      deep rather than wide, and a slow drive is neither — no counter of entries
      notices either one.

    Symlinked directories are not followed (``os.walk`` does not by default),
    which is what stops a cycle; the containment check below is unchanged and
    still judges every accepted file against the selected root.
    """
    started = time.monotonic()
    supported = 0
    unsupported = 0
    total_bytes = 0
    visited = 0
    examples: list[str] = []
    truncated: str | None = None

    def _example(resolved: Path) -> None:
        if len(examples) < 8:
            with contextlib.suppress(ValueError):
                examples.append(resolved.relative_to(base).as_posix())

    def _consider(candidate: Path) -> None:
        """Count one file, if it is one Raiker could read."""
        nonlocal supported, unsupported, total_bytes
        try:
            resolved = candidate.resolve()
            if resolved != base and base not in resolved.parents:
                return
            size = candidate.stat().st_size
        except (OSError, ValueError):
            return
        if candidate.suffix.casefold() in KNOWLEDGE_SOURCE_EXTENSIONS and size <= 5 * 1024 * 1024:
            supported += 1
            total_bytes += size
            _example(resolved)
        else:
            unsupported += 1

    if path.is_file():
        visited = 1
        _consider(path)
        return _SourceReviewWalk(
            supported, unsupported, total_bytes, tuple(examples), visited, None
        )

    base_depth = len(path.parts)
    for dirpath, dirnames, filenames in os.walk(path, onerror=None):
        here = Path(dirpath)
        depth = len(here.parts) - base_depth
        # Pruned in place, before anything inside them is produced. This is the
        # whole finding: the previous walk enumerated these and threw the
        # entries away one at a time.
        dirnames[:] = [
            name
            for name in dirnames
            if name not in SKIPPED_DIRECTORY_NAMES and not name.startswith(".")
        ]
        visited += len(dirnames)
        if depth >= REVIEW_DEPTH_BUDGET:
            dirnames.clear()
            truncated = truncated or "depth_cap"

        for name in filenames:
            visited += 1
            if visited >= REVIEW_VISITED_ENTRY_BUDGET:
                truncated = "visited_entry_cap"
                break
            if time.monotonic() - started >= REVIEW_TIME_BUDGET_SECONDS:
                truncated = "time_cap"
                break
            if name.startswith("."):
                continue
            _consider(here / name)
            # The accepted-file budget is checked after the file is counted, so
            # the number the owner reads is the number that was reached.
            if supported + unsupported >= REVIEW_ACCEPTED_FILE_BUDGET:
                truncated = "accepted_file_cap"
                break

        if truncated in {"visited_entry_cap", "time_cap", "accepted_file_cap"}:
            break
        if visited >= REVIEW_VISITED_ENTRY_BUDGET:
            truncated = "visited_entry_cap"
            break
        if time.monotonic() - started >= REVIEW_TIME_BUDGET_SECONDS:
            truncated = "time_cap"
            break

    return _SourceReviewWalk(
        supported, unsupported, total_bytes, tuple(examples), visited, truncated
    )


#: BUG-218 — how a tool is named on the Knowledge Map, where it differs from the
#: transcript. The registry's labels are written for a transcript line ("Check
#: the weather"); a graph node has room for a noun ("Weather"). Anything unlisted
#: uses the registry's own label (OPT-13), so a new tool is named once.
TOOL_LABELS: dict[str, str] = {
    "read_file": "Read file",
    "write_file": "Write file",
    "edit_file": "Edit file",
    "apply_patch": "Apply patch",
    "list_directory": "List folder",
    "grep": "Search text",
    "glob": "Find files",
    "shell": "Run command",
    "run_command": "Run command",
    "background_run": "Background run",
    "web_fetch": "Fetch page",
    "web_search": "Web search",
    "web_extract": "Read part of a page",
    "weather_lookup": "Weather",
    "memory_search": "Search memory",
    "memory_write": "Remember",
    "knowledge_graph": "Explore graph",
    "conversation_search": "Search chats",
    "code_map_search": "Search code map",
    "code_map_references": "Find references",
    "document_symbols": "Outline file",
    "find_definition": "Find definition",
    "diagnostics": "Check for problems",
    "create_document": "Create document",
    "spawn_subagent": "Delegate",
    "update_plan": "Update plan",
}


#: What a cited source is drawn *as*. A file the answer quoted should look like
#: a file on the map, not like a generic citation — the whole complaint BUG-218
#: answers is that the map showed runtime bookkeeping where the owner expected
#: their own material.
CONTEXT_NODE_TYPES: dict[str, str] = {
    "file": "file",
    "repository": "file",
    "attachment": "file",
    "document": "file",
    "folder": "folder",
    "memory": "memory",
    "conversation": "conversation",
    "web": "source",
    "url": "source",
    "connector": "source",
}


#: BUG-218 — a Chat and a Build session are different work. `sessions.origin`
#: already distinguished them and the map drew both as one green dot.
SESSION_NODE_TYPES: dict[str, str] = {
    "chat": "conversation",
    "build": "build",
    "task": "task_run",
    "workbench": "conversation",
}


SESSION_LABELS: dict[str, str] = {
    "chat": "chat",
    "build": "build session",
    "task": "task run",
    "workbench": "chat",
}


class KnowledgeService:

    def _workspace_source(self: DashboardService, raw_path: str) -> tuple[str, Path]:
        """Resolve one workspace-contained path, for the Build repository refs.

        The Knowledge Map no longer uses this — it has its own, narrower
        boundary in :mod:`raiker.control.knowledge_scope`. Referencing a
        repository is a different act: the owner names a folder they already
        keep in this workspace, and the containment check is against the
        workspace itself.
        """
        candidate = raw_path.strip()
        if not candidate or len(candidate) > MAX_SOURCE_PATH_CHARS:
            raise ValueError("invalid_brain_source_path")
        root = self.workspace_root.resolve()
        path = (root / candidate).resolve()
        if path != root and root not in path.parents:
            raise ValueError("brain_source_outside_workspace")
        relative = path.relative_to(root)
        if any(part in {".git", RUNTIME_DIR_NAME, "node_modules"} for part in relative.parts):
            raise ValueError("brain_source_protected_path")
        if not path.exists():
            raise ValueError("brain_source_not_found")
        return relative.as_posix(), path

    def _scope_roots(self: DashboardService, owner_principal_id: str | None) -> list[ScopeRoot]:
        """The places the Knowledge Map may look for this owner.

        Raiker's own document areas plus the folders this owner granted — never
        the workspace root, which is what made the picker list Raiker's whole
        installation and offer to index it.
        """
        # Scoped to this owner's projects, exactly as the Projects page is: a
        # root list built from every project in the workspace would offer
        # another account's folder as somewhere to browse.
        user_id = self.store.principal_user_id(owner_principal_id) if owner_principal_id else None
        projects = self.store.list_projects(user_id)
        grants = (
            self.store.list_brain_source_grants(owner_principal_id) if owner_principal_id else []
        )
        return build_roots(self.workspace_root.resolve(), projects, grants)

    def _scoped_source(
        self: DashboardService, raw_path: str, *, owner_principal_id: str | None
    ) -> tuple[ScopeRoot, str, Path]:
        try:
            return resolve(self._scope_roots(owner_principal_id), raw_path)
        except ScopeError as exc:
            raise ValueError(exc.reason) from exc

    #
    # There are two kinds of source and they are genuinely different objects: a
    # *managed file* is bytes Raiker holds, copied into its own storage, and a
    # *granted folder* is somewhere on this machine Raiker may read in place.
    # Merging them into one store would mean either copying a folder nobody
    # asked to copy, or holding an upload as a path that can move — so they stay
    # two controllers.
    #
    # What they did not have is one place that answers the owner's question.
    # Memory listed the copies; the Knowledge Map listed the folders; nothing
    # listed both, and an owner asking what Raiker can read had to know the
    # distinction before they could find out. This is that list, and the one
    # door that revokes an entry from it — each still handled by the controller
    # that owns it, so no revocation semantics are re-implemented here.

    def knowledge_sources(self: DashboardService, *, owner_principal_id: str) -> dict[str, Any]:
        """Everything Raiker may read, both kinds, in the order it was added."""
        entries: list[dict[str, Any]] = []
        for row in self.store.list_managed_files(owner_principal_id):
            scope_kind = str(row.get("scope_kind") or "memory")
            project_id = str(row.get("project_id") or "")
            state = str(row.get("index_state") or "")
            entries.append(
                {
                    "source_id": str(row.get("file_id") or ""),
                    "kind": "managed_file",
                    "label": str(row.get("filename") or row.get("relative_path") or ""),
                    "location": str(row.get("relative_path") or ""),
                    "scope": f"project:{project_id}" if project_id else scope_kind,
                    # Raiker wrote these bytes, so revoking takes them with it.
                    # The exception — a project whose root the owner attached —
                    # is the indexer's own rule and is not second-guessed here.
                    "held": True,
                    "index_state": state,
                    # `ready` is the only state whose text retrieval can search.
                    "recall": state == "ready",
                    "graph": False,
                    "added_at": str(row.get("created_at") or ""),
                }
            )
        for grant in self.store.list_brain_source_grants(owner_principal_id):
            root_id = str(grant.get("root_id") or "")
            indexed = [
                source
                for source in self.store.list_brain_sources(owner_principal_id)
                if source == root_id or source.startswith(f"{root_id}/")
            ]
            entries.append(
                {
                    "source_id": root_id,
                    "kind": "granted_folder",
                    "label": str(grant.get("label") or grant.get("path") or root_id),
                    "location": str(grant.get("path") or ""),
                    "scope": "folder",
                    # Read where it lives. Revoking never touches it.
                    "held": False,
                    "index_state": "indexed" if indexed else "granted",
                    "recall": bool(indexed),
                    "graph": bool(indexed),
                    "added_at": str(grant.get("created_at") or ""),
                }
            )
        entries.sort(key=lambda entry: (str(entry["added_at"]), str(entry["source_id"])))
        return {
            "sources": entries,
            "held_count": sum(1 for entry in entries if entry["held"]),
            "granted_count": sum(1 for entry in entries if not entry["held"]),
        }

    def revoke_knowledge_source(
        self: DashboardService, kind: str, source_id: str, *, owner_principal_id: str
    ) -> dict[str, Any]:
        """Stop reading one source, whichever controller owns it.

        Neither branch is new behaviour: a managed file goes through the
        indexer's own retire — which deletes the bytes Raiker wrote and leaves
        an attached root's own files alone — and a granted folder goes through
        the grant revocation, which also drops every source indexed under it so
        the graph stops answering from a folder the owner just closed.
        """
        cleaned = (source_id or "").strip()
        if not cleaned:
            raise ValueError("knowledge_source_not_named")
        if kind == "granted_folder":
            return self.revoke_brain_source_folder(cleaned, owner_principal_id=owner_principal_id)
        if kind == "managed_file":
            from raiker.knowledge.files import ManagedFileError
            from raiker.knowledge.indexing import ManagedFileIndexer

            indexer = ManagedFileIndexer(self.workspace_root, self.store)
            try:
                record = indexer.retire(cleaned, owner_principal_id)
            except ManagedFileError as exc:
                raise ValueError(str(exc)) from exc
            return {"ok": True, "source_id": record.file_id}
        raise ValueError("unknown_knowledge_source_kind")

    def brain_source_roots(self: DashboardService, *, owner_principal_id: str) -> dict[str, Any]:
        """What the picker opens on: the boundary itself, named."""
        return {"roots": [root.to_dict() for root in self._scope_roots(owner_principal_id)]}

    def add_brain_source(self: DashboardService, raw_path: str, *, owner_principal_id: str) -> dict[str, Any]:
        root, relative, _path = self._scoped_source(raw_path, owner_principal_id=owner_principal_id)
        stored = scope_path(root, relative)
        self.store.add_brain_source(owner_principal_id, stored)
        return {"ok": True, "path": stored}

    def remove_brain_source(self: DashboardService, raw_path: str, *, owner_principal_id: str) -> dict[str, Any]:
        try:
            root, relative, _path = self._scoped_source(
                raw_path, owner_principal_id=owner_principal_id
            )
            stored = scope_path(root, relative)
        except ValueError:
            # A source recorded before this boundary existed, or one whose
            # folder has since gone: removing it must still work, or the owner
            # cannot clear a source they can see.
            stored = raw_path.strip()
        self.store.remove_brain_source(owner_principal_id, stored)
        return {"ok": True, "path": stored}

    def grant_brain_source_folder(
        self: DashboardService, raw_path: str, *, owner_principal_id: str
    ) -> dict[str, Any]:
        """Record the owner granting one folder on this machine.

        The folder is read where it is. Nothing is copied into the workspace by
        granting it, which is the difference between this and an upload.
        """
        candidate = (raw_path or "").strip()
        if not candidate or len(candidate) > MAX_SOURCE_PATH_CHARS:
            raise ValueError("invalid_brain_source_path")
        path = Path(candidate).expanduser()
        if not path.is_absolute():
            raise ValueError("brain_grant_requires_absolute_path")
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise ValueError("brain_grant_not_found") from exc
        if not resolved.is_dir():
            raise ValueError("brain_grant_not_a_directory")
        runtime_dir = (self.workspace_root / RUNTIME_DIR_NAME).resolve()
        if resolved == runtime_dir or runtime_dir in resolved.parents:
            # The runtime directory is Raiker's own machinery, and its documents
            # are already offered as their own roots.
            raise ValueError("brain_grant_is_runtime_directory")
        root_id = grant_root_id(resolved)
        self.store.add_brain_source_grant(
            owner_principal_id, root_id, str(resolved), resolved.name or str(resolved)
        )
        self._record_brain_grant_event("brain_source_folder_granted", root_id, str(resolved))
        return {"ok": True, "root_id": root_id, "path": str(resolved)}

    def _record_brain_grant_event(self: DashboardService, event_type: str, root_id: str, path: str) -> None:
        """Granting Raiker access to a folder is a governed step, so it is one
        the audit log carries — with the path, because the owner needs to see
        exactly what they opened and when."""
        from raiker.events.types import make_event

        EventLogWriter(self.store).append(
            make_event(
                session_id="authz",
                turn_id=None,
                event_type=event_type,
                actor="dashboard_service",
                payload={"root_id": root_id, "path": path},
            )
        )

    # A file picked from the owner's computer arrives as bytes, so adding it is
    # necessarily a copy. That makes consent the whole design: `store_copy` has
    # to be explicitly true, the copy lands in one named place the owner can
    # find and delete, and the alternative — granting the folder and reading it
    # where it is — is offered beside it in the dialog.
    def upload_brain_source_file(
        self: DashboardService, filename: str, content_base64: str, store_copy: bool, *, owner_principal_id: str
    ) -> dict[str, Any]:
        if not store_copy:
            raise ValueError("brain_upload_copy_not_authorised")
        name = Path((filename or "").strip()).name
        if not name or name.startswith(".") or len(name) > 200:
            raise ValueError("brain_upload_invalid_filename")
        if Path(name).suffix.casefold() not in KNOWLEDGE_SOURCE_EXTENSIONS:
            raise ValueError("brain_upload_unsupported_file_type")
        try:
            content = base64.b64decode(content_base64.encode("ascii"), validate=True)
        except (ValueError, UnicodeEncodeError) as exc:
            raise ValueError("brain_upload_invalid_content") from exc
        if not content:
            raise ValueError("brain_upload_empty")
        if len(content) > MAX_KNOWLEDGE_UPLOAD_BYTES:
            raise ValueError("brain_upload_too_large")
        destination_dir = internal_io_path(
            self.workspace_root / RUNTIME_DIR_NAME / "artifacts" / KNOWLEDGE_UPLOAD_DIR
        )
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / name
        if destination.exists():
            stem, suffix = Path(name).stem, Path(name).suffix
            destination = destination_dir / f"{stem}-{uuid4().hex[:6]}{suffix}"
        destination.write_bytes(content)
        stored = f"{ARTIFACTS_ROOT_ID}/{KNOWLEDGE_UPLOAD_DIR}/{destination.name}"
        self.store.add_brain_source(owner_principal_id, stored)
        return {
            "ok": True,
            "path": stored,
            "stored_copy": True,
            "byte_size": len(content),
        }

    def revoke_brain_source_folder(
        self: DashboardService, root_id: str, *, owner_principal_id: str
    ) -> dict[str, Any]:
        cleaned = (root_id or "").strip()
        if not cleaned:
            raise ValueError("invalid_brain_source_path")
        revoked = next(
            (
                grant
                for grant in self.store.list_brain_source_grants(owner_principal_id)
                if str(grant.get("root_id")) == cleaned
            ),
            None,
        )
        self.store.remove_brain_source_grant(owner_principal_id, cleaned)
        self._record_brain_grant_event(
            "brain_source_folder_revoked", cleaned, str((revoked or {}).get("path", ""))
        )
        return {"ok": True, "root_id": cleaned}

    def browse_brain_sources(
        self: DashboardService, raw_path: str = "", *, owner_principal_id: str | None = None
    ) -> dict[str, Any]:
        """Browse one contained directory inside one root, and nothing above it."""
        roots = self._scope_roots(owner_principal_id)
        if not (raw_path or "").strip() or raw_path.strip() in {".", "/"}:
            # There is no path meaning "the workspace", so the empty request
            # answers with the boundary rather than with a listing.
            return {
                "path": "",
                "parent": None,
                "roots": [root.to_dict() for root in roots],
                "children": [],
                "truncated": False,
            }
        try:
            root, relative, path = resolve(roots, raw_path)
        except ScopeError as exc:
            raise ValueError(exc.reason) from exc
        if not path.is_dir():
            raise ValueError("brain_source_not_a_directory")
        try:
            values = sorted(
                path.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold())
            )
        except OSError as exc:
            raise ValueError("brain_source_unreadable") from exc
        base = root.path.resolve() if root.path is not None else path
        children: list[dict[str, Any]] = []
        for child in values[:200]:
            try:
                if child.name in SKIPPED_DIRECTORY_NAMES or child.name.startswith("."):
                    continue
                resolved_child = child.resolve()
                # Re-checked after resolution: a symlink inside a granted folder
                # must not become a way out of it.
                if base not in resolved_child.parents:
                    continue
                children.append(
                    {
                        "name": child.name,
                        "path": scope_path(root, resolved_child.relative_to(base).as_posix()),
                        "kind": "folder" if child.is_dir() else "file",
                        "size_bytes": child.stat().st_size if child.is_file() else None,
                    }
                )
            except OSError:
                continue
        return {
            "path": scope_path(root, relative),
            "parent": parent_scope_path(root, relative),
            "roots": [item.to_dict() for item in roots],
            "children": children,
            "truncated": len(values) > 200,
        }

    def review_brain_source(
        self: DashboardService, raw_path: str, *, owner_principal_id: str | None = None
    ) -> dict[str, Any]:
        """Build a bounded, read-only indexing plan before a source is selected."""
        root, relative, path = self._scoped_source(raw_path, owner_principal_id=owner_principal_id)
        relative_path = scope_path(root, relative)
        # Containment is judged against the root that was selected, not against
        # the workspace: a granted folder lives outside the workspace entirely,
        # and everything under it — and nothing above it — is in scope.
        base = root.path.resolve() if root.path is not None else path
        walk = _walk_source_for_review(path, base)

        warnings: list[str] = []
        if walk.truncated_reason is not None:
            warnings.append(REVIEW_TRUNCATION_REASONS[walk.truncated_reason])
        if walk.total_bytes > 100 * 1024 * 1024:
            warnings.append(
                "The selected source exceeds 100 MB; content will be loaded incrementally as it is needed."
            )
        if walk.unsupported:
            warnings.append(f"{walk.unsupported} unsupported or oversized file(s) will be skipped.")
        return {
            "path": relative_path,
            "kind": "folder" if path.is_dir() else "file",
            "supported_files": walk.supported,
            "unsupported_files": walk.unsupported,
            "total_bytes": walk.total_bytes,
            "examples": [scope_path(root, example) for example in walk.examples],
            "warnings": warnings,
            "review_cap": REVIEW_ACCEPTED_FILE_BUDGET,
            # NEW-MAP-03 — what the walk actually cost, and why it stopped if it
            # did. A partial answer that does not say it is partial is the
            # defect this replaced, one level up.
            "visited_entries": walk.visited,
            "truncated": walk.truncated_reason is not None,
            "truncated_reason": walk.truncated_reason,
        }

    def get_brain_preferences(self: DashboardService, owner_principal_id: str) -> dict[str, Any]:
        return {"settings": self.store.load_brain_preferences(owner_principal_id)}

    def save_brain_preferences(
        self: DashboardService, settings: dict[str, Any], *, owner_principal_id: str
    ) -> dict[str, Any]:
        # REM-MAP-04 adds `viewMode`: which of the two readings of the
        # workspace the owner chose. The allowlist is why it has to be named
        # here — a key the server does not know is dropped in silence, so a
        # preference that looks saved and comes back at its default is the
        # failure mode this list produces when it is not kept in step.
        allowed = {
            "transform", "display", "forces", "groups", "positions", "filters",
            "motion", "viewMode",
        }
        clean = {key: value for key, value in settings.items() if key in allowed}
        serialized = json.dumps(clean, sort_keys=True)
        if len(serialized) > 100_000:
            raise ValueError("brain_preferences_too_large")
        if not all(
            isinstance(value, (dict, list, str, int, float, bool, type(None)))
            for value in clean.values()
        ):
            raise ValueError("invalid_brain_preferences")
        updated_at = self.store.save_brain_preferences(owner_principal_id, clean)
        return {"ok": True, "settings": clean, "updated_at": updated_at}

    def brain_view(self: DashboardService, *, principal_id: str, user_id: str | None) -> BrainView:
        """A redacted, read-only relationship graph for the authenticated user."""
        sessions = self.list_sessions(limit=100, user_id=user_id)
        session_ids = {session.session_id for session in sessions}
        tasks = self.list_tasks(user_id=user_id)
        task_ids = {task.task_id for task in tasks}
        tasks_by_id = {task.task_id: task for task in tasks}
        events = [
            self._event_view(row)
            for row in self.store.list_event_index(limit=250)
            if str(row.get("session_id", "")) in session_ids
        ]
        approval_rows = [
            row
            for row in self.store.list_approvals()
            if str(row.get("session_id", "")) in session_ids
        ]
        approval_queue = self.store.suspended_turn_queue_positions(
            [str(row.get("approval_id", "")) for row in approval_rows]
        )
        approvals = [self._approval_view(row, queue=approval_queue) for row in approval_rows]
        subagents = [
            row
            for row in self.store.list_subagent_contracts()
            if str(row.get("parent_task_id", "")) in task_ids
        ]
        memories = list_memory(
            workspace_root=self.workspace_root,
            store=self.store,
            limit=100,
            owner_principal_id=principal_id,
        )
        backups = [
            row
            for row in self.store.list_backup_manifests()
            if str(row.get("created_by", "")) == principal_id
        ]
        nodes = [BrainNodeView(f"principal:{principal_id}", "user", "You", "active")]
        edges: list[BrainEdgeView] = []
        # BUG-218 — projects, which the map never drew even though the colour
        # for them was already defined. A session belongs to one, and "which
        # work belongs together" is the first question a map of your work is
        # asked.
        projects_by_id = {
            str(row["project_id"]): row
            for row in self.store.list_projects(user_id=user_id)
            if not row.get("is_archived")
        }
        used_projects: set[str] = set()

        for session in sessions:
            node_id = f"session:{session.session_id}"
            # BUG-218 — a Chat and a Build session were the same green dot. They
            # are different work and the store already knows which is which;
            # `origin` was simply never read here.
            origin = (getattr(session, "origin", "") or "chat").lower()
            node_type = SESSION_NODE_TYPES.get(origin, "session")
            nodes.append(
                BrainNodeView(
                    node_id,
                    node_type,
                    session.title or f"Untitled {SESSION_LABELS.get(origin, 'session')}",
                    session.status,
                    SESSION_LABELS.get(origin, origin),
                )
            )
            project_id = str(getattr(session, "project_id", "") or "")
            if project_id and project_id in projects_by_id:
                used_projects.add(project_id)
                edges.append(BrainEdgeView(f"project:{project_id}", node_id, "contains"))
            else:
                edges.append(BrainEdgeView(f"principal:{principal_id}", node_id, "owns"))
        for project_id in sorted(used_projects):
            row = projects_by_id[project_id]
            nodes.append(
                BrainNodeView(
                    f"project:{project_id}",
                    "project",
                    str(row.get("name") or "Untitled project"),
                    "active",
                    str(row.get("path") or ""),
                )
            )
            edges.append(
                BrainEdgeView(f"principal:{principal_id}", f"project:{project_id}", "owns")
            )
        for task in tasks:
            node_id = f"task:{task.task_id}"
            nodes.append(
                BrainNodeView(
                    node_id,
                    "task",
                    task.title or "Untitled task",
                    task.status,
                    _task_detail(task),
                    task.progress_percent,
                )
            )
            edges.append(
                BrainEdgeView(
                    f"session:{task.session_id}", node_id, "tracks", task.status == "running"
                )
            )
            # Only work that is actually waiting for its slot is scheduled work.
            # A task that has already run keeps its `scheduled_at`, so listing it
            # here showed a finished or blocked run as "Waiting" indefinitely.
            if task.scheduled_at and task.status == "queued":
                schedule_id = f"schedule:{task.task_id}"
                nodes.append(
                    BrainNodeView(
                        schedule_id, "schedule", "Scheduled work", "waiting", task.scheduled_at
                    )
                )
                edges.append(BrainEdgeView(schedule_id, node_id, "starts"))
        for agent in subagents:
            node_id = f"agent:{agent['subagent_id']}"
            parent_task = tasks_by_id.get(str(agent["parent_task_id"]))
            nodes.append(
                BrainNodeView(
                    node_id,
                    "agent",
                    str(agent["name"]),
                    str(agent["status"]),
                    parent_task.title if parent_task else None,
                )
            )
            edges.append(
                BrainEdgeView(
                    f"task:{agent['parent_task_id']}",
                    node_id,
                    "delegates",
                    str(agent["status"]) == "running",
                )
            )
        # BUG-218 — one node per *tool*, not one per event: most event-index
        # rows typed `tool` are lifecycle bookkeeping, and a map of them hides
        # the chats, context and files underneath.
        #
        # `tool_actions` is where tools actually are, aggregated per session, so
        # a session that ran `read_file` forty times is one node saying forty
        # rather than forty nodes saying nothing.
        for use in self.store.summarize_session_tool_use(
            sorted(session_ids), owner_principal_id=principal_id
        ):
            session_key = str(use["session_id"])
            tool_name = str(use["tool_name"])
            node_id = f"tool:{session_key}:{tool_name}"
            uses = int(use["uses"] or 0)
            failures = int(use["failures"] or 0)
            nodes.append(
                BrainNodeView(
                    node_id,
                    "tool",
                    TOOL_LABELS.get(
                        tool_name, TOOL_LABEL_BY_TOOL.get(tool_name, tool_name.replace("_", " "))
                    ),
                    "failed" if failures and failures == uses else "used",
                    f"{uses} use{'' if uses == 1 else 's'}"
                    + (f", {failures} failed" if failures else ""),
                )
            )
            edges.append(BrainEdgeView(f"session:{session_key}", node_id, "used"))

        # BUG-218 — what the answers actually came from. `turn_sources` is the
        # citation record and the map never read it, so a map of the owner's
        # work showed no context at all. A source is drawn as the thing it is:
        # a cited file is a file node, a fetched page is a source node.
        context_nodes: set[str] = set()
        for cited in self.store.list_session_context_sources(
            sorted(session_ids), principal_id=principal_id
        ):
            locator = str(cited["locator"] or "")
            title = str(cited["title"] or "") or locator or str(cited["kind"])
            kind = str(cited["kind"] or "")
            # Identity is the thing cited, not the citation: the same file read
            # in three sessions is one node with three edges, which is the
            # relationship the map exists to show.
            node_id = f"context:{kind}:{locator or title}"
            # Emitted once even when several sessions cite it — the shared node
            # with an edge per session *is* the relationship this map exists to
            # show, and two nodes carrying one id would leave the force layout
            # drawing the same file twice.
            if node_id not in context_nodes:
                context_nodes.add(node_id)
                # MEM-14 — a citation whose file has since been deleted is drawn
                # as `missing` rather than omitted. Obsidian keeps its
                # unresolved links for the same reason: "this answer rested on
                # something that is gone" is more useful than a tidier map, and
                # dropping the node would leave the work looking ungrounded
                # instead of grounded in something that has moved.
                status = reference_resolution(
                    self.workspace_root,
                    kind=kind,
                    locator=locator,
                    attachment_id=str(cited["attachment_id"] or ""),
                    tool_name=str(cited["tool_name"] or ""),
                )
                nodes.append(
                    BrainNodeView(
                        node_id,
                        CONTEXT_NODE_TYPES.get(kind, "source"),
                        title[:80],
                        "missing" if status == "unresolved" else "cited",
                        f"{kind}" + (f" · via {cited['tool_name']}" if cited["tool_name"] else ""),
                    )
                )
            edges.append(BrainEdgeView(f"session:{cited['session_id']}", node_id, "grounded_in"))

        # BUG-218 — files the owner attached to a conversation. Metadata only;
        # the stored bytes are never read to draw a node.
        for attached in self.store.list_session_attached_files(
            sorted(session_ids), owner_principal_id=principal_id
        ):
            node_id = f"attachment:{attached['attachment_id']}"
            nodes.append(
                BrainNodeView(
                    node_id,
                    "file",
                    str(attached["filename"]),
                    "attached",
                    str(attached["media_type"]),
                )
            )
            edges.append(BrainEdgeView(f"session:{attached['session_id']}", node_id, "attached"))

        event_ids = {event.event_id for event in events}
        # One lookup for every memory whose source event is outside the window,
        # rather than one per memory.
        distant = self.store.sessions_for_events(
            [m.source_event_id for m in memories if m.source_event_id not in event_ids]
        )
        for memory in memories:
            node_id = f"memory:{memory.memory_id}"
            nodes.append(
                BrainNodeView(
                    node_id, "memory", f"Memory · {memory.scope}", "available", memory.sensitivity
                )
            )
            # BUG-218 — a memory whose source event fell outside the event
            # window still anchors to the work that produced it: the session is
            # the durable fallback, never an orphaned node.
            if memory.source_event_id in event_ids:
                edges.append(
                    BrainEdgeView(f"event:{memory.source_event_id}", node_id, "remembered")
                )
            elif distant.get(memory.source_event_id, "") in session_ids:
                edges.append(
                    BrainEdgeView(
                        f"session:{distant[memory.source_event_id]}", node_id, "remembered"
                    )
                )
            else:
                # Neither reachable: the owner still owns it, and an anchored
                # node is more honest than a floating one.
                edges.append(BrainEdgeView(f"principal:{principal_id}", node_id, "remembers"))
        # MEM-06 — reviewed entity facts are first-class graph records. Every
        # relation remains connected to the approved memory that evidenced it;
        # an edge can therefore be inspected instead of trusted as inference.
        entity_nodes: set[str] = set()
        memory_node_ids = {f"memory:{memory.memory_id}" for memory in memories}
        for relationship in self.store.list_memory_relationships(principal_id):
            subject = f"entity:{relationship['subject_entity_id']}"
            object_id = f"entity:{relationship['object_entity_id']}"
            if subject not in entity_nodes:
                entity_nodes.add(subject)
                nodes.append(
                    BrainNodeView(
                        subject,
                        "entity",
                        str(relationship["subject_name"]),
                        "reviewed",
                        str(relationship["subject_type"]),
                    )
                )
            if object_id not in entity_nodes:
                entity_nodes.add(object_id)
                nodes.append(
                    BrainNodeView(
                        object_id,
                        "entity",
                        str(relationship["object_name"]),
                        "reviewed",
                        str(relationship["object_type"]),
                    )
                )
            edges.append(
                BrainEdgeView(
                    subject,
                    object_id,
                    str(relationship["predicate"]),
                    False,
                    str(relationship["relationship_id"]),
                    str(relationship["evidence_memory_id"]),
                    True,
                )
            )
            evidence = f"memory:{relationship['evidence_memory_id']}"
            if evidence in memory_node_ids:
                edges.append(BrainEdgeView(evidence, subject, "evidence_for"))

        for approval in approvals:
            node_id = f"approval:{approval.approval_id}"
            nodes.append(
                BrainNodeView(
                    node_id, "approval", approval.tool_name, approval.status, approval.capability
                )
            )
            edges.append(BrainEdgeView(f"session:{approval.session_id}", node_id, "requires"))
        for backup in backups:
            node_id = f"backup:{backup['manifest_id']}"
            nodes.append(
                BrainNodeView(
                    node_id,
                    "backup",
                    "Backup",
                    "verified" if backup.get("restore_verified_at") else "catalogued",
                )
            )
            edges.append(BrainEdgeView(f"principal:{principal_id}", node_id, "backs_up"))
        # Sources are addressed within the Knowledge Map's boundary, so a stored
        # source that no longer resolves — its grant revoked, its folder gone —
        # simply drops out of the graph rather than being drawn from a stale path.
        roots = self._scope_roots(principal_id)
        for source in self.store.list_brain_sources(principal_id):
            try:
                source_root, relative, path = resolve(roots, source)
            except ScopeError:
                continue
            relative_path = scope_path(source_root, relative)
            base = source_root.path.resolve() if source_root.path is not None else path
            source_id = f"source:{relative_path}"
            source_type = "folder" if path.is_dir() else "file"
            nodes.append(
                BrainNodeView(
                    source_id, source_type, path.name or relative_path, "selected", relative_path
                )
            )
            edges.append(BrainEdgeView(f"principal:{principal_id}", source_id, "added"))
            if path.is_dir():
                try:
                    children = sorted(path.iterdir(), key=lambda child: child.name.casefold())[:100]
                except OSError:
                    children = []
                for child in children:
                    child_path = scope_path(
                        source_root, child.resolve().relative_to(base).as_posix()
                    )
                    child_id = f"source:{child_path}"
                    child_type = "folder" if child.is_dir() else "file"
                    nodes.append(
                        BrainNodeView(child_id, child_type, child.name, "available", child_path)
                    )
                    edges.append(BrainEdgeView(source_id, child_id, "contains"))
        return BrainView(utc_now(), tuple(nodes), tuple(edges))
