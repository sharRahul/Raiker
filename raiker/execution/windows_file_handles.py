"""Windows no-reparse reads and directory pins for scoped filesystem effects.

Strict directory sharing denies delete (rename) AND write (reparse changes).
Guarded parents permit child replacements while remaining nonempty and pinned.
Pin parents before opening a child; checking then opening is not a pin.
"""
from __future__ import annotations

import ctypes
import os
import secrets
from ctypes import wintypes
from pathlib import Path
from typing import Any, BinaryIO

from raiker.storage.internal_paths import display_path


def _absolute(path: Path) -> Path:
    raw = str(path)
    if raw.startswith(("\\\\.\\", "\\??\\")):
        raise ValueError("internal_path_invalid")
    return Path(os.path.abspath(display_path(path)))


def transport_path(path: Path) -> str:
    # internal_io_path resolves symlinks, which would defeat OPEN_REPARSE_POINT.
    # Extend the lexical absolute path instead; every component is opened and
    # validated separately under its already-pinned parent.
    raw = str(_absolute(path))
    return "\\\\?\\UNC\\" + raw[2:] if raw.startswith("\\\\") else "\\\\?\\" + raw


class _FileInformation(ctypes.Structure):
    _fields_ = [
        ("attributes", wintypes.DWORD),
        ("created", wintypes.FILETIME),
        ("accessed", wintypes.FILETIME),
        ("written", wintypes.FILETIME),
        ("volume", wintypes.DWORD),
        ("size_high", wintypes.DWORD),
        ("size_low", wintypes.DWORD),
        ("links", wintypes.DWORD),
        ("index_high", wintypes.DWORD),
        ("index_low", wintypes.DWORD),
    ]


def _error(code: int | None = None) -> OSError:
    # These entry points exist only on Windows; this module is imported and
    # type-checked on other platforms without invoking them.
    return ctypes.WinError(  # type: ignore[attr-defined]
        ctypes.get_last_error() if code is None else code  # type: ignore[attr-defined]
    )


def _kernel() -> Any:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(_FileInformation)]
    kernel.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel.GetFileType.argtypes = [wintypes.HANDLE]
    kernel.GetFileType.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    return kernel


def _open(
    path: Path, *, directory: bool, writable: bool = False, create: bool = False,
    sharing: int | None = None, delete_on_close: bool = False,
) -> int:
    kernel = _kernel()
    # OPEN_EXISTING, OPEN_REPARSE_POINT, BACKUP_SEMANTICS. Never resolve a link
    # before opening it: metadata must describe the entry actually opened.
    access = 0xC0000000 if writable else 0x80000000
    if delete_on_close:
        access |= 0x10000
    share = sharing if sharing is not None else (0 if writable else (1 if directory else 5))
    flags = 0x02200000 | (0x04000000 if delete_on_close else 0)
    handle = kernel.CreateFileW(transport_path(path), access, share, None, 1 if create else 3, flags, None)
    if handle == ctypes.c_void_p(-1).value:
        raise _error()
    try:
        info = _FileInformation()
        if not kernel.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise _error()
        if (info.attributes & 0x400 or bool(info.attributes & 0x10) != directory
                or kernel.GetFileType(handle) != 1):
            raise _error(1920)  # ERROR_CANT_ACCESS_FILE: unsafe entry.
        return int(handle)
    except BaseException:
        kernel.CloseHandle(handle)
        raise


class DirectoryPins:
    """Pin absolute ancestors in order; release only after all I/O has ended."""

    def __init__(self) -> None:
        self._handles: dict[Path, int] = {}
        self._guards: dict[Path, int] = {}

    def __enter__(self) -> DirectoryPins:
        return self

    def pin(self, path: Path) -> None:
        path = _absolute(path)
        for component in (*reversed(path.parents), path):
            if component not in self._handles:
                self._handles[component] = _open(component, directory=True)

    def release(self, path: Path) -> None:
        path = _absolute(path)
        # Keep the directory pinned until the guard's delete-on-close is done.
        guard = self._guards.pop(path, None)
        if guard is not None:
            _kernel().CloseHandle(guard)
        handle = self._handles.pop(path, None)
        if handle is not None:
            _kernel().CloseHandle(handle)

    def close(self) -> None:
        for path in reversed(tuple(self._handles)):
            self.release(path)

    def allow_children(self, path: Path) -> None:
        """Allow child rename/delete without permitting parent redirection.

        Windows child replace needs the parent to share WRITE. A no-delete
        handle pins its name, while an exclusive delete-on-close child keeps it
        nonempty: Windows forbids setting a reparse point on a nonempty folder.
        Establish the guard while the strict pin still denies reparse writes.
        https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-points
        """
        path = _absolute(path)
        self.pin(path)
        if path in self._guards:
            return
        guard = _open(path / f".raiker-pin-{secrets.token_hex(16)}", directory=False,
                      writable=True, create=True, delete_on_close=True)
        try:
            handle = _open(path, directory=True, sharing=3)
        except BaseException:
            _kernel().CloseHandle(guard)
            raise
        old = self._handles[path]
        self._handles[path] = handle
        self._guards[path] = guard
        _kernel().CloseHandle(old)

    def __exit__(self, *_exc: object) -> None:
        self.close()


def regular_reader(path: Path) -> BinaryIO:
    """Open the final entry itself; the caller must keep parents pinned."""
    import msvcrt

    handle = _open(path, directory=False)
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)  # type: ignore[attr-defined]
    except BaseException:
        _kernel().CloseHandle(handle)
        raise
    return os.fdopen(descriptor, "rb")


def fresh_writer(path: Path) -> BinaryIO:
    """Exclusively create a fresh regular staging file; never replace a leaf.

    An exclusive file handle does not prevent hardlink creation on Windows.
    Never use an existing inode for truncating writes, even after a link check.
    """
    import msvcrt

    handle = _open(path, directory=False, writable=True, create=True)
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDWR | os.O_BINARY)  # type: ignore[attr-defined]
    except BaseException:
        _kernel().CloseHandle(handle)
        raise
    return os.fdopen(descriptor, "r+b")
