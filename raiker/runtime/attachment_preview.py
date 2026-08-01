"""Session-authorized, view-only previews of stored attachments (BUG-07).

A chat attachment used to be a dead chip: the bytes were in the governed store
and there was no way to look at them again. This module is the read side of the
file inspector, and it is deliberately the narrowest one that works:

* **Authorization is a stored fact, not an inference.** ``get`` returns
  something only when ``session_attachment_refs`` holds a row joining this
  attachment, this session and this owner — written by the prompt route after it
  confirmed both halves. A valid attachment id from another conversation, or
  another account, resolves to ``None`` and the route answers 404.
* **The preview is data, never a program.** Text formats come back as plain
  text; Markdown comes back as its *source* text, which the web client renders
  through its escape-first renderer — no HTML is ever produced here, so there is
  no server-rendered markup for a document to smuggle a script through. .docx
  and .xlsx are parsed with stdlib zip+XML into bounded text and cell values;
  nothing in a document is evaluated, and macro-enabled package types are off
  the upload allowlist to begin with.
* **PDFs and images stay bytes.** There is no server-side rasteriser or
  re-encoder: the preview names a same-origin, session-authorized URL and the
  browser displays it — its own viewer for a PDF, an ``<img>`` for a picture.
  Both are served with the *validated* content type, ``nosniff`` and inline
  disposition, so bytes can never be interpreted as anything but what they were
  checked to be. The image allowlist is raster-only (PNG/JPEG/WebP/GIF); SVG is
  not an accepted upload, so no previewable image can carry script at all.
* **Everything else fails visibly.** An unsupported type, a record that no
  longer passes validation, or a parse error becomes an ``unavailable`` preview
  carrying a stable reason — never a blank pane and never a partial render.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from raiker.runtime.attachments import (
    DOCX_MEDIA_TYPE,
    IMAGE_MEDIA_TYPES,
    PDF_MEDIA_TYPE,
    TEXT_DOCUMENT_MEDIA_TYPES,
    XLSX_MEDIA_TYPE,
    AttachmentValidationError,
    extract_document_text,
    extract_xlsx_rows,
    validate_document,
    validate_image,
)
from raiker.storage.sqlite import SQLiteStore

# Upper bound on preview text. Independent of (and far below) the extraction cap
# used for model context: this is a reading pane, and shipping 200k characters
# into a browser to be scrolled would be a denial of service on the client.
MAX_PREVIEW_TEXT_CHARS = 40_000

# Bounds on the table a spreadsheet preview renders.
MAX_PREVIEW_ROWS = 200
MAX_PREVIEW_COLUMNS = 30

# Preview kinds the client renders. ``unavailable`` is always a valid answer.
KIND_TEXT = "text"
KIND_MARKDOWN = "markdown"
KIND_TABLE = "table"
KIND_PDF = "pdf"
KIND_IMAGE = "image"
KIND_UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class AttachmentPreview:
    """One file's safe preview representation. Metadata plus inert content."""

    attachment_id: str
    session_id: str
    filename: str
    media_type: str
    kind: str
    byte_size: int
    text: str = ""
    rows: tuple[tuple[str, ...], ...] = ()
    truncated: bool = False
    pdf_url: str | None = None
    image_url: str | None = None
    unavailable_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "attachment_id": self.attachment_id,
            "session_id": self.session_id,
            "filename": self.filename,
            "media_type": self.media_type,
            "kind": self.kind,
            "byte_size": self.byte_size,
            "text": self.text,
            "rows": [list(row) for row in self.rows],
            "truncated": self.truncated,
            "pdf_url": self.pdf_url,
            "image_url": self.image_url,
            "unavailable_reason": self.unavailable_reason,
        }


def _bytes_preview_url(session_id: str, attachment_id: str, suffix: str) -> str:
    from urllib.parse import quote

    return (
        f"/api/sessions/{quote(session_id, safe='')}"
        f"/attachments/{quote(attachment_id, safe='')}/preview/{suffix}"
    )


def pdf_preview_url(session_id: str, attachment_id: str) -> str:
    """The same-origin, session-authorized URL a PDF preview is served from."""
    return _bytes_preview_url(session_id, attachment_id, "pdf")


def image_preview_url(session_id: str, attachment_id: str) -> str:
    """The same-origin, session-authorized URL an image preview is served from."""
    return _bytes_preview_url(session_id, attachment_id, "image")


