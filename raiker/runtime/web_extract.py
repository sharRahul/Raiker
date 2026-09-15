"""Structured reads of a page Raiker has already fetched safely.

`web_fetch` answers one question — *what does this page say?* — and answers it
as a wall of prose. A turn that needs the links on a documentation index, the
rows of a pricing table, or the canonical URL and publication date in a page's
metadata has, until now, had two options: ask the model to find them in that
prose, which is a guess dressed as a read, or reach for a browser, which is a
different and much larger grant of authority for a page that never needed one.

This module is the third option, and its whole design is in one sentence:

> **`web_extract` is a parser over the bounded safe fetch, not a second
> internet client.**

Nothing here opens a socket. Every mode takes the body that
:class:`~raiker.runtime.web_access.WebAccessService` already retrieved under the
`web_fetch` gate, the owner's blocklist, the HTTPS-only address guard and the
re-governed redirect chain, and reads structure out of it. So a destination
`web_fetch` may not reach is a destination `web_extract` may not reach either,
by construction rather than by a second copy of the same checks — and there is
no path by which adding a mode here can widen what leaves the machine.

Three consequences are worth stating plainly, because each is a thing the
result must never pretend otherwise about.

* **Every count is bounded, and truncation is said out loud.** A page with four
  thousand links returns :data:`MAX_LINKS` of them and a ``truncation`` block
  that says so. Silent partial extraction is the failure this module exists to
  avoid: a model handed 200 of 4,000 rows with no marker will reason about the
  200 as if they were all of them.
* **No script runs, ever.** ``script``, ``style``, ``iframe`` and their
  neighbours are dropped by the sanitiser before any mode sees the document, so
  a mode cannot be tricked into evaluating page JavaScript — it has none to
  evaluate.
* **A page this cannot read says so in a type.** When the body carries no
  usable content because the page builds itself in the browser, the result is
  ``static_content_insufficient`` — a typed, honest "a browser would be needed
  here". It is a *statement*, not an escalation: whether a browser capability
  may then be proposed is a separate governed decision that this module has no
  part in and grants nothing towards.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

from raiker.models.tool_registry import _EXTRACT_MODES
from raiker.runtime.web_sanitize import sanitize_html, sanitize_text

#: The modes `web_extract` understands, taken from the registry the model's
#: schema is generated from. Imported rather than restated: a mode advertised
#: and not implemented is refused at the boundary with a name the model just
#: read in its own schema, which is the most confusing failure available. One
#: tuple, two readers, no drift.
EXTRACT_MODES = _EXTRACT_MODES

#: Parser resource limits. Each exists because the alternative is an unbounded
#: copy of somebody else's page entering a context window.
MAX_EXTRACT_CHARS = 20_000
MAX_LINKS = 200
MAX_TABLES = 10
MAX_TABLE_ROWS = 100
MAX_TABLE_COLUMNS = 20
MAX_METADATA_ENTRIES = 60
MAX_STRUCTURED_BLOCKS = 10
MAX_STRUCTURED_CHARS = 8_000
MAX_FIELD_CHARS = 500

#: Below this much readable text, a page that also carried script blocks is far
#: more likely to be a client-rendered application than a short article. The
#: threshold is a heuristic and is reported as one — the result says *why* it
#: concluded static content was insufficient, so a reader can disagree with it.
MIN_STATIC_TEXT_CHARS = 200

#: The `<meta>` names and properties worth returning. An unbounded copy of every
#: meta tag is mostly analytics identifiers, which is somebody's tracking
#: surface rather than material an answer should be drawn from.
_META_PREFIXES = ("og:", "twitter:", "article:", "dc.", "dcterms.")
_META_NAMES = frozenset({
    "description", "author", "keywords", "generator", "robots",
    "publish-date", "publication_date", "date", "language", "title",
})

_WHITESPACE = re.compile(r"\s+")


def _clip(value: str, limit: int = MAX_FIELD_CHARS) -> str:
    text = _WHITESPACE.sub(" ", value).strip()
    return text[:limit]


@dataclass
class _Link:
    href: str
    text: str


class _LinkParser(HTMLParser):
    """Anchors, resolved against the final URL and bounded in number."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self._base = base_url
        self._current: str | None = None
        self._buffer: list[str] = []
        self.links: list[_Link] = []
        self.overflowed = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href") or ""
        # A `javascript:` or `data:` href is not a destination anything here can
        # or should follow, and returning one invites a later caller to try.
        resolved = urljoin(self._base, href.strip())
        if urlparse(resolved).scheme not in ("http", "https"):
            self._current = None
            return
        self._current = resolved
        self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._current is None:
            return
        if len(self.links) >= MAX_LINKS:
            self.overflowed = True
            self._current = None
            return
        self.links.append(_Link(href=self._current, text=_clip("".join(self._buffer), 200)))
        self._current = None
        self._buffer = []


