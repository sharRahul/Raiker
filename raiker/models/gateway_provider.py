"""Provider adapter instrumentation, shared by every ModelRouter caller."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass, field, replace
from typing import Any
from uuid import uuid4

from raiker.models.contracts import (
    EmbeddingRequest,
    EmbeddingResponse,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
)
from raiker.models.gateway import AIGateway, GatewayTarget
from raiker.models.gateway_context import model_call_context


@dataclass
class GatewayOperation:
    request_id: str = field(default_factory=lambda: uuid4().hex)
    attempt: int = 0

    def next_attempt(self) -> int:
        self.attempt += 1
        return self.attempt


class GatewayProvider:
    def __init__(self, provider: Any, gateway: AIGateway, target: GatewayTarget,
                 operation: GatewayOperation | None = None, *, kind: str = "chat") -> None:
        self._provider = provider
        self._gateway = gateway
        self._target = target
        self._operation = operation or GatewayOperation()
        self._kind = kind

    def __getattr__(self, name: str) -> Any:
        # Health and catalogue calls retain their existing provider behavior;
        # they cannot prove that a model completion or embedding will execute.
        return getattr(self._provider, name)

    async def chat(self, request: ModelRequest) -> ModelResponse:
        return await self._gateway.call(
            self._target, self._kind if self._kind != "chat" else model_call_context.get().kind, lambda: self._provider.chat(request),
            request_id=self._operation.request_id, attempt=self._operation.next_attempt(),
            session_id=request.session_id, turn_id=request.turn_id,
        )

    async def stream_chat(self, request: ModelRequest) -> AsyncGenerator[ModelStreamEvent, None]:
        stream = self._gateway.stream(
            self._target, lambda: self._provider.stream_chat(request),
            request_id=self._operation.request_id, attempt=self._operation.next_attempt(),
            session_id=request.session_id, turn_id=request.turn_id,
        )
        try:
            async for event in stream:
                yield event
        finally:
            await stream.aclose()

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        return await self._gateway.call(
            replace(self._target, model=request.model), "embedding", lambda: self._provider.embed(request),
            request_id=self._operation.request_id, attempt=self._operation.next_attempt(),
        )

    async def aclose(self) -> None:
        await self._provider.aclose()
