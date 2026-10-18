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
