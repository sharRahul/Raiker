"""RU-22 — once the model has finished, Build runs the declared checks itself.

In RU-J4 the model ran `python3 -m unittest test_pricing -v` where the project
declared `python3 -m unittest -q`, so the turn read *Not verified* although the
tests passed. The runtime now proposes each declared check that did not run
after the last change, exactly as written, through the same governed command
path as any call the model makes, and the model closes the turn after reading
the results.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from raiker.control.build_outcome import checks_due
from raiker.models.contracts import ModelResponse, ToolCallProposal
from raiker.storage.sqlite import SQLiteStore
from tests.test_bug_346_accepted_build_write import (
    BUILD_WRITE_GATES,
    RELAY,
    _turn_on,
    client,
    headers,
    workspace,
)
from tests.test_turn_resume_after_approval import ScriptedRouter, scripted_model

__all__ = ["client", "headers", "scripted_model", "workspace"]

_WRITE = {"tool_name": "write_file", "status": "success", "created_at": "2026-11-25T10:00:00Z",
          "completed_at": "2026-11-25T10:00:00Z", "arguments_json": '{"path": "pricing.py"}'}


def test_a_check_that_never_ran_is_due() -> None:
    assert checks_due(tool_actions=[_WRITE], command_runs=[], checks=["python3 -m unittest -q"]) == [
        "python3 -m unittest -q"
    ]


def test_a_check_run_in_another_form_is_still_due() -> None:
    other = {"safe_display": "python3 -m unittest test_pricing -v", "state": "succeeded", "exit_code": 0,
             "started_at": "2026-11-25T10:00:05Z", "cwd": "."}
    assert checks_due(tool_actions=[_WRITE], command_runs=[other], checks=["python3 -m unittest -q"]) == [
        "python3 -m unittest -q"
    ]


def test_nothing_is_due_without_a_change_or_without_checks() -> None:
    assert checks_due(tool_actions=[], command_runs=[], checks=["pytest -q"]) == []
    assert checks_due(tool_actions=[_WRITE], command_runs=[], checks=[]) == []


def _shell_rows(workspace: Path, session_id: str) -> list[dict[str, Any]]:
    with SQLiteStore(workspace).connect() as connection:
        return [
            dict(row)
            for row in connection.execute(
                "SELECT tool_name, arguments_json, status FROM tool_actions "
                "WHERE session_id = ? AND tool_name = 'shell'",
                (session_id,),
            )
        ]


def test_build_proposes_the_declared_check_after_the_model_finishes(
    workspace: Path,
    client: TestClient,
    headers: dict[str, str],
    scripted_model: ScriptedRouter,
    offline_default_model: None,
) -> None:
    scripted_model.responses = [
        ModelResponse(
            text="Writing pricing.py.",
            tool_calls=[ToolCallProposal("call_w", "write_file", {"path": "pricing.py", "text": "RATE = 0.1\n"})],
        ),
        ModelResponse(text="Done."),
        ModelResponse(text="The declared check is waiting for you."),
    ]
    for capability in (*BUILD_WRITE_GATES, RELAY):
        _turn_on(client, headers, capability)
    project = client.post("/api/projects", json={"name": "Pricing"}, headers=headers).json()
    pid = project["project_id"]
    put = client.put(f"/api/projects/{pid}/context", json={"checks": ["python3 -m unittest -q"]}, headers=headers)
    assert put.status_code == 200, put.text
    # Build works in the selected project; new sessions are stamped with it.
    selected = client.put("/api/projects/selection", json={"project_id": pid}, headers=headers)
    assert selected.status_code == 200, selected.text

    resp = client.post(
        "/api/prompts",
        json={"text": "Create pricing.py.", "surface": "build", "project_id": pid, "capability_modes": {}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    parked = resp.json()
    approval_id = str(parked["approval"]["approval_id"])
    session_id = str(parked["session_id"])
    client.post(f"/api/approvals/{approval_id}/resolve", json={"approve": True, "reason": "ok"}, headers=headers)
    resumed = client.post(f"/api/approvals/{approval_id}/resume", headers=headers)
    assert resumed.status_code == 200, resumed.text

    rows = _shell_rows(workspace, session_id)
    assert rows, "the runtime proposed no declared check"
    assert '"python3 -m unittest -q"' in rows[0]["arguments_json"]
