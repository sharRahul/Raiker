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
