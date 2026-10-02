"""The user guide, served to the owner inside the product.

Read-only and static: these two routes hand back text that shipped with Raiker.
They authenticate like every other read so the guide lives behind the same door
as the rest of the workspace, and they grant nothing beyond it.

This is BUG-208 slice A. The point is not the routes; it is that once the
product can show the guide, the explanation compiled into 53 components has
somewhere to move to.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from raiker.api.dependencies import authenticate as _auth
from raiker.api.schemas import serialize_dto
from raiker.api.sessions import ApiSession
from raiker.api.wire.settings import GuideIndex, GuideSection
from raiker.guide import list_sections, read_section
from raiker.runtime.authority.models import Principal

router = APIRouter()


@router.get("/api/guide")
def guide_index(
    _request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """The sections this install carries, in reading order.

    An install whose build shipped no guide answers with an empty list and
    ``available: false`` rather than a 404, so the surface can say the guide is
    missing and name why instead of looking broken.
    """
    sections = list_sections()
    answer: GuideIndex = {
        "available": len(sections) > 0,
        "sections": [
            {"slug": section.slug, "title": section.title, "summary": section.summary}
            for section in sections
        ],
        "reason_code": "" if sections else "guide_not_bundled",
    }
    return serialize_dto(answer)


@router.get("/api/guide/{slug}")
def guide_section(
    slug: str,
    _request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """One section's Markdown, rendered by the client."""
    found = read_section(slug)
    if found is None:
        raise HTTPException(status_code=404, detail={"reason_code": "unknown_guide_section"})
    section, markdown = found
    answer: GuideSection = {
        "slug": section.slug,
        "title": section.title,
        "summary": section.summary,
        "markdown": markdown,
    }
    return serialize_dto(answer)
