from __future__ import annotations

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
    ToolAction,
)
from raiker.storage.migrations import PHASE_1_MIGRATION_ID, PHASE_1_SQL


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
        for path in (self.runtime_dir, self.events_dir, self.checkpoints_dir, self.artifacts_dir, self.indexes_dir):
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

    def table_names(self) -> set[str]:
        with self.connect() as connection:
            rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
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
            row = connection.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        return dict(row) if row else None

    def insert_turn(self, session_id: str, turn_id: str, prompt_text: str, status: str = "running") -> None:
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

    def index_event(self, event: AgentEvent, jsonl_path: str, jsonl_offset: int, payload_sha256: str) -> None:
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

    def insert_tool_action(self, action: ToolAction, session_id: str, turn_id: str | None, status: str) -> None:
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
                    utc_now() if status in {"success", "failed", "denied", "approval_required"} else None,
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
