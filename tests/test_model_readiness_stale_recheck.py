"""BUG-238 — a stale observation is re-checked, not turned into a setup prompt.

A readiness observation has a TTL so that no turn runs on a claim older than the
owner's window. It was *also* deciding whether the model was set up at all: once
the window passed, `state` became `stale`, `ready` became false, and every
surface asked the owner to **set up a model they had already set up** — after
every restart, and after any five idle minutes.

Staleness is not unavailability. It means "this worked, and nobody has looked
recently", and the honest response is to look. These tests hold both halves:
the re-check happens, and the TTL keeps its meaning because a turn is admitted
on the *fresh* observation rather than on the expired one.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models.readiness import (
    ModelNotReady,
    ModelReadiness,
    ModelReadinessKey,
    ModelReadinessService,
    ModelReadinessState,
    ProviderCatalogueProbe,
)
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"
PROFILE = "ollama-local-openai-compatible"
MODEL = "gemma4:31b-cloud"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "stale-recheck"
    root.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=root)
    return root


class _CountingProbe:
    """A probe that records every call and answers however the test wants."""

    def __init__(self, store: SQLiteStore, *, state: ModelReadinessState) -> None:
        self._inner = ProviderCatalogueProbe(store)
        self.state = state
        self.calls = 0

    def resolve_key(
        self, owner_principal_id: str, profile_id: str, model: str
    ) -> ModelReadinessKey:
        return self._inner.resolve_key(owner_principal_id, profile_id, model)

    async def check(self, key: ModelReadinessKey) -> ModelReadiness:
        self.calls += 1
        ready = self.state is ModelReadinessState.READY
        return ModelReadiness(
            key=key,
            state=self.state,
            checked_at=None,
            expires_at=None,
            summary="reachable" if ready else "the provider rejected the credential",
            reason_code="model_ready" if ready else "authentication_failed",
            remediation="" if ready else "Re-enter the API key in Models.",
            evidence={"source": "counting_probe"},
        )


def _expire(store: SQLiteStore, workspace: Path) -> ModelReadinessKey:
    """Store a READY observation whose window has already closed."""
    key = ProviderCatalogueProbe(store).resolve_key(OWNER, PROFILE, MODEL)
    past = datetime.now(UTC) - timedelta(hours=2)
    store.save_model_readiness(
        ModelReadiness(
            key=key,
            state=ModelReadinessState.READY,
            checked_at=past.isoformat(),
            expires_at=(past + timedelta(minutes=5)).isoformat(),
            summary="The exact model is reachable.",
            reason_code="model_ready",
            remediation="",
            evidence={"source": "test_fixture"},
        )
    )
    return key


def test_the_stored_observation_really_does_read_as_stale(workspace: Path) -> None:
    """The precondition every other test here depends on."""
    store = SQLiteStore(workspace)
    key = _expire(store, workspace)
    service = ModelReadinessService(store, probe=ProviderCatalogueProbe(store))

    current = service.current(OWNER, key.profile_id, key.model, key.endpoint_fingerprint)

    assert current.state is ModelReadinessState.STALE
    assert current.ready is False


def test_the_pure_read_still_refuses_a_stale_model(workspace: Path) -> None:
    """`require_ready` never reaches a provider; that is what it is for."""
    store = SQLiteStore(workspace)
    _expire(store, workspace)
    probe = _CountingProbe(store, state=ModelReadinessState.READY)
    service = ModelReadinessService(store, probe=probe)

    with pytest.raises(ModelNotReady):
        service.require_ready(OWNER, PROFILE, MODEL)
    assert probe.calls == 0


def test_a_stale_model_is_rechecked_and_admitted(workspace: Path) -> None:
    store = SQLiteStore(workspace)
    _expire(store, workspace)
    probe = _CountingProbe(store, state=ModelReadinessState.READY)
    service = ModelReadinessService(store, probe=probe)

    readiness = asyncio.run(service.require_ready_async(OWNER, PROFILE, MODEL))

    assert readiness.ready is True
    assert probe.calls == 1, "the stale entry is re-checked exactly once"


def test_the_turn_runs_on_the_fresh_observation_not_the_expired_one(
    workspace: Path,
) -> None:
    """The TTL keeps its whole meaning: the admitted claim is newly taken."""
    store = SQLiteStore(workspace)
    _expire(store, workspace)
    service = ModelReadinessService(
        store, probe=_CountingProbe(store, state=ModelReadinessState.READY)
    )

    readiness = asyncio.run(service.require_ready_async(OWNER, PROFILE, MODEL))

    assert readiness.expires_at is not None
    assert datetime.fromisoformat(readiness.expires_at) > datetime.now(UTC)
    # And it was persisted, so the next surface reads the same fresh answer.
    stored = service.current(
        OWNER, readiness.key.profile_id, readiness.key.model,
        readiness.key.endpoint_fingerprint,
    )
    assert stored.ready is True


def test_a_recheck_that_fails_still_refuses_and_reports_the_fresh_reason(
    workspace: Path,
) -> None:
    """"Your key was rejected" is worth far more than "the last check expired"."""
    store = SQLiteStore(workspace)
    _expire(store, workspace)
    probe = _CountingProbe(store, state=ModelReadinessState.AUTHENTICATION_FAILED)
    service = ModelReadinessService(store, probe=probe)

    with pytest.raises(ModelNotReady) as caught:
        asyncio.run(service.require_ready_async(OWNER, PROFILE, MODEL))

    assert probe.calls == 1
    assert caught.value.readiness.reason_code == "authentication_failed"
    assert caught.value.readiness.state is ModelReadinessState.AUTHENTICATION_FAILED


def test_a_never_checked_model_is_not_rechecked_behind_the_owners_back(
    workspace: Path,
) -> None:
    """Only an aged-out observation is re-taken.

    A model with no observation at all has nothing that "worked before", so the
    owner is still told to set it up rather than having Raiker quietly reach a
    provider they never configured.
    """
    store = SQLiteStore(workspace)
    probe = _CountingProbe(store, state=ModelReadinessState.READY)
    service = ModelReadinessService(store, probe=probe)

    with pytest.raises(ModelNotReady) as caught:
        asyncio.run(service.require_ready_async(OWNER, PROFILE, MODEL))

    assert probe.calls == 0
    assert caught.value.readiness.state is ModelReadinessState.NOT_CONFIGURED


def test_a_ready_model_is_admitted_without_reaching_the_provider(
    workspace: Path, mark_model_ready: object
) -> None:
    """The common path stays free: a live observation costs no request."""
    store = SQLiteStore(workspace)
    key = ProviderCatalogueProbe(store).resolve_key(OWNER, PROFILE, MODEL)
    now = datetime.now(UTC)
    store.save_model_readiness(
        ModelReadiness(
            key=key, state=ModelReadinessState.READY, checked_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=5)).isoformat(),
            summary="The exact model is reachable.", reason_code="model_ready",
            remediation="", evidence={},
        )
    )
    probe = _CountingProbe(store, state=ModelReadinessState.READY)
    service = ModelReadinessService(store, probe=probe)

    readiness = asyncio.run(service.require_ready_async(OWNER, PROFILE, MODEL))

    assert readiness.ready is True
    assert probe.calls == 0


def test_a_deliberately_invalidated_connection_is_not_rechecked(
    workspace: Path, mark_model_ready: object
) -> None:
    """`STALE` carries two meanings and only one of them may be auto-resolved.

    `invalidate_model_readiness` writes `STALE` when something changed *under*
    the model — a connection, an endpoint, a credential, a pulled model. The
    stored observation no longer describes reality, and the owner asked for that
    check by changing the thing. Re-checking it silently would collapse the two
    meanings into one, which is the defect this whole area keeps producing.
    """
    store = SQLiteStore(workspace)
    key = ProviderCatalogueProbe(store).resolve_key(OWNER, PROFILE, MODEL)
    now = datetime.now(UTC)
    store.save_model_readiness(
        ModelReadiness(
            key=key, state=ModelReadinessState.READY, checked_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=5)).isoformat(),
            summary="The exact model is reachable.", reason_code="model_ready",
            remediation="", evidence={},
        )
    )
    store.invalidate_model_readiness(OWNER, PROFILE, reason_code="runtime_changed")
    probe = _CountingProbe(store, state=ModelReadinessState.READY)
    service = ModelReadinessService(store, probe=probe)

    with pytest.raises(ModelNotReady) as caught:
        asyncio.run(service.require_ready_async(OWNER, PROFILE, MODEL))

    assert probe.calls == 0, "an invalidated connection keeps its explicit re-check"
    assert caught.value.readiness.reason_code == "runtime_changed"


def test_only_the_expired_reason_is_treated_as_merely_stale() -> None:
    """The predicate reads the reason, not the state alone."""
    from raiker.models.readiness import READINESS_EXPIRED_REASON, _has_merely_expired

    key = ModelReadinessKey(OWNER, PROFILE, MODEL, "fp")

    def _stale(reason: str) -> ModelReadiness:
        return ModelReadiness(
            key=key, state=ModelReadinessState.STALE, checked_at=None, expires_at=None,
            summary="", reason_code=reason, remediation="", evidence={},
        )

    assert _has_merely_expired(_stale(READINESS_EXPIRED_REASON)) is True
    assert _has_merely_expired(_stale("runtime_changed")) is False
    assert _has_merely_expired(_stale("readiness_invalidated")) is False


def test_a_probe_that_raises_refuses_rather_than_escaping(workspace: Path) -> None:
    """A transport failure during the re-check is a refusal, not a 500."""

    class _ExplodingProbe(_CountingProbe):
        async def check(self, key: ModelReadinessKey) -> ModelReadiness:
            self.calls += 1
            raise RuntimeError("connection reset")

    store = SQLiteStore(workspace)
    _expire(store, workspace)
    probe = _ExplodingProbe(store, state=ModelReadinessState.READY)
    service = ModelReadinessService(store, probe=probe)

    with pytest.raises(ModelNotReady):
        asyncio.run(service.require_ready_async(OWNER, PROFILE, MODEL))
    assert probe.calls == 1
