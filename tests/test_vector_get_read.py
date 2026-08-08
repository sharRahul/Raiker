"""Governed read `vector_get` — resolve a vector_id to its stored record.

This is the read half of the embed -> store -> search -> retrieve loop: search
returns `{vector_id, score}` (metadata only), and `vector_get` turns a vector_id
back into its stored 120-char preview + metadata. Like `memory_get`, it is a
governed read routed through the ToolBroker + PolicyEngine read allowlist.
"""

from __future__ import annotations

from pathlib import Path

from machine_identity_helpers import IdentityBoundTestBroker as ToolBroker

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import ClientMetadata, ToolAction, VectorRecord
from raiker.events.writer import EventLogWriter
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.vector_tools import vector_get


def _seed_vector(ws: Path, vector_id: str = "vec_seed_1", preview: str = "hello world doc") -> None:
    SQLiteStore(ws).insert_vector_record(VectorRecord(
        vector_id=vector_id,
        content_hash="abc123",
        content_preview=preview,
        embedding_model="raiker-local-hash-v1",
        dimensions=384,
        scope="default",
        sensitivity="public",
        created_at=utc_now(),
        embedding="[0.0]",
    ))


def _broker(ws: Path) -> ToolBroker:
    store = SQLiteStore(ws)
    return ToolBroker(
        workspace_root=ws,
        policy_engine=PolicyEngine(StaticPolicyConfig(ws)),
        store=store,
        writer=EventLogWriter(store),
    )


# ── Direct function ──────────────────────────────────────────────────────────


def test_vector_get_returns_preview_and_metadata(tmp_path: Path) -> None:
    _seed_vector(tmp_path, preview="the quick brown fox")
    out = vector_get(tmp_path, "vec_seed_1")
    assert out["status"] == "success"
    assert out["vector_id"] == "vec_seed_1"
    assert out["content_preview"] == "the quick brown fox"
    assert out["embedding_model"] == "raiker-local-hash-v1"
    assert out["dimensions"] == 384
    # The raw embedding vector is not returned by the resolve read.
    assert "embedding" not in out


def test_vector_get_unknown_id_fails_closed(tmp_path: Path) -> None:
    SQLiteStore(tmp_path)  # create schema
    out = vector_get(tmp_path, "vec_missing")
    assert out["status"] == "failed"
    assert out["error"]["type"] == "not_found"


def test_vector_get_missing_argument_fails_closed(tmp_path: Path) -> None:
    SQLiteStore(tmp_path)
    out = vector_get(tmp_path, "")
    assert out["status"] == "failed"
    assert out["error"]["type"] == "missing_argument"


# ── Through the governed ToolBroker read path ────────────────────────────────


def test_broker_allows_vector_get_and_returns_preview(tmp_path: Path) -> None:
    _seed_vector(tmp_path, preview="broker retrieved snippet")
    broker = _broker(tmp_path)
    result, decision = broker.execute(
        ToolAction(new_id("act_"), "vector_get", {"vector_id": "vec_seed_1"}, "low", False),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        client=ClientMetadata(type="test_harness", name="tests", version="0.0.0"),
    )
    assert decision.decision == "allow"
    assert decision.reasons == ["workspace_read_allowed"]
    assert result.status == "success"
    assert result.output is not None
    assert result.output["content_preview"] == "broker retrieved snippet"


def test_broker_vector_get_unknown_id_is_a_clean_failure(tmp_path: Path) -> None:
    SQLiteStore(tmp_path)
    broker = _broker(tmp_path)
    result, decision = broker.execute(
        ToolAction(new_id("act_"), "vector_get", {"vector_id": "nope"}, "low", False),
        session_id=new_id("sess_"),
        turn_id=new_id("turn_"),
        client=ClientMetadata(type="test_harness", name="tests", version="0.0.0"),
    )
    # Policy still allows the read; the tool itself reports not_found (no crash).
    assert decision.decision == "allow"
    assert result.status == "failed"
    assert result.error is not None
    assert result.error["type"] == "not_found"
