"""Canonical non-shell protocol shared by remote command transports."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, BinaryIO

PROTOCOL_VERSION = "raiker-command-v1"
MAX_FRAME_BYTES = 256 * 1024
MAX_ARGV_ITEMS = 512
MAX_ARGUMENT_BYTES = 32 * 1024
_FIELDS = {
    "argv",
    "cwd",
    "max_output_bytes",
    "protocol",
    "run_id",
    "timeout_seconds",
}


@dataclass(frozen=True)
class RemoteCommandEnvelope:
    run_id: str
    argv: tuple[str, ...]
    cwd: str
    timeout_seconds: float
    max_output_bytes: int
    protocol: str = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "timeout_seconds", float(self.timeout_seconds))
        object.__setattr__(self, "max_output_bytes", int(self.max_output_bytes))
        if self.protocol != PROTOCOL_VERSION:
            raise ValueError("remote_command_protocol_unsupported")
        if not self.run_id.strip() or any(char in self.run_id for char in "\r\n\0"):
            raise ValueError("remote_command_run_id_invalid")
        if not self.argv or len(self.argv) > MAX_ARGV_ITEMS:
            raise ValueError("remote_command_argv_invalid")
        if any(
            not value
            or "\0" in value
            or len(value.encode("utf-8")) > MAX_ARGUMENT_BYTES
            for value in self.argv
        ):
            raise ValueError("remote_command_argv_invalid")
        posix = PurePosixPath(self.cwd.replace("\\", "/"))
        windows = PureWindowsPath(self.cwd)
        if (
            not self.cwd
            or "\0" in self.cwd
            or posix.is_absolute()
            or windows.is_absolute()
            or ".." in posix.parts
        ):
            raise ValueError("remote_command_cwd_invalid")
        if not 0 < self.timeout_seconds <= 3600:
            raise ValueError("remote_command_timeout_invalid")
        if not 0 < self.max_output_bytes <= 10_000_000:
            raise ValueError("remote_command_output_limit_invalid")

    def payload(self) -> dict[str, Any]:
        return {
            "argv": list(self.argv),
            "cwd": self.cwd,
            "max_output_bytes": self.max_output_bytes,
            "protocol": self.protocol,
            "run_id": self.run_id,
            "timeout_seconds": self.timeout_seconds,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_payload(self)).hexdigest()


def canonical_payload(envelope: RemoteCommandEnvelope) -> bytes:
    return json.dumps(
        envelope.payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def encode_remote_envelope(envelope: RemoteCommandEnvelope) -> bytes:
    payload = canonical_payload(envelope)
    if len(payload) > MAX_FRAME_BYTES:
        raise ValueError("remote_command_frame_too_large")
    return struct.pack(">I", len(payload)) + payload


def decode_remote_envelope(frame: bytes) -> RemoteCommandEnvelope:
    if len(frame) < 4:
        raise ValueError("remote_command_frame_truncated")
    length = struct.unpack(">I", frame[:4])[0]
    if length > MAX_FRAME_BYTES:
        raise ValueError("remote_command_frame_too_large")
    if len(frame) != length + 4:
        raise ValueError("remote_command_frame_length_invalid")
    try:
        value = json.loads(frame[4:].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("remote_command_frame_invalid") from exc
    if not isinstance(value, dict) or set(value) != _FIELDS:
        raise ValueError("remote_command_fields_invalid")
    try:
        return RemoteCommandEnvelope(
            run_id=str(value["run_id"]),
            argv=tuple(str(item) for item in value["argv"]),
            cwd=str(value["cwd"]),
            timeout_seconds=float(value["timeout_seconds"]),
            max_output_bytes=int(value["max_output_bytes"]),
            protocol=str(value["protocol"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("remote_command_"):
            raise
        raise ValueError("remote_command_frame_invalid") from exc


def read_remote_envelope(stream: BinaryIO) -> RemoteCommandEnvelope:
    header = stream.read(4)
    if len(header) != 4:
        raise ValueError("remote_command_frame_truncated")
    length = struct.unpack(">I", header)[0]
    if length > MAX_FRAME_BYTES:
        raise ValueError("remote_command_frame_too_large")
    payload = stream.read(length)
    return decode_remote_envelope(header + payload)
