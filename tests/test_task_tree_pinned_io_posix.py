"""Standalone dirfd regressions runnable without the app/database dependencies."""
from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from raiker.tools import task_tree_io
from raiker.tools.filesystem import FilesystemSafetyError

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX dirfd implementation")


def _scope(root: Path) -> SimpleNamespace:
    return SimpleNamespace(tree=SimpleNamespace(copy_roots=lambda: [(root, root)]))


@pytest.mark.parametrize("operation", ["read", "write"])
def test_posix_parent_swap_after_pin_stays_on_original_descriptor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str) -> None:
    root = tmp_path / "copy"
    parent = root / "src"
    parent.mkdir(parents=True)
    leaf = parent / "file.txt"
    leaf.write_bytes(b"original")
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "file.txt"
    sentinel.write_bytes(b"PRIVATE_SENTINEL")
    original_parent = task_tree_io._parent
    attacked = False

    @contextlib.contextmanager
    def pin_then_swap(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal attacked
        with original_parent(*args, **kwargs) as fd:
            if not attacked:
                attacked = True
                parent.rename(root / "old_src")
                parent.symlink_to(outside, target_is_directory=True)
            yield fd

    monkeypatch.setattr(task_tree_io, "_parent", pin_then_swap)
    if operation == "read":
        assert task_tree_io.read_bytes(leaf, _scope(root)) == b"original"
    else:
        task_tree_io.write_bytes(leaf, b"changed", _scope(root))
        assert (root / "old_src/file.txt").read_bytes() == b"changed"
    assert attacked
    assert sentinel.read_bytes() == b"PRIVATE_SENTINEL"


@pytest.mark.parametrize("link", ["symlink", "hardlink"])
@pytest.mark.parametrize("operation", ["read", "write"])
def test_posix_link_leaf_is_refused_before_io(tmp_path: Path, link: str, operation: str) -> None:
    root = tmp_path / "copy"
    root.mkdir()
    outside = tmp_path / "sentinel"
    outside.write_bytes(b"PRIVATE_SENTINEL")
    leaf = root / "file.txt"
    if link == "symlink":
        leaf.symlink_to(outside)
    else:
        os.link(outside, leaf)
    with pytest.raises((OSError, FilesystemSafetyError)):
        if operation == "read":
            task_tree_io.read_bytes(leaf, _scope(root))
        else:
            task_tree_io.write_bytes(leaf, b"changed", _scope(root))
    assert outside.read_bytes() == b"PRIVATE_SENTINEL"


def test_posix_regular_binary_write_read_scan_delete(tmp_path: Path) -> None:
    root = tmp_path / "copy"
    root.mkdir()
    scope = _scope(root)
    path = root / "nested/file.bin"
    payload = b"\x00\xff\r\n"
    assert task_tree_io.write_bytes(path, payload, scope) == len(payload)
    assert task_tree_io.read_bytes(path, scope) == payload
    assert task_tree_io.walk(root, scope) == [path]
    task_tree_io.unlink(path, scope)
    assert not path.exists()
