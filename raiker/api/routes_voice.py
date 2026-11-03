"""Voice (voice spec V1): choose a profile, install it, test it, use it.

Every route is for the owner on this computer only, like dictation: audio and
the engines that hear and speak never leave it.

* ``GET  /api/voice/status``   — what is chosen, installed and running; contacts nothing.
* ``PUT  /api/voice/settings`` — change the profile or any option.
* ``POST /api/voice/install``  — download and verify the chosen profile, as a model operation.
* ``DELETE /api/voice``        — stop the engines and remove every voice file.
* ``POST /api/voice/speak``    — one sentence in, WAV audio out (read-aloud, conversation).
* ``POST /api/voice/test``     — speak a phrase, transcribe it back, report the accuracy.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, cast

import httpx
from fastapi import APIRouter, BackgroundTasks, Request, Response, status

from raiker.api.auth import AuthMiddleware
from raiker.api.dependencies import workspace_root as _ws
from raiker.api.proxy_guard import is_local_request
from raiker.api.refusals import refusal
from raiker.api.schemas import (
    VoiceInstallRequest,
    VoiceSettingsRequest,
    VoiceSpeakRequest,
    serialize_dto,
)
from raiker.api.sessions import ApiSession
from raiker.api.wire.voice import VoiceRemoved, VoiceStatus, VoiceTestResult
from raiker.models.local_operations import (
    ModelOperationRequest,
    ModelOperationService,
    OperationWorker,
    run_operation,
)
from raiker.models.wire import ModelOperationView
from raiker.storage.sqlite import SQLiteStore
from raiker.voice import installer
from raiker.voice.catalogue import load as load_catalogue
from raiker.voice.engines import VoiceEngineError
from raiker.voice.service import VoiceService

router = APIRouter()

TEST_PHRASE = "Raiker can hear and answer you on this computer."


def _owner(request: Request) -> tuple[ApiSession, str]:
    session, principal = AuthMiddleware(_ws(request)).authenticate(request)
    if session.origin != "local" or not is_local_request(request.scope):
        raise refusal(status.HTTP_403_FORBIDDEN, "voice_local_only")
    return session, principal.principal_id


def _service(request: Request, principal_id: str) -> VoiceService:
    return VoiceService(_ws(request), principal_id)


@router.get("/api/voice/status")
def voice_status(request: Request) -> dict[str, Any]:
    """What is chosen, what is installed, where it would run. Starts nothing."""
    _session, owner = _owner(request)
    answer = cast(VoiceStatus, _service(request, owner).status())
    return serialize_dto(answer)


@router.put("/api/voice/settings")
def write_voice_settings(body: VoiceSettingsRequest, request: Request) -> dict[str, Any]:
    _session, owner = _owner(request)
    service = _service(request, owner)
    changes = body.model_dump(exclude_unset=True)
    if "whisper_model" in changes and changes["whisper_model"]:
        try:
            item = load_catalogue().get(str(changes["whisper_model"]))
        except ValueError as exc:
            raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "voice_item_unknown") from exc
        if item.component != "whisper_model":
            raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "voice_item_unknown")
    service.save(changes)
    answer = cast(VoiceStatus, service.status())
    return serialize_dto(answer)


def run_voice_install(workspace: Path, owner: str, operation_id: str, profile: str) -> None:
    """The install worker: every installable component of ``profile``, verified."""

    def work(op: OperationWorker) -> None:
        service = VoiceService(workspace, owner)
        items = service.installable_items(profile)
        if not items:
            raise VoiceEngineError("voice_profile_nothing_installable")
        total = sum(item.size_bytes or 0 for item in items)
        done = 0

        def advanced(amount: int) -> None:
            nonlocal done
            done += amount
            op.progress(completed_bytes=done, total_bytes=total, phase="downloading_voice")

        with httpx.Client(timeout=httpx.Timeout(30.0, read=120.0)) as client:
            for item in items:
                op.check_cancelled()
                if installer.is_installed(workspace, item):
                    advanced(item.size_bytes or 0)
                    continue
                installer.install_item(workspace, item, client=client, progress=advanced,
                                       cancelled=op.check_cancelled)

    run_operation(
        ModelOperationService(SQLiteStore(workspace)),
        owner,
        operation_id,
        phase="installing_voice",
        failure_code="voice_install_failed",
        work=work,
    )


def start_voice_install(workspace: Path, owner: str, profile: str) -> ModelOperationView:
    return (
        ModelOperationService(SQLiteStore(workspace))
        .start(
            owner,
            ModelOperationRequest(kind="install", target=f"voice:{profile}", confirmed=True,
                                  source_url="https://github.com/ggml-org/whisper.cpp"),
            payload={"profile_id": profile, "framework": "voice"},
        )
        .to_dict()
    )


@router.post("/api/voice/install")
def install_voice(body: VoiceInstallRequest, background: BackgroundTasks, request: Request) -> dict[str, Any]:
    """Download and verify the chosen profile's components in the background."""
    _session, owner = _owner(request)
    service = _service(request, owner)
    profile = body.profile or service.settings().profile
    if profile == "off":
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "voice_off")
    if not service.installable_items(profile):
        raise refusal(status.HTTP_409_CONFLICT, "voice_profile_nothing_installable")
    if body.profile and body.profile != service.settings().profile:
        service.save({"profile": body.profile})
    workspace = Path(_ws(request))
    answer: ModelOperationView = start_voice_install(workspace, owner, profile)
    background.add_task(run_voice_install, workspace, owner, answer["operation_id"], profile)
    return serialize_dto(answer)


@router.delete("/api/voice")
def remove_voice(request: Request) -> dict[str, Any]:
    """Stop every voice engine and remove every voice file, freeing the disk."""
    _session, owner = _owner(request)
    answer: VoiceRemoved = {"freed_bytes": _service(request, owner).remove()}
    return serialize_dto(answer)


@router.post("/api/voice/speak")
def speak(body: VoiceSpeakRequest, request: Request) -> Response:
    """One sentence as WAV audio from the installed speaking engine."""
    _session, owner = _owner(request)
    try:
        audio = _service(request, owner).speak(body.text)
    except VoiceEngineError as exc:
        raise refusal(status.HTTP_409_CONFLICT, str(exc)) from exc
    return Response(content=audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})


def word_error_rate(expected: str, heard: str) -> float:
    """Levenshtein distance over words, divided by the expected word count."""
    def words(text: str) -> list[str]:
        return re.findall(r"[a-z0-9']+", text.lower())

    a, b = words(expected), words(heard)
    if not a:
        return 0.0 if not b else 1.0
    previous = list(range(len(b) + 1))
    for i, word in enumerate(a, start=1):
        current = [i] + [0] * len(b)
        for j, other in enumerate(b, start=1):
            current[j] = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (word != other))
        previous = current
    return round(previous[-1] / len(a), 3)


@router.post("/api/voice/test")
def test_voice(request: Request) -> dict[str, Any]:
    """Spec §6.2 — play a phrase, transcribe it back, and show the accuracy."""
    from raiker.models.speech_runtime import SpeechRuntimeError, SpeechRuntimeSettings, transcribe

    _session, owner = _owner(request)
    service = _service(request, owner)
    started = time.monotonic()
    answer: VoiceTestResult = {"spoke": False, "heard": False, "transcript": None,
                               "word_error_rate": None, "seconds": 0.0, "reason_code": None}
    try:
        audio = service.speak(TEST_PHRASE)
        answer["spoke"] = True
    except VoiceEngineError as exc:
        answer["reason_code"] = str(exc)
        audio = b""
    if audio and service.listening_ready():
        try:
            endpoint = service.listening_endpoint()
            text = transcribe(SpeechRuntimeSettings(endpoint=endpoint), audio, filename="test.wav",
                              content_type="audio/wav", timeout=60.0)
            answer["heard"] = True
            answer["transcript"] = text
            answer["word_error_rate"] = word_error_rate(TEST_PHRASE, text)
        except (VoiceEngineError, SpeechRuntimeError) as exc:
            answer["reason_code"] = getattr(exc, "reason", None) or str(exc)
    elif audio and answer["reason_code"] is None:
        answer["reason_code"] = "voice_listening_not_installed"
    answer["seconds"] = round(time.monotonic() - started, 2)
    return serialize_dto(answer)
