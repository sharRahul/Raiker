"""Connection-bound authorization for off-machine model destinations.

``RAIKER_MODEL_EGRESS_ALLOWLIST`` is retired. What decides whether a model
request may leave the machine is, in order:

1. an explicit owner revocation of the hosted / private-network gate — refuses;
2. the runtime gates and capability policy — unchanged;
3. the owner's saved connection for *that* profile — authorizes that
   connection's own origin (scheme, host, effective port) and no other;
4. no connection — an off-machine request is refused.

Each test names the EGR row of the security matrix it covers. They exercise the
runtime path (factory, router, executors, HTTP helpers) rather than looking for
the absence of old strings.
"""

from __future__ import annotations

import asyncio
import http.server
import json
import logging
import threading
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.auth.vault_key_file import VAULT_KEY_ENV
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.models import ModelProfile
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.models import endpoint_policy
from raiker.models.connections import (
    clear_model_connection,
    get_model_connection,
    put_model_connection,
)
from raiker.models.endpoint_policy import (
    authorize_model_destination,
    canonical_origin,
    classify_endpoint,
)
from raiker.models.exceptions import ModelProviderError, ProviderPolicyError
from raiker.models.factory import ModelProviderFactory, ProviderRuntimePolicy
from raiker.models.owner_runtime import owner_model_runtime
from raiker.models.policy_state import provider_runtime_policy_from_gates
from raiker.models.registry import ModelProfileRegistry, profile_with_model
from raiker.models.router import ModelRouter
from raiker.models.transport import ProviderClientPool
from raiker.runtime.executors.sandbox import (
    SandboxError,
    connector_egress_allowlist,
    get_url,
    post_json,
)
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"
OPEN = ProviderRuntimePolicy(
    allow_policy_gated_provider=True,
    allow_hosted_provider=True,
    allow_private_network_provider=True,
)


@pytest.fixture(autouse=True)
def _vault_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VAULT_KEY_ENV, Fernet.generate_key().decode())
    monkeypatch.delenv("RAIKER_MODEL_EGRESS_ALLOWLIST", raising=False)


def _profile(profile_id: str, model: str = "m") -> ModelProfile:
    return profile_with_model(ModelProfileRegistry.load().resolve_profile_id(profile_id), model)


def _with_raw(profile: ModelProfile, **raw: Any) -> ModelProfile:
    return replace(profile, raw={**profile.raw, **raw})


def _workspace(tmp_path: Path) -> tuple[Path, SQLiteStore]:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws, SQLiteStore(ws)


def _store_router(store: SQLiteStore, principal_id: str = OWNER) -> ModelRouter:
    """A router the way the product builds one: gates and connections read per call."""
    return ModelRouter(
        ModelProfileRegistry.load(),
        runtime_policy=provider_runtime_policy_from_gates(store, principal_id),
        runtime_policy_resolver=lambda: provider_runtime_policy_from_gates(store, principal_id),
        connection_resolver=lambda pid: get_model_connection(store, principal_id, pid),
    )


# ── Canonical origin ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("https://models.example.com", "https://models.example.com:443"),
        ("https://Models.Example.COM/v1", "https://models.example.com/other/path"),
        ("https://models.example.com./v1", "https://models.example.com:443/"),
        ("http://192.168.1.20/v1", "http://192.168.1.20:80"),
        ("http://[::1]:8080/v1", "http://[0:0:0:0:0:0:0:1]:8080"),
        ("http://[FE80::1]:8000", "http://[fe80::1]:8000"),
    ],
)
def test_equal_origins_normalise_to_the_same_value(left: str, right: str) -> None:
    assert canonical_origin(left) == canonical_origin(right)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("https://models.example.com", "https://models.example.com:8443"),
        ("https://models.example.com", "http://models.example.com"),
        ("https://models.example.com", "https://models.example.com.evil.test"),
        ("http://192.168.1.20:8000", "http://192.168.1.21:8000"),
    ],
)
def test_distinct_origins_stay_distinct(left: str, right: str) -> None:
    assert canonical_origin(left) != canonical_origin(right)


