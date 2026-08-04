"""Uploaded-attachment API (web-app task 3): the governed local attachment store.

POST /api/attachments accepts one base64-encoded upload and stores it only after
fail-closed validation. The declared media type selects the validator:

* **Images** (png/jpeg/webp/gif) — allowlist, 5 MB cap, magic-byte sniff. They
  reach a model solely as an image block on a vision-capable profile.
* **Documents** (plain text / markdown / csv, PDF, Word .docx, Excel .xlsx) —
  allowlist, 32 MB cap, per-type sniff. Their locally extracted text reaches a
  model as bounded, untrusted context; the bytes never leave the box.

The response is metadata only — the stored bytes are never echoed back and are
never logged.

The session-scoped preview routes at the bottom of this module are the read
side (BUG-07): they show an already-uploaded file back to the person who
attached it, and only inside the conversation it was attached to. See
``raiker/runtime/attachment_preview.py`` for the authorization rule and the
safe representations.
"""

from __future__ import annotations

import base64
import binascii
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import UploadAttachmentRequest
from raiker.api.sessions import ApiSession
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.runtime.attachment_preview import AttachmentPreviewService
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
from raiker.runtime.source_provenance import SourceProvenanceService
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
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
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
            store, filename=body.filename, media_type=body.media_type, data=data,
            owner_principal_id=auth_data[0].principal_id,
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


# ── Session-scoped file previews (BUG-07: the chat file inspector) ──────────
#
# Every one of these routes answers 404 for anything the caller may not see —
# an unknown id, another account's attachment, or a file that belongs to a
# different conversation. A 403 would confirm the id exists; 404 says nothing.


def _preview_service(request: Request) -> AttachmentPreviewService:
    return AttachmentPreviewService(SQLiteStore(_ws(request)))


def _not_found(reason_code: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"ok": False, "reason_code": reason_code},
    )


@router.get("/api/sessions/{session_id}/attachments")
def list_session_attachments(
    session_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, object]:
    """Metadata for the files this conversation carries. No bytes, no content.

    A reloaded chat restores prompt text but not the files that rode with each
    turn; this is how the transcript redraws its attachment chips.
    """
    files = _preview_service(request).list_session_files(session_id, auth_data[0].principal_id)
    return {"session_id": session_id, "files": files}


