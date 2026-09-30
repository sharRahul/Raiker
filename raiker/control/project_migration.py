"""Moving legacy project folders under the workspace's project root, safely and repeatably."""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from raiker.auth.app_key import ensure_app_key
from raiker.control.project_paths import (
    LEGACY_PROJECT_ROOT as _LEGACY_PROJECT_ROOT,
)
from raiker.control.project_paths import (
    MANAGED_PROJECT_ROOT as _MANAGED_PROJECT_ROOT,
)
from raiker.control.project_paths import (
    contained_project_root as _contained_project_root,
)
from raiker.control.project_paths import (
    project_root_parts as _project_root_parts,
)
from raiker.control.views.projects import ProjectRootMigrationReport
from raiker.storage.sqlite import SQLiteStore


def _default_root_label(row: dict[str, Any]) -> str:
    """A short name for the project's root, without resolving the grant.

    The grant's path arrives on the row from `list_projects`, so naming an
    attached folder costs no extra query. A managed project falls back to its
    subpath's last segment, which is its slug.
    """
    granted = str(row.get("root_grant_path") or "")
    if granted:
        return Path(granted).name or granted
    subpath = str(row.get("root_subpath") or "")
    return subpath.rsplit("/", 1)[-1] if subpath else ""


def _copy_project_tree_exclusive(source: Path, destination: Path) -> None:
    """Copy a tree into an exclusively reserved directory without replacement."""
    for child in source.iterdir():
        target = destination / child.name
        if child.is_symlink():
            raise OSError("project_root_symlink_not_migrated")
        if child.is_dir():
            target.mkdir()
            _copy_project_tree_exclusive(child, target)
        elif child.is_file():
            with child.open("rb") as reader, target.open("xb") as writer:
                shutil.copyfileobj(reader, writer)
            shutil.copystat(child, target, follow_symlinks=False)
        else:
            raise OSError("project_root_special_file_not_migrated")


_PROJECT_ROOT_MIGRATION_DIR = "project-migrations"


_PROJECT_ROOT_STAGE_TREE = "tree"


_PROJECT_ROOT_STAGE_COMPLETE = ".complete"


def _copy_project_tree_resuming(source: Path, destination: Path) -> None:
    """Complete a reserved publication without replacing any existing entry."""
    for child in source.iterdir():
        target = destination / child.name
        if child.is_symlink():
            raise OSError("project_root_symlink_not_migrated")
        if child.is_dir():
            if target.is_symlink() or (target.exists() and not target.is_dir()):
                raise FileExistsError(target)
            if not target.exists():
                target.mkdir()
            _copy_project_tree_resuming(child, target)
        elif child.is_file():
            if target.exists() or target.is_symlink():
                if not target.is_file() or not _same_file(child, target):
                    raise FileExistsError(target)
                continue
            with child.open("rb") as reader, target.open("xb") as writer:
                shutil.copyfileobj(reader, writer)
            shutil.copystat(child, target, follow_symlinks=False)
        else:
            raise OSError("project_root_special_file_not_migrated")


def _same_file(left: Path, right: Path) -> bool:
    if left.stat().st_size != right.stat().st_size:
        return False
    with left.open("rb") as first, right.open("rb") as second:
        while first_chunk := first.read(64 * 1024):
            if first_chunk != second.read(len(first_chunk)):
                return False
        return not second.read(1)


def _same_project_tree(left: Path, right: Path) -> bool:
    """Return true only when two regular project trees have identical content."""
    try:
        left_children = sorted(left.iterdir(), key=lambda child: child.name)
        right_children = sorted(right.iterdir(), key=lambda child: child.name)
    except OSError:
        return False
    if [child.name for child in left_children] != [child.name for child in right_children]:
        return False
    for left_child, right_child in zip(left_children, right_children, strict=True):
        if left_child.is_symlink() or right_child.is_symlink():
            return False
        if left_child.is_dir():
            if not right_child.is_dir() or not _same_project_tree(left_child, right_child):
                return False
        elif left_child.is_file():
            if not right_child.is_file() or not _same_file(left_child, right_child):
                return False
        else:
            return False
    return True


def _write_reservation(path: Path, reservation: dict[str, str]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(reservation, sort_keys=True))
        handle.flush()
        os.fsync(handle.fileno())


def _read_reservation(path: Path) -> dict[str, str] | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return (
        data
        if isinstance(data, dict) and all(isinstance(value, str) for value in data.values())
        else None
    )


