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
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction

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
