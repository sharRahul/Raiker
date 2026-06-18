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


PHASE_3_STORAGE_LIFECYCLE_MIGRATION_ID = "RAIKER-1307-phase3-storage-lifecycle-metadata"

PHASE_3_STORAGE_LIFECYCLE_SQL = """
CREATE TABLE IF NOT EXISTS phase3_storage_lifecycle (
  lifecycle_id TEXT PRIMARY KEY,
  target_capability TEXT NOT NULL,
  record_type TEXT NOT NULL,
  source_preview_id TEXT,
  source_audit_id TEXT,
  rollback_plan_id TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  retention_policy TEXT NOT NULL,
  redaction_policy TEXT NOT NULL,
  can_write_runtime_data INTEGER NOT NULL,
  runtime_writes_enabled INTEGER NOT NULL,
  reasons_json TEXT NOT NULL,
  metadata_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS phase3_storage_lifecycle_events (
  event_id TEXT PRIMARY KEY,
  lifecycle_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
"""

PHASE_3_STORAGE_LIFECYCLE_RETENTION_MIGRATION_ID = "RAIKER-1308-phase3-storage-lifecycle-retention-cleanup-handoff"

PHASE_3_STORAGE_LIFECYCLE_RETENTION_SQL = """
CREATE TABLE IF NOT EXISTS phase3_storage_lifecycle_retention (
  policy_id TEXT PRIMARY KEY,
  lifecycle_target_type TEXT NOT NULL,
  retention_class TEXT NOT NULL,
  expiry_rule TEXT NOT NULL,
  cleanup_eligible INTEGER NOT NULL,
  legal_hold INTEGER NOT NULL,
  manual_hold INTEGER NOT NULL,
  redacted_reason_summary TEXT NOT NULL,
  metadata_only INTEGER NOT NULL,
  execution_enabled INTEGER NOT NULL,
  policy_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS phase3_storage_lifecycle_cleanup_previews (
  preview_id TEXT PRIMARY KEY,
  linked_lifecycle_ids_json TEXT NOT NULL,
  expired_candidate_count INTEGER NOT NULL,
  superseded_candidate_count INTEGER NOT NULL,
  redacted_summaries_json TEXT NOT NULL,
  can_cleanup_now INTEGER NOT NULL,
  cleanup_execution_enabled INTEGER NOT NULL,
  preview_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS phase3_storage_lifecycle_approval_handoffs (
  handoff_id TEXT PRIMARY KEY,
  linked_lifecycle_ids_json TEXT NOT NULL,
  target_capability TEXT NOT NULL,
  approval_state TEXT NOT NULL,
  can_execute_now INTEGER NOT NULL,
  execution_enabled INTEGER NOT NULL,
  redacted_summary TEXT NOT NULL,
  handoff_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS phase3_storage_lifecycle_retention_events (
  event_id TEXT PRIMARY KEY,
  subject_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
"""

PHASE_3_STORAGE_LIFECYCLE_EVIDENCE_MIGRATION_ID = "RAIKER-1309-phase3-storage-lifecycle-evidence-simulation"

PHASE_3_STORAGE_LIFECYCLE_EVIDENCE_SQL = """
CREATE TABLE IF NOT EXISTS phase3_storage_lifecycle_evidence_bundles (
  evidence_id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  metadata_only INTEGER NOT NULL,
  export_only INTEGER NOT NULL,
  execution_enabled INTEGER NOT NULL,
  bundle_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS phase3_storage_lifecycle_policy_simulations (
  simulation_id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  metadata_only INTEGER NOT NULL,
  simulation_only INTEGER NOT NULL,
  execution_enabled INTEGER NOT NULL,
  simulation_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS phase3_storage_lifecycle_evidence_events (
  event_id TEXT PRIMARY KEY,
  subject_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
"""

PHASE_3_GRAPH_CODEMAP_READINESS_MIGRATION_ID = "RAIKER-1310-phase3-graph-codemap-readiness-metadata"

PHASE_3_GRAPH_CODEMAP_READINESS_SQL = """
CREATE TABLE IF NOT EXISTS phase3_graph_codemap_readiness (
  readiness_id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  target_capability TEXT NOT NULL,
  metadata_only INTEGER NOT NULL,
  ready_for_indexing INTEGER NOT NULL,
  runtime_flags_json TEXT NOT NULL,
  blockers_json TEXT NOT NULL,
  contract_json TEXT NOT NULL
);
"""


PHASE_3_SEMANTIC_MEMORY_READINESS_MIGRATION_ID = "RAIKER-1311-phase3-semantic-memory-readiness-metadata"

PHASE_3_SEMANTIC_MEMORY_READINESS_SQL = """
CREATE TABLE IF NOT EXISTS phase3_semantic_memory_readiness (
  readiness_id TEXT PRIMARY KEY,
  target TEXT NOT NULL,
  status TEXT NOT NULL,
  blockers_json TEXT NOT NULL,
  disabled_runtime_flags_json TEXT NOT NULL,
  contract_json TEXT NOT NULL
);
"""


PHASE_3_APPROVAL_PREVIEW_PERSISTENCE_READINESS_MIGRATION_ID = "RAIKER-1312-phase3-approval-preview-persistence-readiness-metadata"

PHASE_3_APPROVAL_PREVIEW_PERSISTENCE_READINESS_SQL = """
CREATE TABLE IF NOT EXISTS phase3_approval_preview_persistence_readiness (
  readiness_id TEXT PRIMARY KEY,
  target TEXT NOT NULL,
  status TEXT NOT NULL,
  blockers_json TEXT NOT NULL,
  disabled_runtime_flags_json TEXT NOT NULL,
  contract_json TEXT NOT NULL
);
"""


PHASE_3_STORAGE_CLEANUP_EXECUTION_READINESS_MIGRATION_ID = "RAIKER-1313-phase3-storage-cleanup-execution-readiness-metadata"

PHASE_3_STORAGE_CLEANUP_EXECUTION_READINESS_SQL = """
CREATE TABLE IF NOT EXISTS phase3_storage_cleanup_execution_readiness (
  readiness_id TEXT PRIMARY KEY,
  target TEXT NOT NULL,
  status TEXT NOT NULL,
  blockers_json TEXT NOT NULL,
  disabled_runtime_flags_json TEXT NOT NULL,
  contract_json TEXT NOT NULL
);
"""


PHASE_3_PLUGIN_SERVER_STARTUP_READINESS_MIGRATION_ID = "RAIKER-1314-phase3-plugin-server-startup-readiness-metadata"

PHASE_3_PLUGIN_SERVER_STARTUP_READINESS_SQL = """
CREATE TABLE IF NOT EXISTS phase3_plugin_server_startup_readiness (
  readiness_id TEXT PRIMARY KEY,
  target TEXT NOT NULL,
  status TEXT NOT NULL,
  blockers_json TEXT NOT NULL,
  disabled_runtime_flags_json TEXT NOT NULL,
  contract_json TEXT NOT NULL
);
"""
