from __future__ import annotations

import contextlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.contracts.models import (
    AgentEvent,
    Checkpoint,
    ConnectorProfile,
    ModelProfile,
    PolicyDecision,
    TaskRecord,
    ToolAction,
)
from raiker.storage.migrations import (
    PHASE_1_MIGRATION_ID,
    PHASE_1_SQL,
    PHASE_2_MIGRATION_ID,
    PHASE_2_MIGRATION_SQL,
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
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def bootstrap(self) -> None:
        self.paths.ensure()
        with sqlite3.connect(self.db_path) as connection:
            connection.executescript(PHASE_1_SQL)
            connection.execute(
                "INSERT OR IGNORE INTO migrations (migration_id, applied_at) VALUES (?, ?)",
                (PHASE_1_MIGRATION_ID, utc_now()),
            )
            self._apply_migration(PHASE_2_MIGRATION_ID, PHASE_2_MIGRATION_SQL, connection)

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

    def create_session(self, session_id: str, project_root: str, title: str | None = None) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO sessions
                (session_id, project_root, created_at, updated_at, status, title)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, project_root, now, now, "open", title),
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
        self, event: AgentEvent, jsonl_path: str, jsonl_offset: int, payload_sha256: str
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO events_index
                (event_id, session_id, turn_id, task_id, event_type, actor, timestamp, jsonl_path, jsonl_offset, payload_sha256, risk_level, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    event.payload.get("risk_level"),
                    event.payload.get("summary"),
                ),
            )

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

    def insert_approval(self, approval_id: str, action_id: str, status: str = "pending") -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO approvals
                (approval_id, action_id, status, approval_scope, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (approval_id, action_id, status, "action", utc_now()),
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
                SELECT approvals.*, tool_actions.session_id, tool_actions.turn_id
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