class _TableParser(HTMLParser):
    """Tables as rows of cell text, bounded in every dimension."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self.overflowed = False
        self._rows: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            if len(self.tables) >= MAX_TABLES:
                self.overflowed = True
                self._rows = None
                return
            self._rows = []
        elif tag == "tr" and self._rows is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            if len(self._row) < MAX_TABLE_COLUMNS:
                self._row.append(_clip("".join(self._cell), 200))
            else:
                self.overflowed = True
            self._cell = None
        elif tag == "tr" and self._row is not None and self._rows is not None:
            if len(self._rows) < MAX_TABLE_ROWS:
                self._rows.append(self._row)
            else:
                self.overflowed = True
            self._row = None
        elif tag == "table" and self._rows is not None:
            self.tables.append(self._rows)
            self._rows = None


class _MetadataParser(HTMLParser):
    """`<title>`, `<meta>` and `<link rel=canonical>`, plus JSON-LD blocks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta: dict[str, str] = {}
        self.canonical = ""
        self.structured: list[str] = []
        self.script_blocks = 0
        self._in_title = False
        self._in_ld = False
        self._ld: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        mapping = {key.lower(): (value or "") for key, value in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = (mapping.get("name") or mapping.get("property") or "").strip().lower()
            content = mapping.get("content", "")
            if not key or not content or len(self.meta) >= MAX_METADATA_ENTRIES:
                return
            if key in _META_NAMES or key.startswith(_META_PREFIXES):
                self.meta[key] = _clip(content)
        elif tag == "link" and "canonical" in mapping.get("rel", "").lower():
            self.canonical = _clip(mapping.get("href", ""))
        elif tag == "script":
            self.script_blocks += 1
            if "ld+json" in mapping.get("type", "").lower():
                self._in_ld = True
                self._ld = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._in_ld:
            self._ld.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._in_ld:
            self._in_ld = False
            if len(self.structured) < MAX_STRUCTURED_BLOCKS:
                self.structured.append("".join(self._ld)[:MAX_STRUCTURED_CHARS])
            self._ld = []


@dataclass
class ExtractResult:
    """One extraction, with everything a reader needs to judge it."""

    mode: str
    content: str = ""
    title: str = ""
    links: list[dict[str, str]] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    structured_data: list[Any] = field(default_factory=list)
    truncated: bool = False
    truncation_notes: list[str] = field(default_factory=list)
    #: Set when the page's body held too little readable content to work with.
    #: A typed statement about *this* page, not a request for a browser.
    static_insufficient_reason: str | None = None


def extract(
    *,
    mode: str,
    body: str,
    content_type: str,
    final_url: str,
    body_truncated: bool = False,
) -> ExtractResult:
    """Read *mode* out of an already-fetched body.

    The caller owns the network; this owns the parsing. Splitting them that way
    is what makes "same egress boundary as `web_fetch`" a property of the code
    rather than a promise in a comment.
    """
    is_html = "html" in content_type or body.lstrip()[:1] == "<"
    result = ExtractResult(mode=mode)
    if body_truncated:
        result.truncated = True
        result.truncation_notes.append("response_truncated_at_fetch_limit")

    if mode in ("main_content", "article"):
        page = sanitize_html(body, max_chars=MAX_EXTRACT_CHARS) if is_html else sanitize_text(
            body, max_chars=MAX_EXTRACT_CHARS
        )
        result.title = page.title
        result.content = page.text
        result.truncated = result.truncated or page.truncated
        if page.truncated:
            result.truncation_notes.append("content_truncated_at_extract_limit")
        if is_html and len(page.text) < MIN_STATIC_TEXT_CHARS:
            meta = _MetadataParser()
            meta.feed(body)
            if meta.script_blocks:
                result.static_insufficient_reason = (
                    f"the page returned {len(page.text)} characters of readable text "
                    f"alongside {meta.script_blocks} script block(s), so its content is "
                    "most likely built in the browser"
                )
        return result

    if mode == "links":
        parser = _LinkParser(final_url)
        parser.feed(body)
        result.links = [{"url": link.href, "text": link.text} for link in parser.links]
        if parser.overflowed:
            result.truncated = True
            result.truncation_notes.append(f"links_capped_at_{MAX_LINKS}")
        return result

    if mode == "tables":
        tables = _TableParser()
        tables.feed(body)
        result.tables = tables.tables
        if tables.overflowed:
            result.truncated = True
            result.truncation_notes.append("tables_or_cells_capped")
        if not tables.tables:
            result.static_insufficient_reason = "the page's HTML contained no table elements"
        return result

    if mode in ("metadata", "structured_data"):
        meta = _MetadataParser()
        meta.feed(body)
        if mode == "metadata":
            result.title = _clip(meta.title)
            result.metadata = dict(meta.meta)
            if meta.canonical:
                result.metadata["canonical_url"] = meta.canonical
            return result
        for block in meta.structured:
            try:
                result.structured_data.append(json.loads(block))
            except ValueError:
                # A block this build cannot parse is reported as unparsed rather
                # than handed to the model as text to interpret: "here is JSON-LD"
                # and "here is a string that failed to parse" are different claims.
                result.truncation_notes.append("structured_block_unparsed")
                result.truncated = True
        if not result.structured_data and not result.truncation_notes:
            result.static_insufficient_reason = (
                "the page carried no application/ld+json structured data"
            )
        return result

    raise ValueError(f"web_extract_unknown_mode:{mode}")
