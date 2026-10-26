"""TOOL-151 — a Build Plan turn questions its own plan before proposing it."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from raiker.contracts.models import PromptOptions
from raiker.runtime.orchestrator import PLAN_POSTURE_PROMPT
from tests.test_environment_context_turns import (
    RecordingRouter,
    _envelope,
    _events,
    _handle,
    _orchestrator,
    _system_text,
)


def _system(tmp_path: Path, planning_mode: str) -> tuple[str, str, Path]:
    router = RecordingRouter()
    orchestrator = _orchestrator(tmp_path, router)
    envelope = replace(
        _envelope("build"),
        options=PromptOptions(max_tool_calls=2, approval_mode="manual", planning_mode=planning_mode),
    )
    _handle(orchestrator, envelope)
    return _system_text(router.seen_messages[0]), envelope.session_id, tmp_path


def test_a_plan_turn_is_told_to_grill_its_plan(tmp_path: Path) -> None:
    text, session_id, workspace = _system(tmp_path, "always")
    assert PLAN_POSTURE_PROMPT in text
    assert "Questions I asked of this plan" in text
    assert _events(workspace, session_id, "plan_posture_applied")


def test_any_other_turn_is_not(tmp_path: Path) -> None:
    text, _session, _ws = _system(tmp_path, "auto")
    assert PLAN_POSTURE_PROMPT not in text
