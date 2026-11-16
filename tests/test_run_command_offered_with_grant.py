"""`run_command` is offered only where a command grant exists (regular use, 2026-11-16)."""

from __future__ import annotations

from pathlib import Path

from raiker.models.contracts import ModelResponse
from tests.test_turn_resume_after_approval import ScriptedRouter, _envelope, _orchestrator


def _offered(tmp_path: Path, granted: bool) -> set[str]:
    router = ScriptedRouter([ModelResponse(text="ok")])
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("Run the tests")
    if granted:
        store = orchestrator.tool_broker.store
        assert store is not None
        store.put_session_command_grant(
            session_id=envelope.session_id, principal_id="principal_owner",
            commands=[["python3", "-m", "unittest"]], timeout_seconds=60,
            expires_at="2999-01-01T00:00:00+00:00",
        )
    orchestrator._preselect_turn_tools(envelope)
    return {spec.name for spec in orchestrator._turn_tool_specs()}


def test_without_a_grant_the_model_is_not_offered_run_command(tmp_path: Path) -> None:
    offered = _offered(tmp_path, granted=False)
    assert "run_command" not in offered
    assert "shell" in offered


def test_with_a_grant_run_command_is_offered(tmp_path: Path) -> None:
    assert "run_command" in _offered(tmp_path, granted=True)
