from __future__ import annotations

import os

from raiker.auth.secure_io import atomic_write_private, ensure_private_dir


def test_exclusive_write_refuses_existing(tmp_path) -> None:  # type: ignore[no-untyped-def]
    target = tmp_path / ".raiker" / "k"
    assert atomic_write_private(target, b"first", exclusive=True) is True
    # a second exclusive write must not overwrite (symlink-swap / race defense)
    assert atomic_write_private(target, b"second", exclusive=True) is False
    assert target.read_bytes() == b"first"


def test_non_exclusive_replaces(tmp_path) -> None:  # type: ignore[no-untyped-def]
    target = tmp_path / ".raiker" / "k"
    atomic_write_private(target, b"one", exclusive=False)
    atomic_write_private(target, b"two", exclusive=False)
    assert target.read_bytes() == b"two"


def test_private_permissions_posix(tmp_path) -> None:  # type: ignore[no-untyped-def]
    if os.name != "posix":
        return
    target = tmp_path / ".raiker" / "k"
    atomic_write_private(target, b"x", exclusive=True)
    assert (target.stat().st_mode & 0o777) == 0o600
    assert (target.parent.stat().st_mode & 0o777) == 0o700


def test_ensure_private_dir_idempotent(tmp_path) -> None:  # type: ignore[no-untyped-def]
    d = tmp_path / ".raiker"
    ensure_private_dir(d)
    ensure_private_dir(d)
    assert d.is_dir()
