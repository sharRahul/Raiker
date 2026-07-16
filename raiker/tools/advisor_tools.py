from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


def consult_advisor(
    workspace_root: str | Path,
    question: str,
    *,
    store: SQLiteStore | None = None,
    principal_id: str | None = None,
) -> dict[str, Any]:
    """Governed advisor consult, brokered as the ``consult_advisor`` tool.

    Lets a (typically local) model ask the owner-configured advisor model one
    bounded question. Everything is enforced inside :class:`AdvisorService`:
    the ``advisor_model_runtime`` gate (fail closed), the decision mode
    (default ``ask`` withholds), the configured advisor profile, and provider
    policy (hosted/private gate + egress allowlist + env-only key) at call
    time. The answer comes back as an untrusted-data block; broker events are
    scrubbed to metadata (see ``ToolBroker._METADATA_ONLY_TOOLS``).
    """
    # Imported at call time: the runtime.authority package (pulled in by the
    # advisor's decision-mode layer) transitively imports the ToolBroker, so a
    # module-level import here would be circular.
    from raiker.runtime.advisor import AdvisorService
    from raiker.storage.sqlite import SQLiteStore

    service = AdvisorService(
        workspace_root, store or SQLiteStore(workspace_root), principal_id=principal_id
    )
    return service.consult(question)
