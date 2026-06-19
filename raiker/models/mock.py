from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from raiker.models.contracts import (
    ModelMessage,
    ModelResponse,
    ToolCallProposal,
    ToolSpec,
    new_call_id,
)
from raiker.runtime.classifier import SimpleClassifier


@dataclass(frozen=True)
class MockModelProvider:
    """Deterministic, offline provider.

    It doubles as a deterministic tool-calling "model": ``chat`` proposes the same tool calls
    the runtime would expect for filesystem/local-action prompts, then returns a final text
    turn once a tool result has been observed. This keeps the model-driven loop fully testable
    with no network and no real model.
    """

    provider: str = "mock"
    model: str = "mock-deterministic"

    def generate(self, prompt: str, context: dict[str, object] | None = None) -> str:
        context_keys = sorted((context or {}).keys())
        suffix = f" context={','.join(context_keys)}" if context_keys else ""
        return f"Mock response to: {prompt}{suffix}"

    def chat(
        self,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
    ) -> ModelResponse:
        if any(message.role == "tool" for message in messages):
            # A tool result has already been observed: end the turn (no further tool calls).
            return ModelResponse(text="", tool_calls=[], finish_reason="stop")
        user_text = next(
            (m.content for m in reversed(list(messages)) if m.role == "user"),
            "",
        )
        proposal = self._propose(user_text)
        if proposal is None:
            return ModelResponse(text=self.generate(user_text), finish_reason="stop")
        return ModelResponse(text="", tool_calls=[proposal], finish_reason="tool_calls")

    def _propose(self, text: str) -> ToolCallProposal | None:
        stripped = text.strip()
        lower = stripped.lower()
        intent = SimpleClassifier().classify(stripped).intent
        if intent == "local_action_request":
            command = stripped[1:].strip() if stripped.startswith("!") else stripped
            return ToolCallProposal(new_call_id(), "shell", {"command": command})
        if intent != "filesystem_query":
            return None
        if lower.startswith("read file"):
            path = stripped[len("read file") :].strip() or "."
            return ToolCallProposal(new_call_id(), "read_file", {"path": path})
        if lower.startswith("read "):
            path = stripped[len("read") :].strip() or "."
            return ToolCallProposal(new_call_id(), "read_file", {"path": path})
        if "grep" in lower or "search" in lower:
            parts = stripped.split(maxsplit=1)
            query = parts[1] if len(parts) > 1 else ""
            return ToolCallProposal(
                new_call_id(),
                "grep",
                {"query": query, "path": ".", "max_results": 50},
            )
        return ToolCallProposal(new_call_id(), "list_directory", {"path": "."})
