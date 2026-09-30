"""The read service behind every page the web UI serves.

GCR-43 / OPT-08. ``DashboardService`` is one class assembled from one part per
domain in ``raiker/control/dashboard_parts/``; the read models it returns live
in ``raiker/control/views/``, one module per domain, and the startup migration
of legacy project folders in ``raiker/control/project_migration.py``. This
module is only the composition root.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from raiker.control.dashboard_parts.approvals import ApprovalService
from raiker.control.dashboard_parts.code import CodeService
from raiker.control.dashboard_parts.execution import ExecutionService
from raiker.control.dashboard_parts.extensions import ExtensionService
from raiker.control.dashboard_parts.knowledge import KnowledgeService
from raiker.control.dashboard_parts.memory import MemoryService
from raiker.control.dashboard_parts.models import ModelService
from raiker.control.dashboard_parts.projects import ProjectService
from raiker.control.dashboard_parts.security import SecurityService
from raiker.control.dashboard_parts.sessions import SessionService
from raiker.control.dashboard_parts.tasks import TaskService
from raiker.control.project_migration import migrate_project_roots
from raiker.control.service import RuntimeControlService
from raiker.runtime.authority.models import PrincipalType
from raiker.storage.sqlite import SQLiteStore


class DashboardService(
    ApprovalService,
    CodeService,
    ExecutionService,
    ExtensionService,
    KnowledgeService,
    MemoryService,
    ModelService,
    ProjectService,
    SecurityService,
    SessionService,
    TaskService,
):
    """Read-only governed views for the web UI. Reuses storage and control services; never mutates."""

    def __init__(self, workspace_root: str | Path = ".") -> None:
        self.workspace_root = Path(workspace_root)
        self.store = SQLiteStore(self.workspace_root)
        self.project_root_migration_report = migrate_project_roots(self.workspace_root, self.store)
        self.control = RuntimeControlService(self.workspace_root)

    def _is_human(self, acting_principal_id: str | None) -> bool:
        principal = self.control._resolve_or_none(acting_principal_id)  # noqa: SLF001
        return principal is not None and principal.principal_type == PrincipalType.HUMAN

    @staticmethod
    def _age_seconds(created_at: str) -> int | None:
        try:
            then = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

        delta = datetime.now(UTC) - then
        return max(0, int(delta.total_seconds()))


__all__ = ["DashboardService"]