@router.get("/api/sessions/{session_id}/attachments/{attachment_id}/preview")
def get_attachment_preview(
    session_id: str,
    attachment_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """One file's safe, view-only preview.

    Bounded text or table rows inline; for a PDF or an image, the same-origin
    URL its bytes are served from. Never the bytes themselves.
    """
    preview = _preview_service(request).get(session_id, attachment_id, auth_data[0].principal_id)
    if preview is None:
        raise _not_found("attachment_preview_not_found")
    return preview.to_dict()


def _inline_filename(filename: str) -> str:
    """An ASCII, quote-free filename safe to place in a Content-Disposition.

    The stored name is user data. Anything that could close the quoted string or
    inject a header parameter is dropped rather than escaped, and an empty
    result falls back to a fixed name.
    """
    cleaned = "".join(
        char for char in filename if char.isascii() and char.isprintable() and char not in '"\\;'
    ).strip()
    return cleaned[:100] or "attachment"


@router.get("/api/sessions/{session_id}/attachments/{attachment_id}/preview/pdf")
def get_attachment_preview_pdf(
    session_id: str,
    attachment_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> Response:
    """Serve one authorized PDF inline for the browser's own viewer."""
    document = _preview_service(request).pdf_document(
        session_id, attachment_id, auth_data[0].principal_id
    )
    if document is None:
        raise _not_found("attachment_preview_not_found")
    filename, data = document
    return _inline_bytes(data, "application/pdf", filename)


@router.get("/api/sessions/{session_id}/attachments/{attachment_id}/preview/image")
def get_attachment_preview_image(
    session_id: str,
    attachment_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> Response:
    """Serve one authorized image inline for an ``<img>`` in the inspector.

    The content type is the one the bytes were just re-validated against (the
    magic-byte sniff in ``validate_image``), pinned with ``nosniff`` — so a file
    can only ever be interpreted as the raster format it actually is. SVG is not
    an accepted upload, so nothing served here can carry script.
    """
    image = _preview_service(request).image_bytes(
        session_id, attachment_id, auth_data[0].principal_id
    )
    if image is None:
        raise _not_found("attachment_preview_not_found")
    filename, media_type, data = image
    return _inline_bytes(data, media_type, filename)


@router.get("/api/sessions/{session_id}/attachments/{attachment_id}/provenance")
def get_attachment_provenance(
    session_id: str,
    attachment_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Which exchange produced this file, and the passage that asked for it (BUG-27).

    A generated document arrived in the transcript with no way back to the
    request behind it. The stored reference already names the turn; this
    resolves it the same way memory provenance is resolved, so both surfaces
    give the same four honest answers — resolved, deleted, changed, or not
    readable here — instead of one of them offering a dead **View source**.
    """
    store = SQLiteStore(_ws(request))
    owner_id = auth_data[0].principal_id
    if not store.session_attachment_ref_exists(
        session_id=session_id, attachment_id=attachment_id, owner_principal_id=owner_id
    ):
        raise _not_found("attachment_unavailable")
    turn_id = ""
    for ref in store.list_session_attachment_refs(
        session_id=session_id, owner_principal_id=owner_id
    ):
        if str(ref.get("attachment_id", "")) == attachment_id:
            turn_id = str(ref.get("turn_id", ""))
            break
    metadata = store.load_attachment_metadata(attachment_id, owner_principal_id=owner_id)
    filename = str((metadata or {}).get("filename", ""))
    excerpt = SourceProvenanceService(store).resolve(
        {"source_session_id": session_id, "source_turn_id": turn_id},
        # The prompt that produced the file is the passage worth highlighting,
        # and it is not stored separately — so the filename is the anchor we
        # actually have. Not found simply means no highlight, which is the
        # `source_changed` answer the resolver already states honestly.
        filename,
        owner_id,
    )
    return {"ok": True, "attachment_id": attachment_id, "filename": filename, **excerpt.to_dict()}


@router.get("/api/sessions/{session_id}/attachments/{attachment_id}/download")
def download_attachment(
    session_id: str,
    attachment_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> Response:
    """Take one authorised file away with you (BUG-28).

    A generated document was previewable and nothing else: the only way to get a
    report Raiker wrote onto disk was to select the preview text and paste it
    somewhere. This is the byte download, and it is deliberately narrow:

    * **Authorisation is the stored reference**, exactly as for preview — this
      session, this attachment, this owner — so a download can never reach a file
      the same person could not already open. 404 for anything else; a 403 would
      confirm the id exists.
    * **Nothing is served as something the browser will run.** The response is
      always ``application/octet-stream`` with an attachment disposition and
      ``nosniff``. HTML, SVG and script-bearing formats are not upload types
      here, and even so the browser is never invited to interpret a download.
    * **The filename is rebuilt, not echoed.** ``_download_filename`` strips
      anything that could break out of the header or name a path.
    * **The download is evidence.** Every one appends ``attachment_downloaded``
      with metadata only — id, name, type, size — never the bytes.
    """
    store = SQLiteStore(_ws(request))
    served = AttachmentPreviewService(store).download_bytes(
        session_id, attachment_id, auth_data[0].principal_id
    )
    if served is None:
        raise _not_found("attachment_unavailable")
    filename, media_type, data = served
    EventLogWriter(store).append(
        make_event(
            session_id=session_id,
            turn_id=None,
            event_type="attachment_downloaded",
            actor="web_ui",
            payload={
                "attachment_id": attachment_id,
                "filename": filename,
                "media_type": media_type,
                "byte_size": len(data),
            },
        )
    )
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{_download_filename(filename)}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
            "Content-Length": str(len(data)),
        },
    )


# ── Turn sources (C6/C4: what the answer was drawn from) ────────────────────
#
# The same 404-for-everything-you-may-not-see rule as the preview routes above,
# and the same authorization shape: a source row is keyed by the owner
# principal, so another account's conversation resolves to an empty list rather
# than to a refusal that would confirm the conversation exists.


@router.get("/api/sessions/{session_id}/sources")
def list_session_sources(
    session_id: str,
    request: Request,
    turn_id: str = "",
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """What this conversation's turns actually read (C6).

    Labels and locators, never passages: a transcript redraws its provenance
    chips from this, and the material behind a chip is fetched only when the
    owner opens one.
    """
    from raiker.runtime.turn_sources import load_sources

    store = SQLiteStore(_ws(request))
    sources = load_sources(
        store, session_id, auth_data[0].principal_id, turn_id or None
    )
    return {
        "session_id": session_id,
        "sources": [source.to_view() for source in sources],
    }


@router.get("/api/sessions/{session_id}/turns/{turn_id}/sources/{source_id}/excerpt")
def get_turn_source_excerpt(
    session_id: str,
    turn_id: str,
    source_id: str,
    request: Request,
    quote: str = "",
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Open one cited source at the passage the turn used (C4).

    Resolution is re-run now rather than served from what was true at capture
    time: a file that has since changed answers ``source_changed``, an
    attachment this account may no longer read answers ``not_authorized``, and
    neither is dressed up as the passage it used to be.

    ``quote`` is the answer sentence the citation marker terminated, when the
    caller opened this from an inline marker rather than from the strip. It
    locates the run inside a source the turn read whole, and it is used for
    exactly one thing — finding an offset — so a caller cannot use it to read
    anything the source does not already contain.
    """
    from raiker.runtime.turn_sources import load_source, resolve_source_excerpt

    store = SQLiteStore(_ws(request))
    owner_id = auth_data[0].principal_id
    source = load_source(store, session_id, turn_id, source_id, owner_id)
    if source is None:
        raise _not_found("turn_source_not_found")
    excerpt = resolve_source_excerpt(
        store,
        workspace_root=_ws(request),
        source=source,
        session_id=session_id,
        owner_principal_id=owner_id,
        quote=quote,
    )
    return {"ok": True, **source.to_view(), **excerpt}


def _download_filename(filename: str) -> str:
    """A safe, path-free name for a downloaded file.

    Built from the stored name rather than trusted from it: separators are
    dropped so nothing can suggest a directory, and the header-breaking
    characters ``_inline_filename`` already removes stay removed.
    """
    flattened = filename.replace("/", "_").replace("\\", "_")
    cleaned = _inline_filename(flattened).lstrip(".")
    return cleaned or "download"


def _inline_bytes(data: bytes, media_type: str, filename: str) -> Response:
    """One authorized file, served for display and nothing else.

    Read-only: an explicit content type with ``nosniff`` so the bytes can never
    be interpreted as something else, an inline disposition so the browser
    displays rather than downloads, and ``no-store`` so a session-scoped file
    does not linger in a shared cache.
    """
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="{_inline_filename(filename)}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )
