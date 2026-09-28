# mypy: disable-error-code="misc"
"""Checkpoints, audit exports, retention policies and backups (GCR-11).

One part of :class:`raiker.storage.sqlite.SQLiteStore`, which inherits it. Every method
is typed against the whole store (``self: SQLiteStore``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import utc_now
from raiker.contracts.models import BackupManifest, Checkpoint, ExportManifest, RetentionPolicy

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


class RecordStore:

    def insert_checkpoint(self: SQLiteStore, checkpoint: Checkpoint, manifest_path: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO checkpoints
                (checkpoint_id, session_id, turn_id, task_id, checkpoint_type, manifest_path, created_at, summary, last_event_id, can_restore_state, can_restore_files)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint.checkpoint_id,
                    checkpoint.session_id,
                    checkpoint.turn_id,
                    None,
                    "turn_stub",
                    manifest_path,
                    checkpoint.created_at,
                    checkpoint.summary,
                    checkpoint.last_event_id,
                    1,
                    0,
                ),
            )

    def insert_checkpoint_capture_entry(
        self: SQLiteStore,
        *,
        manifest_id: str,
        session_id: str,
        turn_id: str | None,
        action_id: str,
        capability: str,
        principal_id: str | None,
        workspace_path: str,
        pre_image_sha256: str | None,
        pre_image_size: int,
        existed_before: bool,
        capture_status: str,
        created_at: str,
    ) -> None:
        """Record one metadata-only pre-image manifest entry (B1 capture).

        No file content is stored here — only the content-address (sha256) of the
        pre-image blob that lives under ``.raiker/checkpoints/objects/``.
        """
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO checkpoint_capture_manifest
                (manifest_id, session_id, turn_id, action_id, capability, principal_id,
                 workspace_path, pre_image_sha256, pre_image_size, existed_before,
                 capture_status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    manifest_id,
                    session_id,
                    turn_id,
                    action_id,
                    capability,
                    principal_id,
                    workspace_path,
                    pre_image_sha256,
                    int(pre_image_size),
                    1 if existed_before else 0,
                    capture_status,
                    created_at,
                ),
            )

    def list_checkpoint_capture_entries(
        self: SQLiteStore,
        *,
        session_id: str | None = None,
        turn_id: str | None = None,
        action_id: str | None = None,
        created_after: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list[object] = []
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if turn_id is not None:
            clauses.append("turn_id = ?")
            params.append(turn_id)
        if action_id is not None:
            clauses.append("action_id = ?")
            params.append(action_id)
        if created_after is not None:
            # Strictly-after the checkpoint's own timestamp: a checkpoint captures
            # the state *at* its creation, so only mutations recorded after it are
            # rewound (the checkpoint's own turn keeps its changes).
            clauses.append("created_at > ?")
            params.append(created_after)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT manifest_id, session_id, turn_id, action_id, capability, principal_id,
                       workspace_path, pre_image_sha256, pre_image_size, existed_before,
                       capture_status, created_at
                FROM checkpoint_capture_manifest
                {where}
                ORDER BY created_at DESC, manifest_id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_checkpoint_capture_health(
        self: SQLiteStore,
        *,
        ok: bool,
        stage: str,
        reason_code: str,
        display_path: str | None,
        checked_at: str,
        remediation: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO checkpoint_capture_health
                   (singleton, ok, stage, reason_code, display_path, checked_at, remediation)
                   VALUES (1, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(singleton) DO UPDATE SET
                     ok=excluded.ok, stage=excluded.stage,
                     reason_code=excluded.reason_code,
                     display_path=excluded.display_path,
                     checked_at=excluded.checked_at,
                     remediation=excluded.remediation""",
                (
                    1 if ok else 0,
                    stage,
                    reason_code,
                    display_path,
                    checked_at,
                    remediation,
                ),
            )

    def get_checkpoint_capture_health(self: SQLiteStore) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT ok, stage, reason_code, display_path, checked_at, remediation "
                "FROM checkpoint_capture_health WHERE singleton = 1"
            ).fetchone()
        return dict(row) if row else None

    def count_checkpoints(self: SQLiteStore, session_id: str | None = None) -> int:
        query = "SELECT COUNT(*) AS cnt FROM checkpoints"
        params: list[Any] = []
        if session_id is not None:
            query += " WHERE session_id = ?"
            params.append(session_id)
        with self.connect() as connection:
            row = connection.execute(query, params).fetchone()
        return int(row["cnt"]) if row else 0

    def list_checkpoints(
        self: SQLiteStore, session_id: str | None = None, limit: int = 50, project_id: str | None = None
    ) -> list[dict]:
        query = "SELECT * FROM checkpoints"
        params: list[Any] = []
        clauses: list[str] = []
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if project_id is not None:
            # Checkpoints belong to a project through their session.
            clauses.append("session_id IN (SELECT session_id FROM sessions WHERE project_id = ?)")
            params.append(project_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(str(limit))
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def load_checkpoint_by_id(self: SQLiteStore, checkpoint_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,)
            ).fetchone()
        return dict(row) if row else None

    def insert_audit_export(self: SQLiteStore, manifest: ExportManifest) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO audit_exports
                (export_id, manifest_hash, scope_json, redacted, event_count, first_event_id, last_event_id, first_timestamp, last_timestamp, export_path, exported_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    manifest.export_id,
                    manifest.manifest_hash,
                    manifest.scope_json,
                    int(manifest.redacted),
                    manifest.event_count,
                    manifest.first_event_id,
                    manifest.last_event_id,
                    manifest.first_timestamp,
                    manifest.last_timestamp,
                    manifest.export_path,
                    manifest.exported_by,
                    manifest.created_at,
                ),
            )

    def list_audit_exports(self: SQLiteStore, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_exports ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def load_audit_export(self: SQLiteStore, export_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM audit_exports WHERE export_id = ?", (export_id,)
            ).fetchone()
        return dict(row) if row else None

    def insert_retention_policy(self: SQLiteStore, policy: RetentionPolicy) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO retention_policies
                (policy_id, target_type, retention_days, legal_hold, enabled, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    policy.policy_id,
                    policy.target_type,
                    policy.retention_days,
                    int(policy.legal_hold),
                    int(policy.enabled),
                    policy.created_by,
                    policy.created_at,
                    policy.updated_at,
                ),
            )

    def list_retention_policies(self: SQLiteStore, enabled_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM retention_policies"
        params: list[Any] = []
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def insert_backup_manifest(self: SQLiteStore, manifest: BackupManifest) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO backup_manifests
                (manifest_id, backup_type, scope_json, path, checksum, size_bytes, created_by, created_at,
                 encryption_key_id, retention_until, legal_hold, erasure_requested_at, erased_at, restore_verified_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    manifest.manifest_id,
                    manifest.backup_type,
                    manifest.scope_json,
                    manifest.path,
                    manifest.checksum,
                    manifest.size_bytes,
                    manifest.created_by,
                    manifest.created_at,
                    manifest.encryption_key_id,
                    manifest.retention_until,
                    int(manifest.legal_hold),
                    manifest.erasure_requested_at,
                    manifest.erased_at,
                    manifest.restore_verified_at,
                ),
            )
        self.record_memory_lifecycle_event(
            f"backup:{manifest.manifest_id}",
            "backup_access",
            manifest.created_by,
            {"operation": "catalog_register"},
        )

    def list_backup_manifests(self: SQLiteStore, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM backup_manifests ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def request_backup_erasure(self: SQLiteStore, manifest_id: str, actor_id: str = "system") -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE backup_manifests SET erasure_requested_at = ? WHERE manifest_id = ? AND legal_hold = 0 AND erased_at IS NULL",
                (utc_now(), manifest_id),
            )
        changed = cursor.rowcount > 0
        if changed:
            self.record_memory_lifecycle_event(
                f"backup:{manifest_id}",
                "backup_access",
                actor_id,
                {"operation": "erasure_requested"},
            )
        return changed

    def record_backup_erased(self: SQLiteStore, manifest_id: str, actor_id: str = "system") -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE backup_manifests SET erased_at = ? WHERE manifest_id = ? AND erasure_requested_at IS NOT NULL AND legal_hold = 0",
                (utc_now(), manifest_id),
            )
        changed = cursor.rowcount > 0
        if changed:
            self.record_memory_lifecycle_event(
                f"backup:{manifest_id}", "backup_access", actor_id, {"operation": "erased"}
            )
        return changed

    def record_backup_restore_verified(self: SQLiteStore, manifest_id: str, actor_id: str = "system") -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE backup_manifests SET restore_verified_at = ? WHERE manifest_id = ? AND erased_at IS NULL",
                (utc_now(), manifest_id),
            )
        changed = cursor.rowcount > 0
        if changed:
            self.record_memory_lifecycle_event(
                f"backup:{manifest_id}",
                "backup_access",
                actor_id,
                {"operation": "restore_verified"},
            )
        return changed

    def set_backup_legal_hold(self: SQLiteStore, manifest_id: str, legal_hold: bool, actor_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE backup_manifests SET legal_hold = ? WHERE manifest_id = ? AND erased_at IS NULL",
                (int(legal_hold), manifest_id),
            )
        changed = cursor.rowcount > 0
        if changed:
            self.record_memory_lifecycle_event(
                f"backup:{manifest_id}", "legal_hold", actor_id, {"legal_hold": legal_hold}
            )
        return changed
