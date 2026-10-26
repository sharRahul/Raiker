"""TOOL-46 — the model reads Raiker's own help articles.

The help panel (QUI-L05) shows the guide in ``docs/guide`` to the owner. This
gives a turn the same text, so a question like *how do I connect Gmail?* is
answered from what this install ships rather than from the model's memory of
some other product. Static, local and read-only: it reaches no network, no
store and no workspace file, which is why it declares no risk signal.

It reads a part at a time, the way the panel shows them. An article runs to
900 lines; the question is usually about one heading of it, and the rest is
context the turn pays for and does not use.
"""

from __future__ import annotations

import re
from typing import Any

from raiker.guide import list_sections, read_part

#: The most of one part a call returns.
MAX_HELP_CHARS = 12_000
#: How many parts a search names, and how many matching lines from each.
MAX_HELP_HITS = 5
_MAX_LINES_PER_HIT = 4


def help_read(slug: str = "", query: str = "", part: str = "") -> dict[str, Any]:
    """The article list, one article's intro and parts, one part, or the parts matching a query."""
    sections = list_sections()
    if not sections:
        return {"status": "failed", "error": {"type": "guide_not_bundled"}}
    slug = (slug or "").strip().lower()
    part = (part or "").strip().lower()
    if slug:
        found = read_part(slug, part)
        if found is None:
            known = next((item for item in sections if item.slug == slug), None)
            if known is not None:
                return {
                    "status": "failed",
                    "error": {"type": "unknown_help_part", "parts": [item.id for item in known.parts]},
                }
            return {
                "status": "failed",
                "error": {"type": "unknown_help_article", "articles": [item.slug for item in sections]},
            }
        section, markdown, chosen = found
        answer: dict[str, Any] = {
            "status": "success",
            "slug": section.slug,
            "title": section.title if chosen is None else f"{section.title} › {chosen.title}",
            "text": markdown[:MAX_HELP_CHARS],
            "truncated": len(markdown) > MAX_HELP_CHARS,
        }
        if chosen is None:
            answer["parts"] = [
                {"part": item.id, "title": item.title, "summary": item.summary} for item in section.parts
            ]
            answer["hint"] = "Read one part with slug and part."
        else:
            answer["part"] = chosen.id
        return answer
    words = [word for word in re.findall(r"[a-z0-9]+", (query or "").lower()) if len(word) > 2]
    if not words:
        return {
            "status": "success",
            "articles": [
                {"slug": item.slug, "title": item.title, "summary": item.summary} for item in sections
            ],
        }
    hits: list[tuple[int, dict[str, Any]]] = []
    for item in sections:
        for piece in item.parts:
            lines = piece.markdown.splitlines()
            lowered = [line.lower() for line in lines]
            # A word in the heading says more about the part than the same word
            # once in its body.
            score = sum(text.count(word) for text in lowered for word in words)
            score += sum(5 for word in words if word in piece.title.lower())
            if score == 0:
                continue
            matching = [
                lines[index].strip()[:300]
                for index, text in enumerate(lowered[1:], start=1)
                if lines[index].strip() and all(word in text for word in words)
            ] or [
                lines[index].strip()[:300]
                for index, text in enumerate(lowered[1:], start=1)
                if lines[index].strip() and any(word in text for word in words)
            ]
            hits.append((score, {
                "slug": item.slug,
                "part": piece.id,
                "title": f"{item.title} › {piece.title}",
                "lines": matching[:_MAX_LINES_PER_HIT],
            }))
    hits.sort(key=lambda pair: pair[0], reverse=True)
    return {
        "status": "success",
        "query": query,
        "matches": [hit for _score, hit in hits[:MAX_HELP_HITS]],
        "hint": "Read a matching part with slug and part.",
    }
