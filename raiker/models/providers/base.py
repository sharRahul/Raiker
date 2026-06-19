from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from raiker.models.contracts import (
    EmbeddingRequest,
    EmbeddingResponse,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ProviderModelInfo,
)
from raiker.models.health import ProviderHealth


class AsyncModelProvider(Protocol):
    provider: str
    model: str
    profile_id: str

    async def health(self, *, timeout: float = 1.0) -> ProviderHealth: ...
    async def list_models(self) -> list[ProviderModelInfo]: ...
    async def chat(self, request: ModelRequest) -> ModelResponse: ...
    def stream_chat(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]: ...
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse: ...
    async def aclose(self) -> None: ...
