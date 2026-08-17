from __future__ import annotations

from typing import Any

from raiker.vector.backends import LEXICAL_FALLBACK_BACKEND, resolve_embedding_backend


def semantic_memory_status(
    candidate_count: int = 0,
    *,
    store: Any | None = None,
    owner_principal_id: str | None = None,
) -> dict[str, object]:
    """What semantic memory is doing right now — for writes *and* for reads.

    MEM-03 — this used to hard-code ``embedding_backend: "disabled"``. That was
    truthful about **writes**: semantic memory writes really are off until the
    owner configures a policy and a backend. It was misleading about **reads**,
    because the vector leg of hybrid retrieval ran on every search regardless,
    on the hashing embedding, and nothing said so. A surface that reads
    "disabled" while a lexical vector leg is scoring results is the kind of
    statement this codebase exists not to make.

    Passing *store* resolves the read backend for real. Without one the answer
    is the always-available floor, which is what a caller with no workspace in
    hand is actually looking at.
    """
    backend = (
        resolve_embedding_backend(store, owner_principal_id=owner_principal_id)
        if store is not None
        else LEXICAL_FALLBACK_BACKEND
    )
    return {
        "semantic_writes_enabled": False,
        "vector_writes_enabled": False,
        # Kept for compatibility with existing readers, and still about writes.
        "embedding_backend": "disabled",
        # The read path, stated separately because it is a different answer.
        "retrieval_embedding_backend": backend.model_label,
        "retrieval_embedding_kind": backend.kind,
        "retrieval_is_semantic": backend.semantic,
        "retrieval_backend_reason": backend.reason_code,
        "candidate_count": candidate_count,
        "reason": "phase3_semantic_memory_writes_disabled_until_policy_and_backend_configured",
    }
