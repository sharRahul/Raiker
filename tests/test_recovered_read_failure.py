"""A failed read the model recovers from does not fail the turn (regular use, 2026-11-16).

A budget CSV attached to Chat is already in the turn's context. A model still
called ``read_file`` on its filename, the read failed (``not_found``), and the
model then answered correctly from the attachment — but the turn closed as
*failed* and Chat read "Not done". A read changes nothing, so its failure stays
a visible failed step and the turn completes; a failed write still fails it.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path

from raiker.models.contracts import ModelResponse, ToolCallProposal
from raiker.runtime.attachments import store_document
from tests.test_turn_resume_after_approval import (
    ScriptedRouter,
    _envelope,
    _identity_for,
    _orchestrator,
)


def test_an_uploaded_csv_can_be_used_after_a_failed_read(tmp_path: Path) -> None:
    filename = "household-budget.csv"
    csv = "Category,September,October\nEating out,180,300\nShopping,200,310\n"
    answer = "Eating out grew by £120 and Shopping grew by £110."
    call = ToolCallProposal(call_id="c1", tool_name="read_file", arguments={"path": filename})
    router = ScriptedRouter([
        ModelResponse(text="Let me look.", tool_calls=[call]),
        ModelResponse(text=answer),
    ])
    orchestrator = _orchestrator(tmp_path, router)
    store = orchestrator.tool_broker.store
    assert store is not None
    attachment = store_document(
        store,
        filename=filename,
        media_type="text/csv",
        data=csv.encode(),
        owner_principal_id="principal_owner",
    )
    envelope = _envelope("Which categories grew most in pounds from September to October?")
    envelope = replace(
        envelope,
        prompt=replace(
            envelope.prompt,
            attachments=[{"type": "document", "attachment_id": attachment.attachment_id}],
        ),
    )
    response = asyncio.run(
        orchestrator.ahandle(envelope, identity=_identity_for(tmp_path, orchestrator, envelope))
    )

    initial_messages, follow_up_messages = router.seen_messages
    for messages in (initial_messages, follow_up_messages):
        assert any("Eating out,180,300" in message.content for message in messages)
        assert any("Shopping,200,310" in message.content for message in messages)
    [tool_result] = [message for message in follow_up_messages if message.role == "tool"]
    assert tool_result.tool_call_id == call.call_id
    assert json.loads(tool_result.content)["type"] == "not_found"
    assert response.status == "completed"
    assert answer in response.message


def test_a_failed_read_with_no_answer_still_fails(tmp_path: Path) -> None:
    call = ToolCallProposal(call_id="c1", tool_name="read_file", arguments={"path": "missing.csv"})
    router = ScriptedRouter([
        ModelResponse(text="Let me look.", tool_calls=[call]),
        ModelResponse(text=""),
    ])
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("Which category grew most?")
    response = asyncio.run(
        orchestrator.ahandle(envelope, identity=_identity_for(tmp_path, orchestrator, envelope))
    )
    assert response.status == "failed"
