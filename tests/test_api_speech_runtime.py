"""BUG-256 — dictation that can run entirely on the owner's own machine.

The tests below stand a real transcription server on loopback rather than
patching the client, because the thing worth proving is that the request Raiker
sends is one an ordinary ``whisper-server`` can parse: a multipart form, on a
route that server actually serves, with the audio in it.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.models.speech_runtime import (
    SpeechRuntimeError,
    normalise_endpoint,
    parse_settings,
    silent_probe_clip,
)


@pytest.fixture()
def client(tmp_path):  # type: ignore[no-untyped-def]
    return TestClient(create_app(tmp_path))


def _owner(client: TestClient) -> dict[str, str]:
    body = client.post(
        "/api/auth/register", json={"username": "rahul", "password": "right-pass-123"}
    )
    assert body.status_code == 200, body.text
    return {"Authorization": f"Bearer {body.json()['token']}"}


class _Whisper(BaseHTTPRequestHandler):
    """A stand-in for the owner's runtime, on whichever route it serves."""

    route = "/v1/audio/transcriptions"
    transcript = "the words that were said"
    received: list[bytes] = []

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's spelling
        length = int(self.headers.get("content-length", "0"))
        _Whisper.received.append(self.rfile.read(length))
        if self.path != type(self).route:
            self.send_response(404)
            self.end_headers()
            return
        payload = json.dumps({"text": type(self).transcript}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args: object) -> None:
        return


@pytest.fixture()
def whisper() -> Iterator[str]:
    _Whisper.received = []
    server = HTTPServer(("127.0.0.1", 0), _Whisper)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


# ── The choice, and what reading it costs ────────────────────────────────────


def test_reading_the_choice_contacts_nothing(client: TestClient) -> None:
    """"Nothing is contacted until you ask" holds for speech as for models."""
    headers = _owner(client)
    body = client.get("/api/speech/runtime", headers=headers).json()
    assert body["runtime"] == {
        "endpoint": "",
        "model": "",
        "configured": False,
        "effective": "browser",
    }


def test_setting_a_runtime_up_is_the_whole_decision(client: TestClient) -> None:
    """There is no mode. An install with a runtime uses it; one without does not.

    A switch would have asked the owner to answer a question they had already
    answered by installing the thing, and left a second place for the two
    surfaces to disagree.
    """
    headers = _owner(client)
    saved = client.put(
        "/api/speech/runtime", headers=headers, json={"endpoint": "http://127.0.0.1:8910"}
    ).json()
    assert saved["runtime"]["effective"] == "local"
    cleared = client.put("/api/speech/runtime", headers=headers, json={"endpoint": ""}).json()
    assert cleared["runtime"]["effective"] == "browser"
    assert "mode" not in cleared["runtime"]


def test_an_address_off_this_machine_is_refused(client: TestClient) -> None:
    """A hosted transcription server is exactly what the setting exists to avoid."""
    headers = _owner(client)
    for endpoint in ("https://api.example.com", "http://192.168.1.40:9000"):
        refused = client.put("/api/speech/runtime", headers=headers, json={"endpoint": endpoint})
        assert refused.status_code == 422, endpoint
        assert refused.json()["detail"]["reason_code"] == "speech_endpoint_not_local"


def test_the_address_can_be_set_without_restating_the_model(client: TestClient) -> None:
    """Most transcription servers serve one model; naming it is optional."""
    headers = _owner(client)
    client.put(
        "/api/speech/runtime",
        headers=headers,
        json={"endpoint": "http://127.0.0.1:8910", "model": "base.en"},
    )
    client.put("/api/speech/runtime", headers=headers, json={"endpoint": "http://127.0.0.1:8911"})
    body = client.get("/api/speech/runtime", headers=headers).json()["runtime"]
    assert body["endpoint"] == "http://127.0.0.1:8911"
    assert body["model"] == "base.en"


def test_a_malformed_voice_section_leaves_dictation_on_the_browser() -> None:
    sections: tuple[object, ...] = (None, [], "browser", {"transcription_endpoint": 7})
    for section in sections:
        assert parse_settings(section).effective == "browser"
    assert parse_settings({"transcription_endpoint": "http://127.0.0.1:8910"}).effective == "local"


def test_an_empty_endpoint_is_a_valid_state_not_a_refusal() -> None:
    assert normalise_endpoint("   ") == ""
    assert normalise_endpoint("http://127.0.0.1:8910/") == "http://127.0.0.1:8910"
    with pytest.raises(SpeechRuntimeError):
        normalise_endpoint("http://speech.example.com")


# ── The transcript ───────────────────────────────────────────────────────────


def test_a_clip_is_transcribed_by_the_owners_own_runtime(
    client: TestClient, whisper: str
) -> None:
    headers = _owner(client)
    client.put("/api/speech/runtime", headers=headers, json={"endpoint": whisper})
    answered = client.post(
        "/api/speech/transcribe",
        headers={**headers, "content-type": "audio/wav"},
        content=silent_probe_clip(),
    )
    assert answered.status_code == 200, answered.text
    assert answered.json() == {"text": "the words that were said"}
    # The audio reached the runtime as a form field it can read.
    assert b'name="file"' in _Whisper.received[-1]