@pytest.mark.parametrize(
    ("endpoint", "code"),
    [
        ("https://user:pass@models.example.com/v1", "endpoint_userinfo_rejected"),
        ("https://models.example.com@evil.test/v1", "endpoint_userinfo_rejected"),
        ("ftp://models.example.com", "endpoint_invalid"),
        ("models.example.com/v1", "endpoint_invalid"),
        ("https://models.example.com:99999", "endpoint_invalid"),
        ("https://models.example.com\\@evil.test", "endpoint_invalid"),
        ("https://models.exa mple.com", "endpoint_invalid"),
        ("http://127.1:8080", "endpoint_ambiguous_host"),
        ("http://2130706433:8080", "endpoint_ambiguous_host"),
        ("http://0x7f.0.0.1:8080", "endpoint_ambiguous_host"),
        ("http://010.0.0.1:8080", "endpoint_ambiguous_host"),
    ],
)
def test_unsafe_or_ambiguous_endpoints_are_refused(endpoint: str, code: str) -> None:
    with pytest.raises(ProviderPolicyError, match=code):
        canonical_origin(endpoint)


# ── EGR-01 … EGR-05: what a connection does and does not authorize ───────────


def test_egr01_saved_hosted_connection_without_legacy_allowlist_is_allowed() -> None:
    resolved = ModelProviderFactory(policy=OPEN, connection={"api_key": "sk-test"}).resolve(
        _profile("openai-hosted", "gpt-4o")
    )
    assert resolved.endpoint == "https://api.openai.com/v1"
    assert resolved.endpoint_kind == "remote_hosted"
    assert resolved.headers["Authorization"] == "Bearer sk-test"


def test_egr02_saved_private_network_connection_is_allowed() -> None:
    """A custom endpoint's address decides its gate (FIXED-935), not a profile flag."""
    resolved = ModelProviderFactory(
        policy=OPEN, connection={"endpoint": "http://192.168.1.20:8000/v1"}
    ).resolve(_profile("generic-openai-compatible", "llama3"))
    assert resolved.endpoint_kind == "private_network"


def test_a_custom_endpoint_may_be_an_owner_named_hosted_service() -> None:
    resolved = ModelProviderFactory(
        policy=OPEN,
        connection={"endpoint": "https://models.example.com/v1", "api_key": "sk-test"},
    ).resolve(_profile("generic-openai-compatible", "llama3"))
    assert resolved.endpoint_kind == "remote_hosted"


def test_egr03_local_model_needs_no_connection() -> None:
    resolved = ModelProviderFactory().resolve(_profile("raiker-local-llama-cpp"))
    assert resolved.endpoint_kind == "local_machine"


def test_a_local_only_profile_is_never_pointed_off_the_machine() -> None:
    with pytest.raises(ProviderPolicyError, match="local_only_rejects_private_network"):
        ModelProviderFactory(
            policy=OPEN, connection={"endpoint": "http://192.168.1.20:8080"}
        ).resolve(_profile("raiker-local-llama-cpp"))


def test_egr04_hosted_provider_without_a_connection_is_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    with pytest.raises(ProviderPolicyError, match="model_connection_required"):
        ModelProviderFactory(policy=OPEN).resolve(_profile("openai-hosted", "gpt-4o"))


