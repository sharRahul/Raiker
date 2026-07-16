from __future__ import annotations

from pathlib import Path
from typing import Any

from raiker.memory.policy import MemorySensitivity, classify_memory_sensitivity
from raiker.memory.store import get_memory, list_memory
from raiker.memory.store import search_memory as _search_memory
from raiker.storage.sqlite import SQLiteStore


def memory_write(
    workspace_root: str | Path,
    text: str,
    *,
    scope: str = "project",
    tags: tuple[str, ...] = (),
    source: str = "agent",
) -> dict[str, Any]:
    _ = (scope, tags, source, SQLiteStore(workspace_root))
    if not text or not text.strip():
        return {
            "status": "failed",
            "error": {"type": "empty_text", "message": "Cannot write empty memory."},
        }
    sensitivity = classify_memory_sensitivity(text)
    if sensitivity in {MemorySensitivity.CREDENTIAL_LIKE, MemorySensitivity.SECRET_LIKE}:
        return {
            "status": "denied",
            "error": {
                "type": "policy_denied",
                "reason": "secret_or_credential_like_memory_blocked",
                "sensitivity": sensitivity.value,
            },
        }
    return {
        "status": "denied",
        "error": {
            "type": "policy_bypass_denied",
            "reason": "memory_write_requires_tool_broker",
        },
    }


def memory_search(
    workspace_root: str | Path,
    query: str,
    *,
    scope: str | None = None,
    max_results: int = 20,
    owner_principal_id: str | None = None,
) -> dict[str, Any]:
    if not query.strip():
        return {"status": "failed", "error": {"type": "empty_query", "message": "Search query cannot be empty."}}
    store = SQLiteStore(workspace_root)
    results = _search_memory(
        query,
        workspace_root=workspace_root,
        scope=scope,
        max_results=max_results,
        store=store,
        owner_principal_id=owner_principal_id,
    )
    return {
        "status": "success",
        "count": len(results),
        "results": [
            {
                "memory_id": r.memory_id,
                "text": r.text[:500],
                "scope": r.scope,
                "sensitivity": r.sensitivity,
                "created_at": r.created_at,
                "tags": list(r.tags),
                "source": r.source,
            }
            for r in results
        ],
    }


def memory_forget(
    workspace_root: str | Path,
    memory_id: str,
) -> dict[str, Any]:
    _ = SQLiteStore(workspace_root)
    if not memory_id.strip():
        return {
            "status": "failed",
            "error": {"type": "missing_memory_id", "message": "memory_id is required."},
        }
    return {
        "status": "denied",
        "error": {
            "type": "policy_bypass_denied",
            "reason": "memory_forget_requires_tool_broker",
        },
    }


def memory_list(
    workspace_root: str | Path,
    *,
    scope: str | None = None,
    limit: int = 50,
    owner_principal_id: str | None = None,
) -> dict[str, Any]:
    results = list_memory(
        workspace_root=workspace_root, scope=scope, limit=limit,
        store=SQLiteStore(workspace_root), owner_principal_id=owner_principal_id,
    )
    return {
        "status": "success",
        "count": len(results),
        "results": [
            {
                "memory_id": r.memory_id,
                "text": r.text[:500],
                "scope": r.scope,
                "sensitivity": r.sensitivity,
                "created_at": r.created_at,
                "tags": list(r.tags),
                "source": r.source,
            }
            for r in results
        ],
    }


def memory_get(
    workspace_root: str | Path,
    memory_id: str,
    *,
    owner_principal_id: str | None = None,
) -> dict[str, Any]:
    entry = get_memory(memory_id, workspace_root=workspace_root, owner_principal_id=owner_principal_id)
    if entry is None:
        return {"status": "failed", "error": {"type": "not_found", "message": f"Memory '{memory_id}' not found."}}
    return {
        "status": "success",
        "memory_id": entry.memory_id,
        "text": entry.text,
        "scope": entry.scope,
        "sensitivity": entry.sensitivity,
        "created_at": entry.created_at,
        "tags": list(entry.tags),
        "source": entry.source,
    }
