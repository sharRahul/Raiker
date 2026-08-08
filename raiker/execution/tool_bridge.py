from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from raiker.tools.filesystem import (
    FilesystemSafetyError,
    list_directory,
    read_file,
    stat_path,
)
from raiker.tools.search import glob, grep

CONTAINER_SAFE_TOOLS: frozenset[str] = frozenset(
    {"glob", "grep", "list_directory", "read_file", "stat_path"}
)
_MAX_BRIDGE_BYTES = 1_000_000
BridgeHandler = Callable[[Path, dict[str, Any]], dict[str, Any]]


def _list_directory(root: Path, arguments: dict[str, Any]) -> dict[str, Any]:
    return list_directory(root, str(arguments.get("path", ".")))


def _read_file(root: Path, arguments: dict[str, Any]) -> dict[str, Any]:
    return read_file(
        root,
        str(arguments.get("path", ".")),
        max_bytes=min(int(arguments.get("max_bytes", 200_000)), 200_000),
    )


def _stat_path(root: Path, arguments: dict[str, Any]) -> dict[str, Any]:
    return stat_path(root, str(arguments.get("path", ".")))


def _glob(root: Path, arguments: dict[str, Any]) -> dict[str, Any]:
    return glob(
        root,
        str(arguments.get("pattern", "*")),
        max_results=min(int(arguments.get("max_results", 100)), 100),
    )


def _grep(root: Path, arguments: dict[str, Any]) -> dict[str, Any]:
    return grep(
        root,
        str(arguments.get("query", "")),
        str(arguments.get("path", ".")),
        include=str(arguments.get("include", "*")),
        max_results=min(int(arguments.get("max_results", 100)), 100),
    )


_HANDLERS: dict[str, BridgeHandler] = {
    "glob": _glob,
    "grep": _grep,
    "list_directory": _list_directory,
    "read_file": _read_file,
    "stat_path": _stat_path,
}


def execute_bridge_request(request: dict[str, Any]) -> dict[str, Any]:
    if request.get("version") != 1:
        return {"status": "failed", "error": {"type": "container_bridge_version_invalid"}}
    tool_name = str(request.get("tool_name", ""))
    if tool_name not in CONTAINER_SAFE_TOOLS:
        return {
            "status": "failed",
            "error": {"type": "container_profile_tool_unsupported"},
        }
    arguments = request.get("arguments")
    if not isinstance(arguments, dict):
        return {"status": "failed", "error": {"type": "container_bridge_arguments_invalid"}}
    repository = Path(str(request.get("repository", ""))).resolve()
    if not repository.is_dir():
        return {"status": "failed", "error": {"type": "container_repository_unavailable"}}
    try:
        return _HANDLERS[tool_name](repository, arguments)
    except (FilesystemSafetyError, OSError, TypeError, ValueError) as exc:
        return {"status": "failed", "error": {"type": str(exc)}}


def main() -> int:
    raw = sys.stdin.read(_MAX_BRIDGE_BYTES + 1)
    if len(raw) > _MAX_BRIDGE_BYTES:
        result = {"status": "failed", "error": {"type": "container_bridge_request_too_large"}}
    else:
        try:
            request = json.loads(raw)
        except json.JSONDecodeError:
            request = None
        result = (
            execute_bridge_request(request)
            if isinstance(request, dict)
            else {"status": "failed", "error": {"type": "container_bridge_request_invalid"}}
        )
    sys.stdout.write(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":  # pragma: no cover - exercised through the container boundary
    raise SystemExit(main())
