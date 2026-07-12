from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.runtime.executors.base import ExecutionResult

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction
    from raiker.storage.sqlite import SQLiteStore


class GithubConnectorExecutor:
    """Real executor for ``connector_github_runtime`` — one governed GitHub read.

    Reached only through ``route_action``, which already applied the capability
    gate, the per-capability decision mode (default ``ask``), and the approval
    flow — so this executor skips the mode layer and enforces everything else
    fail-closed via :class:`raiker.runtime.connectors.GithubConnectorService`:
    the owner credential (``RAIKER_GITHUB_TOKEN``, env only), the owner egress
    allowlist (``api.github.com``), and validated request components.

    Artifacts are **metadata only** — resource, repo, number, title, state, and
    content length. The fetched issue/PR body never enters runtime events; the
    chat path (the brokered ``github_read`` tool) is where the content flows
    back to the calling model as untrusted data.
    """

    capability = "connector_github_runtime"

    def __init__(
        self,
        workspace_root: str | Path,
        store: SQLiteStore,
        fetch_fn: Any | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store
        self._fetch_fn = fetch_fn

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        from raiker.runtime.connectors import GithubConnectorService

        operation = str(action.arguments.get("operation", "read")).strip()
        if operation != "read":
            return self._fail(action.action_id, f"unknown_operation:{operation or 'missing'}")

        service = GithubConnectorService(
            self._workspace_root, self._store, fetch_fn=self._fetch_fn
        )
        outcome = service.read(
            str(action.arguments.get("resource", "")),
            str(action.arguments.get("repo", "")),
            action.arguments.get("number"),
            enforce_modes=False,
        )
        if outcome.get("status") != "success":
            error = outcome.get("error", {})
            return self._fail(action.action_id, str(error.get("type", "connector_failed")))
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary="GitHub read completed; content withheld from artifacts (metadata only).",
            artifacts={
                "resource": outcome.get("resource"),
                "repo": outcome.get("repo"),
                "number": outcome.get("number"),
                "title": outcome.get("title"),
                "state": outcome.get("state"),
                "content_length": outcome.get("content_length"),
                "content_redacted": True,
            },
        )

    def _fail(self, action_id: str, reason_code: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action_id,
            reason_code=reason_code,
            summary="GitHub connector runtime failed closed.",
            artifacts={},
        )


class GmailConnectorExecutor:
    """Real executor for ``connector_gmail_runtime`` — one governed Gmail read.

    Reached only through ``route_action``, which already applied the capability
    gate, the per-capability decision mode (default ``ask``), and the approval
    flow — so this executor skips the mode layer and enforces everything else
    fail-closed via :class:`raiker.runtime.connectors.GmailConnectorService`:
    the owner credential (``RAIKER_GMAIL_TOKEN``, env only), the owner egress
    allowlist (``gmail.googleapis.com``), and validated request components.

    Artifacts are **metadata only** — resource, message id, subject, and content
    length. The fetched message/thread body never enters runtime events; the
    chat path (the brokered ``gmail_read`` tool) is where the content flows back
    to the calling model as untrusted data.
    """

    capability = "connector_gmail_runtime"

    def __init__(
        self,
        workspace_root: str | Path,
        store: SQLiteStore,
        fetch_fn: Any | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store
        self._fetch_fn = fetch_fn

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        from raiker.runtime.connectors import GmailConnectorService

        operation = str(action.arguments.get("operation", "read")).strip()
        if operation != "read":
            return self._fail(action.action_id, f"unknown_operation:{operation or 'missing'}")

        service = GmailConnectorService(
            self._workspace_root, self._store, fetch_fn=self._fetch_fn
        )
        outcome = service.read(
            str(action.arguments.get("resource", "")),
            str(action.arguments.get("message_id", "")),
            enforce_modes=False,
        )
        if outcome.get("status") != "success":
            error = outcome.get("error", {})
            return self._fail(action.action_id, str(error.get("type", "connector_failed")))
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary="Gmail read completed; content withheld from artifacts (metadata only).",
            artifacts={
                "resource": outcome.get("resource"),
                "message_id": outcome.get("message_id"),
                "subject": outcome.get("subject"),
                "content_length": outcome.get("content_length"),
                "content_redacted": True,
            },
        )

    def _fail(self, action_id: str, reason_code: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action_id,
            reason_code=reason_code,
            summary="Gmail connector runtime failed closed.",
            artifacts={},
        )


