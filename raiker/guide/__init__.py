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
class GuidePart:
    """One ``## `` heading of an article and the text under it.

    The help panel shows one of these at a time rather than a whole chapter:
    `working-in-chat.md` alone runs to about 900 lines, and the owner who asked
    how approvals work wants the 80 of them about approvals.
    """

    id: str
    title: str
    summary: str
    markdown: str


@dataclass(frozen=True)
class GuideSection:
    slug: str
    title: str
    summary: str
    parts: tuple[GuidePart, ...] = ()


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
    paragraph: list[str] = []
    fenced = False
    for line in markdown.splitlines():
        stripped = line.strip()
        # A fenced block's contents are not prose. Without this the summary for
        # `getting-started` is its first shell command, which describes nothing.
        if stripped.startswith("```"):
            fenced = not fenced
            continue
        if fenced or not stripped:
            # A paragraph that opens in lower case continues a sentence a code
            # block or list interrupted; it describes nothing on its own.
            if paragraph and paragraph[0][:1].islower():
                paragraph = []
            if paragraph:
                break
            continue
        if stripped.startswith("# ") and title is fallback:
            title = stripped[2:].strip()
            continue
        if (
            title is not fallback
            and not stripped.startswith(("#", ">", "|", "-", "*", "`"))
            and not re.match(r"\d+[.)](\s|$)", stripped)
        ):
            paragraph.append(stripped)
            continue
        if paragraph and not paragraph[0][:1].islower():
            break
        paragraph = []
    if paragraph and paragraph[0][:1].islower():
        paragraph = []
    return title, _first_sentence(_plain(" ".join(paragraph)))


def _plain(text: str) -> str:
    """A line of guide Markdown as the words a reader sees.

    A summary is shown as plain text under a heading. Left as Markdown, it
    showed its own asterisks, backticks and link targets.
    """
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(\*\*|__|`)", "", text)
    text = re.sub(r"(?<![\w*])\*(?=\S)([^*]+?)(?<=\S)\*(?!\w)", r"\1", text)
    return re.sub(r"(?<![\w_])_(?=\S)([^_]+?)(?<=\S)_(?!\w)", r"\1", text)


def _first_sentence(text: str) -> str:
    """The paragraph's first sentence, so a summary is a thought and not a wrapped line."""
    match = re.search(r"(?<=[.!?])\s+(?=[A-Z*`(])", text)
    sentence = text[: match.start()] if match else text
    return sentence if len(sentence) <= 200 else sentence[:197].rsplit(" ", 1)[0] + "…"


def part_id(heading: str) -> str:
    """The anchor GitHub gives a heading, so a guide link's ``#fragment`` names a part."""
    lowered = heading.strip().lower()
    kept = re.sub(r"[^a-z0-9 _-]", "", lowered)
    return kept.replace(" ", "-")


def split_parts(markdown: str) -> tuple[str, tuple[GuidePart, ...]]:
    """An article's intro (everything before its first ``## ``) and its parts.

    A ``## `` inside a fenced block is example text, not a heading, so fences
    are tracked. Two headings that anchor to the same id keep GitHub's ``-1``
    suffix rule, so neither part shadows the other.
    """
    intro: list[str] = []
    parts: list[tuple[str, list[str]]] = []
    fenced = False
    for line in markdown.splitlines():
        if line.strip().startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith("## "):
            parts.append((line[3:].strip(), [line]))
            continue
        (parts[-1][1] if parts else intro).append(line)
    seen: dict[str, int] = {}
    built: list[GuidePart] = []
    for heading, lines in parts:
        base = part_id(heading) or "part"
        count = seen.get(base, 0)
        seen[base] = count + 1
        text = "\n".join(lines).strip() + "\n"
        _title, summary = _title_and_summary(f"# {heading}\n" + "\n".join(lines[1:]), heading)
        built.append(GuidePart(
            id=base if count == 0 else f"{base}-{count}",
            title=heading,
            summary=summary,
            markdown=text,
        ))
    return "\n".join(intro).strip() + "\n", tuple(built)


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
        found[slug] = GuideSection(slug=slug, title=title, summary=summary, parts=split_parts(markdown)[1])
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


def read_part(slug: str, part: str) -> tuple[GuideSection, str, GuidePart | None] | None:
    """An article's intro (``part`` empty) or one of its parts, never the whole chapter.

    ``None`` when the article or the part does not exist. The third value is the
    part read, ``None`` for the intro.
    """
    found = read_section(slug)
    if found is None:
        return None
    section, markdown = found
    intro, parts = split_parts(markdown)
    wanted = (part or "").strip().lower()
    if not wanted:
        return section, intro, None
    chosen = next((item for item in parts if item.id == wanted), None)
    if chosen is None:
        # A guide link may name a ``### `` heading. It lands on the part that
        # holds it rather than on nothing.
        chosen = next(
            (
                item for item in parts
                if any(
                    line.startswith("#") and part_id(line.lstrip("#")) == wanted
                    for line in item.markdown.splitlines()
                )
            ),
            None,
        )
    if chosen is None:
        return None
    return section, chosen.markdown, chosen
