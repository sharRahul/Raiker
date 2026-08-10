"""Readiness has an owner-set TTL, not one fixed window (BUG-83)."""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from raiker.contracts.ids import utc_now
from raiker.models.readiness import (
    DEFAULT_READINESS_TTL_MINUTES,
    MAX_READINESS_TTL_MINUTES,
    MIN_READINESS_TTL_MINUTES,
    ModelReadiness,
    ModelReadinessKey,
    ModelReadinessService,
    ModelReadinessState,
    readiness_ttl_minutes,
)
from raiker.storage.sqlite import SQLiteStore

OWNER = "owner-1"


class _Probe:
    """Answers ready, so the test is about the window rather than the provider."""

    async def check(self, key: ModelReadinessKey) -> ModelReadiness:
        return ModelReadiness(
            key=key, state=ModelReadinessState.READY, checked_at=None, expires_at=None,
            summary="reachable", reason_code="model_ready", remediation="", evidence={},
        )


def _save(store: SQLiteStore, settings: dict[str, object]) -> None:
    store.put_user_settings(OWNER, json.dumps(settings), utc_now())


def test_an_unset_preference_resolves_to_the_default(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    assert readiness_ttl_minutes(store, OWNER) == DEFAULT_READINESS_TTL_MINUTES
    _save(store, {"general.language": "en-GB"})
    assert readiness_ttl_minutes(store, OWNER) == DEFAULT_READINESS_TTL_MINUTES


def test_both_settings_shapes_are_accepted(tmp_path: Path) -> None:
    """The blob carries flat dotted keys and nested objects; neither silently wins."""
    store = SQLiteStore(tmp_path)
    _save(store, {"models.readiness_ttl_minutes": 30})
    assert readiness_ttl_minutes(store, OWNER) == 30
    _save(store, {"models": {"readiness_ttl_minutes": 45}})
    assert readiness_ttl_minutes(store, OWNER) == 45


def test_the_preference_is_clamped_rather_than_trusted(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    _save(store, {"models.readiness_ttl_minutes": 0})
    assert readiness_ttl_minutes(store, OWNER) == MIN_READINESS_TTL_MINUTES
    _save(store, {"models.readiness_ttl_minutes": 100_000})
    assert readiness_ttl_minutes(store, OWNER) == MAX_READINESS_TTL_MINUTES


def test_a_malformed_preference_never_blocks_a_turn(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    _save(store, {"models.readiness_ttl_minutes": "not a number"})
    assert readiness_ttl_minutes(store, OWNER) == DEFAULT_READINESS_TTL_MINUTES


def test_a_check_expires_after_the_owners_window(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    _save(store, {"models.readiness_ttl_minutes": 45})
    now = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    service = ModelReadinessService(store, probe=_Probe(), clock=lambda: now)

    readiness = asyncio.run(service.check(OWNER, "anthropic-hosted", "claude", "fp"))

    assert readiness.expires_at is not None
    expires = datetime.fromisoformat(readiness.expires_at)
    assert expires - now == timedelta(minutes=45)


def test_an_explicit_ttl_still_wins_for_a_caller_that_sets_one(tmp_path: Path) -> None:
    """Tests and one-off callers keep a fixed window; the product takes the owner's."""
    store = SQLiteStore(tmp_path)
    _save(store, {"models.readiness_ttl_minutes": 45})
    now = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    service = ModelReadinessService(
        store, probe=_Probe(), clock=lambda: now, ttl=timedelta(minutes=2)
    )

    readiness = asyncio.run(service.check(OWNER, "anthropic-hosted", "claude", "fp"))

    assert readiness.expires_at is not None
    assert datetime.fromisoformat(readiness.expires_at) - now == timedelta(minutes=2)
