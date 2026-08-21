"""Fail-closed disposable workspace snapshots for credentialed commands."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType


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

    def create(self) -> OverlayManifest:
        if self.staging_root.exists():
            raise ValueError("credential_overlay_exists")
        self.workspace.mkdir(parents=True)
        self.git_snapshot.mkdir()
        try:
            self._copy_tree(self.workspace_root, self.workspace, excluded={".git", ".raiker"})
            git = self.workspace_root / ".git"
            if git.is_dir() and not git.is_symlink():
                self._copy_tree(git, self.git_snapshot, excluded=set())
                self._make_read_only(self.git_snapshot)
            baseline = manifest(self.workspace)
            (self.staging_root / "baseline.json").write_text(
                json.dumps(baseline.entries, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            return baseline
        except BaseException:
            shutil.rmtree(self.staging_root, ignore_errors=True)
            raise

    def delta(self, baseline: OverlayManifest) -> OverlayDelta:
        current = manifest(self.workspace)
        before, after = baseline.entries, current.entries
        created = tuple(sorted(after.keys() - before.keys()))
        deleted = tuple(sorted(before.keys() - after.keys()))
        changed = tuple(sorted(key for key in before.keys() & after.keys() if before[key] != after[key]))
        unsafe = tuple(
            sorted(
                key
                for key in (*created, *changed)
                if after[key][0] == "unsafe" or key == ".git" or key.startswith(".git/")
            )
        )
        return OverlayDelta(created, changed, deleted, unsafe, baseline.digest, current.digest)

    def discard(self) -> None:
        shutil.rmtree(
            self.staging_root,
            ignore_errors=False,
            onerror=_make_writable_and_retry,
        )

    @staticmethod
    def _copy_tree(source: Path, destination: Path, *, excluded: set[str]) -> None:
        root_device = source.stat().st_dev
        for entry in os.scandir(source):
            if entry.name in excluded:
                continue
            target = destination / entry.name
            # ``DirEntry.stat`` reports zero device/link metadata on some
            # Windows Python builds; Path.lstat carries the real file-index
            # values needed for the boundary checks.
            info = Path(entry.path).lstat()
            if (
                info.st_dev != root_device
                or entry.is_symlink()
                or (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)
            ):
                raise ValueError("credential_overlay_unsafe_source")
            if stat.S_ISDIR(info.st_mode):
                target.mkdir()
                CredentialOverlay._copy_tree(Path(entry.path), target, excluded=excluded)
            elif stat.S_ISREG(info.st_mode):
                with open(entry.path, "rb", opener=_no_follow_opener) as reader, open(
                    target, "xb"
                ) as writer:
                    shutil.copyfileobj(reader, writer)
                target.chmod(0o755 if info.st_mode & stat.S_IXUSR else 0o644)
            else:
                raise ValueError("credential_overlay_unsafe_source")

    @staticmethod
    def _make_read_only(root: Path) -> None:
        for path in sorted(root.rglob("*"), reverse=True):
            path.chmod(0o555 if path.is_dir() else 0o444)
        root.chmod(0o555)


def manifest(root: Path) -> OverlayManifest:
    entries: dict[str, tuple[str, int, int]] = {}
    collision_keys: set[str] = set()
    root_device = root.stat().st_dev
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        key = unicodedata.normalize("NFC", relative).casefold()
        info = path.lstat()
        unsafe = (
            key in collision_keys
            or info.st_dev != root_device
            or path.is_symlink()
            or (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)
            or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))
        )
        collision_keys.add(key)
        if unsafe:
            entries[relative] = ("unsafe", 0, 0)
        elif stat.S_ISDIR(info.st_mode):
            entries[relative] = ("directory", 0, info.st_mode & 0o777)
        else:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            entries[relative] = (digest, info.st_size, info.st_mode & 0o777)
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":"))
    return OverlayManifest(entries, hashlib.sha256(canonical.encode()).hexdigest())


def _no_follow_opener(path: str, flags: int) -> int:
    return os.open(path, flags | getattr(os, "O_NOFOLLOW", 0))


def _make_writable_and_retry(
    function: Callable[[str], object],
    path: str,
    _exc: tuple[type[BaseException], BaseException, TracebackType],
) -> None:
    """Restore owner write access on a read-only snapshot before retrying."""
    target = Path(path)
    # POSIX needs write permission on the parent to unlink an entry; Windows
    # needs the entry's read-only bit cleared. Restore both, owner-only, inside
    # the already isolated staging root before repeating shutil's operation.
    target.parent.chmod(stat.S_IRWXU)
    target.chmod(stat.S_IRWXU)
    function(path)
