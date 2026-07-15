"""Governed, default-ask retrieval augmentation wired into the agent turn.

`RetrievalAugmentor` reuses the `vector_embedding_runtime` gate + decision mode:
disabled gate → no-op; enabled + `ask` (default) → withheld; enabled +
`allow`/`auto` → inject retrieved local previews into the model context. These
tests pin that governance plus the orchestrator wiring (event emitted only when
the gate is enabled).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import (
    ClientMetadata,
    PromptEnvelope,
    PromptOptions,
    PromptPayload,
    UserMetadata,
    VectorRecord,
)
from raiker.control.service import RuntimeControlService
from raiker.events.query import EventViewer
from raiker.events.writer import EventLogWriter
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.models.contracts import ModelMessage, ModelResponse, ToolSpec
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.orchestrator import RuntimeOrchestrator
from raiker.runtime.retrieval import RetrievalAugmentor
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.broker import ToolBroker
from raiker.vector import LOCAL_EMBEDDING_MODEL, embed_text

_CAP = "vector_embedding_runtime"


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "rag"
    ws.mkdir()
    return ws


def _enable(ws: Path, *, mode: str | None = None) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "t")
    r = svc.set_capability_state(_CAP, "enabled_runtime", None, "t", confirmation_token="confirm")
    assert r.ok is True, r.reason_code
    if mode is not None:
        m = svc.set_capability_decision_mode(_CAP, mode, None, "t")
        assert m.ok is True, m.reason_code


def _seed(ws: Path, text: str) -> str:
    vector_id = new_id("vec_")
    store = SQLiteStore(ws)
    memory = write_memory(
        text, workspace_root=ws, scope="default", store=store,
        governance=MemoryGovernance("evt_rag", "sess_rag", None, "test", 1, 1, "until_forget", "approved", "test"),
    )
    store.insert_vector_record(VectorRecord(
        vector_id=vector_id,
        content_hash="h",
        content_preview=text[:120],
        embedding_model=LOCAL_EMBEDDING_MODEL,
        dimensions=384,
        scope="default",
        sensitivity="public",
        created_at=utc_now(),
        embedding=json.dumps(embed_text(text, 384)),
    ))
    store.link_memory_projection(memory.memory_id, "vector", vector_id, LOCAL_EMBEDDING_MODEL)
    return vector_id


# ── RetrievalAugmentor governance ────────────────────────────────────────────


def test_disabled_gate_is_noop(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    plan = RetrievalAugmentor(ws, SQLiteStore(ws)).plan("anything")
    assert plan.decision == "disabled"
    assert plan.augmented is False
    assert plan.context_text is None


def test_default_ask_withholds_injection(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)  # gate enabled, decision mode left at the default (ask)
    _seed(ws, "alpha beta gamma retrieval")
    plan = RetrievalAugmentor(ws, SQLiteStore(ws)).plan("alpha beta gamma retrieval")
    assert plan.decision == "ask"
    assert plan.augmented is False
    assert plan.context_text is None
    assert plan.metadata["reason"] == "needs_approval"


def test_deny_never_augments(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws, mode="deny")
    _seed(ws, "alpha beta gamma retrieval")
    plan = RetrievalAugmentor(ws, SQLiteStore(ws)).plan("alpha beta gamma retrieval")
    assert plan.decision == "deny"
    assert plan.augmented is False


def test_allow_injects_retrieved_context(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws, mode="allow")
    vid = _seed(ws, "alpha beta gamma retrieval")
    _seed(ws, "unrelated delta epsilon")
    plan = RetrievalAugmentor(ws, SQLiteStore(ws)).plan("alpha beta gamma retrieval")
    assert plan.decision == "allow"
    assert plan.augmented is True
    assert plan.context_text is not None
    assert "alpha beta gamma retrieval" in plan.context_text
    assert plan.metadata["count"] >= 1
    assert vid in plan.metadata["vector_ids"]
    assert plan.metadata["content_redacted"] is True
    assert "trust=untrusted_memory_data" in plan.context_text
    assert "source=mem_" in plan.context_text
    with SQLiteStore(ws).connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM memory_lifecycle_audit WHERE action = 'recall'").fetchone()[0] >= 1


def test_allow_with_empty_store_does_not_augment(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws, mode="allow")
    plan = RetrievalAugmentor(ws, SQLiteStore(ws)).plan("nothing stored")
    assert plan.augmented is False
    assert plan.metadata["count"] == 0


# ── Orchestrator wiring ──────────────────────────────────────────────────────


class _FakeRouter:
    def __init__(self, text: str) -> None:
        self.text = text
        self.last_messages: Sequence[ModelMessage] | None = None

    async def achat(
        self,
        provider: str,
        model: str,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec] | None = None,
    ) -> ModelResponse:
        self.last_messages = messages
        return ModelResponse(text=self.text, finish_reason="stop")


def _orchestrator(ws: Path, router: _FakeRouter) -> RuntimeOrchestrator:
    store = SQLiteStore(ws)
    writer = EventLogWriter(store)
    broker = ToolBroker(
        workspace_root=ws,
        policy_engine=PolicyEngine(StaticPolicyConfig(ws)),
        store=store,
        writer=writer,
    )
    return RuntimeOrchestrator(
        workspace_root=ws, writer=writer, tool_broker=broker, model_router=router,  # type: ignore[arg-type]
    )


def _envelope(ws: Path, prompt: str) -> PromptEnvelope:
    return PromptEnvelope(
        request_id=new_id("req_"),
        session_id="sess_rag",
        turn_id=new_id("turn_"),
        prompt=PromptPayload(text=prompt),
        options=PromptOptions(max_tool_calls=1),
        client=ClientMetadata(type="test_harness", name="tests", version="0.0.0"),
        user=UserMetadata(),
    )


def _augmentation_events(ws: Path) -> list[dict]:
    viewer = EventViewer(SQLiteStore(ws))
    out = []
    for ev in viewer.list_events(event_type="retrieval_augmentation"):
        payload = viewer.read_event_payload(ev["event_id"])
        out.append((payload or {}).get("payload", {}))
    return out


def test_turn_emits_no_event_when_gate_disabled(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    router = _FakeRouter("done")
    import asyncio

    asyncio.run(_orchestrator(ws, router).ahandle(_envelope(ws, "hello world")))
    assert _augmentation_events(ws) == []


def test_turn_injects_context_when_allowed(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws, mode="allow")
    _seed(ws, "alpha beta gamma retrieval")
    router = _FakeRouter("done")
    import asyncio

    asyncio.run(_orchestrator(ws, router).ahandle(_envelope(ws, "alpha beta gamma retrieval")))
    events = _augmentation_events(ws)
    assert len(events) == 1
    assert events[0]["decision"] == "allow"
    assert events[0]["augmented"] is True
    # The retrieved preview was injected into the model prompt (RAG), not just audited.
    assert router.last_messages is not None
    assert any("alpha beta gamma retrieval" in m.content for m in router.last_messages if m.role == "system")


def test_turn_withholds_context_on_default_ask(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)  # default ask
    _seed(ws, "alpha beta gamma retrieval")
    router = _FakeRouter("done")
    import asyncio

    asyncio.run(_orchestrator(ws, router).ahandle(_envelope(ws, "alpha beta gamma retrieval")))
    events = _augmentation_events(ws)
    assert len(events) == 1
    assert events[0]["decision"] == "ask"
    assert events[0]["augmented"] is False
    # No retrieved preview reached the model prompt.
    assert router.last_messages is not None
    assert not any(
        "alpha beta gamma retrieval" in m.content for m in router.last_messages if m.role == "system"
    )
