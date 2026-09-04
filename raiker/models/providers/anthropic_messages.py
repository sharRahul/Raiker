from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx

from raiker.models.contracts import (
    EmbeddingRequest,
    EmbeddingResponse,
    ModelCapabilities,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ProviderModelInfo,
    ToolCallProposal,
)
from raiker.models.exceptions import (
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderModelNotFoundError,
    ProviderQuotaExhaustedError,
    ProviderRateLimitError,
    ProviderResponseValidationError,
    ProviderStreamError,
    ProviderTimeoutError,
    ProviderUnsupportedCapabilityError,
    ProviderWorkspaceRequiredError,
    is_quota_exhausted,
    needs_workspace_id,
    stream_failure,
)
from raiker.models.health import ProviderHealth

_STOP_REASON_TO_FINISH = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
    "refusal": "error",
    "pause_turn": "stop",
}


def _map_finish(stop_reason: str) -> str:
    return _STOP_REASON_TO_FINISH.get(stop_reason, "stop")


ANTHROPIC_VERSION = "2023-06-01"
EXTENDED_CACHE_TTL_BETA = "extended-cache-ttl-2025-04-11"

# ── Extended thinking: two request shapes, and why one cannot be declared ────
#
# BUG-207 slice B. The Messages API accepts extended thinking in two spellings,
# and which one a model accepts is a property of the *model*, not of the
# provider. Measured against the live catalogue on 2026-08-15:
#
# | Model | `adaptive` | `enabled` + `budget_tokens` |
# |---|---|---|
# | opus-5, sonnet-5, fable-5, opus-4-8, opus-4-7 | accepted | refused |
# | sonnet-4-6, opus-4-6 | accepted | accepted |
# | opus-4-5, haiku-4-5, sonnet-4-5 | refused | accepted |
#
# `model-profiles.json` carries one `reasoning_modes` list for every model
# behind `anthropic-hosted`, so no declaration is right for all of them — and
# the wrong one does not degrade quietly, it fails the whole turn with a 400.
# That is why the profile's declared `{"type": "adaptive"}` was never reached by
# a real turn: the only models it fitted were not the ones being asked.
#
# So the shape is *negotiated* rather than declared. The first request for a
# model uses the declared shape; if the provider refuses it **and names the
# other one in the refusal**, that answer is recorded and the request is made
# once more. This is not a fallback in the sense the runtime forbids — no
# capability is substituted and nothing is silently downgraded. It is the
# spelling of one field, corrected by the only authority on it.
THINKING_ADAPTIVE = "adaptive"
THINKING_BUDGETED = "enabled"
# Used only for the budgeted spelling, where the API requires a number. Sized to
# be useful on a hard question without dominating a short turn's cost; the
# adaptive spelling lets the provider decide, which is why it is preferred.
THINKING_BUDGET_TOKENS = 2048
# What each model turned out to accept, keyed by model id and kept for the life
# of the process. Cleared by `reset_thinking_negotiation()` in tests.
_NEGOTIATED_THINKING: dict[str, str] = {}


class _ThinkingShapeRejected(Exception):
    """The provider refused this thinking spelling and named the other one."""

    def __init__(self, shape: str) -> None:
        super().__init__(f"thinking_shape_rejected:{shape}")
        self.shape = shape


def _rejected_thinking_shape(body: str) -> str | None:
    """The spelling the provider asked for, read out of its own refusal.

    Deliberately keyed on the provider's exact words rather than on "any 400
    mentioning thinking": a refusal that does *not* name an alternative is a
    real error and must stay one.
    """
    lowered = body.lower()
    if "adaptive thinking is not supported" in lowered:
        return THINKING_BUDGETED
    if '"thinking.type.enabled" is not supported' in lowered:
        return THINKING_ADAPTIVE
    return None


def reset_thinking_negotiation() -> None:
    """Forget what every model was observed to accept (tests only)."""
    _NEGOTIATED_THINKING.clear()


def _cache_control(cache_ttl: str | None) -> dict[str, Any] | None:
    if cache_ttl == "5m":
        return {"type": "ephemeral"}
    if cache_ttl == "1h":
        return {"type": "ephemeral", "ttl": "1h"}
    return None


