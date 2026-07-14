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


PHASE_3_EXTERNAL_CHANNELS_NOTIFICATIONS_READINESS_MIGRATION_ID = "RAIKER-1315-phase3-external-channels-notifications-readiness-metadata"

PHASE_3_EXTERNAL_CHANNELS_NOTIFICATIONS_READINESS_SQL = """
CREATE TABLE IF NOT EXISTS phase3_external_channels_notifications_readiness (
  readiness_id TEXT PRIMARY KEY,
  target TEXT NOT NULL,
  status TEXT NOT NULL,
  blockers_json TEXT NOT NULL,
  disabled_runtime_flags_json TEXT NOT NULL,
  contract_json TEXT NOT NULL
);
"""


PHASE_3_REMOTE_CONTAINER_CLOUD_READINESS_MIGRATION_ID = "RAIKER-1316-phase3-remote-container-cloud-readiness-metadata"

PHASE_3_REMOTE_CONTAINER_CLOUD_READINESS_SQL = """
CREATE TABLE IF NOT EXISTS phase3_remote_container_cloud_readiness (
  readiness_id TEXT PRIMARY KEY,
  target TEXT NOT NULL,
  status TEXT NOT NULL,
  blockers_json TEXT NOT NULL,
  disabled_runtime_flags_json TEXT NOT NULL,
  contract_json TEXT NOT NULL
);
"""

PHASE_3_SLICE_A_PROPOSAL_LIFECYCLE_MIGRATION_ID = "RAIKER-1401-phase3-slice-a-proposal-lifecycle"

PHASE_3_SLICE_A_PROPOSAL_LIFECYCLE_SQL = """
CREATE TABLE IF NOT EXISTS proposal_lifecycle_records (
  proposal_id TEXT PRIMARY KEY,
  review_id TEXT NOT NULL,
  finding_id TEXT NOT NULL,
  title TEXT NOT NULL,
  action_type TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  requires_approval INTEGER NOT NULL,
  would_modify_files INTEGER NOT NULL,
  status TEXT NOT NULL,
  files_json TEXT NOT NULL,
  summary TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  source TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_proposal_lifecycle_status ON proposal_lifecycle_records(status);
CREATE INDEX IF NOT EXISTS idx_proposal_lifecycle_updated ON proposal_lifecycle_records(updated_at);
"""

PHASE_3_SLICE_B_APPROVAL_PLANNING_PREVIEW_MIGRATION_ID = "RAIKER-1402-phase3-slice-b-approval-planning-preview"

PHASE_3_SLICE_B_APPROVAL_PLANNING_PREVIEW_SQL = """
CREATE TABLE IF NOT EXISTS proposal_approval_previews (
  preview_id TEXT PRIMARY KEY,
  proposal_id TEXT NOT NULL,
  review_id TEXT NOT NULL,
  finding_id TEXT NOT NULL,
  proposal_status TEXT NOT NULL,
  action_type TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  requires_approval INTEGER NOT NULL,
  would_modify_files INTEGER NOT NULL,
  files_json TEXT NOT NULL,
  required_human_decision TEXT NOT NULL,
  required_safety_checks_json TEXT NOT NULL,
  blocking_conditions_json TEXT NOT NULL,
  recommended_next_action TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  source TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_approval_preview_proposal_id ON proposal_approval_previews(proposal_id);
CREATE INDEX IF NOT EXISTS idx_approval_preview_status ON proposal_approval_previews(status);
CREATE INDEX IF NOT EXISTS idx_approval_preview_created ON proposal_approval_previews(created_at);
"""

PHASE_4_MEMORY_MVP_MIGRATION_ID = "RAIKER-2001-phase4-memory-mvp-approved-memory"

PHASE_4_MEMORY_MVP_SQL = """
CREATE TABLE IF NOT EXISTS approved_memory (
  memory_id TEXT PRIMARY KEY,
  text TEXT NOT NULL,
  scope TEXT NOT NULL,
  sensitivity TEXT NOT NULL,
  source_event_id TEXT NOT NULL,
  memory_type TEXT NOT NULL,
  created_at TEXT NOT NULL,
  tags_json TEXT NOT NULL,
  source TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_approved_memory_scope ON approved_memory(scope);
CREATE INDEX IF NOT EXISTS idx_approved_memory_created ON approved_memory(created_at);
"""

