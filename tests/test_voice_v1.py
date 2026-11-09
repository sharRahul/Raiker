# SPDX-License-Identifier: Apache-2.0
"""Voice spec V1: catalogue, profiles, placement, install, engines, routes.

Real downloads and real engines are not used here; the live round trip lives in
``tests/test_voice_live.py`` behind ``RAIKER_VOICE_LIVE``. What is tested here is
every decision Raiker makes around them: what may be downloaded, what is
recommended, where it runs, what is refused and why, and that the routes say
so without starting anything they were not asked to start.
"""

from __future__ import annotations

import hashlib
import io
import json
import threading
import wave
from dataclasses import replace
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx
import pytest

from raiker.models.engines.resources import Reservation, ResourceLedger
from raiker.models.llama_cpp.hardware import GIB, GpuDevice, HardwareProfile
from raiker.voice import installer
from raiker.voice.catalogue import (
    PERMISSIVE_LICENCES,
    CatalogueError,
    CatalogueItem,
    load,
    parse,
    require_installable,
)
from raiker.voice.planner import plan
from raiker.voice.profiles import recommend, resolve
from raiker.voice.service import VoiceService, parse_settings
from raiker.voice.tts_worker import make_handler, pcm16_wav


def _hardware(*, memory_gib: int = 16, gpu_gib: int | None = None, os_name: str = "windows",
              arch: str = "x64", cores: int = 8) -> HardwareProfile:
    gpus: tuple[GpuDevice, ...] = ()
    backends: tuple[str, ...] = ("cpu",)
    recommended = "cpu"
    if gpu_gib is not None:
        gpus = (GpuDevice(vendor="nvidia", name="NVIDIA RTX 4060", memory_total_bytes=gpu_gib * GIB,
                          memory_free_bytes=gpu_gib * GIB, discrete=True, cuda_version="12.4"),)
        backends, recommended = ("cuda", "cpu"), "cuda"
    return HardwareProfile(
        os=os_name, arch=arch, cpu_cores=cores, total_memory_bytes=memory_gib * GIB,
        available_memory_bytes=(memory_gib - 4) * GIB, gpus=gpus, vulkan_available=False,
        metal_available=False, backends=backends, recommended_backend=recommended, reason="test",
    )


# ── the catalogue ─────────────────────────────────────────────────────────────


def test_every_installable_item_has_a_digest_a_size_and_a_permissive_licence() -> None:
    catalogue = load()
    installable = [item for item in catalogue.items if item.installable]
    assert installable, "the catalogue offers nothing installable"
    for item in installable:
        assert item.url and item.url.startswith("https://"), item.item_id
        assert item.sha256 and len(item.sha256) == 64, item.item_id
        assert item.size_bytes and item.size_bytes > 0, item.item_id
        assert item.licence in PERMISSIVE_LICENCES, item.item_id
    # Anything not installable says why, in words an owner can act on.
    for item in catalogue.items:
        if not item.installable and not item.bundled:
            assert item.pending_reason or item.licence not in PERMISSIVE_LICENCES, item.item_id


