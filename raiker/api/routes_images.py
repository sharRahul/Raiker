"""The Design surface's API: generate an image, list what was generated, fetch one.

Three routes and one rule between them — **the bytes are owner-scoped and are
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

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import GenerateImageRequest
from raiker.api.sessions import ApiSession
from raiker.runtime.authority.models import Principal
from raiker.runtime.executors.tier2_image import SUPPORTED_SIZES
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()


def _ws(request: Request) -> str | Path:
    return request.app.state.workspace_root  # type: ignore[no-any-return]


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    return AuthMiddleware(_ws(request)).authenticate(request)


def _service(request: Request) -> Any:
    from raiker.control.service import RuntimeControlService

    return RuntimeControlService(_ws(request))


def _public(row: dict[str, Any]) -> dict[str, Any]:
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
    }


@router.get("/api/images")
async def list_images(request: Request) -> dict[str, Any]:
    _, principal = _auth(request)
    store = SQLiteStore(_ws(request))
    rows = store.list_image_generations(owner_principal_id=principal.principal_id)
    return {
        "sizes": list(SUPPORTED_SIZES),
        "generations": [_public(row) for row in rows],
    }


@router.post("/api/images")
async def generate_image(body: GenerateImageRequest, request: Request) -> dict[str, Any]:
    _, principal = _auth(request)
    result = _service(request).generate_image(
        principal.principal_id,
        profile_id=body.profile_id.strip(),
        prompt=body.prompt.strip(),
        size=body.size.strip(),
        model=body.model.strip(),
    )
    if not result.ok:
        # The refusal is already recorded against the owner by the executor, so
        # the page can show it in the gallery as well as in the response.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **(result.data or {})}


@router.get("/api/images/{generation_id}/bytes")
async def get_image_bytes(generation_id: str, request: Request) -> Response:
    """The image itself, to the principal who generated it and nobody else."""
    _, principal = _auth(request)
    store = SQLiteStore(_ws(request))
    row = store.get_image_generation(
        generation_id, owner_principal_id=principal.principal_id
    )
    if row is None or not row.get("attachment_id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"ok": False, "reason_code": "unknown_generation"},
        )
    attachment = store.load_attachment(
        str(row["attachment_id"]), owner_principal_id=principal.principal_id
    )
    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"ok": False, "reason_code": "image_bytes_missing"},
        )
    return Response(
        content=bytes(attachment["data"]),
        media_type=str(row.get("media_type") or "image/png"),
        headers={
            # A generated image is private workspace content: it must not be
            # cached by anything between this process and the tab that asked.
            "Cache-Control": "no-store",
            "Content-Disposition": f'inline; filename="{generation_id}.png"',
        },
    )