def _map_status(status: int, *, model: str, body: str = "") -> Exception:
    # Checked first, and only for a 400 that names the other thinking spelling:
    # this is the one refusal the caller can answer itself (BUG-207 slice B).
    if status == 400:
        alternate = _rejected_thinking_shape(body)
        if alternate is not None:
            return _ThinkingShapeRejected(alternate)
    # Checked before auth and rate limiting: Anthropic answers an empty balance
    # with HTTP 400 on a perfectly valid key, so status alone would send the
    # owner to rotate a credential that is not the problem.
    # BUG-272 — a valid, identity-linked key with no workspace named. Checked
    # beside quota and for the same reason: the status is an ordinary 400 and
    # only the body says which 400 it is. There is no credential to rotate here.
    if needs_workspace_id(status, body):
        return ProviderWorkspaceRequiredError(f"provider_workspace_required:http_{status}")
    if is_quota_exhausted(status, body):
        return ProviderQuotaExhaustedError(f"provider_quota_exhausted:http_{status}")
    if status in {401, 403}:
        return ProviderAuthenticationError(f"provider_auth_failed:http_{status}")
    if status == 404:
        return ProviderModelNotFoundError(f"model_not_found:{model}")
    if status == 408:
        return ProviderTimeoutError("provider_timeout")
    if status == 429:
        return ProviderRateLimitError("provider_rate_limited")
    if status >= 500:
        return ProviderConnectionError(f"provider_unavailable:http_{status}")
    return ProviderConnectionError(f"provider_http_error:http_{status}")


def _json(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise ProviderResponseValidationError("invalid_json_response") from exc
    if not isinstance(data, dict):
        raise ProviderResponseValidationError("response_not_object")
    return data


def _to_anthropic_messages(
    messages: list[ModelMessage], *, include_images: bool = False
) -> tuple[str, list[dict[str, Any]]]:
    """Split Raiker messages into top-level system text and Anthropic messages."""
    system_parts: list[str] = []
    converted: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "system":
            system_parts.append(message.content)
            continue
        if message.role == "tool":
            blocks: list[dict[str, Any]] = [
                {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id,
                    "content": message.content,
                }
            ]
            role = "user"
        else:
            blocks = []
            if include_images and message.role == "user":
                blocks.extend(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image.media_type,
                            "data": image.base64_data,
                        },
                    }
                    for image in message.images
                )
            if message.content:
                blocks.append({"type": "text", "text": message.content})
            if message.role == "assistant":
                blocks.extend(
                    {
                        "type": "tool_use",
                        "id": call.call_id,
                        "name": call.tool_name,
                        "input": call.arguments,
                    }
                    for call in message.tool_calls
                )
            role = message.role
        if converted and converted[-1]["role"] == role:
            converted[-1]["content"].extend(blocks)
        elif blocks:
            converted.append({"role": role, "content": blocks})
    return "\n\n".join(part for part in system_parts if part), converted


def _stream_tool_event(raw: dict[str, str]) -> ModelStreamEvent:
    call_id = raw.get("id", "")
    name = raw.get("name", "")
    if not call_id or not name:
        raise ProviderStreamError("stream_tool_call_identity_missing")
    raw_json = raw.get("partial_json", "") or "{}"
    try:
        arguments = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ProviderStreamError("malformed_stream_tool_arguments") from exc
    if not isinstance(arguments, dict):
        raise ProviderStreamError("stream_tool_arguments_not_object")
    return ModelStreamEvent(
        event_type="tool_call_delta",
        tool_call_delta={
            "call_id": call_id,
            "tool_name": name,
            "arguments": arguments,
        },
    )


