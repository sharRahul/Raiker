"""Acceptance tests for the local ``vector_embedding_runtime`` executor.

The executor computes a deterministic, offline embedding (the hashing trick) and
persists a ``vector_records`` row. These tests pin the slice contract:
executes-when-governed (embed + list + search, real persistence, deterministic,
no text leakage) AND fails-closed-when-disabled / on bad input.
"""

from __future__ import annotations

import json
from pathlib import Path

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import VectorRecord
from raiker.control.service import RuntimeControlService
from raiker.events.query import EventViewer
from raiker.events.writer import EventLogWriter
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES, build_default_executor_registry
from raiker.storage.sqlite import SQLiteStore
from raiker.vector import LOCAL_EMBEDDING_MODEL, embed_text

_CAP = "vector_embedding_runtime"
# The action/tool name the router maps to the capability gate (see
# CAPABILITY_GATE_MAP) and that the static policy recognizes.
_TOOL = "vector_embedding"


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "vectors"
    ws.mkdir()
    return ws


def _enable(ws: Path) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    result = svc.set_capability_state(_CAP, "enabled_runtime", None, "test", confirmation_token="confirm")
    assert result.ok is True, result.reason_code


def _authority(ws: Path) -> tuple[RuntimeAuthority, Principal]:
    store = SQLiteStore(ws)
    authority = RuntimeAuthority(
        store, EventLogWriter(store), executor_registry=build_default_executor_registry(ws, store)
    )
    raw = store.get_principal("principal_owner")
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
        session_id="sess_vectors",
    )


# ── Embedding function is deterministic and offline ──────────────────────────


def test_embed_text_is_deterministic_and_normalized() -> None:
    a = embed_text("the quick brown fox", 384)
    b = embed_text("the quick brown fox", 384)
    assert a == b
    assert len(a) == 384
    norm = sum(v * v for v in a) ** 0.5
    assert abs(norm - 1.0) < 1e-9
    # Different text yields a different vector.
    assert embed_text("a completely different sentence", 384) != a
    # Empty text yields the zero vector (norm 0, no tokens).
    assert embed_text("", 384) == [0.0] * 384


# ── Registry membership ──────────────────────────────────────────────────────


def test_vector_embedding_is_real_executor(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    registry = build_default_executor_registry(ws, SQLiteStore(ws))
    assert _CAP in REAL_EXECUTOR_CAPABILITIES
    assert registry.has(_CAP)
    # The provider-backed sibling is a separate real executor (egress-gated).
    assert "model_provider_runtime" in REAL_EXECUTOR_CAPABILITIES


# ── Fails closed when the gate is disabled ───────────────────────────────────


def test_gate_disabled_blocks(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    # Default gates are enabled for integrated capabilities; disable this one to test the fail-closed path.
    RuntimeControlService(ws).disable_capability("vector_embedding_runtime", None, "test")
    authority, principal = _authority(ws)
    result = authority.route_action(_action(principal.principal_id, text="hello world"), principal)
    assert result.decision == "disabled_by_capability_gate"
    assert SQLiteStore(ws).list_vector_records() == []


# ── Executes when governed ───────────────────────────────────────────────────


def test_embed_persists_record_without_leaking_text(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, text="my SECRETPHRASE about quarterly revenue"),
        principal,
    )
    assert result.decision == "allow"
    assert result.message == "executed"

    store = SQLiteStore(ws)
    rows = store.list_vector_records()
    assert len(rows) == 1
    assert rows[0]["embedding_model"] == LOCAL_EMBEDDING_MODEL
    assert rows[0]["dimensions"] == 384
    # The persisted embedding is a real 384-d vector.
    stored_vector = json.loads(rows[0]["embedding"])
    assert len(stored_vector) == 384

    # Source text must never leak into runtime event artifacts.
    viewer = EventViewer(store)
    events = viewer.list_events(event_type="action_executed")
    payload = viewer.read_event_payload(events[0]["event_id"])
    assert payload is not None
    dumped = json.dumps(payload)
    assert "SECRETPHRASE" not in dumped
    assert payload["payload"]["artifacts"]["content_redacted"] is True
    assert payload["payload"]["artifacts"]["dimensions"] == 384


def test_governed_projection_links_only_active_durable_memory(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    store = SQLiteStore(ws)
    memory = write_memory(
        "Approved durable retrieval fact.", workspace_root=ws, store=store,
        governance=MemoryGovernance("evt", "sess", None, "test", 1, 1, "until_forget", "approved", "test"),
    )
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, action="project_memory", memory_id=memory.memory_id), principal
    )
    assert result.decision == "allow"
    assert len(store.list_active_memory_vector_embeddings(LOCAL_EMBEDDING_MODEL)) == 1
    assert store.list_memory_projections(memory.memory_id)[0]["projection_type"] == "vector"


