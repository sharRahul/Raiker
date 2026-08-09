from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from raiker.models.readiness import (
    ModelReadiness,
    ModelReadinessKey,
    ModelReadinessService,
    ModelReadinessState,
)
from raiker.storage.sqlite import SQLiteStore


class AnsweringProbe:
    async def check(self, key: ModelReadinessKey) -> ModelReadiness:
        return ModelReadiness(
            key=key,
            state=ModelReadinessState.READY,
            checked_at="2026-08-09T09:00:00+00:00",
            expires_at="2026-08-09T09:05:00+00:00",
            summary="The exact model is reachable.",
            reason_code="model_ready",
            remediation="",
            evidence={"catalogue_match": True},
        )


def test_ready_is_exact_to_owner_profile_model_and_endpoint(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    service = ModelReadinessService(store, probe=AnsweringProbe())

    ready = asyncio.run(
        service.check(
            "owner-a",
            "ollama-local-openai-compatible",
            "gemma4:31b-cloud",
            "endpoint-a",
        )
    )

    assert ready.state is ModelReadinessState.READY
    assert (
        service.current(
            "owner-a",
            "ollama-local-openai-compatible",
            "other",
            "endpoint-a",
        ).state
        is ModelReadinessState.NOT_CONFIGURED
    )
    assert (
        service.current(
            "owner-b",
            "ollama-local-openai-compatible",
            "gemma4:31b-cloud",
            "endpoint-a",
        ).state
        is ModelReadinessState.NOT_CONFIGURED
    )
    assert (
        service.current(
            "owner-a",
            "ollama-local-openai-compatible",
            "gemma4:31b-cloud",
            "endpoint-b",
        ).state
        is ModelReadinessState.NOT_CONFIGURED
    )


def test_expired_observation_is_stale_not_ready(tmp_path: Path) -> None:
    now = datetime(2026, 8, 9, 10, 0, tzinfo=UTC)
    store = SQLiteStore(tmp_path)
    key = ModelReadinessKey("owner-a", "profile-a", "model-a", "endpoint-a")
    store.save_model_readiness(
        ModelReadiness(
            key=key,
            state=ModelReadinessState.READY,
            checked_at=(now - timedelta(minutes=10)).isoformat(),
            expires_at=(now - timedelta(minutes=5)).isoformat(),
            summary="The model was reachable.",
            reason_code="model_ready",
            remediation="",
            evidence={},
        )
    )

    current = ModelReadinessService(
        store,
        probe=AnsweringProbe(),
        clock=lambda: now,
    ).current("owner-a", "profile-a", "model-a", "endpoint-a")

    assert current.state is ModelReadinessState.STALE
    assert current.reason_code == "readiness_expired"
    assert current.remediation == "Check this model again before sending."


def test_profile_invalidation_marks_all_exact_observations_stale(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    service = ModelReadinessService(store, probe=AnsweringProbe())
    for model in ("model-a", "model-b"):
        asyncio.run(service.check("owner-a", "profile-a", model, "endpoint-a"))
    asyncio.run(service.check("owner-a", "profile-b", "model-a", "endpoint-a"))

    service.invalidate_profile("owner-a", "profile-a", reason_code="connection_changed")

    assert service.current("owner-a", "profile-a", "model-a", "endpoint-a").state is ModelReadinessState.STALE
    assert service.current("owner-a", "profile-a", "model-b", "endpoint-a").reason_code == "connection_changed"
    assert service.current("owner-a", "profile-b", "model-a", "endpoint-a").state is ModelReadinessState.READY


def test_persistence_redacts_sensitive_evidence(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    key = ModelReadinessKey("owner-a", "profile-a", "model-a", "endpoint-a")
    store.save_model_readiness(
        ModelReadiness(
            key=key,
            state=ModelReadinessState.AUTHENTICATION_FAILED,
            checked_at="2026-08-09T09:00:00+00:00",
            expires_at="2026-08-09T09:05:00+00:00",
            summary="Authentication failed.",
            reason_code="provider_authentication_failed",
            remediation="Update the provider credential.",
            evidence={
                "status_code": 401,
                "api_key": "secret-value",
                "authorization": "Bearer secret-value",
                "nested": {"token": "secret-value", "safe": "catalogue"},
            },
        )
    )

    loaded = store.load_model_readiness(key)

    assert loaded is not None
    assert loaded.evidence == {
        "status_code": 401,
        "api_key": "[redacted]",
        "authorization": "[redacted]",
        "nested": {"token": "[redacted]", "safe": "catalogue"},
    }
    assert b"secret-value" not in store.db_path.read_bytes()


def test_list_and_delete_are_owner_scoped(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    service = ModelReadinessService(store, probe=AnsweringProbe())
    asyncio.run(service.check("owner-a", "profile-a", "model-a", "endpoint-a"))
    asyncio.run(service.check("owner-b", "profile-a", "model-a", "endpoint-a"))

    assert [item.key.owner_principal_id for item in store.list_model_readiness("owner-a")] == ["owner-a"]
    assert store.invalidate_model_readiness("owner-a", "profile-a") == 1
    assert store.load_model_readiness(
        ModelReadinessKey("owner-b", "profile-a", "model-a", "endpoint-a")
    ) is not None
