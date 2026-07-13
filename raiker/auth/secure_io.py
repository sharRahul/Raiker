"""Atomic, restrictive-permission writes for local secret files.

Key material (the internal app key, the connector vault key) must never exist on
disk in a world-readable state, even briefly. ``write_bytes`` followed by
``chmod`` leaves a window where the file is created with the process umask.
These helpers create the file with ``0o600`` from the first byte and keep the
containing ``.raiker`` directory ``0o700``.
"""

from __future__ import annotations

import os
from pathlib import Path


def ensure_private_dir(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        os.chmod(directory, 0o700)


def atomic_write_private(path: Path, data: bytes, *, exclusive: bool) -> bool:
    """Write ``data`` to ``path`` with mode ``0o600``, atomically.

    ``exclusive`` uses ``O_EXCL`` so an existing file (or symlink) is never
    followed or overwritten — returns ``False`` in that case. Otherwise the file
    is truncated/created and ``True`` is returned.
    """
    ensure_private_dir(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
    # O_NOFOLLOW: never follow a symlink at the final path component. Combined
    # with O_EXCL (exclusive) or O_TRUNC (replace), this defeats a symlink-swap
    # attack that would otherwise redirect the write through an attacker's link.
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        # Exclusive create lost a race (or a file/symlink already sits here).
        return False
    # Any other OSError (e.g. ELOOP from O_NOFOLLOW hitting a symlink) propagates
    # so a symlink-swap attack fails loudly instead of writing to the wrong place.
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    if os.name == "posix":
        os.chmod(path, 0o600)
    return True
