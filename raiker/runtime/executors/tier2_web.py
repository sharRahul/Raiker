from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.runtime.executors.base import ExecutionResult
from raiker.runtime.executors.sandbox import SandboxError, default_egress_allowlist, fetch_url

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction


class WebFetchExecutor:
    capability = "web_fetch"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        url = str(action.arguments.get("url", "")).strip()
        if not url:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:url",
                summary="Web fetch denied: no URL provided.",
            )
        max_bytes = int(action.arguments.get("max_bytes", 200_000))
        timeout = float(action.arguments.get("timeout", 15))
        try:
            result = fetch_url(
                url,
                egress_allowlist=default_egress_allowlist(),
                max_bytes=max_bytes,
                timeout=timeout,
            )
        except SandboxError as exc:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=str(exc),
                summary="Web fetch blocked by sandbox.",
            )
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary=f"Fetched {url} ({result['body_bytes']}b).",
            artifacts={
                "url": url,
                "body_bytes": result["body_bytes"],
                "truncated": result["truncated"],
            },
        )


class NetworkExecutor:
    capability = "network_execution"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        url = str(action.arguments.get("url", "")).strip()
        if not url:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:url",
                summary="Network execution denied: no URL provided.",
            )
        max_bytes = int(action.arguments.get("max_bytes", 200_000))
        timeout = float(action.arguments.get("timeout", 15))
        try:
            result = fetch_url(
                url,
                egress_allowlist=default_egress_allowlist(),
                max_bytes=max_bytes,
                timeout=timeout,
            )
        except SandboxError as exc:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=str(exc),
                summary="Network execution blocked by sandbox.",
            )
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary=f"Network request to {url} ({result['body_bytes']}b).",
            artifacts={
                "url": url,
                "body_bytes": result["body_bytes"],
                "truncated": result["truncated"],
            },
        )