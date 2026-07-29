from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from raiker.api.auth import AuthMiddleware
from raiker.api.sessions import ApiSession
from raiker.runtime.authority.models import Principal

router = APIRouter()


class LanguageCheckRequest(BaseModel):
    text: str = Field(max_length=20_000)
    language: str = Field(default="en-US", pattern=r"^en(?:-[A-Z]{2})?$")


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    return AuthMiddleware(request.app.state.workspace_root).authenticate(request)


@lru_cache(maxsize=3)
def _tool(language: str) -> Any:
    import language_tool_python  # type: ignore[import-not-found]

    return language_tool_python.LanguageTool(language)


def _check(text: str, language: str) -> list[dict[str, Any]]:
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
    if not body.text.strip():
        return {"status": "available", "matches": []}
    try:
        matches = await asyncio.wait_for(
            asyncio.to_thread(_check, body.text, body.language), timeout=12.0
        )
    except (ImportError, ModuleNotFoundError):
        return {"status": "unavailable", "reason_code": "language_tool_not_installed", "matches": []}
    except TimeoutError:
        return {"status": "unavailable", "reason_code": "language_tool_timeout", "matches": []}
    except Exception:
        return {"status": "unavailable", "reason_code": "language_tool_unavailable", "matches": []}
    return {"status": "available", "matches": matches}
