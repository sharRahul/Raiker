from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

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
    is_quota_exhausted,
    stream_failure,
)
from raiker.models.health import ProviderHealth
from raiker.models.providers.llama_cpp_server import _parse_text_json_tool_calls, _parse_tool_calls


def _join(base: str, path: str) -> str:
    parts = urlsplit(base)
    base_parts = [part for part in parts.path.split("/") if part]
    path_parts = [part for part in path.split("/") if part]
    if base_parts and path_parts and base_parts[-1] == "v1" and path_parts[0] == "v1":
        path_parts = path_parts[1:]
    joined = "/" + "/".join([*base_parts, *path_parts])
    return urlunsplit((parts.scheme, parts.netloc, joined, "", ""))


def _join_origin(base: str, path: str) -> str:
    """Join a provider-native path at the endpoint origin, outside ``/v1``."""
    parts = urlsplit(base)
    joined = "/" + "/".join(part for part in path.split("/") if part)
    return urlunsplit((parts.scheme, parts.netloc, joined, "", ""))


def _map_status(status: int, *, model: str, body: str = "") -> Exception:
    # OpenAI reports an exhausted allowance as 429 `insufficient_quota` and
    # OpenAI-compatible routers as a bare 402. Neither is fixed by waiting, so
    # neither may be reported as a rate limit.
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


def _model_facts_metadata(item: Mapping[str, Any]) -> dict[str, Any]:
    """Capacity and price facts an OpenAI-compatible catalogue may publish.

    Most endpoints publish neither and return an empty dict. OpenRouter is the
    exception: it exposes `context_length` and a `pricing` block quoted per
    single token. Both are passed through untouched — unit conversion belongs to
    `raiker.models.pricing`, which owns the per-million-token convention.
    """
    metadata: dict[str, Any] = {}
    context_length = _context_length(item)
    if context_length is not None:
        metadata["context_length"] = context_length
    pricing = item.get("pricing")
    if isinstance(pricing, Mapping):
        quoted = {
            key: pricing[key]
            for key in ("prompt", "completion", "currency")
            if isinstance(pricing.get(key), (str, int, float))
            and not isinstance(pricing.get(key), bool)
        }
        if "prompt" in quoted and "completion" in quoted:
            metadata["pricing"] = quoted
    return metadata


_CONTEXT_KEYS = (
    "context_length",
    "max_context_length",
    "context_window",
    "context_window_tokens",
    "max_input_tokens",
    "n_ctx",
    "num_ctx",
)


