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
* **A toolchain's folders** (``ENVIRONMENT_NAMES``: ``.venv``, ``node_modules``,
  caches, Cargo's ``target``). They are the task's environment: set up again in
  the copy, never copied from the project and never promoted.

A Git worktree is not a sandbox: this copy is only the *workspace*; the native
runner is the boundary that keeps the task inside it.

Promotion compares each original file against the content hash taken at
snapshot time. If the owner changed a file the task also changed, or created a
path the task also created, promotion refuses (``workspace_promotion_conflict``)
and nothing is written, unless the owner saw both versions and chose to
overwrite that path (:func:`promotion_conflicts` lists them). Each replaced or removed original is backed up first; a
failure part-way restores every backup and removes every file the promotion
created. File rollback cannot undo side effects outside the project.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import secrets
import shutil
import stat
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

EXCLUDED_NAMES = frozenset({".git", ".raiker"})
#: Folders a toolchain fills: installed dependencies and caches. They are the
#: task's environment, not its work, so they are neither copied in from the
#: project (a virtualenv's scripts name the project's own paths, and one
#: `node_modules` can pass the copy's file limit alone) nor part of the change
#: set the owner reviews: `python -m venv .venv` or `npm install` in a copy
#: promotes nothing. Matched as folder names at any depth.
ENVIRONMENT_NAMES = frozenset({
    ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", ".nox",
})
#: At the copy's top only: where the package managers' caches land, because a
#: sandboxed command's HOME is the copy.
ENVIRONMENT_ROOT_NAMES = frozenset({".cache", ".npm", ".local", ".cargo"})
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
                    if not _is_environment(directory, entry.name, top=not prefix.parts):
                        pending.append((Path(entry.path), relative))
                elif entry.is_file(follow_symlinks=False):
                    yield relative.as_posix(), entry, None
                else:
                    yield relative.as_posix(), None, "special_file"


def _is_environment(directory: Path, name: str, *, top: bool) -> bool:
    """Whether the folder *name* in *directory* is a toolchain's, not the task's."""
    if name in ENVIRONMENT_NAMES or (top and name in ENVIRONMENT_ROOT_NAMES):
        return True
    # Cargo's build output, recognised by the manifest beside it.
    return name == "target" and (directory / "Cargo.toml").is_file()


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


def _new_private_directory(base: Path, prefix: str) -> Path:
    """An unpredictable, exclusively created directory under ``base``.

    Not `tempfile.mkdtemp`: since Python 3.13 its 0o700 mode becomes an
    owner-only, non-inheriting ACL on Windows, which cuts off the sandbox
    account's grant on the base and leaves the copy unreadable to the command.
    POSIX keeps 0o700; Windows inherits the base's ACL.
    """
    for _ in range(16):
        candidate = base / f"{prefix}-{secrets.token_hex(8)}"
        try:
            if sys.platform == "win32":
                os.mkdir(candidate)
            else:
                os.mkdir(candidate, 0o700)
        except FileExistsError:
            continue
        return candidate
    raise WorkspaceError("workspace_create_failed")


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
    root = _new_private_directory(base_path, safe_task or "task")
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
    # At any depth: a nested `.git` the task planted would be a repository
    # whose hooks or config the owner's own Git could later run.
    if any(part.casefold() in EXCLUDED_NAMES for part in path.parts):
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


def _conflicts(
    workspace: TaskWorkspace, diff: WorkspaceDiff, targets: dict[str, Path]
) -> tuple[str, ...]:
    found: list[str] = []
    for relative in diff.created:
        if targets[relative].exists() or _path_is_link_like(targets[relative]):
            found.append(relative)
    for relative in (*diff.modified, *diff.deleted):
        target = targets[relative]
        if not target.is_file() or _hash_file(target) != workspace.manifest[relative].sha256:
            found.append(relative)
    return tuple(sorted(found))


def promotion_conflicts(workspace: TaskWorkspace, diff: WorkspaceDiff) -> tuple[str, ...]:
    """Paths the owner changed in the project since the copy was taken (BD-4).

    A created path that now exists in the project, or a modified or deleted one
    whose original no longer matches the snapshot. Promotion refuses each of
    these unless the owner chooses to overwrite it.
    """
    paths = [*diff.created, *diff.modified, *diff.deleted]
    targets = {relative: _target(workspace.source, relative) for relative in paths}
    return _conflicts(workspace, diff, targets)


