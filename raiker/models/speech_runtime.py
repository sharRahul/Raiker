"""The owner's local speech-to-text runtime, governed like any other local runtime.

BUG-256. Every other surface in Raiker can be run entirely on the owner's own
machine — models, embeddings, indexes, storage. Dictation was the exception: the
microphone button drove the browser's own ``SpeechRecognition``, which on Chrome
sends the audio to a speech service off the device. That is the one thing a
local-first product should not do quietly behind a control that looks local.

The answer is not a special case. A transcription server is a local runtime: the
owner points Raiker at one, nothing is contacted until they ask, the endpoint is
subject to the same loopback rule as a local model server, and the audio is
posted to it and never written anywhere. ``whisper.cpp``'s ``whisper-server`` is
the reference, and anything speaking either its native ``/inference`` route or
the OpenAI-compatible ``/v1/audio/transcriptions`` route works unchanged.

Dictation is unavailable until a local runtime is configured. Browser speech
recognition is never used as a fallback.
"""

from __future__ import annotations

import io
import ipaddress
import struct
import wave
from collections.abc import AsyncIterable, Callable
from dataclasses import dataclass
from typing import Any, Final, Literal
from urllib.parse import urlsplit, urlunsplit

import httpx

from raiker.models.endpoint_policy import canonical_origin
from raiker.models.exceptions import ProviderPolicyError
from raiker.models.wire import SpeechRuntimeView

#: The largest clip the host will forward. 16 kHz mono PCM16 is 32 kB a second,
#: so this is a little over six minutes — long past the point where a dictation
#: is one prompt, and far short of anything that could exhaust the host.
MAX_AUDIO_BYTES: Final = 12 * 1024 * 1024

#: Tried in order. The first is what an OpenAI-compatible transcription server
#: answers on; the second is ``whisper-server``'s own. A runtime that speaks
#: either needs no configuration beyond its address.
TRANSCRIBE_PATHS: Final = ("/v1/audio/transcriptions", "/inference")


