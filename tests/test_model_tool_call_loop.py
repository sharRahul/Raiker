from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

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
    # `AgentGateway` records the turn before dispatching (`sessions.track_turn`),
    # and this harness drives the orchestrator directly. Recording it here keeps
    # the harness faithful to the one path a real surface takes — BUG-218's
    # alignment check reads the turn's prompt, and a harness that never wrote one
    # would be testing a state no owner can reach.
    store = orchestrator.tool_broker.store
    if store is not None:
        store.create_session(envelope.session_id, str(orchestrator.workspace_root))
        store.insert_turn(envelope.session_id, envelope.turn_id, envelope.prompt.text)
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


def _event_record(orchestrator: RuntimeOrchestrator, session_id: str, event_type: str) -> dict[str, Any]:
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


def test_auto_withholds_a_write_to_an_existing_file_the_turn_never_looked_at(
    tmp_path: Path,
) -> None:
    """BUG-218 — Auto's alignment check, end to end through the broker.

    The exact reproduction the defect entry gives: every write capability
    permitted, Auto selected, and a change to a file unrelated to the request.
    It used to run. It now falls back to the ordinary approval queue, and the
    approval says which path did not match.
    """
    (tmp_path / "deploy.sh").write_text("#!/bin/sh\nreal deployment\n", encoding="utf-8")
    unrelated = ToolCallProposal(
        call_id="call_write",
        tool_name="write_file",
        arguments={"path": "deploy.sh", "text": "rm -rf /"},
    )
    router = FakeRouter(
        [ModelResponse(text="", tool_calls=[unrelated], finish_reason="tool_calls")]
    )
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("write the report", approval_mode="auto")

    response = _handle(orchestrator, envelope)

    assert response.status == "needs_approval"
    # The file the owner never mentioned is untouched.
    assert (tmp_path / "deploy.sh").read_text(encoding="utf-8") == "#!/bin/sh\nreal deployment\n"

    events = _events(orchestrator, envelope.session_id)
    assert "approval_auto_executed" not in events
    assert "approval_auto_withheld" in events
    assert "approval_requested" in events

    withheld = _event_record(orchestrator, envelope.session_id, "approval_auto_withheld")
    alignment = withheld["payload"]["alignment"]  # type: ignore[index]
    assert alignment["aligned"] is False
    assert alignment["target"] == "deploy.sh"

    # And the evidence travels onto the approval the owner is shown, so they are
    # answering a stated question rather than an unexplained interruption.
    requested = _event_record(orchestrator, envelope.session_id, "approval_requested")
    assert requested["payload"]["alignment"]["target"] == "deploy.sh"  # type: ignore[index]


def test_auto_still_executes_a_write_the_turn_established(tmp_path: Path) -> None:
    """The check must not turn Auto into Manual for the work that was asked for."""
    (tmp_path / "report.md").write_text("old", encoding="utf-8")
    router = FakeRouter(
        [
            ModelResponse(text="", tool_calls=[_write_call()], finish_reason="tool_calls"),
            ModelResponse(text="Done.", finish_reason="stop"),
        ]
    )
    orchestrator = _orchestrator(tmp_path, router)
    # The owner named the file, so an existing `report.md` is established.
    envelope = _envelope("rewrite report.md", approval_mode="auto")

    response = _handle(orchestrator, envelope)

    assert response.status == "completed"
    assert (tmp_path / "report.md").read_text(encoding="utf-8") == "# Report\n"
    events = _events(orchestrator, envelope.session_id)
    assert "approval_auto_executed" in events
    assert "approval_auto_withheld" not in events


def test_skip_is_deliberately_not_alignment_checked(tmp_path: Path) -> None:
    """Skip says no approval is raised at all, and that stays true.

    Attaching a silent second check to Skip would redefine a mode whose entire
    point is not to interrupt. Auto is the mode that promises a review.
    """
    (tmp_path / "deploy.sh").write_text("real deployment\n", encoding="utf-8")
    unrelated = ToolCallProposal(
        call_id="call_write",
        tool_name="write_file",
        arguments={"path": "deploy.sh", "text": "changed"},
    )
    router = FakeRouter(
        [
            ModelResponse(text="", tool_calls=[unrelated], finish_reason="tool_calls"),
            ModelResponse(text="Done.", finish_reason="stop"),
        ]
    )
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("write the report", approval_mode="skip")

    response = _handle(orchestrator, envelope)

    assert response.status == "completed"
    events = _events(orchestrator, envelope.session_id)
    assert "approval_auto_withheld" not in events
    assert "approval_preview_skipped" in events


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


# ── BUG-219: the unattended posture ──────────────────────────────────────────
#
# `dont_ask` is for a run with nobody watching: a scheduled routine at 06:00
# cannot answer a prompt, and parking on one is not the same as declining. Three
# properties, and each is a test.


def test_dont_ask_declines_what_would_have_needed_approval(tmp_path: Path) -> None:
    router = FakeRouter(
        [
            ModelResponse(text="", tool_calls=[_write_call()], finish_reason="tool_calls"),
            ModelResponse(text="I could not do that.", finish_reason="stop"),
        ]
    )
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("write the report", approval_mode="dont_ask")

    response = _handle(orchestrator, envelope)

    # Declined, not queued — and nothing was written.
    assert not (tmp_path / "report.md").exists()
    events = _events(orchestrator, envelope.session_id)
    assert "approval_requested" not in events
    assert "tool_started" not in events
    assert response.status in {"completed", "denied"}


def test_the_refusal_says_it_was_because_nobody_was_there_to_ask(tmp_path: Path) -> None:
    router = FakeRouter(
        [ModelResponse(text="", tool_calls=[_write_call()], finish_reason="tool_calls")]
    )
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("write the report", approval_mode="dont_ask")

    _handle(orchestrator, envelope)

    # "The owner refused this" and "nobody was there to ask" call for different
    # follow-ups, and only the second means re-running attended would work. The
    # audit record has to tell them apart.
    decision = _event_record(orchestrator, envelope.session_id, "policy_decision")
    assert decision["payload"]["decision"] == "deny"  # type: ignore[index]
    assert "denied_no_one_to_ask" in decision["payload"]["reasons"]  # type: ignore[index]


def test_dont_ask_never_widens_a_gate(tmp_path: Path) -> None:
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
    envelope = _envelope("read outside", approval_mode="dont_ask")

    response = _handle(orchestrator, envelope)

    # A refusal posture can only ever refuse more, never less: an action policy
    # already denied stays denied for policy's own reason, not this one.
    assert response.status == "denied"
    decision = _event_record(orchestrator, envelope.session_id, "policy_decision")
    assert "denied_no_one_to_ask" not in decision["payload"]["reasons"]  # type: ignore[index]
    assert "tool_started" not in _events(orchestrator, envelope.session_id)


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