def test_the_bundled_voice_activity_model_is_the_file_the_catalogue_names() -> None:
    item = load().get("silero-vad-v5")
    path = Path(__file__).resolve().parents[1] / item.raw["bundled_path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == item.sha256
    assert path.stat().st_size == item.size_bytes
    assert item.licence == "MIT"


def test_unverified_or_unreviewed_items_are_refused() -> None:
    catalogue = load()
    with pytest.raises(CatalogueError, match="voice_item_pending"):
        require_installable(replace(catalogue.get("whisper-small-q5_1"), pending_reason="not verified"))
    with pytest.raises(CatalogueError, match="voice_item_pending"):
        require_installable(replace(catalogue.get("kokoro-82m-int8"), pending_reason="licence review"))
    item = catalogue.get("kokoro-82m-int8")
    assert require_installable(item) is item
    assert replace(item, licence="GPL-3.0").refusal() == "voice_item_licence_unreviewed"
    assert replace(item, sha256="abc").refusal() == "voice_item_unverified"


def test_a_profile_naming_an_unknown_item_is_refused() -> None:
    raw = json.loads(Path("raiker/config/voice-catalogue.json").read_text(encoding="utf-8"))
    raw["profiles"]["lite"]["listening"] = ["no-such-item"]
    with pytest.raises(CatalogueError, match="voice_catalogue_profile_unknown_item"):
        parse(raw)


# ── profiles and placement ────────────────────────────────────────────────────


def test_the_recommendation_follows_the_hardware() -> None:
    assert recommend(_hardware(memory_gib=8))[0] == "lite"
    profile, why = recommend(_hardware(memory_gib=16, gpu_gib=8))
    assert profile == "balanced" and "RTX 4060" in why
    assert recommend(_hardware(memory_gib=16))[0] == "balanced"
    assert recommend(_hardware(memory_gib=64))[0] == "high"
    assert recommend(_hardware(memory_gib=16, gpu_gib=16))[0] == "high"


def test_a_profile_resolves_to_this_machines_builds() -> None:
    catalogue = load()
    balanced = resolve(catalogue, "balanced", _hardware(memory_gib=16))
    roles = {component.role: component.item.item_id for component in balanced.components}
    assert roles["whisper_engine"] == "whisper-server-windows-x64-cpu"
    assert roles["whisper_model"] == "whisper-small-q5_1"
    assert roles["kokoro_model"] == "kokoro-82m-int8"
    # With a GPU that has room, Balanced takes large-v3-turbo and the CUDA build.
    gpu = resolve(catalogue, "balanced", _hardware(memory_gib=16, gpu_gib=8))
    gpu_roles = {c.role: c.item.item_id for c in gpu.components}
    assert gpu_roles["whisper_model"] == "whisper-large-v3-turbo-q5_0"
    assert gpu_roles["whisper_engine"] == "whisper-server-windows-x64-cuda"
    # English-only picks the .en variant where the profile offers one.
    lite = resolve(catalogue, "lite", _hardware(memory_gib=8, os_name="linux"), english_only=True)
    assert lite.part("whisper_model").item_id == "whisper-base.en-q5_1"  # type: ignore[union-attr]
    assert lite.speaking == "kokoro" and lite.speaking_installable
    assert lite.part("kokoro_model").item_id == "kokoro-82m-int8"  # type: ignore[union-attr]
    # Windows has a pinned engine and models. Linux still waits on its engine.
    assert balanced.speaking_installable and balanced.listening_installable
    linux = resolve(catalogue, "balanced", _hardware(os_name="linux"))
    assert not linux.listening_installable


def test_whisper_goes_on_the_gpu_only_with_headroom_next_to_the_model() -> None:
    catalogue = load()
    hardware = _hardware(memory_gib=32, gpu_gib=8)
    profile = resolve(catalogue, "balanced", hardware, whisper_model="whisper-small-q5_1")
    empty = plan(profile, hardware, ResourceLedger())
    assert empty.fits and empty.placements[0].device == "cuda"
    busy = ResourceLedger()
    busy.reserve(Reservation(owner="llm:slot", kind="llm", ram_bytes=2 * GIB,
                             gpu_id="NVIDIA RTX 4060", vram_bytes=int(7.8 * GIB)))
    crowded = plan(profile, hardware, busy)
    assert crowded.placements[0].device == "cpu"
    assert "GPU is busy" in crowded.sentence
    assert plan(profile, hardware, ResourceLedger(), run_on="cpu").placements[0].device == "cpu"
    # Threads: half the cores, at most 8.
    assert crowded.placements[0].threads == 4


def test_a_profile_that_does_not_fit_is_refused_with_the_smaller_one_named() -> None:
    catalogue = load()
    hardware = _hardware(memory_gib=8)
    held = ResourceLedger()
    held.reserve(Reservation(owner="llm:slot", kind="llm", ram_bytes=5 * GIB))
    hardware = replace(hardware, available_memory_bytes=3 * GIB)
    verdict = plan(resolve(catalogue, "high", hardware), hardware, held)
    assert not verdict.fits
    assert verdict.smaller_profile == "balanced"
    assert verdict.reason_code == "voice_profile_does_not_fit"


# ── installing ────────────────────────────────────────────────────────────────


def _item(payload: bytes, **extra: Any) -> CatalogueItem:
    return CatalogueItem(
        item_id="kokoro-test", component="kokoro_model", name="test", licence="Apache-2.0",
        source_page="https://github.com/x", url="https://github.com/x/releases/download/v1/model.onnx",
        sha256=hashlib.sha256(payload).hexdigest(), size_bytes=len(payload), **extra,
    )


def _client(payload: bytes, *, status: int = 200, host: str = "github.com") -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=payload, request=httpx.Request("GET", f"https://{host}/f"))

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_a_component_is_kept_only_when_it_matches_its_digest(tmp_path: Path) -> None:
    payload = b"onnx-model-bytes" * 100
    item = _item(payload)
    path = installer.install_item(tmp_path, item, client=_client(payload))
    assert path.read_bytes() == payload and installer.is_installed(tmp_path, item)
    assert installer.installed_bytes(tmp_path) >= len(payload)

    other = replace(item, item_id="kokoro-tampered")
    with pytest.raises(installer.VoiceInstallError, match="voice_digest_mismatch"):
        installer.install_item(tmp_path, other, client=_client(b"x" * len(payload)))
    assert not installer.is_installed(tmp_path, other)
    assert not list((tmp_path / "runtimes" / "voice").glob("kokoro-tampered*"))

    with pytest.raises(installer.VoiceInstallError, match="voice_download_oversize"):
        installer.install_item(tmp_path, replace(item, item_id="big"), client=_client(payload + b"!"))
    with pytest.raises(installer.VoiceInstallError, match="voice_item_pending"):
        installer.install_item(tmp_path, replace(item, pending_reason="later"), client=_client(payload))

    assert installer.remove_all(tmp_path) >= len(payload)
    assert not installer.is_installed(tmp_path, item)


