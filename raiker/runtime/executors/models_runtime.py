from __future__ import annotations

import fnmatch
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from raiker.models.endpoint_policy import classify_endpoint, model_egress_allowlist
from raiker.runtime.executors.base import ExecutionResult
from raiker.runtime.executors.sandbox import SandboxError, get_url
from raiker.vector.backends import MAX_MEMORY_INDEX_BATCH

if TYPE_CHECKING:
    from raiker.models.contracts import EmbeddingResponse
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction
    from raiker.storage.sqlite import SQLiteStore

# Phase 4 slice 7: hosted / private-network model runtime.
#
# These executors govern the *connectivity* side of off-machine model access:
# a bounded, metadata-only reachability probe of an owner-allowlisted model
# endpoint. The chat path itself stays inside the model-provider factory,
# which (a) only allows hosted/private providers when the corresponding
# capability gate is enabled (see raiker/models/policy_state.py) and (b)
# re-enforces the same owner egress allowlist per provider construction.
# Credentials are injected from owner env vars by the factory only — never
# from action arguments, and never present in events or artifacts.

Prober = Callable[[str, frozenset[str]], dict]


def _default_prober(url: str, allowlist: frozenset[str]) -> dict:
    return get_url(url, egress_allowlist=allowlist, max_bytes=64_000, timeout=10.0)


class _ModelRuntimeExecutorBase:
    capability = ""
    expected_kind = ""
    require_https = False

    def __init__(self, workspace_root: str | Path, prober: Prober | None = None) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._prober = prober or _default_prober

    def _fail(self, action: GovernedAction, reason: str, summary: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action.action_id,
            reason_code=reason,
            summary=summary,
        )

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        operation = str(action.arguments.get("operation", "")).strip()
        if operation != "connectivity_check":
            return self._fail(
                action,
                f"unknown_operation:{operation or 'missing'}",
                "Model runtime denied: only 'connectivity_check' is supported.",
            )
        endpoint = str(action.arguments.get("endpoint", "")).strip()
        if not endpoint:
            return self._fail(
                action, "missing_argument:endpoint", "Model runtime denied: endpoint required."
            )
        kind = classify_endpoint(endpoint)
        if kind != self.expected_kind:
            return self._fail(
                action,
                f"endpoint_kind_not_allowed:{kind}",
                f"Model runtime denied: endpoint is not {self.expected_kind}.",
            )
        if self.require_https and urlparse(endpoint).scheme != "https":
            return self._fail(
                action,
                "hosted_https_required",
                "Model runtime denied: hosted endpoints require HTTPS.",
            )
        allowlist = model_egress_allowlist()
        if not allowlist:
            return self._fail(
                action,
                "model_egress_denied:no_allowlist",
                "Model runtime blocked: owner egress allowlist is empty (fail closed).",
            )
        host = urlparse(endpoint).netloc
        if not any(fnmatch.fnmatch(host, pattern) for pattern in allowlist):
            return self._fail(
                action,
                f"model_egress_denied:{host}",
                "Model runtime blocked: endpoint host is not on the owner egress allowlist.",
            )
        models_path = str(action.arguments.get("models_path", "/v1/models"))
        url = endpoint.rstrip("/") + "/" + models_path.lstrip("/")
        try:
            probe = self._prober(url, allowlist)
        except SandboxError as exc:
            return self._fail(action, str(exc), "Model runtime probe failed (egress/transport).")
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary="Model endpoint reachable (metadata-only probe).",
            # Metadata only — never the endpoint URL, host, response body, or credentials.
            artifacts={
                "endpoint_kind": kind,
                "status": probe.get("status"),
                "body_bytes": probe.get("body_bytes"),
            },
        )


class HostedModelRuntimeExecutor(_ModelRuntimeExecutorBase):
    """Real executor for ``hosted_model_runtime`` — allowlisted HTTPS reachability probe."""

    capability = "hosted_model_runtime"
    expected_kind = "remote_hosted"
    require_https = True


