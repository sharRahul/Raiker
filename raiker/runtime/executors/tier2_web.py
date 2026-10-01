"""The capability-level web read, routed through the one web implementation.

BUG-232: one implementation of "reach the network". Two that do not enforce
the same controls — HTTPS, the public-address check, pinning, checked
redirects — are one call site away from making Raiker's central claim false, so
this executor delegates to the same
:class:`~raiker.runtime.web_access.WebAccessService` the broker uses. The decision
modes are not re-run here because :class:`~raiker.runtime.authority.router.
RuntimeAuthority` already made that decision before an executor is reached; the
blocklist and the non-editable address guard are inside ``fetch()`` itself and
run on every call regardless.

There is no second capability for this read: a second name with a weaker
guard and no caller is a gate that changes nothing, which is worse than none.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from raiker.runtime.authority.routed import current_routed_authority
from raiker.runtime.executors.base import ExecutionResult

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction
    from raiker.storage.sqlite import SQLiteStore


class WebFetchExecutor:
    capability = "web_fetch"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        url = str(action.arguments.get("url", "")).strip()
        if not url:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:url",
                summary="Web fetch denied: no URL provided.",
            )
        from raiker.runtime.web_access import WebAccessService

        service = WebAccessService(
            self._workspace_root, self._store, principal_id=principal.principal_id
        )
        result = service.fetch(url, authority=current_routed_authority(action.action_id))
        if result.get("status") != "success":
            error = result.get("error") or {}
            reason = str(error.get("type") or "web_fetch_failed")
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=reason,
                summary=str(error.get("message") or "Web fetch failed closed."),
            )
        length = int(result.get("content_length", 0))
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary=f"Fetched {url} ({length} chars).",
            artifacts={
                "url": url,
                "final_url": result.get("final_url", url),
                "content_length": length,
                "truncated": bool(result.get("content_truncated")),
                "untrusted": True,
            },
        )
