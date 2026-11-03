"""Voice spec §5.4 — a spoken turn is an ordinary governed turn, asked to sound spoken."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from raiker.contracts.models import ContractValidationError, normalize_input_mode
from raiker.runtime.orchestrator import SPOKEN_STYLE_PROMPT
from tests.test_environment_context_turns import (
    RecordingRouter,
    _envelope,
    _events,
    _handle,
    _orchestrator,
    _system_text,
)


def _system(tmp_path: Path, input_mode: str) -> tuple[str, str]:
    router = RecordingRouter()
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("chat")
    envelope = replace(envelope, prompt=replace(envelope.prompt, metadata={**envelope.prompt.metadata, "input_mode": input_mode}))
    _handle(orchestrator, envelope)
    return _system_text(router.seen_messages[0]), envelope.session_id


def test_a_spoken_turn_asks_for_a_spoken_answer(tmp_path: Path) -> None:
    text, session_id = _system(tmp_path, "spoken")
    assert SPOKEN_STYLE_PROMPT in text
    assert "never given by voice" in text
    assert _events(tmp_path, session_id, "spoken_style_applied")


def test_a_typed_or_dictated_turn_does_not(tmp_path: Path) -> None:
    for mode in ("typed", "dictated"):
        text, _ = _system(tmp_path / mode, mode)
        assert SPOKEN_STYLE_PROMPT not in text


def test_spoken_is_a_recognised_input_mode() -> None:
    assert normalize_input_mode("spoken") == "spoken"
    with pytest.raises(ContractValidationError):
        normalize_input_mode("shouted")
