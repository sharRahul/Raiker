"""GCR-01, GCR-02, GCR-03, GCR-04, GCR-18 — asking whether a profile would run.

Five call sites in the product only ever wanted that answer: selecting a model,
launching one, saving a connection, `/model use`, and the connection Test. Each
of them answered it by building a live provider and dropping it. Two built it
without the owner's saved connection, so they answered about an endpoint and a
credential the turn would not use; four never closed the `httpx.AsyncClient` the
provider owns.

These tests hold the fixed behaviour: one validation path, through the owner's
connection, that opens nothing.
"""

from __future__ import annotations

import gc

import httpx
import pytest

from raiker.contracts.ids import new_id
from raiker.contracts.models import ClientMetadata, ModelProfile
from raiker.models.exceptions import (
    ProviderConfigurationError,
    ProviderPolicyError,
)
from raiker.models.factory import ModelProviderFactory, ProviderRuntimePolicy
from raiker.models.registry import ModelProfileRegistry
from raiker.models.router import ModelRouter

CLIENT = ClientMetadata(type="test_harness", name="tests", version="0.0.0")

HOSTED_POLICY = ProviderRuntimePolicy(
    allow_policy_gated_provider=True,
    allow_hosted_provider=True,
)


def _anthropic_profile(model: str = "claude-haiku-4-5-20251001") -> ModelProfile:
    registry = ModelProfileRegistry.load()
    shipped = registry.resolve_profile_id("anthropic-hosted")
    return ModelProfile(
        profile_id=shipped.profile_id,
        provider=shipped.provider,
        model=model,
        build_phase=shipped.build_phase,
        default_state=shipped.default_state,
        tui_launch_action=shipped.tui_launch_action,
        local_only=shipped.local_only,
        requires_network=shipped.requires_network,
        raw={**shipped.raw, "model": model},
    )


def _open_async_clients() -> int:
    """How many un-closed `httpx.AsyncClient` objects the process is holding."""
    gc.collect()
    return sum(
        1
        for obj in gc.get_objects()
        if isinstance(obj, httpx.AsyncClient) and not obj.is_closed
    )


# --- GCR-02: validation opens no transport ---------------------------------


def test_validate_opens_no_client() -> None:
    """The whole point: a passing validation leaves nothing to close."""
    profile = _anthropic_profile()
    factory = ModelProviderFactory(
        policy=HOSTED_POLICY, connection={"api_key": "sk-ant-test-key"}
    )
    before = _open_async_clients()
    for _ in range(5):
        factory.validate(profile)
    assert _open_async_clients() == before


def test_create_still_opens_one_and_it_is_closable() -> None:
    """`create` is unchanged — it is the execution path, and it owns a client."""
    profile = _anthropic_profile()
    provider = ModelProviderFactory(
        policy=HOSTED_POLICY, connection={"api_key": "sk-ant-test-key"}
    ).create(profile)
    assert provider.model == "claude-haiku-4-5-20251001"
    assert hasattr(provider, "aclose")


def test_select_profile_leaks_no_client() -> None:
    """Selecting a model repeatedly is what an owner does while choosing one."""
    router = ModelRouter(
        ModelProfileRegistry.load(),
        runtime_policy=ProviderRuntimePolicy(),
    )
    before = _open_async_clients()
    for _ in range(5):
        router.select_profile("ollama-local-openai-compatible")
    assert _open_async_clients() == before
    assert router.active_profile_id == "ollama-local-openai-compatible"


def test_launch_leaks_no_client() -> None:
    router = ModelRouter(
        ModelProfileRegistry.load(),
        runtime_policy=ProviderRuntimePolicy(),
    )
    profile = router.registry.resolve_profile_id("ollama-local-openai-compatible")
    before = _open_async_clients()
    for _ in range(5):
        result = router.launch(
            profile.provider,
            profile.model,
            session_id=new_id("sess_"),
            turn_id=None,
            client=CLIENT,
        )
        assert result.status == "completed"
    assert _open_async_clients() == before


# --- GCR-01: launch sees the owner's saved connection -----------------------


def test_launch_accepts_a_hosted_profile_configured_only_by_connection() -> None:
    """The defect: a key held in the vault was invisible to `launch`.

    The profile ships `requires_api_key` and reads `ANTHROPIC_API_KEY` from the
    environment. An owner who saved their key through Settings has it in the
    connection vault and nowhere else, so `launch` — which built its factory
    without the resolver — refused a profile that every real turn runs.
    """
    registry = ModelProfileRegistry.load()
    profile = _anthropic_profile()
    registry.register(profile)
    router = ModelRouter(
        registry,
        runtime_policy=HOSTED_POLICY,
        connection_resolver=lambda profile_id: (
            {"api_key": "sk-ant-saved-in-the-vault"}
            if profile_id == "anthropic-hosted"
            else None
        ),
    )
    result = router.launch(
        profile.provider,
        profile.model,
        session_id=new_id("sess_"),
        turn_id=None,
        client=CLIENT,
    )
    assert result.status == "completed"
    assert result.profile is not None
    assert result.profile.profile_id == "anthropic-hosted"


