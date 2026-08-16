"""BUG-206 and BUG-207 — the two things a streamed turn could not say.

**BUG-206.** A turn that listed a directory, read a file or fetched a page
rendered exactly like a turn that used none of them. The broker emitted
``tool_started`` / ``tool_completed`` / ``tool_failed`` through its writer and
nothing else, so the facts were readable afterwards on the Audit log and never
during the turn. The ``TOOL`` stream kind was defined in
``raiker/contracts/streaming.py`` and constructed nowhere.

**BUG-207.** Extended thinking was requested, refused by the provider for most
of the catalogue, and — where it did arrive — dropped by a stream parser that
handled ``text_delta`` and ``input_json_delta`` only.

These tests hold both halves: that a row carries strictly less than the durable
event does, and that reasoning is asked for in the spelling the model accepts
and read when it comes back.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.contracts.models import ClientMetadata, ToolAction
from raiker.contracts.streaming import STREAM_KINDS, TOOL, StreamEvent
from raiker.events.writer import EventLogWriter
from raiker.models.contracts import (
    ModelCapabilities,
    ModelMessage,
    ModelRequest,
    ReasoningOptions,
)
from raiker.models.providers.anthropic_messages import (
    AsyncAnthropicMessagesProvider,
    reset_thinking_negotiation,
)
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.presentation import tool_row
from tests.machine_identity_helpers import IdentityBoundTestBroker as ToolBroker


def _broker(tmp_path: Any) -> Any:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    store = SQLiteStore(tmp_path)
    return ToolBroker(
        workspace_root=tmp_path,
        policy_engine=PolicyEngine(StaticPolicyConfig(tmp_path)),
        store=store,
        writer=EventLogWriter(store),
        principal_id="principal_owner",
    )


def _client() -> ClientMetadata:
    return ClientMetadata(type="test_harness", name="tests", version="0.0.0")


# ── BUG-206 slice A: the broker's stream sink ────────────────────────────────


def test_a_successful_call_arrives_on_the_stream_started_then_completed(tmp_path: Any) -> None:
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    broker = _broker(tmp_path)
    sink: list[StreamEvent] = []
    broker.stream_sink = sink

    result, decision = broker.execute(
        ToolAction(new_id("act_"), "list_directory", {"path": "."}, "medium", False),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        client=_client(),
    )

    assert decision.decision == "allow"
    assert result.status == "success"
    assert [event.event_type for event in sink] == ["tool_started", "tool_completed"]
    assert {event.kind for event in sink} == {TOOL}
    assert TOOL in STREAM_KINDS
    started, completed = sink
    assert started.payload["status"] == "running"
    assert completed.payload["status"] == "success"
    # One action id, so the client settles the row it opened rather than
    # adding a second line for the same call.
    assert started.payload["action_id"] == completed.payload["action_id"]
    assert completed.payload["label"] == "List folder"


def test_a_failing_call_carries_its_named_reason(tmp_path: Any) -> None:
    broker = _broker(tmp_path)
    sink: list[StreamEvent] = []
    broker.stream_sink = sink

    result, _ = broker.execute(
        ToolAction(new_id("act_"), "read_file", {"path": "absent.md"}, "medium", False),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        client=_client(),
    )

    assert result.status == "failed"
    failed = sink[-1]
    assert failed.event_type == "tool_failed"
    assert failed.payload["status"] == "failed"
    assert failed.payload["reason"]


def test_without_a_sink_the_broker_behaves_exactly_as_before(tmp_path: Any) -> None:
    """A non-streamed turn, the terminal client, and a direct caller are unchanged."""
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    broker = _broker(tmp_path)
    assert broker.stream_sink is None
    result, _ = broker.execute(
        ToolAction(new_id("act_"), "list_directory", {"path": "."}, "medium", False),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        client=_client(),
    )
    assert result.status == "success"


# ── BUG-206 slice B: what a row may say ──────────────────────────────────────


def test_a_row_names_the_object_in_the_owners_language() -> None:
    row = tool_row("read_file", {"path": "docs/ARCHITECTURE.md"})
    assert row.family == "file-read"
    assert row.label == "Read file"
    assert row.action == "docs/ARCHITECTURE.md"


def test_a_fetch_row_names_the_host_and_never_the_query() -> None:
    """A signed URL carries its credential in the query string, in a shape that
    reads as ordinary base64 to pattern-based redaction. The host is the fact
    the row exists to state and the only part that cannot carry one."""
    row = tool_row(
        "web_fetch",
        {"url": "https://files.example.com:8443/a/b?token=AKIAIOSFODNN7EXAMPLE&x=1#frag"},
    )
    assert row.action == "files.example.com"
    assert "token" not in row.action
    assert "8443" not in row.action


def test_a_command_row_names_the_program_and_never_its_arguments() -> None:
    row = tool_row("shell", {"command": "/usr/bin/curl -H 'Authorization: Bearer abc' https://x"})
    assert row.label == "Run command"
    assert row.action == "curl"


def test_a_metadata_only_tool_derives_no_phrase_from_its_arguments() -> None:
    """`consult_advisor` and projected MCP tools have their argument *values*
    dropped from the durable event. The transcript can never be the looser of
    the two surfaces, so it derives nothing from them either."""
    assert tool_row("consult_advisor", {"question": "a private question"}).action == ""
    mcp = tool_row("mcp__research__search", {"arguments": {"q": "a private query"}})
    assert mcp.label == "Call research"
    assert mcp.action == "search"
    assert "private" not in mcp.action


def test_a_memory_write_row_never_repeats_the_text_being_stored() -> None:
    row = tool_row("memory_write", {"text": "the owner's home address", "scope": "user"})
    assert row.action == "user scope"
    assert "address" not in row.action


def test_a_secret_shaped_argument_is_redacted_before_it_reaches_a_row() -> None:
    row = tool_row("grep", {"query": "sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"})
    assert "sk-ant-api03" not in row.action


def test_an_unknown_tool_renders_as_a_tool_rather_than_as_nothing() -> None:
    row = tool_row("some_future_tool", {"anything": "at all"})
    assert row.family == "tool"
    assert row.label == "Some future tool"
    assert row.action == ""


def test_a_long_path_keeps_its_filename() -> None:
    row = tool_row("read_file", {"path": "a/" * 60 + "the-file-that-matters.md"})
    assert row.action.startswith("…")
    assert row.action.endswith("the-file-that-matters.md")


# ── BUG-207 slice B: the thinking spelling, and reading it back ──────────────


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def collect(iterator: AsyncIterator[Any]) -> list[Any]:
    return [event async for event in iterator]


def _provider(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    summary: bool = True,
) -> AsyncAnthropicMessagesProvider:
    return AsyncAnthropicMessagesProvider(
        profile_id="anthropic-profile",
        provider="anthropic",
        model="claude-test",
        endpoint="https://api.anthropic.test",
        capabilities=ModelCapabilities(
            supports_streaming=True,
            supports_tool_calls=True,
            supports_reasoning=True,
            supports_reasoning_summary=summary,
            reasoning_modes=("adaptive",),
        ),
        extra_headers={"x-api-key": "test-key"},
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def _reasoning_request(model: str = "claude-test") -> ModelRequest:
    return ModelRequest(
        profile_id="anthropic-profile",
        provider="anthropic",
        model=model,
        messages=[ModelMessage(role="user", content="What is 17 * 23?")],
        reasoning=ReasoningOptions(enabled=True, summary="summarized"),
    )


def _answer(*, thinking: str = "") -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    if thinking:
        content.append({"type": "thinking", "thinking": thinking, "signature": "sig"})
    content.append({"type": "text", "text": "391"})
    return {"content": content, "stop_reason": "end_turn", "usage": {}}


@pytest.fixture(autouse=True)
def _forget_negotiated_shapes() -> Any:
    reset_thinking_negotiation()
    yield
    reset_thinking_negotiation()


def test_reasoning_is_asked_for_with_the_summarized_display() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=_answer(thinking="17*23 = 391"))

    response = run(_provider(handler).chat(_reasoning_request()))
    assert seen[0]["thinking"] == {"type": "adaptive", "display": "summarized"}
    # And the thinking block is read back rather than dropped on the floor.
    assert response.reasoning == "17*23 = 391"
    assert response.text == "391"


def test_a_model_that_refuses_adaptive_is_asked_again_in_the_spelling_it_named() -> None:
    """Measured against the live catalogue: `claude-haiku-4-5` and
    `claude-opus-4-5` refuse `adaptive` and name the budgeted spelling, while
    `claude-opus-5` refuses the budgeted one and names `adaptive`. One
    `reasoning_modes` list per provider cannot be right for both, and the wrong
    one fails the whole turn with a 400 rather than dropping reasoning."""
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen.append(payload)
        if payload.get("thinking", {}).get("type") == "adaptive":
            return httpx.Response(
                400,
                json={
                    "type": "error",
                    "error": {
                        "type": "invalid_request_error",
                        "message": "adaptive thinking is not supported on this model",
                    },
                },
            )
        return httpx.Response(200, json=_answer(thinking="thought"))

    response = run(_provider(handler).chat(_reasoning_request()))
    assert [payload["thinking"]["type"] for payload in seen] == ["adaptive", "enabled"]
    assert seen[1]["thinking"]["budget_tokens"] > 0
    assert response.reasoning == "thought"


def test_the_negotiated_spelling_is_remembered_so_it_is_paid_for_once() -> None:
    attempts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        attempts.append(payload["thinking"]["type"])
        if payload["thinking"]["type"] == "adaptive":
            return httpx.Response(
                400,
                json={"error": {"message": "adaptive thinking is not supported on this model"}},
            )
        return httpx.Response(200, json=_answer(thinking="t"))

    provider = _provider(handler)
    run(provider.chat(_reasoning_request()))
    run(provider.chat(_reasoning_request()))
    assert attempts == ["adaptive", "enabled", "enabled"]


def test_a_400_that_names_no_other_spelling_stays_a_real_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"error": {"type": "invalid_request_error", "message": "max_tokens too large"}}
        )

    with pytest.raises(Exception) as raised:
        run(_provider(handler).chat(_reasoning_request()))
    assert "provider_http_error" in str(raised.value) or "quota" in str(raised.value)


def test_no_thinking_block_is_sent_when_reasoning_was_not_asked_for() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=_answer())

    plain = ModelRequest(
        profile_id="anthropic-profile",
        provider="anthropic",
        model="claude-test",
        messages=[ModelMessage(role="user", content="hello")],
    )
    response = run(_provider(handler).chat(plain))
    assert "thinking" not in seen[0]
    assert response.reasoning == ""


def _sse(*events: dict[str, Any]) -> bytes:
    return "".join(f"data: {json.dumps(event)}\n\n" for event in events).encode()


def test_thinking_deltas_are_read_and_kept_apart_from_the_answer() -> None:
    """The branch that was missing. `thinking_delta` fell through a chain that
    handled `text_delta` and `input_json_delta` only, so Raiker paid for
    reasoning tokens, received them, and dropped them."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_sse(
                {"type": "message_start", "message": {"usage": {"input_tokens": 4}}},
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "thinking", "thinking": "", "signature": ""},
                },
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "thinking_delta", "thinking": "17 * 23 "},
                },
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "thinking_delta", "thinking": "= 391."},
                },
                # The signature is an integrity marker for replaying the block.
                # It is not text and must never reach a surface.
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "signature_delta", "signature": "ErkCCosBCBAY"},
                },
                {"type": "content_block_stop", "index": 0},
                {
                    "type": "content_block_delta",
                    "index": 1,
                    "delta": {"type": "text_delta", "text": "391"},
                },
                {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {}},
                {"type": "message_stop"},
            ),
            headers={"content-type": "text/event-stream"},
        )

    events = run(collect(_provider(handler).stream_chat(_reasoning_request())))
    reasoning = [event for event in events if event.event_type == "reasoning_delta"]
    text = [event for event in events if event.event_type == "text_delta"]
    assert "".join(event.reasoning_delta for event in reasoning) == "17 * 23 = 391."
    assert "".join(event.text_delta for event in text) == "391"
    # Never merged: a reasoning event carries no answer text and vice versa.
    assert all(event.text_delta == "" for event in reasoning)
    assert all(event.reasoning_delta == "" for event in text)
    assert not any("ErkCCosBCBAY" in event.reasoning_delta for event in reasoning)


def test_a_stream_refused_for_its_thinking_spelling_is_retried_before_a_token_lands() -> None:
    attempts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        attempts.append(payload["thinking"]["type"])
        if payload["thinking"]["type"] == "adaptive":
            return httpx.Response(
                400,
                json={"error": {"message": "adaptive thinking is not supported on this model"}},
            )
        return httpx.Response(
            200,
            content=_sse(
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "thinking_delta", "thinking": "thought"},
                },
                {
                    "type": "content_block_delta",
                    "index": 1,
                    "delta": {"type": "text_delta", "text": "answer"},
                },
                {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {}},
            ),
            headers={"content-type": "text/event-stream"},
        )

    events = run(collect(_provider(handler).stream_chat(_reasoning_request())))
    assert attempts == ["adaptive", "enabled"]
    assert [event.reasoning_delta for event in events if event.event_type == "reasoning_delta"] == [
        "thought"
    ]
