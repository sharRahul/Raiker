# SPDX-License-Identifier: Apache-2.0
"""Voice spec §13, real engines — opt in with ``RAIKER_VOICE_LIVE=1``.

Downloads real catalogue items from their sources, verifies them against the
catalogue's digests, starts the real engines and uses them. Skipped by default:
it needs the network, a few hundred megabytes and, for Kokoro, the
``kokoro-onnx`` package in Raiker's Python.
"""

from __future__ import annotations

import io
import os
import wave
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.skipif(os.environ.get("RAIKER_VOICE_LIVE") != "1", reason="set RAIKER_VOICE_LIVE=1")


def test_balanced_speaking_installs_verifies_and_speaks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("kokoro_onnx")
    from raiker.cli.principal_resolver import bootstrap_owner
    from raiker.models.engines.resources import ResourceLedger
    from raiker.voice import installer
    from raiker.voice.engines import VoiceEngines
    from raiker.voice.service import VoiceService

    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    engines = VoiceEngines(ws, ledger=ResourceLedger())
    service = VoiceService(ws, "principal_owner", engines=engines)
    service.save({"profile": "balanced", "voice": "af_heart"})
    items = service.installable_items()
    assert {item.item_id for item in items} >= {"kokoro-82m-int8", "kokoro-voices-v1"}
    with httpx.Client(timeout=httpx.Timeout(30.0, read=300.0)) as client:
        for item in items:
            if item.component.startswith("kokoro"):
                installer.install_item(ws, item, client=client)
    try:
        audio = service.speak("Your next meeting is at three o'clock.")
        with wave.open(io.BytesIO(audio)) as clip:
            seconds = clip.getnframes() / clip.getframerate()
            assert clip.getframerate() == 24000
        assert 1.0 < seconds < 8.0
        assert service.status()["speaking"]["state"] == "ready"
    finally:
        engines.stop_all()
    assert service.remove() > 100_000_000
    assert installer.installed_bytes(ws) == 0


@pytest.mark.skipif(not os.environ.get("RAIKER_VOICE_PACKAGED_HOST"), reason="set RAIKER_VOICE_PACKAGED_HOST")
def test_packaged_kokoro_worker_uses_verified_assets_and_local_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the frozen worker separately from whole-profile memory admission."""
    from raiker.models.engines.resources import ResourceLedger
    from raiker.voice import engines as engine_module
    from raiker.voice import installer
    from raiker.voice.catalogue import load

    host = Path(os.environ["RAIKER_VOICE_PACKAGED_HOST"]).resolve()
    assert host.is_file()
    ws = tmp_path / "ws"
    ws.mkdir()
    catalogue = load()
    paths: dict[str, Path] = {}
    with httpx.Client(timeout=httpx.Timeout(30.0, read=300.0)) as client:
        for name in ("kokoro-82m-int8", "kokoro-voices-v1"):
            item = catalogue.get(name)
            installer.install_item(ws, item, client=client)
            path = installer.installed_path(ws, item)
            assert path is not None
            paths[name] = path
    monkeypatch.setattr(engine_module, "worker_argv", lambda: [str(host), "--voice-tts-worker"])
    engines = engine_module.VoiceEngines(ws, ledger=ResourceLedger())
    try:
        running = engines.ensure_speaker("kokoro", model=paths["kokoro-82m-int8"],
                                         voices=paths["kokoro-voices-v1"], threads=1, ram=450_000_000)
        assert httpx.get(f"{running.endpoint}/health").status_code == 403
        audio = engines.synthesise("Your next meeting is at three o'clock.", voice="af_heart", speed=1.0)
        with wave.open(io.BytesIO(audio)) as clip:
            assert clip.getframerate() == 24000
            assert 1.0 < clip.getnframes() / clip.getframerate() < 8.0
            assert any(clip.readframes(clip.getnframes()))
    finally:
        engines.stop_all()
    assert engines.running("speaker") is None

@pytest.mark.skipif(
    os.environ.get("RAIKER_VOICE_WHISPER_LIVE") != "1" or os.name != "nt",
    reason="opt-in Windows CPU Whisper/Kokoro round trip",
)
def test_packaged_kokoro_audio_round_trips_through_verified_windows_whisper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import re

    from raiker.models.engines.resources import ResourceLedger
    from raiker.models.speech_runtime import SpeechRuntimeSettings, transcribe
    from raiker.voice import engines as engine_module
    from raiker.voice import installer
    from raiker.voice.catalogue import load

    host = Path(os.environ["RAIKER_VOICE_PACKAGED_HOST"]).resolve()
    assert host.is_file()
    ws = tmp_path / "roundtrip"
    ws.mkdir()
    catalogue = load()
    paths: dict[str, Path] = {}
    names = ("kokoro-82m-int8", "kokoro-voices-v1", "whisper-server-windows-x64-cpu", "whisper-base.en-q5_1")
    with httpx.Client(timeout=httpx.Timeout(30.0, read=300.0)) as client:
        for name in names:
            item = catalogue.get(name)
            installer.install_item(ws, item, client=client)
            path = installer.installed_path(ws, item)
            assert path is not None, name
            paths[name] = path
    monkeypatch.setattr(engine_module, "worker_argv", lambda: [str(host), "--voice-tts-worker"])
    engines = engine_module.VoiceEngines(ws, ledger=ResourceLedger())
    try:
        engines.ensure_speaker("kokoro", model=paths["kokoro-82m-int8"], voices=paths["kokoro-voices-v1"],
                               threads=1, ram=450_000_000)
        spoken = "The quick brown fox jumps over the lazy dog."
        audio = engines.synthesise(spoken, voice="af_heart", speed=1.0)
        whisper = engines.ensure_whisper(paths["whisper-server-windows-x64-cpu"], paths["whisper-base.en-q5_1"],
                                         threads=2, device="cpu", ram=500_000_000, vram=0, gpu=None)
        heard = transcribe(SpeechRuntimeSettings(endpoint=whisper.endpoint), audio, language="en")
        assert re.findall(r"[a-z]+", heard.lower()) == re.findall(r"[a-z]+", spoken.lower()), heard
    finally:
        engines.stop_all()
    assert engines.running("speaker") is None
    assert engines.running("whisper") is None