class SpeechRuntimeError(RuntimeError):
    """A bounded reason code, for a surface that has to say what went wrong."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


async def read_audio(chunks: AsyncIterable[bytes]) -> bytes:
    """Read at most one bounded recording without buffering an unlimited body."""
    audio = bytearray()
    async for chunk in chunks:
        if len(audio) + len(chunk) > MAX_AUDIO_BYTES:
            raise SpeechRuntimeError("speech_audio_too_large")
        audio.extend(chunk)
    return bytes(audio)


@dataclass(frozen=True)
class SpeechRuntimeSettings:
    """The runtime the owner set up, if any. Reading this contacts nothing."""

    endpoint: str = ""
    model: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.endpoint)

    @property
    def effective(self) -> Literal["local", "unavailable"]:
        """Which runtime the microphone will use — a fact, not a preference.

        Resolved here rather than in the browser so the composer and anything
        that describes it cannot disagree about the answer.
        """
        return "local" if self.configured else "unavailable"

    def to_dict(self) -> SpeechRuntimeView:
        return {
            "endpoint": self.endpoint,
            "model": self.model,
            "configured": self.configured,
            "effective": self.effective,
        }


def parse_settings(section: Any) -> SpeechRuntimeSettings:
    """Read the ``voice`` section back, tolerating anything that is not one.

    Settings are an owner-editable JSON blob, so every field here is treated as
    absent unless it is the shape it should be. A malformed section leaves
    dictation unavailable rather than failing the page that reads it.
    """
    if not isinstance(section, dict):
        return SpeechRuntimeSettings()
    endpoint = section.get("transcription_endpoint")
    model = section.get("transcription_model")
    return SpeechRuntimeSettings(
        endpoint=endpoint.strip() if isinstance(endpoint, str) else "",
        model=model.strip() if isinstance(model, str) else "",
    )


def normalise_endpoint(endpoint: str) -> str:
    """The endpoint as it will be stored, or a refusal.

    An empty value is "no runtime", which is a valid state and the default. Any
    other value has to be an address on this machine: the whole point of the
    setting is that the audio does not leave it, so a hosted or private-network
    transcription server is refused here rather than being allowed to look local.
    """
    trimmed = endpoint.strip().rstrip("/")
    if not trimmed:
        return ""
    try:
        canonical_origin(trimmed)
        parsed = urlsplit(trimmed)
        if parsed.query or parsed.fragment:
            raise ValueError("query or fragment")
        host = parsed.hostname or ""
        if host.lower() == "localhost":
            host = "127.0.0.1"
        address = ipaddress.ip_address(host)
        if not address.is_loopback:
            raise ValueError("not loopback")
        host = f"[{address.compressed}]" if address.version == 6 else address.compressed
        port = f":{parsed.port}" if parsed.port is not None else ""
        return urlunsplit((parsed.scheme, host + port, parsed.path.rstrip("/"), "", ""))
    except (ProviderPolicyError, ValueError) as exc:
        raise SpeechRuntimeError("speech_endpoint_not_local") from exc


def silent_probe_clip(milliseconds: int = 200) -> bytes:
    """A short silent 16 kHz mono clip, for asking a runtime whether it answers.

    Probing with a real request is the same standard the model rows are held to:
    a runtime that returns a model list but cannot transcribe has not been
    proved to work. Silence is enough — what is being tested is the route, the
    format and the reachability, not the transcript.
    """
    frames = int(16_000 * milliseconds / 1000)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(16_000)
        clip.writeframes(struct.pack("<h", 0) * frames)
    return buffer.getvalue()


def _transcript_from(payload: Any) -> str:
    """The text out of whichever shape the runtime answered with."""
    if isinstance(payload, str):
        return payload.strip()
    if not isinstance(payload, dict):
        raise SpeechRuntimeError("speech_transcript_unreadable")
    text = payload.get("text")
    if isinstance(text, str):
        return text.strip()
    # `whisper-server` answers some builds with per-segment rows instead.
    segments = payload.get("segments")
    if isinstance(segments, list):
        parts = [
            str(segment.get("text", "")).strip()
            for segment in segments
            if isinstance(segment, dict)
        ]
        joined = " ".join(part for part in parts if part).strip()
        if joined:
            return joined
    raise SpeechRuntimeError("speech_transcript_unreadable")


def transcribe(
    settings: SpeechRuntimeSettings,
    audio: bytes,
    *,
    filename: str = "dictation.wav",
    content_type: str = "audio/wav",
    language: str | None = None,
    client_factory: Callable[[], httpx.Client] | None = None,
    timeout: float = 120.0,
) -> str:
    """Post one clip to the owner's runtime and return what it heard.

    The audio is held in memory for the length of this call and is never written
    to the workspace — there is no path here that could persist it, which is the
    property the disclosure under the microphone claims.
    """
    if not settings.configured:
        raise SpeechRuntimeError("speech_runtime_not_configured")
    if not audio:
        raise SpeechRuntimeError("speech_audio_missing")
    if len(audio) > MAX_AUDIO_BYTES:
        raise SpeechRuntimeError("speech_audio_too_large")
    origin = normalise_endpoint(settings.endpoint)

    data: dict[str, str] = {"response_format": "json"}
    if settings.model:
        data["model"] = settings.model
    if language and language != "auto":
        data["language"] = language

    # `trust_env=False` for the same reason every other local call in Raiker
    # sets it: an ambient `HTTPS_PROXY` must not be able to route a local
    # transcription through something off the machine.
    make_client = client_factory or (
        lambda: httpx.Client(timeout=timeout, trust_env=False)
    )
    last_refusal: str = "speech_runtime_unreachable"
    with make_client() as client:
        for path in TRANSCRIBE_PATHS:
            path_data = dict(data)
            if path == "/inference" and (not language or language == "auto"):
                path_data["language"] = "auto"
            try:
                response = client.post(
                    f"{origin}{path}",
                    files={"file": (filename, audio, content_type)},
                    data=path_data,
                    follow_redirects=False,
                )
            except httpx.HTTPError as exc:
                raise SpeechRuntimeError("speech_runtime_unreachable") from exc
            if response.status_code in {404, 405}:
                # Not this runtime's route. Try the other one before giving up:
                # `whisper-server` and an OpenAI-compatible server disagree about
                # where transcription lives, and the owner should not have to
                # know which one they installed.
                last_refusal = "speech_runtime_refused"
                continue
            if not response.is_success:
                raise SpeechRuntimeError("speech_runtime_refused")
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
            return _transcript_from(payload)
    raise SpeechRuntimeError(last_refusal)