@dataclass
class AsyncAnthropicMessagesProvider:
    profile_id: str
    provider: str
    model: str
    endpoint: str
    capabilities: ModelCapabilities
    timeout: float = 120.0
    max_tokens: int = 1024
    models_path: str = "/v1/models"
    chat_path: str = "/v1/messages"
    extra_headers: Mapping[str, str] = field(default_factory=dict)
    client: httpx.AsyncClient | None = None

    def __post_init__(self) -> None:
        headers = {"anthropic-version": ANTHROPIC_VERSION, **dict(self.extra_headers)}
        self._client = self.client or httpx.AsyncClient(timeout=self.timeout, headers=headers)
        self._headers = headers
        self._owns_client = self.client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _url(self, path: str) -> str:
        return self.endpoint.rstrip("/") + "/" + path.lstrip("/")

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = {**self._headers, **kwargs.pop("headers", {})}
        try:
            response = await self._client.request(
                method, self._url(path), headers=headers, **kwargs
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("provider_timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderConnectionError("provider_connection_failed") from exc
        if response.status_code >= 400:
            raise _map_status(response.status_code, model=self.model, body=response.text)
        return response

    async def health(self, *, timeout: float = 1.0) -> ProviderHealth:
        try:
            response = await self._request("GET", self.models_path, timeout=timeout)
            models = self._parse_models(_json(response))
            available = any(item.id == self.model for item in models)
            return ProviderHealth(
                self.provider,
                available,
                True,
                "model_available" if available else "model_missing",
            )
        except (
            ProviderConnectionError,
            ProviderTimeoutError,
            ProviderAuthenticationError,
            ProviderRateLimitError,
            ProviderModelNotFoundError,
            ProviderResponseValidationError,
        ) as exc:
            return ProviderHealth(self.provider, False, False, type(exc).__name__)

    async def list_models(self) -> list[ProviderModelInfo]:
        response = await self._request("GET", self.models_path)
        return self._parse_models(_json(response))

    def _parse_models(self, data: dict[str, Any]) -> list[ProviderModelInfo]:
        raw = data.get("data")
        if not isinstance(raw, list):
            raise ProviderResponseValidationError("models_response_missing_data")
        models: list[ProviderModelInfo] = []
        for item in raw:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                # Anthropic publishes the usable context window per model
                # (`max_input_tokens`), so capacity never has to be guessed or
                # pinned in config. It publishes no price.
                metadata: dict[str, Any] = {}
                for key in ("max_input_tokens", "max_tokens"):
                    value = item.get(key)
                    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                        metadata[key] = value
                models.append(
                    ProviderModelInfo(id=item["id"], owned_by="anthropic", metadata=metadata)
                )
        return models

    def _payload(self, request: ModelRequest, *, stream: bool) -> dict[str, Any]:
        if request.response_schema is not None:
            raise ProviderUnsupportedCapabilityError("json_schema_unsupported")
        system, messages = _to_anthropic_messages(
            list(request.messages), include_images=self.capabilities.supports_vision
        )
        cache_control = _cache_control(request.cache_ttl)
        payload: dict[str, Any] = {
            "model": request.model or self.model,
            "max_tokens": request.max_tokens or self.max_tokens,
            "messages": messages,
        }
        if system:
            if cache_control is not None:
                payload["system"] = [
                    {"type": "text", "text": system, "cache_control": cache_control}
                ]
            else:
                payload["system"] = system
        elif cache_control is not None and messages:
            last_block = messages[-1]["content"][-1] if messages[-1]["content"] else None
            if isinstance(last_block, dict):
                last_block["cache_control"] = cache_control
        if stream:
            payload["stream"] = True
        if request.tools:
            if not self.capabilities.supports_tool_calls:
                raise ProviderUnsupportedCapabilityError("tool_calls_unsupported")
            payload["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters
                    or {"type": "object", "properties": {}},
                }
                for tool in request.tools
            ]
        thinking = self._thinking(request)
        if thinking is not None:
            payload["thinking"] = thinking
        return payload

    def _thinking(self, request: ModelRequest) -> dict[str, Any] | None:
        """The `thinking` block for this request, in the spelling this model takes.

        Returns None when reasoning was not asked for, or when this profile does
        not declare it — never a half-enabled block. The first request for a
        model uses the adaptive spelling the profile declares; after a refusal
        that named the other one, the recorded answer is used instead.
        """
        reasoning = request.reasoning
        if not (reasoning and reasoning.enabled and self.capabilities.supports_reasoning):
            return None
        model = request.model or self.model
        shape = _NEGOTIATED_THINKING.get(model, THINKING_ADAPTIVE)
        if shape == THINKING_BUDGETED:
            budget = reasoning.budget_tokens or THINKING_BUDGET_TOKENS
            # The budget has to leave room for the answer, and `max_tokens`
            # counts both. A budget that met or exceeded it would be refused.
            limit = request.max_tokens or self.max_tokens
            return {"type": "enabled", "budget_tokens": max(1024, min(budget, limit - 512))}
        thinking: dict[str, Any] = {"type": THINKING_ADAPTIVE}
        # `display: summarized` is what the owner should see: the provider's own
        # summary of its reasoning rather than its raw scratch text. Asked for
        # only where the profile declares the capability.
        if reasoning.summary and self.capabilities.supports_reasoning_summary:
            thinking["display"] = "summarized"
        return thinking

    @staticmethod
    def _record_thinking_shape(model: str, shape: str) -> None:
        _NEGOTIATED_THINKING[model] = shape

    @staticmethod
    def _cache_headers(request: ModelRequest) -> dict[str, str]:
        if request.cache_ttl == "1h":
            return {"anthropic-beta": EXTENDED_CACHE_TTL_BETA}
        return {}

    async def chat(self, request: ModelRequest) -> ModelResponse:
        for attempt in (0, 1):
            try:
                response = await self._request(
                    "POST",
                    self.chat_path,
                    json=self._payload(request, stream=False),
                    headers=self._cache_headers(request),
                )
            except _ThinkingShapeRejected as rejected:
                if attempt:
                    raise ProviderUnsupportedCapabilityError("reasoning_unsupported") from rejected
                self._record_thinking_shape(request.model or self.model, rejected.shape)
                continue
            return self._parse_chat(_json(response))
        raise ProviderUnsupportedCapabilityError("reasoning_unsupported")

    def _parse_chat(self, data: dict[str, Any]) -> ModelResponse:
        if data.get("type") == "error" or isinstance(data.get("error"), dict):
            raise ProviderConnectionError("provider_response_error")
        content = data.get("content")
        if not isinstance(content, list):
            raise ProviderResponseValidationError("missing_content")
        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls: list[ToolCallProposal] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text" and isinstance(block.get("text"), str):
                text_parts.append(block["text"])
            # BUG-207 — a `thinking` block is the model's own reasoning, kept
            # apart from its answer. The block's `signature` is the provider's
            # integrity marker for a thinking block that is replayed back to it;
            # it is not text and never reaches a surface.
            elif block_type == "thinking" and isinstance(block.get("thinking"), str):
                reasoning_parts.append(block["thinking"])
            elif block_type == "tool_use":
                raw_input = block.get("input")
                arguments: dict[str, Any] = raw_input if isinstance(raw_input, dict) else {}
                tool_calls.append(
                    ToolCallProposal(
                        call_id=str(block.get("id", "")),
                        tool_name=str(block.get("name", "")),
                        arguments=arguments,
                    )
                )
        stop_reason = str(data.get("stop_reason") or "end_turn")
        finish = _map_finish(stop_reason)
        if tool_calls:
            finish = "tool_calls"
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
        return ModelResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            finish_reason=finish,
            usage=usage,
            reasoning="".join(reasoning_parts),
        )

    async def stream_chat(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        if not self.capabilities.supports_streaming:
            raise ProviderUnsupportedCapabilityError("streaming_unsupported")
        try:
            async for event in self._stream_once(request):
                yield event
        except _ThinkingShapeRejected as rejected:
            # Nothing has been yielded yet: the refusal arrives on the response
            # status, before the first SSE line. Record the spelling the
            # provider named and make the request once more (BUG-207 slice B).
            self._record_thinking_shape(request.model or self.model, rejected.shape)
            try:
                async for event in self._stream_once(request):
                    yield event
            except _ThinkingShapeRejected as again:
                raise ProviderUnsupportedCapabilityError("reasoning_unsupported") from again

    async def _stream_once(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        usage_acc: dict[str, Any] = {}
        tool_blocks: dict[int, dict[str, str]] = {}
        finish_emitted = False
        try:
            async with self._client.stream(
                "POST",
                self._url(self.chat_path),
                headers={**self._headers, **self._cache_headers(request)},
                json=self._payload(request, stream=True),
                timeout=self.timeout,
            ) as response:
                if response.status_code >= 400:
                    # The error body has not been read yet on a streamed
                    # response; classification needs it and it is bounded.
                    raise _map_status(
                        response.status_code,
                        model=self.model,
                        body=(await response.aread()).decode("utf-8", "replace"),
                    )
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    try:
                        decoded = json.loads(data)
                    except json.JSONDecodeError as exc:
                        raise ProviderStreamError("malformed_sse_json") from exc
                    if not isinstance(decoded, dict):
                        continue
                    event_type = decoded.get("type")
                    if event_type == "error":
                        raise ProviderStreamError("provider_stream_error")
                    if event_type == "message_start":
                        message = decoded.get("message")
                        start_usage = message.get("usage") if isinstance(message, dict) else None
                        if isinstance(start_usage, dict):
                            usage_acc.update(start_usage)
                    elif event_type == "content_block_start":
                        index = decoded.get("index")
                        block = decoded.get("content_block")
                        if isinstance(index, int) and isinstance(block, dict) and block.get("type") == "tool_use":
                            call_id = block.get("id")
                            name = block.get("name")
                            if not isinstance(call_id, str) or not isinstance(name, str):
                                raise ProviderStreamError("stream_tool_call_identity_missing")
                            initial = block.get("input")
                            partial_json = json.dumps(initial) if isinstance(initial, dict) and initial else ""
                            tool_blocks[index] = {
                                "id": call_id,
                                "name": name,
                                "partial_json": partial_json,
                            }
                    elif event_type == "content_block_delta":
                        index = decoded.get("index")
                        delta = decoded.get("delta")
                        if not isinstance(delta, dict):
                            continue
                        if delta.get("type") == "text_delta":
                            text = delta.get("text")
                            if isinstance(text, str) and text:
                                yield ModelStreamEvent(event_type="text_delta", text_delta=text)
                        # BUG-207 slice B — the branch that was missing. Raiker
                        # asked for extended thinking, the provider sent it, and
                        # every chunk fell through this chain unread. A
                        # `signature_delta` arrives on the same block and is
                        # deliberately *not* handled: it is an integrity marker
                        # for replaying the block, not something to show anyone.
                        elif delta.get("type") == "thinking_delta":
                            thought = delta.get("thinking")
                            if isinstance(thought, str) and thought:
                                yield ModelStreamEvent(
                                    event_type="reasoning_delta", reasoning_delta=thought
                                )
                        elif delta.get("type") == "input_json_delta" and isinstance(index, int):
                            partial = delta.get("partial_json")
                            if isinstance(partial, str):
                                block = tool_blocks.get(index)
                                if block is None:
                                    raise ProviderStreamError("stream_tool_delta_without_start")
                                block["partial_json"] += partial
                    elif event_type == "content_block_stop":
                        index = decoded.get("index")
                        if isinstance(index, int) and index in tool_blocks:
                            yield _stream_tool_event(tool_blocks.pop(index))
                    elif event_type == "message_delta":
                        delta = decoded.get("delta")
                        delta_usage = decoded.get("usage")
                        if isinstance(delta_usage, dict):
                            usage_acc.update(delta_usage)
                        stop = delta.get("stop_reason") if isinstance(delta, dict) else None
                        if isinstance(stop, str) and stop:
                            if tool_blocks:
                                for index in sorted(tool_blocks):
                                    yield _stream_tool_event(tool_blocks[index])
                                tool_blocks.clear()
                            if usage_acc:
                                yield ModelStreamEvent(
                                    event_type="usage", metadata={"usage": dict(usage_acc)}
                                )
                            yield ModelStreamEvent(
                                event_type="finish", finish_reason=_map_finish(stop)
                            )
                            finish_emitted = True
                    elif event_type == "message_stop":
                        if not finish_emitted:
                            if tool_blocks:
                                for index in sorted(tool_blocks):
                                    yield _stream_tool_event(tool_blocks[index])
                            if usage_acc:
                                yield ModelStreamEvent(
                                    event_type="usage", metadata={"usage": dict(usage_acc)}
                                )
                            yield ModelStreamEvent(event_type="finish", finish_reason="stop")
                        return
        except asyncio.CancelledError:
            raise
        except ProviderStreamError:
            raise
        # BUG-207 slice B — this one is answerable by the caller, so it must
        # reach it rather than being flattened into a generic stream failure.
        # Nothing has been yielded when it is raised: the refusal arrives on the
        # response status, before the first SSE line.
        except _ThinkingShapeRejected:
            raise
        except Exception as exc:
            # BUG-72 — a failure the status mapper or the transport already
            # classified keeps its own code; only an unclassified one becomes a
            # stream failure, and it carries its exception type with it.
            raised = stream_failure(exc)
            if raised is exc:
                raise
            raise raised from exc

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        raise ProviderUnsupportedCapabilityError("embeddings_unsupported")
