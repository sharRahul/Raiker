"""Disposable task workspaces: snapshot, diff, reviewed promotion, cleanup.

Autonomous code never runs against the owner's project. A task gets a private
copy under a Raiker-owned directory, works there inside the native sandbox, and
its result reaches the project only through :func:`promote`, which applies the
reviewed change set transactionally or not at all.

What the snapshot deliberately leaves out, and why:

* **``.git`` and ``.raiker``.** Repository metadata stays under Raiker's governed
  Git operations, and Raiker's own state is never task input. Neither is copied,
  so neither can be read or rewritten by sandboxed code, and a path under either
  is never promotable.
* **Links and reparse points.** A symlink or Windows junction in the copy could
  point back into the project or anywhere else on the machine. They are listed
  as skipped rather than copied or followed. Hard links are copied as fresh
  files, so a write in the copy never reaches the original inode.
* **Anything that is not a regular file or directory.** Devices, sockets and
  FIFOs are skipped.

A Git worktree is not a sandbox: this copy is only the *workspace*; the native
runner is the boundary that keeps the task inside it.

Promotion compares each original file against the content hash taken at
snapshot time. If the owner changed a file the task also changed, or created a
path the task also created, promotion refuses (``workspace_promotion_conflict``)
and nothing is written. Each replaced or removed original is backed up first; a
failure part-way restores every backup and removes every file the promotion
created. File rollback cannot undo side effects outside the project.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import stat
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

EXCLUDED_NAMES = frozenset({".git", ".raiker"})
DEFAULT_MAX_FILES = 200_000
DEFAULT_MAX_BYTES = 4 * 1024**3
_CHUNK = 1024 * 1024
_REPARSE_POINT = 0x400  # FILE_ATTRIBUTE_REPARSE_POINT


class WorkspaceError(RuntimeError):
    def __init__(self, reason_code: str, detail: str | None = None) -> None:
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(reason_code if detail is None else f"{reason_code}:{detail}")


@dataclass(frozen=True)
class ManifestEntry:
    sha256: str
    size: int
    executable: bool


@dataclass
class TaskWorkspace:
    task_id: str
    source: Path
    root: Path
    manifest: dict[str, ManifestEntry]
    skipped: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class WorkspaceDiff:
    created: tuple[str, ...]
    modified: tuple[str, ...]
    deleted: tuple[str, ...]
    #: Paths the task produced that can never be promoted (links, special
    #: files, protected names), with the reason for each.
    rejected: tuple[tuple[str, str], ...]

    @property
    def empty(self) -> bool:
        return not (self.created or self.modified or self.deleted)


@dataclass(frozen=True)
class PromotionResult:
    created: tuple[str, ...]
    modified: tuple[str, ...]
    deleted: tuple[str, ...]


def _is_link_like(entry: os.DirEntry[str]) -> bool:
    if entry.is_symlink():
        return True
    is_junction = getattr(entry, "is_junction", None)
    if callable(is_junction) and is_junction():
        return True
    attributes = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
    return bool(attributes & _REPARSE_POINT)


def _path_is_link_like(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(info.st_mode):
        return True
    return bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT)


def _walk(root: Path) -> Iterator[tuple[str, os.DirEntry[str] | None, str | None]]:
    """Yield ``(relative, entry, problem)`` for every entry under ``root``.

    Never follows a link. ``problem`` names why an entry is not a plain file;
    directories are descended into and not yielded.
    """
    pending: list[tuple[Path, PurePosixPath]] = [(root, PurePosixPath())]
    while pending:
        directory, prefix = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                relative = prefix / entry.name
                if not prefix.parts and entry.name in EXCLUDED_NAMES:
                    continue
                if _is_link_like(entry):
                    yield relative.as_posix(), None, "link"
                elif entry.is_dir(follow_symlinks=False):
                    pending.append((Path(entry.path), relative))
                elif entry.is_file(follow_symlinks=False):
                    yield relative.as_posix(), entry, None
                else:
                    yield relative.as_posix(), None, "special_file"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_file(source: Path, target: Path) -> str:
    """Copy bytes (never metadata, never a link) and return their SHA-256."""
    digest = hashlib.sha256()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(source, flags)
    with os.fdopen(descriptor, "rb") as reader, open(target, "xb") as writer:
        for chunk in iter(lambda: reader.read(_CHUNK), b""):
            digest.update(chunk)
            writer.write(chunk)
    return digest.hexdigest()


def create_task_workspace(
    source: str | Path,
    base: str | Path,
    task_id: str,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> TaskWorkspace:
    """Copy ``source`` into a fresh, unpredictable directory under ``base``."""
    source_path = Path(source)
    if _path_is_link_like(source_path) or not source_path.is_dir():
        raise WorkspaceError("workspace_source_invalid")
    source_path = source_path.resolve()
    base_path = Path(base)
    base_path.mkdir(parents=True, exist_ok=True)
    if _path_is_link_like(base_path):
        raise WorkspaceError("workspace_base_invalid")
    base_path = base_path.resolve()
    if base_path == source_path or source_path in base_path.parents:
        raise WorkspaceError("workspace_base_inside_source")
    safe_task = "".join(c if c.isalnum() or c in "-_" else "-" for c in task_id)[:48]
    root = Path(tempfile.mkdtemp(prefix=f"{safe_task or 'task'}-", dir=base_path))
    workspace = TaskWorkspace(task_id, source_path, root, {})
    total = 0
    try:
        for relative, entry, problem in _walk(source_path):
            if problem is not None or entry is None:
                workspace.skipped.append(relative)
                continue
            if len(workspace.manifest) >= max_files:
                raise WorkspaceError("workspace_file_quota_exceeded")
            size = entry.stat(follow_symlinks=False).st_size
            total += size
            if total > max_bytes:
                raise WorkspaceError("workspace_storage_quota_exceeded")
            target = root.joinpath(*PurePosixPath(relative).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = _copy_file(Path(entry.path), target)
            executable = bool(entry.stat(follow_symlinks=False).st_mode & stat.S_IXUSR)
            if executable:
                target.chmod(target.stat().st_mode | stat.S_IXUSR)
            workspace.manifest[relative] = ManifestEntry(digest, size, executable)
    except BaseException:
        discard(workspace)
        raise
    return workspace


def diff_workspace(workspace: TaskWorkspace) -> WorkspaceDiff:
    """What the task changed in its copy, against the snapshot manifest."""
    seen: set[str] = set()
    created: list[str] = []
    modified: list[str] = []
    rejected: list[tuple[str, str]] = []
    for relative, entry, problem in _walk(workspace.root):
        if problem is not None or entry is None:
            rejected.append((relative, problem or "special_file"))
            continue
        reason = _unsafe_relative(relative)
        if reason:
            rejected.append((relative, reason))
            continue
        seen.add(relative)
        original = workspace.manifest.get(relative)
        if original is None:
            created.append(relative)
        elif _hash_file(Path(entry.path)) != original.sha256:
            modified.append(relative)
    for name in EXCLUDED_NAMES:
        if (workspace.root / name).exists() or _path_is_link_like(workspace.root / name):
            rejected.append((name, "protected_path"))
    deleted = [relative for relative in workspace.manifest if relative not in seen]
    return WorkspaceDiff(
        tuple(sorted(created)),
        tuple(sorted(modified)),
        tuple(sorted(deleted)),
        tuple(sorted(rejected)),
    )


def _unsafe_relative(relative: str) -> str | None:
    path = PurePosixPath(relative)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        return "path_traversal"
    if path.parts[0] in EXCLUDED_NAMES:
        return "protected_path"
    if any(":" in part or "\\" in part for part in path.parts):
        return "path_unrepresentable"
    return None


def _target(source: Path, relative: str) -> Path:
    """The project path for ``relative``, refusing any route through a link."""
    reason = _unsafe_relative(relative)
    if reason:
        raise WorkspaceError("workspace_path_unsafe", relative)
    target = source.joinpath(*PurePosixPath(relative).parts)
    current = source
    for part in PurePosixPath(relative).parts:
        current = current / part
        if _path_is_link_like(current):
            raise WorkspaceError("workspace_path_unsafe", relative)
    if source not in target.parents:
        raise WorkspaceError("workspace_path_unsafe", relative)
    return target


@contextlib.contextmanager
def _promotion_lock(workspace: TaskWorkspace) -> Iterator[None]:
    key = hashlib.sha256(str(workspace.source).encode("utf-8")).hexdigest()[:24]
    lock = workspace.root.parent / f".promote-{key}.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise WorkspaceError("workspace_promotion_in_progress") from None
    os.close(descriptor)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            lock.unlink()


def promote(
    workspace: TaskWorkspace,
    diff: WorkspaceDiff,
    *,
    allowed: Callable[[str], bool] | None = None,
) -> PromotionResult:
    """Apply a reviewed diff to the original project, all or nothing.

    ``allowed`` is the effective authority's path check; a change it refuses
    stops the whole promotion before anything is written.
    """
    paths = [*diff.created, *diff.modified, *diff.deleted]
    for relative in paths:
        if allowed is not None and not allowed(relative):
            raise WorkspaceError("workspace_promotion_not_permitted", relative)
    with _promotion_lock(workspace):
        targets = {relative: _target(workspace.source, relative) for relative in paths}
        for relative in diff.created:
            if targets[relative].exists() or _path_is_link_like(targets[relative]):
                raise WorkspaceError("workspace_promotion_conflict", relative)
        for relative in (*diff.modified, *diff.deleted):
            original = workspace.manifest[relative]
            target = targets[relative]
            if not target.is_file() or _hash_file(target) != original.sha256:
                raise WorkspaceError("workspace_promotion_conflict", relative)
        backups = Path(tempfile.mkdtemp(prefix=".promote-backup-", dir=workspace.root.parent))
        saved: dict[str, Path] = {}
        written: list[Path] = []
        made_directories: list[Path] = []
        try:
            for index, relative in enumerate((*diff.modified, *diff.deleted)):
                backup = backups / str(index)
                shutil.copyfile(targets[relative], backup)
                saved[relative] = backup
            for relative in (*diff.created, *diff.modified):
                target = targets[relative]
                for parent in reversed(target.parents):
                    if workspace.source in parent.parents and not parent.exists():
                        parent.mkdir()
                        made_directories.append(parent)
                staged = target.with_name(f".{target.name}.raiker-promote")
                _copy_file(workspace.root.joinpath(*PurePosixPath(relative).parts), staged)
                if relative in diff.created:
                    written.append(target)
                os.replace(staged, target)
            for relative in diff.deleted:
                targets[relative].unlink()
        except BaseException:
            for relative, backup in saved.items():
                # Copied back, not renamed: the backup may be on another volume.
                with contextlib.suppress(OSError):
                    shutil.copyfile(backup, targets[relative])
            for target in written:
                with contextlib.suppress(OSError):
                    target.unlink()
            for directory in reversed(made_directories):
                with contextlib.suppress(OSError):
                    directory.rmdir()
            for relative in (*diff.created, *diff.modified):
                staged = targets[relative].with_name(f".{targets[relative].name}.raiker-promote")
                with contextlib.suppress(OSError):
                    staged.unlink()
            raise
        finally:
            shutil.rmtree(backups, ignore_errors=True)
    return PromotionResult(diff.created, diff.modified, diff.deleted)


def discard(workspace: TaskWorkspace) -> None:
    """Remove the task's copy. Never touches anything outside it."""
    root = workspace.root
    if _path_is_link_like(root) or not root.is_dir():
        return

    def clear_readonly(function: Callable[..., object], path: str, _info: object) -> None:
        with contextlib.suppress(OSError):
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
            function(path)

    if sys.version_info >= (3, 12):
        shutil.rmtree(root, onexc=clear_readonly)
    else:
        shutil.rmtree(root, onerror=clear_readonly)


def sweep_stale(base: str | Path, *, older_than_seconds: float) -> list[Path]:
    """Remove task copies left by a crash. Only direct children of ``base``."""
    base_path = Path(base)
    if not base_path.is_dir() or _path_is_link_like(base_path):
        return []
    cutoff = time.time() - older_than_seconds
    removed: list[Path] = []
    for child in base_path.iterdir():
        if _path_is_link_like(child) or not child.is_dir():
            continue
        if child.stat().st_mtime < cutoff:
            discard(TaskWorkspace("stale", base_path, child, {}))
            removed.append(child)
    return removed