def _project_migration_area(workspace: Path) -> Path:
    """Return Raiker-owned staging storage, never a project file namespace."""
    runtime = workspace / ".raiker"
    area = runtime / _PROJECT_ROOT_MIGRATION_DIR
    for directory in (runtime, area):
        if _is_reparse_point(directory) or (directory.exists() and not directory.is_dir()):
            raise OSError("project_migration_storage_invalid")
    area.mkdir(parents=True, exist_ok=True)
    if _is_reparse_point(area) or not area.is_dir():
        raise OSError("project_migration_storage_invalid")
    return area


def _is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


@dataclass(frozen=True)
class _SourceIdentity:
    """One reading of a project tree, in the two forms the migration needs.

    ``strict`` answers "is this tree still exactly what it was?". ``moved``
    answers the same question about a tree that has just been renamed, and
    differs in exactly one field: a rename bumps the renamed directory's own
    ``st_ctime_ns`` while leaving its inode, size, mtime and every child
    untouched, so the strict form can never hold after a move. Everything that
    would betray a swapped-in tree — the device and inode, the mtime, and every
    child's metadata and bytes — is in both.
    """

    strict: str
    moved: str


def _source_identity(source: Path) -> _SourceIdentity | None:
    """Return a stable content identity for a regular project tree."""
    try:
        before = source.stat(follow_symlinks=False)
    except OSError:
        return None
    if source.is_symlink() or not source.is_dir():
        return None
    digest = hashlib.sha256()
    moved_digest = hashlib.sha256()

    def metadata(info: os.stat_result, *, ctime: bool = True) -> bytes:
        fields = f"{info.st_dev}:{info.st_ino}:{info.st_size}:{info.st_mtime_ns}"
        if ctime:
            fields += f":{info.st_ctime_ns}"
        return f"{fields}\0".encode()

    def include_metadata(kind: bytes, relative: Path, info: os.stat_result) -> None:
        entry = kind + b"\0" + relative.as_posix().encode() + b"\0" + metadata(info)
        digest.update(entry)
        moved_digest.update(entry)

    # The root is the one entry the two readings disagree about, because it is
    # the one inode a rename of this tree touches.
    root_header = b"directory\0.\0"
    digest.update(root_header + metadata(before))
    moved_digest.update(root_header + metadata(before, ctime=False))

    def include(directory: Path, relative: Path) -> bool:
        try:
            children = sorted(directory.iterdir(), key=lambda child: child.name)
        except OSError:
            return False
        for child in children:
            child_relative = relative / child.name
            if child.is_symlink():
                return False
            if child.is_dir():
                try:
                    child_before = child.stat(follow_symlinks=False)
                except OSError:
                    return False
                include_metadata(b"directory", child_relative, child_before)
                if not include(child, child_relative):
                    return False
                try:
                    child_after = child.stat(follow_symlinks=False)
                except OSError:
                    return False
                if (
                    child_before.st_dev,
                    child_before.st_ino,
                    child_before.st_size,
                    child_before.st_mtime_ns,
                    child_before.st_ctime_ns,
                ) != (
                    child_after.st_dev,
                    child_after.st_ino,
                    child_after.st_size,
                    child_after.st_mtime_ns,
                    child_after.st_ctime_ns,
                ):
                    return False
                continue
            if not child.is_file():
                return False
            try:
                child_before = child.stat(follow_symlinks=False)
                include_metadata(b"file", child_relative, child_before)
                with child.open("rb") as reader:
                    while chunk := reader.read(64 * 1024):
                        digest.update(chunk)
                        moved_digest.update(chunk)
                child_after = child.stat(follow_symlinks=False)
            except OSError:
                return False
            if (
                child_before.st_dev,
                child_before.st_ino,
                child_before.st_size,
                child_before.st_mtime_ns,
                child_before.st_ctime_ns,
            ) != (
                child_after.st_dev,
                child_after.st_ino,
                child_after.st_size,
                child_after.st_mtime_ns,
                child_after.st_ctime_ns,
            ):
                return False
        return True

    if not include(source, Path(".")):
        return None
    try:
        after = source.stat(follow_symlinks=False)
    except OSError:
        return None
    if (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        return None
    return _SourceIdentity(digest.hexdigest(), moved_digest.hexdigest())


def _source_is_unchanged(source: Path, identity: _SourceIdentity) -> bool:
    current = _source_identity(source)
    return current is not None and current.strict == identity.strict


def _retain_migrated_source(
    workspace: Path, source: Path, identity: _SourceIdentity, migration_area: Path
) -> Path | None:
    """Retain a verified legacy tree as recoverable, inactive migration residue."""
    if not _source_is_unchanged(source, identity):
        return None
    try:
        if _project_migration_area(workspace) != migration_area:
            return None
    except OSError:
        return None
    residue = migration_area / f"residue-{uuid4().hex}"
    try:
        source.rename(residue)
    except OSError:
        return None
    # The rename is the one change the strict form cannot survive, so the residue
    # is checked against the reading that tolerates exactly that — and against
    # `identity`, taken before the migration published, so a tree swapped in
    # after the check above is still caught here and put back where it was.
    moved = _source_identity(residue)
    if moved is None or moved.moved != identity.moved:
        if not source.exists():
            with contextlib.suppress(OSError):
                residue.rename(source)
        return None
    return residue


def _stage_project_tree(source: Path, migration_area: Path) -> tuple[Path, Path]:
    stage = migration_area / uuid4().hex
    stage.mkdir()
    tree = stage / _PROJECT_ROOT_STAGE_TREE
    tree.mkdir()
    if source.exists():
        _copy_project_tree_exclusive(source, tree)
    complete = stage / _PROJECT_ROOT_STAGE_COMPLETE
    complete.touch(exist_ok=False)
    return stage, tree


def _new_reservation(
    workspace: Path, project_id: str, raw_root: str, stage_name: str
) -> dict[str, str]:
    reservation = {
        "project_id": project_id,
        "raw_root": raw_root,
        "stage_name": stage_name,
        "reservation_id": hmac.new(
            ensure_app_key(workspace), f"{project_id}\0{raw_root}".encode(), hashlib.sha256
        ).hexdigest(),
    }
    payload = json.dumps(reservation, separators=(",", ":"), sort_keys=True).encode()
    reservation["authentication"] = hmac.new(
        ensure_app_key(workspace), payload, hashlib.sha256
    ).hexdigest()
    return reservation


def _reservation_tree(
    workspace: Path,
    migration_area: Path,
    reservation: dict[str, str],
    project_id: str,
    raw_root: str,
) -> tuple[Path, Path] | None:
    if reservation.get("project_id") != project_id or reservation.get("raw_root") != raw_root:
        return None
    reservation_id = reservation.get("reservation_id", "")
    authentication = reservation.get("authentication", "")
    if not reservation_id or not authentication:
        return None
    payload = json.dumps(
        {
            "project_id": project_id,
            "raw_root": raw_root,
            "stage_name": reservation.get("stage_name", ""),
            "reservation_id": reservation_id,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    expected = hmac.new(ensure_app_key(workspace), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(authentication, expected):
        return None
    stage_name = reservation.get("stage_name", "")
    if len(stage_name) != 32 or any(char not in "0123456789abcdef" for char in stage_name):
        return None
    stage = migration_area / stage_name
    tree = stage / _PROJECT_ROOT_STAGE_TREE
    if stage.is_symlink() or tree.is_symlink() or not stage.is_dir() or not tree.is_dir():
        return None
    if not (stage / _PROJECT_ROOT_STAGE_COMPLETE).is_file():
        return None
    return stage, tree


def _find_reservation(
    workspace: Path, migration_area: Path, project_id: str, raw_root: str
) -> tuple[dict[str, str], Path, Path] | None:
    candidates: list[tuple[dict[str, str], Path, Path]] = []
    for sidecar in migration_area.glob("*.json"):
        reservation = _read_reservation(sidecar)
        if reservation is None:
            continue
        staged = _reservation_tree(workspace, migration_area, reservation, project_id, raw_root)
        if staged is not None:
            candidates.append((reservation, *staged))
    if len(candidates) > 1:
        raise OSError("project_migration_reservation_ambiguous")
    return candidates[0] if candidates else None


def migrate_project_roots(workspace_root: Path, store: SQLiteStore) -> ProjectRootMigrationReport:
    """Move legacy ``projects/<slug>`` folders below `.raiker/projects` safely.

    A row changes only after its source and destination have passed containment
    validation. Existing destination folders are never merged or replaced.
    """
    workspace = Path(workspace_root).resolve()
    migrated: list[str] = []
    conflicts: list[str] = []
    unchanged: list[str] = []
    retained_residues: list[str] = []
    projects = store.list_projects()
    managed_roots: list[tuple[str, ...]] = [
        parsed[1]
        for project in projects
        if (parsed := _project_root_parts(str(project.get("root_subpath") or "")))
        and parsed[0] == _MANAGED_PROJECT_ROOT
    ]

    def migration_order(project: dict[str, Any]) -> tuple[int, int]:
        parsed = _project_root_parts(str(project.get("root_subpath") or ""))
        if parsed is not None and parsed[0] == _LEGACY_PROJECT_ROOT:
            return 0, len(parsed[1])
        return 1, 0

    for project in sorted(projects, key=migration_order):
        project_id = str(project["project_id"])
        raw_root = str(project.get("root_subpath") or "")
        source_info = _contained_project_root(workspace, raw_root)
        if source_info is None:
            conflicts.append(project_id)
            continue
        kind, relative, source = source_info
        if kind == _MANAGED_PROJECT_ROOT:
            unchanged.append(project_id)
            continue
        destination_subpath = "/".join((_MANAGED_PROJECT_ROOT, *relative))
        destination_info = _contained_project_root(workspace, destination_subpath)
        if destination_info is None:  # defensive: it is constructed above
            conflicts.append(project_id)
            continue
        destination = destination_info[2]
        was_moved_with_parent = any(
            len(relative) > len(parent) and relative[: len(parent)] == parent
            for parent in managed_roots
        )
        if source.is_symlink() or destination.is_symlink():
            conflicts.append(project_id)
            continue
        try:
            migration_area = _project_migration_area(workspace)
        except OSError:
            conflicts.append(project_id)
            continue
        try:
            owned_reservation = _find_reservation(workspace, migration_area, project_id, raw_root)
        except OSError:
            conflicts.append(project_id)
            continue
        nested_duplicate = (
            was_moved_with_parent
            and source.exists()
            and destination.exists()
            and destination.is_dir()
            and _same_project_tree(source, destination)
        )
        if destination.exists() and (
            destination.is_symlink()
            or not destination.is_dir()
            or (source.exists() and owned_reservation is None and not nested_duplicate)
            or (not source.exists() and owned_reservation is None and not was_moved_with_parent)
        ):
            conflicts.append(project_id)
            continue
        if source.exists() and not source.is_dir():
            conflicts.append(project_id)
            continue
        source_identity = _source_identity(source) if source.exists() else None
        if source.exists() and source_identity is None:
            conflicts.append(project_id)
            continue

        def publish(
            destination: Path = destination,
            destination_subpath: str = destination_subpath,
            source: Path = source,
            migration_area: Path = migration_area,
            was_moved_with_parent: bool = was_moved_with_parent,
            project_id: str = project_id,
            raw_root: str = raw_root,
        ) -> None:
            source_revalidated = _contained_project_root(workspace, raw_root)
            if (
                source_revalidated is None
                or source_revalidated[0] != _LEGACY_PROJECT_ROOT
                or source_revalidated[2] != source
                or source.is_symlink()
            ):
                raise OSError("project_root_source_invalid")
            destination.parent.mkdir(parents=True, exist_ok=True)
            revalidated = _contained_project_root(workspace, destination_subpath)
            if revalidated is None or revalidated[2] != destination:
                raise OSError("project_root_destination_invalid")
            if _project_migration_area(workspace) != migration_area:
                raise OSError("project_migration_storage_invalid")
            if destination.exists():
                if destination.is_symlink() or not destination.is_dir():
                    raise FileExistsError(destination)
                staged = _find_reservation(workspace, migration_area, project_id, raw_root)
                if staged is not None:
                    _copy_project_tree_resuming(
                        source if source.exists() else staged[2], destination
                    )
                    return
                if (
                    was_moved_with_parent
                    and source.exists()
                    and _same_project_tree(source, destination)
                ):
                    return
                if was_moved_with_parent and not source.exists():
                    return
                raise FileExistsError(destination)

            pending = _find_reservation(workspace, migration_area, project_id, raw_root)
            if pending is not None:
                destination.mkdir()
                _copy_project_tree_resuming(source if source.exists() else pending[2], destination)
                return
            stage, tree = _stage_project_tree(source, migration_area)
            reservation = _new_reservation(workspace, project_id, raw_root, stage.name)
            _write_reservation(
                migration_area / f"{reservation['reservation_id']}.json", reservation
            )
            destination.mkdir()
            _copy_project_tree_resuming(tree, destination)

        try:
            updated = store.publish_project_root_atomic(
                project_id,
                raw_root,
                destination_subpath,
                publish,
            )
        except Exception:  # noqa: BLE001 - migration failures preserve the legacy row for retry
            conflicts.append(project_id)
            continue
        if updated:
            migrated.append(project_id)
            managed_roots.append(relative)
            if source_identity is not None and not was_moved_with_parent:
                residue = _retain_migrated_source(
                    workspace, source, source_identity, migration_area
                )
                if residue is not None:
                    retained_residues.append(str(residue.relative_to(workspace)).replace("\\", "/"))
        else:
            conflicts.append(project_id)
    return ProjectRootMigrationReport(
        tuple(migrated), tuple(conflicts), tuple(unchanged), tuple(retained_residues)
    )
