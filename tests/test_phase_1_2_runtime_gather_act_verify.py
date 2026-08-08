from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from raiker.cli.commands import (
    handle_approvals,
    handle_checkpoints,
    handle_events,
    handle_status,
)
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
from raiker.storage.sqlite import SQLiteStore
from tests.machine_identity_helpers import IdentityBoundTestBroker as ToolBroker


class FakeRouter:
    def __init__(self, responses: list[ModelResponse]) -> None:
        self.responses = responses
        self.calls = 0

    async def achat(
        self,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
    ) -> ModelResponse:
        index = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        return self.responses[index]


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


def _envelope(prompt: str) -> PromptEnvelope:
    return PromptEnvelope(
        request_id=new_id("req_"),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        client=ClientMetadata(type="test_harness", name="tests", version="0.0.0"),
        user=UserMetadata(),
        prompt=PromptPayload(text=prompt),
        options=PromptOptions(max_tool_calls=5),
    )


def _events(orchestrator: RuntimeOrchestrator, session_id: str) -> list[dict]:
    path = orchestrator.writer.path_for_session(session_id)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _payload(events: list[dict], event_type: str) -> dict:
    return next(e["payload"] for e in events if e["event_type"] == event_type)


def test_runtime_emits_context_gathering_metadata(tmp_path: Path) -> None:
    router = FakeRouter([ModelResponse(text="hello", finish_reason="stop")])
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("say hi")
    orchestrator.handle(envelope)
    events = _events(orchestrator, envelope.session_id)
    payload = _payload(events, "context_gathered")
    assert "context_bundle_id" in payload
    assert payload["item_count"] >= 1
    assert payload["included_count"] >= 1


def test_context_source_list_is_more_than_current_prompt(tmp_path: Path) -> None:
    router = FakeRouter([ModelResponse(text="hello", finish_reason="stop")])
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("say hi")
    orchestrator.handle(envelope)
    payload = _payload(_events(orchestrator, envelope.session_id), "context_gathered")
    source_types = payload["source_types"]
    assert source_types != ["current_prompt"]
    assert "current_prompt" in source_types
    assert "workspace_summary" in source_types
    assert "capability_status" in source_types


def test_verification_event_is_emitted_for_tool_turn(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hi", encoding="utf-8")
    router = FakeRouter(
        [
            ModelResponse(
                text="",
                tool_calls=[ToolCallProposal("call_ls", "list_directory", {"path": "."})],
                finish_reason="tool_calls",
            ),
            ModelResponse(text="done", finish_reason="stop"),
        ]
    )
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("list files")
    response = orchestrator.handle(envelope)
    assert response.status == "completed"
    types = [e["event_type"] for e in _events(orchestrator, envelope.session_id)]
    assert "verification_started" in types
    assert "verification_completed" in types
    payload = _payload(_events(orchestrator, envelope.session_id), "verification_completed")
    assert payload["overall_status"] == "passed"
    assert payload["safe_to_continue"] is True


def test_denied_tool_action_does_not_execute_and_is_verified(tmp_path: Path) -> None:
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
    assert response.status == "denied"
    types = [e["event_type"] for e in _events(orchestrator, envelope.session_id)]
    assert "tool_started" not in types
    assert "verification_completed" in types
    payload = _payload(_events(orchestrator, envelope.session_id), "verification_completed")
    assert payload["safe_to_continue"] is True


def test_approval_required_action_stops_before_execution(tmp_path: Path) -> None:
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
    envelope = _envelope("run tests")
    response = orchestrator.handle(envelope)
    assert response.status == "needs_approval"
    types = [e["event_type"] for e in _events(orchestrator, envelope.session_id)]
    assert "tool_started" not in types
    assert "verification_completed" in types


def test_existing_terminal_commands_still_work(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    SQLiteStore(tmp_path)
    status = handle_status(workspace_root=tmp_path)
    assert "runtime_execution_enabled: False" in status
    # These should not raise and should return strings.
    assert isinstance(handle_events(workspace_root=tmp_path), str)
    assert isinstance(handle_checkpoints(workspace_root=tmp_path), str)
    assert isinstance(handle_approvals(workspace_root=tmp_path), str)


def test_capability_gates_report_disabled_until_an_owner_enables_one(tmp_path: Path) -> None:
    from raiker.context.gatherer import CAPABILITY_GATE_TOOLS, ContextGatherer

    bundle = ContextGatherer().gather(
        workspace_root=tmp_path,
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        prompt_text="x",
    )
    caps = [i for i in bundle.included_items if i.source.source_type == "capability_status"][0]
    for capability in CAPABILITY_GATE_TOOLS:
        assert caps.metadata[capability]["enabled"] is False  # type: ignore[index]