def test_egr05_private_endpoint_from_the_environment_alone_is_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An environment variable on its own never authorizes off-machine inference."""
    monkeypatch.setenv("RAIKER_TEST_MODEL_ENDPOINT", "http://192.168.1.20:8000/v1")
    profile = _with_raw(
        _profile("generic-openai-compatible", "llama3"),
        endpoint="",
        endpoint_env="RAIKER_TEST_MODEL_ENDPOINT",
    )
    with pytest.raises(ProviderPolicyError, match="model_connection_required"):
        ModelProviderFactory(policy=OPEN).resolve(profile)


# ── EGR-06 / EGR-07: revocation and principals ───────────────────────────────


def test_egr06_explicit_revocation_wins_over_a_saved_connection(tmp_path: Path) -> None:
    ws, store = _workspace(tmp_path)
    put_model_connection(store, OWNER, "openai-hosted", {"api_key": "sk-test"})
    router = _store_router(store)
    profile = _profile("openai-hosted", "gpt-4o")
    router._factory(profile).resolve(profile)  # noqa: SLF001 — allowed before revocation

    RuntimeControlService(ws).disable_capability("hosted_model_runtime", None, "test")

    assert provider_runtime_policy_from_gates(store, OWNER).allow_hosted_provider is False
    with pytest.raises(ProviderPolicyError, match="explicit_policy"):
        router._factory(profile).resolve(profile)  # noqa: SLF001


def test_egr07_another_principals_connection_is_never_used(tmp_path: Path) -> None:
    _ws, store = _workspace(tmp_path)
    put_model_connection(store, "principal_other", "openai-hosted", {"api_key": "sk-theirs"})
    router = _store_router(store, OWNER)
    profile = _profile("openai-hosted", "gpt-4o")
    with pytest.raises(ProviderPolicyError, match="model_connection_required"):
        router._factory(profile).resolve(profile)  # noqa: SLF001


def test_a_connection_saved_for_one_profile_does_not_authorize_another(tmp_path: Path) -> None:
    """EGR-20's root: the router resolves each profile's own connection, or none."""
    _ws, store = _workspace(tmp_path)
    put_model_connection(store, OWNER, "anthropic-hosted", {"api_key": "sk-ant"})
    router = _store_router(store)
    profile = _profile("openai-hosted", "gpt-4o")
    with pytest.raises(ProviderPolicyError, match="model_connection_required"):
        router._factory(profile).resolve(profile)  # noqa: SLF001


# ── EGR-10 / EGR-11 / EGR-14: origin binding ─────────────────────────────────


def test_egr10_an_environment_override_cannot_move_a_saved_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAIKER_TEST_MODEL_ENDPOINT", "https://elsewhere.example.net/v1")
    profile = _with_raw(
        _profile("openai-hosted", "gpt-4o"), endpoint_env="RAIKER_TEST_MODEL_ENDPOINT"
    )
    with pytest.raises(ProviderPolicyError, match="model_connection_origin_mismatch"):
        ModelProviderFactory(policy=OPEN, connection={"api_key": "sk-test"}).resolve(profile)


def test_egr10_a_saved_endpoint_wins_over_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAIKER_TEST_MODEL_ENDPOINT", "https://elsewhere.example.net/v1")
    profile = _with_raw(
        _profile("generic-openai-compatible", "llama3"), endpoint_env="RAIKER_TEST_MODEL_ENDPOINT"
    )
    resolved = ModelProviderFactory(
        policy=OPEN, connection={"endpoint": "http://192.168.1.20:8000/v1"}
    ).resolve(profile)
    assert resolved.endpoint == "http://192.168.1.20:8000/v1"


def test_origin_binding_is_scheme_host_and_port() -> None:
    authorize_model_destination(
        "https://api.openai.com:443/v1/models",
        kind="remote_hosted",
        connection={"api_key": "k"},
        default_endpoint="https://api.openai.com/v1",
    )
    for moved in ("https://api.openai.com:8443/v1", "http://api.openai.com/v1"):
        with pytest.raises(ProviderPolicyError, match="model_connection_origin_mismatch"):
            authorize_model_destination(
                moved,
                kind="remote_hosted",
                connection={"api_key": "k"},
                default_endpoint="https://api.openai.com/v1",
            )


def test_egr14_hosted_http_endpoint_is_refused_without_transport_permission() -> None:
    with pytest.raises(ProviderPolicyError, match="hosted_http_endpoint_rejected"):
        ModelProviderFactory(
            policy=OPEN,
            connection={"endpoint": "http://models.example.com/v1", "api_key": "sk-test"},
        ).resolve(_profile("generic-openai-compatible", "llama3"))


@pytest.fixture
def api(tmp_path: Path) -> Iterator[tuple[TestClient, dict[str, str], SQLiteStore]]:
    ws, store = _workspace(tmp_path)
    raw, _ = ApiSessionStore(ws).create_session(OWNER)
    yield TestClient(create_app(ws)), {"Authorization": f"Bearer {raw}"}, store


def test_egr11_the_owner_changing_the_endpoint_moves_the_authorization(
    api: tuple[TestClient, dict[str, str], SQLiteStore],
) -> None:
    client, auth, store = api
    profile = _profile("generic-openai-compatible", "llama3")
    first = client.put(
        "/api/models/generic-openai-compatible/connection",
        json={"endpoint": "http://192.168.1.20:8000/v1"},
        headers=auth,
    )
    assert first.status_code == 200, first.text
    second = client.put(
        "/api/models/generic-openai-compatible/connection",
        json={"endpoint": "https://models.example.com/v1", "api_key": "sk-test"},
        headers=auth,
    )
    assert second.status_code == 200, second.text
    resolved = _store_router(store)._factory(profile).resolve(profile)  # noqa: SLF001
    assert canonical_origin(resolved.endpoint) == "https://models.example.com:443"


def test_an_environment_key_is_imported_only_by_an_explicit_owner_save(
    api: tuple[TestClient, dict[str, str], SQLiteStore], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The migration path for an installation that kept its key in the environment."""
    client, auth, store = api
    refused = client.put(
        "/api/models/openai-hosted/connection",
        json={"use_environment_credential": True},
        headers=auth,
    )
    assert refused.status_code == 400
    assert refused.json()["detail"]["reason_code"] == "environment_credential_unavailable"

    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env-never-stored")
    card = next(
        p for p in client.get("/api/models", headers=auth).json()["profiles"]
        if p["profile_id"] == "openai-hosted"
    )
    assert card["environment_credential_env"] == "OPENAI_API_KEY"
    assert "sk-from-env" not in json.dumps(card)

    saved = client.put(
        "/api/models/openai-hosted/connection",
        json={"use_environment_credential": True},
        headers=auth,
    )
    assert saved.status_code == 200, saved.text
    stored = get_model_connection(store, OWNER, "openai-hosted") or {}
    assert stored == {"credential_source": "environment"}
    profile = _profile("openai-hosted", "gpt-4o")
    resolved = _store_router(store)._factory(profile).resolve(profile)  # noqa: SLF001
    assert resolved.headers["Authorization"] == "Bearer sk-from-env-never-stored"


