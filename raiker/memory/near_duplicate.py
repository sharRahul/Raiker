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
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
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
    }
