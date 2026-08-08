"""The agent's read of the repository code map (GAP-BUILD B9)."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


def code_map_search(
    workspace_root: str | Path,
    query: str,
    max_results: Any = 10,
    *,
    store: SQLiteStore | None = None,
    principal_id: str | None = None,
) -> dict[str, Any]:
    """Find where something is defined, without reading the tree file by file.

    Everything is enforced inside :class:`CodeMapService`: the
    ``code_map_indexing`` capability gate (off ⇒ fail closed with the reason), the
    decision mode (``deny`` refuses), and the same workspace containment the git
    tools use to decide which repository "this repository" means.

    What comes back is **coordinates, not content** — a path, a line range, a
    signature, a docstring's first line. Reading the code still goes through
    ``read_file``, so the map can never widen what a turn may touch. The names and
    docstrings it returns were copied out of repository files, so the result is
    labelled untrusted data exactly like a fetched page.
    """
    from raiker.graph.codemap_service import CodeMapService
    from raiker.storage.sqlite import SQLiteStore

    try:
        limit = int(max_results)
    except (TypeError, ValueError):
        limit = 10
    service = CodeMapService(
        workspace_root, store or SQLiteStore(workspace_root), principal_id=principal_id
    )
    return service.search(query, limit=limit)
