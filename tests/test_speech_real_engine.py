"""Optional real-runtime test; supply a local endpoint and known WAV fixture."""

import os
from pathlib import Path

import pytest

from raiker.models.speech_runtime import SpeechRuntimeSettings, transcribe


@pytest.mark.parametrize("language", ["en", "hi"])
def test_real_local_speech_engine(language: str) -> None:
    endpoint = os.environ.get("RAIKER_SPEECH_TEST_ENDPOINT")
    fixture = os.environ.get(f"RAIKER_SPEECH_TEST_{language.upper()}_WAV")
    expected = os.environ.get(f"RAIKER_SPEECH_TEST_{language.upper()}_TEXT")
    if not endpoint or not fixture or not expected:
        pytest.skip("Set the local speech endpoint, fixture path and expected text")
    transcript = transcribe(
        SpeechRuntimeSettings(endpoint=endpoint), Path(fixture).read_bytes(), language=language
    )
    assert expected.casefold() in transcript.casefold()
