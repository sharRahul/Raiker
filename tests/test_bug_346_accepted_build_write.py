"""BUG-346 — an accepted Build write is applied once, or says exactly why not.

Found driving BR-D01 live: on a fresh workspace with **File writes** and **Patch
apply** on, a Build turn proposed ``write_file``; the owner pressed **Accept**,
the parked turn resumed, and its row read **Write file notes.txt failed**. No
file was written, the model called its own call invalid, and the proposal's
``tool_actions`` row still read as waiting.

The cause was not the model. On an account, the relay that turns an accepted
decision into an effect (``approval_execution_relay``) has its own gate, and it
is off until the owner turns it on. Accept therefore recorded the decision and
performed nothing — which governance requires — while every surface said only
"metadata-only", the model was told the capability never executes, and the row
was never closed.

These tests take the model out of the loop (a scripted provider proposes one
fixed ``write_file``) and drive the exact path Build uses: an account created
through ``/api/auth/register``, gates turned on through the governed route, a
Build turn on a managed project, **Accept** through
``POST /api/approvals/{id}/resolve`` and the continuation through
``POST /api/approvals/{id}/resume``. The bar is the reference agents': an
approved edit applies once and the loop continues — and where the owner's own
switch stops it, the owner and the model are told which switch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.models.contracts import ModelResponse, ToolCallProposal
from raiker.storage.sqlite import SQLiteStore
from tests.test_turn_resume_after_approval import ScriptedRouter, scripted_model

__all__ = ["scripted_model"]

#: The two switches the live round turned on.
BUILD_WRITE_GATES = ("file_write_execution", "patch_apply_execution")
RELAY = "approval_execution_relay"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    # Registration is loopback-only, as it is for the real first run.
    return TestClient(create_app(workspace), client=("127.0.0.1", 50000))


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    registered = client.post(
        "/api/auth/register",
        json={"username": "owner", "password": "correct horse battery staple 1"},
    )
    assert registered.status_code == 200, registered.text
    body = registered.json()
    return {"Authorization": f"Bearer {body['token']}", "X-CSRF-Token": body.get("csrf_token") or ""}


def _write_notes() -> ToolCallProposal:
    return ToolCallProposal(
        call_id="call_notes",
        tool_name="write_file",
        arguments={"path": "notes.txt", "text": "hello from Build\n"},
    )


def _turn_on(client: TestClient, headers: dict[str, str], capability: str) -> None:
    resp = client.post(
        f"/api/capability-gates/{capability}/set",
        json={"target_state": "enabled_runtime", "reason": "owner turned this on"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


def _build_turn(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    project = client.post("/api/projects", json={"name": "Notes"}, headers=headers)
    assert project.status_code == 200, project.text
    resp = client.post(
        "/api/prompts",
        json={
            "text": "Create notes.txt containing one line.",
            "surface": "build",
            "project_id": project.json()["project_id"],
            # Build's default mode sends no per-turn modes: standing permissions apply.
            "capability_modes": {},
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    parked = dict(resp.json())
    assert parked["status"] == "needs_approval", parked
    return parked


def _write_rows(workspace: Path, session_id: str) -> list[dict[str, Any]]:
    with SQLiteStore(workspace).connect() as connection:
        return [
            dict(row)
            for row in connection.execute(
                "SELECT status, completed_at FROM tool_actions "
                "WHERE session_id = ? AND tool_name = 'write_file'",
                (session_id,),
            )
        ]


def _written(workspace: Path) -> list[Path]:
    return [path for path in workspace.rglob("notes.txt") if ".raiker" not in path.parts]


def _last_tool_outcome(model: ScriptedRouter) -> dict[str, Any]:
    tool_messages = [m for m in model.seen_messages[-1] if m.role == "tool"]
    return dict(json.loads(tool_messages[-1].content))


class TestWithTheBuildSetupOn:
    def test_accept_writes_the_file_once_and_the_turn_carries_on(
        self,
        workspace: Path,
        client: TestClient,
        headers: dict[str, str],
        scripted_model: ScriptedRouter,
        offline_default_model: None,
    ) -> None:
        scripted_model.responses = [
            ModelResponse(text="Creating notes.txt.", tool_calls=[_write_notes()]),
            ModelResponse(text="Created notes.txt."),
        ]
        for capability in (*BUILD_WRITE_GATES, RELAY):
            _turn_on(client, headers, capability)
        parked = _build_turn(client, headers)
        approval_id = str(parked["approval"]["approval_id"])
        session_id, turn_id = str(parked["session_id"]), str(parked["turn_id"])

        detail = client.get(f"/api/approvals/{approval_id}", headers=headers).json()
        assert detail["executes_on_approval"] is True

        resolved = client.post(
            f"/api/approvals/{approval_id}/resolve",
            json={"approve": True, "reason": "accepted in the Build workspace"},
            headers=headers,
        )
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()["executes_action"] is True
        assert resolved.json()["resume"]["resumable"] is True

        resumed = client.post(f"/api/approvals/{approval_id}/resume", headers=headers)
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["status"] == "completed", resumed.json()
        assert _last_tool_outcome(scripted_model)["status"] == "success"

        written = _written(workspace)
        assert len(written) == 1, written
        assert written[0].read_text(encoding="utf-8") == "hello from Build\n"

        # The proposal's own row is closed by the decision, not left waiting.
        rows = _write_rows(workspace, session_id)
        assert [row["status"] for row in rows] == ["success"]
        assert rows[0]["completed_at"]

        # BR-D01 reads those same records: the write is a change now.
        view = client.get(f"/api/sessions/{session_id}/turns/{turn_id}/outcome", headers=headers)
        assert view.status_code == 200, view.text
        assert view.json()["outcome"] == "completed_unverified", view.json()
        assert view.json()["writes"] == 1


class TestWithTheRelayOff:
    """The live round's state: File writes and Patch apply on, the relay never turned on."""

    def test_the_card_names_the_switch_before_the_owner_decides(
        self,
        workspace: Path,
        client: TestClient,
        headers: dict[str, str],
        scripted_model: ScriptedRouter,
        offline_default_model: None,
    ) -> None:
        scripted_model.responses = [
            ModelResponse(text="Creating notes.txt.", tool_calls=[_write_notes()]),
        ]
        for capability in BUILD_WRITE_GATES:
            _turn_on(client, headers, capability)
        parked = _build_turn(client, headers)

        detail = client.get(
            f"/api/approvals/{parked['approval']['approval_id']}", headers=headers
        ).json()
        assert detail["executes_on_approval"] is False
        assert "will not be carried out" in detail["metadata_only_notice"]
        assert "Approval execution relay" in detail["metadata_only_notice"]

    def test_accept_is_recorded_names_the_switch_and_closes_the_row(
        self,
        workspace: Path,
        client: TestClient,
        headers: dict[str, str],
        scripted_model: ScriptedRouter,
        offline_default_model: None,
    ) -> None:
        scripted_model.responses = [
            ModelResponse(text="Creating notes.txt.", tool_calls=[_write_notes()]),
            ModelResponse(text="I could not apply it: the relay is off."),
        ]
        for capability in BUILD_WRITE_GATES:
            _turn_on(client, headers, capability)
        parked = _build_turn(client, headers)
        approval_id = str(parked["approval"]["approval_id"])
        session_id = str(parked["session_id"])

        resolved = client.post(
            f"/api/approvals/{approval_id}/resolve",
            json={"approve": True, "reason": "accepted in the Build workspace"},
            headers=headers,
        )
        assert resolved.status_code == 200, resolved.text
        body = resolved.json()
        # Governance is unchanged: the owner's off switch still wins.
        assert body["executes_action"] is False
        assert body["not_executed_reason"] == f"metadata_only:{RELAY}"
        assert _written(workspace) == []

        resumed = client.post(f"/api/approvals/{approval_id}/resume", headers=headers)
        assert resumed.status_code == 200, resumed.text
        outcome = _last_tool_outcome(scripted_model)
        assert outcome["status"] == "not_executed"
        assert outcome["reason_code"] == f"metadata_only:{RELAY}"
        # Told which switch, not that the capability never executes.
        assert RELAY in outcome["note"]
        assert "without performing them, so nothing ran" not in outcome["note"]

        # Nothing ran, and the row says so instead of waiting on a made decision.
        assert [row["status"] for row in _write_rows(workspace, session_id)] == ["failed"]


class TestRowsSettleOnEveryDecision:
    def test_a_rejection_closes_the_row_as_denied(
        self,
        workspace: Path,
        client: TestClient,
        headers: dict[str, str],
        scripted_model: ScriptedRouter,
        offline_default_model: None,
    ) -> None:
        scripted_model.responses = [
            ModelResponse(text="Creating notes.txt.", tool_calls=[_write_notes()]),
            ModelResponse(text="Understood."),
        ]
        for capability in (*BUILD_WRITE_GATES, RELAY):
            _turn_on(client, headers, capability)
        parked = _build_turn(client, headers)

        resolved = client.post(
            f"/api/approvals/{parked['approval']['approval_id']}/resolve",
            json={"approve": False, "reason": "not now"},
            headers=headers,
        )
        assert resolved.status_code == 200, resolved.text
        assert [row["status"] for row in _write_rows(workspace, str(parked["session_id"]))] == [
            "denied"
        ]
