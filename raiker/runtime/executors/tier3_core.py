from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.graph.indexer import GraphIndexer
from raiker.runtime.executors.base import ExecutionResult

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction
    from raiker.storage.sqlite import SQLiteStore

_MAX_EMBED_TEXT_LEN = 20000
_PREVIEW_LEN = 120


class GraphIndexingExecutor:
    capability = "graph_indexing_runtime"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        scope = str(action.arguments.get("scope", "project"))
        try:
            indexer = GraphIndexer(workspace_root=self._workspace_root)
            indexer.index_python_directory()
            return ExecutionResult(
                ok=True, capability=self.capability, action_id=action.action_id,
                summary="Graph index completed.",
                artifacts={"scope": scope},
            )
        except Exception as exc:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"graph_index_failed:{exc}",
                summary="Graph indexing failed.",
            )


class SemanticMemoryExecutor:
    capability = "semantic_memory_runtime"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        from raiker.memory.store import search_memory
        from raiker.storage.sqlite import SQLiteStore

        query = str(action.arguments.get("query", ""))
        if not query:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:query",
                summary="Semantic memory query denied: no query provided.",
            )
        store = SQLiteStore(self._workspace_root)
        results = search_memory(
            query, workspace_root=self._workspace_root, store=store,
            owner_principal_id=store.account_scope(principal.principal_id),
        )
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=f"Semantic memory search returned {len(results)} results.",
            artifacts={"result_count": len(results)},
        )


class VectorEmbeddingExecutor:
    """Real, local-only executor for ``vector_embedding_runtime``.

    Computes a **deterministic, local, dependency-free** embedding (the hashing
    trick, ``raiker.vector.embed_text``) and persists a ``vector_records`` row —
    no embedding-model download, no network, no external call. This is a genuine
    local runtime, not a stub: it captures lexical overlap and supports offline
    cosine search, but is **not** a learned semantic model (that is the separate,
    egress-gated ``model_provider_runtime`` slice).

    Supported ``action`` argument values: ``embed`` (default), ``list``, and
    ``search`` (cosine retrieval over the locally-stored embeddings). Artifacts
    are metadata only (ids/counts/hash/scores), never the source text or stored
    previews, so embedded content is not emitted into runtime events.
    """

    capability = "vector_embedding_runtime"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        op = action.arguments.get("action", "embed")
        # Owner-scope only for a real account: a CLI-bootstrapped owner has no
        # credential row, and scoping its reads on a non-account principal id
        # hides its own records.
        owner = self._store.account_scope(principal.principal_id)
        if op == "project_memory":
            return self._project_memory(action, owner)
        if op == "embed":
            return self._embed(action, owner)
        if op == "list":
            return self._list(action, owner)
        if op == "search":
            return self._search(action, owner)
        return self._failed(action.action_id, f"unknown_action:{op}")

    def _embed(self, action: GovernedAction, owner_principal_id: str | None) -> ExecutionResult:
        import json

        from raiker.contracts.ids import new_id, utc_now
        from raiker.contracts.models import VectorRecord
        from raiker.vector import LOCAL_EMBEDDING_MODEL, VectorIndex, embed_text

        text = action.arguments.get("text")
        if not isinstance(text, str) or not text.strip():
            return self._failed(action.action_id, "missing_argument:text")
        if len(text) > _MAX_EMBED_TEXT_LEN:
            return self._failed(action.action_id, "text_too_long")
        scope = action.arguments.get("scope", "default")
        sensitivity = action.arguments.get("sensitivity", "public")
        if not isinstance(scope, str) or not isinstance(sensitivity, str):
            return self._failed(action.action_id, "invalid_argument:scope_or_sensitivity")

        dimensions = 384
        vector = embed_text(text, dimensions)
        vector_id = new_id("vec_")
        content_hash = VectorIndex.compute_content_hash(text)
        self._store.insert_vector_record(VectorRecord(
            vector_id=vector_id,
            content_hash=content_hash,
            content_preview=text[:_PREVIEW_LEN],
            embedding_model=LOCAL_EMBEDDING_MODEL,
            dimensions=dimensions,
            scope=scope,
            sensitivity=sensitivity,
            created_at=utc_now(),
            embedding=json.dumps(vector),
            owner_principal_id=owner_principal_id or "",
        ))
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary="Embedding computed locally and stored; source text not emitted.",
            artifacts={
                "vector_id": vector_id,
                "embedding_model": LOCAL_EMBEDDING_MODEL,
                "dimensions": dimensions,
                "content_hash": content_hash,
                "content_redacted": True,
            },
        )

    def _project_memory(self, action: GovernedAction, owner_principal_id: str | None) -> ExecutionResult:
        import json

        memory_id = action.arguments.get("memory_id")
        if not isinstance(memory_id, str) or not memory_id:
            return self._failed(action.action_id, "missing_argument:memory_id")
        memory = self._store.get_active_approved_memory(memory_id, owner_principal_id=owner_principal_id)
        if memory is None:
            return self._failed(action.action_id, "memory_not_active_or_not_found")
        from raiker.contracts.ids import new_id, utc_now
        from raiker.contracts.models import VectorRecord
        from raiker.vector import LOCAL_EMBEDDING_MODEL, VectorIndex, embed_text

        text = str(memory["text"])
        vector_id = new_id("vec_")
        self._store.insert_vector_record(VectorRecord(
            vector_id=vector_id, content_hash=VectorIndex.compute_content_hash(text),
            content_preview=text[:_PREVIEW_LEN], embedding_model=LOCAL_EMBEDDING_MODEL,
            dimensions=384, scope=str(memory["scope"]), sensitivity=str(memory["sensitivity"]),
            created_at=utc_now(), embedding=json.dumps(embed_text(text, 384)),
            owner_principal_id=owner_principal_id or "",
        ))
        self._store.link_memory_projection(
            memory_id, "vector", vector_id, LOCAL_EMBEDDING_MODEL,
            owner_principal_id=owner_principal_id,
        )
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary="Approved durable memory projected to a local vector; source text not emitted.",
            artifacts={"memory_id": memory_id, "vector_id": vector_id, "content_redacted": True},
        )

    def _list(self, action: GovernedAction, owner_principal_id: str | None) -> ExecutionResult:
        records = self._store.list_vector_records(owner_principal_id=owner_principal_id)
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary="Listed local vector records; previews/text are not included in runtime artifacts.",
            artifacts={
                "count": len(records),
                "vector_ids": [str(r["vector_id"]) for r in records],
                "content_redacted": True,
            },
        )

    def _search(self, action: GovernedAction, owner_principal_id: str | None) -> ExecutionResult:
        import json

        from raiker.vector import LOCAL_EMBEDDING_MODEL, VectorIndex, embed_text

        query = action.arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            return self._failed(action.action_id, "missing_argument:query")
        if len(query) > _MAX_EMBED_TEXT_LEN:
            return self._failed(action.action_id, "query_too_long")
        top_k = action.arguments.get("top_k", 5)
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k <= 0 or top_k > 100:
            return self._failed(action.action_id, "invalid_argument:top_k")
        scope = action.arguments.get("scope")
        if scope is not None and not isinstance(scope, str):
            return self._failed(action.action_id, "invalid_argument:scope")

        dimensions = 384
        # Retrieval only compares within the local hashing-embedding space; the
        # query is embedded with the same deterministic local model the stored
        # vectors were created with. Provider-model vectors are not searched here.
        query_vector = embed_text(query, dimensions)
        index = VectorIndex(dimensions)
        for row in self._store.list_vector_embeddings(
            LOCAL_EMBEDDING_MODEL, scope=scope, owner_principal_id=owner_principal_id
        ):
            raw = row.get("embedding")
            if not raw:
                continue
            try:
                vector = json.loads(raw)
            except (TypeError, ValueError):
                continue
            if isinstance(vector, list) and len(vector) == dimensions:
                index.upsert(str(row["vector_id"]), vector)
        results = index.search(query_vector, top_k=top_k)
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary="Vector search returned ranked ids/scores; query text and previews are not emitted.",
            artifacts={
                "count": len(results),
                # Ranked ids + similarity scores only — never the query or stored text.
                "results": [{"vector_id": r["vector_id"], "score": r["score"]} for r in results],
                "embedding_model": LOCAL_EMBEDDING_MODEL,
                "content_redacted": True,
            },
        )

    def _failed(self, action_id: str, reason_code: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action_id,
            reason_code=reason_code,
            summary="Vector embedding runtime failed closed.",
            artifacts={},
        )


