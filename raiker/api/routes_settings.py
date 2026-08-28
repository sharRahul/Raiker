"""Per-account settings (the 9-section settings taxonomy).

Settings are stored per ``principal_id`` as a single JSON blob, so each local
account has its own settings — fully isolated from other accounts on the device.
The client owns the section structure; the server persists and returns it as-is,
plus derived read-only status the UI needs (vault state, MFA enrollment).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import ComposerApprovalModeRequest, SettingsRequest
from raiker.auth.accounts import AccountService
from raiker.auth.vault_key_file import vault_status
from raiker.context.redaction import redact_text
from raiker.contracts.ids import utc_now
from raiker.contracts.models import ContractValidationError, normalize_approval_mode
from raiker.hooks.contracts import HookInput
from raiker.hooks.factory import dispatcher_for_workspace
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()

SPEECH_LANGUAGES = {"auto", "en", "fr", "de", "hi", "it", "ja", "ko", "pt", "ru", "es", "tr", "uk"}


def _ws(request: Request) -> str | Path:
    return request.app.state.workspace_root  # type: ignore[attr-defined]


def _load(ws: str | Path, principal_id: str) -> dict[str, Any]:
    row = SQLiteStore(ws).get_user_settings(principal_id)
    if row is None:
        return {}
    try:
        parsed = json.loads(row["settings_json"])
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def load_reasoning_retention(ws: str | Path, principal_id: str) -> bool:
    """Whether this owner has asked for the model's working to be kept (BUG-215).

    **Off by default, and that default is the posture rather than an oversight.**
    Reasoning can restate anything the prompt contained and it is the one part of
    a turn an owner may specifically not want on disk, so it is retained only on
    an explicit decision. Off does not mean the surface pretends there was none:
    the turn still records *how much* working it produced, so a re-opened turn
    says the working was not kept rather than showing nothing.
    """
    return SQLiteStore(ws).reasoning_retention_enabled(principal_id)


def load_composer_approval_mode(ws: str | Path, principal_id: str) -> str:
    composer = _load(ws, principal_id).get("composer")
    if not isinstance(composer, dict):
        return "manual"
    approval_mode = composer.get("approval_mode")
    if not isinstance(approval_mode, str):
        return "manual"
    try:
        return normalize_approval_mode(approval_mode)
    except ContractValidationError:
        return "manual"


def _leaf_keys(value: Any, prefix: str = "") -> set[str]:
    if isinstance(value, dict):
        keys: set[str] = set()
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            keys.update(_leaf_keys(child, path))
        return keys
    return {prefix} if prefix else set()


def _changed_keys(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    candidates = _leaf_keys(before) | _leaf_keys(after)

    def value_at(source: dict[str, Any], path: str) -> Any:
        value: Any = source
        for part in path.split("."):
            if not isinstance(value, dict) or part not in value:
                return object()
            value = value[part]
        return value

    return sorted(key for key in candidates if value_at(before, key) != value_at(after, key))


async def _check_config_change(
    ws: str | Path,
    principal_id: str,
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    changed_keys = _changed_keys(before, after)
    if not changed_keys:
        return
    # The owner's kill switch is above every configured hook. A project file
    # must never be able to veto being turned off.
    before_hooks_value = before.get("hooks")
    after_hooks_value = after.get("hooks")
    before_hooks: dict[str, Any] = (
        before_hooks_value if isinstance(before_hooks_value, dict) else {}
    )
    after_hooks: dict[str, Any] = (
        after_hooks_value if isinstance(after_hooks_value, dict) else {}
    )
    if after_hooks.get("disabled") is True and before_hooks.get("disabled") is not True:
        return
    changed = [redact_text(key)[0] for key in changed_keys]
    dispatcher = dispatcher_for_workspace(
        SQLiteStore(ws), acting_principal_id=principal_id
    )
    if not dispatcher.is_active():
        return
    outcome = await asyncio.to_thread(
        dispatcher.dispatch,
        HookInput(
            event_name="ConfigChange",
            tool_name="user_settings",
            context={
                "source": "user_settings",
                "changed_keys": changed,
                "changed_key_count": len(changed),
            },
        ),
        session_id=f"settings_{principal_id}",
        turn_id=None,
        client=None,
    )
    if outcome.decision in {"deny", "ask", "defer"}:
        reason = outcome.reasons[0] if outcome.reasons else "settings_change_refused"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=reason)


@router.get("/api/settings")
async def get_settings(request: Request) -> dict[str, Any]:
    _session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    ws = _ws(request)
    return {
        "settings": _load(ws, principal.principal_id),
        "status": {
            "vault": vault_status(ws),
            "mfa_enrolled": AccountService(ws).mfa_enrolled(principal.principal_id),
            "username": principal.display_name,
        },
    }


@router.put("/api/settings")
async def put_settings(body: SettingsRequest, request: Request) -> dict[str, Any]:
    _session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    ws = _ws(request)
    speech_language = body.settings.get("general.speech_language")
    if speech_language is not None and (
        not isinstance(speech_language, str) or speech_language not in SPEECH_LANGUAGES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid_speech_language",
        )
    await _check_config_change(ws, principal.principal_id, _load(ws, principal.principal_id), body.settings)
    SQLiteStore(ws).put_user_settings(
        principal.principal_id, json.dumps(body.settings), utc_now()
    )
    return {"settings": body.settings}


@router.get("/api/settings/composer-approval-mode")
async def get_composer_approval_mode(request: Request) -> dict[str, str]:
    _session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    return {"approval_mode": load_composer_approval_mode(_ws(request), principal.principal_id)}


@router.put("/api/settings/composer-approval-mode")
async def put_composer_approval_mode(
    body: ComposerApprovalModeRequest, request: Request
) -> dict[str, str]:
    _session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    try:
        approval_mode = normalize_approval_mode(body.approval_mode)
    except ContractValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from None

    ws = _ws(request)
    settings = _load(ws, principal.principal_id)
    composer = settings.get("composer")
    if not isinstance(composer, dict):
        composer = {}
        settings["composer"] = composer
    composer["approval_mode"] = approval_mode
    await _check_config_change(ws, principal.principal_id, _load(ws, principal.principal_id), settings)
    SQLiteStore(ws).put_user_settings(principal.principal_id, json.dumps(settings), utc_now())
    return {"approval_mode": approval_mode}
