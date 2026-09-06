from __future__ import annotations

import json
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


def test_scan_detects_complete_mlx_directory_without_loading_model_code(tmp_path: Path) -> None:
    root = tmp_path / "models"
    model = root / "Qwen-MLX-4bit"
    model.mkdir(parents=True)
    (model / "config.json").write_text(
        json.dumps({"model_type": "qwen2", "quantization": {"bits": 4}}),
        encoding="utf-8",
    )
    (model / "model.safetensors").write_bytes(b"weights")
    service = ModelLibraryService(SQLiteStore(tmp_path / "db"))
    service.add_root("owner", root)

    models = service.rescan("owner")

    assert len(models) == 1
    assert models[0].format == "mlx"
    assert models[0].name == "Qwen-MLX-4bit"
    assert models[0].architecture == "qwen2"
    assert models[0].quantization == "4-bit"
    assert models[0].to_dict()["format"] == "mlx"


def test_shards_with_the_same_name_in_two_folders_are_two_models(tmp_path: Path) -> None:
    """GCR-27 — the group key was a base name, and `model` is the commonest one.

    A split GGUF is named `model-00001-of-00002.gguf` by every tool that writes
    one, so two unrelated models one folder apart were grouped into a single
    entry: one model's metadata over the other's files, with a shard count, a
    size and a primary path that belonged to neither.
    """
    root = tmp_path / "models"
    (root / "mistral").mkdir(parents=True)
    (root / "qwen").mkdir(parents=True)
    _gguf(root / "mistral" / "model-00001-of-00002.gguf", "Mistral")
    _gguf(root / "mistral" / "model-00002-of-00002.gguf", "Mistral")
    _gguf(root / "qwen" / "model-00001-of-00002.gguf", "Qwen")
    _gguf(root / "qwen" / "model-00002-of-00002.gguf", "Qwen")
    service = ModelLibraryService(SQLiteStore(tmp_path / "db"))
    service.add_root("owner", root)

    models = service.rescan("owner")

    assert sorted(model.name for model in models) == ["Mistral", "Qwen"]
    for model in models:
        assert model.shard_count == 2
        assert model.expected_shards == 2
        assert model.complete is True
        assert model.name.lower() in model.primary_path.lower()


def test_two_shard_sets_declaring_different_totals_stay_separate(tmp_path: Path) -> None:
    """A directory holding `-of-00002` and `-of-00003` holds two incomplete sets.

    The total was taken from the first shard and never checked against the
    others, so mixed declarations were added up into one set that could look
    complete.
    """
    root = tmp_path / "models"
    root.mkdir()
    _gguf(root / "mix-00001-of-00002.gguf", "Two")
    _gguf(root / "mix-00001-of-00003.gguf", "Three")
    service = ModelLibraryService(SQLiteStore(tmp_path / "db"))
    service.add_root("owner", root)

    models = service.rescan("owner")

    assert len(models) == 2
    assert all(model.complete is False for model in models)
    assert sorted(model.expected_shards for model in models) == [2, 3]
