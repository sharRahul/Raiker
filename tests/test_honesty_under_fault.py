"""AG-5 (beta plan) — a reply cannot be the only account of an action that failed.

The model is shown a tool failure and answers as if it had succeeded: the
classic false-success claim. The runtime's own record decides what the owner
reads: the receipt lists no change, and the answer ends with a **Not done**
line written from the tool result, never from the model's text.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from raiker.models.contracts import ModelResponse
from raiker.runtime.orchestrator import not_done_note
from tests.test_bug_346_accepted_build_write import _write_notes, client, headers, workspace
from tests.test_turn_resume_after_approval import ScriptedRouter, scripted_model

__all__ = ["client", "headers", "scripted_model", "workspace"]

FALSE_CLAIM = "Done — I created notes.txt with your text."


def test_a_refused_write_is_reported_whatever_the_model_claims(
    workspace: Path,
    client: TestClient,
    headers: dict[str, str],
    scripted_model: ScriptedRouter,
    offline_default_model: None,
) -> None:
    calls = {"n": 0}

    def chat(provider: str, model: str, messages: Any, tools: Any = None) -> ModelResponse:
        calls["n"] += 1
        if calls["n"] == 1:
            return ModelResponse(text="Creating notes.txt.", tool_calls=[_write_notes()])
        # The tool result said it was refused; the model claims success anyway.
        return ModelResponse(text=FALSE_CLAIM, tool_calls=[])

    scripted_model.chat = chat  # type: ignore[method-assign]
    # No Build write gate is turned on, so the write is refused by policy.
    project = client.post("/api/projects", json={"name": "Honesty"}, headers=headers).json()["project_id"]
    answer = client.post(
        "/api/prompts",
        json={"text": "Create notes.txt.", "surface": "build", "project_id": project, "capability_modes": {}},
        headers=headers,
    ).json()

    # The write waits for the owner, who refuses it; the turn then resumes and
    # the model is shown the refusal.
    assert answer["status"] == "needs_approval", answer
    approval_id = str(answer["approval"]["approval_id"])
    resolved = client.post(
        f"/api/approvals/{approval_id}/resolve", json={"approve": False, "reason": "not now"}, headers=headers
    )
    assert resolved.status_code == 200, resolved.text
    resumed = client.post(f"/api/approvals/{approval_id}/resume", headers=headers)
    assert resumed.status_code == 200, resumed.text
    answer = {**answer, **resumed.json()}

    assert not [p for p in workspace.rglob("notes.txt") if ".raiker" not in p.parts]
    message = str(answer.get("message", ""))
    assert calls["n"] >= 2, "the model was never asked to answer after the refusal"
    assert FALSE_CLAIM in message, answer
    assert "**Not done:**" in message, message
    assert message.index("**Not done:**") > message.index(FALSE_CLAIM)

    receipt = client.get(
        f"/api/sessions/{answer['session_id']}/turns/{answer['turn_id']}/receipt", headers=headers
    )
    if receipt.status_code == 200:
        assert receipt.json()["changes"] == []


def test_the_note_names_each_action_and_how_it_ended() -> None:
    note = not_done_note({"send_email": ("Email · send", "failed"), "write_file": ("File · write", "denied")})
    assert note == (
        "**Not done:** Email · send failed; File · write was refused. "
        "Raiker's record shows it did not complete."
    )


def test_a_missing_file_is_a_wrong_guess_not_a_failing_capability() -> None:
    """BD-5 — three mistyped paths contained a Build turn's file reads."""
    from types import SimpleNamespace

    from raiker.runtime.orchestrator import RuntimeOrchestrator

    recorded: list[bool] = []
    breaker = SimpleNamespace(record=lambda *_a, ok, **_k: recorded.append(ok))
    orchestrator = RuntimeOrchestrator.__new__(RuntimeOrchestrator)
    miss = SimpleNamespace(status="failed", error={"type": "not_found"})
    fault = SimpleNamespace(status="failed", error={"type": "outside_workspace"})
    action = SimpleNamespace(tool_name="read_file")
    orchestrator._record_tool_outcome(breaker, "owner", action, miss, None)  # type: ignore[arg-type]
    assert recorded == []
    orchestrator._record_tool_outcome(breaker, "owner", action, fault, None)  # type: ignore[arg-type]
    assert recorded == [False]
