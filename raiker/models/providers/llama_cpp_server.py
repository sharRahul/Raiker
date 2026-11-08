from __future__ import annotations

import http.client
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from raiker.models.contracts import (
    ModelMessage,
    ModelResponse,
    ToolCallProposal,
    ToolSpec,
    new_call_id,
)
from raiker.models.exceptions import ProviderConnectionError, ProviderResponseValidationError
from raiker.models.providers.http import MAX_ERROR_BODY_BYTES, MAX_RESPONSE_BYTES

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}
DEFAULT_ENDPOINT = "http://127.0.0.1:8080"




def _split_endpoint(endpoint: str) -> tuple[str, int]:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", ""}:
        # llama.cpp server is local HTTP; HTTPS/remote schemes are out of scope here.
        raise ProviderConnectionError(f"unsupported_endpoint_scheme:{parsed.scheme}")
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8080
    return host, port


def _http_post_json(endpoint: str, path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    host, port = _split_endpoint(endpoint)
    body = json.dumps(payload).encode("utf-8")
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        # DEC-25 — read one byte past the bound, never the whole body.
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if response.status != 200:
            raise ProviderConnectionError(f"http_status:{response.status}")
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ProviderResponseValidationError("provider_response_too_large")
    except (OSError, http.client.HTTPException) as exc:
        raise ProviderConnectionError(f"connection_failed:{exc}") from exc
    finally:
        conn.close()
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderConnectionError(f"invalid_json_response:{exc}") from exc
    if not isinstance(decoded, dict):
        raise ProviderConnectionError("response_not_object")
    return decoded


def _http_get_ok(endpoint: str, path: str, timeout: float) -> bool:
    host, port = _split_endpoint(endpoint)
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        response.read(MAX_ERROR_BODY_BYTES)
        return response.status == 200
    except (OSError, http.client.HTTPException):
        return False
    finally:
        conn.close()


@dataclass(frozen=True)
class LlamaCppServerProvider:
    """Provider for a running llama.cpp ``llama-server`` over its OpenAI-compatible HTTP API.

    Uses only the Python standard library (``http.client``) so Raiker keeps zero runtime
    dependencies. Model output (text and tool calls) is untrusted and validated downstream.
    """

    provider: str = "llama.cpp"
    model: str = "local-gguf"
    endpoint: str = DEFAULT_ENDPOINT
    timeout: float = 120.0
    temperature: float = 0.2
    max_tokens: int = 1024
    tool_call_mode: str = "openai"
    allow_remote: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        host, _ = _split_endpoint(self.endpoint)
        if host not in LOCAL_HOSTS and not self.allow_remote:
            # Egress safety: a non-local model endpoint is a data-egress decision and must be
            # explicitly opted into. Hosted providers stay disabled by policy.
            raise ProviderConnectionError(f"non_local_endpoint_not_allowed:{host}")

    def health(self, *, timeout: float = 1.0) -> bool:
        return _http_get_ok(self.endpoint, "/health", timeout)

    def generate(self, prompt: str, context: dict[str, object] | None = None) -> str:
        return self.chat([ModelMessage(role="user", content=prompt)]).text

    def chat(
        self,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
    ) -> ModelResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [message.to_dict() for message in messages],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        if tools and self.tool_call_mode == "openai":
            payload["tools"] = [spec.to_openai_tool() for spec in tools]
            payload["tool_choice"] = "auto"
        decoded = _http_post_json(self.endpoint, "/v1/chat/completions", payload, self.timeout)
        return self._parse_response(decoded)

    def _parse_response(self, decoded: dict[str, Any]) -> ModelResponse:
        choices = decoded.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderConnectionError("missing_choices")
        choice = choices[0] if isinstance(choices[0], dict) else {}
        message = choice.get("message", {}) if isinstance(choice.get("message"), dict) else {}
        text = str(message.get("content") or "")
        finish_reason = str(choice.get("finish_reason") or "stop")
        tool_calls = _parse_tool_calls(message.get("tool_calls"))
        if not tool_calls and self.tool_call_mode == "text_json":
            tool_calls = _parse_text_json_tool_calls(text)
            if tool_calls:
                text = ""
        finish = "tool_calls" if tool_calls else (finish_reason if finish_reason in {"stop", "length"} else "stop")
        usage = decoded.get("usage") if isinstance(decoded.get("usage"), dict) else None
        return ModelResponse(text=text, tool_calls=tool_calls, finish_reason=finish, usage=usage)


def _parse_tool_calls(raw: Any) -> list[ToolCallProposal]:
    if not isinstance(raw, list):
        return []
    proposals: list[ToolCallProposal] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        function = entry.get("function")
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        if not isinstance(name, str) or not name:
            continue
        arguments = _coerce_arguments(function.get("arguments"))
        raw_id = entry.get("id")
        call_id = raw_id if isinstance(raw_id, str) and raw_id else new_call_id()
        proposals.append(ToolCallProposal(call_id=call_id, tool_name=name, arguments=arguments))
    return proposals


def _coerce_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


#: Typed answer blocks Raiker renders itself: never a tool call.
_ANSWER_BLOCKS = frozenset(
    {"table", "chart", "figures", "compare", "measure", "callout", "proscons", "steps", "diagram"}
)
_FENCED_CALL = re.compile(r"```raiker:([a-z][a-z0-9_]*)(.*?)```", re.DOTALL)
_KEY_VALUE = re.compile(r'([a-z_][a-z0-9_]*)=("(?:[^"\\]|\\.)*"|\S+)')


def _parse_fenced_tool_calls(text: str) -> list[ToolCallProposal]:
    """BD-5 — a small model's ``raiker:<tool> key=value`` fence, read as the call it meant.

    A local 7B model shown Raiker's typed-answer fences wrote tool calls in the
    same shape instead of calling the tool. The fence is only a proposal: the
    tool name is validated against the turn's tools and every argument is
    governed exactly like a native call. Answer blocks are never read as calls.
    """
    calls: list[ToolCallProposal] = []
    for name, rest in _FENCED_CALL.findall(text):
        if name in _ANSWER_BLOCKS:
            continue
        arguments: dict[str, object] = {}
        for key, raw in _KEY_VALUE.findall(rest):
            value: object = raw[1:-1].encode().decode("unicode_escape") if raw.startswith('"') else raw
            if isinstance(value, str) and value.lstrip("-").isdigit():
                value = int(value)
            arguments[key] = value
        calls.append(ToolCallProposal(call_id=new_call_id(), tool_name=name, arguments=arguments))
    return calls


def _parse_text_json_tool_calls(text: str) -> list[ToolCallProposal]:
    """Defensive parse of a ``{"tool": ..., "arguments": {...}}`` block from plain text."""

    fenced = _parse_fenced_tool_calls(text)
    if fenced:
        return fenced
    snippet = text.strip()
    start = snippet.find("{")
    end = snippet.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        parsed = json.loads(snippet[start : end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, dict):
        return []
    name = parsed.get("tool") or parsed.get("name")
    arguments = parsed.get("arguments")
    if not isinstance(name, str) or not name or not isinstance(arguments, dict):
        return []
    return [ToolCallProposal(call_id=new_call_id(), tool_name=name, arguments=arguments)]
