"""MEM-10 — the owner can build a semantic recall space, not just select one.

``list_embedding_spaces`` reads the spaces a workspace *holds vectors in*, which
is right for choosing one and useless for getting one: a default install holds
none, so "Recall backend" offered the lexical fallback and nothing else. These
tests pin the path that produces the first semantic space — one governed
``model_provider_runtime`` action over the approved memories — and the three
things that must stay true about it: the batch is bounded, it is scoped to the
acting principal, and a second run does not re-embed what the first one did.

No test performs real network I/O; the embedder is injected exactly as the
existing ``model_provider_runtime`` acceptance tests inject it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.context.gatherer import ContextGatherer, RetrievalScope
from raiker.contracts.ids import new_id, utc_now
from raiker.control.dashboard import DashboardService
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.knowledge.files import ManagedFileScope, ManagedFileService
from raiker.knowledge.indexing import ManagedFileIndexer
from raiker.memory.query_embedding import GovernedQueryEmbedder
from raiker.memory.retrieval import retrieve_hybrid_memory
from raiker.memory.store import MemoryGovernance, write_memory
from raiker.models.contracts import EmbeddingResponse
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors import ModelProviderExecutor, build_default_executor_registry
from raiker.runtime.executors.models_runtime import Embedder
from raiker.storage.sqlite import SQLiteStore
from raiker.vector.backends import (
    MAX_MEMORY_INDEX_BATCH,
    embedding_capable_profiles,
    resolve_embedding_backend,
)

_CAP = "model_provider_runtime"
_TOOL = "model_provider"
_DOC = "docs/threat-models/model-provider.md"
_ALLOWLIST_ENV = "RAIKER_MODEL_EGRESS_ALLOWLIST"
_PROVIDER = "openai"
_MODEL = "text-embedding-3-small"
_SPACE = f"{_PROVIDER}:{_MODEL}"
_LOCAL_PROVIDER = "llama.cpp"
_LOCAL_MODEL = "local-gguf"
_LOCAL_SPACE = f"{_LOCAL_PROVIDER}:{_LOCAL_MODEL}"


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "semantic_index"
    ws.mkdir()
    return ws


def _enable(ws: Path) -> None:
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    service = RuntimeControlService(ws)
    service.activate_runtime_mode("local_single_user_runtime", None, "test")
    store = SQLiteStore(ws)
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref)"
            " VALUES (?, ?, ?, ?)",
            (_CAP, "principal_owner", utc_now(), _DOC),
        )
    result = service.set_capability_state(
        _CAP, "enabled_runtime", None, "test", confirmation_token="confirm"
    )
    assert result.ok is True, result.reason_code


def _counting_embedder(calls: list[str]) -> Embedder:
    def embed(provider: str, model: str, text: str) -> EmbeddingResponse:
        calls.append(text)
        return EmbeddingResponse(vector=[0.1, 0.2, 0.3], model=_MODEL, usage={"tokens": len(text)})

    return embed


def _authority(ws: Path, embedder: Embedder) -> tuple[RuntimeAuthority, Principal]:
    store = SQLiteStore(ws)
    registry = build_default_executor_registry(ws, store)
    registry.register(_CAP, ModelProviderExecutor(ws, store, embedder=embedder))
    authority = RuntimeAuthority(store, EventLogWriter(store), executor_registry=registry)
    raw = store.get_principal("principal_owner")
    assert raw is not None
    return authority, Principal(**raw)


def _index_action(principal_id: str, **extra: object) -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal_id,
        action_type=_TOOL,
        tool_or_service_name=_TOOL,
        arguments={
            "operation": "index_memories",
            "provider": _PROVIDER,
            "model": _MODEL,
            **extra,
        },
        risk_level=RiskLevelValue.MEDIUM,
        session_id="sess_semantic_index",
    )


def _memory(ws: Path, store: SQLiteStore, text: str) -> str:
    entry = write_memory(
        text,
        workspace_root=ws,
        store=store,
        governance=MemoryGovernance(
            "evt", "sess", None, "test", 1, 1, "until_forget", "approved", "test"
        ),
    )
    return entry.memory_id


# ── What could produce a space at all ────────────────────────────────────────


def test_offered_embedding_models_are_concrete_and_named() -> None:
    """A listed profile names the model, because the model *is* the space.

    A placeholder embedding model picks its name at selection time, so a button
    built on one could not say what it was about to call, and the vectors it
    produced could not be attributed to a space the owner could later select.
    """
    offered = embedding_capable_profiles()
    assert offered, "the shipped profiles include embedding-capable providers"
    for item in offered:
        assert "<" not in item["model"] and ">" not in item["model"]
        assert item["space"] == f"{item['provider']}:{item['model']}"
    assert (_PROVIDER, _MODEL) in {(item["provider"], item["model"]) for item in offered}


# ── The governed batch ───────────────────────────────────────────────────────


def test_index_memories_creates_a_selectable_semantic_space(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_ALLOWLIST_ENV, "api.openai.com")
    ws = _ws(tmp_path)
    _enable(ws)
    store = SQLiteStore(ws)
    for text in ("The backup target is the encrypted NAS.", "Deploys happen on Thursdays."):
        _memory(ws, store, text)

    calls: list[str] = []
    authority, principal = _authority(ws, _counting_embedder(calls))
    result = authority.route_action(_index_action(principal.principal_id), principal)

    assert result.decision == "allow", result.error
    assert result.artifacts["indexed_count"] == 2
    assert result.artifacts["embedding_model"] == _SPACE
    assert len(calls) == 2
    # The point of the whole change: the space is now one recall can be pointed
    # at, and `auto` picks it over the lexical fallback.
    backend = resolve_embedding_backend(store, owner_principal_id="principal_owner")
    assert backend.semantic is True
    assert backend.model_label == _SPACE


def test_local_index_needs_no_remote_egress_allowlist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A loopback embedding is governed, but it is not remote egress."""
    monkeypatch.delenv(_ALLOWLIST_ENV, raising=False)
    ws = _ws(tmp_path)
    _enable(ws)
    store = SQLiteStore(ws)
    _memory(ws, store, "The backup target is the encrypted NAS.")
    calls: list[str] = []
    authority, principal = _authority(ws, _counting_embedder(calls))
    action = _index_action(
        principal.principal_id,
        provider=_LOCAL_PROVIDER,
        model=_LOCAL_MODEL,
    )

    result = authority.route_action(action, principal)

    assert result.decision == "allow", result.error
    assert result.artifacts["embedding_model"] == _LOCAL_SPACE
    assert result.artifacts["local_only"] is True
    assert result.artifacts["provider_backed"] is False
    backend = resolve_embedding_backend(store, owner_principal_id="principal_owner")
    assert backend.kind == "local_model"
    assert backend.model_label == _LOCAL_SPACE


