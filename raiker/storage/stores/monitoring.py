# mypy: disable-error-code="misc"
"""Notifications, security findings, monitoring state, capability containment and
background worker health (GCR-11).

One part of :class:`raiker.storage.sqlite.SQLiteStore`, which inherits it. Every method
is typed against the whole store (``self: SQLiteStore``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

from raiker.contracts.ids import new_id, utc_now

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

#: DEC-24 step 1 — how long a background pass may go unrecorded before it reads
#: as stale. The host tick records every fifteen seconds and the attached-folder
#: watcher at most every two minutes when it is backing off, so five minutes is
#: several missed cycles of the slowest, never one slow pass.
BACKGROUND_PASS_STALE_SECONDS = 300


def _older_than(stamp: str, now: datetime, seconds: int) -> bool:
    """Whether ISO ``stamp`` is more than ``seconds`` before ``now``; unreadable is old."""
    try:
        recorded = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return True
    if recorded.tzinfo is None:
        recorded = recorded.replace(tzinfo=UTC)
    return (now - recorded).total_seconds() > seconds


class MonitoringStore:

    def set_mcp_monitor_state(
        self: SQLiteStore,
        server_id: str,
        principal_id: str,
        monitor_state: str,
        *,
        paused_reason: str | None = None,
        paused_at: str | None = None,
    ) -> bool:
        """Owner-scoped transition of a connection's monitoring/lifecycle state
        (``active`` | ``paused`` | ``killed``). Returns False if the row is
        missing or owned by another principal (isolation), so a containment
        write can never touch another owner's connection. ``paused_reason`` /
        ``paused_at`` are redacted metadata (a rule code + summary, a timestamp)
        — never a payload."""
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE mcp_servers
                   SET monitor_state = ?, paused_reason = ?, paused_at = ?
                   WHERE server_id = ? AND principal_id = ?""",
                (monitor_state, paused_reason, paused_at, server_id, principal_id),
            )
            return cursor.rowcount > 0

    @staticmethod
    def _security_finding_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        raw = data.get("redacted_detail_json")
        try:
            data["redacted_detail"] = json.loads(raw) if isinstance(raw, str) else {}
        except (TypeError, ValueError):
            data["redacted_detail"] = {}
        return data

    def insert_security_finding(
        self: SQLiteStore,
        *,
        principal_id: str,
        source: str,
        severity: str,
        code: str,
        summary: str,
        redacted_detail: dict[str, Any] | None = None,
        subject_id: str | None = None,
        state: str = "open",
    ) -> str:
        """Persist one redacted finding. ``redacted_detail`` must already contain
        redacted metadata only (labels/counts/hostnames) — never a raw value.
        Owner-scoped by ``principal_id``; shared substrate across monitors."""
        finding_id = new_id("find_")
        self._execute(
            """INSERT INTO security_findings
               (finding_id, principal_id, source, severity, code, summary,
                redacted_detail_json, subject_id, state, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                finding_id,
                principal_id,
                source,
                severity,
                code,
                summary,
                json.dumps(dict(redacted_detail or {})),
                subject_id,
                state,
                utc_now(),
            ),
        )
        return finding_id

    def list_security_findings(
        self: SQLiteStore,
        principal_id: str,
        *,
        source: str | None = None,
        subject_id: str | None = None,
        state: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Owner-scoped findings, newest first, optionally filtered by source,
        subject, or state. A different owner resolves nothing (isolation)."""
        conditions = ["principal_id = ?"]
        params: list[Any] = [principal_id]
        if source is not None:
            conditions.append("source = ?")
            params.append(source)
        if subject_id is not None:
            conditions.append("subject_id = ?")
            params.append(subject_id)
        if state is not None:
            conditions.append("state = ?")
            params.append(state)
        params.append(int(limit))
        rows = self._rows(
            f"SELECT * FROM security_findings WHERE {' AND '.join(conditions)} "
            "ORDER BY created_at DESC, rowid DESC LIMIT ?",
            params,
        )
        return [self._security_finding_row(row) for row in rows]


    def insert_notification(
        self: SQLiteStore,
        *,
        principal_id: str,
        kind: str,
        title: str,
        body: str,
        finding_id: str | None = None,
        subject_id: str | None = None,
    ) -> str:
        """Persist one owner-facing notification. ``title`` / ``body`` are already
        redacted human-readable copy (never a raw payload or token). Owner-scoped
        by ``principal_id``; shared across sources (findings + containment)."""
        notification_id = new_id("ntf_")
        self._execute(
            """INSERT INTO notifications
               (notification_id, principal_id, kind, title, body, finding_id,
                subject_id, read, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)""",
            (
                notification_id,
                principal_id,
                kind,
                title,
                body,
                finding_id,
                subject_id,
                utc_now(),
            ),
        )
        return notification_id

    def list_notifications(
        self: SQLiteStore, principal_id: str, *, unread_only: bool = False, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Owner-scoped notifications, newest first. ``unread_only`` filters to
        the unread ones. A different owner resolves nothing (isolation)."""
        conditions = ["principal_id = ?"]
        params: list[Any] = [principal_id]
        if unread_only:
            conditions.append("read = 0")
        params.append(int(limit))
        rows = self._rows(
            f"SELECT * FROM notifications WHERE {' AND '.join(conditions)} "
            "ORDER BY created_at DESC, rowid DESC LIMIT ?",
            params,
        )
        return [dict(row) for row in rows]

    def mark_notification_read(self: SQLiteStore, notification_id: str, principal_id: str) -> bool:
        """Owner-scoped mark-as-read. Returns False if the row is missing or owned
        by another principal (isolation)."""
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE notifications SET read = 1 WHERE notification_id = ? AND principal_id = ?",
                (notification_id, principal_id),
            )
            return cursor.rowcount > 0

    # â”€â”€ Credential lifecycle + security-monitor state (Control Deck Task 5) â”€â”€

    def upsert_credential_lifecycle(
        self: SQLiteStore,
        principal_id: str,
        provider: str,
        *,
        verified_at: str,
        due_at: str,
        status: str,
    ) -> dict[str, Any]:
        credential_id = new_id("cred_")
        self._execute(
            """INSERT INTO credential_lifecycle
               (credential_id, principal_id, provider, rotated_at, verified_at, due_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(principal_id, provider) DO UPDATE SET
                 rotated_at=excluded.rotated_at, verified_at=excluded.verified_at,
                 due_at=excluded.due_at, status=excluded.status""",
            (credential_id, principal_id, provider, verified_at, verified_at, due_at, status),
        )
        row = self.get_credential_lifecycle(principal_id, provider)
        assert row is not None
        return row

    def get_credential_lifecycle(self: SQLiteStore, principal_id: str, provider: str) -> dict[str, Any] | None:
        row = self._row(
            "SELECT * FROM credential_lifecycle WHERE principal_id = ? AND provider = ?",
            (principal_id, provider),
        )
        return dict(row) if row else None

    def list_credential_lifecycle(self: SQLiteStore, principal_id: str) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT * FROM credential_lifecycle WHERE principal_id = ? ORDER BY provider",
            (principal_id,),
        )
        return [dict(row) for row in rows]

    def get_security_monitor_state(
        self: SQLiteStore, principal_id: str, source: str, subject_id: str, code: str
    ) -> dict[str, Any] | None:
        row = self._row(
            """SELECT * FROM security_monitor_state
               WHERE principal_id = ? AND source = ? AND subject_id = ? AND code = ?""",
            (principal_id, source, subject_id, code),
        )
        return dict(row) if row else None

    def set_security_monitor_state(
        self: SQLiteStore,
        principal_id: str,
        source: str,
        subject_id: str,
        code: str,
        *,
        state: str,
        finding_id: str | None,
    ) -> None:
        self._execute(
            """INSERT INTO security_monitor_state
               (principal_id, source, subject_id, code, state, finding_id, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(principal_id, source, subject_id, code) DO UPDATE SET
                 state=excluded.state, finding_id=excluded.finding_id, updated_at=excluded.updated_at""",
            (principal_id, source, subject_id, code, state, finding_id, utc_now()),
        )

    def set_security_finding_state(self: SQLiteStore, finding_id: str, principal_id: str, state: str) -> bool:
        changed = self._execute(
            "UPDATE security_findings SET state = ? WHERE finding_id = ? AND principal_id = ?",
            (state, finding_id, principal_id),
        )
        return changed > 0

    def list_security_monitor_state(self: SQLiteStore, principal_id: str) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT * FROM security_monitor_state WHERE principal_id = ? ORDER BY updated_at DESC",
            (principal_id,),
        )
        return [dict(row) for row in rows]

    # The generic sibling of the MCP monitor's storage: one redacted activity row
    # per governed capability invocation, and one containment row per subject.
    # Owner-scoped throughout — every read and write is keyed by `principal_id`,
    # so one owner's monitor can never see or contain another owner's subject.

    def insert_capability_activity(
        self: SQLiteStore,
        *,
        principal_id: str,
        capability: str,
        subject_id: str,
        operation: str = "",
        hosts: list[str] | None = None,
        tools: list[str] | None = None,
        calls: int = 0,
        bytes_in: int = 0,
        bytes_out: int = 0,
        error_count: int = 0,
        outcome: str = "ok",
        reason_code: str = "",
        arg_sensitivity: str | None = None,
        result_sensitivity: str | None = None,
        observed_at: str | None = None,
    ) -> str:
        activity_id = new_id("cact_")
        self._execute(
            """INSERT INTO capability_activity_log
               (activity_id, principal_id, capability, subject_id, operation, hosts_json,
                tools_json, calls, bytes_in, bytes_out, error_count, outcome, reason_code,
                arg_sensitivity, result_sensitivity, observed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                activity_id,
                principal_id,
                capability,
                subject_id,
                operation,
                json.dumps(sorted(hosts or [])),
                json.dumps(sorted(tools or [])),
                int(calls),
                int(bytes_in),
                int(bytes_out),
                int(error_count),
                outcome,
                reason_code,
                arg_sensitivity,
                result_sensitivity,
                observed_at or utc_now(),
            ),
        )
        return activity_id

    def list_capability_activity(
        self: SQLiteStore, principal_id: str, capability: str, subject_id: str, *, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Most-recent-first activity rows forming one subject's rolling baseline."""
        rows = self._rows(
            """SELECT * FROM capability_activity_log
               WHERE principal_id = ? AND capability = ? AND subject_id = ?
               ORDER BY observed_at DESC, rowid DESC LIMIT ?""",
            (principal_id, capability, subject_id, int(limit)),
        )
        return [
            {
                **dict(row),
                "hosts": json.loads(row["hosts_json"] or "[]"),
                "tools": json.loads(row["tools_json"] or "[]"),
            }
            for row in rows
        ]

    def get_capability_containment(
        self: SQLiteStore, principal_id: str, capability: str, subject_id: str
    ) -> dict[str, Any] | None:
        row = self._row(
            """SELECT * FROM capability_containment
               WHERE principal_id = ? AND capability = ? AND subject_id = ?""",
            (principal_id, capability, subject_id),
        )
        return dict(row) if row else None

    def list_capability_containment(
        self: SQLiteStore, principal_id: str, *, capability: str | None = None
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM capability_containment WHERE principal_id = ?"
        params: list[Any] = [principal_id]
        if capability:
            query += " AND capability = ?"
            params.append(capability)
        rows = self._rows(query + " ORDER BY updated_at DESC", tuple(params))
        return [dict(row) for row in rows]

    def set_capability_containment(
        self: SQLiteStore,
        principal_id: str,
        capability: str,
        subject_id: str,
        *,
        state: str,
        label: str = "",
        reason: str | None = None,
        source: str = "owner",
        finding_id: str | None = None,
        failure_streak: int | None = None,
        last_failure_code: str | None = None,
        contained_at: str | None = None,
        probe_after: str | None = None,
    ) -> dict[str, Any]:
        """Upsert one subject's containment row and return the stored result.

        ``failure_streak``/``last_failure_code``/``probe_after`` are only written
        when supplied, so a containment transition never silently resets the
        breaker's own counters and a counter update never rewrites the owner's
        stated reason.
        """
        now = utc_now()
        existing = self.get_capability_containment(principal_id, capability, subject_id) or {}
        row = {
            "label": label or str(existing.get("label") or ""),
            "state": state,
            "reason": reason,
            "source": source,
            "finding_id": finding_id,
            "failure_streak": (
                int(failure_streak)
                if failure_streak is not None
                else int(existing.get("failure_streak") or 0)
            ),
            "last_failure_code": (
                last_failure_code
                if last_failure_code is not None
                else str(existing.get("last_failure_code") or "")
            ),
            "contained_at": contained_at,
            "probe_after": probe_after,
        }
        self._execute(
            """INSERT INTO capability_containment
               (principal_id, capability, subject_id, label, state, reason, source,
                finding_id, failure_streak, last_failure_code, contained_at, probe_after,
                updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(principal_id, capability, subject_id) DO UPDATE SET
                 label=excluded.label, state=excluded.state, reason=excluded.reason,
                 source=excluded.source, finding_id=excluded.finding_id,
                 failure_streak=excluded.failure_streak,
                 last_failure_code=excluded.last_failure_code,
                 contained_at=excluded.contained_at, probe_after=excluded.probe_after,
                 updated_at=excluded.updated_at""",
            (
                principal_id,
                capability,
                subject_id,
                row["label"],
                row["state"],
                row["reason"],
                row["source"],
                row["finding_id"],
                row["failure_streak"],
                row["last_failure_code"],
                row["contained_at"],
                row["probe_after"],
                now,
            ),
        )
        return {
            "principal_id": principal_id,
            "capability": capability,
            "subject_id": subject_id,
            **row,
            "updated_at": now,
        }

    def record_background_pass(
        self: SQLiteStore, pass_name: str, *, error_class: str | None = None
    ) -> None:
        """Record one host-tick pass, whether it succeeded or threw.

        The passes stay isolated from one another — that part was right — but a
        suppressed exception now leaves evidence. A success resets the streak;
        a failure records only the exception's *class*, never its message, so a
        provider that put a key fragment or a body in the text cannot reach a
        durable row.
        """
        now = utc_now()
        with self.connect() as connection:
            if error_class is None:
                connection.execute(
                    """INSERT INTO background_worker_health
                    (pass_name, last_success_at, consecutive_failures, updated_at)
                    VALUES (?, ?, 0, ?)
                    ON CONFLICT(pass_name) DO UPDATE SET
                      last_success_at = excluded.last_success_at,
                      consecutive_failures = 0,
                      updated_at = excluded.updated_at""",
                    (pass_name, now, now),
                )
                return
            connection.execute(
                """INSERT INTO background_worker_health
                (pass_name, last_failure_at, last_error_class, consecutive_failures,
                 total_failures, updated_at)
                VALUES (?, ?, ?, 1, 1, ?)
                ON CONFLICT(pass_name) DO UPDATE SET
                  last_failure_at = excluded.last_failure_at,
                  last_error_class = excluded.last_error_class,
                  consecutive_failures = background_worker_health.consecutive_failures + 1,
                  total_failures = background_worker_health.total_failures + 1,
                  updated_at = excluded.updated_at""",
                (pass_name, now, error_class[:120], now),
            )

    def list_background_worker_health(
        self: SQLiteStore, *, now: datetime | None = None
    ) -> list[dict[str, Any]]:
        """Every recorded host-tick pass, worst first.

        DEC-24 step 1 — a pass whose last record is older than
        :data:`BACKGROUND_PASS_STALE_SECONDS` is ``stale``, not ``ok``. Health
        was read from the failure streak alone, so a tick that stopped running
        altogether — a host that hung, a worker that died — kept the last
        thing it said, which was "ok", for ever. Not having heard from a pass
        is not evidence that it is well.
        """
        rows = self._rows(
            """SELECT * FROM background_worker_health
            ORDER BY consecutive_failures DESC, pass_name""",
        )
        at = now or datetime.now(UTC)
        out: list[dict[str, Any]] = []
        for row in rows:
            failing = int(row["consecutive_failures"]) > 0
            stale = _older_than(str(row["updated_at"]), at, BACKGROUND_PASS_STALE_SECONDS)
            out.append(
                {
                    "pass_name": str(row["pass_name"]),
                    "last_success_at": row["last_success_at"],
                    "last_failure_at": row["last_failure_at"],
                    "last_error_class": row["last_error_class"],
                    "consecutive_failures": int(row["consecutive_failures"]),
                    "total_failures": int(row["total_failures"]),
                    "healthy": not failing and not stale,
                    "state": "failing" if failing else "stale" if stale else "ok",
                    "updated_at": str(row["updated_at"]),
                }
            )
        # Worst first: failing, then stale, then the rest.
        rank = {"failing": 0, "stale": 1, "ok": 2}
        return sorted(out, key=lambda entry: rank[entry["state"]])
