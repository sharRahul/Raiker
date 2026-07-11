"""Uploaded-attachment API (web-app task 3): the governed local attachment store.

POST /api/attachments accepts one base64-encoded image and stores it only after
fail-closed validation (media-type allowlist, size cap, magic-byte sniff that
the bytes really are the declared type). The response is metadata only — the
stored bytes are never echoed back, never logged, and reach a model solely as
an image block on a vision-capable profile during a later prompt turn.
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
    MAX_IMAGE_BYTES,
    AttachmentValidationError,
    store_image,
)
from raiker.runtime.authority.models import Principal
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()

# Base64 inflates by 4/3; anything longer than this cannot decode to an in-cap
# image, so reject before decoding (cheap fail-closed pre-check).
_MAX_BASE64_CHARS = (MAX_IMAGE_BYTES * 4) // 3 + 8


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
    try:
        stored = store_image(
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