def test_a_download_from_an_unlisted_host_is_refused(tmp_path: Path) -> None:
    payload = b"abc"
    item = replace(_item(payload), url="https://example.com/model.onnx")
    with pytest.raises(installer.VoiceInstallError, match="voice_download_host_refused"):
        installer.install_item(tmp_path, item, client=_client(payload))
    # A redirect to a host that is not on the list is refused, not followed into.
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "github.com":
            return httpx.Response(302, headers={"Location": "https://evil.example/model.onnx"})
        return httpx.Response(200, content=payload)

    redirected = _item(payload)
    with pytest.raises(installer.VoiceInstallError, match="voice_download_host_refused"):
        installer.install_item(tmp_path, redirected, client=httpx.Client(transport=httpx.MockTransport(handler)))


# ── settings ──────────────────────────────────────────────────────────────────


def test_stored_settings_are_read_defensively() -> None:
    assert parse_settings(None).profile == "off"
    settings = parse_settings({"profile": "balanced", "speed": 9, "run_on": "quantum",
                               "whisper_model": "../../etc/passwd",
                               "conversation": {"end_silence_ms": 5, "mode": "hands_free"}})
    assert settings.profile == "balanced" and settings.speed == 2.0 and settings.run_on == "auto"
    assert settings.whisper_model is None
    assert settings.conversation.end_silence_ms == 250 and settings.conversation.mode == "hands_free"
    assert parse_settings({"conversation": "nope"}).conversation.mode == "push_to_talk"


# ── the speaking worker ───────────────────────────────────────────────────────


class _Tone:
    engine = "kokoro"

    def __init__(self) -> None:
        self.spoken: list[str] = []

    def voices(self) -> list[str]:
        return ["af_heart"]

    def synthesise(self, text: str, voice: str | None, speed: float) -> tuple[bytes, int]:
        self.spoken.append(text)
        return b"\x00\x10" * 2400, 24000


