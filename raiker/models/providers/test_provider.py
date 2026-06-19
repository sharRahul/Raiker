from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from raiker.models.contracts import (
    EmbeddingRequest,
    EmbeddingResponse,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ProviderModelInfo,
)
from raiker.models.exceptions import ProviderUnsupportedCapabilityError
from raiker.models.health import ProviderHealth
from raiker.models.mock import MockModelProvider


@dataclass(frozen=True)
class DeterministicTestProvider:
    provider: str = "test"
    model: str = "deterministic-test-model"
    profile_id: str = "deterministic-test"

    async def health(self, *, timeout: float = 1.0) -> ProviderHealth:
        return ProviderHealth(self.provider, True, True, "deterministic_test_provider")

    async def list_models(self) -> list[ProviderModelInfo]:
        return [ProviderModelInfo(id=self.model, owned_by="raiker-tests")]

    async def chat(self, request: ModelRequest) -> ModelResponse:
        return MockModelProvider(provider=self.provider, model=self.model).chat(request.messages, request.tools)

    async def stream_chat(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        response = await self.chat(request)
        if response.text:
            yield ModelStreamEvent(event_type="text_delta", text_delta=response.text)
        yield ModelStreamEvent(event_type="finish", finish_reason=response.finish_reason)

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        raise ProviderUnsupportedCapabilityError("embeddings_unsupported")

    async def aclose(self) -> None:
        return None
