from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from raiker.api.dependencies import authenticate as _auth
from raiker.api.schemas import StrictRequest, serialize_dto
from raiker.api.sessions import ApiSession
from raiker.api.wire.models import LanguageCheck, LanguageMatch
from raiker.runtime.authority.models import Principal

router = APIRouter()


class LanguageCheckRequest(StrictRequest):
    text: str = Field(max_length=20_000)
    language: str = Field(default="en-US", pattern=r"^en(?:-[A-Z]{2})?$")


@lru_cache(maxsize=3)
def _tool(language: str) -> Any:
    import language_tool_python  # type: ignore[import-not-found]

    return language_tool_python.LanguageTool(language)


def _check(text: str, language: str) -> list[LanguageMatch]:
    return [
        {
            "offset": int(match.offset),
            "length": int(match.error_length),
            "message": str(match.message),
            "replacements": [str(item) for item in match.replacements[:8]],
            "rule_id": str(match.rule_id),
            "category": str(match.category),
        }
        for match in _tool(language).check(text)
    ]


@router.post("/api/language/check")
async def check_language(
    body: LanguageCheckRequest,
    _request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Check English locally; prompt text is neither persisted nor logged."""
    answer: LanguageCheck
    if not body.text.strip():
        answer = {"status": "available", "matches": []}
        return serialize_dto(answer)
    try:
        matches = await asyncio.wait_for(
            asyncio.to_thread(_check, body.text, body.language), timeout=12.0
        )
    except (ImportError, ModuleNotFoundError):
        answer = {"status": "unavailable", "reason_code": "language_tool_not_installed", "matches": []}
        return serialize_dto(answer)
    except TimeoutError:
        answer = {"status": "unavailable", "reason_code": "language_tool_timeout", "matches": []}
        return serialize_dto(answer)
    except Exception:
        answer = {"status": "unavailable", "reason_code": "language_tool_unavailable", "matches": []}
        return serialize_dto(answer)
    answer = {"status": "available", "matches": matches}
    return serialize_dto(answer)
