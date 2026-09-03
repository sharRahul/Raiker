"""Dictation's runtime: what the owner chose, and the transcript it produces.

BUG-256. Reading the choice contacts nothing. Probing contacts only the address
the owner typed. Transcribing forwards one clip to that address and returns the
text — the audio is held in memory for the length of the request and is never
written to the workspace, which is what the disclosure under the microphone says.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import SpeechRuntimeRequest
from raiker.contracts.ids import utc_now
from raiker.models.speech_runtime import (
    MAX_AUDIO_BYTES,
    SPEECH_MODES,
    SpeechRuntimeError,
    SpeechRuntimeSettings,
    normalise_endpoint,
    parse_settings,
    silent_probe_clip,
    transcribe,
)
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()


def _ws(request: Request) -> str | Path:
    return request.app.state.workspace_root  # type: ignore[attr-defined]


def _settings_blob(ws: str | Path, principal_id: str) -> dict[str, Any]:
    row = SQLiteStore(ws).get_user_settings(principal_id)
    if row is None:
        return {}
    try:
        parsed = json.loads(row["settings_json"])
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def load_speech_runtime(ws: str | Path, principal_id: str) -> SpeechRuntimeSettings:
    return parse_settings(_settings_blob(ws, principal_id).get("voice"))


def _refuse(reason: str, code: int = status.HTTP_422_UNPROCESSABLE_CONTENT) -> HTTPException:
    return HTTPException(status_code=code, detail={"ok": False, "reason_code": reason})


#: Some transcription servers decide how to decode from the filename alone, so
#: the extension has to match what was actually recorded rather than always
#: claiming WAV.
_CLIP_EXTENSIONS: dict[str, str] = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mpeg": "mp3",
    "audio/mp4": "mp4",
    "audio/flac": "flac",
}


def _clip_name(content_type: str) -> str:
    base = content_type.split(";", 1)[0].strip().lower()
    return f"dictation.{_CLIP_EXTENSIONS.get(base, 'wav')}"


@router.get("/api/speech/runtime")
async def read_speech_runtime(request: Request) -> dict[str, Any]:
    """What the owner chose. Nothing is contacted to answer this."""
    _session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    settings = load_speech_runtime(_ws(request), principal.principal_id)
    return {"runtime": settings.to_dict(), "max_audio_bytes": MAX_AUDIO_BYTES}


@router.put("/api/speech/runtime")
async def write_speech_runtime(
    body: SpeechRuntimeRequest, request: Request
) -> dict[str, Any]:
    """Record the choice, and refuse an address that is not on this machine."""
    _session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    ws = _ws(request)
    current = load_speech_runtime(ws, principal.principal_id)

    mode = current.mode if body.mode is None else body.mode
    if mode not in SPEECH_MODES:
        raise _refuse("invalid_speech_mode")
    try:
        endpoint = (
            current.endpoint if body.endpoint is None else normalise_endpoint(body.endpoint)
        )
    except SpeechRuntimeError as exc:
        raise _refuse(exc.reason) from exc
    model = current.model if body.model is None else body.model.strip()

    blob = _settings_blob(ws, principal.principal_id)
    blob["voice"] = {
        "input": mode,
        "transcription_endpoint": endpoint,
        "transcription_model": model,
    }
    SQLiteStore(ws).put_user_settings(principal.principal_id, json.dumps(blob), utc_now())
    settings = SpeechRuntimeSettings(mode=mode, endpoint=endpoint, model=model)
    return {"runtime": settings.to_dict(), "max_audio_bytes": MAX_AUDIO_BYTES}


@router.post("/api/speech/runtime/probe")
async def probe_speech_runtime(
    request: Request, body: SpeechRuntimeRequest | None = None
) -> dict[str, Any]:
    """Ask the runtime to transcribe a moment of silence, and report the answer.

    A model listing would prove less: a server can enumerate models and still be
    unable to accept an upload on either route Raiker knows. Sending real audio
    is the same standard the model rows are tested to.
    """
    _session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    stored = load_speech_runtime(_ws(request), principal.principal_id)
    endpoint_input = body.endpoint if body and body.endpoint is not None else stored.endpoint
    try:
        endpoint = normalise_endpoint(endpoint_input)
    except SpeechRuntimeError as exc:
        raise _refuse(exc.reason) from exc
    if not endpoint:
        raise _refuse("speech_runtime_not_configured")
    candidate = SpeechRuntimeSettings(
        mode=stored.mode,
        endpoint=endpoint,
        model=body.model.strip() if body and body.model is not None else stored.model,
    )
    try:
        transcribe(candidate, silent_probe_clip(), timeout=20.0)
    except SpeechRuntimeError as exc:
        return {"ok": False, "reason_code": exc.reason, "endpoint": endpoint}
    return {"ok": True, "reason_code": None, "endpoint": endpoint}


@router.post("/api/speech/transcribe")
async def transcribe_clip(request: Request) -> dict[str, Any]:
    """One clip in, one transcript out. Nothing in between reaches the disk.

    The clip arrives as the raw request body rather than a multipart upload.
    One request carries exactly one recording, so the envelope would add a
    server-side form parser — and a dependency — to describe a single field.
    The runtime on the far side is still sent a proper multipart form, which is
    what it expects; `httpx` builds that without help.
    """
    _session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    settings = load_speech_runtime(_ws(request), principal.principal_id)
    if not settings.configured:
        raise _refuse("speech_runtime_not_configured")
    clip = await request.body()
    if not clip:
        raise _refuse("speech_audio_missing")
    if len(clip) > MAX_AUDIO_BYTES:
        raise _refuse("speech_audio_too_large", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
    language = request.query_params.get("language")
    content_type = request.headers.get("content-type") or "audio/wav"
    try:
        text = transcribe(
            settings,
            clip,
            filename=_clip_name(content_type),
            content_type=content_type,
            language=language,
        )
    except SpeechRuntimeError as exc:
        raise _refuse(exc.reason, status.HTTP_502_BAD_GATEWAY) from exc
    return {"text": text}