class PrivateNetworkModelRuntimeExecutor(_ModelRuntimeExecutorBase):
    """Real executor for ``private_network_model_runtime`` — allowlisted home-lab probe."""

    capability = "private_network_model_runtime"
    expected_kind = "private_network"
    require_https = False


# ── Provider-backed embedding (model_provider_runtime) ───────────────────────

# (provider, model, text) -> EmbeddingResponse. Injectable so tests exercise the
# governed persistence path without a live provider or credentials.
Embedder = Callable[[str, str, str], "EmbeddingResponse"]

_MAX_EMBED_TEXT_LEN = 20000
_PREVIEW_LEN = 120


class ModelProviderExecutor:
    """Real executor for ``model_provider_runtime`` — provider-backed semantic embedding.

    Complements ``vector_embedding_runtime`` (local, deterministic hashing): this
    path calls a real LLM provider's embedding endpoint and persists the returned
    **semantic** vector to the shared ``vector_records`` table. It is fail-closed
    and egress/provider-policy gated, in layers:

    - The owner egress allowlist ``RAIKER_MODEL_EGRESS_ALLOWLIST`` must be
      non-empty (checked here before any call).
    - The provider factory (reached via ``ModelRouter``) re-enforces the same
      allowlist per construction, plus the hosted/private gate state
      (``provider_runtime_policy_from_gates``) and API-key presence — credentials
      come **only** from owner env vars, never from action arguments.
    - Unsupported providers fail closed (``embeddings_unsupported``).

    ``operation: project_memory`` resolves an active, non-sensitive approved
    memory and records its projection mapping. Artifacts are metadata only
    (ids/model/dims/hash); source text and provider credentials never enter
    runtime events.
    """

    capability = "model_provider_runtime"

    def __init__(
        self, workspace_root: str | Path, store: SQLiteStore, embedder: Embedder | None = None
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store
        self._embedder = embedder

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        operation = str(action.arguments.get("operation", "embed")).strip()
        if operation not in {"embed", "embed_query", "project_memory", "index_memories"}:
            return self._fail(action.action_id, f"unknown_operation:{operation or 'missing'}")
        if operation == "index_memories":
            return self._index_memories(action, principal)

        memory_id: str | None = None
        owner = self._owner_scope(principal)
        if operation == "project_memory":
            memory_id = action.arguments.get("memory_id")
            if not isinstance(memory_id, str) or not memory_id:
                return self._fail(action.action_id, "missing_argument:memory_id")
            memory = self._store.get_active_approved_memory(memory_id, owner_principal_id=owner)
            if memory is None:
                return self._fail(action.action_id, "memory_not_active_or_not_found")
            if str(memory["sensitivity"]) in {"secret_like", "credential_like"}:
                return self._fail(action.action_id, "memory_sensitivity_not_projectable")
            text = str(memory["text"])
            scope = str(memory["scope"])
            sensitivity = str(memory["sensitivity"])
        else:
            raw_text = action.arguments.get("text")
            if not isinstance(raw_text, str) or not raw_text.strip():
                return self._fail(action.action_id, "missing_argument:text")
            text = raw_text
            scope = action.arguments.get("scope", "default")
            sensitivity = action.arguments.get("sensitivity", "public")
        if not text.strip():
            return self._fail(action.action_id, "missing_argument:text")
        if len(text) > _MAX_EMBED_TEXT_LEN:
            return self._fail(action.action_id, "text_too_long")
        provider = action.arguments.get("provider")
        model = action.arguments.get("model")
        if not isinstance(provider, str) or not provider.strip():
            return self._fail(action.action_id, "missing_argument:provider")
        if not isinstance(model, str) or not model.strip():
            return self._fail(action.action_id, "missing_argument:model")
        local_only = self._local_only_profile(provider, model)
        if not isinstance(scope, str) or not isinstance(sensitivity, str):
            return self._fail(action.action_id, "invalid_argument:scope_or_sensitivity")

        # A loopback-only profile performs no off-machine egress. Hosted and
        # private-network profiles still fail closed without an allowlist; a
        # local llama.cpp/Ollama embedding must not require a fictional remote
        # host merely to pass this executor's outer check.
        if not local_only and not model_egress_allowlist():
            return self._fail(action.action_id, "model_egress_denied:no_allowlist")

        embedder = self._embedder or self._default_embedder(principal.principal_id)
        try:
            response = embedder(provider, model, text)
        except SandboxError as exc:
            return self._fail(action.action_id, str(exc))
        except Exception as exc:  # noqa: BLE001 - map every failure to a fail-closed code
            return self._fail(action.action_id, self._provider_reason(exc))

        vector = getattr(response, "vector", None)
        if (
            not isinstance(vector, list)
            or not vector
            or not all(isinstance(v, (int, float)) for v in vector)
        ):
            return self._fail(action.action_id, "invalid_embedding_response")

        from raiker.contracts.ids import new_id, utc_now
        from raiker.contracts.models import VectorRecord
        from raiker.vector import VectorIndex

        provider_model = str(getattr(response, "model", "") or model)
        embedding_model = f"{provider}:{provider_model}"
        content_hash = VectorIndex.compute_content_hash(text)
        if operation == "embed_query":
            # MEM-10 read half. A search vector is useful only for this search:
            # persisting it would turn every question into a memory record, and
            # putting it in artifacts would copy a high-dimensional derivative
            # of owner text into the durable audit log. Return it only through
            # RuntimeAuthority's explicitly non-audited transient channel.
            return ExecutionResult(
                ok=True,
                capability=self.capability,
                action_id=action.action_id,
                summary="Semantic query embedding computed; query/vector not persisted.",
                artifacts={
                    "operation": "embed_query",
                    "embedding_model": embedding_model,
                    "dimensions": len(vector),
                    "content_hash": content_hash,
                    "provider_backed": not local_only,
                    "local_only": local_only,
                    "content_redacted": True,
                },
                transient={"embedding": [float(value) for value in vector]},
            )
        vector_id = new_id("vec_")
        self._store.insert_vector_record(
            VectorRecord(
                vector_id=vector_id,
                content_hash=content_hash,
                content_preview=text[:_PREVIEW_LEN],
                embedding_model=embedding_model,
                dimensions=len(vector),
                scope=scope,
                sensitivity=sensitivity,
                created_at=utc_now(),
                embedding=_dump_vector(vector),
                owner_principal_id=owner or "",
            )
        )
        if memory_id is not None:
            self._store.link_memory_projection(
                memory_id,
                "vector",
                vector_id,
                embedding_model,
                owner_principal_id=owner,
            )
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary="Provider embedding computed and stored locally; text/credentials not emitted.",
            artifacts={
                "vector_id": vector_id,
                "embedding_model": embedding_model,
                "dimensions": len(vector),
                "content_hash": content_hash,
                "provider_backed": not local_only,
                "local_only": local_only,
                "content_redacted": True,
                **({"memory_id": memory_id} if memory_id is not None else {}),
            },
        )

    def _index_memories(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        """MEM-10 - build a semantic recall space out of the memories that exist.

        ``project_memory`` embeds one named memory, which is the right shape for
        a turn and the wrong one for an owner: a workspace with two hundred
        approved memories and no semantic vectors cannot become searchable two
        hundred approvals at a time. This is the same work under **one** governed
        action - one gate read, one policy review, one approval, one audit
        record - with the eligible set resolved from the principal rather than
        from an argument, so the batch can never be pointed at another account.

        **The space is named for the model the owner chose**, not for whatever the
        provider echoes back. That is a deliberate departure from the single-shot
        ``project_memory`` path above, and it is what makes re-running cheap: the
        candidate filter and the stored label are then the same string, so a
        second run embeds only what has been approved since. A provider that
        answers ``text-embedding-3-small-v2`` to a request for
        ``text-embedding-3-small`` is describing its own routing, not a space the
        owner selected — and taking its word for it meant the filter looked for a
        label nothing was ever stored under, so every run re-embedded the whole
        corpus. The provider's own answer is kept in the artifacts, where it is
        evidence rather than an identity.
        """
        provider = action.arguments.get("provider")
        model = action.arguments.get("model")
        if not isinstance(provider, str) or not provider.strip():
            return self._fail(action.action_id, "missing_argument:provider")
        if not isinstance(model, str) or not model.strip():
            return self._fail(action.action_id, "missing_argument:model")
        local_only = self._local_only_profile(provider, model)
        try:
            limit = int(action.arguments.get("limit", MAX_MEMORY_INDEX_BATCH))
        except (TypeError, ValueError):
            return self._fail(action.action_id, "invalid_argument:limit")
        limit = max(1, min(limit, MAX_MEMORY_INDEX_BATCH))
        if not local_only and not model_egress_allowlist():
            return self._fail(action.action_id, "model_egress_denied:no_allowlist")

        owner = self._owner_scope(principal)
        if owner is None:
            return self._fail(action.action_id, "owner_scope_not_resolved")
        embedding_model = f"{provider}:{model}"
        pending = [
            str(row["memory_id"])
            for row in self._store.list_memories_missing_embedding(
                embedding_model, owner_principal_id=owner, limit=limit
            )
        ]
        pending_chunks = (
            self._store.list_managed_file_chunks_missing_embedding(
                embedding_model,
                owner_principal_id=owner,
                limit=max(0, limit - len(pending)),
            )
            if owner and len(pending) < limit
            else []
        )
        if not pending and not pending_chunks:
            return self._fail(action.action_id, "no_memories_to_index")

        embedder = self._embedder or self._default_embedder(principal.principal_id)
        provider_models: set[str] = set()
        indexed: list[str] = []
        indexed_chunks: list[str] = []
        failures: list[dict[str, str]] = []
        for memory_id in pending:
            memory = self._store.get_active_approved_memory(memory_id, owner_principal_id=owner)
            if memory is None:
                failures.append(
                    {"memory_id": memory_id, "reason_code": "memory_not_active_or_not_found"}
                )
                continue
            text = str(memory["text"])
            if not text.strip() or len(text) > _MAX_EMBED_TEXT_LEN:
                failures.append({"memory_id": memory_id, "reason_code": "text_not_embeddable"})
                continue
            try:
                response = embedder(provider, model, text)
            except SandboxError as exc:
                return self._batch_stop(
                    action.action_id, str(exc), indexed, failures, embedding_model
                )
            except Exception as exc:  # noqa: BLE001 - map every failure to a fail-closed code
                return self._batch_stop(
                    action.action_id,
                    self._provider_reason(exc),
                    indexed,
                    failures,
                    embedding_model,
                )
            vector = getattr(response, "vector", None)
            if (
                not isinstance(vector, list)
                or not vector
                or not all(isinstance(value, (int, float)) for value in vector)
            ):
                return self._batch_stop(
                    action.action_id,
                    "invalid_embedding_response",
                    indexed,
                    failures,
                    embedding_model,
                )
            self._store_memory_vector(
                memory_id=memory_id,
                text=text,
                scope=str(memory["scope"]),
                sensitivity=str(memory["sensitivity"]),
                embedding_model=embedding_model,
                response=response,
                owner=owner,
            )
            indexed.append(memory_id)
            answered = str(getattr(response, "model", "") or "")
            if answered:
                provider_models.add(answered)
        from raiker.memory.policy import MemorySensitivity, classify_memory_sensitivity

        for chunk in pending_chunks:
            chunk_id = str(chunk["chunk_id"])
            text = str(chunk["text"])
            sensitivity = classify_memory_sensitivity(text)
            if sensitivity in {
                MemorySensitivity.SECRET_LIKE,
                MemorySensitivity.CREDENTIAL_LIKE,
            }:
                failures.append(
                    {"chunk_id": chunk_id, "reason_code": "chunk_sensitivity_not_projectable"}
                )
                continue
            if not text.strip() or len(text) > _MAX_EMBED_TEXT_LEN:
                failures.append({"chunk_id": chunk_id, "reason_code": "text_not_embeddable"})
                continue
            try:
                response = embedder(provider, model, text)
            except SandboxError as exc:
                return self._batch_stop(
                    action.action_id,
                    str(exc),
                    [*indexed, *indexed_chunks],
                    failures,
                    embedding_model,
                )
            except Exception as exc:  # noqa: BLE001
                return self._batch_stop(
                    action.action_id,
                    self._provider_reason(exc),
                    [*indexed, *indexed_chunks],
                    failures,
                    embedding_model,
                )
            vector = getattr(response, "vector", None)
            if (
                not isinstance(vector, list)
                or not vector
                or not all(isinstance(value, (int, float)) for value in vector)
            ):
                return self._batch_stop(
                    action.action_id,
                    "invalid_embedding_response",
                    [*indexed, *indexed_chunks],
                    failures,
                    embedding_model,
                )
            if not self._store_file_chunk_vector(
                chunk=chunk,
                embedding_model=embedding_model,
                response=response,
                owner=owner,
            ):
                failures.append({"chunk_id": chunk_id, "reason_code": "chunk_revision_changed"})
                continue
            indexed_chunks.append(chunk_id)
            answered = str(getattr(response, "model", "") or "")
            if answered:
                provider_models.add(answered)
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary=(
                f"Embedded {len(indexed)} approved memories and {len(indexed_chunks)} "
                f"managed-file chunks into {embedding_model}; source text and provider "
                "credentials were not emitted."
            ),
            artifacts={
                "operation": "index_memories",
                "embedding_model": embedding_model,
                # What the provider called itself, kept as evidence. It is not
                # the space's identity; see the note on the method above.
                "provider_models": sorted(provider_models),
                "indexed_count": len(indexed),
                "indexed_file_chunk_count": len(indexed_chunks),
                "skipped_count": len(failures),
                "skipped": failures,
                "provider_backed": not local_only,
                "local_only": local_only,
                "content_redacted": True,
            },
        )

    def _batch_stop(
        self,
        action_id: str,
        reason_code: str,
        indexed: list[str],
        failures: list[dict[str, str]],
        embedding_model: str,
    ) -> ExecutionResult:
        """Stop the batch at the first provider refusal, and say what it had done.

        A partial batch is not rolled back: every vector already stored is a real
        vector in a named space, and deleting it would throw away paid-for work
        to make the record tidier. The counts travel with the refusal so the
        owner sees both halves.
        """
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action_id,
            reason_code=reason_code,
            summary="Model provider runtime failed closed part-way through the index.",
            artifacts={
                "operation": "index_memories",
                "embedding_model": embedding_model,
                "indexed_count": len(indexed),
                "skipped_count": len(failures),
                "skipped": failures,
            },
        )

    def _store_memory_vector(
        self,
        *,
        memory_id: str,
        text: str,
        scope: str,
        sensitivity: str,
        embedding_model: str,
        response: EmbeddingResponse,
        owner: str | None,
    ) -> None:
        from raiker.contracts.ids import new_id, utc_now
        from raiker.contracts.models import VectorRecord
        from raiker.vector import VectorIndex

        vector = list(getattr(response, "vector", []) or [])
        vector_id = new_id("vec_")
        self._store.insert_vector_record(
            VectorRecord(
                vector_id=vector_id,
                content_hash=VectorIndex.compute_content_hash(text),
                content_preview=text[:_PREVIEW_LEN],
                embedding_model=embedding_model,
                dimensions=len(vector),
                scope=scope,
                sensitivity=sensitivity,
                created_at=utc_now(),
                embedding=_dump_vector([float(value) for value in vector]),
                owner_principal_id=owner or "",
            )
        )
        self._store.link_memory_projection(
            memory_id, "vector", vector_id, embedding_model, owner_principal_id=owner
        )

    def _store_file_chunk_vector(
        self,
        *,
        chunk: dict[str, object],
        embedding_model: str,
        response: EmbeddingResponse,
        owner: str,
    ) -> bool:
        from raiker.contracts.ids import new_id, utc_now
        from raiker.contracts.models import VectorRecord
        from raiker.vector import VectorIndex

        text = str(chunk["text"])
        vector = [float(value) for value in list(getattr(response, "vector", []) or [])]
        vector_id = new_id("vec_")
        scope = (
            "knowledge:memory"
            if str(chunk["scope_kind"]) == "memory"
            else f"knowledge:project:{chunk.get('project_id') or ''}"
        )
        self._store.insert_vector_record(
            VectorRecord(
                vector_id=vector_id,
                content_hash=VectorIndex.compute_content_hash(text),
                content_preview=text[:_PREVIEW_LEN],
                embedding_model=embedding_model,
                dimensions=len(vector),
                scope=scope,
                sensitivity="normal",
                created_at=utc_now(),
                embedding=_dump_vector(vector),
                owner_principal_id=owner,
            )
        )
        linked = self._store.link_managed_file_chunk_vector(
            str(chunk["chunk_id"]),
            vector_id,
            embedding_model,
            str(chunk["content_hash"]),
            owner_principal_id=owner,
        )
        if not linked:
            self._store.delete_vector_record(vector_id, owner_principal_id=owner)
        return linked

    def _default_embedder(self, principal_id: str) -> Embedder:
        """The real provider call, usable from wherever the executor is invoked.

        ``asyncio.run`` raises inside a running event loop, and every route into
        this executor from the web API *is* inside one — so the only unmocked
        path here raised ``RuntimeError`` before it reached a provider and
        reported it as ``model_provider_error:RuntimeError``, which reads like a
        provider fault and is not one. :mod:`raiker.runtime.async_bridge`
        holds the one answer, so it is reused rather than solved twice.
        """

        def embed(provider: str, model: str, text: str) -> EmbeddingResponse:
            from raiker.models.connections import get_model_connection
            from raiker.models.policy_state import provider_runtime_policy_from_gates
            from raiker.models.registry import ModelProfileRegistry
            from raiker.models.router import ModelRouter
            from raiker.runtime.async_bridge import run_coro

            registry = ModelProfileRegistry.load()
            policy = provider_runtime_policy_from_gates(self._store, principal_id)
            router = ModelRouter(
                registry,
                runtime_policy=policy,
                # The owner's key lives in the connector vault, put there by the
                # Models page. Without this resolver the factory sees only the
                # process environment, so a key entered in the interface worked
                # for chat and failed here with `provider_api_key_missing` — the
                # same credential, reachable from one path and not the other.
                # Nothing is loosened: the vault is owner-scoped, the factory
                # still re-checks the egress allowlist and the gate state, and
                # the key never enters an action argument or an event.
                connection_resolver=lambda profile_id: get_model_connection(
                    self._store, principal_id, profile_id
                ),
            )
            response: EmbeddingResponse = run_coro(router.aembed(provider, model, text))
            return response

        return embed

    @staticmethod
    def _local_only_profile(provider: str, model: str) -> bool:
        """Resolve locality from the shipped profile, never from its label.

        An injected test embedder still follows the same profile contract. An
        unknown pair returns ``False`` so it can never acquire the local
        allowlist exemption by choosing a local-looking name.
        """
        from raiker.models.registry import ModelProfileRegistry, RegistryError

        try:
            profile = ModelProfileRegistry.load().resolve(provider, model)
        except (RegistryError, OSError, ValueError):
            return False
        return bool(profile.local_only) and not bool(profile.requires_network)

    def _owner_scope(self, principal: Principal) -> str | None:
        """The durable owner id used by both memory rows and their vectors."""
        resolved = self._store.account_scope(principal.principal_id)
        if resolved is not None:
            return resolved
        # A bootstrapped local owner is a human principal but predates a full
        # account-credential row. Memory writes scope to that principal id; the
        # projection must use the same id or owner-scoped recall cannot join it.
        if str(principal.principal_type) == "human":
            return principal.principal_id
        return None

    @staticmethod
    def _provider_reason(exc: Exception) -> str:
        from raiker.models.exceptions import ModelProviderError
        from raiker.models.registry import RegistryError

        if isinstance(exc, RegistryError):
            return "model_profile_not_found"
        if isinstance(exc, ModelProviderError):
            # ModelProviderError messages are a fixed, credential-free vocabulary
            # (e.g. hosted_api_key_missing, embeddings_unsupported, policy codes).
            return f"model_provider_denied:{exc}"
        return f"model_provider_error:{type(exc).__name__}"

    def _fail(self, action_id: str, reason_code: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action_id,
            reason_code=reason_code,
            summary="Model provider runtime failed closed.",
            artifacts={},
        )


