"""The user guide, resolved as a product asset rather than a repository path.

`docs/guide/` has always held the material the interface was explaining on every
screen — 23,236 characters of it, counted across 53 components — and the product
could not reach a word of it (BUG-208). The only way in was the README's
documentation list, which is not something a person running the app is reading.

This module is the read side of that fix. It finds the guide wherever this
install keeps it, lists what is there, and returns one section's Markdown. It
grants nothing: the guide is static text shipped with Raiker, the API layer
above still authenticates the owner, and a slug never becomes a filesystem path
without first matching a file this module itself listed.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import raiker

# A slug is a file stem and nothing else. Anything outside this alphabet cannot
# describe a guide page, so it is refused before a path is built from it — the
# traversal question is answered by never asking it.
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Order the sections are offered in. A reader arriving with no particular
# question should meet them in the order they would be taught, not the order the
# filesystem happens to return.
_READING_ORDER = (
    "getting-started",
    "connecting-a-model",
    "working-in-chat",
    "memory",
    "working-in-build",
    "permissions-and-runtime-modes",
    "tasks-and-projects",
    "extensions-and-mcp",
    "troubleshooting",
)

# `README.md` is the guide's own contents page. The product renders a section
# list of its own, so including it would offer the reader a list inside a list.
_EXCLUDED_STEMS = frozenset({"readme"})


@dataclass(frozen=True)
class GuideSection:
    slug: str
    title: str
    summary: str


def guide_root() -> Path | None:
    """Where this install keeps the guide, or ``None`` when it carries none.

    `RAIKER_GUIDE_DIR` is authoritative when set: an owner who points Raiker at
    a guide and gets a *different* one silently has been told something untrue,
    so a set-but-unusable override resolves to ``None`` rather than falling
    through. Unset, the guide is `docs/guide` beside the package — which is both
    a source checkout and the layout the release bundle lays down.

    A build that shipped no guide returns ``None`` rather than an empty list, so
    the surface above can say the guide is missing instead of showing nothing
    and implying there is nothing to read.
    """
    override = os.environ.get("RAIKER_GUIDE_DIR", "").strip()
    root = Path(override) if override else Path(raiker.__file__).resolve().parent.parent / "docs" / "guide"
    return root if (root / "getting-started.md").is_file() else None


def _title_and_summary(markdown: str, fallback: str) -> tuple[str, str]:
    """The page's own first heading and first sentence of prose.

    Read from the document rather than stored beside it, so a guide edit cannot
    leave the product describing the page as it used to be.
    """
    title = fallback
    summary = ""
    fenced = False
    for line in markdown.splitlines():
        stripped = line.strip()
        # A fenced block's contents are not prose. Without this the summary for
        # `getting-started` is its first shell command, which describes nothing.
        if stripped.startswith("```"):
            fenced = not fenced
            continue
        if fenced or not stripped:
            continue
        if stripped.startswith("# ") and title is fallback:
            title = stripped[2:].strip()
            continue
        if title is not fallback and not stripped.startswith(("#", ">", "|", "-", "*", "`")):
            summary = stripped
            break
    return title, summary


def list_sections() -> list[GuideSection]:
    """Every readable section, in reading order, with unlisted files after it."""
    root = guide_root()
    if root is None:
        return []
    found: dict[str, GuideSection] = {}
    for path in sorted(root.glob("*.md")):
        slug = path.stem.lower()
        if slug in _EXCLUDED_STEMS or not SLUG_PATTERN.match(slug):
            continue
        try:
            markdown = path.read_text(encoding="utf-8")
        except OSError:
            continue
        title, summary = _title_and_summary(markdown, slug.replace("-", " ").capitalize())
        found[slug] = GuideSection(slug=slug, title=title, summary=summary)
    ordered = [found.pop(slug) for slug in _READING_ORDER if slug in found]
    return ordered + sorted(found.values(), key=lambda section: section.slug)


def read_section(slug: str) -> tuple[GuideSection, str] | None:
    """One section's metadata and Markdown, or ``None`` when there is no such page.

    The slug is matched against the sections this module listed, so the path
    read is one this module already resolved — a caller cannot name a file the
    listing would not have offered.
    """
    if not SLUG_PATTERN.match(slug):
        return None
    root = guide_root()
    if root is None:
        return None
    section = next((item for item in list_sections() if item.slug == slug), None)
    if section is None:
        return None
    path = root / f"{slug}.md"
    try:
        return section, path.read_text(encoding="utf-8")
    except OSError:
        return None
