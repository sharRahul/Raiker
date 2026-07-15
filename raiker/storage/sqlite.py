from __future__ import annotations

import contextlib
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pysqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

from raiker.auth.app_key import ensure_app_key
from raiker.contracts.ids import utc_now
from raiker.contracts.models import (
    AgentEvent,
    ApprovalRelayRecord,
    BackupManifest,
    BudgetRecord,
    ChannelPairing,
    Checkpoint,
    ConnectorProfile,
    DependencyEdge,
    ExecutionBudget,
    ExportManifest,
    GraphIndexRecord,
    HostedRoutine,
    ManagedPolicyRule,
    ModelProfile,
    PluginExecutionRecord,
    PluginInstallRecord,
    PolicyDecision,
    ProjectGraph,
    RemoteExecutionProfile,
    RetentionPolicy,
    Role,
    SemanticMemoryWriteRecord,
    SkillCandidate,
    SubagentContract,
    SymbolNode,
    TaskRecord,
    TeamLedger,
    ToolAction,
    User,
    UserRoleAssignment,
    VectorRecord,
)
from raiker.models.session_state import ModelSessionState
from raiker.storage.migrations import (
    API_SESSIONS_MIGRATION_ID,
    API_SESSIONS_SQL,
    ATTACHMENT_STORE_MIGRATION_ID,
    ATTACHMENT_STORE_SQL,
    CALENDAR_EVENTS_MIGRATION_ID,
    CALENDAR_EVENTS_SQL,
    CAPABILITY_DECISION_MODE_MIGRATION_ID,
    CAPABILITY_DECISION_MODE_SQL,
    CONNECTOR_ECOSYSTEM_MIGRATION_ID,
    CONNECTOR_ECOSYSTEM_SQL,
    CONNECTOR_INVOCATIONS_MIGRATION_ID,
    CONNECTOR_INVOCATIONS_SQL,
    EIDETIC_OBSERVATIONS_MIGRATION_ID,
    EIDETIC_OBSERVATIONS_SQL,
    EMAIL_DRAFTS_MIGRATION_ID,
    EMAIL_DRAFTS_SQL,
    GIST_MEMORY_MIGRATION_ID,
    GIST_MEMORY_SQL,
    LOCK_SCREEN_MIGRATION_ID,
    LOCK_SCREEN_SQL,
    MEMORY_ARCHIVE_MIGRATION_ID,
    MEMORY_ARCHIVE_SQL,
    MEMORY_AUDIT_RATE_LIMIT_MIGRATION_ID,
    MEMORY_AUDIT_RATE_LIMIT_SQL,
    MEMORY_BACKUP_CATALOG_MIGRATION_ID,
    MEMORY_BACKUP_CATALOG_SQL,
    MEMORY_CONTROLS_MIGRATION_ID,
    MEMORY_CONTROLS_SQL,
    MEMORY_ENTITY_GRAPH_MIGRATION_ID,
    MEMORY_ENTITY_GRAPH_SQL,
    MEMORY_FTS_MIGRATION_ID,
    MEMORY_FTS_SQL,
    MEMORY_JOBS_MIGRATION_ID,
    MEMORY_JOBS_SQL,
    MEMORY_PROJECTIONS_MIGRATION_ID,
    MEMORY_PROJECTIONS_SQL,
    MEMORY_PURGE_MIGRATION_ID,
    MEMORY_PURGE_SQL,
    MEMORY_RETRIEVAL_AUTHORITY_MIGRATION_ID,
    MEMORY_RETRIEVAL_AUTHORITY_SQL,
    MEMORY_SQLCIPHER_FTS_MIGRATION_ID,
    MEMORY_SQLCIPHER_FTS_SQL,
    MEMORY_TEMPORAL_EVALUATION_MIGRATION_ID,
    MEMORY_TEMPORAL_EVALUATION_SQL,
    MODEL_ADVISOR_MIGRATION_ID,
    MODEL_ADVISOR_SQL,
    MODEL_FALLBACK_SEQUENCE_MIGRATION_ID,
    MODEL_FALLBACK_SEQUENCE_SQL,
    MODEL_SESSION_RESOLVED_MODEL_MIGRATION_ID,
    MODEL_SESSION_RESOLVED_MODEL_SQL,
    PHASE_1_MIGRATION_ID,
    PHASE_1_SQL,
    PHASE_2_MIGRATION_ID,
    PHASE_2_MIGRATION_SQL,
    PHASE_3_APPROVAL_PREVIEW_PERSISTENCE_READINESS_MIGRATION_ID,
    PHASE_3_APPROVAL_PREVIEW_PERSISTENCE_READINESS_SQL,
    PHASE_3_EXTERNAL_CHANNELS_NOTIFICATIONS_READINESS_MIGRATION_ID,
    PHASE_3_EXTERNAL_CHANNELS_NOTIFICATIONS_READINESS_SQL,
    PHASE_3_GRAPH_CODEMAP_READINESS_MIGRATION_ID,
    PHASE_3_GRAPH_CODEMAP_READINESS_SQL,
    PHASE_3_PLUGIN_SERVER_STARTUP_READINESS_MIGRATION_ID,
    PHASE_3_PLUGIN_SERVER_STARTUP_READINESS_SQL,
    PHASE_3_REMOTE_CONTAINER_CLOUD_READINESS_MIGRATION_ID,
    PHASE_3_REMOTE_CONTAINER_CLOUD_READINESS_SQL,
    PHASE_3_SEMANTIC_MEMORY_READINESS_MIGRATION_ID,
    PHASE_3_SEMANTIC_MEMORY_READINESS_SQL,
    PHASE_3_SLICE_A_PROPOSAL_LIFECYCLE_MIGRATION_ID,
    PHASE_3_SLICE_A_PROPOSAL_LIFECYCLE_SQL,
    PHASE_3_SLICE_B_APPROVAL_PLANNING_PREVIEW_MIGRATION_ID,
    PHASE_3_SLICE_B_APPROVAL_PLANNING_PREVIEW_SQL,
    PHASE_3_STORAGE_CLEANUP_EXECUTION_READINESS_MIGRATION_ID,
    PHASE_3_STORAGE_CLEANUP_EXECUTION_READINESS_SQL,
    PHASE_3_STORAGE_LIFECYCLE_EVIDENCE_MIGRATION_ID,
    PHASE_3_STORAGE_LIFECYCLE_EVIDENCE_SQL,
    PHASE_3_STORAGE_LIFECYCLE_MIGRATION_ID,
    PHASE_3_STORAGE_LIFECYCLE_RETENTION_MIGRATION_ID,
    PHASE_3_STORAGE_LIFECYCLE_RETENTION_SQL,
    PHASE_3_STORAGE_LIFECYCLE_SQL,
    PHASE_4_MEMORY_GOVERNANCE_HARDENING_MIGRATION_ID,
    PHASE_4_MEMORY_GOVERNANCE_HARDENING_SQL,
    PHASE_4_MEMORY_MVP_MIGRATION_ID,
    PHASE_4_MEMORY_MVP_SQL,
    PHASE_4_SCHEDULED_ROUTINES_MIGRATION_ID,
    PHASE_4_SCHEDULED_ROUTINES_SQL,
    PHASE_5_AUDIT_EXPORT_MIGRATION_ID,
    PHASE_5_AUDIT_EXPORT_SQL,
    PHASE_5_BUDGET_RECORDS_MIGRATION_ID,
    PHASE_5_BUDGET_RECORDS_SQL,
    PHASE_5_HOSTED_ROUTINES_MIGRATION_ID,
    PHASE_5_HOSTED_ROUTINES_SQL,
    PHASE_5_MANAGED_POLICY_MIGRATION_ID,
    PHASE_5_MANAGED_POLICY_SQL,
    PHASE_5_ORG_ROLES_MIGRATION_ID,
    PHASE_5_ORG_ROLES_SQL,
    PHASE_5_PLUGIN_MARKETPLACE_MIGRATION_ID,
    PHASE_5_PLUGIN_MARKETPLACE_SQL,
    PHASE_5_RETENTION_POLICIES_MIGRATION_ID,
    PHASE_5_RETENTION_POLICIES_SQL,
    PHASE_6_APPROVAL_RELAY_MIGRATION_ID,
    PHASE_6_APPROVAL_RELAY_SQL,
    PHASE_6_CHANNEL_PAIRINGS_MIGRATION_ID,
    PHASE_6_CHANNEL_PAIRINGS_SQL,
    PHASE_6_REMOTE_EXECUTION_MIGRATION_ID,
    PHASE_6_REMOTE_EXECUTION_SQL,
    PHASE_6_SUBAGENTS_MIGRATION_ID,
    PHASE_6_SUBAGENTS_SQL,
    PHASE_6_TEAMS_MIGRATION_ID,
    PHASE_6_TEAMS_SQL,
    PHASE_7_DESKTOP_SESSIONS_MIGRATION_ID,
    PHASE_7_DESKTOP_SESSIONS_SQL,
    PHASE_7_GRAPH_INDEX_MIGRATION_ID,
    PHASE_7_GRAPH_INDEX_SQL,
    PHASE_7_IDE_SESSIONS_MIGRATION_ID,
    PHASE_7_IDE_SESSIONS_SQL,
    PHASE_7_PLUGIN_EXECUTION_MIGRATION_ID,
    PHASE_7_PLUGIN_EXECUTION_SQL,
    PHASE_7_SEMANTIC_MEMORY_MIGRATION_ID,
    PHASE_7_SEMANTIC_MEMORY_SQL,
    PHASE_7_WEB_SESSIONS_MIGRATION_ID,
    PHASE_7_WEB_SESSIONS_SQL,
    PHASE_9_PROJECT_GRAPH_MIGRATION_ID,
    PHASE_9_PROJECT_GRAPH_SQL,
    PHASE_9_SKILL_CANDIDATES_MIGRATION_ID,
    PHASE_9_SKILL_CANDIDATES_SQL,
    PHASE_9_SYMBOL_GRAPH_MIGRATION_ID,
    PHASE_9_SYMBOL_GRAPH_SQL,
    PHASE_9_VECTOR_INDEX_MIGRATION_ID,
    PHASE_9_VECTOR_INDEX_SQL,
    PHASE_10_CAPABILITY_GATE_STATE_MIGRATION_ID,
    PHASE_10_CAPABILITY_GATE_STATE_SQL,
    PHASE_10_RUNTIME_AUTHORITY_MIGRATION_ID,
    PHASE_10_RUNTIME_AUTHORITY_SQL,
    PHASE_10_RUNTIME_MODE_STATE_MIGRATION_ID,
    PHASE_10_RUNTIME_MODE_STATE_SQL,
    PROJECT_CONTEXT_MIGRATION_ID,
    PROJECT_CONTEXT_SQL,
    PROJECT_MEMORY_INHERITANCE_MIGRATION_ID,
    PROJECT_MEMORY_INHERITANCE_SQL,
    PROJECT_SELF_INCLUSIVE_PATH_MIGRATION_ID,
    PROJECTS_MIGRATION_ID,
    PROJECTS_NESTING_MIGRATION_ID,
    PROJECTS_NESTING_SQL,
    PROJECTS_SQL,
    REMINDERS_MIGRATION_ID,
    REMINDERS_SQL,
    SESSION_TAGS_MIGRATION_ID,
    SESSION_TAGS_SQL,
    THREAT_MODEL_ACKS_MIGRATION_ID,
    THREAT_MODEL_ACKS_SQL,
)


