"""Installed-skill API: the Skills tab's read and mutation surface.

A skill is instruction text the owner installs. Adding one grants no capability,
opens no gate, and runs nothing — so these routes are ordinary owner-scoped CRUD
over a validated document store, not a governed execution path.

Two boundaries are worth naming:

* **Upload** is validated before storage (extension allowlist, size caps,
  frontmatter contract, archive-member safety) exactly like an attachment.
* **Verify / import from a URL** is the only route that reaches the network. It
  reads a single document through the sandbox egress boundary against this
  module's own host list, so it fails closed on any other host, and the bytes
  are validated as a skill before anything is written.
"""

from __future__ import annotations

import base64
import binascii
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import (
    BuildSkillRequest,
    RenameSkillRequest,
    SetSkillActiveRequest,
    SetSkillCommandRequest,
    SkillUrlRequest,
    UploadSkillRequest,
    serialize_dto,
)
from raiker.api.sessions import ApiSession
from raiker.runtime.authority.models import Principal
from raiker.skills.package import MAX_BUNDLE_BYTES
from raiker.skills.service import SkillsService

router = APIRouter()

# Base64 inflates by 4/3, so anything longer than this cannot decode to a legal
# bundle. Rejecting before the decode keeps an oversized body cheap to refuse.
_MAX_BASE64_CHARS = (MAX_BUNDLE_BYTES * 4) // 3 + 8

# Reasons that mean "the document is not a valid skill" rather than "you may
# not do this". They are the caller's input problem, so they answer 422.
_INVALID_REASONS = frozenset(
    {
        "skill_invalid_name",
        "skill_missing_description",
        "skill_missing_skill_md",
        "skill_not_an_archive",
        "skill_empty",
        "skill_too_large",
        "skill_too_many_files",
        "skill_unsafe_member_path",
        "skill_unsupported_file_type",
        "skill_unsupported_source",
        "skill_archive_url_unsupported",
        "skill_rename_failed",
        "skill_invalid_command",
        "skill_command_in_use",
    }
)


def _ws(request: Request) -> str | Path:
    return request.app.state.workspace_root  # type: ignore[no-any-return]


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    return AuthMiddleware(_ws(request)).authenticate(request)


def _service(request: Request) -> SkillsService:
    return SkillsService(_ws(request))


def _result(result: Any) -> dict[str, Any]:
    """Map a ControlResult onto an HTTP response: 422 when the document is not a
    valid skill, 404 when the row is not the caller's, 403 otherwise."""
    if result.ok:
        return {"ok": True, **result.data}
    reason = str(result.reason_code or "")
    if reason == "unknown_skill":
        code = status.HTTP_404_NOT_FOUND
    elif reason in _INVALID_REASONS or reason.startswith("skill_fetch_failed"):
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
    else:
        code = status.HTTP_403_FORBIDDEN
    raise HTTPException(status_code=code, detail={"ok": False, "reason_code": reason})


@router.get("/api/skills")
async def list_skills(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Every skill this owner has installed, newest first.

    The response carries metadata and the owner's active choice — never the
    stored archive, which is only read on an explicit download.
    """
    return {"skills": serialize_dto(_service(request).list_skills(auth_data[0].principal_id))}


@router.post("/api/skills")
async def upload_skill(
    body: UploadSkillRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    if len(body.data_base64) > _MAX_BASE64_CHARS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"ok": False, "reason_code": "skill_too_large"},
        )
    try:
        data = base64.b64decode(body.data_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "reason_code": "invalid_base64"},
        ) from exc
    return _result(
        _service(request).install_upload(auth_data[0].principal_id, body.filename, data)
    )


@router.post("/api/skills/verify")
async def verify_skill_url(
    body: SkillUrlRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Read a linked skill and report what it is, storing nothing.

    This is what Chat and Build call when a skill link is pasted, so the owner
    installs against the document's own name and description rather than a URL.
    """
    return _result(_service(request).verify_url(auth_data[0].principal_id, body.url))


@router.post("/api/skills/import")
async def import_skill_url(
    body: SkillUrlRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    return _result(_service(request).import_from_url(auth_data[0].principal_id, body.url))


@router.post("/api/skills/build")
async def build_skill(
    body: BuildSkillRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Install a skill Raiker authored. Held to the same contract as an upload."""
    return _result(
        _service(request).build_skill(
            auth_data[0].principal_id,
            body.name,
            body.description,
            body.body,
            body.command_trigger,
        )
    )


@router.get("/api/skills/{skill_id}/download")
async def download_skill(
    skill_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> Response:
    """Hand back the skill as a ``*.skill`` archive.

    An uploaded archive is returned byte-for-byte; a skill that arrived as a
    bare document is packed on demand into the same layout.
    """
    found = _service(request).get_download(auth_data[0].principal_id, skill_id)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"ok": False, "reason_code": "unknown_skill"},
        )
    filename, payload = found
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put("/api/skills/{skill_id}")
async def rename_skill(
    skill_id: str,
    body: RenameSkillRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    return _result(_service(request).rename(auth_data[0].principal_id, skill_id, body.name))


@router.put("/api/skills/{skill_id}/active")
async def set_skill_active(
    skill_id: str,
    body: SetSkillActiveRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Turn one skill on or off. A deactivated skill stays stored and is
    withheld from every turn until the owner turns it back on."""
    return _result(
        _service(request).set_active(auth_data[0].principal_id, skill_id, body.active)
    )


@router.put("/api/skills/{skill_id}/command")
async def set_skill_command(
    skill_id: str,
    body: SetSkillCommandRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    return _result(
        _service(request).set_command(
            auth_data[0].principal_id, skill_id, body.command_trigger
        )
    )


@router.delete("/api/skills/{skill_id}")
async def delete_skill(
    skill_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    return _result(_service(request).delete(auth_data[0].principal_id, skill_id))
