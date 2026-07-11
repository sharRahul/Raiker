"""Governed uploaded-attachment validation and storage (web-app task 3).

Uploaded bytes are untrusted data. Everything here fails closed:

* **Images** are stored only when their media type is on the image allowlist,
  their size is under the cap, and their magic bytes actually match the declared
  media type. Stored content is delivered to a model exclusively as an image
  block on a vision-capable profile; the bytes never enter text context or event
  payloads.
* **Documents** (plain text / markdown / csv) are stored only when their media
  type is on the document allowlist, their size is under the cap, and their
  bytes decode as clean UTF-8 text (no NUL bytes — a binary file mislabelled as
  text fails closed). Extracted text becomes a bounded, ``untrusted_external``
  context item during a later prompt turn; it is data, never instructions.
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

# Hard per-image size cap (matches typical hosted-provider limits). The API
# body-size override for the upload route is derived from this cap.
MAX_IMAGE_BYTES = 5_000_000

# Text-document media types accepted for upload. These are plain-text formats
# only — no PDF/office binaries in this sub-slice (they are heavy and land
# later). Extraction is a straight UTF-8 decode, so the "magic" check is that
# the bytes really are clean text (see ``validate_document``).
DOCUMENT_MEDIA_TYPES: frozenset[str] = frozenset(
    {"text/plain", "text/markdown", "text/csv"}
)

# Hard per-document size cap. Smaller than the image cap: extracted text goes
# straight into the model's text context, which is far more expensive per byte
# than an opaque image block.
MAX_DOCUMENT_BYTES = 2_000_000

# Upper bound on extracted characters folded into context. A defence-in-depth
# cap in this layer; the gatherer additionally caps to its own per-item budget.
MAX_DOCUMENT_TEXT_CHARS = 200_000

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


def validate_document(media_type: str, data: bytes) -> None:
    """Fail closed unless ``data`` is a real, in-cap text document.

    A document is accepted only when its declared media type is on the
    allowlist, it is non-empty and under the size cap, and its bytes decode as
    UTF-8 with no embedded NUL byte. The NUL check is the text analogue of the
    image magic-byte sniff: a binary file mislabelled as ``text/plain`` fails
    closed instead of being decoded into context.
    """
    if media_type not in DOCUMENT_MEDIA_TYPES:
        raise AttachmentValidationError(f"unsupported_media_type:{media_type or 'missing'}")
    if not data:
        raise AttachmentValidationError("empty_attachment")
    if len(data) > MAX_DOCUMENT_BYTES:
        raise AttachmentValidationError(f"attachment_too_large:{len(data)}>{MAX_DOCUMENT_BYTES}")
    if b"\x00" in data:
        raise AttachmentValidationError("content_does_not_match_media_type")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AttachmentValidationError("content_does_not_match_media_type") from exc


def extract_document_text(media_type: str, data: bytes) -> str:
    """Return the bounded UTF-8 text of a validated document.

    Extraction for these plain-text formats is a straight decode; the result is
    truncated to ``MAX_DOCUMENT_TEXT_CHARS`` so a large upload can never fold an
    unbounded blob into context. The caller must have validated the bytes first.
    """
    text = data.decode("utf-8", errors="replace")
    return text[:MAX_DOCUMENT_TEXT_CHARS]


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
