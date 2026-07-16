from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


def github_read(
    workspace_root: str | Path,
    resource: str,
    repo: str,
    number: Any,
    *,
    store: SQLiteStore | None = None,
    principal_id: str | None = None,
) -> dict[str, Any]:
    """Governed GitHub issue/PR read, brokered as the ``github_read`` tool.

    Lets a model read one GitHub issue or pull request. Everything is enforced
    inside :class:`GithubConnectorService`: the ``connector_github_runtime``
    gate (fail closed), the decision mode (default ``ask`` withholds), the owner
    credential (``RAIKER_GITHUB_TOKEN``, env only), and the owner egress
    allowlist (``api.github.com``). The fetched content comes back as an
    untrusted-data block; broker events are scrubbed to metadata (see
    ``ToolBroker._METADATA_ONLY_TOOLS``).
    """
    # Imported at call time: the runtime.authority package (pulled in by the
    # connector's decision-mode layer) transitively imports the ToolBroker, so a
    # module-level import here would be circular.
    from raiker.runtime.connectors import GithubConnectorService
    from raiker.storage.sqlite import SQLiteStore

    service = GithubConnectorService(
        workspace_root, store or SQLiteStore(workspace_root), principal_id=principal_id
    )
    return service.read(resource, repo, number)


def gmail_read(
    workspace_root: str | Path,
    resource: str,
    message_id: str,
    *,
    store: SQLiteStore | None = None,
    principal_id: str | None = None,
) -> dict[str, Any]:
    """Governed Gmail message/thread read, brokered as the ``gmail_read`` tool.

    Lets a model read one Gmail message or thread. Everything is enforced inside
    :class:`GmailConnectorService`: the ``connector_gmail_runtime`` gate (fail
    closed), the decision mode (default ``ask`` withholds), the owner credential
    (``RAIKER_GMAIL_TOKEN``, env only), and the owner egress allowlist
    (``gmail.googleapis.com``). The fetched content comes back as an
    untrusted-data block; broker events drop the content (see
    ``ToolBroker._CONTENT_RESULT_TOOLS``).
    """
    from raiker.runtime.connectors import GmailConnectorService
    from raiker.storage.sqlite import SQLiteStore

    service = GmailConnectorService(
        workspace_root, store or SQLiteStore(workspace_root), principal_id=principal_id
    )
    return service.read(resource, message_id)


def gcal_read(
    workspace_root: str | Path,
    resource: str,
    calendar_id: str,
    event_id: str = "",
    *,
    store: SQLiteStore | None = None,
    principal_id: str | None = None,
) -> dict[str, Any]:
    """Governed Google Calendar event/calendar read, brokered as ``gcal_read``.

    Everything is enforced inside :class:`GcalConnectorService`: the
    ``connector_gcal_runtime`` gate (fail closed), the decision mode (default
    ``ask`` withholds), the owner credential (``RAIKER_GCAL_TOKEN``, env only),
    and the owner egress allowlist (``www.googleapis.com``). The fetched content
    comes back as an untrusted-data block; broker events drop the content.
    """
    from raiker.runtime.connectors import GcalConnectorService
    from raiker.storage.sqlite import SQLiteStore

    service = GcalConnectorService(
        workspace_root, store or SQLiteStore(workspace_root), principal_id=principal_id
    )
    return service.read(resource, calendar_id, event_id)


def slack_read(
    workspace_root: str | Path,
    resource: str,
    channel: str,
    *,
    store: SQLiteStore | None = None,
    principal_id: str | None = None,
) -> dict[str, Any]:
    """Governed Slack channel info/history read, brokered as ``slack_read``.

    Everything is enforced inside :class:`SlackConnectorService`: the
    ``connector_slack_runtime`` gate (fail closed), the decision mode (default
    ``ask`` withholds), the owner credential (``RAIKER_SLACK_TOKEN``, env only),
    and the owner egress allowlist (``slack.com``). The fetched content comes
    back as an untrusted-data block; broker events drop the content.
    """
    from raiker.runtime.connectors import SlackConnectorService
    from raiker.storage.sqlite import SQLiteStore

    service = SlackConnectorService(
        workspace_root, store or SQLiteStore(workspace_root), principal_id=principal_id
    )
    return service.read(resource, channel)


def connector_read(
    workspace_root: str | Path,
    principal_id: str,
    connector_id: str,
    operation_id: str,
    arguments: dict[str, Any] | None = None,
    *,
    store: SQLiteStore | None = None,
) -> dict[str, Any]:
    """Invoke one manifest-declared GET operation for the authenticated principal."""
    from raiker.runtime.connector_ecosystem import ConnectorInvoker
    from raiker.storage.sqlite import SQLiteStore

    service = ConnectorInvoker(store or SQLiteStore(workspace_root))
    return service.invoke_read_sync(
        principal_id, connector_id, operation_id, arguments or {}
    )