PHASE_4_MEMORY_GOVERNANCE_HARDENING_MIGRATION_ID = (
    "RAIKER-2002-phase4-memory-governance-hardening"
)

PHASE_4_MEMORY_GOVERNANCE_HARDENING_SQL = """
ALTER TABLE approved_memory ADD COLUMN provenance_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE approved_memory ADD COLUMN confidence REAL NOT NULL DEFAULT 0.0;
ALTER TABLE approved_memory ADD COLUMN trust_score REAL NOT NULL DEFAULT 0.0;
ALTER TABLE approved_memory ADD COLUMN retention TEXT NOT NULL DEFAULT 'until_forget';
ALTER TABLE approved_memory ADD COLUMN approval_state TEXT NOT NULL DEFAULT 'approved';
ALTER TABLE approved_memory ADD COLUMN created_by TEXT NOT NULL DEFAULT 'system';
ALTER TABLE approved_memory ADD COLUMN updated_at TEXT;
ALTER TABLE approved_memory ADD COLUMN deleted_at TEXT;
ALTER TABLE approvals ADD COLUMN action_payload_sha256 TEXT;
"""

MODEL_SESSION_RESOLVED_MODEL_MIGRATION_ID = "RAIKER-1203-model-session-resolved-model"

MODEL_SESSION_RESOLVED_MODEL_SQL = """
ALTER TABLE model_session_state ADD COLUMN model TEXT;
"""

PHASE_5_MANAGED_POLICY_MIGRATION_ID = "RAIKER-5001-phase5-managed-policy"

PHASE_5_MANAGED_POLICY_SQL = """
CREATE TABLE IF NOT EXISTS managed_policies (
  rule_id TEXT PRIMARY KEY,
  effect TEXT NOT NULL,
  tool_pattern TEXT NOT NULL,
  arguments_json TEXT,
  priority INTEGER NOT NULL DEFAULT 100,
  enabled INTEGER NOT NULL DEFAULT 1,
  reason TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_managed_policies_enabled ON managed_policies(enabled);
CREATE INDEX IF NOT EXISTS idx_managed_policies_priority ON managed_policies(priority);
"""

PHASE_5_ORG_ROLES_MIGRATION_ID = "RAIKER-5101-phase5-org-roles"

