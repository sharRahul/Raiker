"""Conversation transcript export (BUG-22).

A transcript that can only be read inside the app is not the owner's — it is
the app's. This module turns one governed conversation into a file the owner
keeps: HTML, Markdown, or PDF.

What makes it safe to hand out is stated rather than assumed, and the manifest
route exists precisely so the owner sees it *before* the file is produced:

* **Scope is the session, and only the session.** Every read goes through the
  same user/session visibility boundary as the rest of the product, so an export
  can never reach across accounts or pull in a conversation the caller cannot
  already open.
* **Redaction is applied, and named.** Prompt and response text pass through the
  same secret-shaped-value redactor the API responses use, so a key pasted into
  a chat does not leave the machine inside an export.
* **Attachments are listed, not embedded.** A transcript names the files a turn
  carried — filename, media type, byte size — and does not inline their bytes.
  Embedding a 30 MB spreadsheet into an HTML file is not an export, it is a
  copy, and it would put file content into a document whose handling the owner
  has not thought about.
* **Rendering is local and inert.** The HTML carries its own styles inline, has
  no script, and fetches nothing. The PDF is written by the minimal generator
  below rather than by a rendering engine, so producing one opens no process,
  loads no font file, and reaches no network.

**A declared part is exported as the thing it is (BUG-300).** A turn can declare
that a section of its answer *is* a table or a series
(:mod:`raiker.runtime.typed_parts`), and until this an export read the answer as
one string — so an exported transcript of such a turn showed the raw
``raiker:table`` fence and its JSON. That is honest, because the fence is what
the model wrote, and it is not the table the owner was looking at when they
pressed **Export**.

The splitter is pure, so the export obtains the parts from the text it already
holds and nothing about storage changes. What each medium then does with them is
its own decision, and they are deliberately different answers:

* **HTML** gets a real ``<table>`` with a ``<caption>`` and a header row, so a
  screen reader announces a table and a browser's own *Save as PDF* keeps it one.
* **Markdown** gets a GFM table, because a Markdown transcript is a file somebody
  commits or pastes, and a GFM table survives that.
* **PDF** gets a page-width table laid out in Courier — the one base-14 font
  whose columns line up without font metrics.

**A chart is exported as its own numbers.** All three media render a declared
chart as the table behind it, with the kind and caption stated above it. Drawing
the chart would mean a second chart renderer in Python that could disagree with
the one in the browser, and a picture of a series is not more honest than the
series. The numbers are what an owner filing or sending on a transcript needs.

A **refused** block is exported as the refusal it is. It is never dropped: an
export that silently omits a section is a worse answer than one that says a
section was not accepted.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from raiker.approval_previews import redact_secret_like_text
from raiker.runtime.typed_parts import (
    PART_CHART,
    PART_REFUSED,
    PART_TABLE,
    PART_TEXT,
    ContentPart,
    content_parts,
    renders_as_parts,
)

EXPORT_FORMATS = ("html", "markdown", "pdf")

MEDIA_TYPES = {
    "html": "text/html; charset=utf-8",
    "markdown": "text/markdown; charset=utf-8",
    "pdf": "application/pdf",
}

FILE_EXTENSIONS = {"html": "html", "markdown": "md", "pdf": "pdf"}

# What the manifest tells the owner is applied. Stated as a sentence rather than
# a flag, because "redaction: true" tells nobody what was actually done.
REDACTION_POLICY = (
    "Secret-shaped values (API keys, tokens, and credentials) are replaced with "
    "***REDACTED*** in every message. Attached files are listed by name, type, "
    "and size; their contents are never embedded. Citation source titles and "
    "locators are listed; source passages are never embedded. Tables and charts "
    "an answer declared are rendered as tables in the exported file; a chart is "
    "exported as the numbers behind it."
)


_CITATION_MARKER = re.compile(r"(?P<space>[ \t]*)\[(?P<source_id>s[1-9][0-9]{0,5})\]")


@dataclass(frozen=True)
class TranscriptSource:
    source_id: str
    title: str
    locator: str
    kind: str
    tool_name: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "locator": self.locator,
            "kind": self.kind,
            "tool_name": self.tool_name,
        }


@dataclass(frozen=True)
class TranscriptMessage:
    role: str
    text: str
    timestamp: str | None
    status: str | None = None
    sources: tuple[TranscriptSource, ...] = ()
    unresolved_citation_count: int = 0
    #: BUG-300 — the parts this answer declared, empty when it declared none.
    #: Empty is the ordinary case and means "render ``text`` as prose", which is
    #: what every renderer below did before the typed channel existed.
    parts: tuple[ContentPart, ...] = ()

    @property
    def typed_part_count(self) -> int:
        """Declared tables and charts. Refusals are not counted as content."""
        return sum(1 for part in self.parts if part.type in (PART_TABLE, PART_CHART))

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "text": self.text,
            "timestamp": self.timestamp,
            "status": self.status,
            "sources": [source.to_dict() for source in self.sources],
            "unresolved_citation_count": self.unresolved_citation_count,
            "parts": [part.to_dict() for part in self.parts],
        }


@dataclass(frozen=True)
class TranscriptFile:
    filename: str
    media_type: str
    byte_size: int
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "media_type": self.media_type,
            "byte_size": self.byte_size,
            "source": self.source,
        }


@dataclass(frozen=True)
class Transcript:
    """One conversation, ready to render. Already redacted, already scoped."""

    session_id: str
    title: str
    created_at: str | None
    exported_at: str
    messages: tuple[TranscriptMessage, ...]
    files: tuple[TranscriptFile, ...]

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def unresolved_citation_count(self) -> int:
        return sum(message.unresolved_citation_count for message in self.messages)

    @property
    def typed_part_count(self) -> int:
        """How many declared tables and charts this export will render."""
        return sum(message.typed_part_count for message in self.messages)

    def manifest(self) -> dict[str, Any]:
        """What the owner reviews before choosing a format.

        Deliberately complete: counts, the exact files, the redaction policy in
        words, and the formats on offer. A review that says "3 messages" without
        saying what happens to the attached spreadsheet is not a review.
        """
        return {
            "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at,
            "message_count": self.message_count,
            "file_count": len(self.files),
            "files": [file.to_dict() for file in self.files],
            "redaction_policy": REDACTION_POLICY,
            "formats": list(EXPORT_FORMATS),
            "messages": [message.to_dict() for message in self.messages],
            "unresolved_citation_count": self.unresolved_citation_count,
            "typed_part_count": self.typed_part_count,
        }


def build_transcript(
    *,
    session_id: str,
    title: str,
    created_at: str | None,
    turns: Sequence[Any],
    files: Sequence[Any] = (),
    sources_by_turn: Mapping[str, Sequence[Any]] | None = None,
) -> Transcript:
    """Assemble a redacted transcript from stored turns and attachment records.

    ``turns`` are the persisted turn rows (prompt text plus the agent's summary);
    the live per-event timeline is deliberately not replayed, because an export
    is the conversation, not the runtime trace. Governance evidence has its own
    export path in ``raiker.events.export``.
    """
    messages: list[TranscriptMessage] = []
    for turn in turns:
        prompt = _field(turn, "prompt_text")
        summary = _field(turn, "summary")
        created = _field(turn, "created_at")
        completed = _field(turn, "completed_at")
        status = _field(turn, "status")
        if prompt:
            messages.append(
                TranscriptMessage(role="you", text=redact_secret_like_text(prompt), timestamp=created)
            )
        if summary:
            turn_id = str(_field(turn, "turn_id") or "")
            text, sources, unresolved = _portable_answer(
                redact_secret_like_text(summary),
                (sources_by_turn or {}).get(turn_id, ()),
            )
            # BUG-300 — split *after* redaction, so a secret pasted into a cell
            # is replaced before the cell becomes a cell. The prompt above is
            # deliberately not split: the typed channel is how a *model*
            # declares the shape of its answer, and an owner who types a fence
            # into a question has written a question containing a fence.
            declared = tuple(content_parts(text))
            messages.append(
                TranscriptMessage(
                    role="raiker",
                    text=text,
                    timestamp=completed or created,
                    status=status,
                    sources=sources,
                    unresolved_citation_count=unresolved,
                    parts=declared if renders_as_parts(declared) else (),
                )
            )
    return Transcript(
        session_id=session_id,
        title=title or "Untitled conversation",
        created_at=created_at,
        exported_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        messages=tuple(messages),
        files=tuple(
            TranscriptFile(
                filename=str(_field(file, "filename") or "file"),
                media_type=str(_field(file, "media_type") or "application/octet-stream"),
                byte_size=int(_field(file, "byte_size") or 0),
                source=str(_field(file, "source") or "uploaded"),
            )
            for file in files
        ),
    )


def _portable_answer(
    text: str, source_rows: Sequence[Any]
) -> tuple[str, tuple[TranscriptSource, ...], int]:
    """Resolve answer markers against the owner-visible ledger, without passages."""
    visible: dict[str, TranscriptSource] = {}
    for row in source_rows:
        source_id = str(_field(row, "source_id") or "")
        if not re.fullmatch(r"s[1-9][0-9]{0,5}", source_id):
            continue
        visible[source_id] = TranscriptSource(
            source_id=source_id,
            title=redact_secret_like_text(str(_field(row, "title") or "Untitled source")),
            locator=redact_secret_like_text(str(_field(row, "locator") or "")),
            kind=redact_secret_like_text(str(_field(row, "kind") or "source")),
            tool_name=redact_secret_like_text(str(_field(row, "tool_name") or "")),
        )
    used: list[TranscriptSource] = []
    unresolved = 0

    def resolve(match: re.Match[str]) -> str:
        nonlocal unresolved
        source_id = match.group("source_id")
        source = visible.get(source_id)
        if source is None:
            unresolved += 1
            return ""
        if source not in used:
            used.append(source)
        return f"{match.group('space')}[{source_id}]"

    return _CITATION_MARKER.sub(resolve, text), tuple(used), unresolved


def _field(record: Any, name: str) -> Any:
    if isinstance(record, dict):
        return record.get(name)
    return getattr(record, name, None)


# ── Declared parts, shared across the three media (BUG-300) ──────────────────
#
# Each renderer below decides what a table *looks like* in its own medium. What
# they must not each decide separately is what a part *is*, which is why the
# walk and the two labels live here.

#: A refusal in an export says the same sentence the conversation said, minus
#: the reason code: a file is read away from the product and a code is only
#: useful next to a page that explains it.
_REFUSAL_SENTENCE = (
    "Raiker did not accept one declared part of this answer, so it was not rendered."
)

_CHART_KIND_LABELS = {"bar": "Bar chart", "line": "Line chart", "area": "Area chart"}


def _blocks(message: TranscriptMessage) -> list[ContentPart]:
    """The message as parts, whether or not it declared any.

    A message that declared nothing becomes the single text part it has always
    effectively been, so each renderer has one loop rather than two branches.
    """
    if message.parts:
        return list(message.parts)
    return [ContentPart(PART_TEXT, text=message.text)]


def _chart_table(data: dict[str, Any]) -> tuple[str, list[str], list[list[str]]]:
    """A declared chart as the table behind it: ``(title, columns, rows)``.

    Exporting the numbers rather than drawing the picture is deliberate and is
    stated in the module docstring: a second chart renderer in Python could
    disagree with the one in the browser, and the series is what an owner filing
    or sending a transcript on actually needs.
    """
    kind = _CHART_KIND_LABELS.get(str(data.get("kind", "")), "Chart")
    caption = str(data.get("caption", "") or "")
    y_label = str(data.get("y_label", "") or "")
    title = f"{kind} — {caption}" if caption else kind
    series = [dict(entry) for entry in data.get("series", [])]
    columns = [y_label or "Label"]
    columns += [str(entry.get("name", "") or f"Series {index + 1}") for index, entry in enumerate(series)]
    rows: list[list[str]] = []
    for index, label in enumerate(data.get("labels", [])):
        row = [str(label)]
        for entry in series:
            values = entry.get("values", [])
            row.append(_number(values[index]) if index < len(values) else "")
        rows.append(row)
    return title, columns, rows


def _number(value: Any) -> str:
    """A chart value as text, without the ``.0`` every integer would otherwise carry."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def safe_filename(title: str, session_id: str, fmt: str) -> str:
    """A download name that is recognisably this conversation and nothing else.

    Reduced to a conservative character set: a filename is interpreted by an
    operating system, and a title is model- and human-authored text.
    """
    slug = re.sub(r"[^A-Za-z0-9]+", "-", title or "").strip("-").lower()[:60]
    stem = slug or f"conversation-{session_id[:12]}"
    return f"{stem}.{FILE_EXTENSIONS.get(fmt, 'txt')}"


# ── Markdown ─────────────────────────────────────────────────────────────


def render_markdown(transcript: Transcript) -> str:
    lines = [
        f"# {transcript.title}",
        "",
        f"- Conversation: `{transcript.session_id}`",
        f"- Exported: {transcript.exported_at}",
        f"- Messages: {transcript.message_count}",
        f"- Attached files: {len(transcript.files)}",
        "",
        f"> {REDACTION_POLICY}",
        "",
    ]
    if transcript.files:
        lines += ["## Files in this conversation", ""]
        lines += [
            f"- **{file.filename}** — {file.media_type}, {file.byte_size} bytes ({file.source})"
            for file in transcript.files
        ]
        lines.append("")
    lines += ["## Conversation", ""]
    for message in transcript.messages:
        who = "You" if message.role == "you" else "Raiker"
        stamp = f" — {message.timestamp}" if message.timestamp else ""
        lines += [f"### {who}{stamp}", ""]
        for block in _blocks(message):
            lines += _markdown_block(block)
        if message.sources:
            lines += ["#### Sources for this answer", ""]
            lines += [_markdown_source(source) for source in message.sources]
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _markdown_block(part: ContentPart) -> list[str]:
    """One declared part as GFM — a table stays a table when this file is pasted."""
    if part.type == PART_TABLE:
        caption = str(part.data.get("caption", "") or "")
        head = [f"**{_markdown_inline(caption)}**", ""] if caption else []
        return head + _markdown_table(
            [str(column) for column in part.data.get("columns", [])],
            [[str(cell) for cell in row] for row in part.data.get("rows", [])],
        )
    if part.type == PART_CHART:
        title, columns, rows = _chart_table(part.data)
        return [f"**{_markdown_inline(title)}**", "", *_markdown_table(columns, rows)]
    if part.type == PART_REFUSED:
        return [f"> {_REFUSAL_SENTENCE}", ""]
    return [part.text.strip("\n"), ""]


def _markdown_table(columns: list[str], rows: list[list[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(_markdown_cell(column) for column in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    lines += ["| " + " | ".join(_markdown_cell(cell) for cell in row) + " |" for row in rows]
    lines.append("")
    return lines


def _markdown_cell(value: str) -> str:
    """A cell that cannot break out of its row.

    A pipe would end the cell and a newline would end the table, so both are
    neutralised here rather than left to the reader's Markdown renderer.
    """
    return _markdown_inline(value).replace("|", "\\|")


def _markdown_inline(value: str) -> str:
    return value.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").strip()


def _markdown_source(source: TranscriptSource) -> str:
    title = re.sub(r"([\\`*_{}\[\]()#+!|<>])", r"\\\1", source.title)
    locator = re.sub(r"([\\`*_{}\[\]()#+!|<>])", r"\\\1", source.locator)
    context = " · ".join(part for part in (source.kind, source.tool_name) if part)
    suffix = f" ({context})" if context else ""
    location = f" — {locator}" if locator else ""
    return f"- [{source.source_id}] **{title}**{location}{suffix}"


# ── HTML ─────────────────────────────────────────────────────────────────

_HTML_ESCAPES = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}


def _escape(text: str) -> str:
    return "".join(_HTML_ESCAPES.get(char, char) for char in text)


# Print-first, not app-chrome-first: black on white, one column, page breaks
# that never split a message. The same file reads correctly in a browser and
# comes out of Save as PDF looking like a document rather than a screenshot.
_HTML_STYLE = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; padding: 2rem 1.25rem 3rem; background: #fff; color: #12181b;
  font: 15px/1.55 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
main { max-width: 46rem; margin: 0 auto; }
h1 { font-size: 1.6rem; margin: 0 0 .35rem; }
.meta { color: #5a6a70; font-size: .82rem; margin: 0 0 .2rem; }
.policy { margin: 1.25rem 0; padding: .7rem .9rem; border-left: 3px solid #268d91;
  background: #f2f7f7; color: #33474d; font-size: .82rem; }
h2 { font-size: 1.05rem; margin: 2rem 0 .6rem; padding-bottom: .3rem; border-bottom: 1px solid #dfe5e7; }
ul.files { margin: 0; padding-left: 1.2rem; font-size: .86rem; color: #33474d; }
article { margin: 0 0 1.1rem; page-break-inside: avoid; break-inside: avoid; }
.who { font-weight: 700; font-size: .82rem; letter-spacing: .02em; text-transform: uppercase; color: #268d91; }
.who .stamp { font-weight: 400; text-transform: none; letter-spacing: 0; color: #75868c; margin-left: .5rem; }
.body { margin: .3rem 0 0; padding: .7rem .9rem; border: 1px solid #dfe5e7; border-radius: .6rem;
  white-space: pre-wrap; overflow-wrap: anywhere; background: #fbfcfc; }
article.you .body { background: #eef5f5; }
.body + .body { margin-top: .45rem; }
table.declared { width: 100%; margin: .55rem 0 0; border-collapse: collapse; font-size: .85rem;
  page-break-inside: avoid; break-inside: avoid; }
table.declared caption { caption-side: top; text-align: left; font-weight: 700;
  padding: 0 0 .3rem; color: #33474d; }
table.declared th, table.declared td { border: 1px solid #dfe5e7; padding: .3rem .5rem;
  text-align: left; vertical-align: top; overflow-wrap: anywhere; }
table.declared thead th { background: #eef5f5; }
p.refused { margin: .55rem 0 0; padding: .5rem .7rem; border-left: 3px solid #b08900;
  background: #fbf6e8; color: #33474d; font-size: .82rem; }
.answer-sources { margin: .55rem 0 0; padding: .55rem .8rem; border-left: 2px solid #a9c9ca;
  color: #33474d; font-size: .8rem; }
.answer-sources h3 { margin: 0 0 .25rem; font-size: .8rem; }
.answer-sources ul { margin: 0; padding-left: 1.1rem; }
footer { margin-top: 2.5rem; color: #75868c; font-size: .75rem; }
@page { margin: 18mm 15mm; }
@media print { body { padding: 0; } .policy { background: none; } }
""".strip()


def render_html(transcript: Transcript) -> str:
    parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_escape(transcript.title)}</title>",
        f"<style>{_HTML_STYLE}</style>",
        "</head><body><main>",
        f"<h1>{_escape(transcript.title)}</h1>",
        f'<p class="meta">Conversation {_escape(transcript.session_id)}</p>',
        f'<p class="meta">Exported {_escape(transcript.exported_at)} · '
        f"{transcript.message_count} messages · {len(transcript.files)} files</p>",
        f'<p class="policy">{_escape(REDACTION_POLICY)}</p>',
    ]
    if transcript.files:
        parts.append("<h2>Files in this conversation</h2><ul class='files'>")
        parts += [
            f"<li><strong>{_escape(file.filename)}</strong> — {_escape(file.media_type)}, "
            f"{file.byte_size} bytes ({_escape(file.source)})</li>"
            for file in transcript.files
        ]
        parts.append("</ul>")
    parts.append("<h2>Conversation</h2>")
    for message in transcript.messages:
        who = "You" if message.role == "you" else "Raiker"
        stamp = (
            f'<span class="stamp">{_escape(message.timestamp)}</span>' if message.timestamp else ""
        )
        parts.append(
            f'<article class="{_escape(message.role)}">'
            f'<div class="who">{who}{stamp}</div>'
        )
        for block in _blocks(message):
            parts.append(_html_block(block))
        if message.sources:
            parts.append('<section class="answer-sources"><h3>Sources for this answer</h3><ul>')
            for source in message.sources:
                context = " · ".join(
                    part for part in (source.kind, source.tool_name) if part
                )
                suffix = f" ({_escape(context)})" if context else ""
                locator = f" — {_escape(source.locator)}" if source.locator else ""
                parts.append(
                    f"<li>[{_escape(source.source_id)}] <strong>{_escape(source.title)}</strong>"
                    f"{locator}{suffix}</li>"
                )
            parts.append("</ul></section>")
        parts.append("</article>")
    parts.append(
        "<footer>Exported from Raiker. This document contains no scripts and "
        "fetches nothing.</footer></main></body></html>"
    )
    return "".join(parts)


def _html_block(part: ContentPart) -> str:
    """One declared part as HTML.

    A declared table becomes a real ``<table>`` with a ``<caption>`` and a
    header row — which is what makes a screen reader announce it as a table and
    the browser's own *Save as PDF* keep it one, rather than a grid of
    pre-wrapped characters that happens to look aligned.
    """
    if part.type == PART_TABLE:
        return _html_table(
            str(part.data.get("caption", "") or ""),
            [str(column) for column in part.data.get("columns", [])],
            [[str(cell) for cell in row] for row in part.data.get("rows", [])],
        )
    if part.type == PART_CHART:
        title, columns, rows = _chart_table(part.data)
        return _html_table(title, columns, rows)
    if part.type == PART_REFUSED:
        return f'<p class="refused" role="note">{_escape(_REFUSAL_SENTENCE)}</p>'
    return f'<div class="body">{_escape(part.text.strip(chr(10)))}</div>'


def _html_table(caption: str, columns: list[str], rows: list[list[str]]) -> str:
    out = ['<table class="declared">']
    if caption:
        out.append(f"<caption>{_escape(caption)}</caption>")
    out.append("<thead><tr>")
    out += [f'<th scope="col">{_escape(column)}</th>' for column in columns]
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>")
        out += [f"<td>{_escape(cell)}</td>" for cell in row]
        out.append("</tr>")
    out.append("</tbody></table>")
    return "".join(out)


# ── PDF ──────────────────────────────────────────────────────────────────
#
# A deliberately minimal, dependency-free PDF writer. Raiker will not shell out
# to a headless browser or pull in a rendering engine to produce a transcript:
# both would add a process, a font cache, and an attack surface to what is
# fundamentally "lay text out on pages". This emits a valid PDF 1.4 using the
# base-14 Helvetica fonts every reader ships, so nothing is embedded either.
#
# It handles what a transcript needs — wrapped paragraphs, bold headings, page
# breaks — and nothing more. Rich layout belongs in the HTML export, and the
# browser's own Save as PDF renders that faithfully.

_PAGE_WIDTH = 595  # A4 at 72dpi
_PAGE_HEIGHT = 842
_MARGIN = 56
_LINE_HEIGHT = 14
_BODY_SIZE = 10
_MAX_LINES = (_PAGE_HEIGHT - 2 * _MARGIN) // _LINE_HEIGHT

# BUG-300 — a declared table is laid out in Courier, the one base-14 font whose
# every glyph is the same width. Columns in a proportional font would need the
# font's metrics to align, and embedding a metrics table to draw a transcript is
# exactly the dependency this writer exists to avoid. Courier's advance is 0.6em,
# so the usable width divides into whole characters and the table is page-width
# by construction rather than by guessing.
_TABLE_SIZE = 9
_TABLE_COLUMNS = int((_PAGE_WIDTH - 2 * _MARGIN) / (_TABLE_SIZE * 0.6))


# WinAnsi has these, and Raiker's own strings are full of them — an em dash
# between a chart's kind and its caption, an ellipsis where a cell was cut. They
# were rendering as "?" because the filter below only passed ASCII, which made
# the product's own punctuation look like a decoding failure. Each value is the
# WinAnsi code point, which `latin-1` writes as exactly that byte.
_WINANSI = {
    "—": "\x97", "–": "\x96", "…": "\x85", "•": "\x95",
    "‘": "\x91", "’": "\x92", "“": "\x93", "”": "\x94",
    "·": "\xb7", "−": "-", " ": " ",
}


def _pdf_escape(text: str) -> str:
    out = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    # WinAnsi is what the base-14 fonts speak; anything outside it becomes "?"
    # rather than a mojibake byte sequence that renders as garbage.
    return "".join(
        char if 32 <= ord(char) < 127 else _WINANSI.get(char, "?") for char in out
    )


def _wrap(text: str, width: int) -> list[str]:
    lines: list[str] = []
    for raw in text.split("\n"):
        if raw.strip() == "":
            lines.append("")
            continue
        current = ""
        for word in raw.split(" "):
            candidate = f"{current} {word}".strip()
            if len(candidate) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
            # A single word longer than the line is hard-split rather than
            # allowed to run off the page.
            while len(word) > width:
                lines.append(word[:width])
                word = word[width:]
            current = word
        lines.append(current)
    return lines


def _pdf_block(part: ContentPart) -> list[tuple[str, str]]:
    """One declared part as PDF rows, a table already laid out to the page width."""
    if part.type == PART_TABLE:
        return _pdf_table(
            str(part.data.get("caption", "") or ""),
            [str(column) for column in part.data.get("columns", [])],
            [[str(cell) for cell in row] for row in part.data.get("rows", [])],
        )
    if part.type == PART_CHART:
        title, columns, rows = _chart_table(part.data)
        return _pdf_table(title, columns, rows)
    if part.type == PART_REFUSED:
        return [("meta", _REFUSAL_SENTENCE)]
    return [("body", part.text.strip("\n"))]


def _pdf_table(caption: str, columns: list[str], rows: list[list[str]]) -> list[tuple[str, str]]:
    """Lay a table out in fixed-width columns that together fill the text column.

    Widths are shared out in proportion to what each column actually holds, with
    a floor so a narrow column is still legible, and the remainder goes to the
    widest column so the table ends exactly at the right margin. A cell too long
    for its column is cut with an ellipsis — the full value is in the HTML and
    Markdown exports, and a PDF row that wrapped silently would misalign every
    column after it.
    """
    if not columns:
        return []
    widths = _pdf_column_widths(columns, rows)
    out: list[tuple[str, str]] = []
    if caption:
        out.append(("source-heading", caption))
    out.append(("table-head", _pdf_row(columns, widths)))
    out.append(("table-rule", "  ".join("-" * width for width in widths)))
    out += [("table-row", _pdf_row(row, widths)) for row in rows]
    return out


def _pdf_column_widths(columns: list[str], rows: list[list[str]]) -> list[int]:
    gaps = 2 * (len(columns) - 1)
    budget = max(len(columns) * 3, _TABLE_COLUMNS - gaps)
    natural = [
        max([len(_markdown_inline(column))] + [len(_markdown_inline(row[index])) for row in rows if index < len(row)])
        for index, column in enumerate(columns)
    ]
    total = sum(natural) or 1
    widths = [max(3, round(width * budget / total)) for width in natural]
    # Settle the rounding on the widest column, so the table is exactly the
    # width it claims rather than a character or two short of the margin.
    widest = natural.index(max(natural))
    widths[widest] = max(3, widths[widest] + budget - sum(widths))
    return widths


def _pdf_row(cells: list[str], widths: list[int]) -> str:
    out: list[str] = []
    for index, width in enumerate(widths):
        value = _markdown_inline(cells[index]) if index < len(cells) else ""
        if len(value) > width:
            value = (value[: width - 1] + "…") if width > 1 else value[:width]
        out.append(value.ljust(width))
    return "  ".join(out).rstrip()


def render_pdf(transcript: Transcript) -> bytes:
    """Lay the transcript out over as many pages as it needs."""
    rows: list[tuple[str, str]] = [("heading", transcript.title)]
    rows.append(("meta", f"Conversation {transcript.session_id}"))
    rows.append(
        (
            "meta",
            f"Exported {transcript.exported_at} · {transcript.message_count} messages "
            f"· {len(transcript.files)} files",
        )
    )
    rows.append(("meta", REDACTION_POLICY))
    rows.append(("blank", ""))
    if transcript.files:
        rows.append(("heading", "Files in this conversation"))
        for file in transcript.files:
            rows.append(
                ("meta", f"- {file.filename} — {file.media_type}, {file.byte_size} bytes")
            )
        rows.append(("blank", ""))
    rows.append(("heading", "Conversation"))
    for message in transcript.messages:
        who = "You" if message.role == "you" else "Raiker"
        stamp = f"  {message.timestamp}" if message.timestamp else ""
        rows.append(("who", f"{who}{stamp}"))
        for block in _blocks(message):
            rows += _pdf_block(block)
        if message.sources:
            rows.append(("source-heading", "Sources for this answer"))
            for source in message.sources:
                context = " / ".join(
                    part for part in (source.kind, source.tool_name) if part
                )
                locator = f" - {source.locator}" if source.locator else ""
                suffix = f" ({context})" if context else ""
                rows.append(
                    ("source", f"[{source.source_id}] {source.title}{locator}{suffix}")
                )
        rows.append(("blank", ""))

    pages: list[list[tuple[str, str]]] = [[]]
    # The header of the table currently being laid out, so a table that runs
    # over a page break carries its column names onto the next page instead of
    # leaving the reader to count back.
    open_header: tuple[str, str] | None = None
    for kind, text in rows:
        if kind == "table-head":
            open_header = (kind, text)
        elif kind not in ("table-row", "table-rule"):
            open_header = None
        # Table lines are laid out to the page width already; re-wrapping one
        # would break the alignment that makes it a table.
        wrapped = [text] if kind.startswith("table") else (_wrap(text, 92 if kind == "body" else 84) if text else [""])
        for line in wrapped:
            if len(pages[-1]) >= _MAX_LINES:
                pages.append([])
                if open_header is not None and kind in ("table-row", "table-rule"):
                    pages[-1].append(open_header)
            pages[-1].append((kind, line))
    if not pages[-1]:
        pages.pop()
    if not pages:
        pages = [[("meta", "This conversation has no messages.")]]

    contents: list[bytes] = []
    for page in pages:
        stream = ["BT"]
        y = _PAGE_HEIGHT - _MARGIN
        for kind, line in page:
            if kind.startswith("table"):
                font, size = ("/F4" if kind == "table-head" else "/F3"), _TABLE_SIZE
            else:
                font = "/F2" if kind in ("heading", "who", "source-heading") else "/F1"
                size = 14 if kind == "heading" else (10 if kind != "meta" else 8)
            stream.append(f"{font} {size} Tf")
            stream.append(f"1 0 0 1 {_MARGIN} {y} Tm")
            stream.append(f"({_pdf_escape(line)}) Tj")
            y -= _LINE_HEIGHT
        stream.append("ET")
        contents.append("\n".join(stream).encode("latin-1", "replace"))

    return _assemble_pdf(contents)


def _assemble_pdf(page_streams: list[bytes]) -> bytes:
    """Write the object graph. Object 1 is the catalog, 2 the page tree."""
    objects: list[bytes] = []
    page_count = len(page_streams)
    first_page_obj = 7  # 1 catalog, 2 pages, 3..6 fonts

    kids = " ".join(f"{first_page_obj + i * 2} 0 R" for i in range(page_count))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(
        f"<< /Type /Pages /Count {page_count} /Kids [{kids}] >>".encode("latin-1")
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    # Base-14 as well, so a declared table still embeds nothing (BUG-300).
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold /Encoding /WinAnsiEncoding >>")
    for index, stream in enumerate(page_streams):
        content_obj = first_page_obj + index * 2 + 1
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_PAGE_WIDTH} {_PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R /F4 6 0 R >> >> "
                f"/Contents {content_obj} 0 R >>"
            ).encode("latin-1")
        )
        objects.append(
            b"<< /Length " + str(len(stream)).encode("latin-1") + b" >>\nstream\n" + stream + b"\nendstream"
        )

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("latin-1") + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("latin-1")
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode("latin-1")
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    ).encode("latin-1")
    return bytes(out)


def render(transcript: Transcript, fmt: str) -> tuple[bytes, str]:
    """Render to ``fmt``, returning ``(bytes, media_type)``."""
    if fmt == "markdown":
        return render_markdown(transcript).encode("utf-8"), MEDIA_TYPES["markdown"]
    if fmt == "pdf":
        return render_pdf(transcript), MEDIA_TYPES["pdf"]
    if fmt == "html":
        return render_html(transcript).encode("utf-8"), MEDIA_TYPES["html"]
    raise ValueError("export_format_unsupported")
