from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from raiker.models.speech_runtime import (
    MAX_AUDIO_BYTES,
    SpeechRuntimeError,
    SpeechRuntimeSettings,
    normalise_endpoint,
    read_audio,
    transcribe,
)


@pytest.mark.parametrize("endpoint", [
    "http://attacker.localhost:8000", "http://0.0.0.0:8000", "http://192.168.1.1:8000",
    "http://user@127.0.0.1:8000", "http://127.0.0.1:8000/?x=1",
])
def test_rejects_non_loopback_or_ambiguous_endpoints(endpoint: str) -> None:
    with pytest.raises(SpeechRuntimeError):
        normalise_endpoint(endpoint)


def test_localhost_is_pinned_to_loopback() -> None:
    assert normalise_endpoint("http://localhost:8000") == "http://127.0.0.1:8000"


def test_unconfigured_runtime_reports_unavailable() -> None:
    assert SpeechRuntimeSettings().effective == "unavailable"


def test_transcription_refuses_redirect_even_if_client_follows_by_default() -> None:
    requests: list[str] = []
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(307, headers={"Location": "http://example.com/receive"})
    def client() -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    with pytest.raises(SpeechRuntimeError):
        transcribe(SpeechRuntimeSettings(endpoint="http://127.0.0.1:8000"), b"audio", client_factory=client)
    assert len(requests) == 1


def test_native_whisper_route_requests_language_detection_by_default() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v1/audio/transcriptions":
            return httpx.Response(404)
        return httpx.Response(200, json={"text": "ok"})

    def client() -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handler))

    assert transcribe(SpeechRuntimeSettings(endpoint="http://127.0.0.1:8000"), b"audio", client_factory=client) == "ok"
    assert b'name="language"\r\n\r\nauto' in requests[-1].content


def test_streaming_upload_is_rejected_before_reading_remaining_chunks() -> None:
    class Request:
        async def stream(self) -> AsyncIterator[bytes]:
            yield b"a" * MAX_AUDIO_BYTES
            yield b"b"
            raise AssertionError("read beyond limit")

    with pytest.raises(SpeechRuntimeError, match="speech_audio_too_large"):
        read_audio(Request().stream()).send(None)


@pytest.mark.parametrize(
    ("client", "headers", "allowed"),
    [
        ("127.0.0.1", [], True),
        ("::1", [], True),
        ("192.0.2.4", [], False),
        ("127.0.0.1", [(b"x-forwarded-for", b"192.0.2.4")], False),
    ],
)
def test_speech_api_uses_local_peer_and_forwarding_policy(
    client: str, headers: list[tuple[bytes, bytes]], allowed: bool
) -> None:
    from raiker.api.routes_speech import _require_local
    from raiker.api.sessions import ApiSession

    request = Request({"type": "http", "client": (client, 50000), "server": ("127.0.0.1", 8765), "headers": headers})
    if allowed:
        _require_local(request, ApiSession(session_id="test", principal_id="test"))
    else:
        with pytest.raises(HTTPException) as refusal:
            _require_local(request, ApiSession(session_id="test", principal_id="test"))
        assert refusal.value.status_code == 403