def promote(
    workspace: TaskWorkspace,
    diff: WorkspaceDiff,
    *,
    allowed: Callable[[str], bool] | None = None,
    overwrite: frozenset[str] = frozenset(),
) -> PromotionResult:
    """Apply a reviewed diff to the original project, all or nothing.

    ``allowed`` is the effective authority's path check; a change it refuses
    stops the whole promotion before anything is written. ``overwrite`` names
    the conflicting paths (see :func:`promotion_conflicts`) the owner chose to
    replace after seeing both versions; any other conflict refuses the whole
    promotion, as before. An overwritten original is backed up like any other,
    so a failure part-way restores the owner's version too.
    """
    paths = [*diff.created, *diff.modified, *diff.deleted]
    for relative in paths:
        if allowed is not None and not allowed(relative):
            raise WorkspaceError("workspace_promotion_not_permitted", relative)
    with _promotion_lock(workspace):
        targets = {relative: _target(workspace.source, relative) for relative in paths}
        conflicts = _conflicts(workspace, diff, targets)
        for relative in conflicts:
            if relative not in overwrite:
                raise WorkspaceError("workspace_promotion_conflict", relative)
            if _path_is_link_like(targets[relative]) or (
                targets[relative].exists() and not targets[relative].is_file()
            ):
                # Overwrite replaces a file the owner changed, never a folder or link.
                raise WorkspaceError("workspace_promotion_conflict", relative)
        backups = Path(tempfile.mkdtemp(prefix=".promote-backup-", dir=workspace.root.parent))
        saved: dict[str, Path] = {}
        written: list[Path] = []
        made_directories: list[Path] = []
        try:
            for index, relative in enumerate(paths):
                # Every original that is about to be replaced or removed, the
                # owner's overwritten edits included, is backed up first.
                if targets[relative].is_file():
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
                if relative not in saved:
                    written.append(target)
                os.replace(staged, target)
            for relative in diff.deleted:
                with contextlib.suppress(FileNotFoundError):
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


#: One lock per records directory, shared by every registry instance on it: the
#: broker, the executors and the review API each build their own registry, and
#: two of them creating overlapping copies at once would split one task's work.
_REGISTRY_LOCKS: dict[str, threading.RLock] = {}
_REGISTRY_LOCKS_GUARD = threading.Lock()


def _registry_lock(records: Path) -> threading.RLock:
    key = os.path.normcase(str(records.resolve()))
    with _REGISTRY_LOCKS_GUARD:
        return _REGISTRY_LOCKS.setdefault(key, threading.RLock())


def _contains(outer: Path, inner: Path) -> bool:
    return inner == outer or outer in inner.parents