@pytest.fixture()
def worker() -> Any:
    synth = _Tone()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(synth, "secret-token"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", synth
    server.shutdown()
    server.server_close()


def test_the_worker_speaks_only_for_the_host_that_started_it(worker: Any) -> None:
    base, synth = worker
    headers = {"X-Raiker-Voice-Token": "secret-token"}
    assert httpx.get(f"{base}/health").status_code == 403
    assert httpx.post(f"{base}/synthesize", json={"text": "hi"}, headers={"X-Raiker-Voice-Token": "x"}).status_code == 403
    assert httpx.get(f"{base}/health", headers=headers).json() == {"ok": True, "engine": "kokoro", "voices": ["af_heart"]}
    answer = httpx.post(f"{base}/synthesize", json={"text": "Hello there.", "voice": "af_heart"}, headers=headers)
    assert answer.status_code == 200 and answer.headers["content-type"] == "audio/wav"
    with wave.open(io.BytesIO(answer.content)) as clip:
        assert clip.getframerate() == 24000 and clip.getnframes() == 2400
    assert synth.spoken == ["Hello there."]
    assert httpx.post(f"{base}/synthesize", json={"text": "x" * 2001}, headers=headers).status_code == 413
    assert httpx.post(f"{base}/synthesize", json={"text": "  "}, headers=headers).status_code == 400


def test_pcm16_wav_round_trips() -> None:
    with wave.open(io.BytesIO(pcm16_wav(b"\x01\x00" * 10, 16000))) as clip:
        assert (clip.getnchannels(), clip.getsampwidth(), clip.getframerate(), clip.getnframes()) == (1, 2, 16000, 10)


# ── the engines and the service ───────────────────────────────────────────────


class _FakeProcess:
    def __init__(self) -> None:
        self.ended = False

    def poll(self) -> int | None:
        return 0 if self.ended else None

    def terminate(self) -> None:
        self.ended = True

    def wait(self, timeout: float | None = None) -> int:
        return 0

    def kill(self) -> None:
        self.ended = True


def test_engines_register_their_memory_and_stop_when_idle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from raiker.voice import engines as engines_module
    from raiker.voice.engines import VoiceEngines

    now = [100.0]
    started: list[list[str]] = []

    def spawner(argv: list[str], **_kw: Any) -> _FakeProcess:
        started.append(argv)
        return _FakeProcess()

    monkeypatch.setattr(engines_module.httpx, "get", lambda *a, **k: httpx.Response(200))
    ledger = ResourceLedger()
    engines = VoiceEngines(tmp_path, ledger=ledger, spawner=spawner, clock=lambda: now[0])
    engine = engines.ensure_whisper(Path("/opt/whisper-server"), Path("/m/ggml-small.bin"), threads=4,
                                    device="cpu", ram=500, vram=0, gpu=None)
    assert started[0][:3] == [str(Path("/opt/whisper-server")), "-m", str(Path("/m/ggml-small.bin"))]
    assert "--no-gpu" in started[0] and started[0][started[0].index("--host") + 1] == "127.0.0.1"
    assert ledger.committed() == (500, {})
    # Reused, not started twice.
    assert engines.ensure_whisper(Path("/opt/whisper-server"), Path("/m/x"), threads=4, device="cpu",
                                  ram=500, vram=0, gpu=None) is engine
    assert len(started) == 1
    now[0] += 30
    assert engines.tick(60) == []
    now[0] += 60
    assert engines.tick(60) == ["whisper"]
    assert ledger.committed() == (0, {})
    assert engines.status()["whisper"] == {"running": False, "device": None, "engine": None, "paused_reason": "idle"}


def test_an_engine_that_exits_at_start_is_reported_by_reason(tmp_path: Path) -> None:
    from raiker.voice.engines import VoiceEngineError, VoiceEngines

    def spawner(argv: list[str], *, log_path: Path, pid_path: Path) -> _FakeProcess:
        log_path.write_text("voice_kokoro_runtime_missing\n", encoding="utf-8")
        process = _FakeProcess()
        process.ended = True
        return process

    engines = VoiceEngines(tmp_path, ledger=ResourceLedger(), spawner=spawner)
    with pytest.raises(VoiceEngineError, match="voice_kokoro_runtime_missing"):
        engines.ensure_speaker("kokoro", model=Path("m.onnx"), voices=Path("v.bin"), threads=2, ram=1)


def _owner_ws(tmp_path: Path) -> tuple[Path, str]:
    from raiker.cli.principal_resolver import bootstrap_owner

    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws, "principal_owner"


def test_status_reports_what_is_offered_and_starts_nothing(tmp_path: Path) -> None:
    from raiker.voice.engines import VoiceEngines

    ws, owner = _owner_ws(tmp_path)
    spawned: list[Any] = []
    engines = VoiceEngines(ws, ledger=ResourceLedger(), spawner=lambda *a, **k: spawned.append(a))
    service = VoiceService(ws, owner, hardware=_hardware(memory_gib=16), engines=engines)
    status = service.status()
    assert status["settings"]["profile"] == "off" and status["recommended_profile"] == "balanced"
    assert status["listening"]["state"] == "off"
    service.save({"profile": "balanced", "voice": "bf_emma"})
    status = service.status()
    assert status["settings"]["voice"] == "bf_emma"
    assert status["speaking"]["state"] == "not_installed" and status["speaking"]["engine"] == "kokoro"
    assert status["listening"]["state"] == "not_installed"
    components = {c["item_id"]: c["refusal"] for c in status["listening"]["components"]}
    assert components["whisper-small-q5_1"] is None
    assert "bf_emma" in status["speaking"]["voices"]
    assert spawned == []


def test_dictation_says_listening_is_not_installed_until_it_is(tmp_path: Path) -> None:
    from raiker.voice.engines import VoiceEngineError, VoiceEngines

    ws, owner = _owner_ws(tmp_path)
    service = VoiceService(ws, owner, hardware=_hardware(), engines=VoiceEngines(ws, ledger=ResourceLedger()))
    service.save({"profile": "balanced"})
    assert service.listening_ready() is False
    with pytest.raises(VoiceEngineError, match="voice_listening_not_installed"):
        service.listening_endpoint()
    with pytest.raises(VoiceEngineError, match="voice_speaking_not_installed"):
        service.speak("hello")


# ── routes ────────────────────────────────────────────────────────────────────


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    from fastapi.testclient import TestClient

    from raiker.api.app import create_app
    from raiker.voice import service as service_module

    ws, _owner = _owner_ws(tmp_path)
    monkeypatch.setattr(service_module, "detect", lambda: _hardware(memory_gib=16))
    test_client = TestClient(create_app(ws))
    token = test_client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    test_client.headers["Authorization"] = f"Bearer {token}"
    return test_client


def test_the_routes_choose_install_and_remove(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from raiker.api import routes_voice

    status = client.get("/api/voice/status")
    assert status.status_code == 200, status.text
    assert status.json()["recommended_profile"] == "balanced"
    changed = client.put("/api/voice/settings", json={"profile": "balanced", "conversation": {"end_silence_ms": 700}})
    assert changed.status_code == 200
    assert changed.json()["settings"]["conversation"]["end_silence_ms"] == 700
    assert client.put("/api/voice/settings", json={"profile": "loud"}).status_code == 422
    assert client.put("/api/voice/settings", json={"whisper_model": "kokoro-82m-int8"}).status_code == 422

    ran: list[tuple[Any, ...]] = []
    monkeypatch.setattr(routes_voice, "run_voice_install", lambda *args: ran.append(args))
    started = client.post("/api/voice/install", json={})
    assert started.status_code == 200, started.text
    assert started.json()["kind"] == "install" and started.json()["target"] == "voice:balanced"
    assert ran and ran[0][3] == "balanced"

    speak = client.post("/api/voice/speak", json={"text": "hello"})
    assert speak.status_code == 409 and speak.json()["detail"]["reason_code"] == "voice_speaking_not_installed"
    test = client.post("/api/voice/test")
    assert test.status_code == 200 and test.json()["spoke"] is False
    assert test.json()["reason_code"] == "voice_speaking_not_installed"
    assert client.delete("/api/voice").json() == {"freed_bytes": 0}


def test_the_install_worker_installs_every_installable_component(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from raiker.api import routes_voice
    from raiker.models.local_operations import ModelOperationService
    from raiker.storage.sqlite import SQLiteStore
    from raiker.voice import service as service_module

    ws, owner = _owner_ws(tmp_path)
    monkeypatch.setattr(service_module, "detect", lambda: _hardware(memory_gib=16))
    VoiceService(ws, owner).save({"profile": "balanced"})
    installed: list[str] = []

    def fake_install(workspace: Path, item: CatalogueItem, **kwargs: Any) -> Path:
        installed.append(item.item_id)
        kwargs["progress"](item.size_bytes or 0)
        return workspace

    monkeypatch.setattr(installer, "install_item", fake_install)
    operation = routes_voice.start_voice_install(ws, owner, "balanced")
    routes_voice.run_voice_install(ws, owner, operation["operation_id"], "balanced")
    row = ModelOperationService(SQLiteStore(ws)).require(owner, operation["operation_id"])
    assert row.state == "complete", (row.error_code, row.error_detail)
    assert installed == ["whisper-server-windows-x64-cpu", "whisper-small-q5_1",
                         "kokoro-82m-int8", "kokoro-voices-v1"]


def test_word_error_rate() -> None:
    from raiker.api.routes_voice import word_error_rate

    assert word_error_rate("Raiker can hear you", "raiker can hear you.") == 0.0
    assert word_error_rate("one two three four", "one too three") == 0.5


def test_dictation_uses_the_managed_whisper_engine_when_none_was_set_up_by_hand(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from http.server import BaseHTTPRequestHandler

    received: list[int] = []

    class FakeWhisper(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:
            return

        def do_POST(self) -> None:  # noqa: N802 - stdlib name
            received.append(int(self.headers.get("Content-Length") or 0))
            self.rfile.read(received[-1])
            if self.path != "/inference":
                self.send_response(404)
                self.end_headers()
                return
            body = json.dumps({"text": " what is on today"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeWhisper)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        monkeypatch.setattr(VoiceService, "listening_ready", lambda self: True)
        monkeypatch.setattr(VoiceService, "listening_endpoint",
                            lambda self: f"http://127.0.0.1:{server.server_address[1]}")
        runtime = client.get("/api/speech/runtime").json()["runtime"]
        assert runtime["configured"] is False and runtime["effective"] == "local"
        clip = pcm16_wav(b"\x00\x00" * 1600, 16000)
        answer = client.post("/api/speech/transcribe", content=clip, headers={"Content-Type": "audio/wav"})
        assert answer.status_code == 200, answer.text
        assert answer.json() == {"text": "what is on today"}
        assert received and received[-1] > len(clip)
    finally:
        server.shutdown()
        server.server_close()


def test_dictation_still_says_not_configured_without_a_managed_engine(client: Any) -> None:
    clip = pcm16_wav(b"\x00\x00" * 1600, 16000)
    answer = client.post("/api/speech/transcribe", content=clip, headers={"Content-Type": "audio/wav"})
    assert answer.status_code == 422
    assert answer.json()["detail"]["reason_code"] == "speech_runtime_not_configured"


def test_the_pin_script_fills_digests_from_hugging_face_without_downloading() -> None:
    from scripts.pin_voice_catalogue import pin

    data = json.loads(Path("raiker/config/voice-catalogue.json").read_text(encoding="utf-8"))
    for item in data["items"]:
        if item.get("hf_repo"):
            item["pending_reason"] = "test unpinned entry"
    # Preserve the generic licence-refusal contract with a synthetic item;
    # removed Piper entries must not remain a supported download dependency.
    data["items"].append({"id": "unreviewed-test", "component": "kokoro_model",
                          "name": "test", "licence": "unreviewed", "source_page": "https://huggingface.co/test/model",
                          "hf_repo": "test/model", "hf_path": "model.onnx", "pending_reason": "test unpinned entry"})
    commit = "a" * 40
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(f"{request.method} {request.url.path}")
        if request.url.path.endswith("/revision/main"):
            return httpx.Response(200, json={"sha": commit})
        path = dict(httpx.QueryParams(request.content.decode()))["paths"]
        return httpx.Response(200, json=[{"path": path, "lfs": {"oid": "b" * 64, "size": 1234}}])

    changes = pin(data, httpx.Client(transport=httpx.MockTransport(handler)), {})
    small = next(item for item in data["items"] if item["id"] == "whisper-small-q5_1")
    assert small["url"] == f"https://huggingface.co/ggerganov/whisper.cpp/resolve/{commit}/ggml-small-q5_1.bin"
    assert small["sha256"] == "b" * 64 and small["size_bytes"] == 1234 and "pending_reason" not in small
    # A voice whose licence is unreviewed gets its digest but stays pending.
    unreviewed = next(item for item in data["items"] if item["id"] == "unreviewed-test")
    assert unreviewed["sha256"] == "b" * 64 and "licence" in unreviewed["pending_reason"]
    assert any("digest only" in line for line in changes)
    # One revision lookup per repository, and nothing downloaded.
    assert seen.count("GET /api/models/ggerganov/whisper.cpp/revision/main") == 1
    assert not any("/resolve/" in entry for entry in seen)
    assert parse(data).get("whisper-small-q5_1").installable


def test_all_managed_profiles_use_kokoro_and_removed_piper_is_refused() -> None:
    from raiker.voice.catalogue import parse
    from raiker.voice.tts_worker import parse_args

    catalogue = load()
    assert all(profile.speaking == "kokoro" for profile in catalogue.profiles.values())
    assert not any("piper" in item.item_id or "piper" in item.component for item in catalogue.items)
    for name in catalogue.profiles:
        profile = resolve(catalogue, name, _hardware(memory_gib=32, os_name="linux"))
        assert profile.speaking_installable
        assert profile.part("kokoro_model") and profile.part("kokoro_voices")
    with pytest.raises(CatalogueError, match="voice_item_unknown"):
        catalogue.get("piper-voice-en_US-amy-medium")
    raw = json.loads(Path("raiker/config/voice-catalogue.json").read_text())
    raw["profiles"]["lite"]["speaking"] = "piper"
    with pytest.raises(CatalogueError, match="voice_catalogue_invalid"):
        parse(raw)
    with pytest.raises(SystemExit):
        parse_args(["--engine", "piper"])


def test_removed_voice_settings_fall_back_to_kokoro_default() -> None:
    assert parse_settings({"profile": "lite", "voice": "en_US-amy-medium"}).voice is None
    assert parse_settings({"profile": "lite", "voice": "af_heart"}).voice == "af_heart"

@pytest.mark.parametrize("host", ["us.aws.cdn.hf.co", "us.gcp.cdn.hf.co"])
def test_voice_download_accepts_documented_huggingface_cdn(tmp_path: Path, host: str) -> None:
    payload = b"verified-model"
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "github.com":
            return httpx.Response(302, headers={"Location": f"https://{host}/model"})
        return httpx.Response(200, content=payload)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        path = installer.install_item(tmp_path, _item(payload), client=client)
    assert path.read_bytes() == payload


def test_voice_redirect_is_refused_before_contacting_destination(tmp_path: Path) -> None:
    contacted: list[str] = []
    def handler(request: httpx.Request) -> httpx.Response:
        contacted.append(str(request.url.host))
        return httpx.Response(302, headers={"Location": "https://evil.example/private"})
    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(installer.VoiceInstallError, match="voice_download_host_refused"),
    ):
        installer.install_item(tmp_path, _item(b"data"), client=client)
    assert contacted == ["github.com"]

@pytest.mark.parametrize("location", [None, "/again"])
def test_voice_redirect_failures_are_bounded(tmp_path: Path, location: str | None) -> None:
    requests: list[str] = []
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(302, headers={} if location is None else {"location": location})
    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(installer.VoiceInstallError, match="voice_download_failed"),
    ):
        installer.download(_item(b"data"), tmp_path / "model", client=client)
    assert len(requests) == (1 if location is None else 6)
    assert not list(tmp_path.iterdir())
