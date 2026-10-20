"""Hosted / private-network connectivity checks, bound to the owner's saved connection.

The action names a profile. The destination, the credential and the route the
check takes come from the owner's connection and the provider adapter — never
from the action — so an agent cannot turn a connectivity check into a probe of
an address it chose.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet

from raiker.auth.vault_key_file import VAULT_KEY_ENV
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.models.connections import put_model_connection
from raiker.models.exceptions import ProviderPolicyError
from raiker.models.factory import ModelProviderFactory, ProviderRuntimePolicy
from raiker.models.policy_state import provider_runtime_policy_from_gates
from raiker.models.registry import ModelProfileRegistry
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors import (
    REAL_EXECUTOR_CAPABILITIES,
    build_default_executor_registry,
)
from raiker.runtime.executors.models_runtime import (
    HostedModelRuntimeExecutor,
    PrivateNetworkModelRuntimeExecutor,
)
from raiker.storage.sqlite import SQLiteStore
from tests.factories import governed_action

_HOSTED = "hosted_model_runtime"
_PRIVATE = "private_network_model_runtime"
_DOC = "docs/threat-models/hosted-models.md"
_OWNER = "principal_owner"


@pytest.fixture(autouse=True)
def _vault_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VAULT_KEY_ENV, Fernet.generate_key().decode())


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "hosted"
    ws.mkdir()
    return ws


def _enable(ws: Path, capability: str) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    store = SQLiteStore(ws)
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) VALUES (?, ?, ?, ?)",
            (capability, _OWNER, utc_now(), _DOC),
        )
    result = svc.set_capability_state(capability, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is True, result.reason_code


def _owner(ws: Path) -> Principal:
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    raw = SQLiteStore(ws).get_principal(_OWNER)
    assert raw is not None
    return Principal(**raw)


def _authority(ws: Path) -> tuple[RuntimeAuthority, Principal]:
    store = SQLiteStore(ws)
    authority = RuntimeAuthority(
        store, EventLogWriter(store), executor_registry=build_default_executor_registry(ws, store)
    )
    raw = store.get_principal(_OWNER)
    assert raw is not None
    return authority, Principal(**raw)


def _action(principal_id: str, capability: str, **args: object) -> GovernedAction:
    return governed_action(
        capability,
        principal_id=principal_id,
        arguments=dict(args),
        risk_level=RiskLevelValue.MEDIUM,
    )


class _Recorder:
    """A prober that records where the check would have gone, and sends nothing."""

    def __init__(self) -> None:
        self.endpoints: list[str] = []

    def __call__(self, factory: ModelProviderFactory, profile: Any) -> dict:
        self.endpoints.append(factory.resolve(profile, require_model=False).endpoint)
        return {"model_count": 3}


# ── Registry / governance ────────────────────────────────────────────────────


def test_model_runtime_caps_are_real_executors(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    registry = build_default_executor_registry(ws, SQLiteStore(ws))
    assert _HOSTED in REAL_EXECUTOR_CAPABILITIES
    assert _PRIVATE in REAL_EXECUTOR_CAPABILITIES
    assert registry.has(_HOSTED) and registry.has(_PRIVATE)


def test_fail_closed_when_gate_disabled(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    # Default gates are enabled for integrated capabilities; disable this one to test the fail-closed path.
    RuntimeControlService(ws).disable_capability("hosted_model_runtime", None, "test")
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, _HOSTED, operation="connectivity_check",
                profile_id="openai-hosted"),
        principal,
    )
    assert result.decision == "disabled_by_capability_gate"


def test_enable_requires_threat_model_ack(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    result = svc.set_capability_state(_HOSTED, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is False
    assert "no_threat_model_ack" in (result.reason_code or "")


# ── Executor behaviour ───────────────────────────────────────────────────────


def test_check_without_a_saved_connection_fails_closed(tmp_path: Path) -> None:
    """EGR-04: a hosted profile with no connection is never contacted."""
    ws = _ws(tmp_path)
    recorder = _Recorder()
    executor = HostedModelRuntimeExecutor(ws, SQLiteStore(ws), prober=recorder)
    result = executor.execute(
        _action(_OWNER, _HOSTED, operation="connectivity_check", profile_id="openai-hosted"),
        _owner(ws),
    )
    assert result.ok is False
    assert result.reason_code == "model_connection_required"
    assert recorder.endpoints == []


def test_check_resolves_the_destination_from_the_saved_connection(tmp_path: Path) -> None:
    """EGR-01: a saved hosted connection is checked, with no allowlist anywhere."""
    ws = _ws(tmp_path)
    principal = _owner(ws)
    store = SQLiteStore(ws)
    put_model_connection(store, _OWNER, "openai-hosted", {"api_key": "sk-test"})
    recorder = _Recorder()
    executor = HostedModelRuntimeExecutor(ws, store, prober=recorder)
    result = executor.execute(
        _action(_OWNER, _HOSTED, operation="connectivity_check", profile_id="openai-hosted"),
        principal,
    )
    assert result.ok is True, result.reason_code
    assert recorder.endpoints == ["https://api.openai.com/v1"]
    # Metadata only — no URL, host or credential in the artifacts.
    assert result.artifacts == {
        "profile_id": "openai-hosted",
        "provider": "openai",
        "endpoint_kind": "remote_hosted",
        "model_count": 3,
    }


@pytest.mark.parametrize(
    "argument", ["endpoint", "models_path", "url", "base_url", "path"]
)
def test_an_action_cannot_choose_the_destination(tmp_path: Path, argument: str) -> None:
    """EGR-08 / EGR-09 / EGR-25: destination and probe route are not arguments."""
    ws = _ws(tmp_path)
    principal = _owner(ws)
    store = SQLiteStore(ws)
    put_model_connection(store, _OWNER, "openai-hosted", {"api_key": "sk-test"})
    recorder = _Recorder()
    executor = HostedModelRuntimeExecutor(ws, store, prober=recorder)
    result = executor.execute(
        _action(
            _OWNER,
            _HOSTED,
            operation="connectivity_check",
            profile_id="openai-hosted",
            **{argument: "https://evil.example.com/steal"},
        ),
        principal,
    )
    assert result.ok is False
    assert result.reason_code == f"argument_not_accepted:{argument}"
    assert recorder.endpoints == []


def test_hosted_check_refuses_a_private_connection(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    principal = _owner(ws)
    store = SQLiteStore(ws)
    put_model_connection(
        store, _OWNER, "generic-openai-compatible", {"endpoint": "http://192.168.1.20:8000/v1"}
    )
    executor = HostedModelRuntimeExecutor(ws, store, prober=_Recorder())
    result = executor.execute(
        _action(
            _OWNER, _HOSTED, operation="connectivity_check", profile_id="generic-openai-compatible"
        ),
        principal,
    )
    assert result.ok is False
    assert result.reason_code == "endpoint_kind_not_allowed:private_network"


def test_private_check_accepts_a_saved_home_lab_connection(tmp_path: Path) -> None:
    """EGR-02 / EGR-15: a saved private-network HTTP server is checked."""
    ws = _ws(tmp_path)
    principal = _owner(ws)
    store = SQLiteStore(ws)
    put_model_connection(
        store, _OWNER, "generic-openai-compatible", {"endpoint": "http://192.168.1.20:8000/v1"}
    )
    recorder = _Recorder()
    executor = PrivateNetworkModelRuntimeExecutor(ws, store, prober=recorder)
    result = executor.execute(
        _action(
            _OWNER, _PRIVATE, operation="connectivity_check", profile_id="generic-openai-compatible"
        ),
        principal,
    )
    assert result.ok is True, result.reason_code
    assert recorder.endpoints == ["http://192.168.1.20:8000/v1"]
    assert result.artifacts["endpoint_kind"] == "private_network"
    assert "192.168" not in str(result.artifacts)


def test_another_principals_connection_is_not_reachable(tmp_path: Path) -> None:
    """EGR-07: the lookup is keyed by the acting principal."""
    ws = _ws(tmp_path)
    principal = _owner(ws)
    store = SQLiteStore(ws)
    put_model_connection(store, "principal_someone_else", "openai-hosted", {"api_key": "sk-x"})
    executor = HostedModelRuntimeExecutor(ws, store, prober=_Recorder())
    result = executor.execute(
        _action(_OWNER, _HOSTED, operation="connectivity_check", profile_id="openai-hosted"),
        principal,
    )
    assert result.reason_code == "model_connection_required"


def test_probe_governed_end_to_end(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws, _HOSTED)
    store = SQLiteStore(ws)
    put_model_connection(store, _OWNER, "openai-hosted", {"api_key": "sk-test"})
    registry = build_default_executor_registry(ws, store)
    # Inject a recording prober so CI performs no real network I/O.
    registry.register(_HOSTED, HostedModelRuntimeExecutor(ws, store, prober=_Recorder()))
    authority = RuntimeAuthority(store, EventLogWriter(store), executor_registry=registry)
    raw = store.get_principal(_OWNER)
    assert raw is not None
    principal = Principal(**raw)
    result = authority.route_action(
        _action(principal.principal_id, _HOSTED, operation="connectivity_check",
                profile_id="openai-hosted"),
        principal,
    )
    assert result.decision == "allow" and result.message == "executed"


def test_unknown_operation_fails_closed(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    executor = HostedModelRuntimeExecutor(ws, SQLiteStore(ws), prober=_Recorder())
    action = _action(_OWNER, _HOSTED, operation="chat", profile_id="openai-hosted")
    result = executor.execute(action, _owner(ws))
    assert result.ok is False
    assert result.reason_code == "unknown_operation:chat"


# ── Chat-path policy wiring ──────────────────────────────────────────────────


def test_gate_disabled_yields_fail_closed_provider_policy(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    policy = provider_runtime_policy_from_gates(SQLiteStore(ws))
    assert policy.allow_hosted_provider is False
    assert policy.allow_private_network_provider is False
    assert policy.allow_policy_gated_provider is False


def test_gate_enabled_yields_hosted_provider_policy(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws, _HOSTED)
    policy = provider_runtime_policy_from_gates(SQLiteStore(ws))
    assert policy.allow_hosted_provider is True
    assert policy.allow_private_network_provider is False
    assert policy.allow_policy_gated_provider is True


def test_hosted_provider_requires_a_saved_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-never-real")
    registry = ModelProfileRegistry.load()
    profile = registry.resolve_profile_id("openrouter-policy-gated")
    factory = ModelProviderFactory(
        policy=ProviderRuntimePolicy(allow_hosted_provider=True, allow_policy_gated_provider=True)
    )
    with pytest.raises(ProviderPolicyError, match="model_connection_required"):
        factory.create(profile, require_model=False)


def test_hosted_provider_allowed_with_gate_and_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-never-real")
    registry = ModelProfileRegistry.load()
    profile = registry.resolve_profile_id("openrouter-policy-gated")
    factory = ModelProviderFactory(
        policy=ProviderRuntimePolicy(allow_hosted_provider=True, allow_policy_gated_provider=True),
        connection={"credential_source": "environment"},
    )
    provider = factory.create(profile, require_model=False)
    assert provider.provider == "openrouter"


def test_local_profiles_need_no_connection() -> None:
    registry = ModelProfileRegistry.load()
    profile = registry.resolve_profile_id("raiker-local-llama-cpp")
    provider = ModelProviderFactory().create(profile)
    assert provider.provider == "llama.cpp"
