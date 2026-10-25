"""TOOL-46 — the model reads Raiker's own help articles.

The help panel (QUI-L05) shows the guide in ``docs/guide`` to the owner. This
gives a turn the same text, so a question like *how do I connect Gmail?* is
answered from what this install ships rather than from the model's memory of
some other product. Static, local and read-only: it reaches no network, no
store and no workspace file, which is why it declares no risk signal.
"""

from __future__ import annotations

import re
from typing import Any

from raiker.guide import list_sections, read_section

#: The most of one article a call returns.
MAX_HELP_CHARS = 20_000
#: How many articles a search names, and how many matching lines from each.
MAX_HELP_HITS = 5
_MAX_LINES_PER_HIT = 4


def help_read(slug: str = "", query: str = "") -> dict[str, Any]:
    """The article list, one article, or the articles matching a query."""
    sections = list_sections()
    if not sections:
        return {"status": "failed", "error": {"type": "guide_not_bundled"}}
    slug = (slug or "").strip().lower()
    if slug:
        found = read_section(slug)
        if found is None:
            return {
                "status": "failed",
                "error": {"type": "unknown_help_article", "articles": [item.slug for item in sections]},
            }
        section, markdown = found
        return {
            "status": "success",
            "slug": section.slug,
            "title": section.title,
            "text": markdown[:MAX_HELP_CHARS],
            "truncated": len(markdown) > MAX_HELP_CHARS,
        }
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
        found = read_section(item.slug)
        if found is None:
            continue
        lines = found[1].splitlines()
        lowered = [line.lower() for line in lines]
        score = sum(text.count(word) for text in lowered for word in words)
        if score == 0:
            continue
        matching = [
            lines[index].strip()[:300]
            for index, text in enumerate(lowered)
            if lines[index].strip() and all(word in text for word in words)
        ] or [
            lines[index].strip()[:300]
            for index, text in enumerate(lowered)
            if lines[index].strip() and any(word in text for word in words)
        ]
        hits.append((score, {
            "slug": item.slug,
            "title": item.title,
            "lines": matching[:_MAX_LINES_PER_HIT],
        }))
    hits.sort(key=lambda pair: pair[0], reverse=True)
    return {
        "status": "success",
        "query": query,
        "matches": [hit for _score, hit in hits[:MAX_HELP_HITS]],
        "hint": "Read a whole article with slug.",
    }
