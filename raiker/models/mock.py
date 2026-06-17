from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MockModelProvider:
    provider: str = "mock"
    model: str = "mock-deterministic"

    def generate(self, prompt: str, context: dict[str, object] | None = None) -> str:
        context_keys = sorted((context or {}).keys())
        suffix = f" context={','.join(context_keys)}" if context_keys else ""
        return f"Mock response to: {prompt}{suffix}"
