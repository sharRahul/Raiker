from __future__ import annotations

import json
import os
import secrets
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from raiker.api.sessions import ApiSessionStore
from raiker.auth import passwords
from raiker.cli.principal_resolver import OWNER_BOOTSTRAP_ROLES, _ensure_bootstrap_roles
from raiker.contracts.ids import new_id, utc_now
from raiker.models.exceptions import ProviderConnectionError
from raiker.models.providers.openai_compatible import AsyncOpenAICompatibleProvider
from raiker.models.readiness import (
    ModelReadiness,
    ModelReadinessService,
    ModelReadinessState,
    ProviderCatalogueProbe,
)
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture(scope="session", autouse=True)
def _ensure_git_identity() -> None:
    """Guarantee a git author/committer identity for tests that create commits.

    Several tests initialise a throwaway git repository and run ``git commit``
    (e.g. the code-review and proposal-lifecycle suites). CI runners have no
    global git identity configured, so those commits fail with exit status 128
    ("Author identity unknown"). Populate the standard git identity environment
    variables when they are absent. ``setdefault`` only fills missing values, so
    developer machines that already have a global identity are unaffected.
    """
    os.environ.setdefault("GIT_AUTHOR_NAME", "Raiker Test")
    os.environ.setdefault("GIT_AUTHOR_EMAIL", "raiker-test@example.com")
    os.environ.setdefault("GIT_COMMITTER_NAME", "Raiker Test")
    os.environ.setdefault("GIT_COMMITTER_EMAIL", "raiker-test@example.com")


@pytest.fixture()
def offline_default_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make tests that exercise offline finalisation independent of local Ollama.

    Ollama is Raiker's native default and may legitimately be running on a
    developer machine. Tests for gateway, hook, checkpoint, and terminal
    behaviour must opt into an unavailable provider instead of treating the
    host's model availability as part of their contract.
    """

    async def unavailable_chat(*_args: Any, **_kwargs: Any) -> Any:
        raise ProviderConnectionError("provider_connection_failed")

    async def unavailable_stream(
        *_args: Any, **_kwargs: Any
    ) -> AsyncIterator[Any]:
        raise ProviderConnectionError("provider_connection_failed")
        yield  # pragma: no cover - keeps this an async generator

    monkeypatch.setattr(AsyncOpenAICompatibleProvider, "chat", unavailable_chat)
    monkeypatch.setattr(AsyncOpenAICompatibleProvider, "stream_chat", unavailable_stream)

    def previously_ready(
        service: ModelReadinessService,
        owner_principal_id: str,
        profile_id: str | None,
        model: str | None,
    ) -> ModelReadiness:
        resolved_profile, resolved_model = service.resolve_request_target(
            owner_principal_id, profile_id, model
        )
        key = service._selected_key(  # noqa: SLF001 - readiness is this fixture's boundary
            owner_principal_id, resolved_profile, resolved_model
        )
        now = datetime.now(UTC)
        readiness = ModelReadiness(
            key=key,
            state=ModelReadinessState.READY,
            checked_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=5)).isoformat(),
            summary="The exact model was reachable before the simulated outage.",
            reason_code="model_ready",
            remediation="",
            evidence={"source": "offline_default_model_fixture"},
        )
        service.store.save_model_readiness(readiness)
        return readiness

    monkeypatch.setattr(ModelReadinessService, "require_ready", previously_ready)


SeedAccount = Callable[..., tuple[str, str]]
MarkModelReady = Callable[[Path, str, str, str], None]


@pytest.fixture()
def mark_model_ready() -> MarkModelReady:
    """Seed one exact, short-lived observation for downstream behavior tests."""

    def _mark(
        workspace: Path,
        principal_id: str = "principal_owner",
        profile_id: str = "ollama-local-openai-compatible",
        model: str = "gemma4:31b-cloud",
    ) -> None:
        store = SQLiteStore(workspace)
        key = ProviderCatalogueProbe(store).resolve_key(principal_id, profile_id, model)
        now = datetime.now(UTC)
        store.save_model_readiness(
            ModelReadiness(
                key=key,
                state=ModelReadinessState.READY,
                checked_at=now.isoformat(),
                expires_at=(now + timedelta(minutes=5)).isoformat(),
                summary="The exact model is reachable.",
                reason_code="model_ready",
                remediation="",
                evidence={"source": "test_fixture"},
            )
        )

    return _mark


@pytest.fixture()
def seed_account() -> SeedAccount:
    """Create an extra credential-backed account directly in the database.

    The product policy is one credential-backed human account per local
    instance, so ``/api/auth/register`` refuses a second account and cannot be
    used to build a cross-account fixture. Owner isolation is still live code —
    a recovered-from owner, a CLI-bootstrapped owner, and delegated principals
    all coexist in one database — so the isolation invariants still need a
    second account to prove. Seed it the way the handoff sanctions: straight
    into the tables ``create_initial_account_atomic`` would have written, minus
    the ``instance_account_guard`` claim that enforces the one-account rule.

    Returns the new ``(principal_id, control_session_token)``.
    """

    def _seed(
        workspace: Path, username: str = "bob", password: str = "right-pass-123"
    ) -> tuple[str, str]:
        store = SQLiteStore(workspace)
        _ensure_bootstrap_roles(store)
        now = utc_now()
        user_id = f"user_{secrets.token_hex(8)}"
        principal_id = f"principal_{user_id}"
        encoded, algo = passwords.hash_password(password)
        with store.connect() as connection:
            connection.execute(
                "INSERT INTO users (user_id, display_name, email, is_active, created_at, updated_at) "
                "VALUES (?, ?, NULL, 1, ?, ?)",
                (user_id, username, now, now),
            )
            connection.execute(
                """INSERT INTO principals (principal_id, principal_type, display_name,
                delegated_by_user_id, role_ids, domain_scopes, max_runtime_mode, created_at, is_active)
                VALUES (?, 'human', ?, ?, ?, '[]', 'multi_user_local_runtime', ?, 1)""",
                (principal_id, username, user_id, json.dumps(list(OWNER_BOOTSTRAP_ROLES)), now),
            )
            connection.executemany(
                "INSERT INTO user_role_assignments (assignment_id, user_id, role_id, granted_at, granted_by) "
                "VALUES (?, ?, ?, ?, 'test_fixture')",
                [(new_id("ura_"), user_id, role_id, now) for role_id in OWNER_BOOTSTRAP_ROLES],
            )
            connection.execute(
                "INSERT INTO account_credentials (principal_id, username, password_hash, hash_algo, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (principal_id, username, encoded, algo, now, now),
            )
        store.initialize_principal_controls(principal_id)
        token, _ = ApiSessionStore(workspace).create_session(principal_id, scope="control")
        return principal_id, token

    return _seed
