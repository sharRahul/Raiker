from __future__ import annotations

import fnmatch
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from raiker.models.endpoint_policy import classify_endpoint, model_egress_allowlist
from raiker.runtime.executors.base import ExecutionResult
from raiker.runtime.executors.sandbox import SandboxError, fetch_url

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
    return fetch_url(url, egress_allowlist=allowlist, max_bytes=64_000, timeout=10.0)


class _ModelRuntimeExecutorBase:
    capability = ""
    expected_kind = ""
    require_https = False

    def __init__(self, workspace_root: str | Path, prober: Prober | None = None) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._prober = prober or _default_prober

    def _fail(self, action: GovernedAction, reason: str, summary: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False, capability=self.capability, action_id=action.action_id,
            reason_code=reason, summary=summary,
        )

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        operation = str(action.arguments.get("operation", "")).strip()
        if operation != "connectivity_check":
            return self._fail(action, f"unknown_operation:{operation or 'missing'}",
                              "Model runtime denied: only 'connectivity_check' is supported.")
        endpoint = str(action.arguments.get("endpoint", "")).strip()
        if not endpoint:
            return self._fail(action, "missing_argument:endpoint",
                              "Model runtime denied: endpoint required.")
        kind = classify_endpoint(endpoint)
        if kind != self.expected_kind:
            return self._fail(action, f"endpoint_kind_not_allowed:{kind}",
                              f"Model runtime denied: endpoint is not {self.expected_kind}.")
        if self.require_https and urlparse(endpoint).scheme != "https":
            return self._fail(action, "hosted_https_required",
                              "Model runtime denied: hosted endpoints require HTTPS.")
        allowlist = model_egress_allowlist()
        if not allowlist:
            return self._fail(action, "model_egress_denied:no_allowlist",
                              "Model runtime blocked: owner egress allowlist is empty (fail closed).")
        host = urlparse(endpoint).netloc
        if not any(fnmatch.fnmatch(host, pattern) for pattern in allowlist):
            return self._fail(action, f"model_egress_denied:{host}",
                              "Model runtime blocked: endpoint host is not on the owner egress allowlist.")
        models_path = str(action.arguments.get("models_path", "/v1/models"))
        url = endpoint.rstrip("/") + "/" + models_path.lstrip("/")
        try:
            probe = self._prober(url, allowlist)
        except SandboxError as exc:
            return self._fail(action, str(exc), "Model runtime probe failed (egress/transport).")
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
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

    Only ``operation: embed`` is supported in this slice. Artifacts are metadata
    only (ids/model/dims/hash); the source text and provider credentials never
    enter runtime events.
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
        if operation != "embed":
            return self._fail(action.action_id, f"unknown_operation:{operation or 'missing'}")

        text = action.arguments.get("text")
        if not isinstance(text, str) or not text.strip():
            return self._fail(action.action_id, "missing_argument:text")
        if len(text) > _MAX_EMBED_TEXT_LEN:
            return self._fail(action.action_id, "text_too_long")
        provider = action.arguments.get("provider")
        model = action.arguments.get("model")
        if not isinstance(provider, str) or not provider.strip():
            return self._fail(action.action_id, "missing_argument:provider")
        if not isinstance(model, str) or not model.strip():
            return self._fail(action.action_id, "missing_argument:model")
        scope = action.arguments.get("scope", "default")
        sensitivity = action.arguments.get("sensitivity", "public")
        if not isinstance(scope, str) or not isinstance(sensitivity, str):
            return self._fail(action.action_id, "invalid_argument:scope_or_sensitivity")

        # Owner egress allowlist must be configured (empty = fail closed).
        if not model_egress_allowlist():
            return self._fail(action.action_id, "model_egress_denied:no_allowlist")

        embedder = self._embedder or self._default_embedder()
        try:
            response = embedder(provider, model, text)
        except SandboxError as exc:
            return self._fail(action.action_id, str(exc))
        except Exception as exc:  # noqa: BLE001 - map every failure to a fail-closed code
            return self._fail(action.action_id, self._provider_reason(exc))

        vector = getattr(response, "vector", None)
        if not isinstance(vector, list) or not vector or not all(
            isinstance(v, (int, float)) for v in vector
        ):
            return self._fail(action.action_id, "invalid_embedding_response")

        from raiker.contracts.ids import new_id, utc_now
        from raiker.contracts.models import VectorRecord
        from raiker.vector import VectorIndex

        provider_model = str(getattr(response, "model", "") or model)
        embedding_model = f"{provider}:{provider_model}"
        content_hash = VectorIndex.compute_content_hash(text)
        vector_id = new_id("vec_")
        self._store.insert_vector_record(VectorRecord(
            vector_id=vector_id,
            content_hash=content_hash,
            content_preview=text[:_PREVIEW_LEN],
            embedding_model=embedding_model,
            dimensions=len(vector),
            scope=scope,
            sensitivity=sensitivity,
            created_at=utc_now(),
            embedding=_dump_vector(vector),
        ))
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
                "provider_backed": True,
                "content_redacted": True,
            },
        )

    def _default_embedder(self) -> Embedder:
        def embed(provider: str, model: str, text: str) -> EmbeddingResponse:
            import asyncio

            from raiker.models.policy_state import provider_runtime_policy_from_gates
            from raiker.models.registry import ModelProfileRegistry
            from raiker.models.router import ModelRouter

            registry = ModelProfileRegistry.load(self._workspace_root)
            policy = provider_runtime_policy_from_gates(self._store)
            router = ModelRouter(registry, runtime_policy=policy)
            return asyncio.run(router.aembed(provider, model, text))

        return embed

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
