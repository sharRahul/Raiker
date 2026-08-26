"""Governed, ephemeral query embeddings for semantic memory retrieval."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from raiker.contracts.ids import new_id
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority.admission import capability_admission
from raiker.runtime.authority.decision_modes import DecisionMode
from raiker.runtime.authority.models import Principal, PrincipalType, RiskLevelValue
from raiker.runtime.authority.router import GovernedAction, RuntimeAuthority
from raiker.runtime.executors import build_default_executor_registry

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore
    from raiker.vector.backends import EmbeddingBackend


_EXECUTING_MODES = frozenset({DecisionMode.ALWAYS_ALLOW, DecisionMode.AUTO})


def _principal(store: SQLiteStore, principal_id: str) -> Principal | None:
    raw = store.get_principal(principal_id)
    if raw is None:
        return None
    raw = dict(raw)
    if isinstance(raw.get("principal_type"), str):
        raw["principal_type"] = PrincipalType(raw["principal_type"])
    return Principal(**raw)


def query_embedding_available(
    store: SQLiteStore, owner_principal_id: str | None, backend: EmbeddingBackend
) -> bool:
    """Whether this read can honestly execute the selected semantic backend.

    ``ask`` deliberately means lexical/graph fallback. A passive recall during
    context gathering must not park the turn for approval, and silently treating
    a human caller as pre-approved would make the Memory card disagree with an
    agent search. The owner can choose Always allow or Auto to enable this leg.
    """
    if not backend.semantic or backend.kind != "provider" or not owner_principal_id:
        return False
    admission = capability_admission(store, owner_principal_id, "model_provider_runtime")
    return admission.gate_enabled and admission.decision_mode in _EXECUTING_MODES


class GovernedQueryEmbedder:
    """Embed at most once per backend/query for one turn or tool invocation."""

    def __init__(
        self,
        store: SQLiteStore,
        owner_principal_id: str | None,
        *,
        session_id: str = "memory-retrieval",
        turn_id: str | None = None,
        authority: RuntimeAuthority | None = None,
    ) -> None:
        self._store = store
        self._owner_principal_id = owner_principal_id
        self._session_id = session_id
        self._turn_id = turn_id
        self._authority = authority
        self._cache: dict[tuple[str, str], list[float] | None] = {}

    def __call__(self, backend: EmbeddingBackend, query: str) -> list[float] | None:
        cache_key = (
            backend.model_label,
            hashlib.sha256(query.encode("utf-8")).hexdigest(),
        )
        if cache_key not in self._cache:
            self._cache[cache_key] = self._embed(backend, query)
        return self._cache[cache_key]

    def _embed(self, backend: EmbeddingBackend, query: str) -> list[float] | None:
        owner = self._owner_principal_id
        if not query_embedding_available(self._store, owner, backend) or owner is None:
            return None
        principal = _principal(self._store, owner)
        if principal is None:
            return None
        try:
            provider, model = backend.model_label.split(":", 1)
        except ValueError:
            return None
        if not provider or not model:
            return None

        workspace_root = Path(self._store.paths.workspace_root)
        authority = self._authority
        if authority is None:
            registry = build_default_executor_registry(workspace_root, self._store)
            authority = RuntimeAuthority(
                self._store,
                EventLogWriter(self._store),
                executor_registry=registry,
            )
        result = authority.route_action(
            GovernedAction(
                action_id=new_id("act_"),
                principal_id=principal.principal_id,
                action_type="model_provider",
                tool_or_service_name="model_provider",
                arguments={
                    "operation": "embed_query",
                    "provider": provider,
                    "model": model,
                    "text": query,
                },
                risk_level=RiskLevelValue.LOW,
                session_id=self._session_id,
                turn_id=self._turn_id,
            ),
            principal,
        )
        raw = result.transient.get("embedding") if result.decision == "allow" else None
        if not isinstance(raw, list) or len(raw) != backend.dimensions:
            return None
        if not all(isinstance(value, (int, float)) for value in raw):
            return None
        return [float(value) for value in raw]
