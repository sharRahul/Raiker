from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from raiker.contracts.ids import new_id
from raiker.contracts.models import (
    DEFAULT_MAX_TOOL_CALLS,
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
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker


class FakeRouter:
    """Deterministic model whose tool calls are scripted, to exercise the runtime loop."""

    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = responses
        self.calls = 0

    def chat(
        self,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
    ) -> ModelResponse:
        index = min(self.calls, len(self.responses) - 1)
        self.calls += 1
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


def _envelope(prompt: str, *, max_tool_calls: int = 10) -> PromptEnvelope:
    return PromptEnvelope(
        request_id=new_id("req_"),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        client=ClientMetadata(type="test_harness", name="tests", version="0.0.0"),
        user=UserMetadata(),
        prompt=PromptPayload(text=prompt),
        options=PromptOptions(max_tool_calls=max_tool_calls),
    )


def _events(orchestrator: RuntimeOrchestrator, session_id: str) -> list[str]:
    path = orchestrator.writer.path_for_session(session_id)
    return [json.loads(line)["event_type"] for line in path.read_text(encoding="utf-8").splitlines()]


def _list_dir_call() -> ToolCallProposal:
    return ToolCallProposal(call_id="call_ls", tool_name="list_directory", arguments={"path": "."})


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
    response = orchestrator.handle(envelope)
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
    response = orchestrator.handle(envelope)
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
    orchestrator.handle(envelope)
    events = _events(orchestrator, envelope.session_id)
    assert events.count("tool_completed") == 2


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
    response = orchestrator.handle(envelope)
    events = _events(orchestrator, envelope.session_id)
    assert response.status == "needs_approval"
    assert "approval_requested" in events
    assert "tool_started" not in events


def test_outside_workspace_read_is_denied(tmp_path: Path) -> None:
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
    envelope = _envelope("read outside")
    response = orchestrator.handle(envelope)
    events = _events(orchestrator, envelope.session_id)
    assert response.status == "denied"
    assert "policy_decision" in events
    assert "tool_started" not in events
