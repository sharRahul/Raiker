"""The Build workspace's operating protocol reaches the model, and only there.

`docs/RAIKER_BUILD_PROCESS.md` is the source of the protocol a Build turn runs
under. Two properties are worth guarding, because both are silent when they
break:

1. A Build turn really receives it. A protocol that lives only in a document is
   a protocol the model never sees.
2. A Chat turn does not. Answering a one-line question with a pre-mortem is its
   own failure, and the protocol says so.

The third property is the one that matters for governance: the surface selects
a working method and never authority. That is asserted against the envelope in
`tests/test_api_prompts.py`; here it is asserted where it would actually leak —
the tool specs offered to the model must be identical on both surfaces.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

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
from raiker.models.contracts import ModelMessage, ModelResponse, ToolSpec
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.identity.lifecycle import TurnMachineIdentityLifecycle
from raiker.runtime.orchestrator import (
    _BUILD_PROCESS_PROMPT,
    _SYSTEM_PROMPT,
    RuntimeOrchestrator,
    _system_messages,
)
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker


class RecordingRouter:
    """A model that answers immediately and keeps what it was asked."""

    def __init__(self) -> None:
        self.seen_messages: list[list[ModelMessage]] = []
        self.seen_tools: list[list[str]] = []

    def chat(
        self,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
    ) -> ModelResponse:
        self.seen_messages.append(list(messages))
        self.seen_tools.append(sorted(spec.name for spec in (tools or ())))
        return ModelResponse(text="Done.", finish_reason="stop")

    async def achat(
        self,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
    ) -> ModelResponse:
        return self.chat(provider, model, messages, tools)


def _orchestrator(tmp_path: Path, router: RecordingRouter) -> RuntimeOrchestrator:
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


def _envelope(surface: str) -> PromptEnvelope:
    return PromptEnvelope(
        request_id=new_id("req_"),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        client=ClientMetadata(type="test_harness", name="tests", version="0.0.0"),
        user=UserMetadata(),
        prompt=PromptPayload(text="Rename the config key.", metadata={"surface": surface}),
        options=PromptOptions(max_tool_calls=4, approval_mode="manual"),
    )


def _handle(orchestrator: RuntimeOrchestrator, envelope: PromptEnvelope) -> None:
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
    orchestrator.handle(envelope, identity=identity)


def _system_text(messages: list[ModelMessage]) -> str:
    return "\n".join(message.content for message in messages if message.role == "system")


def test_system_messages_selects_the_protocol_by_surface() -> None:
    assert _system_messages("build") == [_SYSTEM_PROMPT, _BUILD_PROCESS_PROMPT]
    assert _system_messages("chat") == [_SYSTEM_PROMPT]
    # An unrecognised surface must not be read as Build. The gateway refuses one
    # outright; if anything ever reaches here without a surface, the quiet
    # answer is the conservative one.
    assert _system_messages("") == [_SYSTEM_PROMPT]


def test_a_build_turn_receives_the_operating_protocol(tmp_path: Path) -> None:
    router = RecordingRouter()
    _handle(_orchestrator(tmp_path, router), _envelope("build"))

    system = _system_text(router.seen_messages[0])
    assert "Operating protocol for this workspace" in system
    # The four load-bearing clauses, so a future edit cannot quietly drop one.
    for clause in ("FLOOR", "FRAME", "VERIFY", "LOOP"):
        assert f"{clause}" in system
    assert "do not invent specifics" in system
    assert "Read the file before you edit it" in system
    assert "exit code 0 is not the same as correct" in system


def test_a_chat_turn_does_not_receive_it(tmp_path: Path) -> None:
    router = RecordingRouter()
    _handle(_orchestrator(tmp_path, router), _envelope("chat"))

    assert "Operating protocol for this workspace" not in _system_text(router.seen_messages[0])


def test_the_surface_changes_no_tool_the_model_is_offered(tmp_path: Path) -> None:
    build_router = RecordingRouter()
    _handle(_orchestrator(tmp_path / "build", build_router), _envelope("build"))
    chat_router = RecordingRouter()
    _handle(_orchestrator(tmp_path / "chat", chat_router), _envelope("chat"))

    assert build_router.seen_tools[0] == chat_router.seen_tools[0]
    assert build_router.seen_tools[0] != []
