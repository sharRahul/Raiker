from __future__ import annotations

import os
import struct
from pathlib import Path

from raiker.models.library import ModelLibraryService
from raiker.storage.sqlite import SQLiteStore


def _gguf(path: Path, name: str = "Test Model") -> None:
    def string(value: str) -> bytes:
        raw = value.encode()
        return struct.pack("<Q", len(raw)) + raw
    path.write_bytes(b"GGUF" + struct.pack("<IQQ", 3, 0, 1) + string("general.name") + struct.pack("<I", 8) + string(name))


def test_scan_never_follows_symlink_outside_approved_root(tmp_path: Path) -> None:
    root = tmp_path / "approved"
    root.mkdir()
    outside = tmp_path / "private"
    outside.mkdir()
    _gguf(outside / "secret.gguf")
    try:
        os.symlink(outside, root / "escape", target_is_directory=True)
    except OSError:
        return
    service = ModelLibraryService(SQLiteStore(tmp_path / "db"))
    service.add_root("owner", root)
    assert service.rescan("owner") == []


def test_approved_root_scan_indexes_complete_gguf_and_groups_shards(tmp_path: Path) -> None:
    root = tmp_path / "models"
    root.mkdir()
    _gguf(root / "solo.Q4_K_M.gguf", "Solo")
    _gguf(root / "large-00001-of-00002.gguf", "Large")
    _gguf(root / "large-00002-of-00002.gguf", "Large")
    service = ModelLibraryService(SQLiteStore(tmp_path / "db"))
    service.add_root("owner", root)
    models = service.rescan("owner")
    assert [model.name for model in models] == ["Large", "Solo"]
    large = next(model for model in models if model.name == "Large")
    assert large.shard_count == 2
    assert large.complete is True


def test_root_must_be_absolute_existing_directory(tmp_path: Path) -> None:
    service = ModelLibraryService(SQLiteStore(tmp_path / "db"))
    for path in (Path("relative"), tmp_path / "missing"):
        try:
            service.add_root("owner", path)
        except ValueError as exc:
            assert str(exc) == "invalid_model_library_root"
        else:
            raise AssertionError("invalid root was accepted")
