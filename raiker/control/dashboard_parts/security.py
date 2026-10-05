# mypy: disable-error-code="misc"
"""Notifications, security findings and health, credential checks and capability
containment (GCR-43).

One part of :class:`raiker.control.dashboard.DashboardService`, which inherits it. Every method
is typed against the whole store (``self: DashboardService``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from raiker.control.dtos import ControlResult
from raiker.control.views.extensions import McpSessionView
from raiker.control.views.security import (
    BackupsView,
    BackupView,
    CapabilityContainmentView,
    ContainedSubject,
    NotificationDelivery,
    NotificationView,
    SecurityFindingView,
    SecurityHealthView,
)
from raiker.notify.approval_notifier import fire_os_notification
from raiker.notify.delivery_policy import (
    MUTABLE_CATEGORIES,
    QuietHours,
    instant,
    interrupts_enabled,
)
from raiker.security.credentials import CredentialLifecycle, CredentialLifecycleView
from raiker.security.monitoring import SecurityMonitor

if TYPE_CHECKING:
    from raiker.control.dashboard import DashboardService


class SecurityService:

    def list_mcp_findings(
        self: DashboardService, principal_id: str, server_id: str | None = None
    ) -> list[SecurityFindingView]:
        """Owner-scoped redacted findings, newest first, optionally scoped to one
        connection. Read-only view — never exposes a raw value."""
        return [
            SecurityFindingView(
                finding_id=str(row["finding_id"]),
                source=str(row.get("source", "")),
                severity=str(row.get("severity", "")),
                code=str(row.get("code", "")),
                summary=str(row.get("summary", "")),
                redacted_detail=dict(row.get("redacted_detail", {}) or {}),
                subject_id=row.get("subject_id"),
                state=str(row.get("state", "open")),
                created_at=str(row.get("created_at", "")),
            )
            for row in self.store.list_security_findings(
                principal_id, source="mcp_monitor", subject_id=server_id
            )
        ]

    def list_notifications(
        self: DashboardService, principal_id: str, unread_only: bool = False
    ) -> list[NotificationView]:
        """Owner-scoped notifications, newest first."""
        return [
            _notification_view(row)
            for row in self.store.list_notifications(principal_id, unread_only=unread_only)
        ]

    def notification_delivery(
        self: DashboardService, principal_id: str, *, now: datetime | None = None
    ) -> NotificationDelivery:
        """DEC-21a — the delivery policy as it stands now, and what it held."""
        moment = now or datetime.now(UTC)
        settings, zone = self.store.notification_settings(principal_id)
        quiet = QuietHours.from_settings(settings, zone)
        ends = quiet.ends_at(moment)
        starts = quiet.next_starts_at(moment)
        return {
            "quiet_hours": {
                "enabled": quiet.enabled,
                "start": quiet.start.strftime("%H:%M"),
                "end": quiet.end.strftime("%H:%M"),
                "timezone": quiet.timezone,
                "active": quiet.active(moment),
                "ends_at": instant(ends) if ends else None,
                "next_starts_at": instant(starts) if starts else None,
                "critical_in_app": quiet.critical_in_app,
                "critical_desktop": quiet.critical_desktop,
            },
            "decisions_interrupt": not quiet.active(moment),
            "categories": [
                {
                    "category": category,
                    "label": label,
                    "interrupts": interrupts_enabled(settings, category),
                }
                for category, label in MUTABLE_CATEGORIES.items()
            ],
            "held": [
                _notification_view(row)
                for row in self.store.held_notifications(principal_id, now=moment)
            ],
        }

    # ── Backups (DEC-24 step 5) ────────────────────────────────────────────

    def list_backups(self: DashboardService) -> BackupsView:
        from raiker.storage.backup import key_fingerprint, list_backups

        root = Path(self.store.paths.workspace_root)
        return {
            "backups": [cast(BackupView, record.to_dict()) for record in list_backups(root)],
            "key_fingerprint": key_fingerprint(root),
        }

    def create_backup(self: DashboardService, acting_principal_id: str | None) -> ControlResult:
        from raiker.storage.backup import BackupError, create_backup

        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        try:
            record = create_backup(
                self.store.connect(), Path(self.store.paths.workspace_root), reason="owner"
            )
        except BackupError as exc:
            return ControlResult(ok=False, reason_code=exc.reason, data={"detail": str(exc)})
        return ControlResult(ok=True, data=record.to_dict())

    def verify_backup(self: DashboardService, acting_principal_id: str | None, backup_id: str) -> ControlResult:
        from raiker.storage.backup import BackupError, verify_backup

        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        try:
            record = verify_backup(Path(self.store.paths.workspace_root), backup_id)
        except BackupError as exc:
            return ControlResult(ok=False, reason_code=exc.reason)
        return ControlResult(ok=True, data=record.to_dict())

    def restore_backup(self: DashboardService, acting_principal_id: str | None, backup_id: str) -> ControlResult:
        from raiker.storage.backup import BackupError, restore_backup

        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        try:
            restored = restore_backup(Path(self.store.paths.workspace_root), backup_id)
        except BackupError as exc:
            return ControlResult(ok=False, reason_code=exc.reason, data={"detail": str(exc)})
        return ControlResult(ok=True, data=dict(restored.__dict__))

    def delete_backup(self: DashboardService, acting_principal_id: str | None, backup_id: str) -> ControlResult:
        from raiker.storage.backup import BackupError, delete_backup

        if not self._is_human(acting_principal_id):
            return ControlResult(ok=False, reason_code="not_authorized_human")
        try:
            delete_backup(Path(self.store.paths.workspace_root), backup_id)
        except BackupError as exc:
            return ControlResult(ok=False, reason_code=exc.reason)
        return ControlResult(ok=True)

    def acknowledge_held_notifications(
        self: DashboardService, principal_id: str, notification_ids: list[str]
    ) -> int:
        return self.store.acknowledge_held_notifications(principal_id, notification_ids)

    def send_test_notice(self: DashboardService, principal_id: str) -> NotificationView:
        """DEC-21 — a notice written through exactly the path a real one takes.

        Same table, same policy, same OS command: a test that went around the
        policy would say alerts work during the quiet hours that hold them.
        """
        title = "Test notice"
        body = "This is the notice you asked for. Real notices are shown the same way."
        notification_id = self.store.insert_notification(
            principal_id=principal_id, kind="test_notice", title=title, body=body
        )
        fire_os_notification(title, body, store=self.store, notification_id=notification_id)
        row = next(
            row
            for row in self.store.list_notifications(principal_id, limit=50)
            if row["notification_id"] == notification_id
        )
        return _notification_view(row)

    def list_security_credentials(self: DashboardService, principal_id: str) -> list[CredentialLifecycleView]:
        return CredentialLifecycle(self.store).list(principal_id)

    def verify_security_credential(
        self: DashboardService, principal_id: str, provider: str
    ) -> CredentialLifecycleView:
        return CredentialLifecycle(self.store).verify_replacement(principal_id, provider)

    def scan_security(self: DashboardService, principal_id: str) -> list[SecurityFindingView]:
        SecurityMonitor(self.store, self.workspace_root).scan_configured_paths(principal_id)
        return self.list_security_findings(principal_id)

    def check_security_health(
        self: DashboardService, principal_id: str
    ) -> list[SecurityHealthView]:
        SecurityMonitor(self.store, self.workspace_root).check_vault_health(principal_id)
        return self.list_security_health(principal_id)

    def list_security_health(
        self: DashboardService, principal_id: str
    ) -> list[SecurityHealthView]:
        """Return the last recorded monitor state without performing a check."""
        return [
            {
                "source": str(row["source"]),
                "subject_id": str(row["subject_id"]),
                "code": str(row["code"]),
                "state": str(row["state"]),
                "finding_id": row.get("finding_id"),
                "updated_at": str(row["updated_at"]),
            }
            for row in self.store.list_security_monitor_state(principal_id)
        ]

    def check_password_breach(
        self: DashboardService, principal_id: str, password: str, *, enabled: bool
    ) -> list[SecurityFindingView]:
        SecurityMonitor(self.store, self.workspace_root).check_password_breach(
            principal_id, password, enabled=enabled
        )
        return self.list_security_findings(principal_id)

    def list_capability_containment(
        self: DashboardService, principal_id: str
    ) -> CapabilityContainmentView:
        """Every monitored capability's containment state, in one owner-facing shape.

        BUG-77 — monitored MCP connections keep their richer per-session view;
        this is the same three facts (state, reason, the control that clears
        it) for connectors, plugins, subagents, providers, tools and local
        execution, so nothing is contained without being visible.
        """
        from raiker.security.containment import (
            CAPABILITY_LABELS,
            CapabilityContainment,
        )

        views = CapabilityContainment(self.store).list(principal_id)
        return {
            "subjects": [view.to_dict() for view in views],
            "contained": sum(1 for view in views if view.contained),
            "capabilities": [
                {"id": capability, "label": label}
                for capability, label in sorted(CAPABILITY_LABELS.items())
            ],
        }

    def set_capability_containment(
        self: DashboardService, principal_id: str, capability: str, subject_id: str, action: str
    ) -> ContainedSubject:
        """Pause, stop or resume one monitored subject. Every state is revocable."""
        from raiker.security.containment import CAPABILITY_LABELS, CapabilityContainment

        if capability not in CAPABILITY_LABELS:
            raise ValueError(f"unknown_capability:{capability}")
        containment = CapabilityContainment(self.store)
        if action == "pause":
            view = containment.pause(
                principal_id,
                capability,
                subject_id,
                reason="Paused by you. It will not run until you resume it.",
            )
        elif action == "kill":
            view = containment.kill(principal_id, capability, subject_id)
        elif action == "resume":
            view = containment.resume(principal_id, capability, subject_id)
        else:
            raise ValueError(f"unknown_containment_action:{action}")
        return view.to_dict()

    def list_security_findings(self: DashboardService, principal_id: str) -> list[SecurityFindingView]:
        return [
            SecurityFindingView(
                finding_id=str(row["finding_id"]),
                source=str(row.get("source", "")),
                severity=str(row.get("severity", "")),
                code=str(row.get("code", "")),
                summary=str(row.get("summary", "")),
                redacted_detail=dict(row.get("redacted_detail", {}) or {}),
                subject_id=row.get("subject_id"),
                state=str(row.get("state", "open")),
                created_at=str(row.get("created_at", "")),
            )
            for row in self.store.list_security_findings(principal_id)
        ]

    def list_mcp_sessions(self: DashboardService, principal_id: str, server_id: str) -> list[McpSessionView]:
        """Owner-scoped, redacted recent monitor sessions for one MCP connection."""
        return [
            McpSessionView(
                session_row_id=str(row["session_row_id"]),
                server_id=str(row["server_id"]),
                transport=str(row["transport"]),
                operation=str(row["operation"]),
                hosts=tuple(str(host) for host in row.get("hosts", [])),
                tool_calls=int(row["tool_calls"]),
                bytes_in=int(row["bytes_in"]),
                bytes_out=int(row["bytes_out"]),
                error_count=int(row["error_count"]),
                outcome=str(row["outcome"]),
                started_at=str(row["started_at"]),
                ended_at=row.get("ended_at"),
            )
            for row in self.store.list_mcp_session_logs(server_id, principal_id, limit=10)
        ]

    def mark_notification_read(self: DashboardService, notification_id: str, principal_id: str) -> ControlResult:
        """Owner-scoped mark-as-read for one notification."""
        ok = self.store.mark_notification_read(notification_id, principal_id)
        return ControlResult(ok=ok, reason_code=None if ok else "unknown_notification")


def _notification_view(row: dict[str, Any]) -> NotificationView:
    return NotificationView(
        notification_id=str(row["notification_id"]),
        kind=str(row.get("kind", "")),
        title=str(row.get("title", "")),
        body=str(row.get("body", "")),
        finding_id=row.get("finding_id"),
        subject_id=row.get("subject_id"),
        read=bool(row.get("read", 0)),
        created_at=str(row.get("created_at", "")),
        in_app_presentation=row.get("in_app_presentation"),
        desktop_presentation=row.get("desktop_presentation"),
        quiet_until=row.get("quiet_until"),
        summarised_at=row.get("summarised_at"),
        repeat_count=int(row.get("repeat_count") or 0),
        last_repeated_at=row.get("last_repeated_at"),
    )
