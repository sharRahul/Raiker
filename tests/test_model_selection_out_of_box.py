from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from raiker.cli.commands import handle_model_command
from raiker.gateway.agent_gateway import AgentGateway
from raiker.models.exceptions import ProviderConfigurationError
from raiker.models.factory import ModelProviderFactory
from raiker.models.registry import ModelProfileRegistry, profile_with_model
from raiker.models.session_state import TERMINAL_MODEL_SESSION_ID, ModelSessionState
from raiker.storage.sqlite import SQLiteStore

OLLAMA = "ollama-local-openai-compatible"
LLAMA_CPP_DEFAULT = ("llama.cpp", "local-gguf")


def test_model_session_state_persists_resolved_model(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.save_model_session_state(
        ModelSessionState(session_id=TERMINAL_MODEL_SESSION_ID, profile_id=OLLAMA, model="llama3.1")
    )
    loaded = store.load_model_session_state(TERMINAL_MODEL_SESSION_ID)
    assert loaded is not None
    assert loaded.profile_id == OLLAMA
    assert loaded.model == "llama3.1"


def test_factory_lists_placeholder_profile_without_requiring_model() -> None:
    registry = ModelProfileRegistry.load()
    profile = registry.resolve_profile_id(OLLAMA)
    # Default requires a concrete model and rejects the "<model>" placeholder.
    with pytest.raises(ProviderConfigurationError):
        ModelProviderFactory().create(profile)
    # Listing does not need a concrete model name.
    provider = ModelProviderFactory().create(profile, require_model=False)
    try:
        assert provider is not None
    finally:
        asyncio.run(provider.aclose())


def test_profiles_for_provider_and_profile_with_model() -> None:
    registry = ModelProfileRegistry.load()
    profiles = registry.profiles_for_provider("ollama")
    assert any(p.profile_id == OLLAMA for p in profiles)
    effective = profile_with_model(profiles[0], "llama3.1")
    assert effective.model == "llama3.1"
    assert effective.raw["model"] == "llama3.1"


def test_gateway_uses_native_default_without_selection(tmp_path: Path) -> None:
    gateway = AgentGateway(tmp_path)
    assert gateway.default_provider == LLAMA_CPP_DEFAULT


def test_gateway_honors_selected_resolved_model(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.save_model_session_state(
        ModelSessionState(session_id=TERMINAL_MODEL_SESSION_ID, profile_id=OLLAMA, model="llama3.1")
    )
    gateway = AgentGateway(tmp_path)
    assert gateway.default_provider == ("ollama", "llama3.1")
    resolved = gateway.model_registry.resolve(*gateway.default_provider)
    assert resolved.model == "llama3.1"


def test_gateway_falls_back_when_placeholder_unresolved(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.save_model_session_state(
        ModelSessionState(session_id=TERMINAL_MODEL_SESSION_ID, profile_id=OLLAMA, model=None)
    )
    gateway = AgentGateway(tmp_path)
    assert gateway.default_provider == LLAMA_CPP_DEFAULT


def test_cli_use_explicit_model_persists(tmp_path: Path) -> None:
    out = handle_model_command(
        "/model use --provider ollama --model llama3.1", workspace_root=tmp_path
    )
    assert "llama3.1" in out
    state = SQLiteStore(tmp_path).load_model_session_state(TERMINAL_MODEL_SESSION_ID)
    assert state is not None
    assert state.profile_id == OLLAMA
    assert state.model == "llama3.1"
