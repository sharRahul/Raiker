"""The Design surface's API: generate an image, list what was generated, fetch one.

Generate, list and fetch, with one rule between them — **the bytes are owner-scoped and are
never returned by the list**. A gallery says what exists; asking for one image is
a separate request that names it, and both reads are bounded to the principal who
made the generation.

Generation itself does not happen here. It goes through
:meth:`RuntimeControlService.generate_image`, which builds a governed action and
routes it through :class:`~raiker.runtime.authority.router.RuntimeAuthority` so
the capability gate, the decision mode, the approval and the audit event all
apply — the same long way round the telemetry export and the audit export take.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, cast

from fastapi import APIRouter, Request, Response, status

from raiker.api.dependencies import authenticate as _auth
from raiker.api.dependencies import refusal
from raiker.api.dependencies import workspace_root as _ws
from raiker.api.schemas import GenerateImageRequest, RevertImageRequest, serialize_dto
from raiker.api.wire.models import (
    ImageGallery,
    ImageGeneration,
    ImageLifecycleChanged,
    ImageReference,
    ImageReverted,
    ImagesGenerated,
)
from raiker.contracts.ids import new_id
from raiker.runtime.executors.tier2_image import SIZED_PROVIDERS, SUPPORTED_SIZES
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()


def _service(request: Request) -> Any:
    from raiker.control.service import RuntimeControlService

    return RuntimeControlService(_ws(request))


def _public(row: dict[str, Any]) -> ImageGeneration:
    """One generation as the page sees it — metadata only, never the bytes."""
    return {
        "generation_id": row["generation_id"],
        "profile_id": row["profile_id"],
        "provider": row["provider"],
        "model": row["model"],
        "prompt": row["prompt"],
        "size": row["size"],
        "status": row["status"],
        "reason_code": row["reason_code"],
        "has_image": bool(row["attachment_id"]),
        "media_type": row["media_type"],
        "byte_size": row["byte_size"],
        "created_at": row["created_at"],
        # BUG-277 — what this picture was made from, and which of the three
        # requests made it. Together they are the whole lineage: a chain of
        # single parents is a history, and a history is what a version strip
        # draws. `.get` because a row written before the lineage migration has
        # neither, and an image that predates the feature is an origin rather
        # than a broken row.
        "source_generation_id": row.get("source_generation_id"),
        "kind": row.get("kind") or "create",
        "project_id": row.get("project_id"),
        "restored_generation_id": row.get("restored_generation_id"),
        "deleted_at": row.get("deleted_at"),
        "references": _references(row.get("references_json")),
    }


def _references(raw: object) -> list[ImageReference]:
    """UX-DESIGN-03 — what research this picture was sent with, as recorded.

    An unreadable record reads as none rather than failing the gallery: the
    picture is still the owner's, and provenance that cannot be parsed is not
    provenance anyone can show.
    """
    if not isinstance(raw, str) or not raw:
        return []
    try:
        parsed = json.loads(raw)
    except ValueError:
        return []
    if not isinstance(parsed, list):
        return []
    return [
        {
            "name": str(item.get("name", "")),
            "text": str(item.get("text", "")),
            "sources": [str(url) for url in item.get("sources", []) if isinstance(url, str)],
        }
        for item in parsed
        if isinstance(item, dict)
    ]


@router.get("/api/images")
async def list_images(request: Request) -> dict[str, Any]:
    _, principal = _auth(request)
    store = SQLiteStore(_ws(request))
    rows = store.list_image_generations(owner_principal_id=principal.principal_id)
    answer: ImageGallery = {
        "sizes": list(SUPPORTED_SIZES),
        # REM-DESIGN-01 — which providers the size is actually sent to, so the
        # page can stop offering a choice to one that ignores it and stop
        # printing a requested size as though it were the returned picture's.
        "sized_providers": list(SIZED_PROVIDERS),
        "generations": [_public(row) for row in rows],
        "deleted": [
            _public(row)
            for row in store.list_image_generations(
                owner_principal_id=principal.principal_id, deleted=True, limit=60
            )
        ],
    }
    return serialize_dto(answer)


@router.post("/api/images")
async def generate_image(body: GenerateImageRequest, request: Request) -> dict[str, Any]:
    _, principal = _auth(request)
    # GCR-05 — off the loop before the synchronous work starts. Governed
    # execution is sync all the way down and ends in a provider call; run inline
    # here it holds the ASGI event loop for the length of an image generation,
    # and every other request on this host waits behind it. Same reason, and the
    # same hop, as the orchestrator's own tool dispatch.
    result = await asyncio.to_thread(
        lambda: _service(request).generate_image(
            principal.principal_id,
            profile_id=body.profile_id.strip(),
            prompt=body.prompt.strip(),
            size=body.size.strip(),
            model=body.model.strip(),
            source_generation_id=body.source_generation_id.strip(),
            variations=body.variations,
            project_id=body.project_id.strip(),
            references=[
                {"name": item.name, "text": item.text, "sources": list(item.sources)}
                for item in body.references
            ],
        )
    )
    if not result.ok:
        # The refusal is already recorded against the owner by the executor, so
        # the page can show it in the gallery as well as in the response.
        raise refusal(status.HTTP_400_BAD_REQUEST, result.reason_code)
    answer = cast(ImagesGenerated, {"ok": True, **(result.data or {})})
    return serialize_dto(answer)


#: The extension a download is named with, by the media type the provider
#: returned. A JPEG saved as ``.png`` opens in some viewers and not others.
_EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}


def _download_name(row: dict[str, Any]) -> str:
    """``raiker-<words from the prompt>-<id tail>.<ext>`` — a name a person can
    find in a downloads folder, made only of characters every filesystem
    accepts, so nothing the prompt says can shape the header."""
    words = re.findall(r"[a-z0-9]+", str(row.get("prompt") or "").lower())[:6]
    stem = "-".join(words)[:48].strip("-") or "image"
    extension = _EXTENSIONS.get(str(row.get("media_type") or ""), "png")
    return f"raiker-{stem}-{str(row['generation_id'])[-6:]}.{extension}"


@router.post("/api/images/{generation_id}/revert")
async def revert_image(
    generation_id: str, body: RevertImageRequest, request: Request
) -> dict[str, Any]:
    """Go back to an earlier version as a new version (DEC-07 step 4).

    ``generation_id`` is the head the owner is looking at; ``body.to`` is the
    earlier version in its own history whose picture comes back. Nothing is
    rewritten or removed and no provider is contacted. Anything that is not a
    version of this owner's picture in that lineage answers 404.
    """
    _, principal = _auth(request)
    store = SQLiteStore(_ws(request))
    row = store.revert_image_generation(
        head_generation_id=generation_id,
        target_generation_id=body.to.strip(),
        owner_principal_id=principal.principal_id,
        generation_id=new_id("img_"),
    )
    if row is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_version_in_lineage")
    answer: ImageReverted = {"ok": True, "generation": _public(row)}
    return serialize_dto(answer)


@router.delete("/api/images/{generation_id}")
async def delete_image(generation_id: str, request: Request) -> dict[str, Any]:
    """Put a picture in Recently deleted (UX-DESIGN-01). Recoverable: the row
    and its bytes stay until the owner removes it for good."""
    _, principal = _auth(request)
    store = SQLiteStore(_ws(request))
    if not store.set_image_generation_deleted(
        generation_id, owner_principal_id=principal.principal_id, deleted=True
    ):
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_generation")
    answer: ImageLifecycleChanged = {
        "ok": True, "generation_id": generation_id, "state": "deleted",
    }
    return serialize_dto(answer)


@router.post("/api/images/{generation_id}/restore")
async def restore_image(generation_id: str, request: Request) -> dict[str, Any]:
    """Bring a picture back from Recently deleted, lineage intact."""
    _, principal = _auth(request)
    store = SQLiteStore(_ws(request))
    if not store.set_image_generation_deleted(
        generation_id, owner_principal_id=principal.principal_id, deleted=False
    ):
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_deleted_generation")
    answer: ImageLifecycleChanged = {
        "ok": True, "generation_id": generation_id, "state": "restored",
    }
    return serialize_dto(answer)


@router.delete("/api/images/{generation_id}/purge")
async def purge_image(generation_id: str, request: Request) -> dict[str, Any]:
    """Remove a picture from Recently deleted for good, with its bytes.

    Only a picture already put away can be removed: the irreversible step is
    always the second one. An id that is not this owner's, or is not in
    Recently deleted, answers the same 404 as one that was never issued.
    """
    _, principal = _auth(request)
    store = SQLiteStore(_ws(request))
    if not store.purge_image_generation(generation_id, owner_principal_id=principal.principal_id):
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_deleted_generation")
    answer: ImageLifecycleChanged = {
        "ok": True, "generation_id": generation_id, "state": "removed",
    }
    return serialize_dto(answer)


@router.get("/api/images/{generation_id}/bytes")
async def get_image_bytes(
    generation_id: str, request: Request, download: bool = False
) -> Response:
    """The image itself, to the principal who generated it and nobody else.

    ``?download=1`` asks for it as a file (UX-DESIGN-01 export): the same
    owner-scoped bytes, named for what they are, with the extension of the
    media type actually returned rather than always ``.png``.
    """
    _, principal = _auth(request)
    store = SQLiteStore(_ws(request))
    row = store.get_image_generation(
        generation_id, owner_principal_id=principal.principal_id
    )
    if row is None or not row.get("attachment_id"):
        raise refusal(status.HTTP_404_NOT_FOUND, "unknown_generation")
    attachment = store.load_attachment(
        str(row["attachment_id"]), owner_principal_id=principal.principal_id
    )
    if attachment is None:
        raise refusal(status.HTTP_404_NOT_FOUND, "image_bytes_missing")
    return Response(
        content=bytes(attachment["data"]),
        media_type=str(row.get("media_type") or "image/png"),
        headers={
            # A generated image is private workspace content: it must not be
            # cached by anything between this process and the tab that asked.
            "Cache-Control": "no-store",
            "Content-Disposition": (
                f'attachment; filename="{_download_name(row)}"'
                if download
                else f'inline; filename="{_download_name(row)}"'
            ),
        },
    )