def test_missing_text_fails_closed(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(_action(principal.principal_id, scope="docs"), principal)
    assert result.error == "missing_argument:text"
    assert SQLiteStore(ws).list_vector_records() == []


def test_unknown_action_fails_closed(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, action="delete", text="x"), principal
    )
    assert result.error == "unknown_action:delete"


def test_list_returns_count_only(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    authority.route_action(_action(principal.principal_id, text="first document"), principal)
    authority.route_action(_action(principal.principal_id, text="second document"), principal)
    result = authority.route_action(_action(principal.principal_id, action="list"), principal)
    assert result.decision == "allow"

    viewer = EventViewer(SQLiteStore(ws))
    list_artifacts = None
    for ev in viewer.list_events(event_type="action_executed"):
        payload = viewer.read_event_payload(ev["event_id"])
        artifacts = (payload or {}).get("payload", {}).get("artifacts", {})
        if "count" in artifacts:
            list_artifacts = artifacts
    assert list_artifacts is not None
    assert list_artifacts["count"] == 2
    assert list_artifacts["content_redacted"] is True


# ── Retrieval (search) closes the embed -> store -> retrieve loop ─────────────


def _embed_doc(authority: RuntimeAuthority, principal: Principal, ws: Path, text: str) -> str:
    authority.route_action(_action(principal.principal_id, text=text), principal)
    # list_vector_records is newest-first, so [0] is the row just written.
    return str(SQLiteStore(ws).list_vector_records()[0]["vector_id"])


def _search_artifacts(authority: RuntimeAuthority, principal: Principal, ws: Path, **args: object) -> dict:
    result = authority.route_action(_action(principal.principal_id, action="search", **args), principal)
    assert result.decision == "allow", getattr(result, "error", result.decision)
    viewer = EventViewer(SQLiteStore(ws))
    found = None
    for ev in viewer.list_events(event_type="action_executed"):
        payload = viewer.read_event_payload(ev["event_id"])
        artifacts = (payload or {}).get("payload", {}).get("artifacts", {})
        if "results" in artifacts:
            found = artifacts
    assert found is not None
    return found


def test_search_ranks_exact_match_first_without_leaking_query(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    id1 = _embed_doc(authority, principal, ws, "alpha beta QUERYLEAKZ")
    _embed_doc(authority, principal, ws, "delta epsilon zeta")
    _embed_doc(authority, principal, ws, "eta theta iota")

    art = _search_artifacts(authority, principal, ws, query="alpha beta QUERYLEAKZ", top_k=3)
    assert art["count"] == 3
    assert art["embedding_model"] == LOCAL_EMBEDDING_MODEL
    assert art["content_redacted"] is True
    # The identical document ranks first with cosine ~1.0.
    assert art["results"][0]["vector_id"] == id1
    assert art["results"][0]["score"] >= 0.999

    # The query text must never leak into the search event payload.
    viewer = EventViewer(SQLiteStore(ws))
    for ev in viewer.list_events(event_type="action_executed"):
        payload = viewer.read_event_payload(ev["event_id"])
        if "results" in (payload or {}).get("payload", {}).get("artifacts", {}):
            assert "QUERYLEAKZ" not in json.dumps(payload)


def test_search_respects_top_k(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    for text in ("one apple", "two banana", "three cherry"):
        _embed_doc(authority, principal, ws, text)
    art = _search_artifacts(authority, principal, ws, query="apple", top_k=1)
    assert art["count"] == 1
    assert len(art["results"]) == 1


def test_search_ignores_other_embedding_models(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    local_id = _embed_doc(authority, principal, ws, "local hashing document")
    # A provider-model vector in the same table must NOT be returned by local search.
    store = SQLiteStore(ws)
    store.insert_vector_record(VectorRecord(
        vector_id="vec_provider_x",
        content_hash="deadbeef",
        content_preview="provider doc",
        embedding_model="openai:text-embedding-3-small",
        dimensions=384,
        scope="default",
        sensitivity="public",
        created_at=utc_now(),
        embedding=json.dumps([0.5] * 384),
    ))
    art = _search_artifacts(authority, principal, ws, query="local hashing document", top_k=5)
    returned = {r["vector_id"] for r in art["results"]}
    assert returned == {local_id}
    assert "vec_provider_x" not in returned


def test_search_empty_store_returns_zero(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    art = _search_artifacts(authority, principal, ws, query="nothing stored yet")
    assert art["count"] == 0
    assert art["results"] == []


def test_search_missing_query_fails_closed(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(_action(principal.principal_id, action="search"), principal)
    assert result.error == "missing_argument:query"


def test_search_invalid_top_k_fails_closed(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    authority, principal = _authority(ws)
    result = authority.route_action(
        _action(principal.principal_id, action="search", query="x", top_k=0), principal
    )
    assert result.error == "invalid_argument:top_k"