class CodeMapIndexExecutor:
    """B9 — build or refresh the repository code map, under the owner's switch.

    This is what makes ``graph_codemap_indexing`` a capability the owner can turn
    on rather than a name on a matrix. A capability with no executor is stripped
    of its enable targets by the activation layer and reads as *deferred* in the
    interface, which is exactly what this one was: a real gate in front of a scan
    that did not exist.

    It executes nothing outside the workspace and returns nothing but counts.
    The map it writes is derived from files the agent may already read, and
    reading one at the coordinates it records still goes through ``read_file``,
    workspace containment, and the policy engine — so indexing adds no authority
    to the turn that asked for it.
    """

    capability = "code_map_indexing"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        from raiker.graph.codemap_service import CodeMapService

        service = CodeMapService(
            self._workspace_root, self._store, principal_id=principal.principal_id
        )
        operation = str(action.arguments.get("operation", "build"))
        if operation == "refresh":
            raw = action.arguments.get("paths", [])
            paths = [str(item) for item in raw] if isinstance(raw, (list, tuple)) else []
            if not paths:
                return ExecutionResult(
                    ok=False, capability=self.capability, action_id=action.action_id,
                    reason_code="missing_argument:paths",
                    summary="Code map refresh needs the paths that changed.",
                )
            result = service.refresh_paths(paths)
            return ExecutionResult(
                ok=result.get("status") == "refreshed",
                capability=self.capability, action_id=action.action_id,
                reason_code="" if result.get("status") == "refreshed" else str(result.get("reason", "")),
                summary=f"Code map refreshed {result.get('refreshed', 0)} file(s).",
                artifacts={k: v for k, v in result.items() if k != "paths"},
            )
        if operation != "build":
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=f"unknown_operation:{operation}",
                summary="Code map executor supports 'build' and 'refresh'.",
            )
        result = service.build()
        status = str(result.get("status", ""))
        if status in ("indexed", "partial"):
            return ExecutionResult(
                ok=True, capability=self.capability, action_id=action.action_id,
                summary=(
                    f"Code map {status}: {result['file_count']} files, "
                    f"{result['symbol_count']} symbols in {result['repository']}."
                ),
                artifacts=result,
            )
        error = result.get("error", {}) if isinstance(result.get("error"), dict) else {}
        return ExecutionResult(
            ok=False, capability=self.capability, action_id=action.action_id,
            reason_code=str(error.get("type", "code_map_failed")),
            summary=str(error.get("message", "Code map indexing failed closed.")),
            artifacts={},
        )
