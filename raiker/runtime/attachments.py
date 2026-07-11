"""Governed uploaded-attachment validation and storage (web-app task 3).

Uploaded bytes are untrusted data. Everything here fails closed:

* **Images** are stored only when their media type is on the image allowlist,
  their size is under the cap, and their magic bytes actually match the declared
  media type. Stored content is delivered to a model exclusively as an image
  block on a vision-capable profile; the bytes never enter text context or event
  payloads.
* **Documents** (plain text / markdown / csv, PDF, and Word .docx) are stored
  only when their media type is on the document allowlist, their size is under
  the cap, and their bytes pass a type-specific sniff — clean UTF-8 (no NUL) for
  text, a ``%PDF-`` header that pypdf can parse and is not encrypted for PDF, a
  well-formed OOXML zip for .docx. Extraction is local-only (a decode for text,
  pypdf for PDF, stdlib zip+XML for .docx); no document bytes ever leave the
  box. The bounded extracted text becomes an ``untrusted_external`` context item
  during a later prompt turn; it is data, never instructions.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from raiker.contracts.ids import new_id
from raiker.storage.sqlite import SQLiteStore

# Image media types accepted for upload, mapped to the magic-byte prefixes a
# genuine file of that type must start with. Anything else is rejected —
# including a real image whose declared type does not match its bytes.
IMAGE_MEDIA_TYPES: dict[str, tuple[bytes, ...]] = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),  # plus a "WEBP" tag at offset 8, checked below
}

# Hard per-image size cap. Matches the Anthropic Messages API's 5 MB-per-image
# limit. The API body-size override for the upload route is derived from the
# largest attachment cap.
MAX_IMAGE_BYTES = 5_000_000

# Plain-text document media types: extraction is a straight UTF-8 decode, so the
# "magic" check is that the bytes really are clean text (see ``validate_text``).
TEXT_DOCUMENT_MEDIA_TYPES: frozenset[str] = frozenset(
    {"text/plain", "text/markdown", "text/csv"}
)

# PDF and Word (.docx) media types. These are binary containers; extraction is a
# local-only text pull (pypdf for PDF, stdlib zip+XML for docx). No bytes ever
# leave the box — only the bounded extracted text reaches a model, as untrusted
# context, exactly like a plain-text document.
PDF_MEDIA_TYPE = "application/pdf"
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Every document media type the upload route accepts (dispatched by type).
DOCUMENT_MEDIA_TYPES: frozenset[str] = (
    TEXT_DOCUMENT_MEDIA_TYPES | {PDF_MEDIA_TYPE, DOCX_MEDIA_TYPE}
)

# Hard per-document size cap. Matches the Anthropic PDF API's 32 MB request
# limit (also ≈ claude.ai's per-file upload cap), applied to every document
# type. Extracted text is separately bounded by ``MAX_DOCUMENT_TEXT_CHARS``, so
# the byte cap governs only the upload size, never how much lands in context.
MAX_DOCUMENT_BYTES = 32_000_000

# Largest page count read from a PDF (matches the Anthropic PDF API's 100-page
# limit). Extra pages are dropped with a truncated flag rather than rejected.
MAX_PDF_PAGES = 100

# Upper bound on extracted characters folded into context. A defence-in-depth
# cap in this layer; the gatherer additionally caps to its own per-item budget.
MAX_DOCUMENT_TEXT_CHARS = 200_000

# Largest attachment of any kind, used to size the upload route's body cap.
MAX_ATTACHMENT_BYTES = max(MAX_IMAGE_BYTES, MAX_DOCUMENT_BYTES)

# Longest filename persisted; anything longer is truncated (metadata only —
# the name is display information, never a filesystem path).
_MAX_FILENAME_CHARS = 200


class AttachmentValidationError(Exception):
    """Raised when an upload fails validation. ``reason`` is a stable code."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class StoredAttachment:
    attachment_id: str
    kind: str
    filename: str
    media_type: str
    byte_size: int
    sha256: str


def validate_image(media_type: str, data: bytes) -> None:
    """Fail closed unless ``data`` is a real, in-cap image of ``media_type``."""
    if media_type not in IMAGE_MEDIA_TYPES:
        raise AttachmentValidationError(f"unsupported_media_type:{media_type or 'missing'}")
    if not data:
        raise AttachmentValidationError("empty_attachment")
    if len(data) > MAX_IMAGE_BYTES:
        raise AttachmentValidationError(f"attachment_too_large:{len(data)}>{MAX_IMAGE_BYTES}")
    prefixes = IMAGE_MEDIA_TYPES[media_type]
    if not any(data.startswith(prefix) for prefix in prefixes):
        raise AttachmentValidationError("content_does_not_match_media_type")
    if media_type == "image/webp" and data[8:12] != b"WEBP":
        raise AttachmentValidationError("content_does_not_match_media_type")


