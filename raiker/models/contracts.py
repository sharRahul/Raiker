from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

MODEL_ROLES = {"system", "user", "assistant", "tool"}
FINISH_REASONS = {"stop", "tool_calls", "length", "error"}
MODEL_STREAM_EVENT_TYPES = {"text_delta", "tool_call_delta", "usage", "finish"}
TOOL_CALL_MODES = {
    "native",
    "openai",
    "text_json",
    "json_schema",
    "native_or_text_json",
    "native_or_json_schema",
}


class ModelContractError(ValueError):
    pass


def new_call_id() -> str:
    return f"call_{uuid4().hex}"


def summarize_model_usage(usage: Mapping[str, Any] | None) -> dict[str, int]:
    """Normalize a provider's ``usage`` dict into comparable token counts.

    Providers report usage differently — Anthropic exposes
    ``cache_read_input_tokens`` / ``cache_creation_input_tokens`` at the top
    level; OpenAI-compatible endpoints nest cache hits under
    ``prompt_tokens_details.cached_tokens``. This flattens both into a common
    metadata-only shape (token counts only, never prompt/response text) so the
    runtime can emit and the UI can render cache activity irrespective of which
    model served the turn. Missing fields are simply omitted; a non-dict input
    yields ``{}``.
    """
    if not isinstance(usage, Mapping):
        return {}
    out: dict[str, int] = {}

    def _put(key: str, value: Any) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, int) and value >= 0:
            out[key] = value

    _put("input_tokens", usage.get("input_tokens", usage.get("prompt_tokens")))
    _put("output_tokens", usage.get("output_tokens", usage.get("completion_tokens")))
    cached = usage.get("cache_read_input_tokens")
    if cached is None:
        details = usage.get("prompt_tokens_details")
        if isinstance(details, Mapping):
            cached = details.get("cached_tokens")
    _put("cache_read_tokens", cached)
    _put("cache_write_tokens", usage.get("cache_creation_input_tokens"))
    if "cache_read_tokens" in out:
        out["cache_hit"] = int(out["cache_read_tokens"] > 0)
    return out


@dataclass(frozen=True)
class ModelImage:
    """One validated image riding a user message as untrusted visual data."""

    media_type: str
    base64_data: str

    def __post_init__(self) -> None:
        if not self.media_type.startswith("image/"):
            raise ModelContractError("invalid_image_media_type")
        if not self.base64_data:
            raise ModelContractError("missing_image_data")


@dataclass(frozen=True)
class ModelMessage:
    """A single chat message exchanged with a model provider.

    ``content`` from ``assistant``/``tool`` roles is untrusted model/tool output and must
    never be treated as instruction authority by the runtime.
    """

    role: str
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    images: tuple[ModelImage, ...] = ()
    tool_calls: tuple[ToolCallProposal, ...] = ()

    def __post_init__(self) -> None:
        if self.role not in MODEL_ROLES:
            raise ModelContractError(f"invalid_model_role:{self.role}")
        if not isinstance(self.content, str):
            raise ModelContractError("message_content_must_be_string")
        if self.images and self.role != "user":
            raise ModelContractError("images_require_user_role")
        if self.tool_calls and self.role != "assistant":
            raise ModelContractError("tool_calls_require_assistant_role")
        if self.role == "tool" and not self.tool_call_id:
            raise ModelContractError("tool_message_requires_call_id")
        if self.role != "tool" and self.tool_call_id is not None:
            raise ModelContractError("tool_call_id_requires_tool_role")

    def to_dict(self) -> dict[str, Any]:
        message: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name is not None:
            message["name"] = self.name
        if self.tool_call_id is not None:
            message["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.call_id,
                    "type": "function",
                    "function": {
                        "name": call.tool_name,
                        "arguments": json.dumps(call.arguments),
                    },
                }
                for call in self.tool_calls
            ]
        return message