def test_the_native_whisper_route_is_tried_when_the_openai_one_is_not_served(
    client: TestClient, whisper: str
) -> None:
    """An owner should not have to know which build they installed."""
    _Whisper.route = "/inference"
    try:
        headers = _owner(client)
        client.put("/api/speech/runtime", headers=headers, json={"endpoint": whisper})
        answered = client.post(
            "/api/speech/transcribe",
            headers={**headers, "content-type": "audio/wav"},
            content=silent_probe_clip(),
        )
        assert answered.status_code == 200, answered.text
        assert answered.json()["text"] == "the words that were said"
    finally:
        _Whisper.route = "/v1/audio/transcriptions"


def test_transcribing_without_a_runtime_says_so(client: TestClient) -> None:
    headers = _owner(client)
    refused = client.post(
        "/api/speech/transcribe",
        headers={**headers, "content-type": "audio/wav"},
        content=silent_probe_clip(),
    )
    assert refused.status_code == 422
    assert refused.json()["detail"]["reason_code"] == "speech_runtime_not_configured"


def test_an_unreachable_runtime_is_reported_as_one(client: TestClient) -> None:
    headers = _owner(client)
    client.put("/api/speech/runtime", headers=headers, json={"endpoint": "http://127.0.0.1:9"})
    refused = client.post(
        "/api/speech/transcribe",
        headers={**headers, "content-type": "audio/wav"},
        content=silent_probe_clip(),
    )
    assert refused.status_code == 502
    assert refused.json()["detail"]["reason_code"] == "speech_runtime_unreachable"


def test_an_empty_recording_is_refused_before_anything_is_contacted(
    client: TestClient, whisper: str
) -> None:
    headers = _owner(client)
    client.put("/api/speech/runtime", headers=headers, json={"endpoint": whisper})
    refused = client.post(
        "/api/speech/transcribe", headers={**headers, "content-type": "audio/wav"}, content=b""
    )
    assert refused.status_code == 422
    assert refused.json()["detail"]["reason_code"] == "speech_audio_missing"
    assert _Whisper.received == []


def test_the_probe_proves_the_runtime_by_transcribing_silence(
    client: TestClient, whisper: str
) -> None:
    headers = _owner(client)
    answered = client.post(
        "/api/speech/runtime/probe", headers=headers, json={"endpoint": whisper}
    )
    assert answered.status_code == 200, answered.text
    assert answered.json() == {"ok": True, "reason_code": None, "endpoint": whisper}
    assert _Whisper.received, "the probe must actually contact the runtime"


def test_the_probe_reports_a_failure_rather_than_raising(client: TestClient) -> None:
    headers = _owner(client)
    answered = client.post(
        "/api/speech/runtime/probe", headers=headers, json={"endpoint": "http://127.0.0.1:9"}
    )
    assert answered.status_code == 200, answered.text
    assert answered.json()["ok"] is False
    assert answered.json()["reason_code"] == "speech_runtime_unreachable"


def test_the_probe_refuses_an_endpoint_it_will_never_be_allowed_to_use(
    client: TestClient,
) -> None:
    headers = _owner(client)
    refused = client.post(
        "/api/speech/runtime/probe", headers=headers, json={"endpoint": "https://api.example.com"}
    )
    assert refused.status_code == 422
    assert refused.json()["detail"]["reason_code"] == "speech_endpoint_not_local"


def test_a_transcript_reaches_the_composer_unredacted(
    client: TestClient, whisper: str
) -> None:
    """BUG-268's lesson, applied before it can happen again.

    A transcript is a high-entropy-looking string with no structure the secret
    redactor can distinguish from a token. Dictating a sentence must not put
    `[REDACTED_SECRET]` in the owner's draft.
    """
    _Whisper.transcript = "AKIA5T3XQ2LMNOPQRSTU deploy the staging cluster"
    try:
        headers = _owner(client)
        client.put("/api/speech/runtime", headers=headers, json={"endpoint": whisper})
        answered = client.post(
            "/api/speech/transcribe",
            headers={**headers, "content-type": "audio/wav"},
            content=silent_probe_clip(),
        )
        assert answered.json()["text"] == "AKIA5T3XQ2LMNOPQRSTU deploy the staging cluster"
    finally:
        _Whisper.transcript = "the words that were said"


def test_speech_routes_need_an_owner(client: TestClient) -> None:
    assert client.get("/api/speech/runtime").status_code == 401
    assert client.post("/api/speech/transcribe", content=b"x").status_code == 401


def test_a_settings_save_cannot_revert_the_runtime_address(client: TestClient) -> None:
    """Two surfaces edit `voice`; only one route writes it.

    The Settings page sends the whole settings blob it last read. Without this
    rule an address configured on the Models page afterwards would be silently
    reverted by the next unrelated save.
    """
    headers = _owner(client)
    client.put("/api/speech/runtime", headers=headers, json={"endpoint": "http://127.0.0.1:8910"})
    saved = client.put(
        "/api/settings",
        headers=headers,
        json={
            "settings": {
                "general.speech_language": "en",
                "voice": {"transcription_endpoint": ""},
            }
        },
    )
    assert saved.status_code == 200, saved.text
    runtime = client.get("/api/speech/runtime", headers=headers).json()["runtime"]
    assert runtime["endpoint"] == "http://127.0.0.1:8910"
    # The rest of the blob is saved exactly as sent.
    assert client.get("/api/settings", headers=headers).json()["settings"][
        "general.speech_language"
    ] == "en"
