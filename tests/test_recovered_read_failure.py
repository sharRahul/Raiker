"""A failed read the model recovers from does not fail the turn (regular use, 2026-11-16).

A budget CSV attached to Chat is already in the turn's context. A model still
called ``read_file`` on its filename, the read failed (``not_found``), and the
model then answered correctly from the attachment — but the turn closed as
*failed* and Chat read "Not done". A read changes nothing, so its failure stays
a visible failed step and the turn completes; a failed write still fails it.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from raiker.models.contracts import ModelResponse, ToolCallProposal
from tests.test_turn_resume_after_approval import (
    ScriptedRouter,
    _envelope,
    _identity_for,
    _orchestrator,
)


def _run(tmp_path: Path, call: ToolCallProposal, answer: str) -> str:
    router = ScriptedRouter([
        ModelResponse(text="Let me look.", tool_calls=[call]),
        ModelResponse(text=answer),
    ])
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("Which category grew most?")
    response = asyncio.run(
        orchestrator.ahandle(envelope, identity=_identity_for(tmp_path, orchestrator, envelope))
    )
    return response.status


def test_a_failed_read_followed_by_an_answer_completes_the_turn(tmp_path: Path) -> None:
    call = ToolCallProposal(call_id="c1", tool_name="read_file", arguments={"path": "household-budget.csv"})
    assert _run(tmp_path, call, "Eating out grew most, by £120.") == "completed"


def test_a_failed_read_with_no_answer_still_fails(tmp_path: Path) -> None:
    call = ToolCallProposal(call_id="c1", tool_name="read_file", arguments={"path": "missing.csv"})
    assert _run(tmp_path, call, "") == "failed"