class TaskWorkspaceRegistry:
    """One disposable copy per (owner, session, task root), kept across a task.

    Successive commands *and file edits* in a session work in the same copy and
    see each other's work, and the owner reviews the accumulated change set
    once. A session never holds two copies where one contains the other: that
    would split one task's work across two trees, so :meth:`acquire` returns the
    copy that already covers a path and refuses a wider one
    (``task_copy_scope_conflict``) until the narrower copy is applied or
    discarded.

    A project turn *binds* its session to the project root (:meth:`bind`), so
    the first copy is of the whole project whichever tool asks first. Records
    and bindings live in a Raiker-owned directory that no sandbox is granted,
    never in the project.
    """

    def __init__(self, base: str | Path, *, records: str | Path | None = None) -> None:
        self.base = Path(base)
        # Records name each copy's source, which is where promotion writes.
        # Where sandboxed code can write the copy base (the Windows account
        # boundary grants it the whole base), records must live elsewhere, or
        # a task could rewrite a record and redirect a promotion.
        self.records = Path(records) if records is not None else self.base
        self._lock = _registry_lock(self.records)

    @classmethod
    def for_workspace(
        cls, workspace_root: str | Path, *, base: str | Path | None = None
    ) -> TaskWorkspaceRegistry:
        """Copies live outside the Raiker workspace; records in its own state."""
        root = Path(workspace_root).resolve()
        return cls(
            base if base is not None else root.parent / f"{root.name}-sandboxes",
            records=root / ".raiker" / "task-workspaces",
        )

    @staticmethod
    def key(owner_principal_id: str, session_id: str, source: Path) -> str:
        text = "\x00".join((owner_principal_id, session_id, str(source.resolve())))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]

    def _record(self, key: str) -> Path:
        if len(key) != 32 or any(c not in "0123456789abcdef" for c in key):
            raise WorkspaceError("workspace_not_found")
        return self.records / f"{key}.json"

    def acquire(
        self, owner_principal_id: str, session_id: str, source: str | Path
    ) -> tuple[str, TaskWorkspace]:
        """The session's copy covering *source*, created if there is none.

        The returned copy's ``source`` may be an ancestor of *source*; callers
        address *source* inside it by its path relative to ``workspace.source``.
        """
        source_path = Path(source).resolve()
        with self._lock:
            for key, workspace in self.session_copies(owner_principal_id, session_id):
                if _contains(workspace.source.resolve(), source_path):
                    return key, workspace
                if _contains(source_path, workspace.source.resolve()):
                    raise WorkspaceError("task_copy_scope_conflict", str(workspace.source))
            key = self.key(owner_principal_id, session_id, source_path)
            workspace = create_task_workspace(source_path, self.base, session_id)
            self._save(key, owner_principal_id, session_id, workspace)
            return key, workspace

    def covering(
        self, owner_principal_id: str, session_id: str, path: str | Path
    ) -> TaskWorkspace | None:
        """The session's existing copy that contains *path*, without creating one."""
        target = Path(path).resolve()
        for _, workspace in self.session_copies(owner_principal_id, session_id):
            if _contains(workspace.source.resolve(), target):
                return workspace
        return None

    def session_copies(
        self, owner_principal_id: str, session_id: str
    ) -> list[tuple[str, TaskWorkspace]]:
        return [
            (key, workspace)
            for key, session, workspace in self.entries(owner_principal_id)
            if session == session_id
        ]

    def session_owner(self, session_id: str) -> str | None:
        """Whose task this session is, from its binding or any live copy."""
        binding = self._load_binding(session_id)
        if binding is not None:
            return binding[0]
        if not self.records.is_dir():
            return None
        for record in sorted(self.records.glob("*.json")):
            loaded = self._load(record.stem)
            if loaded is not None and loaded[2] == session_id:
                return loaded[0]
        return None

    # Session binding: the task root a session's copy is taken from.

    def bind(self, owner_principal_id: str, session_id: str, root: str | Path) -> None:
        """Record that this session's task is the project at *root*.

        Rebinding is a no-op while the session holds a copy, so a turn that
        names a different project cannot move work already in progress.
        """
        resolved = Path(root).resolve()
        with self._lock:
            if self.session_copies(owner_principal_id, session_id):
                return
            path = self._binding_path(session_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            staged = path.with_suffix(".tmp")
            staged.write_text(
                json.dumps({"owner_principal_id": owner_principal_id, "root": str(resolved)}),
                encoding="utf-8",
            )
            os.replace(staged, path)

    def scope_for(self, owner_principal_id: str, session_id: str, path: str | Path) -> Path:
        """The folder a copy for *path* should be taken from.

        The session's bound task root when it contains *path*, so every tool
        lands in one copy of the project; otherwise *path* itself.
        """
        target = Path(path).resolve()
        root = self.bound_root(owner_principal_id, session_id)
        return root if root is not None and _contains(root, target) else target

    def bound_root(self, owner_principal_id: str, session_id: str) -> Path | None:
        binding = self._load_binding(session_id)
        if binding is None or binding[0] != owner_principal_id:
            return None
        return binding[1]

    def _binding_path(self, session_id: str) -> Path:
        digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:32]
        return self.records / "sessions" / f"{digest}.json"

    def _load_binding(self, session_id: str) -> tuple[str, Path] | None:
        try:
            document = json.loads(self._binding_path(session_id).read_text(encoding="utf-8"))
            return str(document["owner_principal_id"]), Path(str(document["root"]))
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def load(self, owner_principal_id: str, key: str) -> TaskWorkspace:
        loaded = self._load(key)
        # Another owner's copy reads exactly like a missing one.
        if loaded is None or loaded[0] != owner_principal_id:
            raise WorkspaceError("workspace_not_found")
        return loaded[1]

    def entries(self, owner_principal_id: str) -> list[tuple[str, str, TaskWorkspace]]:
        """``(key, session_id, workspace)`` for the owner's live copies."""
        found: list[tuple[str, str, TaskWorkspace]] = []
        if not self.records.is_dir():
            return found
        for record in sorted(self.records.glob("*.json")):
            loaded = self._load(record.stem)
            if loaded is not None and loaded[0] == owner_principal_id:
                found.append((record.stem, loaded[2], loaded[1]))
        return found

    def release(self, owner_principal_id: str, key: str) -> None:
        """Discard the copy and forget it. The project is not touched."""
        with self._lock:
            workspace = self.load(owner_principal_id, key)
            discard(workspace)
            with contextlib.suppress(FileNotFoundError):
                self._record(key).unlink()

    def _save(
        self, key: str, owner_principal_id: str, session_id: str, workspace: TaskWorkspace
    ) -> None:
        document = {
            "owner_principal_id": owner_principal_id,
            "session_id": session_id,
            "task_id": workspace.task_id,
            "source": str(workspace.source),
            "root": str(workspace.root),
            "created_at": workspace.created_at,
            "skipped": workspace.skipped,
            "manifest": {
                relative: [entry.sha256, entry.size, entry.executable]
                for relative, entry in workspace.manifest.items()
            },
        }
        record = self._record(key)
        record.parent.mkdir(parents=True, exist_ok=True)
        staged = record.with_suffix(".tmp")
        staged.write_text(json.dumps(document), encoding="utf-8")
        os.replace(staged, record)

    def _load(self, key: str) -> tuple[str, TaskWorkspace, str] | None:
        record = self._record(key)
        try:
            document = json.loads(record.read_text(encoding="utf-8"))
            root = Path(document["root"])
            # A record must name a copy directly under this registry's base.
            if root.parent.resolve() != self.base.resolve() or not root.is_dir():
                return None
            workspace = TaskWorkspace(
                str(document["task_id"]),
                Path(document["source"]),
                root,
                {
                    str(relative): ManifestEntry(str(entry[0]), int(entry[1]), bool(entry[2]))
                    for relative, entry in dict(document["manifest"]).items()
                },
                [str(item) for item in document.get("skipped", [])],
                float(document.get("created_at", 0.0)),
            )
            return str(document["owner_principal_id"]), workspace, str(document["session_id"])
        except (OSError, ValueError, KeyError, TypeError, IndexError):
            return None

    def sweep_orphans(self, *, older_than_seconds: float = 24 * 3600) -> list[Path]:
        """Remove copies no record names, left by a crash before it was saved.

        A recorded copy holds work the owner has not reviewed yet, so it is
        never swept: only the owner's discard or promotion removes it.
        """
        if not self.base.is_dir() or _path_is_link_like(self.base):
            return []
        # A base shared with records kept elsewhere (the Windows account base)
        # holds other workspaces' copies too; this registry cannot tell them
        # from orphans, so it removes nothing there.
        if self.records.resolve() != self.base.resolve():
            return []
        with self._lock:
            recorded = set()
            for record in self.records.glob("*.json"):
                loaded = self._load(record.stem)
                if loaded is not None:
                    recorded.add(loaded[1].root.resolve())
            cutoff = time.time() - older_than_seconds
            removed: list[Path] = []
            for child in self.base.iterdir():
                if _path_is_link_like(child) or not child.is_dir():
                    continue
                if child.resolve() in recorded or child.stat().st_mtime >= cutoff:
                    continue
                discard(TaskWorkspace("orphan", self.base, child, {}))
                removed.append(child)
            return removed


