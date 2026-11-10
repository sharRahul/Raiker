"""Perform task-copy I/O through pinned directories and validated file handles.

The authority still chooses/names the real project path. Its mapped copy path
is only an address: never use a prior pathname check as permission to open it.
"""
from __future__ import annotations

import contextlib
import io
import os
import stat
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any, BinaryIO

from raiker.storage.internal_paths import display_path


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(display_path(path)))


def _transport(path: Path) -> Path:
    if sys.platform == "win32":
        from raiker.execution.windows_file_handles import transport_path

        return Path(transport_path(path))
    return path


def copy_root(path: Path, authority: Any) -> Path | None:
    tree = getattr(authority, "tree", None)
    if tree is None:
        return None
    absolute = _absolute(path)
    roots = [_absolute(root) for _, root in tree.copy_roots()]
    return next((root for root in sorted(roots, key=lambda p: len(p.parts), reverse=True)
                 if absolute == root or root in absolute.parents), None)


def _refuse(reason: str) -> None:
    from raiker.tools.filesystem import FilesystemSafetyError

    raise FilesystemSafetyError(reason)


def _regular(handle: BinaryIO) -> os.stat_result:
    info = os.fstat(handle.fileno())
    if not stat.S_ISREG(info.st_mode):
        _refuse("task_copy_not_regular")
    if info.st_nlink != 1:
        _refuse("task_copy_hardlink")
    return info


