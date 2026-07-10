from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from raiker.models.contracts import (
    EmbeddingRequest,
    EmbeddingResponse,
    ModelCapabilities,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ProviderModelInfo,
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
from raiker.models.providers.llama_cpp_server import _parse_text_json_tool_calls, _parse_tool_calls


def _join(base: str, path: str) -> str:
    parts = urlsplit(base)
    base_parts = [p for p in parts.path.split("/") if p]
    path_parts = [p for p in path.split("/") if p]
    if base_parts and path_parts and base_parts[-1] == "v1" and path_parts[0] == "v1":
        path_parts = path_parts[1:]
    joined = "/" + "/".join([*base_parts, *path_parts])
    return urlunsplit((parts.scheme, parts.netloc, joined, "", ""))


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


@dataclass
class AsyncOpenAICompatibleProvider:
    profile_id: str
    provider: str
    model: str
    endpoint: str
    capabilities: ModelCapabilities
    timeout: float = 120.0
    temperature: float = 0.2
    max_tokens: int = 1024
    tool_call_mode: str = "text_json"
    health_path: str = "/health"
    models_path: str = "/v1/models"
    chat_path: str = "/v1/chat/completions"
    embeddings_path: str = "/v1/embeddings"
    extra_headers: Mapping[str, str] = field(default_factory=dict)
    client: httpx.AsyncClient | None = None

    def __post_init__(self) -> None:
        self._client = self.client or httpx.AsyncClient(timeout=self.timeout, headers=dict(self.extra_headers))
        self._owns_client = self.client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self._client.request(method, _join(self.endpoint, path), **kwargs)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("provider_timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderConnectionError("provider_connection_failed") from exc
        if response.status_code >= 400:
            raise _map_status(response.status_code, model=self.model)
        return response

    async def health(self, *, timeout: float = 1.0) -> ProviderHealth:
        try:
            path = self.health_path if self.provider == "llama.cpp" else self.models_path
            response = await self._request("GET", path, timeout=timeout)
            detail = "reachable"
            if path == self.models_path:
                models = self._parse_models(_json(response))
                detail = "model_available" if any(m.id == self.model for m in models) else "model_missing"
                return ProviderHealth(self.provider, detail == "model_available", True, detail)
            return ProviderHealth(self.provider, True, True, detail)
        except (ProviderConnectionError, ProviderTimeoutError, ProviderAuthenticationError, ProviderModelNotFoundError, ProviderResponseValidationError) as exc:
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
                owned_by = item.get("owned_by") if isinstance(item.get("owned_by"), str) else None
                models.append(ProviderModelInfo(id=item["id"], owned_by=owned_by, metadata={}))
        return models

    def _payload(self, request: ModelRequest, *, stream: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model or self.model,
            "messages": [m.to_dict() for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": stream,
        }
        if request.tools and self.capabilities.supports_tool_calls:
            payload["tools"] = [t.to_openai_tool() for t in request.tools]
            payload["tool_choice"] = "auto"
        reasoning = request.reasoning
        if reasoning and reasoning.enabled and self.capabilities.supports_reasoning:
            if reasoning.effort and self.capabilities.supports_reasoning_effort:
                payload["reasoning_effort"] = reasoning.effort
            if reasoning.budget_tokens and self.capabilities.supports_reasoning_budget_tokens:
                payload["reasoning_budget_tokens"] = reasoning.budget_tokens
            if reasoning.summary and self.capabilities.supports_reasoning_summary:
                payload["reasoning_summary"] = reasoning.summary
        return payload

    async def chat(self, request: ModelRequest) -> ModelResponse:
        response = await self._request("POST", self.chat_path, json=self._payload(request, stream=False))
        return self._parse_chat(_json(response))

    def _parse_chat(self, data: dict[str, Any]) -> ModelResponse:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ProviderResponseValidationError("missing_choices")
        choice = choices[0]
        raw_message = choice.get("message")
        message: dict[str, Any] = raw_message if isinstance(raw_message, dict) else {}
        text = str(message.get("content") or "")
        tool_calls = _parse_tool_calls(message.get("tool_calls"))
        if not tool_calls and self.tool_call_mode in {"text_json", "native_or_text_json", "native_or_json_schema"}:
            tool_calls = _parse_text_json_tool_calls(text)
            if tool_calls:
                text = ""
        raw_finish = str(choice.get("finish_reason") or "stop")
        finish = "tool_calls" if tool_calls else (raw_finish if raw_finish in {"stop", "length"} else "stop")
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
        return ModelResponse(text=text, tool_calls=tool_calls, finish_reason=finish, usage=usage)

    async def stream_chat(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        try:
            async with self._client.stream("POST", _join(self.endpoint, self.chat_path), json=self._payload(request, stream=True)) as response:
                if response.status_code >= 400:
                    raise _map_status(response.status_code, model=self.model)
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        yield ModelStreamEvent(event_type="finish", finish_reason="stop")
                        return
                    try:
                        decoded = json.loads(data)
                    except json.JSONDecodeError as exc:
                        raise ProviderStreamError("malformed_sse_json") from exc
                    choices = decoded.get("choices") if isinstance(decoded, dict) else None
                    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                        continue
                    choice = choices[0]
                    raw_delta = choice.get("delta")
                    delta: dict[str, Any] = raw_delta if isinstance(raw_delta, dict) else {}
                    text = delta.get("content") if isinstance(delta.get("content"), str) else ""
                    finish = choice.get("finish_reason") if isinstance(choice.get("finish_reason"), str) else None
                    if text:
                        yield ModelStreamEvent(event_type="text_delta", text_delta=text)
                    if finish:
                        # Map protocol vocabulary ("content_filter", "function_call", …)
                        # into the contract's finish reasons — raw passthrough would
                        # fail ModelResponse validation downstream.
                        yield ModelStreamEvent(
                            event_type="finish",
                            finish_reason=finish if finish in {"stop", "length", "tool_calls"} else "stop",
                        )
        except asyncio.CancelledError:
            raise
        except ProviderStreamError:
            raise
        except Exception as exc:
            if isinstance(exc, (ProviderConnectionError, ProviderTimeoutError, ProviderAuthenticationError, ProviderRateLimitError, ProviderModelNotFoundError)):
                raise ProviderStreamError(type(exc).__name__) from exc
            raise

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        if not self.capabilities.supports_embeddings:
            raise ProviderUnsupportedCapabilityError("embeddings_unsupported")
        response = await self._request("POST", self.embeddings_path, json={"model": request.model or self.model, "input": request.text})
        data = _json(response)
        rows = data.get("data")
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise ProviderResponseValidationError("embedding_response_missing_data")
        vector = rows[0].get("embedding")
        if not isinstance(vector, list) or not all(isinstance(v, int | float) for v in vector):
            raise ProviderResponseValidationError("embedding_vector_invalid")
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
        return EmbeddingResponse(vector=[float(v) for v in vector], model=self.model, usage=usage)
