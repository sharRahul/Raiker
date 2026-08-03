"""B2 — a turn parked for an approval resumes instead of costing a re-prompt.

Before this, the agent loop `break`ed on `needs_approval` and the turn returned.
Even with BUG-06/FIXED-08 making an approved write really happen, the agent
stopped dead at its first write: the owner had to re-prompt, which discarded the
model's working state and re-paid for the whole context. These tests cover the
suspend → resolve → resume path end to end, and its boundaries.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.contracts.models import (
    ClientMetadata,
    PromptEnvelope,
    PromptOptions,
    PromptPayload,
    UserMetadata,
)
from raiker.events.writer import EventLogWriter
from raiker.models.contracts import ModelMessage, ModelResponse, ToolCallProposal, ToolSpec
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.orchestrator import RuntimeOrchestrator
from raiker.runtime.turn_suspension import (
    TurnSuspensionError,
    approval_outcome,
    deserialize_messages,
    serialize_messages,
)
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker


class ScriptedRouter:
    """A model whose replies are scripted, so the loop is the thing under test."""

    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = responses
        self.calls = 0
        self.seen_messages: list[list[ModelMessage]] = []

    def chat(
        self,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
    ) -> ModelResponse:
        index = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        self.seen_messages.append(list(messages))
        return self.responses[index]

    async def achat(
        self,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
    ) -> ModelResponse:
        return self.chat(provider, model, messages, tools)


def _orchestrator(tmp_path: Path, router: ScriptedRouter) -> RuntimeOrchestrator:
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    broker = ToolBroker(
        workspace_root=tmp_path,
        policy_engine=PolicyEngine(StaticPolicyConfig(tmp_path)),
        store=store,
        writer=writer,
    )
    return RuntimeOrchestrator(
        workspace_root=tmp_path,
        writer=writer,
        tool_broker=broker,
        model_router=router,  # type: ignore[arg-type]
    )


def _envelope(prompt: str) -> PromptEnvelope:
    return PromptEnvelope(
        request_id=new_id("req_"),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        client=ClientMetadata(type="test_harness", name="tests", version="0.0.0"),
        user=UserMetadata(),
        prompt=PromptPayload(text=prompt),
        options=PromptOptions(max_tool_calls=10),
    )


def _write_call() -> ToolCallProposal:
    return ToolCallProposal(
        call_id="call_write",
        tool_name="write_file",
        arguments={"path": "report.md", "text": "# Report\n"},
    )


def _event_types(orchestrator: RuntimeOrchestrator, session_id: str) -> list[str]:
    path = orchestrator.writer.path_for_session(session_id)
    return [json.loads(line)["event_type"] for line in path.read_text(encoding="utf-8").splitlines()]


# ── Suspension ───────────────────────────────────────────────────────────────


class TestTurnIsParkedOnApproval:
    def test_the_working_state_is_parked_against_the_approval(self, tmp_path: Path) -> None:
        router = ScriptedRouter([
            ModelResponse(text="I will write the report.", tool_calls=[_write_call()])
        ])
        orchestrator = _orchestrator(tmp_path, router)
        envelope = _envelope("Write the quarterly report to report.md")

        response = asyncio.run(orchestrator.ahandle(envelope))

        assert response.status == "needs_approval"
        assert response.approval is not None
        assert response.approval["resumable"] is True
        approval_id = str(response.approval["approval_id"])
        assert approval_id

        row = SQLiteStore(tmp_path).load_suspended_turn(approval_id)
        assert row is not None
        assert row["status"] == "suspended"
        assert row["turn_id"] == envelope.turn_id
        assert row["session_id"] == envelope.session_id
        assert row["call_id"] == "call_write"
        assert row["tool_name"] == "write_file"
        # The assistant message carrying the proposed call must be parked too —
        # a `tool` result is only valid against the call it answers.
        parked = deserialize_messages(str(row["messages_json"]))
        assert parked[-1].role == "assistant"
        assert parked[-1].tool_calls[0].call_id == "call_write"
        assert "turn_suspended_for_approval" in _event_types(orchestrator, envelope.session_id)

    def test_the_parked_conversation_never_enters_the_event_log(self, tmp_path: Path) -> None:
        router = ScriptedRouter([
            ModelResponse(text="Writing the secret plan now.", tool_calls=[_write_call()])
        ])
        orchestrator = _orchestrator(tmp_path, router)
        envelope = _envelope("Write the quarterly report")
        asyncio.run(orchestrator.ahandle(envelope))

        path = orchestrator.writer.path_for_session(envelope.session_id)
        suspended = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if json.loads(line)["event_type"] == "turn_suspended_for_approval"
        ]
        assert suspended
        payload = suspended[0]["payload"]
        # Counts and ids only. The transcript stays in the encrypted store, and
        # ADD-02's queue counters are counts too — never the queued arguments.
        assert set(payload) - {"client"} == {
            "approval_id", "tool_name", "suspended_messages", "tool_calls_made",
            "queue_position", "queue_total", "queued_calls",
        }
        assert "secret plan" not in json.dumps(suspended[0])
        assert "quarterly report" not in json.dumps(suspended[0])


# ── Resumption ───────────────────────────────────────────────────────────────


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def headers(workspace: Path) -> dict[str, str]:
    raw, _ = ApiSessionStore(workspace).create_session("principal_owner")
    return {"Authorization": f"Bearer {raw}"}


@pytest.fixture
def scripted_model(monkeypatch: pytest.MonkeyPatch) -> ScriptedRouter:
    """Script the model for the *whole app*, gateway included.

    The resume endpoints build their own `AgentGateway`, so patching the router
    class is what lets an end-to-end HTTP test drive the real wiring — routes,
    gateway, orchestrator, broker, store — with only the provider stubbed.
    """
    from raiker.models.router import ModelRouter

    script = ScriptedRouter([])

    async def _achat(
        self: Any,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
    ) -> ModelResponse:
        return script.chat(provider, model, messages, tools)

    async def _astream(
        self: Any,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
    ) -> AsyncIterator[Any]:
        from raiker.models.contracts import ModelStreamEvent

        response = script.chat(provider, model, messages, tools)
        if response.text:
            yield ModelStreamEvent(event_type="text_delta", text_delta=response.text)
        for call in response.tool_calls:
            yield ModelStreamEvent(
                event_type="tool_call_delta",
                tool_call_delta={
                    "call_id": call.call_id,
                    "tool_name": call.tool_name,
                    "arguments": call.arguments,
                },
            )
        yield ModelStreamEvent(event_type="finish", finish_reason=response.finish_reason)

    monkeypatch.setattr(ModelRouter, "achat", _achat, raising=False)
    monkeypatch.setattr(ModelRouter, "astream", _astream, raising=False)
    return script


def _park_turn(workspace: Path, router: ScriptedRouter) -> tuple[str, PromptEnvelope]:
    """Run a turn to the point where it parks for approval, and return the id."""
    store = SQLiteStore(workspace)
    writer = EventLogWriter(store)
    broker = ToolBroker(
        workspace_root=workspace,
        policy_engine=PolicyEngine(StaticPolicyConfig(workspace)),
        store=store,
        writer=writer,
        principal_id="principal_owner",
    )
    orchestrator = RuntimeOrchestrator(
        workspace_root=workspace,
        writer=writer,
        tool_broker=broker,
        model_router=router,  # type: ignore[arg-type]
    )
    envelope = _envelope("Write the quarterly report to report.md")
    store.create_session(envelope.session_id, str(workspace))
    with store.connect() as connection:
        connection.execute(
            "UPDATE sessions SET user_id = (SELECT user_id FROM principals WHERE principal_id = 'principal_owner') WHERE session_id = ?",
            (envelope.session_id,),
        )
    store.insert_turn(envelope.session_id, envelope.turn_id, envelope.prompt.text)
    response = asyncio.run(orchestrator.ahandle(envelope))
    assert response.approval is not None, response.message
    return str(response.approval["approval_id"]), envelope


class TestResumeAfterApproval:
    def test_approving_resumes_the_same_turn_with_the_real_result(
        self, workspace: Path, headers: dict[str, str], scripted_model: ScriptedRouter
    ) -> None:
        router = ScriptedRouter([
            ModelResponse(text="Writing it now.", tool_calls=[_write_call()]),
            ModelResponse(text="Done — report.md now contains the quarterly report."),
        ])
        scripted_model.responses = router.responses
        approval_id, envelope = _park_turn(workspace, scripted_model)
        client = TestClient(create_app(workspace))

        resolved = client.post(
            f"/api/approvals/{approval_id}/resolve",
            json={"approve": True, "reason": "ship it"},
            headers=headers,
        )
        assert resolved.status_code == 200, resolved.text
        body = resolved.json()
        assert body["executes_action"] is True
        assert body["resume"] == {
            "resumable": True,
            "session_id": envelope.session_id,
            "turn_id": envelope.turn_id,
            # ADD-02 — a single-call turn is a batch of one with nothing queued.
            "queue_position": 1,
            "queue_total": 1,
            "queued_calls": 0,
        }
        assert (workspace / "report.md").read_text(encoding="utf-8") == "# Report\n"

        resumed = client.post(f"/api/approvals/{approval_id}/resume", headers=headers)
        assert resumed.status_code == 200, resumed.text
        continuation = resumed.json()
        assert continuation["status"] == "completed"
        assert "report.md" in continuation["message"]
        # The *same* turn: one exchange in the transcript, not two.
        assert continuation["turn_id"] == envelope.turn_id
        assert continuation["session_id"] == envelope.session_id

        # The model saw the real outcome as the tool result for its own call.
        replayed = scripted_model.seen_messages[-1]
        tool_messages = [m for m in replayed if m.role == "tool"]
        assert tool_messages, replayed
        outcome = json.loads(tool_messages[-1].content)
        assert tool_messages[-1].tool_call_id == "call_write"
        assert outcome["status"] == "success"
        assert outcome["executed"] is True
        assert outcome["path"] == "report.md"

    def test_the_resumed_turn_keeps_the_original_working_state(
        self, workspace: Path, headers: dict[str, str], scripted_model: ScriptedRouter
    ) -> None:
        # The whole point of B2: the continuation is not a fresh prompt, so the
        # model still has everything it had built up before the approval.
        router = ScriptedRouter([
            ModelResponse(text="Writing it now.", tool_calls=[_write_call()]),
            ModelResponse(text="Done."),
        ])
        scripted_model.responses = router.responses
        approval_id, _envelope = _park_turn(workspace, scripted_model)
        client = TestClient(create_app(workspace))
        client.post(
            f"/api/approvals/{approval_id}/resolve",
            json={"approve": True, "reason": "ok"},
            headers=headers,
        )
        client.post(f"/api/approvals/{approval_id}/resume", headers=headers)

        first_call, resumed_call = scripted_model.seen_messages[0], scripted_model.seen_messages[-1]
        # Everything the model had on the first call is still in front of it,
        # plus its own tool call and the result.
        assert [m.content for m in first_call] == [
            m.content for m in resumed_call[: len(first_call)]
        ]
        assert resumed_call[len(first_call)].role == "assistant"
        assert resumed_call[len(first_call)].tool_calls[0].call_id == "call_write"
        assert resumed_call[-1].role == "tool"

    def test_rejecting_resumes_with_a_refusal_the_model_can_react_to(
        self, workspace: Path, headers: dict[str, str], scripted_model: ScriptedRouter
    ) -> None:
        router = ScriptedRouter([
            ModelResponse(text="Writing it now.", tool_calls=[_write_call()]),
            ModelResponse(text="Understood — I have not written the file."),
        ])
        scripted_model.responses = router.responses
        approval_id, _envelope = _park_turn(workspace, scripted_model)
        client = TestClient(create_app(workspace))

        resolved = client.post(
            f"/api/approvals/{approval_id}/resolve",
            json={"approve": False, "reason": "not now"},
            headers=headers,
        )
        assert resolved.status_code == 200
        assert resolved.json()["resume"]["resumable"] is True

        resumed = client.post(f"/api/approvals/{approval_id}/resume", headers=headers)
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["status"] == "completed"
        assert not (workspace / "report.md").exists()

        outcome = json.loads(
            [m for m in scripted_model.seen_messages[-1] if m.role == "tool"][-1].content
        )
        assert outcome["status"] == "rejected"
        assert outcome["executed"] is False
        assert "rejected" in outcome["note"].lower()

    def test_a_resumed_turn_can_itself_park_again(
        self, workspace: Path, headers: dict[str, str], scripted_model: ScriptedRouter
    ) -> None:
        # A real agent proposes more than one write. The second proposal must
        # park exactly like the first, against its own approval.
        second = ToolCallProposal(
            call_id="call_write_2",
            tool_name="write_file",
            arguments={"path": "summary.md", "text": "summary\n"},
        )
        router = ScriptedRouter([
            ModelResponse(text="First file.", tool_calls=[_write_call()]),
            ModelResponse(text="Now the summary.", tool_calls=[second]),
        ])
        scripted_model.responses = router.responses
        approval_id, envelope = _park_turn(workspace, scripted_model)
        client = TestClient(create_app(workspace))
        client.post(
            f"/api/approvals/{approval_id}/resolve",
            json={"approve": True, "reason": "ok"},
            headers=headers,
        )
        resumed = client.post(f"/api/approvals/{approval_id}/resume", headers=headers)

        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["status"] == "needs_approval"
        store = SQLiteStore(workspace)
        parked = [
            row
            for row in _all_suspended(store)
            if row["approval_id"] != approval_id and row["status"] == "suspended"
        ]
        assert len(parked) == 1
        assert parked[0]["call_id"] == "call_write_2"
        assert parked[0]["turn_id"] == envelope.turn_id


def _all_suspended(store: SQLiteStore) -> list[dict[str, Any]]:
    with store.connect() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM suspended_turns")]


class TestResumeBoundaries:
    def test_resuming_before_the_approval_is_resolved_is_refused(
        self, workspace: Path, headers: dict[str, str], scripted_model: ScriptedRouter
    ) -> None:
        router = ScriptedRouter([
            ModelResponse(text="Writing it now.", tool_calls=[_write_call()])
        ])
        scripted_model.responses = router.responses
        approval_id, _envelope = _park_turn(workspace, scripted_model)
        client = TestClient(create_app(workspace))

        resumed = client.post(f"/api/approvals/{approval_id}/resume", headers=headers)
        assert resumed.status_code == 409
        assert resumed.json()["detail"]["reason_code"] == "approval_not_resolved"

    def test_a_turn_resumes_at_most_once(
        self, workspace: Path, headers: dict[str, str], scripted_model: ScriptedRouter
    ) -> None:
        # Replaying a parked turn would re-send the whole conversation and let
        # the model act twice on one decision.
        router = ScriptedRouter([
            ModelResponse(text="Writing it now.", tool_calls=[_write_call()]),
            ModelResponse(text="Done."),
        ])
        scripted_model.responses = router.responses
        approval_id, _envelope = _park_turn(workspace, scripted_model)
        client = TestClient(create_app(workspace))
        client.post(
            f"/api/approvals/{approval_id}/resolve",
            json={"approve": True, "reason": "ok"},
            headers=headers,
        )
        assert client.post(f"/api/approvals/{approval_id}/resume", headers=headers).status_code == 200

        replay = client.post(f"/api/approvals/{approval_id}/resume", headers=headers)
        assert replay.status_code == 409
        assert replay.json()["detail"]["reason_code"] == "suspended_turn_already_resumed"

    def test_an_unknown_approval_has_nothing_to_resume(
        self, workspace: Path, headers: dict[str, str], scripted_model: ScriptedRouter
    ) -> None:
        client = TestClient(create_app(workspace))
        resumed = client.post("/api/approvals/appr_nope/resume", headers=headers)
        assert resumed.status_code == 404
        assert resumed.json()["detail"]["reason_code"] == "suspended_turn_not_found"

    def test_resume_requires_authentication(self, workspace: Path) -> None:
        client = TestClient(create_app(workspace))
        assert client.post("/api/approvals/appr_1/resume").status_code == 401
        assert client.post("/api/approvals/appr_1/resume/stream").status_code == 401

    def test_an_approval_with_no_parked_turn_reports_it_honestly(
        self, workspace: Path, headers: dict[str, str], scripted_model: ScriptedRouter
    ) -> None:
        # A CLI-proposed or connector-store approval has no chat turn behind it.
        from raiker.contracts.models import ToolAction

        store = SQLiteStore(workspace)
        store.create_session("sess_x", str(workspace))
        action = ToolAction(
            action_id="act_x",
            tool_name="write_file",
            arguments={"path": "x.md", "text": "x"},
            risk_level="high",
            requires_approval=True,
        )
        store.insert_tool_action(action, session_id="sess_x", turn_id="turn_x", status="approval_required")
        store.insert_approval("appr_x", action)

        client = TestClient(create_app(workspace))
        resolved = client.post(
            "/api/approvals/appr_x/resolve",
            json={"approve": True, "reason": "ok"},
            headers=headers,
        )
        assert resolved.status_code == 200
        assert resolved.json()["resume"] == {"resumable": False}


class TestStreamingResume:
    def test_the_continuation_streams_like_an_ordinary_turn(
        self, workspace: Path, headers: dict[str, str], scripted_model: ScriptedRouter
    ) -> None:
        router = ScriptedRouter([
            ModelResponse(text="Writing it now.", tool_calls=[_write_call()]),
            ModelResponse(text="Done — the report is written."),
        ])
        scripted_model.responses = router.responses
        approval_id, _envelope = _park_turn(workspace, scripted_model)
        client = TestClient(create_app(workspace))
        client.post(
            f"/api/approvals/{approval_id}/resolve",
            json={"approve": True, "reason": "ok"},
            headers=headers,
        )

        with client.stream(
            "POST", f"/api/approvals/{approval_id}/resume/stream", headers=headers
        ) as stream:
            assert stream.status_code == 200
            payloads = [
                json.loads(line[len("data: ") :])
                for line in stream.iter_lines()
                if line.startswith("data: ")
            ]
        assert payloads
        finals = [p for p in payloads if p["kind"] == "final"]
        assert finals and finals[-1]["response"]["status"] == "completed"


# ── Pure data: serialisation and the outcome the model sees ──────────────────


class TestSuspensionData:
    def test_a_malformed_parked_conversation_fails_closed(self) -> None:
        for broken in ("not json", "{}", "[]", '[{"role": "nonsense", "content": ""}]'):
            with pytest.raises(TurnSuspensionError):
                deserialize_messages(broken)

    def test_an_oversized_conversation_is_refused_rather_than_stored(self) -> None:
        from raiker.runtime.turn_suspension import MAX_SUSPENDED_MESSAGES_BYTES

        huge = [ModelMessage(role="user", content="x" * (MAX_SUSPENDED_MESSAGES_BYTES + 1))]
        with pytest.raises(TurnSuspensionError, match="suspended_turn_too_large"):
            serialize_messages(huge)

    def test_the_three_outcomes_are_distinguishable(self) -> None:
        rejected = approval_outcome(approved=False, executed=False)
        executed = approval_outcome(
            approved=True, executed=True, capability="file_write_execution",
            artifacts={"path": "a.md"},
        )
        recorded = approval_outcome(
            approved=True, executed=False, capability="shell_execution"
        )
        assert rejected["status"] == "rejected"
        assert executed["status"] == "success" and executed["path"] == "a.md"
        # Approved-but-not-executed must never look like success, or the model
        # will report an effect that never happened.
        assert recorded["status"] == "not_executed"
        assert recorded["executed"] is False
        assert len({rejected["status"], executed["status"], recorded["status"]}) == 3