#: A file diff is cut at this size, and says so.
FILE_DIFF_MAX_BYTES = 200_000


@dataclass(frozen=True)
class FileDiff:
    path: str
    status: str
    text: str
    binary: bool
    truncated: bool


def _diff_side(path: Path) -> tuple[str, bool]:
    """A file's text for a diff, or ``("", True)`` when it is not text."""
    if _path_is_link_like(path) or not path.is_file():
        return "", False
    with path.open("rb") as handle:
        data = handle.read(FILE_DIFF_MAX_BYTES * 4)
    if b"\0" in data:
        return "", True
    return data.decode("utf-8", errors="replace"), False


def file_diff(workspace: TaskWorkspace, diff: WorkspaceDiff, path: str) -> FileDiff | None:
    """*path*'s unified diff, project against copy, or ``None`` if it is unchanged.

    Only a path in *diff* is answered, so nothing outside the change set is read.
    Raises :class:`WorkspaceError` when the project side is reached through a link.
    """
    import difflib

    if path in diff.created:
        status = "created"
    elif path in diff.modified:
        status = "modified"
    elif path in diff.deleted:
        status = "deleted"
    else:
        return None
    before, before_binary = ("", False) if status == "created" else _diff_side(
        _target(workspace.source, path)
    )
    after, after_binary = ("", False) if status == "deleted" else _diff_side(
        workspace.root / path
    )
    binary = before_binary or after_binary
    text = "" if binary else "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile="/dev/null" if status == "created" else f"a/{path}",
            tofile="/dev/null" if status == "deleted" else f"b/{path}",
        )
    )
    return FileDiff(
        path, status, text[:FILE_DIFF_MAX_BYTES], binary, len(text) > FILE_DIFF_MAX_BYTES
    )

