from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.models.endpoint_policy import MODEL_EGRESS_ALLOWLIST_ENV
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

_HOSTED = "hosted_model_runtime"
_PRIVATE = "private_network_model_runtime"
_DOC = "docs/threat-models/hosted-models.md"


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "hosted"
    ws.mkdir()
    return ws


def _enable(ws: Path, capability: str) -> None:
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    store = SQLiteStore(ws)
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) VALUES (?, ?, ?, ?)",
            (capability, "principal_rahul", utc_now(), _DOC),
        )
    result = svc.set_capability_state(capability, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is True, result.reason_code


def _authority(ws: Path) -> tuple[RuntimeAuthority, Principal]:
    store = SQLiteStore(ws)
    authority = RuntimeAuthority(
        store, EventLogWriter(store), executor_registry=build_default_executor_registry(ws, store)
    )
    raw = store.get_principal("principal_rahul")
    assert raw is not None
    return authority, Principal(**raw)


def _action(principal_id: str, capability: str, **args: object) -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal_id,
        action_type=capability,
        tool_or_service_name=capability,
        arguments=dict(args),
        risk_level=RiskLevelValue.MEDIUM,
    )


def _fake_prober(url: str, allowlist: frozenset[str]) -> dict:
    return {"status": 200, "body_bytes": 42, "truncated": False}


# ── Registry / governance ────────────────────────────────────────────────────


def test_model_runtime_caps_are_real_executors(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    registry = build_default_executor_registry(ws, SQLiteStore(ws))
    assert _HOSTED in REAL_EXECUTOR_CAPABILITIES
    assert _PRIVATE in REAL_EXECUTOR_CAPABILITIES
    assert registry.has(_HOSTED) and registry.has(_PRIVATE)


def test_fail_closed_when_gate_disabled(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    # Default gates are enabled for integrated capabilities; disable this one to test the fail-closed path.
    RuntimeControlService(ws).disable_capability("hosted_model_runtime", None, "test")
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, _HOSTED, operation="connectivity_check",
                endpoint="https://api.example.com"),
        principal,
    )
    assert result.decision == "disabled_by_capability_gate"


def test_enable_requires_threat_model_ack(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    result = svc.set_capability_state(_HOSTED, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is False
    assert "no_threat_model_ack" in (result.reason_code or "")


# ── Executor behaviour ───────────────────────────────────────────────────────


def test_probe_fails_closed_without_allowlist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(MODEL_EGRESS_ALLOWLIST_ENV, raising=False)
    ws = _ws(tmp_path)
    _enable(ws, _HOSTED)
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, _HOSTED, operation="connectivity_check",
                endpoint="https://api.openai.com"),
        principal,
    )
    assert result.error is not None
    assert result.error.startswith("model_egress_denied:no_allowlist")


def test_probe_rejects_non_allowlisted_host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MODEL_EGRESS_ALLOWLIST_ENV, "api.openai.com")
    executor = HostedModelRuntimeExecutor(_ws(tmp_path), prober=_fake_prober)
    action = _action("principal_rahul", _HOSTED, operation="connectivity_check",
                     endpoint="https://evil.example.com")
    result = executor.execute(action, None)  # type: ignore[arg-type]
    assert result.ok is False
    assert result.reason_code == "model_egress_denied:evil.example.com"


def test_hosted_probe_requires_https(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MODEL_EGRESS_ALLOWLIST_ENV, "api.openai.com")
    executor = HostedModelRuntimeExecutor(_ws(tmp_path), prober=_fake_prober)
    action = _action("principal_rahul", _HOSTED, operation="connectivity_check",
                     endpoint="http://api.openai.com")
    result = executor.execute(action, None)  # type: ignore[arg-type]
    assert result.ok is False
    assert result.reason_code == "hosted_https_required"


def test_hosted_probe_rejects_local_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MODEL_EGRESS_ALLOWLIST_ENV, "*")
    executor = HostedModelRuntimeExecutor(_ws(tmp_path), prober=_fake_prober)
    action = _action("principal_rahul", _HOSTED, operation="connectivity_check",
                     endpoint="https://127.0.0.1:8080")
    result = executor.execute(action, None)  # type: ignore[arg-type]
    assert result.ok is False
    assert result.reason_code == "endpoint_kind_not_allowed:local_machine"


def test_private_probe_accepts_allowlisted_private_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(MODEL_EGRESS_ALLOWLIST_ENV, "192.168.1.*")
    executor = PrivateNetworkModelRuntimeExecutor(_ws(tmp_path), prober=_fake_prober)
    action = _action("principal_rahul", _PRIVATE, operation="connectivity_check",
                     endpoint="http://192.168.1.20:8000")
    result = executor.execute(action, None)  # type: ignore[arg-type]
    assert result.ok is True
    # Metadata only — no URL/host/credentials in artifacts.
    assert result.artifacts == {"endpoint_kind": "private_network", "status": 200, "body_bytes": 42}


def test_probe_governed_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MODEL_EGRESS_ALLOWLIST_ENV, "api.openai.com")
    ws = _ws(tmp_path)
    _enable(ws, _HOSTED)
    store = SQLiteStore(ws)
    registry = build_default_executor_registry(ws, store)
    # Inject a fake prober so CI performs no real network I/O.
    registry.register(_HOSTED, HostedModelRuntimeExecutor(ws, prober=_fake_prober))
    authority = RuntimeAuthority(store, EventLogWriter(store), executor_registry=registry)
    raw = store.get_principal("principal_rahul")
    assert raw is not None
    principal = Principal(**raw)
    result = authority.route_action(
        _action(principal.principal_id, _HOSTED, operation="connectivity_check",
                endpoint="https://api.openai.com"),
        principal,
    )
    assert result.decision == "allow" and result.message == "executed"


def test_unknown_operation_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MODEL_EGRESS_ALLOWLIST_ENV, "api.openai.com")
    executor = HostedModelRuntimeExecutor(_ws(tmp_path), prober=_fake_prober)
    action = _action("principal_rahul", _HOSTED, operation="chat", endpoint="https://api.openai.com")
    result = executor.execute(action, None)  # type: ignore[arg-type]
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


def test_hosted_provider_requires_egress_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(MODEL_EGRESS_ALLOWLIST_ENV, raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-never-real")
    registry = ModelProfileRegistry.load()
    profile = registry.resolve_profile_id("openrouter-policy-gated")
    factory = ModelProviderFactory(
        policy=ProviderRuntimePolicy(allow_hosted_provider=True, allow_policy_gated_provider=True)
    )
    with pytest.raises(ProviderPolicyError, match="model_egress_denied:no_allowlist"):
        factory.create(profile, require_model=False)


def test_hosted_provider_allowed_with_gate_and_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(MODEL_EGRESS_ALLOWLIST_ENV, "openrouter.ai")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-never-real")
    registry = ModelProfileRegistry.load()
    profile = registry.resolve_profile_id("openrouter-policy-gated")
    factory = ModelProviderFactory(
        policy=ProviderRuntimePolicy(allow_hosted_provider=True, allow_policy_gated_provider=True)
    )
    provider = factory.create(profile, require_model=False)
    assert provider.provider == "openrouter"


def test_local_profiles_unaffected_by_model_egress_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(MODEL_EGRESS_ALLOWLIST_ENV, raising=False)
    registry = ModelProfileRegistry.load()
    profile = registry.resolve_profile_id("raiker-local-llama-cpp")
    provider = ModelProviderFactory().create(profile)
    assert provider.provider == "llama.cpp"
