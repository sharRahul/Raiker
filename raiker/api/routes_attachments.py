"""Uploaded-attachment API (web-app task 3): the governed local attachment store.

POST /api/attachments accepts one base64-encoded upload and stores it only after
fail-closed validation. The declared media type selects the validator:

* **Images** (png/jpeg/webp/gif) — allowlist, 5 MB cap, magic-byte sniff. They
  reach a model solely as an image block on a vision-capable profile.
* **Documents** (plain text / markdown / csv) — allowlist, 2 MB cap, UTF-8/NUL
  sniff. Their extracted text reaches a model as bounded, untrusted context.

The response is metadata only — the stored bytes are never echoed back and are
never logged.
"""

from __future__ import annotations

import base64
import binascii
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import UploadAttachmentRequest
from raiker.api.sessions import ApiSession
from raiker.runtime.attachments import (
    DOCUMENT_MEDIA_TYPES,
    IMAGE_MEDIA_TYPES,
    MAX_ATTACHMENT_BYTES,
    AttachmentValidationError,
    StoredAttachment,
    store_document,
    store_image,
)
from raiker.runtime.authority.models import Principal
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()

# Base64 inflates by 4/3; anything longer than this cannot decode to the largest
# in-cap attachment, so reject before decoding (cheap fail-closed pre-check).
# Per-type size limits are still enforced by the validators after decode.
_MAX_BASE64_CHARS = (MAX_ATTACHMENT_BYTES * 4) // 3 + 8


def _ws(request: Request) -> str | Path:
    return request.app.state.workspace_root  # type: ignore[no-any-return]


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    return AuthMiddleware(_ws(request)).authenticate(request)


@router.post("/api/attachments")
def upload_attachment(
    body: UploadAttachmentRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, object]:
    if len(body.data_base64) > _MAX_BASE64_CHARS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"ok": False, "reason_code": "attachment_too_large"},
        )
    try:
        data = base64.b64decode(body.data_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "reason_code": "invalid_base64"},
        ) from exc
    store = SQLiteStore(_ws(request))
    # The declared media type selects the validator. Anything on neither
    # allowlist is rejected before either store function runs (fail closed).
    if body.media_type in IMAGE_MEDIA_TYPES:
        storer = store_image
    elif body.media_type in DOCUMENT_MEDIA_TYPES:
        storer = store_document
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "ok": False,
                "reason_code": f"unsupported_media_type:{body.media_type or 'missing'}",
            },
        )
    try:
        stored: StoredAttachment = storer(
            store, filename=body.filename, media_type=body.media_type, data=data
        )
    except AttachmentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "reason_code": exc.reason},
        ) from exc
    return {
        "ok": True,
        "attachment_id": stored.attachment_id,
        "kind": stored.kind,
        "filename": stored.filename,
        "media_type": stored.media_type,
        "byte_size": stored.byte_size,
        "sha256": stored.sha256,
    }
