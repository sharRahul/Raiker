"""BUG-72 — a turn that really runs a tool must survive its own tool call.

With `web_fetch` enabled and its decision mode at **Allow**, every turn that
called it came back as the whole answer:

    model_unavailable: provider_stream_failed

…with no server log line and no way for the owner to tell what had failed. The
same prompt at **Ask** answered normally, because a withheld call returns
instantly and never touches the network.

Three separate defects made that one symptom, and this module holds one group
per defect:

1. **The tool ran on the event loop.** `ToolBroker.execute` is synchronous, and
   so is every tool under it: `web_fetch` is a blocking DNS lookup plus an
   HTTPS GET capped at fifteen seconds. The orchestrator only moved a call to a
   worker thread when the batch held *more than one* read — so the ordinary
   single call froze the whole ASGI process, which is why the provider client
   could not notice its pooled connection closing underneath it.
2. **The adapter destroyed the reason.** Both streaming adapters caught every
   already-classified provider error and re-raised it as one
   `ProviderStreamError`, so an expired key, an empty balance, a rate limit and
   a dropped socket all reached the owner as `provider_stream_failed`.
3. **The turn said nothing useful and logged nothing.** The answer was a raw
   reason code claiming the model was unavailable, and the server log had no
   line at all.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

import pytest

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import (
    EVENT_TYPES,
    ClientMetadata,
    PolicyDecision,
    PromptEnvelope,
    PromptOptions,
    PromptPayload,
    ToolAction,
    ToolResult,
    UserMetadata,
)
from raiker.events.query import EventViewer
from raiker.gateway.agent_gateway import AgentGateway
from raiker.models.contracts import ModelResponse
from raiker.models.exceptions import (
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderQuotaExhaustedError,
    ProviderStreamError,
    ProviderTimeoutError,
    provider_error_code,
    provider_failure_message,
    stream_failure,
)
from raiker.models.session_state import TERMINAL_MODEL_SESSION_ID, ModelSessionState


def _envelope() -> PromptEnvelope:
    return PromptEnvelope(
        request_id=new_id("req_"),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        client=ClientMetadata(type="rest", name="test", version="0"),
        user=UserMetadata(),
        prompt=PromptPayload(text="read a page"),
        options=PromptOptions(model_profile=""),
    )


def _gateway(tmp_path: Path) -> AgentGateway:
    gw = AgentGateway(tmp_path)
    gw.store.save_model_session_state(
        ModelSessionState(
            session_id=TERMINAL_MODEL_SESSION_ID,
            profile_id="anthropic-hosted",
            model="claude-opus-4-8",
        )
    )
    return gw


class TestToolExecutionNeverOccupiesTheEventLoop:
    """Defect 1 — the blocking call that starved the provider connection."""

    def test_a_single_blocking_tool_call_does_not_stall_the_loop(self, tmp_path: Path) -> None:
        gw = _gateway(tmp_path)
        action = ToolAction(
            action_id=new_id("act_"),
            tool_name="web_fetch",
            arguments={"url": "https://example.test/"},
            risk_level="medium",
            requires_approval=False,
            proposed_by="model",
        )

        def blocking_execute(*_args: Any, **_kwargs: Any) -> tuple[ToolResult, PolicyDecision]:
            # Exactly what `web_fetch` does: a synchronous socket call. Half a
            # second is long enough that a stalled loop is unambiguous and short
            # enough to keep the suite fast.
            time.sleep(0.5)
            now = utc_now()
            return (
                ToolResult(
                    action_id=action.action_id,
                    tool_name=action.tool_name,
                    status="success",
                    output={"status": "success"},
                    error=None,
                    started_at=now,
                    completed_at=now,
                ),
                PolicyDecision(
                    decision_id=new_id("pol_"),
                    action_id=action.action_id,
                    decision="allow",
                    reasons=["allowed_read"],
                    requires_user_approval=False,
                    risk_level="medium",
                    timestamp=now,
                ),
            )

        gw.runtime.tool_broker.execute = blocking_execute  # type: ignore[assignment]

        async def scenario() -> int:
            ticks = 0

            async def heartbeat() -> None:
                nonlocal ticks
                while True:
                    await asyncio.sleep(0.05)
                    ticks += 1

            beat = asyncio.create_task(heartbeat())
            try:
                await gw.runtime._aexecute_tool(action, _envelope(), None)
            finally:
                beat.cancel()
            return ticks

        ticks = asyncio.run(scenario())
        # A loop held by the tool records at most the one tick it owes the
        # `await`. A loop that stayed free records roughly ten.
        assert ticks >= 5, f"the event loop was blocked during the tool call ({ticks} ticks)"


class TestAStreamFailureKeepsItsOwnReason:
    """Defect 2 — `provider_stream_failed` swallowed every classified cause."""

    @pytest.mark.parametrize(
        "raised",
        [
            ProviderAuthenticationError("provider_auth_failed:http_401"),
            ProviderQuotaExhaustedError("provider_quota_exhausted:http_400"),
            ProviderTimeoutError("provider_timeout"),
            ProviderConnectionError("provider_connection_failed"),
        ],
    )
    def test_a_classified_provider_error_is_returned_unchanged(
        self, raised: Exception
    ) -> None:
        assert stream_failure(raised) is raised
        assert provider_error_code(stream_failure(raised)) == str(raised)

    def test_an_unclassified_failure_carries_its_exception_type(self) -> None:
        wrapped = stream_failure(RuntimeError("socket went away"))
        assert isinstance(wrapped, ProviderStreamError)
        # The class name, never the provider's own message: a message may carry
        # a key fragment or a request body, a class name cannot.
        assert provider_error_code(wrapped) == "provider_stream_failed:RuntimeError"
        assert "socket went away" not in str(wrapped)

    def test_both_streaming_adapters_use_the_same_rule(self) -> None:
        import inspect

        from raiker.models.providers import anthropic_messages, openai_compatible

        for module in (anthropic_messages, openai_compatible):
            source = inspect.getsource(module)
            assert "stream_failure(exc)" in source, module.__name__
            # The old blanket wrapper is what lost the reason; it must not
            # reappear in either adapter.
            assert "ProviderStreamError(type(exc).__name__)" not in source, module.__name__


class TestAFailedTurnSaysWhatToDo:
    """Defect 3 — a raw reason code as the whole answer, and a silent log."""

    def test_the_message_leads_with_the_repair_and_keeps_the_code(self) -> None:
        message = provider_failure_message("provider_auth_failed:http_401")
        assert message.startswith("I could not finish that:")
        assert "Update the key on Models" in message
        # The machine code stays, for support and for the troubleshooting table.
        assert "(model_unavailable: provider_auth_failed:http_401)" in message

    def test_every_reason_code_family_has_a_repair(self) -> None:
        from raiker.models.exceptions import (
            _PROVIDER_ERROR_CLASS_CODES,
            provider_error_sentence,
        )

        generic = provider_error_sentence("something_nobody_declared")
        for code in _PROVIDER_ERROR_CLASS_CODES.values():
            assert provider_error_sentence(code) != generic, code

    def test_a_failed_turn_is_written_to_the_server_log(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        gw = _gateway(tmp_path)

        async def fake_achat(provider, model, messages, tools=None, **kwargs):  # type: ignore[no-untyped-def]
            raise ProviderStreamError("provider_stream_failed:RemoteProtocolError")

        gw.runtime.model_router.achat = fake_achat  # type: ignore[assignment]
        with caplog.at_level(logging.WARNING, logger="raiker.runtime.orchestrator"):
            response = asyncio.run(gw.runtime._acall_model(_envelope(), []))

        assert response.finish_reason == "error"
        assert "model_unavailable: provider_stream_failed:RemoteProtocolError" in response.text
        logged = "\n".join(record.getMessage() for record in caplog.records)
        assert "model request failed" in logged
        assert "reason=provider_stream_failed:RemoteProtocolError" in logged
        assert "error_class=ProviderStreamError" in logged


class TestOneRetryForATransportFailureAndNoneForADecision:
    """A dropped connection costs one re-attempt; a refusal costs none."""

    def _attempts(self, gw: AgentGateway, exc: Exception) -> tuple[int, list[str]]:
        calls: list[str] = []

        async def fake_achat(provider, model, messages, tools=None, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(f"{provider}/{model}")
            raise exc

        gw.runtime.model_router.achat = fake_achat  # type: ignore[assignment]
        envelope = _envelope()
        asyncio.run(gw.runtime._acall_model(envelope, []))
        viewer = EventViewer(gw.store)
        events = [
            str(event["event_type"])
            for event in viewer.list_events(session_id=envelope.session_id)
        ]
        return len(calls), events

    def test_a_dropped_connection_is_tried_once_more_on_the_same_model(
        self, tmp_path: Path
    ) -> None:
        gw = _gateway(tmp_path)
        attempts, events = self._attempts(gw, ProviderConnectionError("provider_connection_failed"))
        assert attempts == 2
        assert "model_request_retried" in events

    def test_a_rejected_credential_is_not_retried(self, tmp_path: Path) -> None:
        gw = _gateway(tmp_path)
        attempts, events = self._attempts(
            gw, ProviderAuthenticationError("provider_auth_failed:http_401")
        )
        assert attempts == 1
        assert "model_request_retried" not in events

    def test_an_empty_balance_is_not_retried(self, tmp_path: Path) -> None:
        gw = _gateway(tmp_path)
        attempts, _ = self._attempts(
            gw, ProviderQuotaExhaustedError("provider_quota_exhausted:http_400")
        )
        assert attempts == 1

    def test_a_healthy_turn_makes_exactly_one_request(self, tmp_path: Path) -> None:
        gw = _gateway(tmp_path)
        calls: list[str] = []

        async def fake_achat(provider, model, messages, tools=None, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(provider)
            return ModelResponse(text="ok", finish_reason="stop")

        gw.runtime.model_router.achat = fake_achat  # type: ignore[assignment]
        asyncio.run(gw.runtime._acall_model(_envelope(), []))
        assert calls == calls[:1]

    def test_the_retry_event_type_is_declared(self) -> None:
        # FIXED-97: an emitted event type that is not declared kills the turn at
        # the moment it tries to say what happened.
        assert "model_request_retried" in EVENT_TYPES
