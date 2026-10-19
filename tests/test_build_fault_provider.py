"""BR-D06 — a provider that fails after an accepted write, driven through the real routes.

The model proposes one write, the owner accepts it, the write lands, and the
provider then fails on the continuation. The turn's transcript can say anything;
the outcome is read from the runtime's records and stays **Not verified**, with
nothing passed — never verified on the strength of a write alone.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from raiker.models.contracts import ModelResponse
from raiker.models.exceptions import ModelProviderError
from tests.test_bug_346_accepted_build_write import (
    BUILD_WRITE_GATES,
    RELAY,
    _turn_on,
    _write_notes,
    client,
    headers,
    workspace,
)
from tests.test_turn_resume_after_approval import ScriptedRouter, scripted_model

__all__ = ["client", "headers", "scripted_model", "workspace"]


def test_a_provider_failing_after_an_accepted_write_never_verifies(
    workspace: Path,
    client: TestClient,
    headers: dict[str, str],
    scripted_model: ScriptedRouter,
    offline_default_model: None,
) -> None:
    calls = {"n": 0}
    proposal = ModelResponse(text="Creating notes.txt.", tool_calls=[_write_notes()])

    def chat(provider: str, model: str, messages: Any, tools: Any = None) -> ModelResponse:
        calls["n"] += 1
        if calls["n"] == 1:
            return proposal
        raise ModelProviderError("provider_unavailable")

    scripted_model.chat = chat  # type: ignore[method-assign]
    for capability in (*BUILD_WRITE_GATES, RELAY):
        _turn_on(client, headers, capability)
    project = client.post("/api/projects", json={"name": "Faults"}, headers=headers).json()["project_id"]
    parked = client.post(
        "/api/prompts",
        json={"text": "Create notes.txt.", "surface": "build", "project_id": project, "capability_modes": {}},
        headers=headers,
    ).json()
    assert parked["status"] == "needs_approval", parked
    approval_id = str(parked["approval"]["approval_id"])
    resolved = client.post(
        f"/api/approvals/{approval_id}/resolve", json={"approve": True, "reason": "accepted"}, headers=headers
    )
    assert resolved.status_code == 200, resolved.text
    resumed = client.post(f"/api/approvals/{approval_id}/resume", headers=headers)
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] != "completed" or calls["n"] >= 2

    written = [path for path in workspace.rglob("notes.txt") if ".raiker" not in path.parts]
    assert len(written) == 1
    outcome = client.get(
        f"/api/sessions/{parked['session_id']}/turns/{parked['turn_id']}/outcome", headers=headers
    ).json()
    assert outcome["outcome"] == "completed_unverified", outcome
    assert outcome["writes"] == 1
    assert all(row["result"] != "passed" for row in outcome["checks"])
