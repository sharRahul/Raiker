"""Streaming runtime + gateway tests.

Prove the streaming path yields incremental text deltas and a final response, that the
synchronous ``ahandle``/``submit_prompt`` paths are unchanged, and that the gateway
streaming path still produces the durable checkpoint/turn-close finalisation.
"""

from __future__ import annotations

import asyncio
import tempfile
from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path

from raiker.cli.commands import build_prompt_envelope
from raiker.contracts.streaming import FINAL, LIFECYCLE, TEXT_DELTA, StreamEvent
from raiker.events.writer import EventLogWriter
from raiker.gateway.agent_gateway import AgentGateway
from raiker.models.contracts import ModelMessage, ModelResponse, ModelStreamEvent, ToolSpec
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.orchestrator import RuntimeOrchestrator
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker


class StreamingRouter:
    """A router whose astream yields fixed deltas (and an achat fallback)."""

    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks

    async def astream(
        self,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
    ) -> AsyncIterator[ModelStreamEvent]:
        for chunk in self.chunks:
            yield ModelStreamEvent(event_type="text_delta", text_delta=chunk)
        yield ModelStreamEvent(event_type="finish", finish_reason="stop")

    async def achat(
        self,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
    ) -> ModelResponse:
        return ModelResponse(text="".join(self.chunks), finish_reason="stop")


def _orchestrator(tmp_path: Path, router: object) -> RuntimeOrchestrator:
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
        default_provider=("test", "m"),
    )


def test_runtime_streams_text_deltas_then_final() -> None:
    tmp = Path(tempfile.mkdtemp())
    orch = _orchestrator(tmp, StreamingRouter(["Hello", ", ", "world"]))
    env = build_prompt_envelope("hi")

    async def main() -> tuple[list[str], str, list[str]]:
        deltas: list[str] = []
        kinds: list[str] = []
        final_msg = ""
        async for ev in orch.astream_handle(env):
            kinds.append(ev.kind)
            if ev.kind == TEXT_DELTA:
                deltas.append(ev.text)
            if ev.kind == FINAL and ev.response is not None:
                final_msg = ev.response.message
        return deltas, final_msg, kinds

    deltas, final_msg, kinds = asyncio.run(main())
    assert deltas == ["Hello", ", ", "world"]
    assert final_msg == "Hello, world"
    assert LIFECYCLE in kinds
    # text deltas must arrive before the final event
    assert kinds.index(TEXT_DELTA) < kinds.index(FINAL)


def test_ahandle_unchanged_uses_achat_not_stream() -> None:
    tmp = Path(tempfile.mkdtemp())

    class AchatOnlyRouter(StreamingRouter):
        async def astream(self, *a, **k):  # type: ignore[no-untyped-def]
            raise AssertionError("ahandle must not call astream")
            yield  # pragma: no cover

    orch = _orchestrator(tmp, AchatOnlyRouter(["only", "-achat"]))
    response = asyncio.run(orch.ahandle(build_prompt_envelope("hi")))
    assert response.status == "completed"
    assert response.message == "only-achat"


def test_gateway_stream_finalizes_with_checkpoint_offline(offline_default_model: None) -> None:
    # No model server in tests -> the real gateway streams the safe model_unavailable
    # result, but the streaming path must still finalise (checkpoint + events path).
    tmp = Path(tempfile.mkdtemp())
    gateway = AgentGateway(tmp)
    env = build_prompt_envelope("hello")

    async def main() -> StreamEvent | None:
        final: StreamEvent | None = None
        async for ev in gateway.astream_prompt(env):
            if ev.kind == FINAL:
                final = ev
        return final

    final = asyncio.run(main())
    assert final is not None and final.response is not None
    assert final.response.events_path
    assert final.response.checkpoint_path
    assert "model_unavailable" in final.response.message


def test_gateway_stream_and_submit_reach_same_status_offline(offline_default_model: None) -> None:
    tmp = Path(tempfile.mkdtemp())
    gateway = AgentGateway(tmp)

    streamed_final = asyncio.run(_last_final(gateway, "x"))
    submitted = asyncio.run(gateway.submit_prompt_async(build_prompt_envelope("x")))
    assert streamed_final is not None and streamed_final.response is not None
    assert streamed_final.response.status == submitted.status == "failed"


def test_gateway_stream_stops_when_its_tracked_task_is_cancelled(
    mark_model_ready: Callable[..., None],
) -> None:
    tmp = Path(tempfile.mkdtemp())
    mark_model_ready(tmp, "local_user")
    gateway = AgentGateway(tmp)
    gateway.runtime.model_router = StreamingRouter(["first", "second"])  # type: ignore[assignment]
    env = build_prompt_envelope("hello")

    async def main() -> StreamEvent | None:
        stream = gateway.astream_prompt(env).__aiter__()
        await anext(stream)
        task = gateway.store.list_tasks(session_id=env.session_id)[0]
        gateway.store.cancel_task(task.task_id, "user requested stop")
        final: StreamEvent | None = None
        async for event in stream:
            if event.kind == FINAL:
                final = event
        return final

    final = asyncio.run(main())
    assert final is not None and final.response is not None
    # B17/C13 — a turn the owner stopped reports `stopped`, not `failed`: the
    # runtime did what it was told, and calling that a failure blamed it for the
    # owner's decision.
    assert final.response.status == "stopped"
    assert final.response.message == "Stopped by user at a safe boundary."
    assert gateway.store.list_tasks(session_id=env.session_id)[0].status == "cancelled"


async def _last_final(gateway: AgentGateway, text: str) -> StreamEvent | None:
    final: StreamEvent | None = None
    async for ev in gateway.astream_prompt(build_prompt_envelope(text)):
        if ev.kind == FINAL:
            final = ev
    return final


def test_stream_event_rejects_invalid_kind() -> None:
    import pytest

    with pytest.raises(ValueError):
        StreamEvent(kind="not_a_kind")
