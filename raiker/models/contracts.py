from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

MODEL_ROLES = {"system", "user", "assistant", "tool"}
FINISH_REASONS = {"stop", "tool_calls", "length", "error"}


class ModelContractError(ValueError):
    pass


def new_call_id() -> str:
    return f"call_{uuid4().hex}"


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

    def __post_init__(self) -> None:
        if self.role not in MODEL_ROLES:
            raise ModelContractError(f"invalid_model_role:{self.role}")

    def to_dict(self) -> dict[str, Any]:
        message: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name is not None:
            message["name"] = self.name
        if self.tool_call_id is not None:
            message["tool_call_id"] = self.tool_call_id
        return message


@dataclass(frozen=True)
class ToolSpec:
    """Description of a tool exposed to the model, in OpenAI-compatible function shape."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)

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
        if self.finish_reason not in FINISH_REASONS:
            raise ModelContractError(f"invalid_finish_reason:{self.finish_reason}")