def test_a_second_run_does_not_re_embed_what_the_first_one_did(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-running is how an owner picks up memories approved since — not a bill.

    Every embedded row is a provider call the owner paid for. A second run that
    re-sent the same text would make "keep the index current" cost the same as
    building it from scratch every time.
    """
    monkeypatch.setenv(_ALLOWLIST_ENV, "api.openai.com")
    ws = _ws(tmp_path)
    _enable(ws)
    store = SQLiteStore(ws)
    _memory(ws, store, "The backup target is the encrypted NAS.")

    calls: list[str] = []
    authority, principal = _authority(ws, _counting_embedder(calls))
    assert (
        authority.route_action(_index_action(principal.principal_id), principal).decision == "allow"
    )
    assert len(calls) == 1

    _memory(ws, store, "Deploys happen on Thursdays.")
    result = authority.route_action(_index_action(principal.principal_id), principal)
    assert result.decision == "allow", result.error
    assert result.artifacts["indexed_count"] == 1
    assert calls == [
        "The backup target is the encrypted NAS.",
        "Deploys happen on Thursdays.",
    ]


def test_query_is_embedded_once_and_a_paraphrase_reaches_the_vector_leg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BUG-240: the selected semantic space now embeds both sides of recall."""
    monkeypatch.setenv(_ALLOWLIST_ENV, "api.openai.com")
    ws = _ws(tmp_path)
    _enable(ws)
    store = SQLiteStore(ws)
    _memory(ws, store, "The backup target is the encrypted NAS.")

    calls: list[str] = []

    def semantic(provider: str, model: str, text: str) -> EmbeddingResponse:
        calls.append(text)
        vector = [1.0, 0.0, 0.0] if "backup" in text or "disaster" in text else [0.0, 1.0, 0.0]
        return EmbeddingResponse(vector=vector, model=_MODEL, usage=None)

    authority, principal = _authority(ws, semantic)
    assert (
        authority.route_action(_index_action(principal.principal_id), principal).decision == "allow"
    )
    mode = RuntimeControlService(ws).set_capability_decision_mode(
        _CAP, "always_allow", principal.principal_id, "semantic recall test"
    )
    assert mode.ok, mode.reason_code
    embedder = GovernedQueryEmbedder(
        store,
        principal.principal_id,
        session_id="sess_semantic_read",
        turn_id="turn_semantic_read",
        authority=authority,
    )

    first = retrieve_hybrid_memory(
        store=store,
        query="Where is the disaster destination?",
        owner_principal_id=principal.principal_id,
        query_embedder=embedder,
    )
    second = retrieve_hybrid_memory(
        store=store,
        query="Where is the disaster destination?",
        owner_principal_id=principal.principal_id,
        query_embedder=embedder,
    )

    assert first and first[0].text == "The backup target is the encrypted NAS."
    assert first[0].sources == ("vector",)
    assert second[0].memory_id == first[0].memory_id
    assert calls.count("Where is the disaster destination?") == 1
    # Search questions are ephemeral, not new vector records.
    assert len(store.list_vector_records()) == 1


def test_managed_file_passage_is_semantic_and_revision_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BUG-240: the same governed query reaches owned document projections."""
    monkeypatch.setenv(_ALLOWLIST_ENV, "api.openai.com")
    ws = _ws(tmp_path)
    _enable(ws)
    store = SQLiteStore(ws)
    files = ManagedFileService(ws, store)
    indexer = ManagedFileIndexer(ws, store)
    record = files.import_file(
        ManagedFileScope("memory"),
        "runbooks/recovery.md",
        b"The encrypted NAS is the disaster recovery destination.",
        "text/markdown",
        "principal_owner",
    )
    indexer.index(record.file_id, "principal_owner")
    calls: list[str] = []

    def semantic(provider: str, model: str, text: str) -> EmbeddingResponse:
        calls.append(text)
        vector = [1.0, 0.0, 0.0] if "NAS" in text or "backups" in text else [0.0, 1.0, 0.0]
        return EmbeddingResponse(vector=vector, model=_MODEL, usage=None)

    authority, principal = _authority(ws, semantic)
    built = authority.route_action(_index_action(principal.principal_id), principal)
    assert built.decision == "allow", built.error
    assert built.artifacts["indexed_count"] == 0
    assert built.artifacts["indexed_file_chunk_count"] == 1
    assert (
        RuntimeControlService(ws)
        .set_capability_decision_mode(
            _CAP, "always_allow", principal.principal_id, "semantic file recall test"
        )
        .ok
    )
    embedder = GovernedQueryEmbedder(store, principal.principal_id, authority=authority)
    backend = resolve_embedding_backend(store, owner_principal_id=principal.principal_id)
    assert backend.model_label == _SPACE
    query_vector = embedder(backend, "Where should backups be stored?")
    assert query_vector == [1.0, 0.0, 0.0]
    assert store.search_managed_file_chunk_vectors(
        query_vector,
        backend.model_label,
        owner_principal_id=principal.principal_id,
    )

    hits = ContextGatherer._recalled_files(
        store,
        "Where should backups be stored?",
        principal.principal_id,
        RetrievalScope("chat", None),
        query_embedder=embedder,
    )

    assert hits and hits[0]["file_id"] == record.file_id
    assert hits[0]["sources"] == ["vector"]
    assert calls.count("Where should backups be stored?") == 1
    vector_count = len(store.list_vector_records(owner_principal_id=principal.principal_id))
    assert vector_count == 1

    indexer.retire(record.file_id, principal.principal_id)
    assert (
        store.search_managed_file_chunk_vectors(
            [1.0, 0.0, 0.0],
            _SPACE,
            owner_principal_id=principal.principal_id,
        )
        == []
    )
    assert store.list_vector_records(owner_principal_id=principal.principal_id) == []


def test_ask_mode_drops_semantic_leg_without_parking_an_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_ALLOWLIST_ENV, "api.openai.com")
    ws = _ws(tmp_path)
    _enable(ws)
    store = SQLiteStore(ws)
    calls: list[str] = []
    authority, principal = _authority(ws, _counting_embedder(calls))
    backend = type(resolve_embedding_backend(store))(
        backend_id="provider", kind="provider", model_label=_SPACE, dimensions=3
    )

    vector = GovernedQueryEmbedder(store, principal.principal_id, authority=authority)(
        backend, "private search question"
    )

    assert vector is None
    assert calls == []
    assert store.count_pending_approvals() == 0


def test_query_embedding_audit_excludes_query_and_vector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_ALLOWLIST_ENV, "api.openai.com")
    ws = _ws(tmp_path)
    _enable(ws)
    store = SQLiteStore(ws)
    authority, principal = _authority(ws, _counting_embedder([]))
    assert (
        RuntimeControlService(ws)
        .set_capability_decision_mode(
            _CAP, "always_allow", principal.principal_id, "semantic recall test"
        )
        .ok
    )
    backend = type(resolve_embedding_backend(store))(
        backend_id="provider", kind="provider", model_label=_SPACE, dimensions=3
    )
    query = "the uniquely private semantic question"

    result = GovernedQueryEmbedder(
        store, principal.principal_id, session_id="sess_query_audit", authority=authority
    )(backend, query)

    assert result == [0.1, 0.2, 0.3]
    event_text = (store.paths.events_dir / "sess_query_audit.jsonl").read_text(encoding="utf-8")
    assert query not in event_text
    assert "[0.1, 0.2, 0.3]" not in event_text
    assert '"operation":"embed_query"' in event_text.replace(" ", "")


def test_the_space_is_named_for_the_model_the_owner_chose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A provider echoing a variant name must not rename the space.

    Taking the provider's word for the label meant the candidate filter looked
    for a string nothing had ever been stored under, so a second run re-embedded
    the whole corpus — for as long as the owner kept the index current. The
    provider's own answer is kept as evidence in the artifacts.
    """
    monkeypatch.setenv(_ALLOWLIST_ENV, "api.openai.com")
    ws = _ws(tmp_path)
    _enable(ws)
    store = SQLiteStore(ws)
    _memory(ws, store, "The backup target is the encrypted NAS.")
    _memory(ws, store, "Deploys happen on Thursdays.")

    calls: list[str] = []

    def renaming(provider: str, model: str, text: str) -> EmbeddingResponse:
        calls.append(text)
        return EmbeddingResponse(vector=[0.1, 0.2], model="text-embedding-3-small-v2", usage=None)

    authority, principal = _authority(ws, renaming)
    first = authority.route_action(_index_action(principal.principal_id), principal)
    assert first.decision == "allow", first.error
    assert first.artifacts["embedding_model"] == _SPACE
    assert first.artifacts["provider_models"] == ["text-embedding-3-small-v2"]
    assert first.artifacts["indexed_count"] == 2
    assert len(calls) == 2

    second = authority.route_action(_index_action(principal.principal_id), principal)
    assert second.error == "no_memories_to_index"
    assert len(calls) == 2
    # And the space the owner can then select is the one they asked for.
    assert (
        resolve_embedding_backend(store, owner_principal_id="principal_owner").model_label == _SPACE
    )


def test_nothing_to_index_fails_closed_rather_than_reporting_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_ALLOWLIST_ENV, "api.openai.com")
    ws = _ws(tmp_path)
    _enable(ws)
    calls: list[str] = []
    authority, principal = _authority(ws, _counting_embedder(calls))
    result = authority.route_action(_index_action(principal.principal_id), principal)
    assert result.error == "no_memories_to_index"
    assert calls == []


