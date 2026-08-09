from __future__ import annotations

import struct
from pathlib import Path

import pytest

from raiker.models.gguf import read_gguf_metadata


def _string(value: str) -> bytes:
    encoded = value.encode()
    return struct.pack("<Q", len(encoded)) + encoded


def _gguf(name: str = "Tiny Model") -> bytes:
    metadata = _string("general.name") + struct.pack("<I", 8) + _string(name)
    metadata += _string("general.architecture") + struct.pack("<I", 8) + _string("llama")
    return b"GGUF" + struct.pack("<IQQ", 3, 0, 2) + metadata


def test_reads_only_bounded_gguf_header_metadata(tmp_path: Path) -> None:
    model = tmp_path / "tiny.Q4_K_M.gguf"
    model.write_bytes(_gguf() + b"x" * 1024)
    result = read_gguf_metadata(model, max_header_bytes=512)
    assert result.name == "Tiny Model"
    assert result.architecture == "llama"
    assert result.quantization == "Q4_K_M"
    assert result.tensor_count == 0


def test_rejects_non_gguf_and_headers_over_limit(tmp_path: Path) -> None:
    invalid = tmp_path / "bad.gguf"
    invalid.write_bytes(b"nope")
    with pytest.raises(ValueError, match="invalid_gguf_magic"):
        read_gguf_metadata(invalid)
    large = tmp_path / "large.gguf"
    large.write_bytes(_gguf("x" * 400))
    with pytest.raises(ValueError, match="gguf_header_too_large"):
        read_gguf_metadata(large, max_header_bytes=64)
