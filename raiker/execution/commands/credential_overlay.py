"""Fail-closed disposable workspace snapshots for credentialed commands."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import unicodedata
from bisect import bisect_left
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from types import TracebackType
from typing import BinaryIO

_MAX_SNAPSHOT_ENTRIES = 100_000
_MAX_SNAPSHOT_BYTES = 2 * 1024**3


@dataclass
class _CopyBudget:
    entries: int = 0
    bytes: int = 0

    def add(self, info: os.stat_result) -> None:
        self.entries += 1
        if self.entries > _MAX_SNAPSHOT_ENTRIES:
            raise ValueError("credential_overlay_entry_limit_exceeded")
        if stat.S_ISREG(info.st_mode):
            self.bytes += info.st_size
            if self.bytes > _MAX_SNAPSHOT_BYTES:
                raise ValueError("credential_overlay_size_limit_exceeded")


@dataclass(frozen=True)
class OverlayManifest:
    entries: dict[str, tuple[str, int, int]]
    digest: str


@dataclass(frozen=True)
class OverlayDelta:
    created: tuple[str, ...]
    changed: tuple[str, ...]
    deleted: tuple[str, ...]
    unsafe: tuple[str, ...]
    baseline_digest: str
    current_digest: str

    @property
    def mergeable(self) -> bool:
        return not self.unsafe


class CredentialOverlay:
    """Copies only governed workspace data; `.git` and `.raiker` never enter it."""

    def __init__(self, workspace_root: Path, staging_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.staging_root = staging_root.resolve()
        self.workspace = self.staging_root / "workspace"
        self.git_snapshot = self.staging_root / "git"
        self._owned_identity: tuple[int, int] | None = None

    def create(self) -> OverlayManifest:
        if self.staging_root.is_relative_to(
            self.workspace_root
        ) or self.workspace_root.is_relative_to(self.staging_root):
            raise ValueError("credential_overlay_overlapping_roots")
        self.staging_root.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.staging_root.mkdir()
        except FileExistsError as exc:
            raise ValueError("credential_overlay_exists") from exc
        created = self.staging_root.lstat()
        self._owned_identity = (created.st_dev, created.st_ino)
        try:
            self.workspace.mkdir()
            self.git_snapshot.mkdir()
            budget = _CopyBudget()
            self._copy_tree(
                self.workspace_root, self.workspace, excluded={".git", ".raiker"}, budget=budget
            )
            git = self.workspace_root / ".git"
            if git.is_dir() and not git.is_symlink():
                self._copy_tree(git, self.git_snapshot, excluded=set(), budget=budget)
                self._make_read_only(self.git_snapshot)
            baseline = manifest(self.workspace)
            (self.staging_root / "baseline.json").write_text(
                json.dumps(baseline.entries, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            return baseline
        except BaseException:
            with suppress(OSError, ValueError):
                self.discard()
            raise

    def delta(self, baseline: OverlayManifest) -> OverlayDelta:
        if _manifest_digest(baseline.entries) != baseline.digest:
            raise ValueError("credential_overlay_invalid_baseline")
        current = manifest(self.workspace)
        before, after = baseline.entries, current.entries
        created = tuple(sorted(after.keys() - before.keys()))
        deleted = tuple(sorted(before.keys() - after.keys()))
        changed = tuple(
            sorted(key for key in before.keys() & after.keys() if before[key] != after[key])
        )
        unsafe = tuple(
            sorted(
                key
                for key in (*created, *changed, *deleted)
                if after.get(key, ("", 0, 0))[0] == "unsafe"
                or before.get(key, ("", 0, 0))[0] == "unsafe"
                or any(
                    unicodedata.normalize("NFC", part).casefold() in {".git", ".raiker"}
                    for part in key.split("/")
                )
            )
        )
        return OverlayDelta(created, changed, deleted, unsafe, baseline.digest, current.digest)

    def promotion_conflicts(self, baseline: OverlayManifest) -> tuple[str, ...]:
        """Report observed conflicts; this does not authorize promotion.

        Directory handles are not pinned, so this observation can become stale
        immediately. A future promotion transaction must revalidate atomically.
        """
        delta = self.delta(baseline)
        if not delta.mergeable:
            raise ValueError("credential_overlay_unsafe_delta")
        original = manifest(self.workspace_root, excluded={".git", ".raiker"})
        if any(entry[0] == "unsafe" for entry in (*baseline.entries.values(), *original.entries.values())):
            raise ValueError("credential_overlay_unsafe_original")
        before = _casefold_index(baseline.entries)
        owner = _casefold_index(original.entries)
        owner_changes = sorted(key for key in before.keys() | owner.keys() if before.get(key) != owner.get(key))
        deleted = set(delta.deleted)
        conflicts: set[str] = set()
        for path in (*delta.created, *delta.changed, *delta.deleted):
            parts = path.split("/")
            for length in range(1, len(parts) + 1):
                key = _fold_path("/".join(parts[:length]))
                if before.get(key) != owner.get(key):
                    conflicts.add(path)
                    break
            if path in deleted and baseline.entries.get(path, ("", 0, 0))[0] == "directory":
                prefix = _fold_path(path) + "/"
                position = bisect_left(owner_changes, prefix)
                if position < len(owner_changes) and owner_changes[position].startswith(prefix):
                    conflicts.add(path)
        return tuple(sorted(conflicts))

    def discard(self) -> None:
        try:
            current = self.staging_root.lstat()
        except OSError as exc:
            raise ValueError("credential_overlay_not_owned") from exc
        if (
            self._owned_identity is None
            or (current.st_dev, current.st_ino) != self._owned_identity
            or not stat.S_ISDIR(current.st_mode)
            or getattr(current, "st_file_attributes", 0) & 0x400
        ):
            raise ValueError("credential_overlay_not_owned")
        shutil.rmtree(
            self.staging_root,
            ignore_errors=False,
            onerror=partial(_make_writable_and_retry, self.staging_root),
        )
        self._owned_identity = None

    @staticmethod
    def _copy_tree(
        source: Path, destination: Path, *, excluded: set[str], budget: _CopyBudget
    ) -> None:
        root_device = _directory_device(source)
        for entry in os.scandir(source):
            if unicodedata.normalize("NFC", entry.name).casefold() in excluded:
                continue
            target = destination / entry.name
            # ``DirEntry.stat`` reports zero device/link metadata on some
            # Windows Python builds; Path.lstat carries the real file-index
            # values needed for the boundary checks.
            info = Path(entry.path).lstat()
            budget.add(info)
            if (
                info.st_dev != root_device
                or entry.is_symlink()
                or getattr(info, "st_file_attributes", 0) & 0x400
                or (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)
            ):
                raise ValueError("credential_overlay_unsafe_source")
            if stat.S_ISDIR(info.st_mode):
                target.mkdir()
                CredentialOverlay._copy_tree(
                    Path(entry.path), target, excluded=excluded, budget=budget
                )
                target.chmod(info.st_mode & 0o777)
            elif stat.S_ISREG(info.st_mode):
                with (
                    open(entry.path, "rb", opener=_no_follow_opener) as reader,
                    open(target, "xb") as writer,
                ):
                    opened = os.fstat(reader.fileno())
                    if (
                        not stat.S_ISREG(opened.st_mode)
                        or opened.st_dev != info.st_dev
                        or opened.st_ino != info.st_ino
                        or opened.st_nlink != 1
                        or opened.st_size != info.st_size
                        or opened.st_mtime_ns != info.st_mtime_ns
                    ):
                        raise ValueError("credential_overlay_unsafe_source")
                    _copy_bounded(reader, writer, opened.st_size)
                    after = os.fstat(reader.fileno())
                    if (
                        after.st_nlink != 1
                        or after.st_size != opened.st_size
                        or after.st_mtime_ns != opened.st_mtime_ns
                        or after.st_ctime_ns != opened.st_ctime_ns
                    ):
                        raise ValueError("credential_overlay_unsafe_source")
                target.chmod(info.st_mode & 0o777)
            else:
                raise ValueError("credential_overlay_unsafe_source")

    @staticmethod
    def _make_read_only(root: Path) -> None:
        for path in sorted(root.rglob("*"), reverse=True):
            path.chmod(0o555 if path.is_dir() else 0o444)
        root.chmod(0o555)


def _copy_bounded(reader: BinaryIO, writer: BinaryIO, size: int) -> None:
    copied = 0
    while True:
        chunk = reader.read(min(1024 * 1024, size - copied + 1))
        if not chunk:
            break
        copied += len(chunk)
        if copied > size:
            raise ValueError("credential_overlay_unsafe_source")
        writer.write(chunk)
    if copied != size:
        raise ValueError("credential_overlay_unsafe_source")


def manifest(
    root: Path,
    *,
    max_entries: int = _MAX_SNAPSHOT_ENTRIES,
    max_bytes: int = _MAX_SNAPSHOT_BYTES,
    excluded: set[str] | None = None,
) -> OverlayManifest:
    if max_entries < 0 or max_bytes < 0:
        raise ValueError("credential_overlay_invalid_limit")
    entries: dict[str, tuple[str, int, int]] = {}
    collision_keys: set[str] = set()
    root_device = _directory_device(root)
    total_bytes = 0
    for path, info in sorted(
        _snapshot_entries(root, root_device, max_entries, excluded or set()), key=lambda item: item[0]
    ):
        relative = path.relative_to(root).as_posix()
        key = unicodedata.normalize("NFC", relative).casefold()
        unsafe = (
            key in collision_keys
            or info.st_dev != root_device
            or stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & 0x400
            or (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)
            or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))
        )
        collision_keys.add(key)
        if unsafe:
            entries[relative] = ("unsafe", 0, 0)
        elif stat.S_ISDIR(info.st_mode):
            entries[relative] = ("directory", 0, info.st_mode & 0o777)
        else:
            total_bytes += info.st_size
            if total_bytes > max_bytes:
                raise ValueError("credential_overlay_size_limit_exceeded")
            digest = _stable_file_digest(path, info)
            entries[relative] = (
                (digest, info.st_size, info.st_mode & 0o777)
                if digest is not None
                else ("unsafe", 0, 0)
            )
    return OverlayManifest(entries, _manifest_digest(entries))


def _manifest_digest(entries: dict[str, tuple[str, int, int]]) -> str:
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _directory_device(root: Path) -> int:
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("credential_overlay_unsafe_root")
    return info.st_dev


def _snapshot_entries(
    root: Path, root_device: int, max_entries: int, excluded: set[str]
) -> list[tuple[Path, os.stat_result]]:
    """Never descend through a known link, reparse point, or foreign device.

    Directory handles are not pinned yet; concurrent directory replacement
    remains a release blocker and must not be treated as a secure workspace.
    """
    result: list[tuple[Path, os.stat_result]] = []
    pending = [root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                if unicodedata.normalize("NFC", entry.name).casefold() in excluded:
                    continue
                path = Path(entry.path)
                info = path.lstat()
                if len(result) >= max_entries:
                    raise ValueError("credential_overlay_entry_limit_exceeded")
                result.append((path, info))
                if (
                    stat.S_ISDIR(info.st_mode)
                    and info.st_dev == root_device
                    and not getattr(info, "st_file_attributes", 0) & 0x400
                ):
                    pending.append(path)
    return result


def _fold_path(path: str) -> str:
    return unicodedata.normalize("NFC", path).casefold()


def _casefold_index(
    entries: dict[str, tuple[str, int, int]],
) -> dict[str, tuple[str, tuple[str, int, int]]]:
    return {_fold_path(path): (path, value) for path, value in entries.items()}


def _no_follow_opener(path: str, flags: int) -> int:
    return os.open(path, flags | getattr(os, "O_NOFOLLOW", 0))


def _stable_file_digest(path: Path, inspected: os.stat_result) -> str | None:
    try:
        with open(path, "rb", opener=_no_follow_opener) as reader:
            opened = os.fstat(reader.fileno())
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_dev != inspected.st_dev
                or opened.st_ino != inspected.st_ino
                or opened.st_nlink != 1
                or opened.st_size != inspected.st_size
                or opened.st_mtime_ns != inspected.st_mtime_ns
            ):
                return None
            digest = hashlib.sha256()
            bytes_read = 0
            for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                bytes_read += len(chunk)
                if bytes_read > opened.st_size:
                    return None
                digest.update(chunk)
            if bytes_read != opened.st_size:
                return None
            after = os.fstat(reader.fileno())
            if (
                after.st_nlink != 1
                or after.st_size != opened.st_size
                or after.st_mtime_ns != opened.st_mtime_ns
                or after.st_ctime_ns != opened.st_ctime_ns
            ):
                return None
            return digest.hexdigest()
    except OSError:
        return None


def _make_writable_and_retry(
    root: Path,
    function: Callable[[str], object],
    path: str,
    _exc: tuple[type[BaseException], BaseException, TracebackType | None],
) -> None:
    """Restore owner write access on a read-only snapshot before retrying."""
    target = Path(path)
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise ValueError("credential_overlay_unsafe_cleanup") from exc
    if any(part in {".", ".."} for part in relative.parts):
        raise ValueError("credential_overlay_unsafe_cleanup")
    current = root
    for part in (None, *relative.parts):
        if part is not None:
            current = current / part
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("credential_overlay_unsafe_cleanup")
    # POSIX needs write permission on the parent to unlink an entry; Windows
    # needs the entry's read-only bit cleared. Restore both, owner-only, inside
    # the already isolated staging root before repeating shutil's operation.
    if target != root:
        target.parent.chmod(stat.S_IRWXU)
    target.chmod(stat.S_IRWXU)
    function(path)
