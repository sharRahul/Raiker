from __future__ import annotations

PHASE_1_MIGRATION_ID = "RAIKER-0201-phase1-bootstrap"

PHASE_1_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS migrations (
  migration_id TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  project_root TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  status TEXT NOT NULL,
  parent_session_id TEXT,
  forked_from_checkpoint_id TEXT,
  title TEXT,
  summary TEXT
);

CREATE TABLE IF NOT EXISTS turns (
  turn_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(session_id),
  parent_turn_id TEXT,
  turn_type TEXT NOT NULL,
  status TEXT NOT NULL,
  prompt_text TEXT,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  summary TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(session_id),
  parent_turn_id TEXT REFERENCES turns(turn_id),
  parent_task_id TEXT,
  title TEXT NOT NULL,
  objective TEXT NOT NULL,
  status TEXT NOT NULL,
  current_step TEXT,
  progress_percent INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT,
  summary TEXT
);

CREATE TABLE IF NOT EXISTS events_index (
  event_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  turn_id TEXT,
  task_id TEXT,
  event_type TEXT NOT NULL,
  actor TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  jsonl_path TEXT NOT NULL,
  jsonl_offset INTEGER,
  payload_sha256 TEXT,
  risk_level TEXT,
  summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_session_time ON events_index(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_type_time ON events_index(event_type, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_task_time ON events_index(task_id, timestamp);

CREATE TABLE IF NOT EXISTS tool_actions (
  action_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  turn_id TEXT,
  task_id TEXT,
  tool_name TEXT NOT NULL,
  arguments_json TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  status TEXT NOT NULL,
  proposed_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS policy_decisions (
  decision_id TEXT PRIMARY KEY,
  action_id TEXT NOT NULL REFERENCES tool_actions(action_id),
  decision TEXT NOT NULL,
  reasons_json TEXT NOT NULL,
  policy_version TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
  approval_id TEXT PRIMARY KEY,
  action_id TEXT NOT NULL REFERENCES tool_actions(action_id),
  status TEXT NOT NULL,
  approval_scope TEXT,
  approved_by TEXT,
  channel_message_id TEXT,
  created_at TEXT NOT NULL,
  resolved_at TEXT,
  expires_at TEXT
);

CREATE TABLE IF NOT EXISTS memory_candidates (
  candidate_id TEXT PRIMARY KEY,
  source_event_id TEXT NOT NULL,
  memory_type TEXT NOT NULL,
  scope TEXT NOT NULL,
  text TEXT NOT NULL,
  sensitivity TEXT NOT NULL,
  confidence REAL NOT NULL,
  decision TEXT NOT NULL,
  reason TEXT,
  created_at TEXT NOT NULL,
  resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS connector_profiles (
  connector_id TEXT PRIMARY KEY,
  channel_type TEXT NOT NULL,
  display_name TEXT NOT NULL,
  build_phase TEXT NOT NULL,
  default_state TEXT NOT NULL,
  interface_status TEXT NOT NULL,
  profile_json TEXT NOT NULL,
  loaded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_profiles (
  profile_id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  build_phase TEXT NOT NULL,
  default_state TEXT NOT NULL,
  profile_json TEXT NOT NULL,
  loaded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS checkpoints (
  checkpoint_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  turn_id TEXT,
  task_id TEXT,
  checkpoint_type TEXT NOT NULL,
  manifest_path TEXT NOT NULL,
  created_at TEXT NOT NULL,
  summary TEXT,
  last_event_id TEXT,
  can_restore_state INTEGER NOT NULL,
  can_restore_files INTEGER NOT NULL
);
"""

PHASE_2_MIGRATION_ID = "RAIKER-1101-phase2-task-summary"

PHASE_2_MIGRATION_SQL = """
ALTER TABLE tasks ADD COLUMN summary TEXT;
"""
