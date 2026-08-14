from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path


class CacheSnapshotError(RuntimeError):
    pass


@dataclass(frozen=True)
class CacheSnapshot:
    digest: str
    file_count: int
    byte_count: int


class CacheSnapshotService:
    """Validate and atomically publish an untrusted worker cache delta."""

    _publish_lock = threading.Lock()

    def __init__(self, *, max_files: int = 25_000, max_bytes: int = 512_000_000) -> None:
        self.max_files = max_files
        self.max_bytes = max_bytes

    def publish(self, source: Path, target: Path) -> CacheSnapshot:
        source = source.resolve()
        target = target.resolve()
        entries, file_count, byte_count, digest = self._validate(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent))
        cleanup_staging = True
        try:
            for relative, is_directory in entries:
                source_path = source / relative
                destination = staging / relative
                if is_directory:
                    destination.mkdir(parents=True, exist_ok=True)
                    destination.chmod(0o700)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with source_path.open("rb") as reader, destination.open("xb") as writer:
                    shutil.copyfileobj(reader, writer, length=1024 * 1024)
                destination.chmod(stat.S_IRUSR | stat.S_IWUSR)
            self._publish(staging, target)
            cleanup_staging = False
        finally:
            if cleanup_staging and staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
        return CacheSnapshot(digest, file_count, byte_count)

    def _validate(self, source: Path) -> tuple[list[tuple[Path, bool]], int, int, str]:
        if not source.is_dir() or source.is_symlink():
            raise CacheSnapshotError("cache_snapshot_source_invalid")
        entries: list[tuple[Path, bool]] = []
        files = 0
        total = 0
        hasher = hashlib.sha256()
        for root, directories, filenames in os.walk(source, topdown=True, followlinks=False):
            root_path = Path(root)
            for name in sorted([*directories, *filenames]):
                path = root_path / name
                relative = path.relative_to(source)
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode) or not (
                    stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)
                ):
                    raise CacheSnapshotError("cache_snapshot_unsafe_entry")
                if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                    raise CacheSnapshotError("cache_snapshot_hardlink_rejected")
                is_directory = stat.S_ISDIR(info.st_mode)
                entries.append((relative, is_directory))
                hasher.update(relative.as_posix().encode())
                hasher.update(b"d" if is_directory else b"f")
                if not is_directory:
                    files += 1
                    total += info.st_size
                    if files > self.max_files:
                        raise CacheSnapshotError("cache_snapshot_file_limit")
                    if total > self.max_bytes:
                        raise CacheSnapshotError("cache_snapshot_byte_limit")
                    with path.open("rb") as handle:
                        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                            hasher.update(chunk)
        return entries, files, total, hasher.hexdigest()

    @classmethod
    def _publish(cls, staging: Path, target: Path) -> None:
        with cls._publish_lock:
            backup = target.with_name(f".{target.name}.previous")
            if backup.exists():
                shutil.rmtree(backup)
            if target.exists():
                os.replace(target, backup)
            try:
                os.replace(staging, target)
            except BaseException:
                if backup.exists() and not target.exists():
                    os.replace(backup, target)
                raise
            if backup.exists():
                shutil.rmtree(backup)
