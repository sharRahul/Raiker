from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    PHASE_10_RUNTIME_AUTHORITY_MIGRATION_ID,
    PHASE_10_RUNTIME_AUTHORITY_SQL,
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
        connection = sqlite3.connect(self.db_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def bootstrap(self) -> None:
        self.paths.ensure()
        with sqlite3.connect(self.db_path) as connection:
            connection.executescript(PHASE_1_SQL)
            connection.executescript("""
CREATE TABLE IF NOT EXISTS model_session_state (
  session_id TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL,
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
            with contextlib.suppress(sqlite3.OperationalError):
                connection.execute("ALTER TABLE events_index ADD COLUMN prev_event_sha256 TEXT")
            with contextlib.suppress(sqlite3.OperationalError):
                connection.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT REFERENCES users(user_id)")

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

    def table_names(self) -> set[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        return {str(row["name"]) for row in rows}

    def create_session(self, session_id: str, project_root: str, title: str | None = None, user_id: str | None = None) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO sessions
                (session_id, project_root, created_at, updated_at, status, title, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, project_root, now, now, "open", title, user_id),
            )

    def load_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_sessions(self, limit: int = 10) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

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
                (task_id, session_id, parent_turn_id, parent_task_id, title, objective, status, current_step, progress_percent, created_at, updated_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )

    def load_task(self, task_id: str) -> TaskRecord | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        return TaskRecord(**dict(row))

    def list_tasks(
        self, session_id: str | None = None, status: str | None = None
    ) -> list[TaskRecord]:
        query = "SELECT * FROM tasks"
        params: list[Any] = []
        conditions: list[str] = []
        if session_id is not None:
            conditions.append("session_id = ?")
            params.append(session_id)
        if status is not None:
            conditions.append("status = ?")
            params.append(status)
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

    def list_checkpoints(self, session_id: str | None = None, limit: int = 50) -> list[dict]:
        query = "SELECT * FROM checkpoints"
        params: list[Any] = []
        if session_id is not None:
            query += " WHERE session_id = ?"
            params.append(session_id)
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
                (memory_id, text, scope, sensitivity, source_event_id, memory_type, created_at, tags_json, source, provenance_json, confidence, trust_score, retention, approval_state, created_by, updated_at, deleted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )

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
        return cursor.rowcount > 0

    def delete_approved_memory(self, memory_id: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM approved_memory WHERE memory_id = ?", (memory_id,))

    def list_approved_memory(self, scope: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        query = "SELECT * FROM approved_memory WHERE deleted_at IS NULL"
        params: list[Any] = []
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
                (session_id, profile_id, reasoning_enabled, reasoning_effort, reasoning_mode, reasoning_budget_tokens, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (state.session_id, state.profile_id, int(state.reasoning_enabled), state.reasoning_effort, state.reasoning_mode, state.reasoning_budget_tokens, utc_now()),
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
                (manifest_id, backup_type, scope_json, path, checksum, size_bytes, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (manifest.manifest_id, manifest.backup_type, manifest.scope_json, manifest.path, manifest.checksum, manifest.size_bytes, manifest.created_by, manifest.created_at),
            )

    def list_backup_manifests(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM backup_manifests ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

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
                (vector_id, content_hash, content_preview, embedding_model, dimensions, scope, sensitivity, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (record.vector_id, record.content_hash, record.content_preview, record.embedding_model, record.dimensions, record.scope, record.sensitivity, record.created_at),
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
            reasoning_enabled=bool(row["reasoning_enabled"]),
            reasoning_effort=row["reasoning_effort"],
            reasoning_mode=row["reasoning_mode"],
            reasoning_budget_tokens=row["reasoning_budget_tokens"],
        )

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
