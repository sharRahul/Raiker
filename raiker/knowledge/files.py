"""Contained storage for original, untrusted managed knowledge files."""

from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import TYPE_CHECKING, Literal

from raiker.contracts.ids import utc_now
from raiker.storage.internal_paths import internal_io_path

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


ManagedFileScopeKind = Literal["memory", "project"]


class ManagedFileError(ValueError):
    """A stable managed-file boundary failure."""


@dataclass(frozen=True)
class ManagedFileScope:
    kind: ManagedFileScopeKind
    project_id: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"memory", "project"}:
            raise ManagedFileError("managed_file_scope_invalid")
        if self.kind == "memory" and self.project_id is not None:
            raise ManagedFileError("managed_file_scope_invalid")
        if self.kind == "project" and not self.project_id:
            raise ManagedFileError("managed_file_scope_invalid")


@dataclass(frozen=True)
class ManagedFileRecord:
    file_id: str
    owner_principal_id: str
    scope_kind: ManagedFileScopeKind
    project_id: str | None
    relative_path: str
    media_type: str
    size_bytes: int
    content_hash: str
    index_state: str
    index_error: str | None
    created_at: str
    updated_at: str
    retired_at: str | None

    @classmethod
    def from_row(cls, row: dict[str, object]) -> ManagedFileRecord:
        return cls(
            file_id=str(row["file_id"]),
            owner_principal_id=str(row["owner_principal_id"]),
            scope_kind=str(row["scope_kind"]),  # type: ignore[arg-type]
            project_id=str(row["project_id"]) if row["project_id"] is not None else None,
            relative_path=str(row["relative_path"]),
            media_type=str(row["media_type"]),
            size_bytes=int(str(row["size_bytes"])),
            content_hash=str(row["content_hash"]),
            index_state=str(row["index_state"]),
            index_error=str(row["index_error"]) if row["index_error"] is not None else None,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            retired_at=str(row["retired_at"]) if row["retired_at"] is not None else None,
        )

    def scope(self) -> ManagedFileScope:
        """The logical scope this file belongs to, rebuilt from its own row."""
        return ManagedFileScope(self.scope_kind, self.project_id)


