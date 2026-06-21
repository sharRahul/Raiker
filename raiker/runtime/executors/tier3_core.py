from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.graph.indexer import GraphIndexer
from raiker.runtime.executors.base import ExecutionResult, not_implemented

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction


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
        query = str(action.arguments.get("query", ""))
        if not query:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:query",
                summary="Semantic memory query denied: no query provided.",
            )
        results = search_memory(query, workspace_root=self._workspace_root)
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=f"Semantic memory search returned {len(results)} results.",
            artifacts={"result_count": len(results)},
        )


class VectorEmbeddingExecutor:
    capability = "vector_embedding_runtime"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        # No embedding model or vector store is wired yet; reporting success
        # while persisting nothing would be a silent fake. Fail closed.
        return not_implemented(self.capability, action.action_id)


class ModelProviderExecutor:
    capability = "model_provider_runtime"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        # Real provider dispatch is owned by the gateway/provider layer; this
        # executor does not perform a model call, so it fails closed.
        return not_implemented(self.capability, action.action_id)