class AttachmentPreviewService:
    """Reads previews for attachments this session and owner may actually see."""

    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    def authorized_record(
        self, session_id: str, attachment_id: str, owner_id: str
    ) -> dict[str, Any] | None:
        """Return the stored attachment row, or None when it is not readable here.

        Two independent checks, both required: the session/attachment/owner
        reference must exist, *and* the attachment row itself must still belong
        to this owner (``load_attachment`` scopes on ``owner_principal_id``).
        """
        if not self._store.session_attachment_ref_exists(
            session_id=session_id, attachment_id=attachment_id, owner_principal_id=owner_id
        ):
            return None
        return self._store.load_attachment(attachment_id, owner_principal_id=owner_id)

    def get(self, session_id: str, attachment_id: str, owner_id: str) -> AttachmentPreview | None:
        """Return the safe preview for one authorized attachment, or None."""
        record = self.authorized_record(session_id, attachment_id, owner_id)
        if record is None:
            return None
        return self._preview(session_id, record)

    def pdf_document(
        self, session_id: str, attachment_id: str, owner_id: str
    ) -> tuple[str, bytes] | None:
        """Return ``(filename, bytes)`` for one authorized PDF, or None.

        Re-validates on the way out, so a record that predates or bypassed
        upload validation is never streamed to a browser as a PDF. The filename
        rides along because the route needs it for the inline disposition and a
        second load would re-read the whole blob.
        """
        served = self.served_bytes(session_id, attachment_id, owner_id)
        if served is None or served[1] != PDF_MEDIA_TYPE:
            return None
        return served[0], served[2]

    def image_bytes(
        self, session_id: str, attachment_id: str, owner_id: str
    ) -> tuple[str, str, bytes] | None:
        """Return ``(filename, media_type, bytes)`` for one authorized image.

        The media type comes back with the bytes because the route must pin it
        on the response: the picture is served as exactly the type its magic
        bytes were just checked against, never as a type the client guessed.
        """
        served = self.served_bytes(session_id, attachment_id, owner_id)
        if served is None or served[1] not in IMAGE_MEDIA_TYPES:
            return None
        return served

    def served_bytes(
        self, session_id: str, attachment_id: str, owner_id: str
    ) -> tuple[str, str, bytes] | None:
        """Authorize and re-validate one attachment's raw bytes for display.

        Validation runs again on the way out (magic bytes for an image, a
        parseable non-encrypted document for a PDF), so a record that predates
        or bypassed upload validation is never streamed to a browser.
        """
        record = self.authorized_record(session_id, attachment_id, owner_id)
        if record is None:
            return None
        media_type = str(record.get("media_type", ""))
        data = bytes(record.get("data", b""))
        try:
            if media_type in IMAGE_MEDIA_TYPES:
                validate_image(media_type, data)
            elif media_type == PDF_MEDIA_TYPE:
                validate_document(PDF_MEDIA_TYPE, data)
            else:
                # Nothing else is ever served as raw bytes; text formats reach
                # the client inside the JSON preview, bounded and inert.
                return None
        except AttachmentValidationError:
            return None
        return str(record.get("filename", "")), media_type, data

    def download_bytes(
        self, session_id: str, attachment_id: str, owner_id: str
    ) -> tuple[str, str, bytes] | None:
        """Authorise one attachment for download (BUG-28).

        Download is deliberately *not* ``served_bytes``. That path exists to put
        pixels or a PDF in front of the browser's own viewer, so it is limited to
        the two types that can be displayed safely and re-validates them as
        exactly those types. Taking a file away with you is a different act: a
        generated .docx, a .xlsx, a Markdown report are all legitimate downloads
        and none of them can be displayed inline. So this authorises anything the
        conversation actually holds — the same stored reference, the same owner
        scoping, no wider — and leaves *how* it is delivered to the route, which
        never serves a download as anything the browser will run.

        Returns ``(filename, media_type, bytes)`` or ``None`` when this account
        may not see the file, or when the bytes are no longer retained.
        """
        record = self.authorized_record(session_id, attachment_id, owner_id)
        if record is None:
            return None
        data = bytes(record.get("data", b""))
        if not data:
            # The reference survives but the bytes do not. Distinguishable from
            # "you may not see this" by the caller, so the pane can say the file
            # is no longer retained instead of implying it never existed.
            return None
        return str(record.get("filename", "")), str(record.get("media_type", "")), data

    def list_session_files(self, session_id: str, owner_id: str) -> list[dict[str, Any]]:
        """Metadata for every attachment referenced by one session (no bytes).

        Lets a reloaded conversation redraw its chips: the transcript persists
        prompt text, not the files that rode with it.
        """
        files: list[dict[str, Any]] = []
        for ref in self._store.list_session_attachment_refs(
            session_id=session_id, owner_principal_id=owner_id
        ):
            attachment_id = str(ref.get("attachment_id", ""))
            metadata = self._store.load_attachment_metadata(
                attachment_id, owner_principal_id=owner_id
            )
            if metadata is None:
                continue
            files.append(
                {
                    "attachment_id": attachment_id,
                    "turn_id": str(ref.get("turn_id", "")),
                    "kind": str(metadata.get("kind", "")),
                    "filename": str(metadata.get("filename", "")),
                    "media_type": str(metadata.get("media_type", "")),
                    "byte_size": int(metadata.get("byte_size", 0) or 0),
                    "previewable": is_previewable(str(metadata.get("media_type", ""))),
                    "source": str(ref.get("source", "uploaded")),
                    "created_at": str(metadata.get("created_at", ref.get("created_at", ""))),
                }
            )
        return files

    # ── representations ──────────────────────────────────────────────────

    def _preview(self, session_id: str, record: dict[str, Any]) -> AttachmentPreview:
        media_type = str(record.get("media_type", ""))
        attachment_id = str(record.get("attachment_id", ""))
        filename = str(record.get("filename", ""))
        data = bytes(record.get("data", b""))
        byte_size = int(record.get("byte_size", len(data)) or 0)

        def build(
            kind: str,
            *,
            text: str = "",
            rows: tuple[tuple[str, ...], ...] = (),
            truncated: bool = False,
            pdf_url: str | None = None,
            image_url: str | None = None,
            unavailable_reason: str | None = None,
        ) -> AttachmentPreview:
            return AttachmentPreview(
                attachment_id=attachment_id,
                session_id=session_id,
                filename=filename,
                media_type=media_type,
                byte_size=byte_size,
                kind=kind,
                text=text,
                rows=rows,
                truncated=truncated,
                pdf_url=pdf_url,
                image_url=image_url,
                unavailable_reason=unavailable_reason,
            )

        if not is_previewable(media_type):
            return build(KIND_UNAVAILABLE, unavailable_reason="unsupported_for_preview")
        if media_type in IMAGE_MEDIA_TYPES:
            # Re-validated here as well as on the byte route, so an unreadable
            # record reports itself in the pane instead of rendering as a broken
            # image icon with no explanation.
            try:
                validate_image(media_type, data)
            except AttachmentValidationError as exc:
                return build(KIND_UNAVAILABLE, unavailable_reason=exc.reason)
            return build(KIND_IMAGE, image_url=image_preview_url(session_id, attachment_id))
        try:
            validate_document(media_type, data)
        except AttachmentValidationError as exc:
            # A stored file that no longer validates is reported honestly rather
            # than parsed anyway or rendered as an empty pane.
            return build(KIND_UNAVAILABLE, unavailable_reason=exc.reason)
        if media_type == PDF_MEDIA_TYPE:
            return build(KIND_PDF, pdf_url=pdf_preview_url(session_id, attachment_id))
        try:
            if media_type == XLSX_MEDIA_TYPE:
                rows, truncated = self._bounded_rows(data)
                return build(KIND_TABLE, rows=rows, truncated=truncated)
            text = extract_document_text(media_type, data)
        except Exception as exc:  # noqa: BLE001
            # Malformed XML, a truncated archive, an unreadable page: a parse
            # failure is an unavailable preview, never a 500.
            reason = exc.reason if isinstance(exc, AttachmentValidationError) else "unreadable"
            return build(KIND_UNAVAILABLE, unavailable_reason=reason)
        bounded = text[:MAX_PREVIEW_TEXT_CHARS]
        kind = KIND_MARKDOWN if media_type == "text/markdown" else KIND_TEXT
        return build(kind, text=bounded, truncated=len(text) > len(bounded))

    @staticmethod
    def _bounded_rows(data: bytes) -> tuple[tuple[tuple[str, ...], ...], bool]:
        """The first sheet's cells, clipped to what a reading pane can show."""
        rows, extract_truncated = extract_xlsx_rows(data)
        truncated = extract_truncated or len(rows) > MAX_PREVIEW_ROWS
        bounded: list[tuple[str, ...]] = []
        for row in rows[:MAX_PREVIEW_ROWS]:
            if len(row) > MAX_PREVIEW_COLUMNS:
                truncated = True
            bounded.append(tuple(row[:MAX_PREVIEW_COLUMNS]))
        return tuple(bounded), truncated


def is_previewable(media_type: str) -> bool:
    """True for the file types the inspector knows how to show safely."""
    return media_type in (
        set(TEXT_DOCUMENT_MEDIA_TYPES)
        | {PDF_MEDIA_TYPE, DOCX_MEDIA_TYPE, XLSX_MEDIA_TYPE}
        | set(IMAGE_MEDIA_TYPES)
    )
