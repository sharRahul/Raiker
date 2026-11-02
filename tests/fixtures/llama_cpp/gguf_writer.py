"""Writes minimal, valid GGUF headers so the planner reads real files in tests."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

_U32, _I32, _F32, _BOOL, _STRING, _ARRAY, _U64 = 4, 5, 6, 7, 8, 9, 10


def _string(text: str) -> bytes:
    data = text.encode("utf-8")
    return struct.pack("<Q", len(data)) + data


def _value(value: Any) -> tuple[int, bytes]:
    if isinstance(value, bool):
        return _BOOL, struct.pack("<?", value)
    if isinstance(value, int):
        return _U32, struct.pack("<I", value)
    if isinstance(value, float):
        return _F32, struct.pack("<f", value)
    if isinstance(value, str):
        return _STRING, _string(value)
    if isinstance(value, list):
        if value and isinstance(value[0], str):
            body = struct.pack("<IQ", _STRING, len(value)) + b"".join(_string(item) for item in value)
        else:
            body = struct.pack("<IQ", _I32, len(value)) + b"".join(struct.pack("<i", int(item)) for item in value)
        return _ARRAY, body
    raise TypeError(type(value))


def write_gguf(path: Path, metadata: dict[str, Any], *, pad_bytes: int = 0) -> Path:
    """A GGUF v3 file with ``metadata`` and no tensors, padded to a size."""
    body = struct.pack("<4sIQQ", b"GGUF", 3, 0, len(metadata))
    for key, value in metadata.items():
        kind, encoded = _value(value)
        body += _string(key) + struct.pack("<I", kind) + encoded
    path.write_bytes(body + b"\0" * pad_bytes)
    return path


def llama_metadata(
    *, layers: int = 32, context: int = 131072, embedding: int = 4096, heads: int = 32, kv_heads: int = 8,
    vocab: int = 2000,
) -> dict[str, Any]:
    return {
        "general.architecture": "llama",
        "general.name": "Test Llama",
        "llama.block_count": layers,
        "llama.context_length": context,
        "llama.embedding_length": embedding,
        "llama.attention.head_count": heads,
        "llama.attention.head_count_kv": kv_heads,
        # A large array the planner must skip rather than materialise.
        "tokenizer.ggml.tokens": [f"tok{index}" for index in range(vocab)],
    }