def _dump_vector(vector: list[float]) -> str:
    import json

    return json.dumps([float(v) for v in vector])


# ── Advisor model (advisor_model_runtime) ─────────────────────────────────────


class AdvisorModelRuntimeExecutor:
    """Real executor for ``advisor_model_runtime`` — one governed advisor consult.

    Reached only through ``route_action``, which already applied the capability
    gate, the per-capability decision mode (default ``ask``), and the approval
    flow — so this executor skips the mode layer and enforces everything else
    fail-closed via :class:`raiker.runtime.advisor.AdvisorService`: a configured
    non-test advisor profile with a concrete model, a bounded question, and
    provider policy (hosted/private gate + owner egress allowlist + env-only
    API key) re-checked per call by the provider factory.

    Artifacts are **metadata only** — profile id, provider, model, and
    question/answer lengths. The question and answer text never enter runtime
    events; the chat path (the brokered ``consult_advisor`` tool) is where the
    answer actually flows back to the calling model.
    """

    capability = "advisor_model_runtime"

    def __init__(
        self,
        workspace_root: str | Path,
        store: SQLiteStore,
        consult_fn: Callable[[str, str, str], str] | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store
        self._consult_fn = consult_fn

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        from raiker.runtime.advisor import AdvisorService

        operation = str(action.arguments.get("operation", "consult")).strip()
        if operation != "consult":
            return self._fail(action.action_id, f"unknown_operation:{operation or 'missing'}")
        question = action.arguments.get("question")
        if not isinstance(question, str) or not question.strip():
            return self._fail(action.action_id, "missing_argument:question")

        service = AdvisorService(
            self._workspace_root,
            self._store,
            consult_fn=self._consult_fn,
            principal_id=principal.principal_id if principal is not None else None,
        )
        outcome = service.consult(question, enforce_modes=False)
        if outcome.get("status") != "success":
            error = outcome.get("error", {})
            return self._fail(action.action_id, str(error.get("type", "advisor_failed")))
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary="Advisor consulted; answer withheld from artifacts (metadata only).",
            artifacts={
                "advisor_profile_id": outcome.get("advisor_profile_id"),
                "provider": outcome.get("provider"),
                "model": outcome.get("model"),
                "question_length": len(question),
                "answer_length": outcome.get("answer_length"),
                "content_redacted": True,
            },
        )

    def _fail(self, action_id: str, reason_code: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action_id,
            reason_code=reason_code,
            summary="Advisor model runtime failed closed.",
            artifacts={},
        )
