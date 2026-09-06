"""GCR-46 — an unreadable pin store is not an unset one.

A hosted profile ships a `<model>` placeholder, so the model it runs is the one
the owner pinned. Three readers of that pin — the gateway resolving a turn's
profile, readiness resolving the target it reports on, and the advisor resolving
what a consult would call — each caught every exception from the store and
returned `None`.

`None` already means "the owner pinned nothing", and for a placeholder profile
that makes the profile unrunnable. So a storage failure did not surface as a
storage failure: it dropped the owner's model from the fallback chain, reported
`not_configured` about a model they had configured, and sent them to redo a
choice that was stored and merely unreadable.
"""

from __future__ import annotations

from typing import Any

import pytest

from raiker.models.configured_models import (
    ConfiguredModelStoreUnavailable,
    pinned_model,
)
from raiker.models.readiness import (
    ModelReadinessService,
    ModelReadinessState,
)

OWNER = "prin_owner"


class _ReadableStore:
    """A store that answers, with one pin saved for a hosted profile."""

    def __init__(self, pairs: list[tuple[str, str]] | None = None) -> None:
        self._pairs = pairs if pairs is not None else [
            ("anthropic-hosted", "claude-haiku-4-5-20251001")
        ]

    def list_configured_models(self, principal_id: str) -> list[tuple[str, str]]:
        return list(self._pairs)


class _UnreadableStore:
    """A store whose read fails — a locked database, a corrupt page, a bad disk."""

    def list_configured_models(self, principal_id: str) -> list[tuple[str, str]]:
        raise OSError("database is locked")


# --- the helper -------------------------------------------------------------


def test_a_readable_store_with_a_pin_answers_with_it() -> None:
    assert (
        pinned_model(_ReadableStore(), OWNER, "anthropic-hosted")
        == "claude-haiku-4-5-20251001"
    )


def test_a_readable_store_without_a_pin_answers_none() -> None:
    """`None` keeps its one meaning: read, and nothing is pinned."""
    assert pinned_model(_ReadableStore([]), OWNER, "anthropic-hosted") is None
    assert pinned_model(_ReadableStore(), OWNER, "openai-hosted") is None


def test_the_most_recent_pin_wins() -> None:
    store = _ReadableStore(
        [("anthropic-hosted", "claude-old"), ("anthropic-hosted", "claude-new")]
    )
    assert pinned_model(store, OWNER, "anthropic-hosted") == "claude-new"


def test_an_unreadable_store_raises_rather_than_answering_none() -> None:
    with pytest.raises(ConfiguredModelStoreUnavailable) as raised:
        pinned_model(_UnreadableStore(), OWNER, "anthropic-hosted")
    assert str(raised.value) == "configured_model_store_unavailable"
    assert isinstance(raised.value.__cause__, OSError)


# --- readiness --------------------------------------------------------------


class _ReadinessStore(_UnreadableStore):
    """Everything readiness needs, with only the pin read failing."""

    def __init__(self) -> None:
        self.saved: list[Any] = []

    def save_model_readiness(self, readiness: Any) -> None:
        self.saved.append(readiness)

    def load_model_readiness(self, key: Any) -> Any:
        return None

    def invalidate_model_readiness(
        self, owner_principal_id: str, profile_id: str, *, reason_code: str = ""
    ) -> int:
        return 0

    def list_model_readiness(
        self, owner_principal_id: str, profile_id: str | None = None
    ) -> list[Any]:
        return []

    def get_account(self, principal_id: str) -> Any:
        return None

    def load_principal_model_state(self, principal_id: str) -> Any:
        return None

    def load_model_session_state(self, session_id: str) -> Any:
        return None

    def load_principal_model_fallback_sequence(self, principal_id: str) -> list[str]:
        return []

    def load_model_fallback_sequence(self, session_id: str) -> list[str]:
        return []


class _Probe:
    async def check(self, key: Any) -> Any:  # pragma: no cover - never reached
        raise AssertionError("a chain that cannot resolve must not reach a provider")

    def resolve_key(self, owner: str, profile_id: str, model: str) -> Any:
        return ModelReadinessService.key(owner, profile_id, model, "fingerprint")


def _service() -> tuple[ModelReadinessService, _ReadinessStore]:
    store = _ReadinessStore()
    return ModelReadinessService(store=store, probe=_Probe()), store


def test_the_chain_names_the_storage_failure_instead_of_resolving_anyway() -> None:
    """The interface outcome: a named state, not a verdict about the model."""
    service, _ = _service()
    chain = service.resolve_chain(OWNER, "anthropic-hosted", None)
    assert len(chain) == 1
    entry = chain[0]
    assert entry.state is ModelReadinessState.CONFIGURATION_UNREADABLE
    assert entry.reason_code == "configured_model_store_unavailable"
    assert entry.ready is False
    # Not `not_configured`: that one asks the owner to choose a model, and they
    # already did.
    assert entry.state is not ModelReadinessState.NOT_CONFIGURED


def test_the_owner_is_told_it_is_storage_and_not_their_model() -> None:
    service, _ = _service()
    entry = service.resolve_chain(OWNER, "anthropic-hosted", None)[0]
    assert "could not read which model you chose" in entry.summary
    assert "storage failure" in entry.remediation
    assert "not a problem with" in entry.remediation


def test_the_turn_is_refused_with_that_reason() -> None:
    from raiker.models.readiness import ModelNotReady

    service, _ = _service()
    with pytest.raises(ModelNotReady) as raised:
        service.require_ready(OWNER, "anthropic-hosted", None)
    detail = raised.value.detail()["readiness"]
    assert isinstance(detail, dict)
    assert detail["state"] == "configuration_unreadable"
    assert detail["reason_code"] == "configured_model_store_unavailable"


def test_the_degraded_entry_is_never_stored() -> None:
    """It describes the moment the question was asked, not a provider."""
    service, store = _service()
    service.resolve_chain(OWNER, "anthropic-hosted", None)
    assert store.saved == []


class _ReadableReadinessStore(_ReadinessStore):
    """The same store with a readable pin, so only the failing case differs."""

    def list_configured_models(self, principal_id: str) -> list[tuple[str, str]]:
        return [("anthropic-hosted", "claude-haiku-4-5-20251001")]


def test_a_readable_store_resolves_the_pin_and_reports_on_it() -> None:
    """The whole point is that only the failing case changed."""
    service = ModelReadinessService(store=_ReadableReadinessStore(), probe=_Probe())
    chain = service.resolve_chain(OWNER, "anthropic-hosted", None)
    assert chain[0].state is not ModelReadinessState.CONFIGURATION_UNREADABLE
    assert chain[0].key.model == "claude-haiku-4-5-20251001"