class ManagedFileService:
    """Write imported bytes only below the owner's declared managed scope."""

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.store = store

    def import_file(
        self,
        scope: ManagedFileScope,
        relative_path: str,
        data: bytes,
        media_type: str,
        owner_principal_id: str,
    ) -> ManagedFileRecord:
        relative = self._relative_path(relative_path)
        root = self.scope_root(scope, owner_principal_id)
        destination = self.contained_destination(root, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination = self.contained_destination(root, relative)
        temporary = destination.with_name(f".{destination.name}.{secrets.token_hex(8)}.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())

            def publish() -> None:
                if destination.exists() or destination.is_symlink():
                    destination.unlink()
                temporary.replace(destination)

            now = utc_now()
            file_id = f"mfile_{secrets.token_hex(16)}"
            published = self.store.publish_managed_file_atomic(
                file_id=file_id,
                owner_principal_id=owner_principal_id,
                scope_kind=scope.kind,
                project_id=scope.project_id,
                relative_path=relative,
                media_type=media_type,
                size_bytes=len(data),
                content_hash=hashlib.sha256(data).hexdigest(),
                index_state="queued",
                index_error=None,
                created_at=now,
                updated_at=now,
                publish=publish,
            )
            if not published:
                raise ManagedFileError("managed_file_already_exists")
        except OSError as exc:
            raise ManagedFileError("managed_file_write_failed") from exc
        finally:
            if temporary.exists():
                temporary.unlink(missing_ok=True)
        record = self.store.get_managed_file(file_id, owner_principal_id)
        if record is None:  # pragma: no cover - the insert is synchronous
            raise RuntimeError("managed_file_insert_missing")
        return ManagedFileRecord.from_row(record)

    def scope_root(self, scope: ManagedFileScope, owner_principal_id: str) -> Path:
        runtime_root = internal_io_path(self.workspace_root / ".raiker")
        self._require_within(runtime_root.resolve(), internal_io_path(self.workspace_root).resolve())
        if self.store.get_principal(owner_principal_id) is None:
            raise ManagedFileError("managed_file_scope_not_found")
        if scope.kind == "memory":
            root = internal_io_path(runtime_root / "memory-files")
        else:
            owner_user_id = self.store.principal_user_id(owner_principal_id)
            if owner_user_id is None:
                raise ManagedFileError("managed_file_scope_not_found")
            project = self.store.load_project(scope.project_id or "", user_id=owner_user_id)
            if project is None:
                raise ManagedFileError("managed_file_scope_not_found")
            attached = self._attached_root(project, owner_principal_id)
            if attached is not None:
                # The owner's own folder. Import, extraction, chunking and
                # retirement all follow it with no other change — the one thing
                # that differs is who owns the bytes, which `owns_bytes` below
                # is what answers.
                return attached
            projects_root = internal_io_path(runtime_root / "projects")
            self._require_within(projects_root.resolve(), runtime_root.resolve())
            root = self._managed_project_root(str(project["root_subpath"]), projects_root)
            self._require_within(root.resolve(), projects_root.resolve())

        self._require_within(root.resolve(), runtime_root.resolve())
        root.mkdir(parents=True, exist_ok=True)
        return root

    def delete_file(self, file_id: str, owner_principal_id: str) -> ManagedFileRecord:
        """Remove one file's bytes and retire its catalogue row.

        The path is re-derived from the scope, never taken from the stored
        string, so a tampered row cannot direct a delete outside the managed
        root. A missing file on disk is not an error -- the catalogue row is
        still retired, which is what retrieval reads.
        """
        row = self.store.get_managed_file(file_id, owner_principal_id)
        if row is None:
            raise ManagedFileError("managed_file_not_found")
        record = ManagedFileRecord.from_row(row)
        if record.retired_at is not None:
            raise ManagedFileError("managed_file_retired")
        root = self.scope_root(record.scope(), owner_principal_id)
        destination = self.contained_destination(root, record.relative_path)
        if self.owns_bytes(record.scope(), owner_principal_id):
            try:
                destination.unlink(missing_ok=True)
            except OSError as exc:
                raise ManagedFileError("managed_file_delete_failed") from exc
        self.store.retire_managed_file(file_id, owner_principal_id)
        reloaded = self.store.get_managed_file(file_id, owner_principal_id)
        if reloaded is None:  # pragma: no cover - the row was read moments ago
            raise ManagedFileError("managed_file_not_found")
        return ManagedFileRecord.from_row(reloaded)

    def owns_bytes(self, scope: ManagedFileScope, owner_principal_id: str) -> bool:
        """Whether removing a catalogue row should remove the file too.

        Raiker wrote a managed file's bytes, so retiring it takes them with it.
        The bytes under an attached root are the owner's, discovered rather than
        imported: retiring the row must drop only the projection, or reindexing
        an edited file would delete the file that was edited.
        """
        if scope.kind != "project":
            return True
        owner_user_id = self.store.principal_user_id(owner_principal_id)
        project = self.store.load_project(scope.project_id or "", user_id=owner_user_id)
        return self._attached_root(project, owner_principal_id) is None

    def _attached_root(
        self, project: dict[str, object] | None, owner_principal_id: str
    ) -> Path | None:
        """This project's attached folder, or nothing if it has none."""
        from raiker.control.project_roots import resolve_project_root

        if project is None:
            return None
        root = resolve_project_root(
            project, self.store.list_brain_source_grants(owner_principal_id), self.workspace_root
        )
        if root.kind != "attached":
            return None
        if root.path is None or root.missing:
            raise ManagedFileError("managed_file_scope_not_found")
        # Normalised the same way every other scope root is, so the containment
        # check below compares two paths of the same shape. On Windows a bare
        # path and its extended-length form are not `relative_to` each other,
        # which would make every file in an attached root look like an escape.
        return internal_io_path(root.path)

    def _managed_project_root(self, root_subpath: str, projects_root: Path) -> Path:
        """Resolve legacy `projects/<slug>` rows into Task 2's destination."""

        parts = root_subpath.replace("\\", "/").split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ManagedFileError("managed_file_path_outside_scope")
        if parts[0] == "projects":
            relative_parts = parts[1:]
        elif len(parts) >= 3 and parts[:2] == [".raiker", "projects"]:
            relative_parts = parts[2:]
        else:
            raise ManagedFileError("managed_file_path_outside_scope")
        if not relative_parts:
            raise ManagedFileError("managed_file_path_outside_scope")
        return internal_io_path(projects_root.joinpath(*relative_parts))

    @staticmethod
    def _relative_path(relative_path: str) -> str:
        raw = str(relative_path)
        windows = PureWindowsPath(raw)
        if (
            not raw
            or raw.startswith(("/", "\\"))
            or windows.is_absolute()
            or windows.drive
        ):
            raise ManagedFileError("managed_file_path_outside_scope")
        normalized = raw.replace("\\", "/")
        parts = normalized.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ManagedFileError("managed_file_path_outside_scope")
        return "/".join(parts)

    def contained_destination(self, root: Path, relative: str) -> Path:
        destination = internal_io_path(root / Path(relative))
        self._require_within(destination.resolve(), root.resolve())
        return destination

    @staticmethod
    def _require_within(candidate: Path, root: Path) -> None:
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ManagedFileError("managed_file_path_outside_scope") from exc
