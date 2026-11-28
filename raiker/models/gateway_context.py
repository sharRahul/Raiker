"""Task-local correlation metadata; never an authorization source."""
from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from raiker.models.contracts import ModelStreamEvent


@dataclass(frozen=True)
class ModelCallContext:
    kind: str = "chat"
    session_id: str | None = None
    turn_id: str | None = None


_DEFAULT_CONTEXT = ModelCallContext()
model_call_context: ContextVar[ModelCallContext] = ContextVar(
    "model_call_context", default=_DEFAULT_CONTEXT
)


@contextmanager
def model_request_context(*, kind: str = "chat", session_id: str | None = None,
                          turn_id: str | None = None) -> Iterator[None]:
    token = model_call_context.set(ModelCallContext(kind, session_id, turn_id))
    try:
        yield
    finally:
        model_call_context.reset(token)


async def correlated_model_stream(
    stream: AsyncIterator[ModelStreamEvent], *, session_id: str, turn_id: str
) -> AsyncGenerator[ModelStreamEvent, None]:
    """Bind metadata while advancing a provider, never while yielding to a client."""
    try:
        while True:
            with model_request_context(session_id=session_id, turn_id=turn_id):
                try:
                    event = await anext(stream)
                except StopAsyncIteration:
                    return
            yield event
    finally:
        if hasattr(stream, "aclose"):
            await stream.aclose()