def test_a_pasted_key_and_the_environment_key_are_not_both_accepted(
    api: tuple[TestClient, dict[str, str], SQLiteStore], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, auth, _store = api
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    response = client.put(
        "/api/models/openai-hosted/connection",
        json={"use_environment_credential": True, "api_key": "sk-pasted"},
        headers=auth,
    )
    assert response.status_code == 400
    assert response.json()["detail"]["reason_code"] == "environment_credential_with_pasted_key"


# ── EGR-12 / EGR-13: redirects ───────────────────────────────────────────────


class _Server:
    """A loopback HTTP server recording what reached it."""

    def __init__(self, status: int, location: str = "", body: bytes = b"{}") -> None:
        self.requests: list[dict[str, str]] = []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def _answer(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                if length:
                    self.rfile.read(length)
                outer.requests.append({k.lower(): v for k, v in self.headers.items()})
                self.send_response(status)
                if location:
                    self.send_header("Location", location)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = _answer  # noqa: N815
            do_POST = _answer  # noqa: N815

            def log_message(self, *args: object) -> None:
                return None

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def servers() -> Iterator[tuple[_Server, _Server]]:
    target = _Server(200, body=b'{"data": []}')
    redirector = _Server(302, location=f"{target.url}/stolen")
    yield redirector, target
    redirector.close()
    target.close()


def test_egr12_egr13_urllib_model_helper_refuses_a_redirect(
    servers: tuple[_Server, _Server],
) -> None:
    redirector, target = servers
    host = redirector.url.split("//", 1)[1]
    with pytest.raises(SandboxError, match="redirect_refused:302"):
        post_json(
            f"{redirector.url}/v1/images/generations",
            {"prompt": "a cat"},
            egress_allowlist=frozenset({host}),
            headers={"Authorization": "Bearer sk-secret"},
        )
    assert len(redirector.requests) == 1
    assert target.requests == [], "the credential must not follow the redirect"


def test_egr12_egr13_provider_http_client_does_not_follow_a_redirect(
    servers: tuple[_Server, _Server],
) -> None:
    redirector, target = servers
    profile = _with_raw(_profile("raiker-local-llama-cpp"), endpoint=redirector.url)
    connection = {"endpoint": redirector.url}
    pool = ProviderClientPool()

    async def body() -> None:
        provider = ModelProviderFactory(connection=connection, client_pool=pool).create(
            profile, require_model=False
        )
        try:
            with pytest.raises(ModelProviderError):
                await provider.list_models()
        finally:
            await provider.aclose()
            await pool.aclose()

    asyncio.run(body())
    assert len(redirector.requests) == 1
    assert target.requests == []


# ── EGR-16 / EGR-22: embeddings and credential rotation ──────────────────────


def test_egr16_egr22_authorized_embedding_uses_the_current_saved_key(tmp_path: Path) -> None:
    _ws, store = _workspace(tmp_path)
    put_model_connection(store, OWNER, "openai-hosted", {"api_key": "sk-first"})
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((str(request.url), request.headers.get("authorization", "")))
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2]}], "model": "e"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    registry = ModelProfileRegistry.load()
    router = _store_router(store)
    profile = _with_raw(_profile("openai-hosted", "text-embedding-3-small"), supports_embeddings=True)
    registry.register(profile)

    async def embed() -> None:
        factory = router._factory(profile)  # noqa: SLF001
        provider = ModelProviderFactory(
            client=client, policy=router.runtime_policy, connection=factory.connection
        ).create(profile)
        try:
            from raiker.models.contracts import EmbeddingRequest

            await provider.embed(EmbeddingRequest(profile.profile_id, "openai", profile.model, "hi"))
        finally:
            await provider.aclose()

    asyncio.run(embed())
    put_model_connection(store, OWNER, "openai-hosted", {"api_key": "sk-rotated"})
    asyncio.run(embed())
    asyncio.run(client.aclose())
    assert [auth for _url, auth in seen] == ["Bearer sk-first", "Bearer sk-rotated"]
    assert all(url.startswith("https://api.openai.com/") for url, _auth in seen)