@dataclass(frozen=True)
class ToolSpec:
    """Description of a tool exposed to the model, in OpenAI-compatible function shape."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ModelContractError("missing_tool_name")
        if not isinstance(self.description, str):
            raise ModelContractError("tool_description_must_be_string")
        if not isinstance(self.parameters, dict):
            raise ModelContractError("tool_parameters_must_be_object")

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters or {"type": "object", "properties": {}},
            },
        }


@dataclass(frozen=True)
class ToolCallProposal:
    """A tool call proposed by the model. Untrusted until validated against the tool registry."""

    call_id: str
    tool_name: str
    arguments: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.call_id:
            raise ModelContractError("missing_tool_call_id")
        if not self.tool_name:
            raise ModelContractError("missing_tool_name")
        if not isinstance(self.arguments, dict):
            raise ModelContractError("tool_arguments_must_be_object")


@dataclass(frozen=True)
class ModelResponse:
    """Structured result of one model turn."""

    text: str
    tool_calls: list[ToolCallProposal] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise ModelContractError("response_text_must_be_string")
        if self.finish_reason not in FINISH_REASONS:
            raise ModelContractError(f"invalid_finish_reason:{self.finish_reason}")
        if self.usage is not None and not isinstance(self.usage, dict):
            raise ModelContractError("usage_must_be_object")


@dataclass(frozen=True)
class ProviderModelInfo:
    id: str
    owned_by: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ModelContractError("missing_provider_model_id")


@dataclass(frozen=True)
class ModelCapabilities:
    supports_streaming: bool = False
    supports_embeddings: bool = False
    supports_tool_calls: bool = False
    supports_vision: bool = False
    supports_json_schema: bool = False
    supports_reasoning: bool = False
    supports_reasoning_effort: bool = False
    supports_reasoning_budget_tokens: bool = False
    supports_reasoning_summary: bool = False
    reasoning_effort_values: tuple[str, ...] = ()
    reasoning_modes: tuple[str, ...] = ()
    reasoning_trace_visible: bool = False


@dataclass(frozen=True)
class ReasoningOptions:
    enabled: bool = False
    effort: str | None = None
    budget_tokens: int | None = None
    summary: str | None = None

    def __post_init__(self) -> None:
        if not self.enabled and any(
            value is not None for value in (self.effort, self.budget_tokens, self.summary)
        ):
            raise ModelContractError("disabled_reasoning_has_options")
        if self.budget_tokens is not None and self.budget_tokens <= 0:
            raise ModelContractError("reasoning_budget_must_be_positive")


@dataclass(frozen=True)
class ModelRequest:
    profile_id: str
    provider: str
    model: str
    messages: Sequence[ModelMessage]
    tools: Sequence[ToolSpec] | None = None
    temperature: float = 0.2
    max_tokens: int = 1024
    stream: bool = False
    tool_call_mode: str = "text_json"
    context_window_tokens: int | None = None
    reasoning: ReasoningOptions | None = None
    session_id: str | None = None
    turn_id: str | None = None
    cache_ttl: str | None = None
    response_schema: dict[str, Any] | None = None
    response_schema_name: str = "raiker_response"

    def __post_init__(self) -> None:
        if not self.profile_id or not self.provider or not self.model:
            raise ModelContractError("model_request_identity_missing")
        if not self.messages:
            raise ModelContractError("model_request_messages_empty")
        if isinstance(self.temperature, bool) or not isinstance(self.temperature, int | float):
            raise ModelContractError("temperature_must_be_number")
        if not math.isfinite(float(self.temperature)) or not 0 <= float(self.temperature) <= 2:
            raise ModelContractError("temperature_out_of_range")
        if isinstance(self.max_tokens, bool) or not isinstance(self.max_tokens, int) or self.max_tokens <= 0:
            raise ModelContractError("max_tokens_must_be_positive")
        if self.context_window_tokens is not None and self.context_window_tokens <= 0:
            raise ModelContractError("context_window_must_be_positive")
        if self.tool_call_mode not in TOOL_CALL_MODES:
            raise ModelContractError(f"invalid_tool_call_mode:{self.tool_call_mode}")
        if self.response_schema is not None:
            if not isinstance(self.response_schema, dict):
                raise ModelContractError("response_schema_must_be_object")
            if not self.response_schema_name:
                raise ModelContractError("response_schema_name_missing")


@dataclass(frozen=True)
class ModelStreamEvent:
    event_type: str
    text_delta: str = ""
    finish_reason: str | None = None
    tool_call_delta: dict[str, object] | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.event_type not in MODEL_STREAM_EVENT_TYPES:
            raise ModelContractError(f"invalid_stream_event_type:{self.event_type}")
        if self.event_type == "finish":
            if self.finish_reason not in FINISH_REASONS:
                raise ModelContractError(f"invalid_stream_finish_reason:{self.finish_reason}")
        elif self.finish_reason is not None:
            raise ModelContractError("finish_reason_requires_finish_event")
        if self.event_type == "tool_call_delta" and not isinstance(self.tool_call_delta, dict):
            raise ModelContractError("tool_call_delta_requires_object")
        if self.event_type != "tool_call_delta" and self.tool_call_delta is not None:
            raise ModelContractError("tool_call_delta_requires_tool_event")


@dataclass(frozen=True)
class EmbeddingRequest:
    profile_id: str
    provider: str
    model: str
    text: str

    def __post_init__(self) -> None:
        if not self.profile_id or not self.provider or not self.model:
            raise ModelContractError("embedding_request_identity_missing")
        if not isinstance(self.text, str) or not self.text:
            raise ModelContractError("embedding_text_missing")


@dataclass(frozen=True)
class EmbeddingResponse:
    vector: list[float]
    model: str
    usage: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if not self.vector:
            raise ModelContractError("embedding_vector_empty")
        if not all(isinstance(value, float) and math.isfinite(value) for value in self.vector):
            raise ModelContractError("embedding_vector_invalid")
        if not self.model:
            raise ModelContractError("embedding_model_missing")
