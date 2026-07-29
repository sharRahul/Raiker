from pathlib import Path

from raiker.storage.sqlite import SQLiteStore


def test_configured_models_keep_multiple_models_and_providers(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.bootstrap()

    store.save_configured_model("owner-a", "anthropic-hosted", "claude-haiku")
    store.save_configured_model("owner-a", "anthropic-hosted", "claude-opus")
    store.save_configured_model(
        "owner-a", "ollama-local-openai-compatible", "gemma4:31b-cloud"
    )

    assert store.list_configured_models("owner-a") == [
        ("anthropic-hosted", "claude-haiku"),
        ("anthropic-hosted", "claude-opus"),
        ("ollama-local-openai-compatible", "gemma4:31b-cloud"),
    ]
    assert store.list_configured_models("owner-b") == []


def test_saving_the_same_configured_model_is_idempotent(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.bootstrap()

    store.save_configured_model("owner-a", "anthropic-hosted", "claude-haiku")
    store.save_configured_model("owner-a", "anthropic-hosted", "claude-haiku")

    assert store.list_configured_models("owner-a") == [
        ("anthropic-hosted", "claude-haiku")
    ]
    assert store.is_configured_model(
        "owner-a", "anthropic-hosted", "claude-haiku"
    )
    assert not store.is_configured_model(
        "owner-b", "anthropic-hosted", "claude-haiku"
    )
