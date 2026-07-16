from __future__ import annotations

from pathlib import Path
from typing import Any

from raiker.storage.sqlite import SQLiteStore


def vector_get(
    workspace_root: str | Path, vector_id: str, *, owner_principal_id: str | None = None
) -> dict[str, Any]:
    """Resolve a ``vector_id`` (e.g. from ``vector_embedding_runtime`` search
    results) to its stored record — the read half of the embed → store → search →
    retrieve loop.

    This is a governed **read** (like ``memory_get``): it returns to the caller and
    is audited through the ToolBroker read path. The vector table only persists a
    bounded 120-char ``content_preview`` (not the full source text), so that — plus
    metadata — is what is returned. The raw embedding vector is deliberately not
    returned (it is not content and is large). Missing ids fail closed with
    ``not_found``.
    """
    if not isinstance(vector_id, str) or not vector_id.strip():
        return {"status": "failed", "error": {"type": "missing_argument", "message": "vector_id is required."}}
    record = SQLiteStore(workspace_root).get_vector_record(
        vector_id, owner_principal_id=owner_principal_id
    )
    if record is None:
        return {
            "status": "failed",
            "error": {"type": "not_found", "message": f"Vector '{vector_id}' not found."},
        }
    return {
        "status": "success",
        "vector_id": record["vector_id"],
        "content_preview": record["content_preview"],
        "embedding_model": record["embedding_model"],
        "dimensions": record["dimensions"],
        "scope": record["scope"],
        "sensitivity": record["sensitivity"],
        "created_at": record["created_at"],
    }
