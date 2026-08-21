"""Windows-safe paths for Raiker-owned runtime data.

Workspace paths stay ordinary and user-facing.  Only paths used for Raiker's
own I/O cross this boundary, which adds the Windows extended-length transport
prefix without leaking that prefix into receipts or UI.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_EXTENDED = "\\\\?\\"
_EXTENDED_UNC = "\\\\?\\UNC\\"
_DEVICE = "\\\\.\\"
_NT_DEVICE = "\\??\\"


def _validated_extended(raw: str) -> str:
    upper = raw.upper()
    if raw.startswith(_DEVICE) or raw.startswith(_NT_DEVICE):
        raise ValueError("internal_path_invalid")
    if not raw.startswith(_EXTENDED):
        return ""
    if upper.startswith(_EXTENDED_UNC.upper()):
        tail = raw[len(_EXTENDED_UNC) :]
        parts = [part for part in tail.split("\\") if part]
        if len(parts) < 2:
            raise ValueError("internal_path_invalid")
        return raw
    tail = raw[len(_EXTENDED) :]
    if len(tail) < 3 or tail[1:3] != ":\\" or not tail[0].isalpha():
        raise ValueError("internal_path_invalid")
    return raw


def internal_io_path(path: str | Path) -> Path:
    """Return an absolute path suitable for Raiker-owned internal I/O."""

    raw = str(path)
    if sys.platform == "win32":
        extended = _validated_extended(raw)
        if extended:
            return Path(extended)
    candidate = Path(path)
    if not candidate.is_absolute():
        raise ValueError("internal_path_must_be_absolute")
    resolved = candidate.resolve()
    if sys.platform != "win32":
        return resolved
    normalized = str(resolved)
    if normalized.startswith("\\\\"):
        return Path(_EXTENDED_UNC + normalized[2:])
    drive, _tail = os.path.splitdrive(normalized)
    if not drive:
        raise ValueError("internal_path_invalid")
    return Path(_EXTENDED + normalized)


def display_path(path: str | Path) -> str:
    """Return an ordinary path string for metadata, logs, CLI, and UI."""

    raw = str(path)
    if raw.upper().startswith(_EXTENDED_UNC.upper()):
        return "\\\\" + raw[len(_EXTENDED_UNC) :]
    if raw.startswith(_EXTENDED):
        return raw[len(_EXTENDED) :]
    return raw
