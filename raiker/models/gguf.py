from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO


@dataclass(frozen=True)
class GgufMetadata:
    path: Path
    version: int
    tensor_count: int
    metadata_count: int
    name: str
    architecture: str
    quantization: str | None
    header_bytes: int


class _Reader:
    def __init__(self, stream: BinaryIO, limit: int) -> None:
        self.stream = stream
        self.limit = limit
        self.used = 0

    def read(self, size: int) -> bytes:
        if size < 0 or self.used + size > self.limit:
            raise ValueError("gguf_header_too_large")
        data = self.stream.read(size)
        self.used += len(data)
        if len(data) != size:
            raise ValueError("truncated_gguf_header")
        return data

    def unpack(self, fmt: str) -> tuple[Any, ...]:
        return struct.unpack(fmt, self.read(struct.calcsize(fmt)))

    def string(self) -> str:
        (length,) = self.unpack("<Q")
        if length > self.limit:
            raise ValueError("gguf_header_too_large")
        return self.read(length).decode("utf-8", errors="replace")


_SCALAR_FORMATS = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}


def _value(reader: _Reader, value_type: int) -> Any:
    if value_type == 8:
        return reader.string()
    if value_type == 9:
        (element_type,) = reader.unpack("<I")
        (count,) = reader.unpack("<Q")
        if count > 1_000_000:
            raise ValueError("gguf_metadata_array_too_large")
        return [_value(reader, element_type) for _ in range(count)]
    fmt = _SCALAR_FORMATS.get(value_type)
    if fmt is None:
        raise ValueError("unsupported_gguf_metadata_type")
    return reader.unpack(fmt)[0]


def read_gguf_metadata(path: Path, max_header_bytes: int = 8_388_608) -> GgufMetadata:
    with path.open("rb") as stream:
        reader = _Reader(stream, max_header_bytes)
        if reader.read(4) != b"GGUF":
            raise ValueError("invalid_gguf_magic")
        version, tensor_count, metadata_count = reader.unpack("<IQQ")
        if version not in {2, 3}:
            raise ValueError("unsupported_gguf_version")
        if metadata_count > 100_000:
            raise ValueError("gguf_metadata_count_too_large")
        metadata: dict[str, Any] = {}
        for _ in range(metadata_count):
            key = reader.string()
            (value_type,) = reader.unpack("<I")
            metadata[key] = _value(reader, value_type)
    quant = re.search(r"(?:^|[.-])((?:Q|IQ)\d[^.]*)\.gguf$", path.name, re.IGNORECASE)
    return GgufMetadata(
        path=path, version=version, tensor_count=tensor_count, metadata_count=metadata_count,
        name=str(metadata.get("general.name") or path.stem),
        architecture=str(metadata.get("general.architecture") or "unknown"),
        quantization=quant.group(1) if quant else None, header_bytes=reader.used,
    )