def store_image(
    store: SQLiteStore, *, filename: str, media_type: str, data: bytes
) -> StoredAttachment:
    """Validate and persist one uploaded image, returning metadata only."""
    validate_image(media_type, data)
    attachment_id = new_id("att_")
    digest = hashlib.sha256(data).hexdigest()
    safe_name = (filename or "attachment").strip()[:_MAX_FILENAME_CHARS] or "attachment"
    store.save_attachment(
        attachment_id=attachment_id,
        kind="image",
        filename=safe_name,
        media_type=media_type,
        sha256=digest,
        data=data,
    )
    return StoredAttachment(
        attachment_id=attachment_id,
        kind="image",
        filename=safe_name,
        media_type=media_type,
        byte_size=len(data),
        sha256=digest,
    )


def load_image(store: SQLiteStore, attachment_id: str) -> dict[str, Any] | None:
    """Return the stored image record (metadata + bytes) or None.

    Re-validates on the way out so a record that somehow bypassed or predates
    validation still fails closed instead of reaching a provider.
    """
    record = store.load_attachment(attachment_id)
    if record is None or record.get("kind") != "image":
        return None
    try:
        validate_image(str(record.get("media_type", "")), bytes(record.get("data", b"")))
    except AttachmentValidationError:
        return None
    return record


def _validate_common(media_type: str, data: bytes) -> None:
    """Allowlist + non-empty + size checks shared by every document type."""
    if media_type not in DOCUMENT_MEDIA_TYPES:
        raise AttachmentValidationError(f"unsupported_media_type:{media_type or 'missing'}")
    if not data:
        raise AttachmentValidationError("empty_attachment")
    if len(data) > MAX_DOCUMENT_BYTES:
        raise AttachmentValidationError(f"attachment_too_large:{len(data)}>{MAX_DOCUMENT_BYTES}")


def _validate_text(data: bytes) -> None:
    """Fail closed unless ``data`` is clean UTF-8 text.

    The NUL check is the text analogue of the image magic-byte sniff: a binary
    file mislabelled as ``text/plain`` fails closed instead of being decoded
    into context.
    """
    if b"\x00" in data:
        raise AttachmentValidationError("content_does_not_match_media_type")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AttachmentValidationError("content_does_not_match_media_type") from exc


def _validate_pdf(data: bytes) -> None:
    """Fail closed unless ``data`` is a real, parseable, non-encrypted PDF."""
    if not data.startswith(b"%PDF-"):
        raise AttachmentValidationError("content_does_not_match_media_type")
    reader = _open_pdf_reader(data)  # fails closed if pypdf is missing/unreadable
    if reader.is_encrypted:
        raise AttachmentValidationError("pdf_encrypted")
    if len(reader.pages) == 0:
        raise AttachmentValidationError("pdf_no_pages")


def _validate_docx(data: bytes) -> None:
    """Fail closed unless ``data`` is a real Word (.docx) OOXML package."""
    # A .docx is a ZIP (PK\x03\x04) whose payload contains word/document.xml.
    if not data.startswith(b"PK\x03\x04"):
        raise AttachmentValidationError("content_does_not_match_media_type")
    import io
    import zipfile

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if "word/document.xml" not in archive.namelist():
                raise AttachmentValidationError("content_does_not_match_media_type")
    except zipfile.BadZipFile as exc:
        raise AttachmentValidationError("content_does_not_match_media_type") from exc


def validate_document(media_type: str, data: bytes) -> None:
    """Fail closed unless ``data`` is a real, in-cap document of ``media_type``.

    Dispatches on the declared media type: plain-text formats must be clean
    UTF-8, PDFs must parse (and not be encrypted), .docx must be a well-formed
    OOXML package. Anything off the allowlist, empty, or over the size cap fails
    closed before type-specific checks run.
    """
    _validate_common(media_type, data)
    if media_type in TEXT_DOCUMENT_MEDIA_TYPES:
        _validate_text(data)
    elif media_type == PDF_MEDIA_TYPE:
        _validate_pdf(data)
    elif media_type == DOCX_MEDIA_TYPE:
        _validate_docx(data)
    else:  # pragma: no cover — guarded by _validate_common's allowlist
        raise AttachmentValidationError(f"unsupported_media_type:{media_type or 'missing'}")