@contextlib.contextmanager
def _parent(path: Path, root: Path, *, create: bool = False) -> Iterator[Any]:
    """Pin the entire absolute ancestor chain, including ancestors of copy root."""
    absolute = _absolute(path)
    if root not in absolute.parents and absolute != root:
        _refuse("task_copy_scope")
    if sys.platform == "win32":
        from raiker.execution.windows_file_handles import DirectoryPins

        with DirectoryPins() as pins:
            if create:
                current = Path(absolute.anchor)
                for part in absolute.parent.parts[1:]:
                    current /= part
                    try:
                        pins.pin(current)
                    except FileNotFoundError:
                        if current != root and root not in current.parents:
                            raise
                        _transport(current).mkdir()
                        pins.pin(current)
            else:
                pins.pin(absolute.parent)
            yield pins
        return
    if not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
        _refuse("task_copy_pinned_io_unavailable")
    handles: list[int] = []
    try:
        fd = os.open(absolute.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        handles.append(fd)
        current = Path(absolute.anchor)
        for part in absolute.parent.parts[1:]:
            current /= part
            try:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                if not create or (current != root and root not in current.parents):
                    raise
                with contextlib.suppress(FileExistsError):
                    os.mkdir(part, dir_fd=fd)
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            handles.append(child)
            fd = child
        yield fd
    finally:
        for fd in reversed(handles):
            os.close(fd)


@contextlib.contextmanager
def reader(path: Path, authority: Any = None) -> Iterator[BinaryIO]:
    root = copy_root(path, authority)
    if root is None:
        with path.open("rb") as handle:
            yield handle
        return
    with _parent(path, root) as parent:
        if sys.platform == "win32":
            from raiker.execution.windows_file_handles import regular_reader

            with regular_reader(path) as handle:
                _regular(handle)
                yield handle
        else:
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            with os.fdopen(fd, "rb") as handle:
                _regular(handle)
                yield handle


def read_bytes(path: Path, authority: Any = None, limit: int | None = None) -> bytes:
    with reader(path, authority) as handle:
        return handle.read() if limit is None else handle.read(limit)


def read_text(path: Path, authority: Any = None) -> str:
    with reader(path, authority) as handle, io.TextIOWrapper(handle, encoding="utf-8") as text:
        return text.read()


def write_text(path: Path, text: str, authority: Any = None, *, expected: str | None = None) -> int:
    return write_bytes(path, text.replace("\n", os.linesep).encode("utf-8"), authority, expected_text=expected)


def write_bytes(path: Path, data: bytes, authority: Any = None, *, expected_text: str | None = None) -> int:
    root = copy_root(path, authority)
    expected = expected_text
    if root is None:
        path.parent.mkdir(parents=True, exist_ok=True)
        return path.write_bytes(data)
    with _parent(path, root, create=True) as parent:
        if sys.platform == "win32":
            from raiker.execution.windows_file_handles import fresh_writer, regular_reader
            try:
                handle = regular_reader(path)
            except FileNotFoundError:
                if expected is not None:
                    raise
            else:
                with handle:
                    _regular(handle)
                    if expected is not None and handle.read().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n") != expected:
                        _refuse("task_copy_changed")
            parent.allow_children(path.parent)
            stage_path = path.parent / (".raiker-write-" + uuid.uuid4().hex)
            try:
                with fresh_writer(stage_path) as handle:
                    handle.write(data)
                    handle.flush()
                os.replace(_transport(stage_path), _transport(path))
            finally:
                with contextlib.suppress(FileNotFoundError):
                    _transport(stage_path).unlink()
            return len(data)
        # Never truncate an existing inode on POSIX: hardlink creation cannot
        # be excluded by a Python file lock. Replace its entry atomically.
        try:
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        except FileNotFoundError:
            if expected is not None:
                raise
            mode = 0o600
        else:
            with os.fdopen(fd, "rb") as handle:
                mode = _regular(handle).st_mode & 0o777
                if expected is not None and handle.read().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n") != expected:
                    _refuse("task_copy_changed")
        stage = ".raiker-write-" + uuid.uuid4().hex
        fd = os.open(stage, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        try:
            with os.fdopen(fd, "wb") as out:
                os.fchmod(out.fileno(), mode)
                out.write(data)
                out.flush()
            os.replace(stage, path.name, src_dir_fd=parent, dst_dir_fd=parent)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(stage, dir_fd=parent)
    return len(data)


def unlink(path: Path, authority: Any = None, *, missing_ok: bool = False) -> None:
    root = copy_root(path, authority)
    if root is None:
        path.unlink(missing_ok=missing_ok)
        return
    with _parent(path, root) as parent:
        try:
            if sys.platform == "win32":
                from raiker.execution.windows_file_handles import regular_reader

                with regular_reader(path) as handle:
                    _regular(handle)
                parent.allow_children(path.parent)
                _transport(path).unlink()
                return
            info = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                _refuse("task_copy_unsafe_delete")
            os.unlink(path.name, dir_fd=parent)
        except FileNotFoundError:
            if not missing_ok:
                raise


def entries(path: Path, authority: Any = None, *, root: Path | None = None) -> list[tuple[str, bool]]:
    """A directory snapshot, never following any child link or reparse point."""
    root = root or copy_root(path, authority)
    if root is None:
        return [(child.name, child.is_dir()) for child in path.iterdir()]
    # A dummy child makes _parent pin/open the directory being enumerated.
    with _parent(path / ".raiker-enumeration", root) as parent:
        if sys.platform == "win32":
            names = os.listdir(_transport(path))
            rows = [(name, os.lstat(_transport(path / name))) for name in names]
        else:
            names = os.listdir(parent)
            rows = [(name, os.stat(name, dir_fd=parent, follow_symlinks=False)) for name in names]
        return [(name, stat.S_ISDIR(info.st_mode)) for name, info in rows
                if not name.startswith((".raiker-pin-", ".raiker-write-"))
                and not stat.S_ISLNK(info.st_mode)
                and not (getattr(info, "st_file_attributes", 0) & 0x400)
                and (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))]


def stat_info(path: Path, authority: Any = None) -> os.stat_result:
    root = copy_root(path, authority)
    if root is None:
        return path.stat()
    if stat.S_ISDIR(_transport(path).lstat().st_mode):
        with _parent(path / ".raiker-stat", root) as parent:
            return _transport(path).stat() if sys.platform == "win32" else os.fstat(parent)
    with reader(path, authority) as handle:
        return os.fstat(handle.fileno())


def exists(path: Path, authority: Any = None) -> bool:
    if copy_root(path, authority) is None:
        return path.exists()
    try:
        stat_info(path, authority)
        return True
    except (FileNotFoundError, NotADirectoryError):
        return False


def is_file(path: Path, authority: Any = None) -> bool:
    if copy_root(path, authority) is None:
        return path.is_file()
    return stat.S_ISREG(stat_info(path, authority).st_mode)


def is_dir(path: Path, authority: Any = None) -> bool:
    if copy_root(path, authority) is None:
        return path.is_dir()
    return stat.S_ISDIR(stat_info(path, authority).st_mode)


def walk(path: Path, authority: Any = None, *, directories: bool = False, root: Path | None = None) -> list[Path]:
    found: list[Path] = []
    pending = [path]
    while pending:
        parent = pending.pop()
        try:
            children = entries(parent, authority, root=root)
        except OSError:
            continue
        for name, is_directory in children:
            child = parent / name
            if is_directory:
                pending.append(child)
                if directories:
                    found.append(child)
            else:
                found.append(child)
    return found
