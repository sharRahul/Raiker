from __future__ import annotations

import asyncio
import importlib.metadata
import tomllib
from pathlib import Path

import httpx
import pytest

from raiker.cli.commands import (
    handle_model_command,
    handle_model_command_async,
    handle_providers,
    handle_reasoning_command,
    render_models,
)
from raiker.models.contracts import ModelCapabilities, ModelMessage, ModelRequest
from raiker.models.exceptions import ProviderConfigurationError, ProviderPolicyError
from raiker.models.factory import ModelProviderFactory, ProviderRuntimePolicy
from raiker.models.providers.openai_compatible import AsyncOpenAICompatibleProvider, _join
from raiker.models.registry import ModelProfileRegistry
from raiker.models.router import ModelRouter


def test_real_httpx_and_dependencies() -> None:
    assert not Path("httpx.py").exists()
    assert "Raiker/httpx.py" not in str(httpx.__file__)
    try:
        deps = importlib.metadata.requires("raiker") or []
    except importlib.metadata.PackageNotFoundError:
        with open("pyproject.toml", "rb") as handle:
            deps = tomllib.loads(handle.read().decode())["project"]["dependencies"]
    assert any(d.startswith("httpx") for d in deps)
    # fastapi is now an intentional dependency (the API/UI surface). langchain and
    # llama-index remain disallowed: they would bypass Raiker contracts.
    assert not any(d.startswith(("langchain", "llama-index")) for d in deps)


@pytest.mark.parametrize(("base", "path", "expected"), [
    ("http://127.0.0.1:8080", "/v1/chat/completions", "http://127.0.0.1:8080/v1/chat/completions"),
    ("http://127.0.0.1:8080/", "/v1/chat/completions", "http://127.0.0.1:8080/v1/chat/completions"),
    ("http://127.0.0.1:8080/v1", "/v1/chat/completions", "http://127.0.0.1:8080/v1/chat/completions"),
    ("http://127.0.0.1:8080/v1/", "chat/completions", "http://127.0.0.1:8080/v1/chat/completions"),
    ("http://127.0.0.1:11434/v1", "/v1/models", "http://127.0.0.1:11434/v1/models"),
    ("https://openrouter.ai/api/v1", "/v1/chat/completions", "https://openrouter.ai/api/v1/chat/completions"),
])
def test_join(base: str, path: str, expected: str) -> None:
    assert _join(base, path) == expected


def test_production_router_rejects_test_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAIKER_TEST_MODE", raising=False)
    router = ModelRouter(ModelProfileRegistry.load())
    assert router.default_provider()[0] == "llama.cpp"
    with pytest.raises(ProviderPolicyError):
        router.select_profile("mock-test")


def test_test_mode_allows_test_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAIKER_TEST_MODE", "1")
    router = ModelRouter(ModelProfileRegistry.load())
    profile = router.select_profile("mock-test")
    assert profile.profile_id == "mock-test"


def test_factory_policy_openrouter(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = ModelProfileRegistry.load()
    profile = registry.resolve_profile_id("openrouter-policy-gated")
    with pytest.raises(ProviderPolicyError):
        ModelProviderFactory().create(profile)
    with pytest.raises(ProviderConfigurationError):
        ModelProviderFactory(policy=ProviderRuntimePolicy(allow_policy_gated_provider=True, allow_hosted_provider=True)).create(profile)
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret")
    configured = type(profile)(**{**profile.__dict__, "model": "openrouter-model"})
    # Phase 4 slice 7: off-machine model endpoints also require the owner
    # egress allowlist — empty allowlist fails closed even with hosted policy.
    monkeypatch.delenv("RAIKER_MODEL_EGRESS_ALLOWLIST", raising=False)
    with pytest.raises(ProviderPolicyError, match="model_egress_denied:no_allowlist"):
        ModelProviderFactory(policy=ProviderRuntimePolicy(allow_policy_gated_provider=True, allow_hosted_provider=True)).create(configured)
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "openrouter.ai")
    provider = ModelProviderFactory(policy=ProviderRuntimePolicy(allow_policy_gated_provider=True, allow_hosted_provider=True)).create(configured)
    assert provider.provider == "openrouter"


def test_factory_rejects_vllm_without_private_network_policy() -> None:
    profile = ModelProfileRegistry.load().resolve_profile_id("vllm-homelab-openai-compatible")
    configured = type(profile)(**{**profile.__dict__, "model": "vllm-model"})
    with pytest.raises(ProviderPolicyError):
        ModelProviderFactory(policy=ProviderRuntimePolicy(allow_policy_gated_provider=True)).create(configured)


def test_async_openai_success_and_live_urls() -> None:
    seen = []
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "m", "owned_by": "local"}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": {"total_tokens": 2}})
    p = AsyncOpenAICompatibleProvider("p", "llama.cpp", "m", "http://127.0.0.1:8080/v1", ModelCapabilities(supports_embeddings=True), client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    async def main() -> None:
        resp = await p.chat(ModelRequest("p", "llama.cpp", "m", [ModelMessage("user", "secret")]))
        assert resp.text == "ok"
        models = await p.list_models()
        assert models[0].id == "m"
    asyncio.run(main())
    assert seen == ["http://127.0.0.1:8080/v1/chat/completions", "http://127.0.0.1:8080/v1/models"]


def test_stream_cancellation_preserves_cancelled_error() -> None:
    async def main() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            raise asyncio.CancelledError()
        p = AsyncOpenAICompatibleProvider("p", "llama.cpp", "m", "http://127.0.0.1:8080", ModelCapabilities(), client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        with pytest.raises(asyncio.CancelledError):
            async for _ in p.stream_chat(ModelRequest("p", "llama.cpp", "m", [ModelMessage("user", "x")])):
                pass
    asyncio.run(main())


def test_cli_persists_model_state(tmp_path: Path) -> None:
    assert "raiker-local-llama-cpp" in handle_model_command("/model current", workspace_root=tmp_path)
    # A placeholder-model profile now attempts auto-detection; with no server reachable it reports a
    # connection error and does not persist the selection (the native default stays active).
    # A developer machine may have a live local Ollama serving multiple models; then the CLI asks
    # for an explicit --model instead. Either way the placeholder selection must not persist.
    out = handle_model_command("/model use ollama-local-openai-compatible", workspace_root=tmp_path)
    assert "Could not reach ollama" in out or "Select one with /model use --provider ollama" in out
    assert "raiker-local-llama-cpp" in handle_model_command("/model current", workspace_root=tmp_path)
    assert "(selected)" in render_models(workspace_root=tmp_path)
    assert "does not support reasoning" in handle_reasoning_command("/reasoning set high", workspace_root=tmp_path)


def test_model_health_active_loop_uses_async_path(tmp_path: Path) -> None:
    async def main() -> None:
        sync_out = handle_model_command("/model health", workspace_root=tmp_path)
        assert "Model command requires async command path" in sync_out
        async_out = await handle_model_command_async("/model health", workspace_root=tmp_path)
        assert "Model health:" in async_out

    asyncio.run(main())


def test_placeholder_profiles_remain_listable() -> None:
    providers = handle_providers()
    models = render_models()
    assert "ollama-local-openai-compatible" in providers
    assert "lm-studio-local-openai-compatible" in providers
    assert "ollama-local-openai-compatible" in models
    assert "lm-studio-local-openai-compatible" in models