@dataclass(frozen=True)
class RuntimePaths:
    workspace_root: Path

    @property
    def runtime_dir(self) -> Path:
        return self.workspace_root / ".raiker"

    @property
    def db_path(self) -> Path:
        return self.runtime_dir / "raiker.db"

    @property
    def events_dir(self) -> Path:
        return self.runtime_dir / "events"

    @property
    def checkpoints_dir(self) -> Path:
        return self.runtime_dir / "checkpoints"

    @property
    def artifacts_dir(self) -> Path:
        return self.runtime_dir / "artifacts"

    @property
    def indexes_dir(self) -> Path:
        return self.runtime_dir / "indexes"

    def ensure(self) -> None:
        for path in (
            self.runtime_dir,
            self.events_dir,
            self.checkpoints_dir,
            self.artifacts_dir,
            self.indexes_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


class SQLiteStore:
    def __init__(self, workspace_root: str | Path) -> None:
        self.paths = RuntimePaths(Path(workspace_root).resolve())
        self.paths.ensure()
        self.db_path = self.paths.db_path
        self.bootstrap()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path), timeout=5.0)
        key_hex = hashlib.sha256(ensure_app_key(self.paths.workspace_root)).hexdigest()
        connection.execute(f"PRAGMA key = \"x'{key_hex}'\"")
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def bootstrap(self) -> None:
        self.paths.ensure()
        self._migrate_plaintext_database()
        with self.connect() as connection:
            connection.executescript(PHASE_1_SQL)
            connection.executescript("""
CREATE TABLE IF NOT EXISTS model_session_state (
  session_id TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL,
  model TEXT,
  reasoning_enabled INTEGER NOT NULL DEFAULT 0,
  reasoning_effort TEXT,
  reasoning_mode TEXT,
  reasoning_budget_tokens INTEGER,
  updated_at TEXT NOT NULL
);
""")
            connection.execute(
                "INSERT OR IGNORE INTO migrations (migration_id, applied_at) VALUES (?, ?)",
                (PHASE_1_MIGRATION_ID, utc_now()),
            )

            self._apply_migration(PHASE_2_MIGRATION_ID, PHASE_2_MIGRATION_SQL, connection)
            self._apply_migration(
                MODEL_SESSION_RESOLVED_MODEL_MIGRATION_ID,
                MODEL_SESSION_RESOLVED_MODEL_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_3_STORAGE_LIFECYCLE_MIGRATION_ID, PHASE_3_STORAGE_LIFECYCLE_SQL, connection
            )
            self._apply_migration(
                PHASE_3_STORAGE_LIFECYCLE_RETENTION_MIGRATION_ID,
                PHASE_3_STORAGE_LIFECYCLE_RETENTION_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_3_STORAGE_LIFECYCLE_EVIDENCE_MIGRATION_ID,
                PHASE_3_STORAGE_LIFECYCLE_EVIDENCE_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_3_GRAPH_CODEMAP_READINESS_MIGRATION_ID,
                PHASE_3_GRAPH_CODEMAP_READINESS_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_3_SEMANTIC_MEMORY_READINESS_MIGRATION_ID,
                PHASE_3_SEMANTIC_MEMORY_READINESS_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_3_APPROVAL_PREVIEW_PERSISTENCE_READINESS_MIGRATION_ID,
                PHASE_3_APPROVAL_PREVIEW_PERSISTENCE_READINESS_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_3_STORAGE_CLEANUP_EXECUTION_READINESS_MIGRATION_ID,
                PHASE_3_STORAGE_CLEANUP_EXECUTION_READINESS_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_3_PLUGIN_SERVER_STARTUP_READINESS_MIGRATION_ID,
                PHASE_3_PLUGIN_SERVER_STARTUP_READINESS_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_3_EXTERNAL_CHANNELS_NOTIFICATIONS_READINESS_MIGRATION_ID,
                PHASE_3_EXTERNAL_CHANNELS_NOTIFICATIONS_READINESS_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_3_REMOTE_CONTAINER_CLOUD_READINESS_MIGRATION_ID,
                PHASE_3_REMOTE_CONTAINER_CLOUD_READINESS_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_3_SLICE_A_PROPOSAL_LIFECYCLE_MIGRATION_ID,
                PHASE_3_SLICE_A_PROPOSAL_LIFECYCLE_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_3_SLICE_B_APPROVAL_PLANNING_PREVIEW_MIGRATION_ID,
                PHASE_3_SLICE_B_APPROVAL_PLANNING_PREVIEW_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_4_MEMORY_MVP_MIGRATION_ID,
                PHASE_4_MEMORY_MVP_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_4_MEMORY_GOVERNANCE_HARDENING_MIGRATION_ID,
                PHASE_4_MEMORY_GOVERNANCE_HARDENING_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_5_MANAGED_POLICY_MIGRATION_ID,
                PHASE_5_MANAGED_POLICY_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_5_ORG_ROLES_MIGRATION_ID,
                PHASE_5_ORG_ROLES_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_5_AUDIT_EXPORT_MIGRATION_ID,
                PHASE_5_AUDIT_EXPORT_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_5_PLUGIN_MARKETPLACE_MIGRATION_ID,
                PHASE_5_PLUGIN_MARKETPLACE_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_5_HOSTED_ROUTINES_MIGRATION_ID,
                PHASE_5_HOSTED_ROUTINES_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_5_BUDGET_RECORDS_MIGRATION_ID,
                PHASE_5_BUDGET_RECORDS_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_5_RETENTION_POLICIES_MIGRATION_ID,
                PHASE_5_RETENTION_POLICIES_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_6_CHANNEL_PAIRINGS_MIGRATION_ID,
                PHASE_6_CHANNEL_PAIRINGS_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_6_APPROVAL_RELAY_MIGRATION_ID,
                PHASE_6_APPROVAL_RELAY_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_6_SUBAGENTS_MIGRATION_ID,
                PHASE_6_SUBAGENTS_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_6_TEAMS_MIGRATION_ID,
                PHASE_6_TEAMS_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_6_REMOTE_EXECUTION_MIGRATION_ID,
                PHASE_6_REMOTE_EXECUTION_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_7_DESKTOP_SESSIONS_MIGRATION_ID,
                PHASE_7_DESKTOP_SESSIONS_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_7_WEB_SESSIONS_MIGRATION_ID,
                PHASE_7_WEB_SESSIONS_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_7_PLUGIN_EXECUTION_MIGRATION_ID,
                PHASE_7_PLUGIN_EXECUTION_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_7_GRAPH_INDEX_MIGRATION_ID,
                PHASE_7_GRAPH_INDEX_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_7_SEMANTIC_MEMORY_MIGRATION_ID,
                PHASE_7_SEMANTIC_MEMORY_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_7_IDE_SESSIONS_MIGRATION_ID,
                PHASE_7_IDE_SESSIONS_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_9_VECTOR_INDEX_MIGRATION_ID,
                PHASE_9_VECTOR_INDEX_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_9_SYMBOL_GRAPH_MIGRATION_ID,
                PHASE_9_SYMBOL_GRAPH_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_9_PROJECT_GRAPH_MIGRATION_ID,
                PHASE_9_PROJECT_GRAPH_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_9_SKILL_CANDIDATES_MIGRATION_ID,
                PHASE_9_SKILL_CANDIDATES_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_10_RUNTIME_AUTHORITY_MIGRATION_ID,
                PHASE_10_RUNTIME_AUTHORITY_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_10_RUNTIME_MODE_STATE_MIGRATION_ID,
                PHASE_10_RUNTIME_MODE_STATE_SQL,
                connection,
            )
            self._apply_migration(
                PHASE_10_CAPABILITY_GATE_STATE_MIGRATION_ID,
                PHASE_10_CAPABILITY_GATE_STATE_SQL,
                connection,
            )
            with contextlib.suppress(sqlite3.OperationalError):
                connection.execute("ALTER TABLE vector_records ADD COLUMN embedding TEXT")
            with contextlib.suppress(sqlite3.OperationalError):
                connection.execute("ALTER TABLE events_index ADD COLUMN prev_event_sha256 TEXT")
            with contextlib.suppress(sqlite3.OperationalError):
                connection.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT REFERENCES users(user_id)")
            self._apply_migration(
                CAPABILITY_DECISION_MODE_MIGRATION_ID, CAPABILITY_DECISION_MODE_SQL, connection
            )
            self._apply_migration(REMINDERS_MIGRATION_ID, REMINDERS_SQL, connection)
            for _col in (
                "ALTER TABLE reminders ADD COLUMN delivery_status TEXT NOT NULL DEFAULT 'active'",
                "ALTER TABLE reminders ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE reminders ADD COLUMN max_retries INTEGER NOT NULL DEFAULT 3",
                "ALTER TABLE reminders ADD COLUMN delivered_at TEXT",
            ):
                with contextlib.suppress(sqlite3.OperationalError):
                    connection.execute(_col)
            self._apply_migration(CALENDAR_EVENTS_MIGRATION_ID, CALENDAR_EVENTS_SQL, connection)
            self._apply_migration(EMAIL_DRAFTS_MIGRATION_ID, EMAIL_DRAFTS_SQL, connection)
            self._apply_migration(API_SESSIONS_MIGRATION_ID, API_SESSIONS_SQL, connection)
            self._apply_migration(THREAT_MODEL_ACKS_MIGRATION_ID, THREAT_MODEL_ACKS_SQL, connection)
            self._apply_migration(
                PHASE_4_SCHEDULED_ROUTINES_MIGRATION_ID, PHASE_4_SCHEDULED_ROUTINES_SQL, connection
            )
            self._apply_migration(
                MODEL_FALLBACK_SEQUENCE_MIGRATION_ID, MODEL_FALLBACK_SEQUENCE_SQL, connection
            )
            self._apply_migration(MODEL_ADVISOR_MIGRATION_ID, MODEL_ADVISOR_SQL, connection)
            self._apply_migration(ATTACHMENT_STORE_MIGRATION_ID, ATTACHMENT_STORE_SQL, connection)
            self._apply_migration(PROJECTS_MIGRATION_ID, PROJECTS_SQL, connection)
            self._apply_migration(PROJECT_CONTEXT_MIGRATION_ID, PROJECT_CONTEXT_SQL, connection)
            self._apply_migration(
                CONNECTOR_ECOSYSTEM_MIGRATION_ID, CONNECTOR_ECOSYSTEM_SQL, connection
            )
            self._apply_migration(
                CONNECTOR_INVOCATIONS_MIGRATION_ID, CONNECTOR_INVOCATIONS_SQL, connection
            )
            with contextlib.suppress(sqlite3.OperationalError):
                connection.execute(
                    "ALTER TABLE sessions ADD COLUMN project_id TEXT REFERENCES projects(project_id)"
                )
            # Conversation organisation: a per-session pin/bookmark flag. It is
            # an organizing label only (like projects) — it grants nothing and
            # changes no gate, policy, or authority. Default 0 (unpinned).
            with contextlib.suppress(sqlite3.OperationalError):
                connection.execute("ALTER TABLE sessions ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
            self._apply_migration(LOCK_SCREEN_MIGRATION_ID, LOCK_SCREEN_SQL, connection)
            self._apply_migration(
                MEMORY_CONTROLS_MIGRATION_ID, MEMORY_CONTROLS_SQL, connection
            )
            self._apply_migration(
                SESSION_TAGS_MIGRATION_ID, SESSION_TAGS_SQL, connection
            )
            self._apply_migration(
                PROJECTS_NESTING_MIGRATION_ID, PROJECTS_NESTING_SQL, connection
            )
            self._apply_migration(
                PROJECT_MEMORY_INHERITANCE_MIGRATION_ID,
                PROJECT_MEMORY_INHERITANCE_SQL,
                connection,
            )
            self._backfill_self_inclusive_project_paths(connection)
            self._apply_migration(MEMORY_ARCHIVE_MIGRATION_ID, MEMORY_ARCHIVE_SQL, connection)
            self._apply_migration(EIDETIC_OBSERVATIONS_MIGRATION_ID, EIDETIC_OBSERVATIONS_SQL, connection)
            self._apply_migration(MEMORY_PURGE_MIGRATION_ID, MEMORY_PURGE_SQL, connection)
            self._apply_migration(GIST_MEMORY_MIGRATION_ID, GIST_MEMORY_SQL, connection)
            self._apply_migration(MEMORY_PROJECTIONS_MIGRATION_ID, MEMORY_PROJECTIONS_SQL, connection)
            self._apply_migration(MEMORY_FTS_MIGRATION_ID, MEMORY_FTS_SQL, connection)
            self._apply_migration(
                MEMORY_SQLCIPHER_FTS_MIGRATION_ID, MEMORY_SQLCIPHER_FTS_SQL, connection
            )
            self._apply_migration(
                MEMORY_RETRIEVAL_AUTHORITY_MIGRATION_ID,
                MEMORY_RETRIEVAL_AUTHORITY_SQL,
                connection,
            )
            self._apply_migration(
                MEMORY_TEMPORAL_EVALUATION_MIGRATION_ID,
                MEMORY_TEMPORAL_EVALUATION_SQL,
                connection,
            )
            self._apply_migration(
                MEMORY_ENTITY_GRAPH_MIGRATION_ID, MEMORY_ENTITY_GRAPH_SQL, connection
            )
            self._apply_migration(
                MEMORY_BACKUP_CATALOG_MIGRATION_ID, MEMORY_BACKUP_CATALOG_SQL, connection
            )
            self._apply_migration(MEMORY_JOBS_MIGRATION_ID, MEMORY_JOBS_SQL, connection)
            self._apply_migration(
                MEMORY_AUDIT_RATE_LIMIT_MIGRATION_ID, MEMORY_AUDIT_RATE_LIMIT_SQL, connection
            )
            self._rebuild_memory_fts(connection)
            for _alter_sql in (
                "ALTER TABLE api_sessions ADD COLUMN scope TEXT NOT NULL DEFAULT 'control'",
                "ALTER TABLE api_sessions ADD COLUMN absolute_expires_at TEXT",
                "ALTER TABLE api_sessions ADD COLUMN last_seen_at TEXT",
                "ALTER TABLE api_sessions ADD COLUMN device_label TEXT",
                "ALTER TABLE tasks ADD COLUMN priority TEXT",
                "ALTER TABLE tasks ADD COLUMN scheduled_at TEXT",
                "ALTER TABLE tasks ADD COLUMN recurrence TEXT",
                "ALTER TABLE tasks ADD COLUMN reminder_at TEXT",
                # Project-scoped schedules (backlog item 1): a task/schedule
                # belongs to the project it was created under, so project work
                # stays project-scoped. Organizing scope only — grants nothing.
                "ALTER TABLE tasks ADD COLUMN project_id TEXT REFERENCES projects(project_id)",
            ):
                with contextlib.suppress(sqlite3.OperationalError):
                    connection.execute(_alter_sql)

    def _migrate_plaintext_database(self) -> None:
        """Convert a legacy stdlib-SQLite file before SQLCipher opens it."""
        if not self.db_path.exists() or not self.db_path.read_bytes()[:16].startswith(b"SQLite format 3"):
            return
        import sqlite3 as plaintext_sqlite

        legacy_path = self.db_path.with_suffix(".plaintext-backup")
        self.db_path.replace(legacy_path)
        try:
            with plaintext_sqlite.connect(legacy_path) as source, self.connect() as encrypted:
                # SQLite dumps do not guarantee parent-before-child INSERT order.
                # Import under the legacy database's existing integrity state, then
                # restore enforcement for every normal Raiker connection.
                encrypted.execute("PRAGMA foreign_keys = OFF")
                # FTS virtual-table shadow rows are engine-specific. Rebuild this
                # disposable projection from approved memory after importing.
                dump = "\n".join(
                    line for line in source.iterdump() if "approved_memory_fts" not in line
                ).replace("USING fts5(", "USING fts4(")
                encrypted.executescript(dump)
                encrypted.execute("PRAGMA foreign_keys = ON")
            legacy_path.unlink()
        except Exception:
            if self.db_path.exists():
                self.db_path.unlink()
            legacy_path.replace(self.db_path)
            raise

    def _apply_migration(self, migration_id: str, sql: str, connection: sqlite3.Connection) -> None:
        row = connection.execute(
            "SELECT applied_at FROM migrations WHERE migration_id = ?", (migration_id,)
        ).fetchone()
        if row is not None:
            return
        with contextlib.suppress(sqlite3.OperationalError):
            connection.executescript(sql)
        connection.execute(
            "INSERT OR IGNORE INTO migrations (migration_id, applied_at) VALUES (?, ?)",
            (migration_id, utc_now()),
        )

    def _backfill_self_inclusive_project_paths(self, connection: sqlite3.Connection) -> None:
        """Derive paths from the authoritative adjacency list once per database."""
        if connection.execute(
            "SELECT 1 FROM migrations WHERE migration_id = ?",
            (PROJECT_SELF_INCLUSIVE_PATH_MIGRATION_ID,),
        ).fetchone() is not None:
            return
        rows = connection.execute("SELECT project_id, parent_id FROM projects").fetchall()
        parents = {str(row[0]): str(row[1]) if row[1] is not None else None for row in rows}
        paths: dict[str, str] = {}

        def resolve(project_id: str, visiting: set[str]) -> str:
            if project_id in paths:
                return paths[project_id]
            if project_id in visiting:
                raise RuntimeError("project_parent_cycle_detected")
            parent_id = parents[project_id]
            parent_path = "/" if parent_id is None else resolve(parent_id, visiting | {project_id})
            paths[project_id] = f"{parent_path}{project_id}/"
            return paths[project_id]

        for project_id in parents:
            resolve(project_id, set())
        connection.executemany(
            "UPDATE projects SET path = ?, updated_at = ? WHERE project_id = ?",
            [(path, utc_now(), project_id) for project_id, path in paths.items()],
        )
        connection.execute(
            "INSERT INTO migrations (migration_id, applied_at) VALUES (?, ?)",
            (PROJECT_SELF_INCLUSIVE_PATH_MIGRATION_ID, utc_now()),
        )

    def table_names(self) -> set[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        return {str(row["name"]) for row in rows}

    def create_session(self, session_id: str, project_root: str, title: str | None = None, user_id: str | None = None) -> None:
        now = utc_now()
        # New sessions are stamped with the active project (if any) so project
        # scoping needs no caller changes — an organizing label, not authority.
        project_id = self.get_active_project()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO sessions
                (session_id, project_root, created_at, updated_at, status, title, user_id, project_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, project_root, now, now, "open", title, user_id, project_id),
            )

    # ── Projects (web-app task 5: named organizing scopes, governance-neutral) ──

    ACTIVE_PROJECT_SCOPE = "local_single_user"

    def create_project(self, project_id: str, name: str, root_subpath: str, parent_id: str | None = None) -> None:
        with self.connect() as connection:
            if parent_id:
                parent = connection.execute("SELECT path FROM projects WHERE project_id = ?", (parent_id,)).fetchone()
                parent_path = parent["path"] if parent else "/"
                path = f"{parent_path}{project_id}/"
            else:
                path = f"/{project_id}/"
            connection.execute(
                "INSERT INTO projects (project_id, name, root_subpath, created_at, parent_id, path, is_archived, archived_at) VALUES (?, ?, ?, ?, ?, ?, 0, NULL)",
                (project_id, name, root_subpath, utc_now(), parent_id, path),
            )

    def load_project(self, project_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE project_id = ?", (project_id,)
            ).fetchone()
        return dict(row) if row else None

    def load_project_by_name(self, name: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE name = ?", (name,)
            ).fetchone()
        return dict(row) if row else None

    def load_project_context(self, project_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT instructions, attachment_ids_json, memory_enabled, memory_mode FROM project_contexts WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            return {"instructions": "", "attachment_ids": [], "memory_enabled": False, "memory_mode": "inherit"}
        try:
            attachment_ids = json.loads(str(row["attachment_ids_json"]))
        except (TypeError, ValueError):
            attachment_ids = []
        return {
            "instructions": str(row["instructions"]),
            "attachment_ids": [str(item) for item in attachment_ids if isinstance(item, str)],
            "memory_enabled": bool(row["memory_enabled"]),
            "memory_mode": str(row["memory_mode"]),
        }

    def save_project_context(
        self,
        project_id: str,
        *,
        instructions: str,
        attachment_ids: list[str],
        memory_enabled: bool | None = None,
        memory_mode: str | None = None,
    ) -> None:
        mode = memory_mode or ("enabled" if memory_enabled else "disabled")
        if mode not in {"inherit", "enabled", "disabled"}:
            raise ValueError("invalid_memory_mode")
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO project_contexts (project_id, instructions, attachment_ids_json, memory_enabled, memory_mode, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                  instructions = excluded.instructions,
                  attachment_ids_json = excluded.attachment_ids_json,
                  memory_enabled = excluded.memory_enabled,
                  memory_mode = excluded.memory_mode,
                  updated_at = excluded.updated_at
                """,
                (project_id, instructions, json.dumps(attachment_ids), int(mode == "enabled"), mode, utc_now()),
            )

    def list_projects(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT projects.*, COUNT(sessions.session_id) AS session_count
                FROM projects
                LEFT JOIN sessions ON sessions.project_id = projects.project_id
                GROUP BY projects.project_id
                ORDER BY projects.created_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_active_project(self) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT project_id FROM active_project WHERE scope_id = ?",
                (self.ACTIVE_PROJECT_SCOPE,),
            ).fetchone()
        return str(row["project_id"]) if row is not None and row["project_id"] else None

    def save_active_project(self, project_id: str | None) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO active_project (scope_id, project_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(scope_id) DO UPDATE SET project_id = excluded.project_id, updated_at = excluded.updated_at
                """,
                (self.ACTIVE_PROJECT_SCOPE, project_id, utc_now()),
            )

    def load_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_sessions(
        self, limit: int = 10, project_id: str | None = None, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM sessions"
        params: list[Any] = []
        conditions: list[str] = []
        if project_id is not None:
            conditions.append("project_id = ?")
            params.append(project_id)
        if user_id is not None:
            # An account sees its own sessions plus legacy/unattributed ones
            # (user_id IS NULL); another account's sessions stay hidden.
            conditions.append("(user_id = ? OR user_id IS NULL)")
            params.append(user_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def search_sessions(self, query: str, user_id: str | None = None) -> list[dict[str, Any]]:
        term = f"%{query}%"
        conditions = ["(sessions.title LIKE ? OR turns.prompt_text LIKE ? OR turns.summary LIKE ?)"]
        params: list[Any] = [term, term, term]
        if user_id is not None:
            conditions.append("(sessions.user_id = ? OR sessions.user_id IS NULL)")
            params.append(user_id)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT sessions.* FROM sessions
                LEFT JOIN turns ON turns.session_id = sessions.session_id
                WHERE """ + " AND ".join(conditions) + " GROUP BY sessions.session_id ORDER BY sessions.updated_at DESC",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_project(self, project_id: str) -> bool:
        with self.connect() as connection:
            session_ids = [r[0] for r in connection.execute("SELECT session_id FROM sessions WHERE project_id = ?", (project_id,))]
            if connection.execute("SELECT 1 FROM projects WHERE project_id = ?", (project_id,)).fetchone() is None:
                return False
            if session_ids:
                marks = ",".join("?" for _ in session_ids)
                action_ids = f"SELECT action_id FROM tool_actions WHERE session_id IN ({marks})"
                connection.execute(f"DELETE FROM policy_decisions WHERE action_id IN ({action_ids})", session_ids)
                for table in ("events_index", "tool_actions", "checkpoints", "tasks", "turns", "model_session_state", "model_fallback_sequence", "model_advisor", "session_tags"):
                    connection.execute(f"DELETE FROM {table} WHERE session_id IN ({marks})", session_ids)
                connection.execute(f"DELETE FROM sessions WHERE session_id IN ({marks})", session_ids)
            connection.execute("UPDATE active_project SET project_id = NULL WHERE project_id = ?", (project_id,))
            connection.execute("DELETE FROM project_contexts WHERE project_id = ?", (project_id,))
            connection.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
        return True

    # ── Nested projects/folders (conversation organisation remainder) ──────────
    # Arbitrary-depth folder hierarchy via hybrid adjacency list + materialized
    # path. Parent reference uses ON DELETE SET NULL so children survive parent
    # hard-delete. Path trigger auto-syncs on parent_id change. Partial index
    # on active tree for fast daily queries.

    def list_project_tree(self, include_archived: bool = False) -> list[dict[str, Any]]:
        """Return nested tree of projects (active by default)."""
        where = "" if include_archived else "WHERE is_archived = 0"
        with self.connect() as conn:
            rows = conn.execute(f"""
                SELECT * FROM projects {where} ORDER BY path, created_at
            """).fetchall()
        nodes = {row["project_id"]: {**dict(row), "children": []} for row in rows}
        roots = []
        for row in rows:
            node = nodes[row["project_id"]]
            if row["parent_id"] is None:
                roots.append(node)
            elif row["parent_id"] in nodes:
                nodes[row["parent_id"]]["children"].append(node)
        return roots

    def move_project(self, project_id: str, new_parent_id: str | None) -> bool:
        """Move project (and subtree) under new parent. Returns False if cycle or not found."""
        with self.connect() as conn:
            row = conn.execute("SELECT project_id, path FROM projects WHERE project_id = ?", (project_id,)).fetchone()
            if not row:
                return False
            old_path = row["path"]
            new_path = f"/{project_id}/"
            if new_parent_id:
                new_parent_row = conn.execute("SELECT path FROM projects WHERE project_id = ?", (new_parent_id,)).fetchone()
                if not new_parent_row:
                    return False
                new_parent_path = new_parent_row["path"]
                if new_parent_path.startswith(old_path):
                    return False  # would create cycle
                new_path = f"{new_parent_path}{project_id}/"
            conn.execute(
                "UPDATE projects SET path = ? || substr(path, ?), updated_at = ? WHERE path LIKE ?",
                (new_path, len(old_path) + 1, utc_now(), old_path + "%"),
            )
            conn.execute(
                "UPDATE projects SET parent_id = ?, updated_at = ? WHERE project_id = ?",
                (new_parent_id, utc_now(), project_id),
            )
        return True

    def archive_project(self, project_id: str) -> bool:
        """Soft-archive project and all descendants. Idempotent."""
        with self.connect() as conn:
            row = conn.execute("SELECT path FROM projects WHERE project_id = ?", (project_id,)).fetchone()
            if not row:
                return False
            path = row["path"]
            now = utc_now()
            conn.execute(
                "UPDATE projects SET is_archived = 1, archived_at = ?, updated_at = ? WHERE path LIKE ?",
                (now, now, path + "%"),
            )
        return True

    def delete_project_with_orphanage(self, project_id: str) -> bool:
        """Hard-delete project; archive descendants + reparent to NULL with orphaned/ path."""
        with self.connect() as conn:
            row = conn.execute("SELECT path FROM projects WHERE project_id = ?", (project_id,)).fetchone()
            if not row:
                return False
            path = row["path"]
            now = utc_now()
            # Delete sessions for target project (FK: ON DELETE NO ACTION)
            session_ids = [r[0] for r in conn.execute("SELECT session_id FROM sessions WHERE project_id = ?", (project_id,))]
            if session_ids:
                marks = ",".join("?" for _ in session_ids)
                action_ids = f"SELECT action_id FROM tool_actions WHERE session_id IN ({marks})"
                conn.execute(f"DELETE FROM policy_decisions WHERE action_id IN ({action_ids})", session_ids)
                for table in ("events_index", "tool_actions", "checkpoints", "tasks", "turns", "model_session_state", "model_fallback_sequence", "model_advisor", "session_tags"):
                    conn.execute(f"DELETE FROM {table} WHERE session_id IN ({marks})", session_ids)
                conn.execute(f"DELETE FROM sessions WHERE session_id IN ({marks})", session_ids)
            # 1) Archive descendants (excluding target)
            conn.execute(
                "UPDATE projects SET is_archived = 1, archived_at = ?, parent_id = CASE WHEN parent_id = ? THEN NULL ELSE parent_id END, path = '/orphaned/' || ? || '/' || substr(path, ?), updated_at = ? WHERE path LIKE ? AND project_id != ?",
                (now, project_id, project_id, len(path) + 1, now, path + "%", project_id),
            )
            conn.execute("UPDATE active_project SET project_id = NULL WHERE project_id = ?", (project_id,))
            # 2) Hard delete target (project_contexts cascades via ON DELETE CASCADE)
            conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
        return True

    def get_ancestor_contexts(self, project_id: str) -> list[dict[str, Any]]:
        """Return context rows for all active ancestors of project_id, ordered root→leaf."""
        with self.connect() as conn:
            target = conn.execute("SELECT path FROM projects WHERE project_id = ?", (project_id,)).fetchone()
            if not target:
                return []
            path = target["path"]
            rows = conn.execute("""
                SELECT pc.* FROM project_contexts pc
                JOIN projects p ON p.project_id = pc.project_id
                WHERE ? LIKE p.path || '%' AND p.project_id != ? AND p.is_archived = 0
                ORDER BY LENGTH(p.path) ASC
            """, (path, project_id)).fetchall()
        return [dict(r) for r in rows]

    def load_effective_project_context(self, project_id: str) -> dict[str, Any]:
        """Return the project's context merged with every active ancestor's.

        Instructions concatenate root→leaf so the nearest folder speaks last;
        attachment ids union in the same order; ``memory_enabled`` is the
        leaf's own value (an ancestor cannot opt a child into project memory).
        Archived ancestors contribute nothing. This is the single merge used by
        both the live context gatherer and the dashboard read path.
        """
        own = self.load_project_context(project_id)
        instructions: list[str] = []
        attachment_ids: list[str] = []
        memory_mode = "inherit"
        for ancestor in self.get_ancestor_contexts(project_id):
            text = str(ancestor.get("instructions") or "").strip()
            if text:
                instructions.append(text)
            raw = ancestor.get("attachment_ids_json")
            if raw:
                with contextlib.suppress(TypeError, ValueError):
                    attachment_ids.extend(
                        str(item) for item in json.loads(str(raw)) if isinstance(item, str)
                    )
            if ancestor.get("memory_mode") in {"enabled", "disabled"}:
                memory_mode = str(ancestor["memory_mode"])
        own_instructions = str(own.get("instructions") or "").strip()
        if own_instructions:
            instructions.append(own_instructions)
        attachment_ids.extend(own.get("attachment_ids", []))
        if own.get("memory_mode") in {"enabled", "disabled"}:
            memory_mode = str(own["memory_mode"])
        return {
            "instructions": "\n\n".join(instructions),
            "attachment_ids": list(dict.fromkeys(attachment_ids)),
            "memory_enabled": memory_mode == "enabled",
            "memory_mode": memory_mode,
        }

    def _session_owner(
        self, connection: sqlite3.Connection, session_id: str
    ) -> tuple[bool, str | None]:
        """Return (exists, owner_user_id). ``exists`` is False when the session
        does not exist; ``owner`` is None for legacy unattributed sessions."""
        row = connection.execute(
            "SELECT user_id FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return False, None
        return True, dict(row).get("user_id")

    def set_session_project(
        self, session_id: str, project_id: str | None, user_id: str | None = None
    ) -> bool:
        """Move one session into a project, or out of every project with
        ``project_id=None``. Returns False if the session does not exist or is
        owned by another account (user isolation mirrors set_session_pinned).
        The caller validates that ``project_id`` names a real project — a
        project is an organizing scope, so the move grants nothing; it only
        changes the bounded context the chat receives."""
        with self.connect() as connection:
            exists, owner = self._session_owner(connection, session_id)
            if not exists:
                return False
            if (
                user_id is not None
                and owner is not None
                and str(owner) != user_id
            ):
                return False
            connection.execute(
                "UPDATE sessions SET project_id = ?, updated_at = ? WHERE session_id = ?",
                (project_id, utc_now(), session_id),
            )
        return True

    def set_session_pinned(
        self, session_id: str, pinned: bool, user_id: str | None = None
    ) -> bool:
        """Pin (or unpin) a session. Returns False if the session does not exist
        or is owned by another account (user isolation mirrors list_sessions)."""
        with self.connect() as connection:
            exists, owner = self._session_owner(connection, session_id)
            if not exists:
                return False
            if (
                user_id is not None
                and owner is not None
                and str(owner) != user_id
            ):
                return False
            connection.execute(
                "UPDATE sessions SET pinned = ?, updated_at = ? WHERE session_id = ?",
                (1 if pinned else 0, utc_now(), session_id),
            )
        return True

    # ── Session tags (conversation organisation remainder) ─────────────────
    # A tag is an organizing label only (like the `pinned` flag and the
    # `projects` table) — it grants nothing and changes no gate, policy, or
    # authority. Many-to-many: a session carries an ordered set of tags; the
    # same tag may be reused across sessions. Setters are full-replace so the
    # caller's normalized list is the single source of truth. User/session
    # visibility mirrors set_session_pinned — an account cannot retag another
    # account's session.

    def list_session_tags(self, session_id: str) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT tag FROM session_tags WHERE session_id = ? ORDER BY tag",
                (session_id,),
            ).fetchall()
        return [str(row["tag"]) for row in rows]

    def set_session_tags(
        self, session_id: str, tags: list[str], user_id: str | None = None
    ) -> bool:
        """Full-replace the tag set for one session. ``tags`` is the already
        normalized, deduplicated, ordered list. Returns False if the session
        does not exist or is owned by another account (mirrors
        set_session_pinned). FK ON DELETE CASCADE keeps rows consistent if the
        session is removed out-of-band, but the explicit delete_session
        cascade also clears them."""
        with self.connect() as connection:
            exists, owner = self._session_owner(connection, session_id)
            if not exists:
                return False
            if (
                user_id is not None
                and owner is not None
                and str(owner) != user_id
            ):
                return False
            connection.execute(
                "DELETE FROM session_tags WHERE session_id = ?", (session_id,)
            )
            if tags:
                now = utc_now()
                connection.executemany(
                    "INSERT OR IGNORE INTO session_tags (session_id, tag, created_at) VALUES (?, ?, ?)",
                    [(session_id, tag, now) for tag in tags],
                )
            connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (utc_now(), session_id),
            )
        return True

    def delete_session(self, session_id: str, user_id: str | None = None) -> bool:
        """Delete one session and its cascaded rows (turns, events index, tool
        actions, policy decisions, checkpoints, tasks). Returns False if the
        session does not exist or is owned by another account. The per-session
        events JSONL file is removed too — it is the append-only transcript and
        must not be left orphaned. Mirrors delete_project's cascade scope."""
        with self.connect() as connection:
            exists, owner = self._session_owner(connection, session_id)
            if not exists:
                return False
            if (
                user_id is not None
                and owner is not None
                and str(owner) != user_id
            ):
                return False
            self._delete_session_rows(connection, session_id)
        # Remove the per-session events transcript file (best-effort; the db rows
        # above are already the source of truth and are committed).
        with contextlib.suppress(FileNotFoundError):
            (self.paths.events_dir / f"{session_id}.jsonl").unlink()
        return True

    @staticmethod
    def _delete_session_rows(connection: sqlite3.Connection, session_id: str) -> None:
        action_ids = "SELECT action_id FROM tool_actions WHERE session_id = ?"
        connection.execute(
            f"DELETE FROM policy_decisions WHERE action_id IN ({action_ids})", (session_id,)
        )
        for table in (
            "events_index", "tool_actions", "checkpoints", "tasks", "turns",
            "model_session_state", "model_fallback_sequence", "model_advisor", "session_tags",
        ):
            connection.execute(f"DELETE FROM {table} WHERE session_id = ?", (session_id,))
        connection.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

    def delete_sessions(self, session_ids: list[str], user_id: str | None = None) -> bool:
        """Atomically delete visible sessions and their cascaded rows."""
        if not session_ids or len(set(session_ids)) != len(session_ids):
            return False
        with self.connect() as connection:
            for session_id in session_ids:
                exists, owner = self._session_owner(connection, session_id)
                if not exists or (user_id is not None and owner is not None and str(owner) != user_id):
                    return False
            for session_id in session_ids:
                self._delete_session_rows(connection, session_id)
        for session_id in session_ids:
            with contextlib.suppress(FileNotFoundError):
                (self.paths.events_dir / f"{session_id}.jsonl").unlink()
        return True

    # ── Memory controls (backlog item 3) ──────────────────────────────────
    # memory_pins is an organizing label only (like session/project pins) —
    # it grants nothing and changes no authority. memory_settings.incognito
    # is a single-row flag (one scope) that, when on, withholds approved
    # project memory from the turn context (the context gatherer reads it).

    MEMORY_SETTINGS_SCOPE = "local_single_user"

    def set_memory_pinned(self, memory_id: str, pinned: bool) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO memory_pins (memory_id, pinned, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET pinned = excluded.pinned, updated_at = excluded.updated_at
                """,
                (memory_id, 1 if pinned else 0, utc_now()),
            )

    def list_pinned_memory_ids(self) -> set[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT memory_id FROM memory_pins WHERE pinned = 1"
            ).fetchall()
        return {str(row["memory_id"]) for row in rows}

    def is_memory_incognito(self) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT incognito FROM memory_settings WHERE scope_id = ?",
                (self.MEMORY_SETTINGS_SCOPE,),
            ).fetchone()
        return bool(row["incognito"]) if row is not None else False

    def set_memory_incognito(self, incognito: bool) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO memory_settings (scope_id, incognito, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(scope_id) DO UPDATE SET incognito = excluded.incognito, updated_at = excluded.updated_at
                """,
                (self.MEMORY_SETTINGS_SCOPE, 1 if incognito else 0, utc_now()),
            )

    def list_turns(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM turns WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def load_turn(self, turn_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
        return dict(row) if row else None

    def insert_turn(
        self, session_id: str, turn_id: str, prompt_text: str, status: str = "running"
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO turns
                (turn_id, session_id, turn_type, status, prompt_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (turn_id, session_id, "prompt", status, prompt_text, utc_now()),
            )

    def complete_turn(self, turn_id: str, status: str, summary: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE turns SET status = ?, completed_at = ?, summary = ? WHERE turn_id = ?",
                (status, utc_now(), summary, turn_id),
            )

    def index_event(
        self, event: AgentEvent, jsonl_path: str, jsonl_offset: int, payload_sha256: str,
        prev_event_sha256: str | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO events_index
                (event_id, session_id, turn_id, task_id, event_type, actor, timestamp, jsonl_path, jsonl_offset, payload_sha256, prev_event_sha256, risk_level, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.session_id,
                    event.turn_id,
                    event.payload.get("task_id"),
                    event.event_type,
                    event.actor,
                    event.timestamp,
                    jsonl_path,
                    jsonl_offset,
                    payload_sha256,
                    prev_event_sha256,
                    event.payload.get("risk_level"),
                    event.payload.get("summary"),
                ),
            )

    @staticmethod
    def tool_action_payload_sha256(tool_name: str, arguments_json: str, risk_level: str) -> str:
        payload = json.dumps(
            {
                "tool_name": tool_name,
                "arguments": json.loads(arguments_json),
                "risk_level": risk_level,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def insert_tool_action(
        self, action: ToolAction, session_id: str, turn_id: str | None, status: str
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO tool_actions
                (action_id, session_id, turn_id, task_id, tool_name, arguments_json, risk_level, status, proposed_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT proposed_at FROM tool_actions WHERE action_id = ?), ?), ?)
                """,
                (
                    action.action_id,
                    session_id,
                    turn_id,
                    None,
                    action.tool_name,
                    json.dumps(action.arguments, sort_keys=True),
                    action.risk_level,
                    status,
                    action.action_id,
                    utc_now(),
                    utc_now()
                    if status in {"success", "failed", "denied", "approval_required"}
                    else None,
                ),
            )

    def load_tool_action(self, action_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM tool_actions WHERE action_id = ?", (action_id,)
            ).fetchone()
        return dict(row) if row else None

    def insert_policy_decision(self, decision: PolicyDecision) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO policy_decisions
                (decision_id, action_id, decision, reasons_json, policy_version, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.decision_id,
                    decision.action_id,
                    decision.decision,
                    json.dumps(decision.reasons),
                    decision.policy_version,
                    decision.timestamp or utc_now(),
                ),
            )

    def insert_approval(
        self, approval_id: str, action: ToolAction | str, status: str = "pending"
    ) -> None:
        if isinstance(action, ToolAction):
            action_id = action.action_id
            payload_hash = self.tool_action_payload_sha256(
                action.tool_name,
                json.dumps(action.arguments, sort_keys=True),
                action.risk_level,
            )
        else:
            action_id = action
            row = self.load_tool_action(action_id)
            if row is None:
                raise ValueError(f"unknown_tool_action:{action_id}")
            payload_hash = self.tool_action_payload_sha256(
                str(row["tool_name"]),
                str(row["arguments_json"]),
                str(row["risk_level"]),
            )
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO approvals
                (approval_id, action_id, status, approval_scope, created_at, action_payload_sha256)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (approval_id, action_id, status, "action", utc_now(), payload_hash),
            )

    def insert_checkpoint(self, checkpoint: Checkpoint, manifest_path: str) -> None:
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

    def upsert_model_profiles(self, profiles: list[ModelProfile]) -> None:
        now = utc_now()
        with self.connect() as connection:
            for profile in profiles:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO model_profiles
                    (profile_id, provider, model, build_phase, default_state, profile_json, loaded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        profile.profile_id,
                        profile.provider,
                        profile.model,
                        profile.build_phase,
                        profile.default_state,
                        json.dumps(profile.raw, sort_keys=True),
                        now,
                    ),
                )

    def upsert_connector_profiles(self, profiles: list[ConnectorProfile]) -> None:
        now = utc_now()
        with self.connect() as connection:
            for profile in profiles:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO connector_profiles
                    (connector_id, channel_type, display_name, build_phase, default_state, interface_status, profile_json, loaded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        profile.connector_id,
                        profile.channel_type,
                        profile.display_name,
                        profile.build_phase,
                        profile.default_state,
                        profile.interface_status,
                        json.dumps(profile.raw, sort_keys=True),
                        now,
                    ),
                )

    def insert_task(self, task: TaskRecord) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO tasks
                (task_id, session_id, parent_turn_id, parent_task_id, title, objective, status, current_step, progress_percent, created_at, updated_at, completed_at, priority, scheduled_at, recurrence, reminder_at, project_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.session_id,
                    task.parent_turn_id,
                    task.parent_task_id,
                    task.title,
                    task.objective,
                    task.status,
                    task.current_step,
                    task.progress_percent,
                    task.created_at,
                    task.updated_at,
                    task.completed_at,
                    task.priority,
                    task.scheduled_at,
                    task.recurrence,
                    task.reminder_at,
                    task.project_id,
                ),
            )

    def load_task(self, task_id: str) -> TaskRecord | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        return TaskRecord(**dict(row))

    def list_tasks(
        self,
        session_id: str | None = None,
        status: str | None = None,
        user_id: str | None = None,
        project_id: str | None = None,
    ) -> list[TaskRecord]:
        query = "SELECT * FROM tasks"
        params: list[Any] = []
        conditions: list[str] = []
        if session_id is not None:
            conditions.append("session_id = ?")
            params.append(session_id)
        if project_id is not None:
            # Project-scoped schedules: a project's task list shows only the
            # tasks created under that project.
            conditions.append("project_id = ?")
            params.append(project_id)
        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        if user_id is not None:
            # Only tasks whose owning session is visible to this account
            # (its own sessions plus legacy/unattributed ones).
            conditions.append(
                "session_id IN (SELECT session_id FROM sessions "
                "WHERE user_id = ? OR user_id IS NULL)"
            )
            params.append(user_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [TaskRecord(**dict(row)) for row in rows]

    def _update_task(self, task_id: str, **updates: str | int | None) -> None:
        now = utc_now()
        updates["updated_at"] = now
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [task_id]
        with self.connect() as connection:
            connection.execute(f"UPDATE tasks SET {set_clause} WHERE task_id = ?", values)

    def update_task_progress(self, task_id: str, current_step: str, progress_percent: int) -> None:
        self._update_task(task_id, current_step=current_step, progress_percent=progress_percent)

    def complete_task(self, task_id: str, summary: str | None = None) -> None:
        now = utc_now()
        self._update_task(task_id, status="completed", completed_at=now, summary=summary)

    def fail_task(self, task_id: str, reason: str) -> None:
        now = utc_now()
        self._update_task(task_id, status="failed", completed_at=now, summary=reason)

    def cancel_task(self, task_id: str, reason: str) -> None:
        now = utc_now()
        self._update_task(task_id, status="cancelled", completed_at=now, summary=reason)

    def list_event_index(
        self,
        session_id: str | None = None,
        turn_id: str | None = None,
        task_id: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
        project_id: str | None = None,
        user_id: str | None = None,
        apply_user_visibility_filter: bool = False,
    ) -> list[dict]:
        query = "SELECT * FROM events_index"
        params: list[Any] = []
        conditions: list[str] = []
        if session_id is not None:
            conditions.append("session_id = ?")
            params.append(session_id)
        if turn_id is not None:
            conditions.append("turn_id = ?")
            params.append(turn_id)
        if task_id is not None:
            conditions.append("task_id = ?")
            params.append(task_id)
        if event_type is not None:
            conditions.append("event_type = ?")
            params.append(event_type)
        if project_id is not None:
            conditions.append(
                "session_id IN (SELECT session_id FROM sessions WHERE project_id = ?)"
            )
            params.append(project_id)
        if apply_user_visibility_filter:
            if user_id is None:
                conditions.append(
                    "session_id IN (SELECT session_id FROM sessions WHERE user_id IS NULL)"
                )
            else:
                conditions.append(
                    "session_id IN (SELECT session_id FROM sessions "
                    "WHERE user_id = ? OR user_id IS NULL)"
                )
                params.append(user_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(str(limit))
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def count_events(self, session_id: str | None = None) -> int:
        query = "SELECT COUNT(*) AS cnt FROM events_index"
        params: list[Any] = []
        if session_id is not None:
            query += " WHERE session_id = ?"
            params.append(session_id)
        with self.connect() as connection:
            row = connection.execute(query, params).fetchone()
        return int(row["cnt"]) if row else 0

    def count_checkpoints(self, session_id: str | None = None) -> int:
        query = "SELECT COUNT(*) AS cnt FROM checkpoints"
        params: list[Any] = []
        if session_id is not None:
            query += " WHERE session_id = ?"
            params.append(session_id)
        with self.connect() as connection:
            row = connection.execute(query, params).fetchone()
        return int(row["cnt"]) if row else 0

    def count_tasks(self, session_id: str | None = None) -> int:
        query = "SELECT COUNT(*) AS cnt FROM tasks"
        params: list[Any] = []
        if session_id is not None:
            query += " WHERE session_id = ?"
            params.append(session_id)
        with self.connect() as connection:
            row = connection.execute(query, params).fetchone()
        return int(row["cnt"]) if row else 0

    def count_pending_approvals(self) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS cnt FROM approvals WHERE status = 'pending'"
            ).fetchone()
        return int(row["cnt"]) if row else 0

    def load_event_index(self, event_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM events_index WHERE event_id = ?", (event_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_checkpoints(
        self, session_id: str | None = None, limit: int = 50, project_id: str | None = None
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

    def load_checkpoint_by_id(self, checkpoint_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_approvals(self, status: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT approvals.*, tool_actions.session_id, tool_actions.turn_id, tool_actions.tool_name, tool_actions.arguments_json, tool_actions.risk_level
            FROM approvals
            JOIN tool_actions ON approvals.action_id = tool_actions.action_id
        """
        params: list[Any] = []
        if status is not None:
            query += " WHERE approvals.status = ?"
            params.append(status)
        query += " ORDER BY approvals.created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def load_approval(self, approval_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT approvals.*, tool_actions.session_id, tool_actions.turn_id, tool_actions.tool_name, tool_actions.arguments_json, tool_actions.risk_level
                FROM approvals
                JOIN tool_actions ON approvals.action_id = tool_actions.action_id
                WHERE approval_id = ?
                """,
                (approval_id,),
            ).fetchone()
        return dict(row) if row else None

    def resolve_approval(
        self, approval_id: str, *, status: str, resolved_by: str, resolved_at: str
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE approvals SET status = ?, approved_by = ?, resolved_at = ? WHERE approval_id = ? AND status = 'pending'",
                (status, resolved_by, resolved_at, approval_id),
            )

    def update_task_status(self, task_id: str, status: str) -> None:
        self._update_task(task_id, status=status)

    def insert_memory_candidate(self, candidate: Any) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO memory_candidates
                (candidate_id, source_event_id, memory_type, scope, text, sensitivity, confidence, decision, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.candidate_id,
                    candidate.source_event_id,
                    candidate.memory_type,
                    candidate.scope,
                    candidate.text,
                    candidate.sensitivity,
                    candidate.confidence,
                    candidate.decision,
                    candidate.created_at,
                ),
            )

    def list_memory_candidates(self, decision: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM memory_candidates"
        params: list[Any] = []
        if decision is not None:
            query += " WHERE decision = ?"
            params.append(decision)
        query += " ORDER BY created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def insert_approved_memory(self, entry: Any) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO approved_memory
                (memory_id, text, scope, sensitivity, source_event_id, memory_type, created_at, tags_json, source, provenance_json, confidence, trust_score, retention, approval_state, created_by, updated_at, deleted_at, archived_at, search_enabled, expires_at, valid_from, valid_until, supersedes_memory_id, superseded_at, remembered_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.memory_id,
                    entry.text,
                    entry.scope,
                    entry.sensitivity,
                    entry.source_event_id,
                    entry.memory_type,
                    entry.created_at,
                    json.dumps(list(entry.tags)),
                    entry.source,
                    json.dumps(entry.provenance, sort_keys=True),
                    entry.confidence,
                    entry.trust_score,
                    entry.retention,
                    entry.approval_state,
                    entry.created_by,
                    entry.updated_at,
                    entry.deleted_at,
                    entry.archived_at,
                    int(entry.search_enabled),
                    entry.expires_at,
                    entry.valid_from or entry.created_at,
                    entry.valid_until,
                    entry.supersedes_memory_id,
                    entry.superseded_at,
                    entry.remembered_reason,
                ),
            )
            self._sync_memory_fts(connection, entry.memory_id)

    def update_approved_memory(self, entry: Any) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE approved_memory SET text = ?, sensitivity = ?, tags_json = ?, updated_at = ?,
                search_enabled = ?, expires_at = ?, valid_from = ?, valid_until = ?,
                supersedes_memory_id = ?, superseded_at = ?, remembered_reason = ?
                WHERE memory_id = ? AND deleted_at IS NULL""",
                (
                    entry.text,
                    entry.sensitivity,
                    json.dumps(list(entry.tags)),
                    entry.updated_at,
                    int(entry.search_enabled),
                    entry.expires_at,
                    entry.valid_from or entry.created_at,
                    entry.valid_until,
                    entry.supersedes_memory_id,
                    entry.superseded_at,
                    entry.remembered_reason,
                    entry.memory_id,
                ),
            )
            self._sync_memory_fts(connection, entry.memory_id)
        return cursor.rowcount > 0

    def supersede_approved_memory(self, memory_id: str, replacement_id: str, *, at: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE approved_memory SET approval_state = 'superseded', valid_until = ?, superseded_at = ?,
                updated_at = ? WHERE memory_id = ? AND deleted_at IS NULL AND superseded_at IS NULL""",
                (at, at, at, memory_id),
            )
            self._sync_memory_fts(connection, memory_id)
            connection.execute(
                "UPDATE approved_memory SET supersedes_memory_id = ? WHERE memory_id = ?",
                (memory_id, replacement_id),
            )
        return cursor.rowcount > 0

    def create_memory_evaluation_run(self, report: Any, *, strategy: str = "lexical_fts") -> str:
        from raiker.contracts.ids import new_id

        evaluation_id = new_id("mev_")
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO memory_evaluation_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (evaluation_id, report.corpus_version, strategy, report.case_count, report.precision_at_k,
                 report.recall_at_k, report.mean_reciprocal_rank, report.ndcg_at_k,
                 report.policy_leak_count, report.p50_latency_ms, report.p95_latency_ms,
                 report.token_count, report.compute_cost_usd, report.storage_bytes, utc_now()),
            )
        return evaluation_id

    def upsert_memory_entity(self, entity_id: str, name: str, entity_type: str) -> None:
        normalized_name = " ".join(name.casefold().split())
        if not normalized_name or not entity_type.strip():
            raise ValueError("invalid_memory_entity")
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO memory_entities VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(normalized_name, entity_type) DO UPDATE SET display_name = excluded.display_name, updated_at = excluded.updated_at""",
                (entity_id, normalized_name, name.strip(), entity_type.strip(), now, now),
            )

    def link_memory_entities(
        self, relationship_id: str, subject_entity_id: str, predicate: str, object_entity_id: str,
        evidence_memory_id: str, confidence: float,
    ) -> None:
        if not predicate.strip() or not 0 <= confidence <= 1 or self.get_active_approved_memory(evidence_memory_id) is None:
            raise ValueError("invalid_memory_relationship")
        with self.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO memory_entity_relationships VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
                (relationship_id, subject_entity_id, predicate.strip(), object_entity_id, evidence_memory_id, confidence, utc_now()),
            )
        self.link_memory_projection(evidence_memory_id, "graph", relationship_id, "memory-entity-v1")

    def list_memory_entity_neighborhood(self, entity_id: str, scope: str | None = None) -> list[dict[str, Any]]:
        now = utc_now()
        query = """SELECT r.*, s.display_name AS subject_name, o.display_name AS object_name
        FROM memory_entity_relationships r JOIN memory_entities s ON s.entity_id = r.subject_entity_id
        JOIN memory_entities o ON o.entity_id = r.object_entity_id
        JOIN approved_memory m ON m.memory_id = r.evidence_memory_id
        WHERE r.active = 1 AND (r.subject_entity_id = ? OR r.object_entity_id = ?)
          AND m.deleted_at IS NULL AND m.archived_at IS NULL AND m.search_enabled = 1
          AND (m.expires_at IS NULL OR m.expires_at > ?) AND m.superseded_at IS NULL"""
        params: list[Any] = [entity_id, entity_id, now]
        if scope:
            query += " AND m.scope = ?"
            params.append(scope)
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def mark_approved_memory_forgotten(
        self, memory_id: str, *, deleted_at: str, updated_at: str
    ) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE approved_memory
                SET approval_state = ?, deleted_at = ?, updated_at = ?
                WHERE memory_id = ? AND deleted_at IS NULL
                """,
                ("forgotten", deleted_at, updated_at, memory_id),
            )
            self._sync_memory_fts(connection, memory_id)
        return cursor.rowcount > 0

    def set_approved_memory_archived(self, memory_id: str, *, archived_at: str | None, updated_at: str | None) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE approved_memory SET archived_at = ?, updated_at = ? WHERE memory_id = ? AND deleted_at IS NULL",
                (archived_at, updated_at, memory_id),
            )
            self._sync_memory_fts(connection, memory_id)
        return cursor.rowcount > 0

    def create_memory_purge_record(self, purge_id: str, memory_id: str, requested_by: str, confirmed_at: str, disposition: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute("INSERT INTO memory_purge_records (purge_id, memory_id, requested_by, confirmed_at, disposition_json) VALUES (?, ?, ?, ?, ?)", (purge_id, memory_id, requested_by, confirmed_at, json.dumps(disposition, sort_keys=True)))

    def deactivate_memory_projections(self, memory_id: str) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE memory_projections SET active = 0 WHERE memory_id = ?", (memory_id,))

    def set_memory_projections_active(self, memory_id: str, active: bool) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE memory_projections SET active = ? WHERE memory_id = ?", (int(active), memory_id))

    def link_memory_projection(self, memory_id: str, projection_type: str, projection_id: str, source_version: str) -> None:
        if projection_type not in {"fts", "vector", "graph"}:
            raise ValueError("invalid_memory_projection_type")
        with self.connect() as connection:
            row = connection.execute("SELECT deleted_at, archived_at FROM approved_memory WHERE memory_id = ?", (memory_id,)).fetchone()
            if row is None:
                raise ValueError("unknown_memory")
            connection.execute(
                "INSERT OR REPLACE INTO memory_projections (memory_id, projection_type, projection_id, source_version, active) VALUES (?, ?, ?, ?, ?)",
                (memory_id, projection_type, projection_id, source_version, int(row["deleted_at"] is None and row["archived_at"] is None)),
            )

    def list_memory_projections(self, memory_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM memory_projections WHERE memory_id = ? ORDER BY projection_type, projection_id", (memory_id,)).fetchall()
        return [dict(row) for row in rows]

    def get_active_approved_memory(self, memory_id: str) -> dict[str, Any] | None:
        now = utc_now()
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM approved_memory WHERE memory_id = ? AND deleted_at IS NULL
                AND archived_at IS NULL AND search_enabled = 1
                AND (expires_at IS NULL OR expires_at > ?)
                AND (valid_from IS NULL OR valid_from <= ?)
                AND (valid_until IS NULL OR valid_until > ?) AND superseded_at IS NULL""",
                (memory_id, now, now, now),
            ).fetchone()
        return dict(row) if row else None

    def reconcile_memory_projections(self) -> dict[str, int]:
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE memory_projections SET active = CASE WHEN EXISTS (
                    SELECT 1 FROM approved_memory m WHERE m.memory_id = memory_projections.memory_id
                    AND m.deleted_at IS NULL AND m.archived_at IS NULL
                ) THEN 1 ELSE 0 END"""
            )
            self._rebuild_memory_fts(connection)
        return {"projection_rows_reconciled": cursor.rowcount}

    @staticmethod
    def _sync_memory_fts(connection: sqlite3.Connection, memory_id: str) -> None:
        connection.execute("DELETE FROM approved_memory_fts WHERE memory_id = ?", (memory_id,))
        connection.execute(
            """INSERT INTO approved_memory_fts(memory_id, text, tags)
            SELECT memory_id, text, tags_json FROM approved_memory
            WHERE memory_id = ? AND deleted_at IS NULL AND archived_at IS NULL
              AND search_enabled = 1 AND (expires_at IS NULL OR expires_at > ?)
              AND (valid_from IS NULL OR valid_from <= ?) AND (valid_until IS NULL OR valid_until > ?)
              AND superseded_at IS NULL""",
            (memory_id, utc_now(), utc_now(), utc_now()),
        )

    @staticmethod
    def _rebuild_memory_fts(connection: sqlite3.Connection) -> None:
        try:
            connection.execute("DELETE FROM approved_memory_fts")
        except sqlite3.OperationalError:
            # Repair a legacy FTS5 dump that was imported by an older SQLCipher
            # migration. The FTS table is a rebuildable projection, never source.
            connection.execute("DROP TABLE IF EXISTS approved_memory_fts")
            connection.execute(
                "CREATE VIRTUAL TABLE approved_memory_fts USING fts4("
                "memory_id UNINDEXED, text, tags)"
            )
        connection.execute("""INSERT INTO approved_memory_fts(memory_id, text, tags)
            SELECT memory_id, text, tags_json FROM approved_memory
            WHERE deleted_at IS NULL AND archived_at IS NULL AND search_enabled = 1
              AND (expires_at IS NULL OR expires_at > ?)
              AND (valid_from IS NULL OR valid_from <= ?) AND (valid_until IS NULL OR valid_until > ?)
              AND superseded_at IS NULL""", (utc_now(), utc_now(), utc_now()))

    def search_approved_memory(self, query: str, scope: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        terms = [term for term in query.replace('"', " ").replace("-", " ").split() if len(term) >= 3]
        if not terms:
            return []
        sql = """SELECT m.* FROM approved_memory_fts f JOIN approved_memory m ON m.memory_id = f.memory_id
        WHERE approved_memory_fts MATCH ? AND m.deleted_at IS NULL AND m.archived_at IS NULL
          AND m.search_enabled = 1 AND (m.expires_at IS NULL OR m.expires_at > ?)
          AND (m.valid_from IS NULL OR m.valid_from <= ?) AND (m.valid_until IS NULL OR m.valid_until > ?)
          AND m.superseded_at IS NULL"""
        now = utc_now()
        params: list[Any] = [" ".join(terms), now, now, now]
        if scope is not None:
            sql += " AND m.scope = ?"
            params.append(scope)
        sql += " ORDER BY m.created_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def delete_approved_memory(self, memory_id: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM approved_memory_fts WHERE memory_id = ?", (memory_id,))
            connection.execute("DELETE FROM approved_memory WHERE memory_id = ?", (memory_id,))

    def list_approved_memory(self, scope: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        query = "SELECT * FROM approved_memory WHERE deleted_at IS NULL AND archived_at IS NULL AND search_enabled = 1 AND (expires_at IS NULL OR expires_at > ?)"
        params: list[Any] = [utc_now()]
        if scope is not None:
            query += " AND scope = ?"
            params.append(scope)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def save_model_session_state(self, state: ModelSessionState) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO model_session_state
                (session_id, profile_id, model, reasoning_enabled, reasoning_effort, reasoning_mode, reasoning_budget_tokens, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (state.session_id, state.profile_id, state.model, int(state.reasoning_enabled), state.reasoning_effort, state.reasoning_mode, state.reasoning_budget_tokens, utc_now()),
            )

    def insert_managed_policy(self, rule: ManagedPolicyRule) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO managed_policies
                (rule_id, effect, tool_pattern, arguments_json, priority, enabled, reason, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule.rule_id,
                    rule.effect,
                    rule.tool_pattern,
                    rule.arguments_json,
                    rule.priority,
                    int(rule.enabled),
                    rule.reason,
                    rule.created_by,
                    rule.created_at,
                    rule.updated_at,
                ),
            )

    def list_managed_policies(self, enabled_only: bool = True) -> list[dict[str, Any]]:
        query = "SELECT * FROM managed_policies"
        params: list[Any] = []
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY priority ASC, created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def insert_user(self, user: User) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO users
                (user_id, display_name, email, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user.user_id,
                    user.display_name,
                    user.email,
                    int(user.is_active),
                    user.created_at,
                    user.updated_at,
                ),
            )

    def list_users(self, active_only: bool = True) -> list[dict[str, Any]]:
        query = "SELECT * FROM users"
        params: list[Any] = []
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def load_user(self, user_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        return dict(row) if row else None

    def deactivate_user(self, user_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE users SET is_active = 0, updated_at = ? WHERE user_id = ? AND is_active = 1",
                (utc_now(), user_id),
            )
        return cursor.rowcount > 0

    def insert_role(self, role: Role) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO roles
                (role_id, name, description, is_system_role, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    role.role_id,
                    role.name,
                    role.description,
                    int(role.is_system_role),
                    role.created_at,
                ),
            )

    def list_roles(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM roles ORDER BY is_system_role DESC, name ASC"
            ).fetchall()
        return [dict(row) for row in rows]

    def load_role(self, role_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM roles WHERE role_id = ?", (role_id,)
            ).fetchone()
        return dict(row) if row else None

    def delete_role(self, role_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM roles WHERE role_id = ? AND is_system_role = 0",
                (role_id,),
            )
        return cursor.rowcount > 0

    def insert_user_role_assignment(self, assignment: UserRoleAssignment) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO user_role_assignments
                (assignment_id, user_id, role_id, granted_at, granted_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    assignment.assignment_id,
                    assignment.user_id,
                    assignment.role_id,
                    assignment.granted_at,
                    assignment.granted_by,
                ),
            )

    def list_user_roles(self, user_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT ura.*, r.name AS role_name, r.description AS role_description
                FROM user_role_assignments ura
                JOIN roles r ON ura.role_id = r.role_id
                WHERE ura.user_id = ?
                ORDER BY ura.granted_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_user_role_assignment(self, assignment_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM user_role_assignments WHERE assignment_id = ?",
                (assignment_id,),
            )
        return cursor.rowcount > 0

    def insert_audit_export(self, manifest: ExportManifest) -> None:
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

    def list_audit_exports(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_exports ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def load_audit_export(self, export_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM audit_exports WHERE export_id = ?", (export_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_last_event_sha256(self, session_id: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_sha256 FROM events_index WHERE session_id = ? ORDER BY timestamp DESC LIMIT 1",
                (session_id,),
            ).fetchone()
        return str(row["payload_sha256"]) if row else None

    def list_session_events_for_integrity(
        self, session_id: str
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT event_id, payload_sha256, prev_event_sha256, jsonl_path, jsonl_offset FROM events_index WHERE session_id = ? ORDER BY jsonl_offset ASC",
                (session_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def insert_plugin_install_record(self, record: PluginInstallRecord) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO plugin_install_records
                (record_id, plugin_id, version, trust_level, checksum, signature, source_url, commit_sha, permissions_json, status, installed_at, installed_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.record_id,
                    record.plugin_id,
                    record.version,
                    record.trust_level,
                    record.checksum,
                    record.signature,
                    record.source_url,
                    record.commit_sha,
                    record.permissions_json,
                    record.status,
                    record.installed_at,
                    record.installed_by,
                ),
            )

    def list_plugin_install_records(self, status: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM plugin_install_records"
        params: list[Any] = []
        if status is not None:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY installed_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def load_plugin_install_record(self, record_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM plugin_install_records WHERE record_id = ?", (record_id,)
            ).fetchone()
        return dict(row) if row else None

    def revoke_plugin_install_record(self, record_id: str) -> bool:
        """Flip an install record's status from ``installed`` to ``revoked``.

        Returns True only if a currently-installed record was updated. This is
        the fail-closed off-switch for the plugin install/execution slices; it
        never deletes the record or touches permissions.
        """
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE plugin_install_records SET status = 'revoked' "
                "WHERE record_id = ? AND status = 'installed'",
                (record_id,),
            )
        return cursor.rowcount > 0

    def insert_hosted_routine(self, routine: HostedRoutine) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO hosted_routines
                (routine_id, name, routine_type, schedule, endpoint, enabled, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (routine.routine_id, routine.name, routine.routine_type, routine.schedule, routine.endpoint, int(routine.enabled), routine.created_by, routine.created_at, routine.updated_at),
            )

    def list_hosted_routines(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM hosted_routines"
        params: list[Any] = []
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def delete_hosted_routine(self, routine_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM hosted_routines WHERE routine_id = ?", (routine_id,)
            )
        return cursor.rowcount > 0

    def insert_budget_record(self, budget: BudgetRecord) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO budget_records
                (budget_id, name, max_cost, current_cost, currency, scope, enabled, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (budget.budget_id, budget.name, budget.max_cost, budget.current_cost, budget.currency, budget.scope, int(budget.enabled), budget.created_by, budget.created_at, budget.updated_at),
            )

    def list_budget_records(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM budget_records"
        params: list[Any] = []
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def load_budget_record(self, budget_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM budget_records WHERE budget_id = ?", (budget_id,)
            ).fetchone()
        return dict(row) if row else None

    def update_budget_cost(self, budget_id: str, additional_cost: float) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE budget_records SET current_cost = current_cost + ?, updated_at = ? WHERE budget_id = ?",
                (additional_cost, utc_now(), budget_id),
            )
        return cursor.rowcount > 0

    def insert_retention_policy(self, policy: RetentionPolicy) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO retention_policies
                (policy_id, target_type, retention_days, legal_hold, enabled, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (policy.policy_id, policy.target_type, policy.retention_days, int(policy.legal_hold), int(policy.enabled), policy.created_by, policy.created_at, policy.updated_at),
            )

    def list_retention_policies(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM retention_policies"
        params: list[Any] = []
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def insert_backup_manifest(self, manifest: BackupManifest) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO backup_manifests
                (manifest_id, backup_type, scope_json, path, checksum, size_bytes, created_by, created_at,
                 encryption_key_id, retention_until, legal_hold, erasure_requested_at, erased_at, restore_verified_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (manifest.manifest_id, manifest.backup_type, manifest.scope_json, manifest.path, manifest.checksum, manifest.size_bytes, manifest.created_by, manifest.created_at, manifest.encryption_key_id, manifest.retention_until, int(manifest.legal_hold), manifest.erasure_requested_at, manifest.erased_at, manifest.restore_verified_at),
            )

    def list_backup_manifests(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM backup_manifests ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def request_backup_erasure(self, manifest_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE backup_manifests SET erasure_requested_at = ? WHERE manifest_id = ? AND legal_hold = 0 AND erased_at IS NULL",
                (utc_now(), manifest_id),
            )
        return cursor.rowcount > 0

    def record_backup_erased(self, manifest_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE backup_manifests SET erased_at = ? WHERE manifest_id = ? AND erasure_requested_at IS NOT NULL AND legal_hold = 0",
                (utc_now(), manifest_id),
            )
        return cursor.rowcount > 0

    def record_backup_restore_verified(self, manifest_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE backup_manifests SET restore_verified_at = ? WHERE manifest_id = ? AND erased_at IS NULL",
                (utc_now(), manifest_id),
            )
        return cursor.rowcount > 0

    def enqueue_memory_job(self, job_type: str, dedup_key: str, max_attempts: int = 3) -> str:
        from raiker.contracts.ids import new_id

        if job_type not in {"reconcile", "integrity_scan"} or not dedup_key or max_attempts < 1:
            raise ValueError("invalid_memory_job")
        now = utc_now()
        job_id = new_id("mjob_")
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO memory_jobs VALUES (?, ?, ?, 'queued', 0, ?, NULL, NULL, ?, ?)
                ON CONFLICT(job_type, dedup_key) DO NOTHING""",
                (job_id, job_type, dedup_key, max_attempts, now, now),
            )
            row = connection.execute(
                "SELECT job_id FROM memory_jobs WHERE job_type = ? AND dedup_key = ?", (job_type, dedup_key)
            ).fetchone()
        return str(row["job_id"])

    def claim_memory_job(self, lease_until: str) -> dict[str, Any] | None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT * FROM memory_jobs WHERE status IN ('queued', 'retry')
                OR (status = 'running' AND lease_until < ?) ORDER BY created_at LIMIT 1""", (now,)
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "UPDATE memory_jobs SET status = 'running', attempts = attempts + 1, lease_until = ?, updated_at = ? WHERE job_id = ?",
                (lease_until, now, row["job_id"]),
            )
            claimed = connection.execute("SELECT * FROM memory_jobs WHERE job_id = ?", (row["job_id"],)).fetchone()
        return dict(claimed) if claimed else None

    def finish_memory_job(self, job_id: str, error: str | None = None) -> bool:
        now = utc_now()
        with self.connect() as connection:
            if error is None:
                cursor = connection.execute(
                    "UPDATE memory_jobs SET status = 'completed', lease_until = NULL, updated_at = ? WHERE job_id = ? AND status = 'running'", (now, job_id)
                )
            else:
                cursor = connection.execute(
                    """UPDATE memory_jobs SET status = CASE WHEN attempts >= max_attempts THEN 'dead_letter' ELSE 'retry' END,
                    lease_until = NULL, last_error = ?, updated_at = ? WHERE job_id = ? AND status = 'running'""",
                    (error[:500], now, job_id),
                )
        return cursor.rowcount > 0

    def consume_memory_job_rate_limit(self, job_type: str, *, limit_per_minute: int) -> bool:
        if limit_per_minute < 1:
            raise ValueError("invalid_memory_job_rate_limit")
        window = utc_now()[:16] + ":00Z"
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT count FROM memory_job_rate_windows WHERE job_type = ? AND window_started_at = ?", (job_type, window)
            ).fetchone()
            count = int(row["count"]) if row else 0
            if count >= limit_per_minute:
                return False
            connection.execute(
                """INSERT INTO memory_job_rate_windows VALUES (?, ?, 1)
                ON CONFLICT(job_type, window_started_at) DO UPDATE SET count = count + 1""", (job_type, window)
            )
        return True

    def record_memory_lifecycle_event(self, memory_id: str, action: str, actor_id: str, details: dict[str, Any] | None = None) -> str:
        from raiker.contracts.ids import new_id

        if action not in {"archive", "restore", "forget", "purge", "correct", "export", "import", "recall"}:
            raise ValueError("invalid_memory_lifecycle_action")
        audit_id = new_id("mla_")
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO memory_lifecycle_audit VALUES (?, ?, ?, ?, ?, ?)",
                (audit_id, memory_id, action, actor_id, json.dumps(details or {}, sort_keys=True), utc_now()),
            )
        return audit_id

    # ── Phase 6: Channels & Relay ──

    def insert_channel_pairing(self, pairing: ChannelPairing) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO channel_pairings
                (pairing_id, connector_id, channel_type, display_name, paired_at, paired_by, enabled, sender_allowlist_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (pairing.pairing_id, pairing.connector_id, pairing.channel_type, pairing.display_name, pairing.paired_at, pairing.paired_by, int(pairing.enabled), pairing.sender_allowlist_json),
            )

    def list_channel_pairings(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM channel_pairings"
        params: list[Any] = []
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY paired_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def insert_approval_relay(self, relay: ApprovalRelayRecord) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO approval_relay_records
                (relay_id, pairing_id, action_id, status, requested_at, resolved_at, resolved_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (relay.relay_id, relay.pairing_id, relay.action_id, relay.status, relay.requested_at, relay.resolved_at, relay.resolved_by),
            )

    # ── Phase 4 slice 2: scheduled routines (on-demand; no daemon) ──

    def insert_scheduled_routine(self, routine: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO scheduled_routines
                (routine_id, name, interval_seconds, payload_json, enabled, next_run, last_run, created_by, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    routine["routine_id"], routine["name"], int(routine["interval_seconds"]),
                    routine["payload_json"], int(routine.get("enabled", 0)), routine["next_run"],
                    routine.get("last_run"), routine["created_by"], routine["created_at"],
                    routine.get("status", "scheduled"),
                ),
            )

    def get_scheduled_routine(self, routine_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM scheduled_routines WHERE routine_id = ?", (routine_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_scheduled_routines(
        self, *, enabled_only: bool = False, due_before: str | None = None
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM scheduled_routines"
        conditions: list[str] = []
        params: list[Any] = []
        if enabled_only:
            conditions.append("enabled = 1")
        if due_before is not None:
            conditions.append("next_run <= ?")
            params.append(due_before)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY next_run ASC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def update_scheduled_routine_run(self, routine_id: str, *, last_run: str, next_run: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE scheduled_routines SET last_run = ?, next_run = ? WHERE routine_id = ?",
                (last_run, next_run, routine_id),
            )

    # ── Phase 6: Subagents ──

    def insert_subagent_contract(self, contract: SubagentContract) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO subagent_contracts
                (subagent_id, parent_task_id, name, mode, allowed_tools_json, max_depth, max_runtime_seconds, max_cost, created_by, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (contract.subagent_id, contract.parent_task_id, contract.name, contract.mode, contract.allowed_tools_json, contract.max_depth, contract.max_runtime_seconds, contract.max_cost, contract.created_by, contract.created_at, contract.status),
            )

    def list_subagent_contracts(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM subagent_contracts ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    # ── Phase 6: Teams ──

    def insert_team_ledger(self, team: TeamLedger) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO team_ledgers
                (team_id, name, mode, members_json, max_depth, max_cost, created_by, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (team.team_id, team.name, team.mode, team.members_json, team.max_depth, team.max_cost, team.created_by, team.created_at, team.status),
            )

    def list_team_ledgers(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM team_ledgers ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    # ── Phase 6: Remote Execution & Budget ──

    def insert_remote_execution_profile(self, profile: RemoteExecutionProfile) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO remote_execution_profiles
                (profile_id, profile_type, name, config_json, enabled, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (profile.profile_id, profile.profile_type, profile.name, profile.config_json, int(profile.enabled), profile.created_by, profile.created_at, profile.updated_at),
            )

    def list_remote_execution_profiles(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM remote_execution_profiles"
        params: list[Any] = []
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def insert_execution_budget(self, budget: ExecutionBudget) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO execution_budgets
                (budget_id, name, max_cost, current_cost, currency, profile_id, enabled, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (budget.budget_id, budget.name, budget.max_cost, budget.current_cost, budget.currency, budget.profile_id, int(budget.enabled), budget.created_by, budget.created_at, budget.updated_at),
            )

    def list_execution_budgets(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM execution_budgets"
        params: list[Any] = []
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def delete_managed_policy(self, rule_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM managed_policies WHERE rule_id = ?", (rule_id,)
            )
        return cursor.rowcount > 0

    # ── Phase 7: Plugin Execution ──

    def insert_plugin_execution_record(self, record: PluginExecutionRecord) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO plugin_execution_records
                (execution_id, plugin_id, version, trust_level, permissions_json, entrypoint, status, started_at, completed_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (record.execution_id, record.plugin_id, record.version, record.trust_level, record.permissions_json, record.entrypoint, record.status, record.started_at, record.completed_at, record.created_by),
            )

    def list_plugin_execution_records(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM plugin_execution_records ORDER BY COALESCE(started_at, created_by) DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    # ── Phase 7: Graph Index ──

    def insert_graph_index_record(self, record: GraphIndexRecord) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO graph_index_records
                (index_id, workspace_root, status, nodes_count, edges_count, started_at, completed_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (record.index_id, record.workspace_root, record.status, record.nodes_count, record.edges_count, record.started_at, record.completed_at, record.created_by),
            )

    def list_graph_index_records(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM graph_index_records ORDER BY COALESCE(started_at, index_id) DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    # ── Phase 7: Semantic Memory Writes ──

    def insert_semantic_memory_write(self, record: SemanticMemoryWriteRecord) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO semantic_memory_write_records
                (write_id, content_summary, embedding_model, vector_count, status, approved_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (record.write_id, record.content_summary, record.embedding_model, record.vector_count, record.status, record.approved_by, record.created_at),
            )

    def list_semantic_memory_writes(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM semantic_memory_write_records ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    # ── Phase 9: Vector Records ──

    def insert_vector_record(self, record: VectorRecord) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO vector_records
                (vector_id, content_hash, content_preview, embedding_model, dimensions, scope, sensitivity, embedding, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (record.vector_id, record.content_hash, record.content_preview, record.embedding_model, record.dimensions, record.scope, record.sensitivity, record.embedding, record.created_at),
            )

    def list_vector_records(self, scope: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        query = "SELECT * FROM vector_records"
        params: list[Any] = []
        if scope:
            query += " WHERE scope = ?"
            params.append(scope)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_vector_record(self, vector_id: str) -> dict[str, Any] | None:
        """Return one vector record by id (or ``None``). Includes the stored preview."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM vector_records WHERE vector_id = ?", (vector_id,)
            ).fetchone()
        return dict(row) if row is not None else None

    def list_vector_embeddings(
        self, embedding_model: str, scope: str | None = None
    ) -> list[dict[str, Any]]:
        """Return ``(vector_id, embedding)`` rows for one embedding model.

        Cosine similarity is only meaningful within a single embedding space, so
        retrieval fetches vectors for exactly one ``embedding_model`` (optionally
        narrowed to a ``scope``). Rows with no stored embedding are excluded. No
        row limit — the caller ranks the full corpus for that model.
        """
        query = (
            "SELECT vector_id, embedding FROM vector_records "
            "WHERE embedding_model = ? AND embedding IS NOT NULL"
        )
        params: list[Any] = [embedding_model]
        if scope:
            query += " AND scope = ?"
            params.append(scope)
        query += " ORDER BY created_at"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def list_active_memory_vector_embeddings(
        self, embedding_model: str, scope: str | None = None
    ) -> list[dict[str, Any]]:
        now = utc_now()
        query = """SELECT v.vector_id, v.embedding, p.memory_id FROM vector_records v
        JOIN memory_projections p ON p.projection_id = v.vector_id
          AND p.projection_type = 'vector' AND p.active = 1
        JOIN approved_memory m ON m.memory_id = p.memory_id
        WHERE v.embedding_model = ? AND v.embedding IS NOT NULL
          AND m.deleted_at IS NULL AND m.archived_at IS NULL AND m.search_enabled = 1
          AND (m.expires_at IS NULL OR m.expires_at > ?)
          AND (m.valid_from IS NULL OR m.valid_from <= ?)
          AND (m.valid_until IS NULL OR m.valid_until > ?) AND m.superseded_at IS NULL"""
        params: list[Any] = [embedding_model, now, now, now]
        if scope:
            query += " AND m.scope = ?"
            params.append(scope)
        query += " ORDER BY v.created_at"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    # ── Phase 9: Symbol Nodes & Dependency Edges ──

    def insert_symbol_node(self, node: SymbolNode) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO symbol_nodes
                (symbol_id, name, kind, file_path, line_number, module, parent_symbol_id, doc_preview)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (node.symbol_id, node.name, node.kind, node.file_path, node.line_number, node.module, node.parent_symbol_id, node.doc_preview),
            )

    def list_symbol_nodes(self, kind: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = "SELECT * FROM symbol_nodes"
        params: list[Any] = []
        if kind:
            query += " WHERE kind = ?"
            params.append(kind)
        query += " ORDER BY file_path, line_number LIMIT ?"
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def insert_dependency_edge(self, edge: DependencyEdge) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO dependency_edges
                (edge_id, source_symbol_id, target_symbol_id, dep_type, file_path, line_number, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (edge.edge_id, edge.source_symbol_id, edge.target_symbol_id, edge.dep_type, edge.file_path, edge.line_number, edge.created_at),
            )

    # ── Phase 9: Project Graphs ──

    def insert_project_graph(self, graph: ProjectGraph) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO project_graphs
                (graph_id, workspace_root, module_count, dependency_count, built_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (graph.graph_id, graph.workspace_root, graph.module_count, graph.dependency_count, graph.built_at),
            )

    def list_project_graphs(self, limit: int = 10) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM project_graphs ORDER BY built_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    # ── Phase 9: Skill Candidates ──

    def insert_skill_candidate(self, candidate: SkillCandidate) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO skill_candidates
                (candidate_id, name, description, source_workflow_json, suggested_tools_json, provenance, status, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (candidate.candidate_id, candidate.name, candidate.description, candidate.source_workflow_json, candidate.suggested_tools_json, candidate.provenance, candidate.status, candidate.created_by, candidate.created_at),
            )

    def list_skill_candidates(self, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        query = "SELECT * FROM skill_candidates"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def load_model_session_state(self, session_id: str) -> ModelSessionState | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM model_session_state WHERE session_id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        return ModelSessionState(
            session_id=str(row["session_id"]),
            profile_id=str(row["profile_id"]),
            model=(str(row["model"]) if row["model"] else None),
            reasoning_enabled=bool(row["reasoning_enabled"]),
            reasoning_effort=row["reasoning_effort"],
            reasoning_mode=row["reasoning_mode"],
            reasoning_budget_tokens=row["reasoning_budget_tokens"],
        )

    def save_model_fallback_sequence(self, session_id: str, profile_ids: list[str]) -> None:
        """Persist the ordered, user-owned model fallback sequence for ``session_id``.

        The list is stored verbatim (deduplication/validation is the caller's job).
        An empty list clears the sequence.
        """
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO model_fallback_sequence
                (session_id, profile_ids_json, updated_at)
                VALUES (?, ?, ?)
                """,
                (session_id, json.dumps(list(profile_ids)), utc_now()),
            )

    def load_model_fallback_sequence(self, session_id: str) -> list[str]:
        """Return the ordered fallback profile ids for ``session_id`` ([] if unset)."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT profile_ids_json FROM model_fallback_sequence WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return []
        try:
            value = json.loads(row["profile_ids_json"])
        except (ValueError, TypeError):
            return []
        return [str(item) for item in value] if isinstance(value, list) else []

    def save_model_advisor(self, session_id: str, profile_id: str | None) -> None:
        """Persist the user-owned advisor model profile id (None/empty clears it).

        Storing the id grants nothing — the consult path is gated by the
        ``advisor_model_runtime`` capability, its decision mode, and provider
        policy at call time. Validation is the caller's job.
        """
        with self.connect() as connection:
            if not profile_id:
                connection.execute(
                    "DELETE FROM model_advisor WHERE session_id = ?", (session_id,)
                )
                return
            connection.execute(
                """
                INSERT OR REPLACE INTO model_advisor (session_id, profile_id, updated_at)
                VALUES (?, ?, ?)
                """,
                (session_id, profile_id, utc_now()),
            )

    def load_model_advisor(self, session_id: str) -> str | None:
        """Return the persisted advisor profile id for ``session_id`` (None if unset)."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT profile_id FROM model_advisor WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return str(row["profile_id"]) if row is not None else None

    # ── Uploaded attachments (web-app task 3): governed local attachment store ──

    def save_attachment(
        self,
        *,
        attachment_id: str,
        kind: str,
        filename: str,
        media_type: str,
        sha256: str,
        data: bytes,
    ) -> None:
        """Persist validated attachment bytes. Validation is the caller's job
        (``raiker.runtime.attachments``) — this layer only stores what it is given."""
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO attachments
                (attachment_id, kind, filename, media_type, byte_size, sha256, data, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (attachment_id, kind, filename, media_type, len(data), sha256, data, utc_now()),
            )

    def load_attachment(self, attachment_id: str) -> dict[str, Any] | None:
        """Return the stored attachment (metadata + raw bytes), or None if unknown."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM attachments WHERE attachment_id = ?", (attachment_id,)
            ).fetchone()
        if row is None:
            return None
        record = dict(row)
        record["data"] = bytes(record["data"])
        return record

    def load_attachment_metadata(self, attachment_id: str) -> dict[str, Any] | None:
        """Return attachment metadata only — the bytes never ride this path."""
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT attachment_id, kind, filename, media_type, byte_size, sha256, created_at
                FROM attachments WHERE attachment_id = ?
                """,
                (attachment_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    # ── Phase 10: Runtime Authority (Principals + Risk Acceptance) ──

    def insert_principal(self, principal_id: str, principal_type: str, display_name: str,
                         delegated_by_user_id: str | None = None,
                         model_profile_id: str | None = None,
                         session_id: str | None = None,
                         role_ids: tuple[str, ...] = (),
                         domain_scopes: tuple[str, ...] = (),
                         max_runtime_mode: str = "development_preview",
                         expires_at: str | None = None,
                         is_active: bool = True) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO principals
                (principal_id, principal_type, display_name, delegated_by_user_id,
                 model_profile_id, session_id, role_ids, domain_scopes,
                 max_runtime_mode, created_at, expires_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    principal_id, principal_type, display_name, delegated_by_user_id,
                    model_profile_id, session_id,
                    json.dumps(list(role_ids), sort_keys=True),
                    json.dumps(list(domain_scopes), sort_keys=True),
                    max_runtime_mode, utc_now(), expires_at, int(is_active),
                ),
            )

    # ── Local-account credentials & settings (lock screen) ──────────────────
    def upsert_account(
        self,
        principal_id: str,
        username: str,
        password_hash: str,
        hash_algo: str,
        created_at: str,
        updated_at: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO account_credentials
                   (principal_id, username, password_hash, hash_algo, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(principal_id) DO UPDATE SET
                     username=excluded.username,
                     password_hash=excluded.password_hash,
                     hash_algo=excluded.hash_algo,
                     updated_at=excluded.updated_at""",
                (principal_id, username, password_hash, hash_algo, created_at, updated_at),
            )

    def get_account_by_username(self, username: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM account_credentials WHERE username = ?", (username,)
            ).fetchone()
        return dict(row) if row is not None else None

    def get_account(self, principal_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM account_credentials WHERE principal_id = ?", (principal_id,)
            ).fetchone()
        return dict(row) if row is not None else None

    def set_account_failed(
        self, principal_id: str, failed_attempts: int, locked_until: str | None
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE account_credentials SET failed_attempts = ?, locked_until = ? "
                "WHERE principal_id = ?",
                (failed_attempts, locked_until, principal_id),
            )

    def set_account_mfa(
        self,
        principal_id: str,
        enrolled: bool,
        secret_encrypted: bytes | None,
        backup_codes_hashed: str | None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE account_credentials SET mfa_enrolled = ?, mfa_secret_encrypted = ?, "
                "backup_codes_hashed = ? WHERE principal_id = ?",
                (int(enrolled), secret_encrypted, backup_codes_hashed, principal_id),
            )

    def set_account_password(
        self, principal_id: str, password_hash: str, hash_algo: str, updated_at: str
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE account_credentials SET password_hash = ?, hash_algo = ?, updated_at = ? "
                "WHERE principal_id = ?",
                (password_hash, hash_algo, updated_at, principal_id),
            )

    def delete_account(self, principal_id: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM account_credentials WHERE principal_id = ?", (principal_id,)
            )

    def purge_account(self, principal_id: str) -> None:
        """Irreversibly remove an account and all its per-principal data."""
        with self.connect() as connection:
            for sql in (
                "DELETE FROM account_credentials WHERE principal_id = ?",
                "DELETE FROM user_settings WHERE principal_id = ?",
                "DELETE FROM trusted_contacts WHERE principal_id = ?",
                "DELETE FROM connector_credentials WHERE principal_id = ?",
                "DELETE FROM connector_installations WHERE principal_id = ?",
                "DELETE FROM api_sessions WHERE principal_id = ?",
            ):
                connection.execute(sql, (principal_id,))
            connection.execute(
                "UPDATE principals SET is_active = 0 WHERE principal_id = ?", (principal_id,)
            )

    def list_accounts(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT principal_id, username, mfa_enrolled, created_at FROM account_credentials "
                "ORDER BY created_at ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_user_settings(self, principal_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM user_settings WHERE principal_id = ?", (principal_id,)
            ).fetchone()
        return dict(row) if row is not None else None

    def put_user_settings(self, principal_id: str, settings_json: str, updated_at: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO user_settings (principal_id, settings_json, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(principal_id) DO UPDATE SET
                     settings_json=excluded.settings_json, updated_at=excluded.updated_at""",
                (principal_id, settings_json, updated_at),
            )

    def get_principal(self, principal_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM principals WHERE principal_id = ?", (principal_id,)
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["role_ids"] = tuple(json.loads(result.get("role_ids", "[]")))
        result["domain_scopes"] = tuple(json.loads(result.get("domain_scopes", "[]")))
        result["is_active"] = bool(result.get("is_active", 1))
        return result

    def list_principals(self, active_only: bool = True, principal_type: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM principals"
        params: list[Any] = []
        conditions: list[str] = []
        if active_only:
            conditions.append("is_active = 1")
        if principal_type:
            conditions.append("principal_type = ?")
            params.append(principal_type)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d["role_ids"] = tuple(json.loads(d.get("role_ids", "[]")))
            d["domain_scopes"] = tuple(json.loads(d.get("domain_scopes", "[]")))
            d["is_active"] = bool(d.get("is_active", 1))
            results.append(d)
        return results

    def deactivate_principal(self, principal_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE principals SET is_active = 0 WHERE principal_id = ? AND is_active = 1",
                (principal_id,),
            )
        return cursor.rowcount > 0

    def get_role_name(self, role_id: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT name FROM roles WHERE role_id = ?", (role_id,)
            ).fetchone()
        return str(row["name"]) if row else None

    def insert_risk_acceptance(self, acceptance: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO risk_acceptances
                (risk_acceptance_id, accepted_by, accepted_for_principal_id, action_id,
                 action_type, domain_scope, risk_level, risk_summary, data_involved,
                 expected_effect, one_time_or_reusable, expires_at, created_at,
                 policy_decision_id, approval_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    acceptance["risk_acceptance_id"],
                    acceptance["accepted_by"],
                    acceptance["accepted_for_principal_id"],
                    acceptance["action_id"],
                    acceptance["action_type"],
                    acceptance["domain_scope"],
                    acceptance["risk_level"],
                    acceptance["risk_summary"],
                    acceptance["data_involved"],
                    acceptance["expected_effect"],
                    acceptance.get("one_time_or_reusable", "one_time"),
                    acceptance.get("expires_at"),
                    acceptance["created_at"],
                    acceptance.get("policy_decision_id"),
                    acceptance.get("approval_id"),
                ),
            )

    def find_valid_risk_acceptance(self, principal_id: str, action_type: str,
                                    domain_scope: str, risk_level: str) -> dict[str, Any] | None:
        now = utc_now()
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM risk_acceptances
                WHERE accepted_for_principal_id = ?
                  AND action_type = ?
                  AND domain_scope = ?
                  AND risk_level = ?
                  AND (expires_at IS NULL OR expires_at >= ?)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (principal_id, action_type, domain_scope, risk_level, now),
            ).fetchone()
        return dict(row) if row else None

    def consume_risk_acceptance(self, risk_acceptance_id: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM risk_acceptances WHERE risk_acceptance_id = ?",
                (risk_acceptance_id,),
            )

    def list_risk_acceptances(self, principal_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM risk_acceptances"
        params: list[Any] = []
        if principal_id:
            query += " WHERE accepted_for_principal_id = ?"
            params.append(principal_id)
        query += " ORDER BY created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    # ── Runtime Mode State ──

    def get_runtime_mode_state(self) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM runtime_mode_state ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def get_active_runtime_mode(self) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM runtime_mode_state WHERE status = 'active' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def insert_runtime_mode_state(self, record: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO runtime_mode_state
                  (runtime_mode_id, mode_name, status, activated_by, activated_at,
                   disabled_by, disabled_at, reason, risk_acceptance_id, approval_id,
                   policy_decision_id, validation_evidence_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["runtime_mode_id"],
                    record["mode_name"],
                    record["status"],
                    record.get("activated_by"),
                    record.get("activated_at"),
                    record.get("disabled_by"),
                    record.get("disabled_at"),
                    record.get("reason"),
                    record.get("risk_acceptance_id"),
                    record.get("approval_id"),
                    record.get("policy_decision_id"),
                    record.get("validation_evidence_id"),
                    record["created_at"],
                    record["updated_at"],
                ),
            )

    def update_runtime_mode_state(self, runtime_mode_id: str, updates: dict[str, Any]) -> None:
        sets: list[str] = []
        params: list[Any] = []
        for key in ("status", "mode_name", "activated_by", "activated_at", "disabled_by",
                     "disabled_at", "reason", "risk_acceptance_id", "approval_id",
                     "policy_decision_id", "validation_evidence_id", "updated_at"):
            if key in updates:
                sets.append(f"{key} = ?")
                params.append(updates[key])
        if not sets:
            return
        params.append(runtime_mode_id)
        with self.connect() as connection:
            connection.execute(
                f"UPDATE runtime_mode_state SET {', '.join(sets)} WHERE runtime_mode_id = ?",
                params,
            )

    def disable_all_runtime_modes(self, disabled_by: str, reason: str) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """UPDATE runtime_mode_state SET status = 'disabled', disabled_by = ?,
                   disabled_at = ?, reason = ?, updated_at = ? WHERE status = 'active'""",
                (disabled_by, now, reason, now),
            )

    # ── Capability Gate State ──

    def get_capability_gate_state(self, capability: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM capability_gate_state WHERE capability = ?",
                (capability,),
            ).fetchone()
        return dict(row) if row else None

    def list_capability_gate_states(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM capability_gate_state ORDER BY capability"
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_capability_gate_state(self, record: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO capability_gate_state
                  (capability, state, runtime_mode, requested_by, requested_at,
                   activated_by, activated_at, disabled_by, disabled_at, reason,
                   readiness_snapshot_json, risk_acceptance_id, approval_id,
                   policy_decision_id, event_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["capability"],
                    record["state"],
                    record.get("runtime_mode"),
                    record.get("requested_by"),
                    record.get("requested_at"),
                    record.get("activated_by"),
                    record.get("activated_at"),
                    record.get("disabled_by"),
                    record.get("disabled_at"),
                    record.get("reason"),
                    record.get("readiness_snapshot_json"),
                    record.get("risk_acceptance_id"),
                    record.get("approval_id"),
                    record.get("policy_decision_id"),
                    record.get("event_id"),
                    record["created_at"],
                    record["updated_at"],
                ),
            )

    def delete_capability_gate_state(self, capability: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM capability_gate_state WHERE capability = ?",
                (capability,),
            )

    # ── Capability decision modes (ask / deny / always_allow / auto) ──────────

    def get_capability_decision_mode(self, capability: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT decision_mode FROM capability_decision_mode WHERE capability = ?",
                (capability,),
            ).fetchone()
        return str(row["decision_mode"]) if row else None

    def list_capability_decision_modes(self) -> dict[str, str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT capability, decision_mode FROM capability_decision_mode"
            ).fetchall()
        return {str(r["capability"]): str(r["decision_mode"]) for r in rows}

    def upsert_capability_decision_mode(self, record: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO capability_decision_mode
                  (capability, decision_mode, set_by, set_at, reason, event_id,
                   created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["capability"],
                    record["decision_mode"],
                    record.get("set_by"),
                    record.get("set_at"),
                    record.get("reason"),
                    record.get("event_id"),
                    record["created_at"],
                    record["updated_at"],
                ),
            )

    # ── Reminders (local-only Tier-6 reminder_runtime) ────────────────────────

    def insert_reminder(self, record: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO reminders
                  (reminder_id, title, due_at, notes, status, created_by,
                   created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["reminder_id"],
                    record["title"],
                    record.get("due_at"),
                    record.get("notes"),
                    record["status"],
                    record["created_by"],
                    record["created_at"],
                    record["updated_at"],
                ),
            )

    def list_reminders(self, *, status: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if status is None:
                rows = connection.execute(
                    "SELECT * FROM reminders ORDER BY created_at"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM reminders WHERE status = ? ORDER BY created_at",
                    (status,),
                ).fetchall()
        return [dict(row) for row in rows]

    def list_due_reminders(self, due_before: str, *, delivery_status: str = "active") -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM reminders WHERE delivery_status = ? AND due_at IS NOT NULL AND due_at <= ? ORDER BY due_at ASC",
                (delivery_status, due_before),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_reminder_status(self, reminder_id: str, status: str, *, delivery_status: str | None = None, delivered_at: str | None = None, retry_count: int | None = None, updated_at: str) -> bool:
        sets = ["status = ?", "updated_at = ?"]
        params: list[Any] = [status, updated_at]
        if delivery_status is not None:
            sets.append("delivery_status = ?")
            params.append(delivery_status)
        if delivered_at is not None:
            sets.append("delivered_at = ?")
            params.append(delivered_at)
        if retry_count is not None:
            sets.append("retry_count = ?")
            params.append(retry_count)
        params.append(reminder_id)
        with self.connect() as connection:
            cur = connection.execute(
                f"UPDATE reminders SET {', '.join(sets)} WHERE reminder_id = ?",
                params,
            )
        return cur.rowcount > 0

    # ── Calendar events (local-only calendar_runtime) ─────────────────────────

    def insert_calendar_event(self, record: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO calendar_events
                  (event_id, title, starts_at, ends_at, location, notes, status,
                   created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["event_id"], record["title"], record.get("starts_at"),
                    record.get("ends_at"), record.get("location"), record.get("notes"),
                    record["status"], record["created_by"], record["created_at"],
                    record["updated_at"],
                ),
            )

    def list_calendar_events(self, *, status: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if status is None:
                rows = connection.execute(
                    "SELECT * FROM calendar_events ORDER BY created_at"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM calendar_events WHERE status = ? ORDER BY created_at",
                    (status,),
                ).fetchall()
        return [dict(row) for row in rows]

    # ── Email drafts (local-only email_runtime; never sends) ──────────────────

    def insert_email_draft(self, record: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO email_drafts
                  (draft_id, subject, recipients, body, status, created_by,
                   created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["draft_id"], record["subject"], record.get("recipients"),
                    record.get("body"), record["status"], record["created_by"],
                    record["created_at"], record["updated_at"],
                ),
            )

    def list_email_drafts(self, *, status: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if status is None:
                rows = connection.execute(
                    "SELECT * FROM email_drafts ORDER BY created_at"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM email_drafts WHERE status = ? ORDER BY created_at",
                    (status,),
                ).fetchall()
        return [dict(row) for row in rows]

    def get_email_draft(self, draft_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM email_drafts WHERE draft_id = ?", (draft_id,)
            ).fetchone()
        return dict(row) if row else None

    def update_email_draft_status(self, draft_id: str, status: str, *, updated_at: str) -> bool:
        with self.connect() as connection:
            cur = connection.execute(
                "UPDATE email_drafts SET status = ?, updated_at = ? WHERE draft_id = ?",
                (status, updated_at, draft_id),
            )
        return cur.rowcount > 0