# ── EGR-20 / EGR-21: fallback and deletion mid-session ───────────────────────


def test_egr20_an_unauthorized_fallback_model_is_denied(tmp_path: Path) -> None:
    _ws, store = _workspace(tmp_path)
    put_model_connection(store, OWNER, "anthropic-hosted", {"api_key": "sk-ant"})
    router = _store_router(store)
    registry = router.registry
    registry.register(_profile("openai-hosted", "gpt-4o"))

    async def fallback() -> None:
        from raiker.models.contracts import ModelMessage

        await router.achat("openai", "gpt-4o", [ModelMessage("user", "hi")])

    with pytest.raises(ProviderPolicyError, match="model_connection_required"):
        asyncio.run(fallback())


def test_egr21_a_connection_deleted_mid_session_denies_the_next_request(
    tmp_path: Path,
) -> None:
    _ws, store = _workspace(tmp_path)
    put_model_connection(store, OWNER, "openai-hosted", {"api_key": "sk-test"})
    router, _selected = owner_model_runtime(store, OWNER, EventLogWriter(store))
    profile = _profile("openai-hosted", "gpt-4o")
    router._factory(profile).resolve(profile)  # noqa: SLF001
    clear_model_connection(store, OWNER, "openai-hosted")
    with pytest.raises(ProviderPolicyError, match="model_connection_required"):
        router._factory(profile).resolve(profile)  # noqa: SLF001


def test_a_gate_revoked_mid_turn_stops_the_next_call(tmp_path: Path) -> None:
    """The gateway's router lives for a turn; the gates are read per call."""
    ws, store = _workspace(tmp_path)
    put_model_connection(store, OWNER, "openai-hosted", {"api_key": "sk-test"})
    router, _selected = owner_model_runtime(store, OWNER, EventLogWriter(store))
    profile = _profile("openai-hosted", "gpt-4o")
    router._factory(profile).resolve(profile)  # noqa: SLF001
    RuntimeControlService(ws).disable_capability("hosted_model_runtime", None, "test")
    with pytest.raises(ProviderPolicyError):
        router._factory(profile).resolve(profile)  # noqa: SLF001


# ── EGR-23: the retired allowlist is ignored ─────────────────────────────────


