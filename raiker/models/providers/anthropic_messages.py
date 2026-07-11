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
    ProviderRateLimitError,
    ProviderResponseValidationError,
    ProviderStreamError,
    ProviderTimeoutError,
    ProviderUnsupportedCapabilityError,
)
from raiker.models.health import ProviderHealth

# Anthropic stop_reason → Raiker contract finish_reason (contracts.FINISH_REASONS).
# Both the buffered and the streaming path must map through this table — the raw
# Anthropic vocabulary ("end_turn", "tool_use", …) is not valid in ModelResponse.
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

# Native Anthropic Messages API adapter over raw httpx — Raiker deliberately
# owns its transport (no SDK wrappers; httpx.AsyncClient is the only runtime
# HTTP dependency). Model outputs and tool calls remain untrusted proposals
# that must pass Raiker validation, policy, and approval downstream.
#
# API shape (Messages API, anthropic-version 2023-06-01):
# - POST /v1/messages: system is a top-level field; messages alternate
#   user/assistant with content blocks; tools use {name, description,
#   input_schema}; tool results are user-role tool_result blocks.
# - Current-generation models (Opus 4.6+) use adaptive thinking
#   ({"type": "adaptive"}) and reject sampling params (temperature/top_p),
#   so this adapter never sends temperature.

ANTHROPIC_VERSION = "2023-06-01"

# Beta header required to opt into the 1-hour extended prompt-cache TTL. The
# default 5-minute ephemeral cache needs no beta header.
EXTENDED_CACHE_TTL_BETA = "extended-cache-ttl-2025-04-11"


def _cache_control(cache_ttl: str | None) -> dict[str, Any] | None:
    """Anthropic ``cache_control`` block for a requested TTL, or None if caching is off.

    ``"5m"`` → the default ephemeral cache (no ``ttl`` field); ``"1h"`` → the
    1-hour extended cache. Any other value disables caching.
    """
    if cache_ttl == "5m":
        return {"type": "ephemeral"}
    if cache_ttl == "1h":
        return {"type": "ephemeral", "ttl": "1h"}
    return None


