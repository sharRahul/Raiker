"""Acceptance tests for the provider-backed ``model_provider_runtime`` executor.

This executor calls a real LLM provider's embedding endpoint and persists the
returned semantic vector. Tests use an **injected embedder** so the governed
persistence path is exercised without a live provider or credentials, and pin
the layered fail-closed gating (egress allowlist, gate, arg validation). No test
performs real network I/O.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.control.service import RuntimeControlService
from raiker.events.query import EventViewer
from raiker.events.writer import EventLogWriter
from raiker.models.contracts import EmbeddingResponse
from raiker.models.exceptions import ProviderUnsupportedCapabilityError
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors import (
    REAL_EXECUTOR_CAPABILITIES,
    ModelProviderExecutor,
    build_default_executor_registry,
)
from raiker.storage.sqlite import SQLiteStore

_CAP = "model_provider_runtime"
_TOOL = "model_provider"
_DOC = "docs/threat-models/model-provider.md"
_ALLOWLIST_ENV = "RAIKER_MODEL_EGRESS_ALLOWLIST"


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "model_provider"
    ws.mkdir()
    return ws


def _enable(ws: Path) -> None:
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    store = SQLiteStore(ws)
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref) VALUES (?, ?, ?, ?)",
            (_CAP, "principal_rahul", utc_now(), _DOC),
        )
    result = svc.set_capability_state(_CAP, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is True, result.reason_code


def _fake_embedder(vector: list[float]):
    def embed(provider: str, model: str, text: str) -> EmbeddingResponse:
        return EmbeddingResponse(vector=vector, model=model, usage={"tokens": len(text)})

    return embed


def _authority(ws: Path, *, embedder=None) -> tuple[RuntimeAuthority, Principal]:
    store = SQLiteStore(ws)
    registry = build_default_executor_registry(ws, store)
    if embedder is not None:
        registry.register(_CAP, ModelProviderExecutor(ws, store, embedder=embedder))
    authority = RuntimeAuthority(store, EventLogWriter(store), executor_registry=registry)
    raw = store.get_principal("principal_rahul")
    assert raw is not None
    return authority, Principal(**raw)


def _action(principal_id: str, **args: object) -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal_id,
        action_type=_TOOL,
        tool_or_service_name=_TOOL,
        arguments=dict(args),
        risk_level=RiskLevelValue.MEDIUM,
        session_id="sess_model_provider",
    )


# ── Registry membership ──────────────────────────────────────────────────────


def test_model_provider_is_real_executor(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    registry = build_default_executor_registry(ws, SQLiteStore(ws))
    assert _CAP in REAL_EXECUTOR_CAPABILITIES
    assert registry.has(_CAP)


# ── Fails closed when the gate is disabled ───────────────────────────────────


def test_gate_disabled_blocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_ALLOWLIST_ENV, "api.openai.com")
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    authority, principal = _authority(ws, embedder=_fake_embedder([0.1, 0.2, 0.3]))
    result = authority.route_action(_action(principal.principal_id, text="hello", provider="openai", model="m"), principal)
    assert result.decision == "disabled_by_capability_gate"
    assert SQLiteStore(ws).list_vector_records() == []


def test_enable_requires_threat_model_ack(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("rahul", "Rahul", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    result = svc.set_capability_state(_CAP, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is False
    assert "no_threat_model_ack" in (result.reason_code or "")


# ── Egress allowlist gates the provider call ─────────────────────────────────


def test_empty_egress_allowlist_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_ALLOWLIST_ENV, raising=False)
    ws = _ws(tmp_path)
    _enable(ws)
    # No injected embedder: proves the egress guard trips before any provider call.
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, text="hello", provider="openai", model="m"), principal
    )
    assert result.error == "model_egress_denied:no_allowlist"
    assert SQLiteStore(ws).list_vector_records() == []


# ── Arg validation fails closed ──────────────────────────────────────────────


def test_missing_text_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_ALLOWLIST_ENV, "api.openai.com")
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(_action(principal.principal_id, provider="openai", model="m"), principal)
    assert result.error == "missing_argument:text"


def test_unknown_operation_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_ALLOWLIST_ENV, "api.openai.com")
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, operation="generate", text="x", provider="openai", model="m"),
        principal,
    )
    assert result.error == "unknown_operation:generate"


# ── Provider errors fail closed ──────────────────────────────────────────────


def test_provider_error_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_ALLOWLIST_ENV, "api.openai.com")
    ws = _ws(tmp_path)
    _enable(ws)

    def _raises(provider: str, model: str, text: str) -> EmbeddingResponse:
        raise ProviderUnsupportedCapabilityError("embeddings_unsupported")

    authority, principal = _authority(ws, embedder=_raises)
    result = authority.route_action(
        _action(principal.principal_id, text="hello", provider="anthropic", model="claude"), principal
    )
    assert result.error == "model_provider_denied:embeddings_unsupported"
    assert SQLiteStore(ws).list_vector_records() == []


# ── Executes when governed ───────────────────────────────────────────────────


def test_embed_persists_provider_vector_without_leaking_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_ALLOWLIST_ENV, "api.openai.com")
    ws = _ws(tmp_path)
    _enable(ws)
    vector = [0.11, 0.22, 0.33, 0.44]
    authority, principal = _authority(ws, embedder=_fake_embedder(vector))
    result = authority.route_action(
        _action(
            principal.principal_id,
            text="my SECRETPHRASE about quarterly revenue",
            provider="openai",
            model="text-embedding-3-small",
        ),
        principal,
    )
    assert result.decision == "allow"
    assert result.message == "executed"

    store = SQLiteStore(ws)
    rows = store.list_vector_records()
    assert len(rows) == 1
    assert rows[0]["embedding_model"] == "openai:text-embedding-3-small"
    assert rows[0]["dimensions"] == 4
    assert json.loads(rows[0]["embedding"]) == vector

    # Source text must never leak into runtime event artifacts.
    viewer = EventViewer(store)
    events = viewer.list_events(event_type="action_executed")
    payload = viewer.read_event_payload(events[0]["event_id"])
    assert payload is not None
    dumped = json.dumps(payload)
    assert "SECRETPHRASE" not in dumped
    artifacts = payload["payload"]["artifacts"]
    assert artifacts["provider_backed"] is True
    assert artifacts["content_redacted"] is True
    assert artifacts["embedding_model"] == "openai:text-embedding-3-small"
