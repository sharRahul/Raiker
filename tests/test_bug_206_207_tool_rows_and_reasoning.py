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
from pathlib import Path
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
from raiker.models.exceptions import ProviderUnsupportedCapabilityError
from raiker.models.providers.anthropic_messages import (
    AsyncAnthropicMessagesProvider,
    reset_thinking_negotiation,
)
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.presentation import (
    _FAMILY_BY_TOOL,
    _LABEL_BY_TOOL,
    TOOL_FAMILIES,
    tool_row,
)
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
    row = tool_row("read_file", {"path": "docs/architecture/ARCHITECTURE.md"})
    assert row.family == "file-read"
    assert row.label == "Read file"
    assert row.action == "docs/architecture/ARCHITECTURE.md"


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
        # What the shipped `anthropic-hosted` profile declares, and what the
        # router therefore puts on every real Anthropic request. The dataclass
        # default is 1024, which is below the budgeted spelling's own floor plus
        # the room an answer needs (GCR-31): a number no real turn runs with,
        # and the wrong one to negotiate a thinking spelling against.
        max_tokens=16000,
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


# ── The two halves of the row, kept from drifting ────────────────────────────


def _web_source(relative: str) -> str:
    root = Path(__file__).resolve().parents[1] / "apps" / "web" / "src" / "lib"
    return (root / relative).read_text(encoding="utf-8")


def _between(text: str, after: str, until: str) -> str:
    """The source between two markers, with line comments removed first.

    These files are heavily commented by design, and a `;` or a quoted word
    inside a comment would otherwise end the segment early — which is a parsing
    bug that reads as a missing glyph.
    """
    import re

    stripped = re.sub(r"//[^\n]*", "", text)
    return stripped.split(after, 1)[1].split(until, 1)[0]


def test_every_family_the_runtime_can_send_has_a_glyph_in_the_client() -> None:
    """A family added on one side and not the other renders as the fallback.

    Silently: an unknown family is *supposed* to fall back, which is exactly why
    a missing glyph would not look like a bug. This is the check that fails
    instead — the same directional guard `test_api_contract_schemas.py` applies
    to the response DTOs.
    """
    import re

    presentation = _web_source("chatPresentation.ts")
    union = _between(presentation, "export type ToolFamily", ";")
    declared = set(re.findall(r'"([a-z-]+)"', union))
    icons = _between(presentation, "const FAMILY_ICON", "};")
    mapped = dict(re.findall(r'^\s*"?([a-z-]+)"?:\s*"([a-z-]+)"', icons, re.M))

    assert not set(TOOL_FAMILIES) - declared, (
        f"ToolFamily is missing: {sorted(set(TOOL_FAMILIES) - declared)}"
    )
    assert not declared - set(TOOL_FAMILIES), (
        f"ToolFamily names families the runtime never sends: {sorted(declared - set(TOOL_FAMILIES))}"
    )
    assert not set(TOOL_FAMILIES) - set(mapped), (
        f"FAMILY_ICON has no glyph for: {sorted(set(TOOL_FAMILIES) - set(mapped))}"
    )

    # And every glyph it names is one the icon set actually declares, so a typo
    # renders nothing rather than the fallback it was never asked for.
    icon_names = set(re.findall(r'"([a-z-]+)"', _between(_web_source("icons.ts"), "export type IconName", ";")))
    unknown = set(mapped.values()) - icon_names
    assert not unknown, f"FAMILY_ICON names glyphs the set does not declare: {sorted(unknown)}"


def test_every_model_exposed_tool_has_a_family_and_a_label() -> None:
    """A tool added to the registry without a row entry still renders as a tool.

    That is the fallback working, not the row being right: it would carry the
    neutral spanner and a name derived from its identifier. This fails while the
    entry is missing, which is when it is cheap to add.
    """
    from raiker.models.tool_registry import MODEL_EXPOSED_TOOLS

    missing_family = sorted(set(MODEL_EXPOSED_TOOLS) - set(_FAMILY_BY_TOOL))
    missing_label = sorted(set(MODEL_EXPOSED_TOOLS) - set(_LABEL_BY_TOOL))
    assert not missing_family, f"tools with no icon family: {missing_family}"
    assert not missing_label, f"tools with no owner-language label: {missing_label}"

    # And nothing in the tables names a tool that no longer exists, which is how
    # a rename leaves a label behind that can never be reached. `vector_get` is
    # brokered but deliberately not advertised to the model, so it is named here
    # rather than silently allowed by a looser comparison.
    broker_only = {"vector_get"}
    stale = sorted(
        (set(_FAMILY_BY_TOOL) | set(_LABEL_BY_TOOL)) - set(MODEL_EXPOSED_TOOLS) - broker_only
    )
    assert not stale, f"row entries for tools that no longer exist: {stale}"


def test_every_family_named_in_the_table_is_a_declared_family() -> None:
    unknown = sorted(set(_FAMILY_BY_TOOL.values()) - set(TOOL_FAMILIES))
    assert not unknown, f"tools mapped to families that do not exist: {unknown}"


def test_a_model_that_will_not_think_says_what_to_do_about_it() -> None:
    """The remediation for this one is on the composer, not on Models.

    The default sentence sends the owner to run a readiness check, which will
    pass — the model is reachable, it just will not think in either spelling the
    provider offers. Naming the wrong remedy is the defect FIXED-01 removed from
    the connection card, applied to the other end of the turn.
    """
    from raiker.models.exceptions import provider_failure_message

    message = provider_failure_message("reasoning_unsupported")
    assert "Set Thinking back to default" in message
    assert "readiness check" not in message
    # The machine code stays where support and the audit trail can read it.
    assert "reasoning_unsupported" in message


def test_a_thinking_budget_always_leaves_room_for_the_answer() -> None:
    """GCR-31 — the clamp ended at `max(1024, …)`, which clamps *upward*.

    The comment beside it said the budget has to leave room for the answer and
    `max_tokens` counts both. With `max_tokens` at 1024 the expression returned
    a 1024-token thinking budget, leaving the answer nothing: exactly the
    request the comment describes as one the provider would refuse.
    """
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

    request = ModelRequest(
        profile_id="anthropic-profile",
        provider="anthropic",
        model="claude-test",
        messages=[ModelMessage(role="user", content="What is 17 * 23?")],
        reasoning=ReasoningOptions(enabled=True, summary="summarized"),
        max_tokens=4096,
    )
    run(_provider(handler).chat(request))

    budgeted = seen[1]["thinking"]
    assert budgeted["type"] == "enabled"
    assert budgeted["budget_tokens"] < seen[1]["max_tokens"]
    assert budgeted["budget_tokens"] >= 1024


def test_a_max_tokens_too_small_for_thinking_is_said_out_loud() -> None:
    """Never clamp upward beyond the available budget: say what is wrong instead."""
    from raiker.models.exceptions import provider_error_sentence

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
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

    request = ModelRequest(
        profile_id="anthropic-profile",
        provider="anthropic",
        model="claude-test",
        messages=[ModelMessage(role="user", content="What is 17 * 23?")],
        reasoning=ReasoningOptions(enabled=True, summary="summarized"),
        max_tokens=1024,
    )

    with pytest.raises(ProviderUnsupportedCapabilityError) as raised:
        run(_provider(handler).chat(request))

    assert str(raised.value) == "reasoning_budget_exceeds_output_limit"
    # And the owner is told which number to change, not a raw code.
    sentence = provider_error_sentence("reasoning_budget_exceeds_output_limit")
    assert "maximum output" in sentence