def test_launch_still_refuses_when_nothing_is_saved() -> None:
    """The same profile with nothing saved is still refused, fail-closed.

    The refusal is `model_egress_denied:no_allowlist`, which is the earliest
    honest one: with no saved connection and no environment allowlist there is
    no authority to reach `api.anthropic.com` at all, so the credential question
    is never reached. That is also the measure of GCR-01 — the connection is
    what authorises this profile's own endpoint, and `launch` could not see it.
    """
    registry = ModelProfileRegistry.load()
    registry.register(_anthropic_profile())
    router = ModelRouter(
        registry,
        runtime_policy=HOSTED_POLICY,
        connection_resolver=lambda profile_id: None,
    )
    result = router.launch(
        "anthropic",
        "claude-haiku-4-5-20251001",
        session_id=new_id("sess_"),
        turn_id=None,
        client=CLIENT,
    )
    assert result.status == "failed"
    assert result.message == "model_egress_denied:no_allowlist"


def test_validate_reads_the_endpoint_the_connection_names() -> None:
    """A saved endpoint is what gets validated, not the profile's shipped one."""
    profile = _anthropic_profile()
    resolved = ModelProviderFactory(
        policy=HOSTED_POLICY,
        connection={"api_key": "sk-ant-test", "endpoint": "https://proxy.example.com"},
    ).resolve(profile)
    assert resolved.endpoint == "https://proxy.example.com"


def test_validate_rejects_a_stored_workspace_id_of_the_wrong_shape() -> None:
    """BUG-274's check now runs at validation, not first turn.

    It used to live inside the branch that constructs the Anthropic provider, so
    a malformed stored workspace id passed every validation in the product and
    failed only when a turn tried to run.
    """
    profile = _anthropic_profile()
    factory = ModelProviderFactory(
        policy=HOSTED_POLICY,
        connection={"api_key": "sk-ant-test", "workspace_id": "not a workspace id"},
    )
    with pytest.raises(ProviderConfigurationError):
        factory.validate(profile)


def test_validate_refuses_a_policy_gated_provider() -> None:
    """Validation is the same refusal `create` gives, not a weaker one."""
    profile = _anthropic_profile()
    with pytest.raises(ProviderPolicyError, match="policy_approval"):
        ModelProviderFactory(connection={"api_key": "sk-ant-test"}).validate(profile)


def test_router_validate_profile_uses_the_routers_own_connection() -> None:
    registry = ModelProfileRegistry.load()
    profile = _anthropic_profile()
    registry.register(profile)
    seen: list[str] = []

    def resolver(profile_id: str) -> dict[str, str] | None:
        seen.append(profile_id)
        return {"api_key": "sk-ant-test"}

    router = ModelRouter(
        registry, runtime_policy=HOSTED_POLICY, connection_resolver=resolver
    )
    router.validate_profile(profile)
    assert seen == ["anthropic-hosted"]


# --- GCR-03: reasoning is judged against the model that will run ------------


def test_reasoning_target_is_the_native_default_not_the_first_profile() -> None:
    """`list_profiles()[0]` is a position in a shipped file, not a choice."""
    registry = ModelProfileRegistry.load()
    router = ModelRouter(registry)
    assert registry.list_profiles()[0].profile_id == "raiker-local-llama-cpp"
    assert router.reasoning_profile().profile_id == router.default_profile().profile_id
    assert router.reasoning_profile().raw.get("is_native_default") is True


def test_reasoning_target_follows_the_active_selection() -> None:
    registry = ModelProfileRegistry.load()
    registry.register(_anthropic_profile())
    router = ModelRouter(registry, runtime_policy=HOSTED_POLICY)
    router.active_profile_id = "anthropic-hosted"
    assert router.reasoning_profile().profile_id == "anthropic-hosted"


def test_set_reasoning_accepts_a_mode_the_named_profile_supports() -> None:
    """The defect, stated as behaviour: a reasoning model may be set to reason.

    Before the fix this raised `reasoning_not_supported`, because the profile it
    consulted was the first llama.cpp entry in the registry rather than the
    Anthropic profile the owner had selected.
    """
    registry = ModelProfileRegistry.load()
    registry.register(_anthropic_profile())
    router = ModelRouter(registry, runtime_policy=HOSTED_POLICY)
    message = router.set_reasoning("adaptive", profile_id="anthropic-hosted")
    assert message == "Reasoning mode set to adaptive."
    assert router.reasoning is not None
    assert router.reasoning.enabled is True


def test_set_reasoning_follows_the_active_profile_without_being_told() -> None:
    registry = ModelProfileRegistry.load()
    registry.register(_anthropic_profile())
    router = ModelRouter(registry, runtime_policy=HOSTED_POLICY)
    router.active_profile_id = "anthropic-hosted"
    assert router.set_reasoning("adaptive") == "Reasoning mode set to adaptive."


def test_set_reasoning_still_refuses_a_profile_that_declares_no_reasoning() -> None:
    router = ModelRouter(ModelProfileRegistry.load())
    with pytest.raises(ProviderPolicyError, match="reasoning_not_supported"):
        router.set_reasoning("adaptive", profile_id="raiker-local-llama-cpp")


def test_set_reasoning_off_needs_no_reasoning_support() -> None:
    router = ModelRouter(ModelProfileRegistry.load())
    assert router.set_reasoning("off") == "Reasoning controls disabled."


# --- GCR-04, GCR-18: the parameters that did nothing ------------------------


def test_generate_no_longer_accepts_a_context_it_would_ignore() -> None:
    router = ModelRouter(ModelProfileRegistry.load())
    with pytest.raises(TypeError):
        router.generate("ollama", "gemma4:31b-cloud", "hi", {"unused": True})  # type: ignore[call-arg]


def test_default_provider_no_longer_accepts_an_unused_timeout() -> None:
    router = ModelRouter(ModelProfileRegistry.load())
    with pytest.raises(TypeError):
        router.default_provider(health_timeout=1.0)  # type: ignore[call-arg]