def _open_pdf_reader(data: bytes) -> Any:
    """Return a pypdf reader for ``data``, failing closed on any problem.

    The import is lazy so a deployment without pypdf rejects PDF uploads with an
    honest reason rather than crashing at import time. A corrupt PDF is likewise
    a fail-closed validation error, never a silent empty extraction.
    """
    try:
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError
    except ImportError as exc:
        raise AttachmentValidationError("pdf_extraction_unavailable") from exc
    import io

    try:
        return PdfReader(io.BytesIO(data))
    except (PyPdfError, ValueError, OSError) as exc:
        raise AttachmentValidationError("pdf_unreadable") from exc


def _extract_pdf_text(data: bytes) -> str:
    """Bounded local text extraction from a validated PDF (≤ MAX_PDF_PAGES)."""
    reader = _open_pdf_reader(data)
    parts: list[str] = []
    for page in reader.pages[:MAX_PDF_PAGES]:
        try:
            parts.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 — a bad page must not abort extraction
            continue
    return "\n".join(parts)[:MAX_DOCUMENT_TEXT_CHARS]


def _extract_docx_text(data: bytes) -> str:
    """Bounded local text extraction from a validated .docx (stdlib only)."""
    import io
    import xml.etree.ElementTree as ET
    import zipfile

    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        xml_bytes = archive.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    # Join paragraph text: each <w:p> becomes a line, <w:t> runs its text.
    lines: list[str] = []
    for paragraph in root.iter(f"{ns}p"):
        runs = [node.text or "" for node in paragraph.iter(f"{ns}t")]
        lines.append("".join(runs))
    return "\n".join(lines)[:MAX_DOCUMENT_TEXT_CHARS]


def extract_document_text(media_type: str, data: bytes) -> str:
    """Return the bounded extracted text of a validated document.

    Plain-text formats decode directly; PDFs and .docx are extracted locally
    (pypdf / stdlib zip+XML). Every path truncates to ``MAX_DOCUMENT_TEXT_CHARS``
    so a large upload can never fold an unbounded blob into context. The caller
    must have validated the bytes first.
    """
    if media_type in TEXT_DOCUMENT_MEDIA_TYPES:
        return data.decode("utf-8", errors="replace")[:MAX_DOCUMENT_TEXT_CHARS]
    if media_type == PDF_MEDIA_TYPE:
        return _extract_pdf_text(data)
    if media_type == DOCX_MEDIA_TYPE:
        return _extract_docx_text(data)
    return ""  # pragma: no cover — validated media types only


def store_document(
    store: SQLiteStore, *, filename: str, media_type: str, data: bytes
) -> StoredAttachment:
    """Validate and persist one uploaded document, returning metadata only."""
    validate_document(media_type, data)
    attachment_id = new_id("att_")
    digest = hashlib.sha256(data).hexdigest()
    safe_name = (filename or "attachment").strip()[:_MAX_FILENAME_CHARS] or "attachment"
    store.save_attachment(
        attachment_id=attachment_id,
        kind="document",
        filename=safe_name,
        media_type=media_type,
        sha256=digest,
        data=data,
    )
    return StoredAttachment(
        attachment_id=attachment_id,
        kind="document",
        filename=safe_name,
        media_type=media_type,
        byte_size=len(data),
        sha256=digest,
    )


def load_document(store: SQLiteStore, attachment_id: str) -> dict[str, Any] | None:
    """Return a stored document with its bounded extracted text, or None.

    Re-validates the bytes on the way out (fail closed if a record predates or
    bypassed validation) and attaches an ``extracted_text`` field so the caller
    never has to decode raw bytes itself.
    """
    record = store.load_attachment(attachment_id)
    if record is None or record.get("kind") != "document":
        return None
    media_type = str(record.get("media_type", ""))
    data = bytes(record.get("data", b""))
    try:
        validate_document(media_type, data)
    except AttachmentValidationError:
        return None
    text = extract_document_text(media_type, data)
    return {
        **record,
        "extracted_text": text,
        "extract_truncated": len(text) >= MAX_DOCUMENT_TEXT_CHARS,
    }
