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
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from raiker.approval_previews import redact_secret_like_text

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
    "and size; their contents are never embedded."
)


@dataclass(frozen=True)
class TranscriptMessage:
    role: str
    text: str
    timestamp: str | None
    status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "text": self.text,
            "timestamp": self.timestamp,
            "status": self.status,
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
        }


def build_transcript(
    *,
    session_id: str,
    title: str,
    created_at: str | None,
    turns: Sequence[Any],
    files: Sequence[Any] = (),
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
            messages.append(
                TranscriptMessage(
                    role="raiker",
                    text=redact_secret_like_text(summary),
                    timestamp=completed or created,
                    status=status,
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


def _field(record: Any, name: str) -> Any:
    if isinstance(record, dict):
        return record.get(name)
    return getattr(record, name, None)


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
        lines += [f"### {who}{stamp}", "", message.text, ""]
    return "\n".join(lines).rstrip() + "\n"


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
            f'<div class="body">{_escape(message.text)}</div>'
            "</article>"
        )
    parts.append(
        "<footer>Exported from Raiker. This document contains no scripts and "
        "fetches nothing.</footer></main></body></html>"
    )
    return "".join(parts)


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


def _pdf_escape(text: str) -> str:
    out = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    # WinAnsi is what the base-14 fonts speak; anything outside it becomes "?"
    # rather than a mojibake byte sequence that renders as garbage.
    return "".join(char if 32 <= ord(char) < 127 else "?" for char in out)


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
        rows.append(("body", message.text))
        rows.append(("blank", ""))

    pages: list[list[tuple[str, str]]] = [[]]
    for kind, text in rows:
        wrapped = _wrap(text, 92 if kind == "body" else 84) if text else [""]
        for line in wrapped:
            if len(pages[-1]) >= _MAX_LINES:
                pages.append([])
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
            font = "/F2" if kind in ("heading", "who") else "/F1"
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
    first_page_obj = 5  # 1 catalog, 2 pages, 3+4 fonts

    kids = " ".join(f"{first_page_obj + i * 2} 0 R" for i in range(page_count))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(
        f"<< /Type /Pages /Count {page_count} /Kids [{kids}] >>".encode("latin-1")
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    for index, stream in enumerate(page_streams):
        content_obj = first_page_obj + index * 2 + 1
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_PAGE_WIDTH} {_PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
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
