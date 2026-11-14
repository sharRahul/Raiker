# SPDX-License-Identifier: Apache-2.0
"""FIXED-1439 — say when a proposed memory repeats one already approved.

Memory proposals arrive from conversations, and the same fact said twice in
two chats became two proposals that each looked new. Approving both stored
the fact twice, and forgetting it later left the other copy behind.

This is a review aid, not a filter: nothing is withheld or merged. A proposal
whose words closely match an approved memory says so on its card, naming that
memory, and the owner decides. The comparison is lexical and local (word sets,
normalised), so it runs without a model, sends nothing anywhere and gives the
same answer every time.

2026-11-15 — and by meaning, where the owner already lets the built-in
embedding model run (``nearest_by_meaning``): the same fact in other words is
found with the vectors background indexing keeps. The words check runs first
and needs nothing; the meaning check embeds the proposal through the same
governed path recall uses, and says nothing when that path may not run.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any

_WORD = re.compile(r"[a-z0-9]+")
#: Words that carry no fact of their own ("the owner prefers" / "user likes").
_FILLER = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have",
    "i", "in", "is", "it", "its", "me", "my", "of", "on", "or", "owner", "s",
    "that", "the", "their", "they", "this", "to", "user", "was", "with",
})
#: At or above this share of shared words, a proposal is called a near-duplicate.
THRESHOLD = 0.8
#: At or above this cosine in a real embedding space, the same fact said in other
#: words ("I fly out of Lisbon" / "my home airport is LIS"). Deliberately high:
#: a review aid that cries wolf is one the owner stops reading.
MEANING_THRESHOLD = 0.9


def _words(text: str) -> frozenset[str]:
    return frozenset(word for word in _WORD.findall(text.lower()) if word not in _FILLER)


def similarity(left: str, right: str) -> float:
    """Jaccard similarity of the two texts' content words, 0.0–1.0."""
    a, b = _words(left), _words(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def nearest_approved(
    text: str, approved: Iterable[Mapping[str, Any]]
) -> dict[str, Any] | None:
    """The approved memory this text most closely repeats, if any reaches the threshold."""
    best: tuple[float, Mapping[str, Any]] | None = None
    for memory in approved:
        score = similarity(text, str(memory.get("text") or ""))
        if score >= THRESHOLD and (best is None or score > best[0]):
            best = (score, memory)
    if best is None:
        return None
    score, memory = best
    return {
        "memory_id": str(memory.get("memory_id") or ""),
        "text": str(memory.get("text") or ""),
        "similarity": round(score, 2),
        "basis": "words",
    }


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def nearest_by_meaning(
    text: str,
    approved: Iterable[Mapping[str, Any]],
    vectors: Mapping[str, list[float]],
    embed: Callable[[str], list[float] | None],
) -> dict[str, Any] | None:
    """The approved memory this text repeats *in other words*, by embedding.

    Only memories with a stored vector in the same embedding space take part;
    ``embed`` returns ``None`` when the model may not run, and then nothing is
    claimed — the lexical answer stands alone.
    """
    if not vectors:
        return None
    query = embed(text)
    if not query:
        return None
    by_id = {str(memory.get("memory_id") or ""): memory for memory in approved}
    best: tuple[float, str] | None = None
    for memory_id, vector in vectors.items():
        if memory_id not in by_id or len(vector) != len(query):
            continue
        score = _cosine(query, vector)
        if score >= MEANING_THRESHOLD and (best is None or score > best[0]):
            best = (score, memory_id)
    if best is None:
        return None
    score, memory_id = best
    return {
        "memory_id": memory_id,
        "text": str(by_id[memory_id].get("text") or ""),
        "similarity": round(score, 2),
        "basis": "meaning",
    }


def stored_vectors(store: Any, model_label: str, owner_principal_id: str) -> dict[str, list[float]]:
    """Approved memories' stored vectors in one embedding space, by memory id."""
    vectors: dict[str, list[float]] = {}
    for row in store.list_active_memory_vector_embeddings(model_label, owner_principal_id=owner_principal_id):
        try:
            vector = json.loads(str(row["embedding"]))
        except (TypeError, ValueError):
            continue
        if isinstance(vector, list) and vector:
            vectors[str(row["memory_id"])] = [float(value) for value in vector]
    return vectors
