"""ChatGPT-subscription adapter backed by the local Codex App Server."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import suppress

from raiker.models.codex_app_server import CodexAppServerClient
from raiker.models.contracts import (
    EmbeddingRequest,
    EmbeddingResponse,
    ModelCapabilities,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ProviderModelInfo,
)
from raiker.models.exceptions import ProviderUnsupportedCapabilityError
from raiker.models.health import ProviderHealth
from raiker.models.subscription_limits import LimitWindowSink


class AsyncCodexAppServerProvider:
    """A text-only model provider; Codex retains subscription credentials."""

    provider = "chatgpt-codex"

    def __init__(
        self,
        *,
        profile_id: str,
        model: str,
        capabilities: ModelCapabilities,
        client_factory: Callable[[], CodexAppServerClient] = CodexAppServerClient,
        on_limit_windows: LimitWindowSink | None = None,
    ) -> None:
        self.profile_id = profile_id
        self.model = model
        self.capabilities = capabilities
        self._client_factory = client_factory
        # BUG-254 — where the limit windows the subscription volunteers with a
        # turn are handed on. Optional: a provider built without one still runs
        # turns, it just has nowhere to report what the subscription said.
        self._on_limit_windows = on_limit_windows
        self._clients: list[CodexAppServerClient] = []

    def _client(self) -> CodexAppServerClient:
        client = self._client_factory()
        self._clients.append(client)
        return client

    async def health(self, *, timeout: float = 1.0) -> ProviderHealth:
        try:
            account = await self._client().account_status()
        except Exception:
            return ProviderHealth(self.provider, False, False, "codex_app_server_unavailable")
        return ProviderHealth(
            self.provider,
            account.signed_in,
            account.signed_in,
            "chatgpt_subscription_connected" if account.signed_in else "chatgpt_subscription_signed_out",
        )

    async def list_models(self) -> list[ProviderModelInfo]:
        return [ProviderModelInfo(id=model, owned_by="chatgpt-codex") for model in await self._client().list_models()]

    @staticmethod
    def _prompt(request: ModelRequest) -> str:
        if request.tools or request.response_schema is not None:
            raise ProviderUnsupportedCapabilityError("codex_app_server_tools_unsupported")
        if any(message.images or message.tool_calls for message in request.messages):
            raise ProviderUnsupportedCapabilityError("codex_app_server_non_text_input_unsupported")
        return "\n\n".join(f"{message.role}: {message.content}" for message in request.messages)

    async def chat(self, request: ModelRequest) -> ModelResponse:
        client = self._client()
        text = await client.complete_chat(
            model=request.model,
            prompt=self._prompt(request),
            effort=(request.reasoning.effort if request.reasoning and request.reasoning.enabled else None),
        )
        # Reporting what the subscription said must never be able to fail the
        # turn it rode in on: the answer is already in hand.
        if self._on_limit_windows is not None and client.last_limit_windows:
            with suppress(Exception):
                self._on_limit_windows(self.profile_id, client.last_limit_windows)
        return ModelResponse(text=text)

    async def stream_chat(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        response = await self.chat(request)
        if response.text:
            yield ModelStreamEvent(event_type="text_delta", text_delta=response.text)
        yield ModelStreamEvent(event_type="finish", finish_reason=response.finish_reason)

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        raise ProviderUnsupportedCapabilityError("codex_app_server_embeddings_unsupported")

    async def aclose(self) -> None:
        while self._clients:
            await self._clients.pop().aclose()