PHASE_5_ORG_ROLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
  user_id TEXT PRIMARY KEY,
  display_name TEXT,
  email TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS roles (
  role_id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  is_system_role INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_role_assignments (
  assignment_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(user_id),
  role_id TEXT NOT NULL REFERENCES roles(role_id),
  granted_at TEXT NOT NULL,
  granted_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_user_role_user ON user_role_assignments(user_id);
CREATE INDEX IF NOT EXISTS idx_user_role_role ON user_role_assignments(role_id);
"""

PHASE_5_PLUGIN_MARKETPLACE_MIGRATION_ID = "RAIKER-5301-phase5-plugin-marketplace"

PHASE_5_PLUGIN_MARKETPLACE_SQL = """
CREATE TABLE IF NOT EXISTS plugin_install_records (
  record_id TEXT PRIMARY KEY,
  plugin_id TEXT NOT NULL,
  version TEXT NOT NULL,
  trust_level TEXT NOT NULL,
  checksum TEXT,
  signature TEXT,
  source_url TEXT,
  commit_sha TEXT,
  permissions_json TEXT NOT NULL,
  status TEXT NOT NULL,
  installed_at TEXT NOT NULL,
  installed_by TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_plugin_install_plugin_id ON plugin_install_records(plugin_id);
CREATE INDEX IF NOT EXISTS idx_plugin_install_status ON plugin_install_records(status);
"""

PHASE_5_HOSTED_ROUTINES_MIGRATION_ID = "RAIKER-5401-phase5-hosted-routines"

PHASE_5_HOSTED_ROUTINES_SQL = """
CREATE TABLE IF NOT EXISTS hosted_routines (
  routine_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  routine_type TEXT NOT NULL,
  schedule TEXT,
  endpoint TEXT,
  enabled INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""

PHASE_5_BUDGET_RECORDS_MIGRATION_ID = "RAIKER-5501-phase5-budget-records"

PHASE_5_BUDGET_RECORDS_SQL = """
CREATE TABLE IF NOT EXISTS budget_records (
  budget_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  max_cost REAL NOT NULL,
  current_cost REAL NOT NULL DEFAULT 0.0,
  currency TEXT NOT NULL DEFAULT 'USD',
  scope TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""

PHASE_5_RETENTION_POLICIES_MIGRATION_ID = "RAIKER-5601-phase5-retention-policies"

PHASE_5_RETENTION_POLICIES_SQL = """
CREATE TABLE IF NOT EXISTS retention_policies (
  policy_id TEXT PRIMARY KEY,
  target_type TEXT NOT NULL,
  retention_days INTEGER NOT NULL,
  legal_hold INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS backup_manifests (
  manifest_id TEXT PRIMARY KEY,
  backup_type TEXT NOT NULL,
  scope_json TEXT NOT NULL,
  path TEXT,
  checksum TEXT,
  size_bytes INTEGER,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""

PHASE_6_CHANNEL_PAIRINGS_MIGRATION_ID = "RAIKER-6001-phase6-channel-pairings"

PHASE_6_CHANNEL_PAIRINGS_SQL = """
CREATE TABLE IF NOT EXISTS channel_pairings (
  pairing_id TEXT PRIMARY KEY,
  connector_id TEXT NOT NULL,
  channel_type TEXT NOT NULL,
  display_name TEXT NOT NULL,
  paired_at TEXT NOT NULL,
  paired_by TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 0,
  sender_allowlist_json TEXT NOT NULL DEFAULT '[]'
);
"""

PHASE_6_APPROVAL_RELAY_MIGRATION_ID = "RAIKER-6101-phase6-approval-relay"

PHASE_6_APPROVAL_RELAY_SQL = """
CREATE TABLE IF NOT EXISTS approval_relay_records (
  relay_id TEXT PRIMARY KEY,
  pairing_id TEXT NOT NULL,
  action_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  requested_at TEXT NOT NULL,
  resolved_at TEXT,
  resolved_by TEXT
);
"""

PHASE_6_SUBAGENTS_MIGRATION_ID = "RAIKER-6201-phase6-subagents"

PHASE_6_SUBAGENTS_SQL = """
CREATE TABLE IF NOT EXISTS subagent_contracts (
  subagent_id TEXT PRIMARY KEY,
  parent_task_id TEXT NOT NULL,
  name TEXT NOT NULL,
  mode TEXT NOT NULL,
  allowed_tools_json TEXT NOT NULL,
  max_depth INTEGER NOT NULL DEFAULT 1,
  max_runtime_seconds INTEGER NOT NULL DEFAULT 300,
  max_cost REAL NOT NULL DEFAULT 0.0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'created'
);
"""

PHASE_6_TEAMS_MIGRATION_ID = "RAIKER-6301-phase6-teams"

PHASE_6_TEAMS_SQL = """
CREATE TABLE IF NOT EXISTS team_ledgers (
  team_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  mode TEXT NOT NULL,
  members_json TEXT NOT NULL,
  max_depth INTEGER NOT NULL DEFAULT 1,
  max_cost REAL NOT NULL DEFAULT 0.0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'created'
);
"""

PHASE_6_REMOTE_EXECUTION_MIGRATION_ID = "RAIKER-6401-phase6-remote-execution"

PHASE_6_REMOTE_EXECUTION_SQL = """
CREATE TABLE IF NOT EXISTS remote_execution_profiles (
  profile_id TEXT PRIMARY KEY,
  profile_type TEXT NOT NULL,
  name TEXT NOT NULL,
  config_json TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_budgets (
  budget_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  max_cost REAL NOT NULL,
  current_cost REAL NOT NULL DEFAULT 0.0,
  currency TEXT NOT NULL DEFAULT 'USD',
  profile_id TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""

PHASE_7_DESKTOP_SESSIONS_MIGRATION_ID = "RAIKER-7001-phase7-desktop-sessions"

PHASE_7_DESKTOP_SESSIONS_SQL = """
CREATE TABLE IF NOT EXISTS desktop_app_sessions (
  session_id TEXT PRIMARY KEY,
  app_version TEXT NOT NULL,
  window_state TEXT NOT NULL DEFAULT 'normal',
  connected_at TEXT NOT NULL,
  last_active_at TEXT NOT NULL
);
"""

PHASE_7_WEB_SESSIONS_MIGRATION_ID = "RAIKER-7101-phase7-web-sessions"

PHASE_7_WEB_SESSIONS_SQL = """
CREATE TABLE IF NOT EXISTS web_api_sessions (
  token_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  client_type TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
"""

PHASE_7_PLUGIN_EXECUTION_MIGRATION_ID = "RAIKER-7401-phase7-plugin-execution"

PHASE_7_PLUGIN_EXECUTION_SQL = """
CREATE TABLE IF NOT EXISTS plugin_execution_records (
  execution_id TEXT PRIMARY KEY,
  plugin_id TEXT NOT NULL,
  version TEXT NOT NULL,
  trust_level TEXT NOT NULL,
  permissions_json TEXT NOT NULL,
  entrypoint TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'planned',
  started_at TEXT,
  completed_at TEXT,
  created_by TEXT NOT NULL
);
"""

PHASE_7_GRAPH_INDEX_MIGRATION_ID = "RAIKER-7501-phase7-graph-index"

PHASE_7_GRAPH_INDEX_SQL = """
CREATE TABLE IF NOT EXISTS graph_index_records (
  index_id TEXT PRIMARY KEY,
  workspace_root TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'requested',
  nodes_count INTEGER NOT NULL DEFAULT 0,
  edges_count INTEGER NOT NULL DEFAULT 0,
  started_at TEXT,
  completed_at TEXT,
  created_by TEXT NOT NULL
);
"""

PHASE_7_SEMANTIC_MEMORY_MIGRATION_ID = "RAIKER-7601-phase7-semantic-memory"

PHASE_7_SEMANTIC_MEMORY_SQL = """
CREATE TABLE IF NOT EXISTS semantic_memory_write_records (
  write_id TEXT PRIMARY KEY,
  content_summary TEXT NOT NULL,
  embedding_model TEXT NOT NULL,
  vector_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'requested',
  approved_by TEXT,
  created_at TEXT NOT NULL
);
"""

PHASE_7_IDE_SESSIONS_MIGRATION_ID = "RAIKER-7701-phase7-ide-sessions"

PHASE_7_IDE_SESSIONS_SQL = """
CREATE TABLE IF NOT EXISTS ide_extension_sessions (
  session_id TEXT PRIMARY KEY,
  extension_version TEXT NOT NULL,
  ide_type TEXT NOT NULL,
  connected_at TEXT NOT NULL
);
"""

PHASE_9_VECTOR_INDEX_MIGRATION_ID = "RAIKER-9001-phase9-vector-index"

PHASE_9_VECTOR_INDEX_SQL = """
CREATE TABLE IF NOT EXISTS vector_records (
  vector_id TEXT PRIMARY KEY,
  content_hash TEXT NOT NULL,
  content_preview TEXT NOT NULL,
  embedding_model TEXT NOT NULL,
  dimensions INTEGER NOT NULL,
  scope TEXT NOT NULL DEFAULT 'default',
  sensitivity TEXT NOT NULL DEFAULT 'public',
  created_at TEXT NOT NULL
);
"""

PHASE_9_SYMBOL_GRAPH_MIGRATION_ID = "RAIKER-9101-phase9-symbol-graph"

PHASE_9_SYMBOL_GRAPH_SQL = """
CREATE TABLE IF NOT EXISTS symbol_nodes (
  symbol_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  file_path TEXT NOT NULL,
  line_number INTEGER NOT NULL,
  module TEXT NOT NULL,
  parent_symbol_id TEXT,
  doc_preview TEXT
);

CREATE TABLE IF NOT EXISTS dependency_edges (
  edge_id TEXT PRIMARY KEY,
  source_symbol_id TEXT NOT NULL,
  target_symbol_id TEXT NOT NULL,
  dep_type TEXT NOT NULL,
  file_path TEXT NOT NULL,
  line_number INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
"""

PHASE_9_PROJECT_GRAPH_MIGRATION_ID = "RAIKER-9201-phase9-project-graph"

PHASE_9_PROJECT_GRAPH_SQL = """
CREATE TABLE IF NOT EXISTS project_graphs (
  graph_id TEXT PRIMARY KEY,
  workspace_root TEXT NOT NULL,
  module_count INTEGER NOT NULL DEFAULT 0,
  dependency_count INTEGER NOT NULL DEFAULT 0,
  built_at TEXT NOT NULL
);
"""

PHASE_9_SKILL_CANDIDATES_MIGRATION_ID = "RAIKER-9301-phase9-skill-candidates"

PHASE_9_SKILL_CANDIDATES_SQL = """
CREATE TABLE IF NOT EXISTS skill_candidates (
  candidate_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  source_workflow_json TEXT NOT NULL,
  suggested_tools_json TEXT NOT NULL,
  provenance TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'proposed',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""

PHASE_10_RUNTIME_AUTHORITY_MIGRATION_ID = "RAIKER-10001-phase10-runtime-authority"

PHASE_10_RUNTIME_AUTHORITY_SQL = """
CREATE TABLE IF NOT EXISTS principals (
  principal_id TEXT PRIMARY KEY,
  principal_type TEXT NOT NULL,
  display_name TEXT NOT NULL,
  delegated_by_user_id TEXT,
  model_profile_id TEXT,
  session_id TEXT,
  role_ids TEXT NOT NULL DEFAULT '[]',
  domain_scopes TEXT NOT NULL DEFAULT '[]',
  max_runtime_mode TEXT NOT NULL DEFAULT 'development_preview',
  created_at TEXT NOT NULL,
  expires_at TEXT,
  is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS risk_acceptances (
  risk_acceptance_id TEXT PRIMARY KEY,
  accepted_by TEXT NOT NULL,
  accepted_for_principal_id TEXT NOT NULL,
  action_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  domain_scope TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  risk_summary TEXT NOT NULL,
  data_involved TEXT NOT NULL,
  expected_effect TEXT NOT NULL,
  one_time_or_reusable TEXT NOT NULL DEFAULT 'one_time',
  expires_at TEXT,
  created_at TEXT NOT NULL,
  policy_decision_id TEXT,
  approval_id TEXT
);
"""

PHASE_5_AUDIT_EXPORT_MIGRATION_ID = "RAIKER-5201-phase5-audit-export"

PHASE_5_AUDIT_EXPORT_SQL = """
CREATE TABLE IF NOT EXISTS audit_exports (
  export_id TEXT PRIMARY KEY,
  manifest_hash TEXT NOT NULL,
  scope_json TEXT NOT NULL,
  redacted INTEGER NOT NULL DEFAULT 1,
  event_count INTEGER NOT NULL,
  first_event_id TEXT,
  last_event_id TEXT,
  first_timestamp TEXT,
  last_timestamp TEXT,
  export_path TEXT,
  exported_by TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""

PHASE_10_RUNTIME_MODE_STATE_MIGRATION_ID = "RAIKER-1001-runtime-mode-state"

PHASE_10_RUNTIME_MODE_STATE_SQL = """
CREATE TABLE IF NOT EXISTS runtime_mode_state (
  runtime_mode_id TEXT PRIMARY KEY,
  mode_name TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('inactive', 'active', 'disabled')),
  activated_by TEXT,
  activated_at TEXT,
  disabled_by TEXT,
  disabled_at TEXT,
  reason TEXT,
  risk_acceptance_id TEXT,
  approval_id TEXT,
  policy_decision_id TEXT,
  validation_evidence_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""

PHASE_10_CAPABILITY_GATE_STATE_MIGRATION_ID = "RAIKER-1002-capability-gate-state"

PHASE_10_CAPABILITY_GATE_STATE_SQL = """
CREATE TABLE IF NOT EXISTS capability_gate_state (
  capability TEXT PRIMARY KEY,
  state TEXT NOT NULL,
  runtime_mode TEXT,
  requested_by TEXT,
  requested_at TEXT,
  activated_by TEXT,
  activated_at TEXT,
  disabled_by TEXT,
  disabled_at TEXT,
  reason TEXT,
  readiness_snapshot_json TEXT,
  risk_acceptance_id TEXT,
  approval_id TEXT,
  policy_decision_id TEXT,
  event_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""

# ── Calendar events & email drafts (Tier-6, local-only) ──────────────────────

CALENDAR_EVENTS_MIGRATION_ID = "RAIKER-6003-calendar-events"

CALENDAR_EVENTS_SQL = """
CREATE TABLE IF NOT EXISTS calendar_events (
  event_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  starts_at TEXT,
  ends_at TEXT,
  location TEXT,
  notes TEXT,
  status TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""

EMAIL_DRAFTS_MIGRATION_ID = "RAIKER-6004-email-drafts"

EMAIL_DRAFTS_SQL = """
CREATE TABLE IF NOT EXISTS email_drafts (
  draft_id TEXT PRIMARY KEY,
  subject TEXT NOT NULL,
  recipients TEXT,
  body TEXT,
  status TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""

# ── Reminders (Tier-6 reminder_runtime, local-only) ──────────────────────────

REMINDERS_MIGRATION_ID = "RAIKER-6002-reminders"

REMINDERS_SQL = """
CREATE TABLE IF NOT EXISTS reminders (
  reminder_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  due_at TEXT,
  notes TEXT,
  status TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""

# ── Capability Decision Modes (Ask / Deny / Always Allow / Auto) ─────────────

CAPABILITY_DECISION_MODE_MIGRATION_ID = "RAIKER-1003-capability-decision-mode"

CAPABILITY_DECISION_MODE_SQL = """
CREATE TABLE IF NOT EXISTS capability_decision_mode (
  capability TEXT PRIMARY KEY,
  decision_mode TEXT NOT NULL,
  set_by TEXT,
  set_at TEXT,
  reason TEXT,
  event_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""

# ── Threat Model Acks (Workstream C) ─────────────────────────────────────────

THREAT_MODEL_ACKS_MIGRATION_ID = "RAIKER-11002-threat-model-acks"

THREAT_MODEL_ACKS_SQL = """
CREATE TABLE IF NOT EXISTS threat_model_acks (
  capability TEXT PRIMARY KEY,
  acked_by TEXT NOT NULL,
  acked_at TEXT NOT NULL,
  doc_ref TEXT NOT NULL DEFAULT ''
);
"""

# ── API Sessions (Workstream B) ─────────────────────────────────────────────

API_SESSIONS_MIGRATION_ID = "RAIKER-11001-api-sessions"

API_SESSIONS_SQL = """
CREATE TABLE IF NOT EXISTS api_sessions (
  session_id TEXT PRIMARY KEY,
  principal_id TEXT NOT NULL REFERENCES principals(principal_id),
  token_hash TEXT NOT NULL,
  scopes TEXT NOT NULL DEFAULT '["control"]',
  created_at TEXT NOT NULL,
  expires_at TEXT,
  revoked INTEGER NOT NULL DEFAULT 0
);
"""

# ── Phase 4 slice 2: local scheduled routines (on-demand, no daemon) ─────────

PHASE_4_SCHEDULED_ROUTINES_MIGRATION_ID = "RAIKER-2002-phase4-scheduled-routines"

PHASE_4_SCHEDULED_ROUTINES_SQL = """
CREATE TABLE IF NOT EXISTS scheduled_routines (
  routine_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  interval_seconds INTEGER NOT NULL,
  payload_json TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 0,
  next_run TEXT NOT NULL,
  last_run TEXT,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'scheduled'
);
"""

# Ordered, user-owned model fallback sequence. When the actively selected model
# provider is unavailable (no network, timeout, non-responsive host, policy
# denial), the runtime walks this ordered list of profile ids and tries the next
# one — typically a local backend (llama.cpp / Ollama / LM Studio / vLLM). Each
# candidate is still resolved and gated through the model router, so fallback can
# never bypass provider policy. Stored one ordered list per client session id.
MODEL_FALLBACK_SEQUENCE_MIGRATION_ID = "RAIKER-1004-model-fallback-sequence"

MODEL_FALLBACK_SEQUENCE_SQL = """
CREATE TABLE IF NOT EXISTS model_fallback_sequence (
  session_id TEXT PRIMARY KEY,
  profile_ids_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""

# Web-app task 2: the user-owned advisor model. A single profile id per client
# session — the (typically hosted) model a local model may consult through the
# governed `consult_advisor` tool. Persisting the choice grants nothing: the
# consult is gated by advisor_model_runtime + its decision mode, and the
# provider call re-checks the hosted/private gate, egress allowlist, and key.
MODEL_ADVISOR_MIGRATION_ID = "RAIKER-1005-model-advisor"

MODEL_ADVISOR_SQL = """
CREATE TABLE IF NOT EXISTS model_advisor (
  session_id TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""

# Web-app task 3 (uploaded attachments): the governed local attachment store.
# Uploaded bytes land here only after fail-closed validation (media-type
# allowlist, size cap, magic-byte sniff) and are always treated as untrusted
# data. Content is delivered to a model solely as an image block on a
# vision-capable profile — attachment bytes never enter event payloads or
# text context (metadata only: filename, media type, size, sha256).
# Web-app task 5: project folders. A project is a named organizing scope — its
# own workspace subpath plus the sessions (and, via sessions, checkpoints) that
# belong to it. Governance-neutral by design: a project grants no authority and
# its root_subpath is always contained inside the workspace (enforced by the
# service; the subpath is derived server-side, never taken from the client).
# active_project persists which project new sessions are stamped with, one row
# per scope (the local single-user runtime uses a single fixed scope id).
PROJECTS_MIGRATION_ID = "RAIKER-1007-projects"

PROJECTS_SQL = """
CREATE TABLE IF NOT EXISTS projects (
  project_id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  root_subpath TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS active_project (
  scope_id TEXT PRIMARY KEY,
  project_id TEXT REFERENCES projects(project_id),
  updated_at TEXT NOT NULL
);
"""

ATTACHMENT_STORE_MIGRATION_ID = "RAIKER-1006-attachment-store"

ATTACHMENT_STORE_SQL = """
CREATE TABLE IF NOT EXISTS attachments (
  attachment_id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  filename TEXT NOT NULL,
  media_type TEXT NOT NULL,
  byte_size INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  data BLOB NOT NULL,
  created_at TEXT NOT NULL
);
"""

PROJECT_CONTEXT_MIGRATION_ID = "RAIKER-1010-project-context"
PROJECT_CONTEXT_SQL = """
CREATE TABLE IF NOT EXISTS project_contexts (
  project_id TEXT PRIMARY KEY REFERENCES projects(project_id) ON DELETE CASCADE,
  instructions TEXT NOT NULL DEFAULT '',
  attachment_ids_json TEXT NOT NULL DEFAULT '[]',
  memory_enabled INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);
"""

# Manifest-driven outbound connector ecosystem. Catalog metadata remains in a
# versioned config file; these tables hold only per-principal lifecycle state,
# encrypted credentials, validated manifests, and action-bound write intents.
CONNECTOR_ECOSYSTEM_MIGRATION_ID = "RAIKER-1008-connector-ecosystem"

CONNECTOR_ECOSYSTEM_SQL = """
CREATE TABLE IF NOT EXISTS connector_installations (
  principal_id TEXT NOT NULL,
  connector_id TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 0,
  auth_status TEXT NOT NULL DEFAULT 'not_connected',
  installed_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (principal_id, connector_id)
);

CREATE TABLE IF NOT EXISTS connector_credentials (
  principal_id TEXT NOT NULL,
  connector_id TEXT NOT NULL,
  encrypted_payload BLOB NOT NULL,
  expires_at TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (principal_id, connector_id)
);

CREATE TABLE IF NOT EXISTS connector_manifests (
  connector_id TEXT PRIMARY KEY,
  manifest_json TEXT NOT NULL,
  manifest_sha256 TEXT NOT NULL,
  installed_by TEXT NOT NULL,
  installed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS connector_write_intents (
  intent_id TEXT PRIMARY KEY,
  approval_id TEXT UNIQUE,
  principal_id TEXT NOT NULL,
  connector_id TEXT NOT NULL,
  operation_id TEXT NOT NULL,
  arguments_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  executed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_connector_installations_principal
  ON connector_installations(principal_id);
CREATE INDEX IF NOT EXISTS idx_connector_intents_approval
  ON connector_write_intents(approval_id);
"""

CONNECTOR_INVOCATIONS_MIGRATION_ID = "RAIKER-1009-connector-invocations"
CONNECTOR_INVOCATIONS_SQL = """
CREATE TABLE IF NOT EXISTS connector_invocations (
  invocation_id TEXT PRIMARY KEY,
  principal_id TEXT NOT NULL,
  connector_id TEXT NOT NULL,
  operation_id TEXT NOT NULL,
  method TEXT NOT NULL,
  status TEXT NOT NULL,
  session_id TEXT,
  started_at TEXT NOT NULL,
  completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_connector_invocations_lifecycle
  ON connector_invocations(principal_id, connector_id, started_at DESC);
"""


LOCK_SCREEN_MIGRATION_ID = "RAIKER-6001-local-lock-screen"
LOCK_SCREEN_SQL = """
CREATE TABLE IF NOT EXISTS account_credentials (
  principal_id TEXT PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  hash_algo TEXT NOT NULL,
  failed_attempts INTEGER NOT NULL DEFAULT 0,
  locked_until TEXT,
  mfa_enrolled INTEGER NOT NULL DEFAULT 0,
  mfa_secret_encrypted BLOB,
  backup_codes_hashed TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_settings (
  principal_id TEXT PRIMARY KEY,
  settings_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trusted_contacts (
  contact_id TEXT PRIMARY KEY,
  principal_id TEXT NOT NULL,
  name TEXT NOT NULL,
  method TEXT NOT NULL,
  value TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_account_username ON account_credentials(username);
CREATE INDEX IF NOT EXISTS idx_trusted_contacts_principal ON trusted_contacts(principal_id);
"""

# Reliable memory controls (backlog item 3): a user-visible memory list with
# pin/bookmark + an incognito opt-out boundary. memory_pins is an organizing
# label (grants nothing, like session/project pins). memory_settings is a
# single-row table (one scope id) holding the incognito flag; when it is on,
# the context gatherer withholds approved project memory from the turn context.
MEMORY_CONTROLS_MIGRATION_ID = "RAIKER-1008-memory-controls"

MEMORY_CONTROLS_SQL = """
CREATE TABLE IF NOT EXISTS memory_pins (
  memory_id TEXT PRIMARY KEY,
  pinned INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_settings (
  scope_id TEXT PRIMARY KEY,
  incognito INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);
"""

# Conversation organisation (backlog item 2 remainder): session tags. A tag is
# an organizing label only — like the per-session `pinned` flag and the
# `projects` table, it grants nothing and changes no gate, policy, or
# authority. Many-to-many: one session may carry many tags and the same tag
# may be reused across sessions. FK ON DELETE CASCADE mirrors the explicit
# cascade in delete_session/delete_project so rows are never orphaned.
SESSION_TAGS_MIGRATION_ID = "RAIKER-1011-session-tags"

SESSION_TAGS_SQL = """
CREATE TABLE IF NOT EXISTS session_tags (
  session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
  tag TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (session_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_session_tags_tag ON session_tags(tag);
"""

# Nested projects/folders (conversation organisation remainder): arbitrary-depth
# folder hierarchy via hybrid adjacency list + materialized path. Parent
# reference uses ON DELETE SET NULL so children survive parent hard-delete.
# Path trigger auto-syncs on parent_id change. Partial index on active tree.
PROJECTS_NESTING_MIGRATION_ID = "RAIKER-1012-projects-nesting"

PROJECTS_NESTING_SQL = """
ALTER TABLE projects ADD COLUMN parent_id TEXT REFERENCES projects(project_id) ON DELETE SET NULL;
ALTER TABLE projects ADD COLUMN path TEXT NOT NULL DEFAULT '/';
ALTER TABLE projects ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0;
ALTER TABLE projects ADD COLUMN archived_at TEXT;
ALTER TABLE projects ADD COLUMN updated_at TEXT;

CREATE INDEX IF NOT EXISTS idx_projects_parent ON projects(parent_id);
CREATE INDEX IF NOT EXISTS idx_active_projects_path ON projects(path) WHERE is_archived = 0;
CREATE INDEX IF NOT EXISTS idx_all_projects_path ON projects(path);
"""
