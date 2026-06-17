from __future__ import annotations

import pytest

from raiker.contracts.ids import new_id
from raiker.contracts.models import ClientMetadata
from raiker.models.registry import ModelProfileRegistry, RegistryError
from raiker.models.router import ModelRouter


def test_mock_model_provider_deterministic() -> None:
    router = ModelRouter(ModelProfileRegistry.load())
    assert router.generate("mock", "mock-deterministic", "Hello") == router.generate(
        "mock", "mock-deterministic", "Hello"
    )


def test_unknown_provider_fails() -> None:
    router = ModelRouter(ModelProfileRegistry.load())
    with pytest.raises(RegistryError):
        router.generate("unknown", "model", "Hello")


def test_launch_resolves_mock_profile(tmp_path) -> None:  # type: ignore[no-untyped-def]
    router = ModelRouter(ModelProfileRegistry.load())
    result = router.launch(
        "mock",
        "mock-deterministic",
        session_id=new_id("sess_"),
        turn_id=None,
        client=ClientMetadata(type="test_harness", name="tests", version="0.0.0"),
    )
    assert result.status == "completed"
    assert result.profile is not None
    assert result.profile.profile_id == "mock-test"
