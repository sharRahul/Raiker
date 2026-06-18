from __future__ import annotations


def semantic_memory_status(candidate_count: int = 0) -> dict[str, object]:
    return {
        "semantic_writes_enabled": False,
        "embedding_backend": "disabled",
        "candidate_count": candidate_count,
        "reason": "phase3_semantic_memory_writes_disabled_until_policy_and_backend_configured",
    }