def test_egr23_the_old_allowlist_neither_opens_nor_closes_anything(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "*,evil.example.com")
    monkeypatch.setattr(endpoint_policy, "_legacy_notice_given", False)
    profile = _profile("openai-hosted", "gpt-4o")
    with caplog.at_level(logging.WARNING, logger="raiker.models.endpoint_policy"):
        # It does not open an unconnected provider…
        with pytest.raises(ProviderPolicyError, match="model_connection_required"):
            ModelProviderFactory(policy=OPEN).resolve(profile)
        # …and a host missing from it does not close a connected one.
        monkeypatch.setenv("RAIKER_MODEL_EGRESS_ALLOWLIST", "unrelated.example.org")
        ModelProviderFactory(policy=OPEN, connection={"api_key": "sk"}).resolve(profile)
        ModelProviderFactory(policy=OPEN, connection={"api_key": "sk"}).resolve(profile)
    notices = [r for r in caplog.records if "RAIKER_MODEL_EGRESS_ALLOWLIST" in r.getMessage()]
    assert len(notices) == 1, "named once per process, not on every request"
    assert "evil.example.com" not in notices[0].getMessage()
    assert "unrelated.example.org" not in notices[0].getMessage()


# ── EGR-24 / EGR-26: proxies and unrelated egress ────────────────────────────


def test_egr24_pooled_clients_follow_owner_proxies_except_for_loopback() -> None:
    pool = ProviderClientPool()

    async def body() -> None:
        hosted = pool.client(endpoint="https://api.openai.com/v1", timeout=30.0)
        local = pool.client(endpoint="http://127.0.0.1:11434/v1", timeout=30.0)
        assert hosted.trust_env is True
        assert local.trust_env is False
        for client in (hosted, local):
            assert client.follow_redirects is False
            assert "authorization" not in {name.lower() for name in client.headers}
        await pool.aclose()

    asyncio.run(body())


def test_egr26_unrelated_egress_allowlists_are_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", raising=False)
    assert connector_egress_allowlist() == frozenset()
    monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "api.github.com")
    assert connector_egress_allowlist() == frozenset({"api.github.com"})
    # The general GET helper still fails closed without an allowlist.
    with pytest.raises(SandboxError, match="egress_denied:no_allowlist"):
        get_url("https://api.github.com/", egress_allowlist=frozenset())


# ── EGR-27 / EGR-28: restart, readiness, catalogue and auxiliary calls ───────


def test_egr27_connections_and_revocations_survive_a_restart(tmp_path: Path) -> None:
    ws, store = _workspace(tmp_path)
    put_model_connection(store, OWNER, "openai-hosted", {"api_key": "sk-test"})
    RuntimeControlService(ws).disable_capability("private_network_model_runtime", None, "test")
    reopened = SQLiteStore(ws)
    policy = provider_runtime_policy_from_gates(reopened, OWNER)
    assert policy.allow_hosted_provider is True
    assert policy.allow_private_network_provider is False
    profile = _profile("openai-hosted", "gpt-4o")
    _store_router(reopened)._factory(profile).resolve(profile)  # noqa: SLF001


def test_egr28_catalogue_discovery_follows_the_same_rule(tmp_path: Path) -> None:
    _ws, store = _workspace(tmp_path)
    router = _store_router(store)
    with pytest.raises(ProviderPolicyError, match="model_connection_required"):
        asyncio.run(router.alist_models_for_profile(_profile("openai-hosted", "gpt-4o")))


def test_egr28_the_advisor_uses_the_owners_connection_or_nothing(tmp_path: Path) -> None:
    from raiker.runtime.advisor import AdvisorService

    ws, store = _workspace(tmp_path)
    consult = AdvisorService(ws, store, principal_id=OWNER)._default_consult_fn()  # noqa: SLF001
    with pytest.raises(ProviderPolicyError, match="model_connection_required"):
        consult("openai", "gpt-4o", "Is this plan sound?")


def test_classification_is_unchanged_for_local_private_and_hosted() -> None:
    assert classify_endpoint("http://127.0.0.1:11434/v1") == "local_machine"
    assert classify_endpoint("http://192.168.1.20:8000/v1") == "private_network"
    assert classify_endpoint("http://gpu-box:8000/v1") == "private_network"
    assert classify_endpoint("https://api.openai.com/v1") == "remote_hosted"
