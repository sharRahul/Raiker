"""Ollama's own chat API, so Raiker can say how much context to load.

Ollama's OpenAI-compatible route (``/v1/chat/completions``) takes no
``num_ctx``: a model loads at Ollama's default, which on Ollama 0.40 is the
model's full trained context. Measured on the Windows test PC on 2026-11-25,
``qwen3.5:9b`` loaded at 262,144 tokens, 15 GB on a 16 GB card, 8 % on the CPU,
and a one-line answer took minutes. Ollama's native ``/api/chat`` takes
``options.num_ctx`` and honours it (``gemma3:1b``: 32,768 through ``/v1``, 4,096
through ``/api/chat`` with the option).

The context is chosen from fixed steps, the smallest that holds this request's
messages, tools and answer budget, and never above what the model was trained
for. Steps rather than an exact size, because every different ``num_ctx`` makes
Ollama reload the model: a conversation grows through a few steps, not a reload
per turn.

Only the request and the reply's shape differ from the OpenAI route; the
origin is the same policy-checked one (the ``/v1`` suffix replaced), and the
reply is read into the same :class:`ModelResponse` and stream events.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from raiker.models.contracts import ModelMessage, ModelRequest, ToolCallProposal
from raiker.models.exceptions import ProviderResponseValidationError, ProviderStreamError

#: The context sizes Raiker asks for, smallest first.
CONTEXT_STEPS: tuple[int, ...] = (8_192, 16_384, 32_768, 65_536, 131_072)
#: Used when the model's own maximum is not known.
DEFAULT_MAXIMUM = 32_768
#: A deliberately generous characters-per-token figure, so a request is never
#: given a context that cuts its start off.
_CHARS_PER_TOKEN = 3


def estimated_tokens(request: ModelRequest) -> int:
    """An upper-leaning estimate of the request's prompt in tokens."""
    characters = sum(len(message.content or "") for message in request.messages)
    for message in request.messages:
        for call in message.tool_calls or ():
            characters += len(json.dumps(call.arguments)) + len(call.tool_name)
        # An image costs Ollama's vision encoder a fixed number of tokens per
        # tile; 1,000 per picture is above every current local model's figure.
        characters += 1_000 * _CHARS_PER_TOKEN * len(message.images or ())
    for tool in request.tools or ():
        characters += len(json.dumps(tool.to_openai_tool()))
    return characters // _CHARS_PER_TOKEN + 64


def context_for(request: ModelRequest, *, maximum: int | None) -> int:
    """The smallest step that holds the request and its answer, within the model."""
    ceiling = maximum if maximum and maximum > 0 else DEFAULT_MAXIMUM
    need = estimated_tokens(request) + max(int(request.max_tokens or 0), 256)
    for step in CONTEXT_STEPS:
        if step >= need:
            return min(step, ceiling)
    return min(CONTEXT_STEPS[-1], ceiling) if ceiling <= CONTEXT_STEPS[-1] else min(need, ceiling)


def _message(message: ModelMessage, *, vision: bool) -> dict[str, Any]:
    out: dict[str, Any] = {"role": message.role, "content": message.content or ""}
    if message.images and message.role == "user" and vision:
        out["images"] = [image.base64_data for image in message.images]
    if message.tool_calls:
        # Native Ollama takes the arguments as an object, not a JSON string.
        out["tool_calls"] = [
            {"function": {"name": call.tool_name, "arguments": dict(call.arguments)}}
            for call in message.tool_calls
        ]
    if message.role == "tool" and message.name:
        out["tool_name"] = message.name
    return out


def payload(
    request: ModelRequest,
    *,
    model: str,
    stream: bool,
    num_ctx: int,
    vision: bool,
    tools: bool,
) -> dict[str, Any]:
    """The ``/api/chat`` body for *request*."""
    body: dict[str, Any] = {
        "model": model,
        "messages": [_message(message, vision=vision) for message in request.messages],
        "stream": stream,
        "options": {
            "num_ctx": num_ctx,
            "temperature": request.temperature,
            "num_predict": request.max_tokens,
        },
    }
    if tools and request.tools:
        body["tools"] = [tool.to_openai_tool() for tool in request.tools]
    if request.response_schema is not None:
        body["format"] = request.response_schema
    return body


def _arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            raise ProviderResponseValidationError("malformed_tool_arguments") from exc
        if isinstance(decoded, dict):
            return decoded
    raise ProviderResponseValidationError("tool_arguments_not_object")


def tool_calls(raw: Any, *, offset: int = 0) -> list[ToolCallProposal]:
    """Native tool calls in Raiker's shape; Ollama gives them no ids."""
    if not isinstance(raw, list):
        return []
    calls: list[ToolCallProposal] = []
    for position, item in enumerate(raw):
        function = item.get("function") if isinstance(item, Mapping) else None
        if not isinstance(function, Mapping) or not isinstance(function.get("name"), str):
            continue
        call_id = item.get("id") if isinstance(item.get("id"), str) and item.get("id") else None
        calls.append(
            ToolCallProposal(
                call_id=call_id or f"call_{offset + position}",
                tool_name=function["name"],
                arguments=_arguments(function.get("arguments")),
            )
        )
    return calls


def usage(data: Mapping[str, Any]) -> dict[str, Any] | None:
    """Ollama's counts under the names the ledger reads."""
    prompt = data.get("prompt_eval_count")
    completion = data.get("eval_count")
    if not isinstance(prompt, int) and not isinstance(completion, int):
        return None
    prompt_tokens = prompt if isinstance(prompt, int) else 0
    completion_tokens = completion if isinstance(completion, int) else 0
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def finish_reason(data: Mapping[str, Any], *, has_tools: bool) -> str:
    if has_tools:
        return "tool_calls"
    return "length" if data.get("done_reason") == "length" else "stop"


def raise_error(data: Mapping[str, Any], *, streaming: bool) -> None:
    """Ollama reports a failure in the body as ``{"error": "..."}``."""
    error = data.get("error")
    if isinstance(error, str) and error:
        kind = ProviderStreamError if streaming else ProviderResponseValidationError
        raise kind(f"ollama_error:{error[:120]}")
