"""Credential pools: backup keys rotated on rate limits and empty quota.

A connection may hold up to three backup keys. A request whose key is rate
limited (429) or out of quota moves to the next key in the same turn; the
refused key sits out for a minute or an hour. Keys are only ever named by
position — no view, event or sentence carries a key's value.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.auth.vault_key_file import VAULT_KEY_ENV
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models import credential_pool
from raiker.models.connections import get_model_connection, put_model_connection
from raiker.models.contracts import ModelMessage, ModelResponse
from raiker.models.exceptions import ProviderQuotaExhaustedError, ProviderRateLimitError
from raiker.models.registry import ModelProfileRegistry
from raiker.models.router import ModelRouter
from raiker.storage.sqlite import SQLiteStore

PROFILE = "openai-hosted"
OWNER = "principal_owner"


@pytest.fixture(autouse=True)
def _fresh_pool() -> Any:
    credential_pool.forget()
    yield
    credential_pool.forget()


def test_rested_keys_come_first_and_the_benched_last() -> None:
    connection = {"api_key": "a", "api_key_2": "b", "api_key_3": "c", "label": "x"}
    assert [p for p, _ in credential_pool.attempt_order(PROFILE, connection, now=0)] == [1, 2, 3]
    credential_pool.bench(PROFILE, 1, "quota_exhausted", now=0)
    credential_pool.bench(PROFILE, 2, "rate_limited", now=0)
    order = credential_pool.attempt_order(PROFILE, connection, now=10)
    # Rested first, then the benched soonest-rested first.
    assert [p for p, _ in order] == [3, 2, 1]
    assert order[0][1] == {"api_key": "c", "label": "x"}
    # A rate limit rests a minute; afterwards the key is back in its place.
    assert [p for p, _ in credential_pool.attempt_order(PROFILE, connection, now=61)] == [2, 3, 1]


def test_a_single_key_is_used_as_it_is() -> None:
    assert credential_pool.attempt_order(PROFILE, {"api_key": "a"}) == [(1, {"api_key": "a"})]


def test_the_card_sentence_names_positions_never_values() -> None:
    connection = {"api_key": "sk-secret-primary", "api_key_2": "sk-secret-backup"}
    credential_pool.bench(PROFILE, 1, "rate_limited", now=0)
    credential_pool.record_use(PROFILE, 2)
    text = credential_pool.describe(PROFILE, connection, now=0)
    assert text == "Using backup key 2; key 1 rate limited for about 1 min."
    assert "secret" not in text


class _Provider:
    def __init__(self, key: str, sent: list[str], refuse: dict[str, Exception]) -> None:
        self.provider = "openai"
        self.model = "gpt-test"
        self._key = key
        self._sent = sent
        self._refuse = refuse

    async def chat(self, _request: Any) -> ModelResponse:
        self._sent.append(self._key)
        if self._key in self._refuse:
            raise self._refuse[self._key]
        return ModelResponse(text=f"answered with {self._key}")

    async def stream_chat(self, request: Any) -> Any:
        self._sent.append(self._key)
        if self._key in self._refuse:
            raise self._refuse[self._key]
        yield {"type": "text", "text": "hi"}

    async def aclose(self) -> None: ...


def _router(monkeypatch: pytest.MonkeyPatch, connection: dict[str, str], refuse: dict[str, Exception]):  # type: ignore[no-untyped-def]
    sent: list[str] = []
    router = ModelRouter(ModelProfileRegistry.load(), connection_resolver=lambda _pid: connection)

    class _Factory:
        def __init__(self, key: str) -> None:
            self.key = key

        def create(self, _profile: Any) -> _Provider:
            return _Provider(self.key, sent, refuse)

    monkeypatch.setattr(
        router, "_factory", lambda _profile, conn=None: _Factory((conn or connection)["api_key"])
    )
    return router, sent


def test_a_rate_limited_key_hands_the_turn_to_the_next(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = {"api_key": "k1", "api_key_2": "k2"}
    router, sent = _router(monkeypatch, connection, {"k1": ProviderRateLimitError("provider_rate_limited")})
    response = asyncio.run(router.achat("openai", "gpt-test", [ModelMessage("user", "hi")]))
    assert response.text == "answered with k2"
    assert sent == ["k1", "k2"]
    # The refused key sits out: the next turn starts on key 2.
    asyncio.run(router.achat("openai", "gpt-test", [ModelMessage("user", "again")]))
    assert sent == ["k1", "k2", "k2"]


def test_an_empty_quota_rotates_too_and_every_key_spent_reports_it(monkeypatch: pytest.MonkeyPatch) -> None:
    spent = ProviderQuotaExhaustedError("provider_quota_exhausted:http_402")
    connection = {"api_key": "k1", "api_key_2": "k2"}
    router, sent = _router(monkeypatch, connection, {"k1": spent, "k2": spent})
    with pytest.raises(ProviderQuotaExhaustedError):
        asyncio.run(router.achat("openai", "gpt-test", [ModelMessage("user", "hi")]))
    assert sent == ["k1", "k2"]


def test_a_stream_rotates_only_before_anything_streamed(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = {"api_key": "k1", "api_key_2": "k2"}
    router, sent = _router(monkeypatch, connection, {"k1": ProviderRateLimitError("provider_rate_limited")})

    async def collect() -> list[Any]:
        return [event async for event in router.astream("openai", "gpt-test", [ModelMessage("user", "hi")])]

    assert asyncio.run(collect()) == [{"type": "text", "text": "hi"}]
    assert sent == ["k1", "k2"]


def test_other_failures_never_rotate(monkeypatch: pytest.MonkeyPatch) -> None:
    from raiker.models.exceptions import ProviderAuthenticationError

    connection = {"api_key": "k1", "api_key_2": "k2"}
    router, sent = _router(monkeypatch, connection, {"k1": ProviderAuthenticationError("provider_auth_failed")})
    with pytest.raises(ProviderAuthenticationError):
        asyncio.run(router.achat("openai", "gpt-test", [ModelMessage("user", "hi")]))
    assert sent == ["k1"]


@pytest.fixture
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, dict[str, str], SQLiteStore]:
    monkeypatch.setenv(VAULT_KEY_ENV, Fernet.generate_key().decode())
    ws = tmp_path / "pool"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    raw, _ = ApiSessionStore(ws).create_session(OWNER)
    return TestClient(create_app(ws)), {"Authorization": f"Bearer {raw}"}, SQLiteStore(ws)


def test_backup_keys_are_saved_kept_and_cleared_without_ever_being_shown(
    api: tuple[TestClient, dict[str, str], SQLiteStore],
) -> None:
    client, auth, store = api
    put_model_connection(store, OWNER, PROFILE, {"api_key": "primary"})
    # Backups on their own join the saved connection.
    resp = client.put(f"/api/models/{PROFILE}/connection", json={"backup_api_keys": ["b1", " b2 "]}, headers=auth)
    assert resp.status_code == 200, resp.text
    saved = get_model_connection(store, OWNER, PROFILE) or {}
    assert (saved["api_key"], saved["api_key_2"], saved["api_key_3"]) == ("primary", "b1", "b2")

    view = client.get("/api/models", headers=auth)
    card = next(p for p in view.json()["profiles"] if p["profile_id"] == PROFILE)
    assert card["backup_key_count"] == 2
    assert "b1" not in json.dumps(view.json()) and "primary" not in json.dumps(view.json())

    # Re-pasting the primary keeps them; an empty list clears them.
    client.put(f"/api/models/{PROFILE}/connection", json={"api_key": "primary-2"}, headers=auth)
    saved = get_model_connection(store, OWNER, PROFILE) or {}
    assert (saved["api_key"], saved["api_key_2"]) == ("primary-2", "b1")
    client.put(f"/api/models/{PROFILE}/connection", json={"backup_api_keys": []}, headers=auth)
    saved = get_model_connection(store, OWNER, PROFILE) or {}
    assert saved["api_key"] == "primary-2"
    assert "api_key_2" not in saved and "api_key_3" not in saved


def test_more_than_three_backup_keys_are_refused(api: tuple[TestClient, dict[str, str], SQLiteStore]) -> None:
    client, auth, _store = api
    resp = client.put(
        f"/api/models/{PROFILE}/connection", json={"api_key": "p", "backup_api_keys": ["1", "2", "3", "4"]}, headers=auth
    )
    assert resp.status_code == 422