def _map_status(status: int, *, model: str) -> Exception:
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
    """Split Raiker messages into (system_text, anthropic messages).

    Tool-role messages become user-role ``tool_result`` blocks; consecutive
    same-role turns are merged because the Messages API requires alternation.
    Image attachments become base64 image blocks only when ``include_images``
    (i.e. the profile declares vision support); otherwise they are dropped
    fail-closed so a non-vision model is never sent an unsupported block.
    """
    system_parts: list[str] = []
    converted: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "system":
            system_parts.append(message.content)
            continue
        if message.role == "tool":
            blocks: list[dict[str, Any]] = [{
                "type": "tool_result",
                "tool_use_id": message.tool_call_id or "",
                "content": message.content,
            }]
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
                # The tool_use blocks this assistant turn made. Required: a
                # later tool_result must reference a tool_use id from a prior
                # assistant message or the API rejects the whole request.
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
        return self.endpoint.rstrip("/") + path

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = {**self._headers, **kwargs.pop("headers", {})}
        try:
            response = await self._client.request(method, self._url(path), headers=headers, **kwargs)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("provider_timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderConnectionError("provider_connection_failed") from exc
        if response.status_code >= 400:
            raise _map_status(response.status_code, model=self.model)
        return response

    async def health(self, *, timeout: float = 1.0) -> ProviderHealth:
        try:
            response = await self._request("GET", self.models_path, timeout=timeout)
            models = self._parse_models(_json(response))
            available = any(m.id == self.model for m in models)
            return ProviderHealth(self.provider, available, True, "model_available" if available else "model_missing")
        except (ProviderConnectionError, ProviderTimeoutError, ProviderAuthenticationError,
                ProviderModelNotFoundError, ProviderResponseValidationError) as exc:
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
                models.append(ProviderModelInfo(id=item["id"], owned_by="anthropic", metadata={}))
        return models

    def _payload(self, request: ModelRequest, *, stream: bool) -> dict[str, Any]:
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
                # Break the cache at the end of the (stable) system prompt. Per the
                # Anthropic cache ordering (tools → system → messages) this reuses
                # tools + system across turns within the TTL. System becomes a list
                # of content blocks so the breakpoint can ride the last block.
                payload["system"] = [{"type": "text", "text": system, "cache_control": cache_control}]
            else:
                payload["system"] = system
        elif cache_control is not None and messages:
            # No system prompt: fall back to a breakpoint on the last content block
            # of the last message so at least the message prefix is cached.
            last_block = messages[-1]["content"][-1] if messages[-1]["content"] else None
            if isinstance(last_block, dict):
                last_block["cache_control"] = cache_control
        if stream:
            payload["stream"] = True
        if request.tools and self.capabilities.supports_tool_calls:
            payload["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters or {"type": "object", "properties": {}},
                }
                for t in request.tools
            ]
        reasoning = request.reasoning
        if reasoning and reasoning.enabled and self.capabilities.supports_reasoning:
            thinking: dict[str, Any] = {"type": "adaptive"}
            if reasoning.summary and self.capabilities.supports_reasoning_summary:
                thinking["display"] = "summarized"
            payload["thinking"] = thinking
        return payload

    @staticmethod
    def _cache_headers(request: ModelRequest) -> dict[str, str]:
        """Per-request beta header needed only for the 1-hour extended cache TTL."""
        if request.cache_ttl == "1h":
            return {"anthropic-beta": EXTENDED_CACHE_TTL_BETA}
        return {}

    async def chat(self, request: ModelRequest) -> ModelResponse:
        response = await self._request(
            "POST", self.chat_path,
            json=self._payload(request, stream=False),
            headers=self._cache_headers(request),
        )
        return self._parse_chat(_json(response))

    def _parse_chat(self, data: dict[str, Any]) -> ModelResponse:
        content = data.get("content")
        if not isinstance(content, list):
            raise ProviderResponseValidationError("missing_content")
        text_parts: list[str] = []
        tool_calls: list[ToolCallProposal] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text" and isinstance(block.get("text"), str):
                text_parts.append(block["text"])
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
            # thinking blocks are intentionally dropped: private chain-of-thought
            # is never surfaced through Raiker contracts.
        stop_reason = str(data.get("stop_reason") or "end_turn")
        finish = _map_finish(stop_reason)
        if tool_calls:
            finish = "tool_calls"
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
        return ModelResponse(text="".join(text_parts), tool_calls=tool_calls, finish_reason=finish, usage=usage)

    async def stream_chat(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        usage_acc: dict[str, Any] = {}
        try:
            async with self._client.stream(
                "POST", self._url(self.chat_path),
                headers={**self._headers, **self._cache_headers(request)},
                json=self._payload(request, stream=True),
            ) as response:
                if response.status_code >= 400:
                    raise _map_status(response.status_code, model=self.model)
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
                    if event_type == "message_start":
                        # Input + cache usage arrives up front; output tokens come
                        # in message_delta. Merge and surface once so cache-hit
                        # metrics survive the streamed path.
                        message = decoded.get("message")
                        start_usage = message.get("usage") if isinstance(message, dict) else None
                        if isinstance(start_usage, dict):
                            usage_acc.update(start_usage)
                    elif event_type == "content_block_delta":
                        delta = decoded.get("delta")
                        if isinstance(delta, dict) and delta.get("type") == "text_delta":
                            text = delta.get("text")
                            if isinstance(text, str) and text:
                                yield ModelStreamEvent(event_type="text_delta", text_delta=text)
                    elif event_type == "message_delta":
                        delta = decoded.get("delta")
                        delta_usage = decoded.get("usage")
                        if isinstance(delta_usage, dict):
                            usage_acc.update(delta_usage)
                        stop = delta.get("stop_reason") if isinstance(delta, dict) else None
                        if isinstance(stop, str) and stop:
                            if usage_acc:
                                yield ModelStreamEvent(event_type="usage", metadata={"usage": dict(usage_acc)})
                            yield ModelStreamEvent(event_type="finish", finish_reason=_map_finish(stop))
                    elif event_type == "message_stop":
                        return
        except asyncio.CancelledError:
            raise
        except ProviderStreamError:
            raise
        except Exception as exc:
            if isinstance(exc, (ProviderConnectionError, ProviderTimeoutError,
                                ProviderAuthenticationError, ProviderRateLimitError,
                                ProviderModelNotFoundError)):
                raise ProviderStreamError(type(exc).__name__) from exc
            raise

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        raise ProviderUnsupportedCapabilityError("embeddings_unsupported")