def test_a_credential_shaped_memory_never_reaches_the_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The batch inherits ``project_memory``'s sensitivity boundary exactly.

    A batch that widened it would be the worst possible place to widen it: the
    owner approves one run and every secret-shaped memory leaves the machine.
    """
    monkeypatch.setenv(_ALLOWLIST_ENV, "api.openai.com")
    ws = _ws(tmp_path)
    _enable(ws)
    store = SQLiteStore(ws)
    _memory(ws, store, "api_key=abcdefghijklmnop")
    _memory(ws, store, "The backup target is the encrypted NAS.")

    calls: list[str] = []
    authority, principal = _authority(ws, _counting_embedder(calls))
    result = authority.route_action(_index_action(principal.principal_id), principal)
    assert result.decision == "allow", result.error
    assert calls == ["The backup target is the encrypted NAS."]


def test_a_provider_refusal_stops_the_batch_and_reports_what_it_had_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_ALLOWLIST_ENV, "api.openai.com")
    ws = _ws(tmp_path)
    _enable(ws)
    store = SQLiteStore(ws)
    for index in range(3):
        _memory(ws, store, f"Memory number {index} about backups and deploys.")

    seen: list[str] = []

    def flaky(provider: str, model: str, text: str) -> EmbeddingResponse:
        seen.append(text)
        if len(seen) == 2:
            raise RuntimeError("boom")
        return EmbeddingResponse(vector=[0.1, 0.2], model=_MODEL, usage=None)

    authority, principal = _authority(ws, flaky)
    result = authority.route_action(_index_action(principal.principal_id), principal)
    assert result.error is not None and result.error.startswith("model_provider_error:")
    assert result.artifacts["indexed_count"] == 1
    # The vector the first call produced is kept: it is a real vector in a named
    # space, and discarding paid-for work to tidy the record helps nobody.
    assert len(store.list_vector_records()) == 1


def test_the_batch_is_bounded_by_the_shared_ceiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_ALLOWLIST_ENV, "api.openai.com")
    ws = _ws(tmp_path)
    _enable(ws)
    store = SQLiteStore(ws)
    for index in range(4):
        _memory(ws, store, f"Memory number {index} about backups and deploys.")

    calls: list[str] = []
    authority, principal = _authority(ws, _counting_embedder(calls))
    result = authority.route_action(
        _index_action(principal.principal_id, limit=MAX_MEMORY_INDEX_BATCH * 10), principal
    )
    assert result.decision == "allow", result.error
    assert result.artifacts["indexed_count"] == 4

    over = ModelProviderExecutor(ws, store)
    assert MAX_MEMORY_INDEX_BATCH == 500
    assert over.capability == _CAP


# ── The owner surface ────────────────────────────────────────────────────────


def test_settings_report_what_is_waiting_and_what_could_embed_it(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    store = SQLiteStore(ws)
    _memory(ws, store, "The backup target is the encrypted NAS.")

    settings = DashboardService(ws).get_memory_settings("principal_owner")
    assert settings.unindexed_memories == 1
    assert (_PROVIDER, _MODEL) in {
        (item["provider"], item["model"]) for item in settings.embedding_providers
    }
    offered = next(
        item
        for item in settings.embedding_providers
        if (item["provider"], item["model"]) == (_PROVIDER, _MODEL)
    )
    assert offered["unindexed_memories"] == 1
    assert offered["pending_count"] == 1


def test_an_unoffered_model_is_refused_before_any_provider_call(tmp_path: Path) -> None:
    """Refused, not attempted: a space Raiker cannot name is not one to build."""
    ws = _ws(tmp_path)
    _enable(ws)
    result = RuntimeControlService(ws).build_memory_embedding_index(
        "principal_owner", "openai", "not-a-real-embedding-model"
    )
    assert result.ok is False
    assert result.reason_code == "embedding_model_not_offered"


def test_an_unnamed_model_is_refused(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    _enable(ws)
    result = RuntimeControlService(ws).build_memory_embedding_index("principal_owner", "", "")
    assert result.ok is False
    assert result.reason_code == "embedding_model_not_named"
