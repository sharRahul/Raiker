from __future__ import annotations

import pytest

from raiker.contracts.ids import new_id
from raiker.contracts.models import ClientMetadata, ModelProfile
from raiker.models.exceptions import ProviderPolicyError
from raiker.models.factory import ModelProviderFactory
from raiker.models.registry import ModelProfileRegistry, RegistryError
from raiker.models.router import ModelRouter


def test_test_provider_profiles_are_rejected_fail_closed() -> None:
    profile = ModelProfile(
        profile_id="synthetic-offline",
        provider="mock",
        model="anything",
        build_phase="test",
        default_state="enabled",
        tui_launch_action="",
        local_only=True,
        requires_network=False,
        raw={"test_only": True},
    )
    with pytest.raises(ProviderPolicyError, match="test_provider_not_available"):
        ModelProviderFactory().create(profile)


def test_unknown_provider_fails() -> None:
    router = ModelRouter(ModelProfileRegistry.load())
    with pytest.raises(RegistryError):
        router.generate("unknown", "model", "Hello")


def test_launch_fails_for_unregistered_provider(tmp_path) -> None:  # type: ignore[no-untyped-def]
    router = ModelRouter(ModelProfileRegistry.load())
    result = router.launch(
        "mock",
        "no-such-model",
        session_id=new_id("sess_"),
        turn_id=None,
        client=ClientMetadata(type="test_harness", name="tests", version="0.0.0"),
    )
    assert result.status == "failed"
    assert result.profile is None


def test_a_model_the_local_service_lists_without_tools_is_sent_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real Ollama answers HTTP 400 when tools reach a model it lists without them.

    ``gemma3:1b`` is listed with ``capabilities: ["completion"]``; the turn must go
    without tools rather than fail, and a model that takes tools keeps them.
    """
    from raiker.contracts.ids import utc_now
    from raiker.models import local_service
    from raiker.models.contracts import ToolSpec

    answer = local_service.ServiceLiveness(
        "ollama",
        "http://127.0.0.1:11434/v1",
        True,
        ("gemma3:1b", "qwen3:8b", "silent:latest"),
        utc_now(),
        capabilities=(
            ("gemma3:1b", frozenset({"completion"})),
            ("qwen3:8b", frozenset({"completion", "tools"})),
        ),
    )
    monkeypatch.setattr(local_service, "liveness", lambda runtime, endpoint, **_: answer)
    router = ModelRouter(ModelProfileRegistry.load())
    profile = router.registry.resolve_profile_id("ollama-local-openai-compatible")
    tools = [ToolSpec("read_file", "Read a file")]

    assert router._tools_for(profile, "gemma3:1b", tools) is None
    assert router._tools_for(profile, "qwen3:8b", tools) == tools
    # A model whose capabilities were not published is not second-guessed.
    assert router._tools_for(profile, "silent:latest", tools) == tools


def test_an_endpoint_that_refuses_tools_is_asked_again_without_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A custom endpoint serving a tool-less model answers 400 "does not support tools".

    Raiker cannot know that in advance (only Ollama's own catalogue says so),
    so the refusal is the signal: the same request goes again without tools,
    once, and the pair is remembered so later turns skip the refused attempt.
    """
    import asyncio

    from raiker.models import router as router_module
    from raiker.models.contracts import ModelMessage, ModelResponse, ToolSpec
    from raiker.models.exceptions import ProviderUnsupportedCapabilityError
    from raiker.models.providers.http import provider_status_error

    refusal = provider_status_error(
        400, model="gemma3:1b", body='{"error":{"message":"gemma3:1b does not support tools"}}'
    )
    assert isinstance(refusal, ProviderUnsupportedCapabilityError)

    sent: list[object] = []

    class _Provider:
        provider = "openai-compatible"
        model = "gemma3:1b"

        async def chat(self, request):  # type: ignore[no-untyped-def]
            sent.append(request.tools)
            if request.tools:
                raise refusal
            return ModelResponse(text="hello")

        async def aclose(self) -> None: ...

    class _Factory:
        def create(self, _profile):  # type: ignore[no-untyped-def]
            return _Provider()

    router_module._TOOLLESS_MODELS.clear()
    router = ModelRouter(ModelProfileRegistry.load())
    monkeypatch.setattr(router, "_factory", lambda _profile: _Factory())
    monkeypatch.setattr(router, "_profile", lambda _p, model: router.registry.resolve_profile_id("generic-openai-compatible"))
    tools = [ToolSpec("read_file", "Read a file")]
    messages = [ModelMessage("user", "hi")]

    response = asyncio.run(router.achat("openai-compatible", "gemma3:1b", messages, tools))
    assert response.text == "hello"
    assert sent == [tools, None]
    # Remembered: the next turn goes without tools at once.
    asyncio.run(router.achat("openai-compatible", "gemma3:1b", messages, tools))
    assert sent == [tools, None, None]
    router_module._TOOLLESS_MODELS.clear()