def _positive_context(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed > 0 else None
    return None


def _context_length(value: Any, *, depth: int = 0) -> int | None:
    """Read common, bounded local-runtime capacity fields without guessing."""
    if depth > 4:
        return None
    if isinstance(value, Mapping):
        for key in _CONTEXT_KEYS:
            parsed = _positive_context(value.get(key))
            if parsed is not None:
                return parsed
        # Ollama exposes architecture-qualified keys such as
        # ``llama.context_length`` in ``model_info``.
        for key, candidate in value.items():
            if isinstance(key, str) and key.endswith(".context_length"):
                parsed = _positive_context(candidate)
                if parsed is not None:
                    return parsed
        for key in (
            "model_info",
            "capabilities",
            "config",
            "loaded_context",
            "loaded_instances",
            "instances",
            "default_generation_settings",
        ):
            parsed = _context_length(value.get(key), depth=depth + 1)
            if parsed is not None:
                return parsed
    if isinstance(value, list):
        for candidate in value[:100]:
            parsed = _context_length(candidate, depth=depth + 1)
            if parsed is not None:
                return parsed
    return None


def _ollama_parameter_context(parameters: Any) -> int | None:
    if not isinstance(parameters, str):
        return None
    match = re.search(r"(?m)^\s*num_ctx\s+(\d+)\s*$", parameters)
    return _positive_context(match.group(1)) if match else None


def _model_identifier(value: Mapping[str, Any]) -> str | None:
    for key in ("id", "model", "name", "model_key", "key"):
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def _raise_in_band_error(value: Any) -> None:
    if isinstance(value, dict):
        code = value.get("code")
        suffix = f":{code}" if isinstance(code, int | str) else ""
        raise ProviderConnectionError(f"provider_response_error{suffix}")


def _content_text(content: Any) -> tuple[str, bool]:
    """Normalize OpenAI-compatible string/part-array content without leaking shape."""
    if isinstance(content, str):
        return content, False
    if not isinstance(content, list):
        return "", False
    parts: list[str] = []
    refused = False
    for part in content:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type")
        if part_type in {"text", "output_text"} and isinstance(part.get("text"), str):
            parts.append(part["text"])
        elif part_type == "refusal" and isinstance(part.get("refusal"), str):
            parts.append(part["refusal"])
            refused = True
    return "".join(parts), refused


def _finish_reason(raw: Any, *, has_tools: bool = False, refused: bool = False) -> str:
    if has_tools:
        return "tool_calls"
    if refused or raw in {"content_filter", "error"}:
        return "error"
    return raw if raw in {"stop", "length", "tool_calls"} else "stop"


def _tool_call_events(raw_calls: dict[int, dict[str, str]]) -> list[ModelStreamEvent]:
    events: list[ModelStreamEvent] = []
    for index in sorted(raw_calls):
        raw = raw_calls[index]
        name = raw.get("name", "")
        if not name:
            raise ProviderStreamError("stream_tool_call_missing_name")
        raw_arguments = raw.get("arguments", "") or "{}"
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            raise ProviderStreamError("malformed_stream_tool_arguments") from exc
        if not isinstance(arguments, dict):
            raise ProviderStreamError("stream_tool_arguments_not_object")
        events.append(
            ModelStreamEvent(
                event_type="tool_call_delta",
                tool_call_delta={
                    "call_id": raw.get("id") or f"call_{index}",
                    "tool_name": name,
                    "arguments": arguments,
                },
            )
        )
    return events


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
        self._headers = dict(self.extra_headers)
        self._client = self.client or httpx.AsyncClient(
            timeout=self.timeout, headers=self._headers
        )
        self._owns_client = self.client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = {**self._headers, **kwargs.pop("headers", {})}
        try:
            response = await self._client.request(
                method, _join(self.endpoint, path), headers=headers, **kwargs
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
            path = self.health_path if self.provider == "llama.cpp" else self.models_path
            response = await self._request("GET", path, timeout=timeout)
            detail = "reachable"
            if path == self.models_path:
                models = self._parse_models(_json(response))
                detail = "model_available" if any(item.id == self.model for item in models) else "model_missing"
                return ProviderHealth(self.provider, detail == "model_available", True, detail)
            return ProviderHealth(self.provider, True, True, detail)
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
        models = self._parse_models(_json(response))
        return await self._with_local_context(models)

    async def _native_request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Read optional metadata from the same local runtime origin.

        These reads never introduce a new host: `_join_origin` retains the
        already policy-checked scheme and authority and only replaces `/v1`.
        """
        headers = {**self._headers, **kwargs.pop("headers", {})}
        response = await self._client.request(
            method, _join_origin(self.endpoint, path), headers=headers, **kwargs
        )
        if response.status_code >= 400:
            raise _map_status(response.status_code, model=self.model, body=response.text)
        return _json(response)

    async def _with_local_context(
        self, models: list[ProviderModelInfo]
    ) -> list[ProviderModelInfo]:
        """Enrich local catalogues with their effective context capacity.

        Provider-native metadata is supplementary: an old runtime, disabled
        endpoint, or unexpected response leaves the ordinary model catalogue
        usable and the capacity honestly unknown.
        """
        capacities: dict[str, int] = {}
        try:
            if self.provider == "ollama":
                try:
                    running = await self._native_request("GET", "/api/ps")
                except Exception:  # noqa: BLE001 — older Ollama can still answer /api/show
                    running = {}
                rows = running.get("models")
                if isinstance(rows, list):
                    for row in rows:
                        if not isinstance(row, Mapping):
                            continue
                        identifier = _model_identifier(row)
                        capacity = _context_length(row)
                        if identifier and capacity:
                            capacities[identifier] = capacity
                for model in models:
                    if model.id in capacities:
                        continue
                    try:
                        detail = await self._native_request(
                            "POST", "/api/show", json={"model": model.id}
                        )
                    except Exception:  # noqa: BLE001 — one model must not fail the catalogue
                        continue
                    capacity = _ollama_parameter_context(detail.get("parameters")) or _context_length(detail)
                    if capacity:
                        capacities[model.id] = capacity
            elif self.provider == "lm-studio":
                catalogue = await self._native_request("GET", "/api/v1/models")
                rows = catalogue.get("models") or catalogue.get("data")
                if isinstance(rows, list):
                    for row in rows:
                        if not isinstance(row, Mapping):
                            continue
                        identifier = _model_identifier(row)
                        capacity = _context_length(row)
                        if identifier and capacity:
                            capacities[identifier] = capacity
            elif self.provider == "llama.cpp":
                props = await self._native_request("GET", "/props")
                capacity = _context_length(props)
                if capacity:
                    capacities.update({model.id: capacity for model in models})
        except Exception:  # noqa: BLE001 — native discovery is best-effort
            return models

        return [
            ProviderModelInfo(
                id=model.id,
                owned_by=model.owned_by,
                metadata={
                    **dict(model.metadata),
                    **({"context_length": capacities[model.id]} if model.id in capacities else {}),
                },
            )
            for model in models
        ]

    def _parse_models(self, data: dict[str, Any]) -> list[ProviderModelInfo]:
        _raise_in_band_error(data.get("error"))
        raw = data.get("data")
        if not isinstance(raw, list):
            raise ProviderResponseValidationError("models_response_missing_data")
        models: list[ProviderModelInfo] = []
        for item in raw:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                owned_by = item.get("owned_by") if isinstance(item.get("owned_by"), str) else None
                models.append(
                    ProviderModelInfo(
                        id=item["id"], owned_by=owned_by, metadata=_model_facts_metadata(item)
                    )
                )
        return models

    def _message_dict(self, message: ModelMessage) -> dict[str, Any]:
        if not (message.images and message.role == "user" and self.capabilities.supports_vision):
            return message.to_dict()
        parts: list[dict[str, Any]] = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:{image.media_type};base64,{image.base64_data}"},
            }
            for image in message.images
        ]
        if message.content:
            parts.append({"type": "text", "text": message.content})
        serialized = message.to_dict()
        serialized["content"] = parts
        return serialized

    def _payload(self, request: ModelRequest, *, stream: bool) -> dict[str, Any]:
        messages = [self._message_dict(message) for message in request.messages]
        payload: dict[str, Any] = {
            "model": request.model or self.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": stream,
        }
        if request.tools:
            if not self.capabilities.supports_tool_calls:
                raise ProviderUnsupportedCapabilityError("tool_calls_unsupported")
            payload["tools"] = [tool.to_openai_tool() for tool in request.tools]
            payload["tool_choice"] = "auto"
        if request.response_schema is not None:
            if not self.capabilities.supports_json_schema:
                raise ProviderUnsupportedCapabilityError("json_schema_unsupported")
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.response_schema_name,
                    "strict": True,
                    "schema": request.response_schema,
                },
            }
        if request.cache_ttl and self.provider == "llama.cpp":
            # OpenAI prompt caching is automatic. Its Chat Completions API does
            # not accept Anthropic-style message breakpoints or the obsolete
            # `prompt_cache_options` envelope; sending either makes an otherwise
            # valid tool call fail with HTTP 400. llama.cpp's explicit switch is
            # the only OpenAI-compatible hint used here.
            payload["cache_prompt"] = True
        if stream and self.provider in {"openai", "ollama"}:
            payload["stream_options"] = {"include_usage": True}
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
        response = await self._request(
            "POST", self.chat_path, json=self._payload(request, stream=False)
        )
        return self._parse_chat(_json(response))

    def _parse_chat(self, data: dict[str, Any]) -> ModelResponse:
        _raise_in_band_error(data.get("error"))
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ProviderResponseValidationError("missing_choices")
        choice = choices[0]
        _raise_in_band_error(choice.get("error"))
        raw_message = choice.get("message")
        message: dict[str, Any] = raw_message if isinstance(raw_message, dict) else {}
        text, content_refusal = _content_text(message.get("content"))
        direct_refusal = message.get("refusal")
        refused = content_refusal or isinstance(direct_refusal, str)
        if isinstance(direct_refusal, str) and direct_refusal and direct_refusal not in text:
            text = f"{text}{direct_refusal}"
        tool_calls = _parse_tool_calls(message.get("tool_calls"))
        if not tool_calls and self.tool_call_mode in {
            "text_json",
            "native_or_text_json",
            "native_or_json_schema",
        }:
            tool_calls = _parse_text_json_tool_calls(text)
            if tool_calls:
                text = ""
        finish = _finish_reason(
            choice.get("finish_reason"), has_tools=bool(tool_calls), refused=refused
        )
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
        return ModelResponse(text=text, tool_calls=tool_calls, finish_reason=finish, usage=usage)

    async def stream_chat(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        if not self.capabilities.supports_streaming:
            raise ProviderUnsupportedCapabilityError("streaming_unsupported")
        tool_calls: dict[int, dict[str, str]] = {}
        finish_emitted = False
        try:
            async with self._client.stream(
                "POST",
                _join(self.endpoint, self.chat_path),
                headers=self._headers,
                json=self._payload(request, stream=True),
                timeout=self.timeout,
            ) as response:
                if response.status_code >= 400:
                    # Streamed responses have not read their body yet, and the
                    # classification below needs it.
                    raise _map_status(
                        response.status_code,
                        model=self.model,
                        body=(await response.aread()).decode("utf-8", "replace"),
                    )
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        if not finish_emitted:
                            for event in _tool_call_events(tool_calls):
                                yield event
                            yield ModelStreamEvent(event_type="finish", finish_reason="stop")
                        return
                    try:
                        decoded = json.loads(data)
                    except json.JSONDecodeError as exc:
                        raise ProviderStreamError("malformed_sse_json") from exc
                    if not isinstance(decoded, dict):
                        continue
                    _raise_in_band_error(decoded.get("error"))
                    usage = decoded.get("usage")
                    choices = decoded.get("choices")
                    if isinstance(usage, dict) and (not isinstance(choices, list) or not choices):
                        yield ModelStreamEvent(event_type="usage", metadata={"usage": usage})
                        continue
                    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                        continue
                    choice = choices[0]
                    _raise_in_band_error(choice.get("error"))
                    raw_delta = choice.get("delta")
                    delta: dict[str, Any] = raw_delta if isinstance(raw_delta, dict) else {}
                    text, content_refusal = _content_text(delta.get("content"))
                    direct_refusal = delta.get("refusal")
                    refused = content_refusal or isinstance(direct_refusal, str)
                    if isinstance(direct_refusal, str) and direct_refusal and direct_refusal not in text:
                        text = f"{text}{direct_refusal}"
                    if text:
                        yield ModelStreamEvent(event_type="text_delta", text_delta=text)
                    raw_tool_calls = delta.get("tool_calls")
                    if isinstance(raw_tool_calls, list):
                        for position, raw_call in enumerate(raw_tool_calls):
                            if not isinstance(raw_call, dict):
                                continue
                            raw_index = raw_call.get("index")
                            index = raw_index if isinstance(raw_index, int) else position
                            current = tool_calls.setdefault(
                                index, {"id": "", "name": "", "arguments": ""}
                            )
                            call_id = raw_call.get("id")
                            if isinstance(call_id, str):
                                current["id"] = call_id
                            function = raw_call.get("function")
                            if isinstance(function, dict):
                                name = function.get("name")
                                arguments = function.get("arguments")
                                if isinstance(name, str):
                                    current["name"] += name
                                if isinstance(arguments, str):
                                    current["arguments"] += arguments
                    raw_finish = choice.get("finish_reason")
                    if isinstance(raw_finish, str):
                        for event in _tool_call_events(tool_calls):
                            yield event
                        finish = _finish_reason(
                            raw_finish, has_tools=bool(tool_calls), refused=refused
                        )
                        yield ModelStreamEvent(event_type="finish", finish_reason=finish)
                        finish_emitted = True
        except asyncio.CancelledError:
            raise
        except ProviderStreamError:
            raise
        except Exception as exc:
            # BUG-72 — see the same guard in the Anthropic adapter: a classified
            # provider error keeps its own reason code instead of collapsing
            # into one that names only the stream.
            raised = stream_failure(exc)
            if raised is exc:
                raise
            raise raised from exc

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        if not self.capabilities.supports_embeddings:
            raise ProviderUnsupportedCapabilityError("embeddings_unsupported")
        response = await self._request(
            "POST",
            self.embeddings_path,
            json={"model": request.model, "input": request.text},
        )
        data = _json(response)
        _raise_in_band_error(data.get("error"))
        rows = data.get("data")
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise ProviderResponseValidationError("embedding_response_missing_data")
        vector = rows[0].get("embedding")
        if not isinstance(vector, list) or not all(
            isinstance(value, int | float) and not isinstance(value, bool) for value in vector
        ):
            raise ProviderResponseValidationError("embedding_vector_invalid")
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
        return EmbeddingResponse(
            vector=[float(value) for value in vector], model=request.model, usage=usage
        )