class GcalConnectorExecutor:
    """Real executor for ``connector_gcal_runtime`` — one governed Calendar read.

    Reached only through ``route_action`` (gate + decision mode + approval flow
    already applied), so this executor skips the mode layer and enforces
    everything else fail-closed via
    :class:`raiker.runtime.connectors.GcalConnectorService`. Artifacts are
    **metadata only** — resource, calendar id, event id, title, and content
    length; the fetched event/calendar body never enters runtime events.
    """

    capability = "connector_gcal_runtime"

    def __init__(
        self,
        workspace_root: str | Path,
        store: SQLiteStore,
        fetch_fn: Any | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store
        self._fetch_fn = fetch_fn

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        from raiker.runtime.connectors import GcalConnectorService

        operation = str(action.arguments.get("operation", "read")).strip()
        if operation != "read":
            return self._fail(action.action_id, f"unknown_operation:{operation or 'missing'}")

        service = GcalConnectorService(self._workspace_root, self._store, fetch_fn=self._fetch_fn)
        outcome = service.read(
            str(action.arguments.get("resource", "")),
            str(action.arguments.get("calendar_id", "")),
            str(action.arguments.get("event_id", "")),
            enforce_modes=False,
        )
        if outcome.get("status") != "success":
            error = outcome.get("error", {})
            return self._fail(action.action_id, str(error.get("type", "connector_failed")))
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary="Calendar read completed; content withheld from artifacts (metadata only).",
            artifacts={
                "resource": outcome.get("resource"),
                "calendar_id": outcome.get("calendar_id"),
                "event_id": outcome.get("event_id"),
                "title": outcome.get("title"),
                "content_length": outcome.get("content_length"),
                "content_redacted": True,
            },
        )

    def _fail(self, action_id: str, reason_code: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action_id,
            reason_code=reason_code,
            summary="Calendar connector runtime failed closed.",
            artifacts={},
        )


class SlackConnectorExecutor:
    """Real executor for ``connector_slack_runtime`` — one governed Slack read.

    Reached only through ``route_action`` (gate + decision mode + approval flow
    already applied), so this executor skips the mode layer and enforces
    everything else fail-closed via
    :class:`raiker.runtime.connectors.SlackConnectorService`. Artifacts are
    **metadata only** — resource, channel, title, and content length; the fetched
    channel info/history never enters runtime events.
    """

    capability = "connector_slack_runtime"

    def __init__(
        self,
        workspace_root: str | Path,
        store: SQLiteStore,
        fetch_fn: Any | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store
        self._fetch_fn = fetch_fn

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        from raiker.runtime.connectors import SlackConnectorService

        operation = str(action.arguments.get("operation", "read")).strip()
        if operation != "read":
            return self._fail(action.action_id, f"unknown_operation:{operation or 'missing'}")

        service = SlackConnectorService(self._workspace_root, self._store, fetch_fn=self._fetch_fn)
        outcome = service.read(
            str(action.arguments.get("resource", "")),
            str(action.arguments.get("channel", "")),
            enforce_modes=False,
        )
        if outcome.get("status") != "success":
            error = outcome.get("error", {})
            return self._fail(action.action_id, str(error.get("type", "connector_failed")))
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary="Slack read completed; content withheld from artifacts (metadata only).",
            artifacts={
                "resource": outcome.get("resource"),
                "channel": outcome.get("channel"),
                "title": outcome.get("title"),
                "content_length": outcome.get("content_length"),
                "content_redacted": True,
            },
        )

    def _fail(self, action_id: str, reason_code: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action_id,
            reason_code=reason_code,
            summary="Slack connector runtime failed closed.",
            artifacts={},
        )
