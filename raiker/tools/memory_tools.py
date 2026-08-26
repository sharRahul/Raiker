from __future__ import annotations

from pathlib import Path
from typing import Any

from raiker.memory.policy import MemorySensitivity, classify_memory_sensitivity
from raiker.memory.query_embedding import GovernedQueryEmbedder
from raiker.memory.retrieval import retrieve_hybrid_memory
from raiker.memory.store import get_memory, list_memory
from raiker.storage.sqlite import SQLiteStore
from raiker.vector.backends import resolve_embedding_backend


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
    entity_id: str | None = None,
    max_results: int = 20,
    owner_principal_id: str | None = None,
) -> dict[str, Any]:
    """Search approved memory the way the runtime does — all three legs.

    **MEM-11.** This used to call ``search_memory``, which is the lexical index
    and nothing else, while the ambient recall the gatherer injects into the
    same turn used :func:`retrieve_hybrid_memory` — lexical *plus* vector *plus*
    graph. Two different answers to the same question reached the model in one
    turn, and the weaker one was the half the model could actually steer.

    It was also the half that silently ignored the owner's settings: choosing a
    recall backend on the Memory page changed the injected context and left this
    tool exactly as it was, so the interface described a choice that did not
    apply to the search the model ran.

    Both now go through one function. The result names the legs each hit came
    from and the embedding space that was searched, because "recalled by
    similarity" means something different in a learned space than in the hashing
    fallback, and a model reasoning about its own sources should be able to
    tell.
    """
    if not query.strip():
        return {"status": "failed", "error": {"type": "empty_query", "message": "Search query cannot be empty."}}
    store = SQLiteStore(workspace_root)
    query_embedder = GovernedQueryEmbedder(store, owner_principal_id)
    results = retrieve_hybrid_memory(
        store=store,
        query=query,
        scope=scope,
        entity_id=entity_id,
        limit=max_results,
        owner_principal_id=owner_principal_id,
        query_embedder=query_embedder,
    )
    backend = resolve_embedding_backend(store, owner_principal_id=owner_principal_id)
    # Reported from what the graph leg actually anchored on, not from whether an
    # `entity_id` was supplied — since MEM-12 the anchors are resolved from the
    # query when none is. Naming them is the useful half: "the graph leg ran"
    # invites a follow-up question that "it ran from *the NAS*" already answers.
    anchors = (
        [{"entity_id": entity_id, "display_name": "", "entity_type": ""}]
        if entity_id
        else store.match_memory_entities(
            query, owner_principal_id=owner_principal_id
        )
    )
    return {
        "status": "success",
        "count": len(results),
        # What answered, stated rather than implied. `legs` is what ran at all;
        # a caller comparing two searches needs to know the graph leg was idle
        # because no entity was named, not because nothing matched.
        "retrieval": {
            "strategy": "hybrid",
            "legs": ["lexical", "vector"] + (["graph"] if anchors else []),
            "graph_anchors": [
                {
                    "entity_id": str(a["entity_id"]),
                    "name": str(a.get("display_name") or ""),
                    "type": str(a.get("entity_type") or ""),
                }
                for a in anchors
            ],
            "embedding_backend": backend.model_label,
            "embedding_is_semantic": backend.semantic,
        },
        "results": [
            {
                "memory_id": r.memory_id,
                "text": r.text[:500],
                "scope": r.scope,
                "sensitivity": r.sensitivity,
                "created_at": r.created_at,
                "tags": list(r.tags),
                "source": r.source,
                # Which legs found *this* hit, so a lexical-only match is not
                # read as corroborated by three independent signals.
                "sources": list(r.sources),
                "score": round(r.score, 6),
                "trust_label": r.trust_label,
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
