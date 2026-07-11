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

    service = GithubConnectorService(workspace_root, store or SQLiteStore(workspace_root))
    return service.read(resource, repo, number)


def gmail_read(
    workspace_root: str | Path,
    resource: str,
    message_id: str,
    *,
    store: SQLiteStore | None = None,
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

    service = GmailConnectorService(workspace_root, store or SQLiteStore(workspace_root))
    return service.read(resource, message_id)
