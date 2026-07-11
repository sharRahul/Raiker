"""Governed uploaded-attachment validation and storage (web-app task 3).

Uploaded bytes are untrusted data. Everything here fails closed: an upload is
stored only when its media type is on the image allowlist, its size is under
the cap, and its magic bytes actually match the declared media type. Stored
content is delivered to a model exclusively as an image block on a
vision-capable profile; the bytes never enter text context or event payloads.
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
