from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.contracts.models import (
    DEFAULT_MAX_TOOL_CALLS,
    AgentResponse,
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
from raiker.runtime.identity.lifecycle import TurnMachineIdentityLifecycle
from raiker.runtime.orchestrator import RuntimeOrchestrator
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker


class FakeRouter:
    """Deterministic model whose tool calls are scripted, to exercise the runtime loop."""

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


def _orchestrator(tmp_path: Path, router: FakeRouter) -> RuntimeOrchestrator:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    writer = EventLogWriter(store)
    broker = ToolBroker(
        workspace_root=tmp_path,
        policy_engine=PolicyEngine(StaticPolicyConfig(tmp_path)),
        store=store,
        writer=writer,
        principal_id="principal_owner",
    )
    return RuntimeOrchestrator(
        workspace_root=tmp_path,
        writer=writer,
        tool_broker=broker,
        model_router=router,  # type: ignore[arg-type]
    )


def _handle(
    orchestrator: RuntimeOrchestrator, envelope: PromptEnvelope
) -> AgentResponse:
    identity = TurnMachineIdentityLifecycle(
        orchestrator.workspace_root,
        orchestrator.tool_broker.store,
        orchestrator.writer,
    ).start(
        owner_principal_id="principal_owner",
        session_id=envelope.session_id,
        turn_id=envelope.turn_id,
        role_ids=("assistant",),
    )
    return orchestrator.handle(envelope, identity=identity)


def _envelope(
    prompt: str, *, max_tool_calls: int = 10, approval_mode: str = "manual"
) -> PromptEnvelope:
    return PromptEnvelope(
        request_id=new_id("req_"),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        client=ClientMetadata(type="test_harness", name="tests", version="0.0.0"),
        user=UserMetadata(),
        prompt=PromptPayload(text=prompt),
        options=PromptOptions(max_tool_calls=max_tool_calls, approval_mode=approval_mode),
    )


def _events(orchestrator: RuntimeOrchestrator, session_id: str) -> list[str]:
    path = orchestrator.writer.path_for_session(session_id)
    return [json.loads(line)["event_type"] for line in path.read_text(encoding="utf-8").splitlines()]


def _event_record(orchestrator: RuntimeOrchestrator, session_id: str, event_type: str) -> dict[str, object]:
    path = orchestrator.writer.path_for_session(session_id)
    return next(
        record
        for record in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
        if record["event_type"] == event_type
    )


def _list_dir_call() -> ToolCallProposal:
    return ToolCallProposal(call_id="call_ls", tool_name="list_directory", arguments={"path": "."})


def _write_call() -> ToolCallProposal:
    return ToolCallProposal(
        call_id="call_write",
        tool_name="write_file",
        arguments={"path": "report.md", "text": "# Report\n"},
    )


def test_model_drives_a_tool_call_then_responds(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hi", encoding="utf-8")
    router = FakeRouter(
        [
            ModelResponse(text="", tool_calls=[_list_dir_call()], finish_reason="tool_calls"),
            ModelResponse(text="Here are the files.", finish_reason="stop"),
        ]
    )
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("list files in this project")
    response = _handle(orchestrator, envelope)
    assert response.status == "completed"
    assert response.message == "Here are the files."
    events = _events(orchestrator, envelope.session_id)
    for expected in [
        "model_request_started",
        "action_proposed",
        "policy_decision",
        "tool_started",
        "tool_completed",
        "verification_completed",
        "model_request_completed",
        "response_created",
    ]:
        assert expected in events


def test_model_executes_every_parallel_read_and_returns_every_result(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "b.txt").write_text("beta", encoding="utf-8")
    calls = [
        ToolCallProposal("call_a", "read_file", {"path": "a.txt"}),
        ToolCallProposal("call_b", "read_file", {"path": "b.txt"}),
    ]
    router = FakeRouter([
        ModelResponse(text="Reading both.", tool_calls=calls, finish_reason="tool_calls"),
        ModelResponse(text="Compared both files.", finish_reason="stop"),
    ])
    orchestrator = _orchestrator(tmp_path, router)
    response = _handle(orchestrator, _envelope("compare a and b"))
    assert response.message == "Compared both files."
    follow_up = router.seen_messages[1]
    assistant = next(message for message in follow_up if message.role == "assistant" and message.tool_calls)
    assert [call.call_id for call in assistant.tool_calls] == ["call_a", "call_b"]
    assert [message.tool_call_id for message in follow_up if message.role == "tool"] == ["call_a", "call_b"]
    assert _events(orchestrator, response.session_id).count("tool_completed") == 2


def test_runtime_discloses_a_tool_level_withholding_without_relying_on_model_copy(
    tmp_path: Path,
) -> None:
    """BUG-60: an allowed call that a capability gate withholds is runtime UI state."""
    router = FakeRouter([
        ModelResponse(text="", tool_calls=[_list_dir_call()], finish_reason="tool_calls"),
        ModelResponse(text="The model may narrate this, but is not the disclosure.", finish_reason="stop"),
    ])
    orchestrator = _orchestrator(tmp_path, router)
    orchestrator.tool_broker.executors["list_directory"] = lambda _args: {
        "status": "denied",
        "error": {
            "type": "capability_disabled",
            "message": "Accès withheld — enable the permission.",
            "remediation_route": "capabilities",
        },
    }
    envelope = _envelope("list files")

    response = _handle(orchestrator, envelope)

    assert response.status == "failed", response
    event = _event_record(orchestrator, envelope.session_id, "model_tool_call_refused")
    assert {key: event["payload"][key] for key in (
        "tool_name", "reasons", "disclosed_by", "refusal_source", "remediation_route"
    )} == {
        "tool_name": "list_directory",
        "reasons": ["capability_disabled"],
        "disclosed_by": "runtime",
        "refusal_source": "tool",
        "remediation_route": "capabilities",
    }
    tool_message = next(message for message in router.seen_messages[1] if message.role == "tool")
    assert "Accès withheld — enable the permission." in tool_message.content


def test_unknown_tool_call_is_rejected(tmp_path: Path) -> None:
    router = FakeRouter(
        [
            ModelResponse(
                text="",
                tool_calls=[ToolCallProposal("call_x", "definitely_not_a_tool", {})],
                finish_reason="tool_calls",
            )
        ]
    )
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("do something")
    response = _handle(orchestrator, envelope)
    events = _events(orchestrator, envelope.session_id)
    assert "model_tool_call_rejected" in events
    assert "tool_started" not in events
    assert response.status == "completed"


def test_default_tool_call_budget_is_effectively_unbounded() -> None:
    # The default is a runaway-loop fail-safe, not a working limit: a turn
    # should end because the model finishes (or the provider's context/token
    # budget runs out), never because of the default counter.
    assert PromptOptions().max_tool_calls == DEFAULT_MAX_TOOL_CALLS
    assert DEFAULT_MAX_TOOL_CALLS >= 10_000


def test_tool_call_budget_is_enforced(tmp_path: Path) -> None:
    router = FakeRouter(
        [ModelResponse(text="", tool_calls=[_list_dir_call()], finish_reason="tool_calls")]
    )
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("loop", max_tool_calls=2)
    _handle(orchestrator, envelope)
    events = _events(orchestrator, envelope.session_id)
    assert events.count("tool_completed") == 2


def test_tool_round_trip_carries_assistant_tool_call_message(tmp_path: Path) -> None:
    """A valid tool round-trip on both wire protocols: the follow-up model call
    must contain the assistant message that made the tool call (Anthropic
    tool_use / OpenAI tool_calls) followed by the matching tool result —
    hosted providers reject a tool result with no preceding tool call."""
    (tmp_path / "README.md").write_text("hi", encoding="utf-8")
    router = FakeRouter(
        [
            ModelResponse(text="Listing…", tool_calls=[_list_dir_call()], finish_reason="tool_calls"),
            ModelResponse(text="Done.", finish_reason="stop"),
        ]
    )
    orchestrator = _orchestrator(tmp_path, router)
    _handle(orchestrator, _envelope("list files"))
    assert len(router.seen_messages) == 2
    follow_up = router.seen_messages[1]
    assistant = [m for m in follow_up if m.role == "assistant" and m.tool_calls]
    assert len(assistant) == 1
    assert assistant[0].tool_calls[0].call_id == "call_ls"
    tool_msgs = [m for m in follow_up if m.role == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0].tool_call_id == "call_ls"
    # The assistant message must come before its tool result.
    assert follow_up.index(assistant[0]) < follow_up.index(tool_msgs[0])


def test_assistant_tool_calls_serialize_for_both_protocols() -> None:
    from raiker.models.providers.anthropic_messages import _to_anthropic_messages

    assistant = ModelMessage(role="assistant", content="Listing…", tool_calls=(_list_dir_call(),))
    tool = ModelMessage(role="tool", content="{}", tool_call_id="call_ls", name="list_directory")

    # OpenAI shape: tool_calls field with JSON-encoded arguments.
    serialized = assistant.to_dict()
    assert serialized["tool_calls"][0]["id"] == "call_ls"
    assert serialized["tool_calls"][0]["function"]["name"] == "list_directory"

    # Anthropic shape: assistant tool_use block whose id matches the tool_result.
    _, converted = _to_anthropic_messages([assistant, tool])
    assert converted[0]["role"] == "assistant"
    tool_use = [b for b in converted[0]["content"] if b["type"] == "tool_use"]
    assert tool_use and tool_use[0]["id"] == "call_ls"
    assert converted[1]["role"] == "user"
    assert converted[1]["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "call_ls",
        "content": "{}",
    }


def test_model_proposed_shell_requires_approval(tmp_path: Path) -> None:
    router = FakeRouter(
        [
            ModelResponse(
                text="",
                tool_calls=[ToolCallProposal("call_sh", "shell", {"command": "pytest"})],
                finish_reason="tool_calls",
            )
        ]
    )
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("run the tests")
    response = _handle(orchestrator, envelope)
    events = _events(orchestrator, envelope.session_id)
    assert response.status == "needs_approval"
    assert "approval_requested" in events
    assert "tool_started" not in events


def test_auto_approval_executes_an_ordinary_file_write_with_preview_evidence(tmp_path: Path) -> None:
    router = FakeRouter(
        [
            ModelResponse(text="", tool_calls=[_write_call()], finish_reason="tool_calls"),
            ModelResponse(text="Done.", finish_reason="stop"),
        ]
    )
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("write the report", approval_mode="auto")

    response = _handle(orchestrator, envelope)

    assert response.status == "completed"
    assert (tmp_path / "report.md").read_text(encoding="utf-8") == "# Report\n"
    events = _events(orchestrator, envelope.session_id)
    assert "approval_requested" not in events
    assert "approval_auto_executed" in events
    auto_event = _event_record(orchestrator, envelope.session_id, "approval_auto_executed")
    assert auto_event["payload"]["proposal_preview"]["status"] == "proposal"  # type: ignore[index]
    assert orchestrator.tool_broker.store is not None
    with orchestrator.tool_broker.store.connect() as connection:
        stored_actor = connection.execute(
            "SELECT proposed_by FROM tool_actions WHERE session_id = ? ORDER BY proposed_at DESC LIMIT 1",
            (envelope.session_id,),
        ).fetchone()
    assert stored_actor is not None
    assert str(stored_actor["proposed_by"]).startswith("principal_turn_agent_")
    executed = _event_record(orchestrator, envelope.session_id, "action_executed")
    assert executed["payload"]["posture"]["principal_id"] == stored_actor["proposed_by"]  # type: ignore[index]


def test_skip_approval_executes_an_ordinary_file_write_without_preview(tmp_path: Path) -> None:
    router = FakeRouter(
        [
            ModelResponse(text="", tool_calls=[_write_call()], finish_reason="tool_calls"),
            ModelResponse(text="Done.", finish_reason="stop"),
        ]
    )
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("write the report", approval_mode="skip")

    response = _handle(orchestrator, envelope)

    assert response.status == "completed"
    assert (tmp_path / "report.md").read_text(encoding="utf-8") == "# Report\n"
    events = _events(orchestrator, envelope.session_id)
    assert "approval_requested" not in events
    assert "approval_preview_skipped" in events
    skip_event = _event_record(orchestrator, envelope.session_id, "approval_preview_skipped")
    assert "proposal_preview" not in skip_event["payload"]  # type: ignore[operator]


def test_outside_workspace_read_is_denied_even_when_approvals_are_skipped(tmp_path: Path) -> None:
    router = FakeRouter(
        [
            ModelResponse(
                text="",
                tool_calls=[ToolCallProposal("call_r", "read_file", {"path": "../secret.txt"})],
                finish_reason="tool_calls",
            )
        ]
    )
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("read outside", approval_mode="skip")
    response = _handle(orchestrator, envelope)
    events = _events(orchestrator, envelope.session_id)
    assert response.status == "denied"
    assert "policy_decision" in events
    assert "tool_started" not in events
