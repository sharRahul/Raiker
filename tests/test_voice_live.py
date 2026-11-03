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
