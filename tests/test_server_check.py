"""Local-server checks: is this server set up for agent work?

Verified live on 2026-10-18 against this host's Ollama: ``gemma3:1b`` refused
tools, ``gpt-oss:20b-cloud`` called the probe natively, and
``qwen2.5-coder:7b`` returned it as plain text while serving 32,768 tokens.
These tests pin the classification, the advice and the loopback-only context
read without a server.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from raiker.models import server_check
from raiker.models.contracts import ModelResponse, ToolCallProposal
from raiker.models.exceptions import ProviderConnectionError, ProviderUnsupportedCapabilityError
from raiker.models.registry import ModelProfileRegistry
from raiker.models.router import ModelRouter


def _router(outcome: Any) -> tuple[ModelRouter, list[Any]]:
    seen: list[Any] = []

    class _Provider:
        provider = "ollama"
        model = "m"
        tool_call_mode = "native_or_text_json"

        async def chat(self, request: Any) -> ModelResponse:
            seen.append((self.tool_call_mode, request.tools))
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        async def aclose(self) -> None: ...

    class _Factory:
        def create(self, _profile: Any) -> _Provider:
            return _Provider()

    router = ModelRouter(ModelProfileRegistry.load())
    router._factory = lambda _profile, _connection=None: _Factory()  # type: ignore[method-assign, assignment, return-value]
    return router, seen


@pytest.mark.parametrize(
    ("outcome", "verdict"),
    [
        (ModelResponse(text="", tool_calls=[ToolCallProposal("c1", "raiker_ping", {})]), "native"),
        (ModelResponse(text='{"name": "raiker_ping", "arguments": {}}'), "as_text"),
        (ModelResponse(text="Hello!"), "not_called"),
        (ProviderUnsupportedCapabilityError("tool_calls_unsupported:http_400"), "refused"),
        (ProviderConnectionError("provider_connection_failed"), "unavailable"),
    ],
)
def test_each_server_behaviour_gets_its_own_verdict(outcome: Any, verdict: str) -> None:
    router, seen = _router(outcome)
    got, _reason = asyncio.run(server_check.probe_tool_calling(router, "ollama", "gemma3:1b"))
    assert got == verdict
    # Native parsing only, so a text reply is never mistaken for a tool call.
    assert seen[0][0] == "native"
    assert [tool.name for tool in seen[0][1]] == ["raiker_ping"]


def test_the_advice_names_the_setting_that_fixes_it() -> None:
    assert "--jinja" in server_check.advice("llama.cpp", "refused", None)[0]
    assert "does not support tools" in server_check.advice("ollama", "refused", None)[0]
    assert "--enable-auto-tool-choice" in server_check.advice("openai-compatible", "refused", None)[0]
    assert "tool-call-parser" in server_check.advice("openai-compatible", "as_text", None)[0]
    small = server_check.advice("ollama", "native", 4096)
    assert len(small) == 1 and "OLLAMA_CONTEXT_LENGTH" in small[0]
    assert server_check.advice("ollama", "native", 131_072) == []


class _Client:
    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes
        self.urls: list[str] = []

    def __call__(self, **_options: Any) -> _Client:
        return self

    def __enter__(self) -> _Client:
        return self

    def __exit__(self, *_exc: Any) -> None: ...

    def get(self, url: str) -> httpx.Response:
        self.urls.append(url)
        return httpx.Response(200, json=self.routes[url])


def test_serving_context_is_read_from_each_servers_own_status(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client(
        {
            "http://127.0.0.1:11434/api/ps": {"models": [{"name": "qwen2.5-coder:7b", "context_length": 32768}]},
            "http://127.0.0.1:8080/props": {"default_generation_settings": {"n_ctx": 8192}},
            "http://127.0.0.1:8000/v1/models": {"data": [{"id": "Qwen/Qwen3-8B", "max_model_len": 40960}]},
        }
    )
    monkeypatch.setattr(server_check.httpx, "Client", client)
    assert server_check.serving_context("ollama", "http://127.0.0.1:11434/v1", "qwen2.5-coder:7b") == 32768
    assert server_check.serving_context("llama.cpp", "http://127.0.0.1:8080/v1", "local-gguf") == 8192
    assert server_check.serving_context("openai-compatible", "http://127.0.0.1:8000/v1", "Qwen/Qwen3-8B") == 40960


def test_an_off_machine_endpoint_is_never_probed_for_context(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client({})
    monkeypatch.setattr(server_check.httpx, "Client", client)
    assert server_check.serving_context("openai-compatible", "https://gpu.example.com/v1", "m") is None
    assert server_check.serving_context("openai-compatible", "http://192.168.1.20:8000/v1", "m") is None
    assert client.urls == []
