from __future__ import annotations

from pathlib import Path
from typing import Any

from raiker.tools.filesystem import glob_paths, grep_files


def glob(workspace_root: str | Path, pattern: str, *, max_results: int = 100) -> dict[str, Any]:
    return glob_paths(workspace_root, pattern, max_results=max_results)


def grep(
    workspace_root: str | Path,
    query: str,
    path: str | Path = ".",
    *,
    include: str = "*",
    max_results: int = 100,
) -> dict[str, Any]:
    return grep_files(workspace_root, query, path, include=include, max_results=max_results)
