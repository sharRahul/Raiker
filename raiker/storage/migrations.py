from __future__ import annotations

PHASE_1_MIGRATION_ID = "RAIKER-0201-phase1-bootstrap"
LEGACY_ACCOUNT_BOOTSTRAP_ROLES_MIGRATION_ID = "RAIKER-2021-legacy-account-bootstrap-roles"
OWNED_CONTEXT_DATA_MIGRATION_ID = "RAIKER-2022-owned-context-data"
OWNED_MEMORY_METADATA_MIGRATION_ID = "RAIKER-2023-owned-memory-metadata"

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
  max_runtime_mode TEXT NOT NULL DEFAULT 'raiker_runtime',
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

# Safe session lifecycle (Control Deck task 3): a per-session soft-archive
# state. Archiving is a reversible organizing action — it never deletes
# transcripts, events, checkpoints, or permissions; it only moves a session out
# of the default active list. `archived` defaults to 0 (active) so every
# existing row stays visible; `archived_at` records when it was last archived.
# The owner/archive/updated_at index serves the default active listing, which
# filters by owner and archived state and orders by recency. Additive columns
# only — grants nothing and changes no gate, policy, or authority.
SESSION_ARCHIVE_MIGRATION_ID = "RAIKER-1015-session-archive-lifecycle"

SESSION_ARCHIVE_SQL = """
ALTER TABLE sessions ADD COLUMN archived INTEGER NOT NULL DEFAULT 0;
ALTER TABLE sessions ADD COLUMN archived_at TEXT;
CREATE INDEX IF NOT EXISTS idx_sessions_owner_archived_updated ON sessions(user_id, archived, updated_at DESC);
"""

# Governed local MCP builder + connector (Control Deck task 4): an owner-scoped
# registry of local stdio MCP server profiles the owner has built or connected.
# `command` is the JSON-encoded argv (interpreter + workspace-relative script);
# it is owner-configured, allowlist-validated at execution time, and never a
# remote endpoint. `principal_id` scopes every row to its creator so one owner
# can never see or reach another owner's servers. No secrets or tool payloads
# are stored here — only the profile metadata. Additive table only.
MCP_SERVERS_MIGRATION_ID = "RAIKER-1016-mcp-server-profiles"

MCP_SERVERS_SQL = """
CREATE TABLE IF NOT EXISTS mcp_servers (
  server_id TEXT PRIMARY KEY,
  principal_id TEXT NOT NULL,
  name TEXT NOT NULL,
  command TEXT NOT NULL,
  template TEXT,
  transport TEXT NOT NULL DEFAULT 'stdio',
  status TEXT NOT NULL DEFAULT 'created',
  created_at TEXT NOT NULL,
  last_connected_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_mcp_servers_owner ON mcp_servers(principal_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_mcp_servers_owner_name ON mcp_servers(principal_id, name);
"""

# MCP server runtime state (Control Deck task 4b): the last handshake's outcome
# for a server profile — the JSON-encoded list of tool names the connector
# discovered and their count. Recorded so the management page can show each
# server's tools without re-spawning it on every page load. Tool names are not
# secrets; no tool arguments or output are ever stored. Additive columns only.
MCP_SERVER_RUNTIME_MIGRATION_ID = "RAIKER-1017-mcp-server-runtime-state"

MCP_SERVER_RUNTIME_SQL = """
ALTER TABLE mcp_servers ADD COLUMN tools TEXT;
ALTER TABLE mcp_servers ADD COLUMN tool_count INTEGER NOT NULL DEFAULT 0;
"""

# Remote MCP endpoints (monitored MCP connections, Phase A): a connection can be
# a local stdio server (command) or a remote HTTP MCP server. `endpoint_url` is
# the owner-added remote URL (null for stdio); `auth_ref` names *where* the owner
# token lives (an env var name), never the token itself — the token is read at
# call time and never stored or logged. The owner adding a URL is the
# authorization; the connection is monitored, not allowlist-blocked. Additive.
MCP_REMOTE_ENDPOINT_MIGRATION_ID = "RAIKER-1018-mcp-remote-endpoint"

MCP_REMOTE_ENDPOINT_SQL = """
ALTER TABLE mcp_servers ADD COLUMN endpoint_url TEXT;
ALTER TABLE mcp_servers ADD COLUMN auth_ref TEXT;
"""

# Per-session MCP monitoring + anomaly detection (monitored MCP connections,
# Phase B) plus the shared redacted-findings substrate (also used by Control
# Deck Task 5 self-monitoring). Two additive tables:
#
# `mcp_session_log` — one row per governed MCP session, redacted metadata only:
#   the tool-call count, the hosts contacted (netloc only, never a full URL or
#   query), byte counts, error count, and outcome. **No payloads, tokens, or
#   host secrets are ever stored here** — the monitor classifies value *shapes*
#   transiently and keeps only labels/counts. `principal_id` scopes every row to
#   its owner. Rolling rows form each connection's baseline.
#
# `security_findings` — a redacted finding raised by a monitor (`source`, e.g.
#   `mcp_monitor`). `redacted_detail_json` holds only redacted metadata (labels,
#   counts, hostnames, added/removed tool names), never a raw value. `subject_id`
#   is a generic reference to what the finding is about (the MCP `server_id` for
#   `mcp_monitor` findings). `state` moves open → acknowledged → resolved. Shared
#   with Task 5. Owner-scoped by `principal_id`.
MCP_MONITORING_MIGRATION_ID = "RAIKER-1019-mcp-monitoring"

MCP_MONITORING_SQL = """
CREATE TABLE IF NOT EXISTS mcp_session_log (
  session_row_id TEXT PRIMARY KEY,
  server_id TEXT,
  principal_id TEXT NOT NULL,
  transport TEXT NOT NULL DEFAULT 'stdio',
  operation TEXT NOT NULL,
  hosts_json TEXT,
  tool_calls INTEGER NOT NULL DEFAULT 0,
  bytes_in INTEGER NOT NULL DEFAULT 0,
  bytes_out INTEGER NOT NULL DEFAULT 0,
  error_count INTEGER NOT NULL DEFAULT 0,
  outcome TEXT NOT NULL DEFAULT 'ok',
  started_at TEXT NOT NULL,
  ended_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_mcp_session_log_conn
  ON mcp_session_log(principal_id, server_id, started_at DESC);

CREATE TABLE IF NOT EXISTS security_findings (
  finding_id TEXT PRIMARY KEY,
  principal_id TEXT NOT NULL,
  source TEXT NOT NULL,
  severity TEXT NOT NULL,
  code TEXT NOT NULL,
  summary TEXT NOT NULL,
  redacted_detail_json TEXT,
  subject_id TEXT,
  state TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_security_findings_owner
  ON security_findings(principal_id, source, state, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_security_findings_subject
  ON security_findings(principal_id, subject_id, created_at DESC);
"""

# Notify + instant kill switch + revocable auto-pause circuit breaker
# (monitored MCP connections, Phase C). Two additive parts:
#
# 1. `mcp_servers` gains a monitoring/lifecycle state so a connection can be
#    contained without deleting it: `monitor_state` is `active` | `paused` |
#    `killed`. `paused` is the revocable circuit breaker a high-severity anomaly
#    trips (and the owner's one-call stop); `killed` is the instant kill switch.
#    Both are revocable by the owner (resume → `active`). `paused_reason` /
#    `paused_at` record why and when, redacted (a rule code + summary, never a
#    payload). Containment is never an owner-facing ban — it keeps a
#    frictionless-by-default posture safe when the owner is away.
#
# 2. `notifications` — the shared owner-facing notification substrate (also used
#    by Control Deck Task 5). One row per notification: `kind`, `title`, `body`
#    (all redacted, human-readable copy), an optional `finding_id` / `subject_id`
#    link back to what raised it, and a `read` flag. Owner-scoped by
#    `principal_id`. Every finding and every containment transition raises one.
MCP_CONTAINMENT_MIGRATION_ID = "RAIKER-1020-mcp-containment-notifications"

MCP_CONTAINMENT_SQL = """
ALTER TABLE mcp_servers ADD COLUMN monitor_state TEXT NOT NULL DEFAULT 'active';
ALTER TABLE mcp_servers ADD COLUMN paused_reason TEXT;
ALTER TABLE mcp_servers ADD COLUMN paused_at TEXT;

CREATE TABLE IF NOT EXISTS notifications (
  notification_id TEXT PRIMARY KEY,
  principal_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  finding_id TEXT,
  subject_id TEXT,
  read INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notifications_owner
  ON notifications(principal_id, read, created_at DESC);
"""

# Control Deck Task 5: owner-scoped credential lifecycle metadata and monitor
# transition state. These rows deliberately contain labels, timestamps, and
# finding ids only; encrypted credential material remains in connector_credentials.
CREDENTIAL_SECURITY_MIGRATION_ID = "RAIKER-1021-credential-security"

CREDENTIAL_SECURITY_SQL = """
CREATE TABLE IF NOT EXISTS credential_lifecycle (
  credential_id TEXT PRIMARY KEY,
  principal_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  rotated_at TEXT NOT NULL,
  verified_at TEXT,
  due_at TEXT NOT NULL,
  status TEXT NOT NULL,
  UNIQUE(principal_id, provider)
);
CREATE INDEX IF NOT EXISTS idx_credential_lifecycle_owner
  ON credential_lifecycle(principal_id, status, due_at);

CREATE TABLE IF NOT EXISTS security_monitor_state (
  principal_id TEXT NOT NULL,
  source TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  code TEXT NOT NULL,
  state TEXT NOT NULL,
  finding_id TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(principal_id, source, subject_id, code)
);
"""

# Workstream B / Slice B1 — checkpoint capture manifest. Each mutation executed
# through the broker/relay records the *pre-image* of the file it is about to
# overwrite (or the absence of a not-yet-existing file) as a content-addressed
# blob under `.raiker/checkpoints/objects/`; this table is the metadata-only
# manifest that maps a governed mutation to the blob hash of its pre-image, so a
# later restore (B2) can put the file back byte-for-byte. Only metadata lives
# here and in the event log — never file content. `capture_status` is one of
# `captured` (pre-image blob stored), `absent` (file did not exist; restore =
# delete), or `oversize` (file exceeded the size cap and could not be snapshot,
# so it is not restorable — recorded honestly rather than silently dropped).
CHECKPOINT_CAPTURE_MANIFEST_MIGRATION_ID = "RAIKER-1201-checkpoint-capture-manifest"

CHECKPOINT_CAPTURE_MANIFEST_SQL = """
CREATE TABLE IF NOT EXISTS checkpoint_capture_manifest (
  manifest_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  turn_id TEXT,
  action_id TEXT NOT NULL,
  capability TEXT NOT NULL,
  principal_id TEXT,
  workspace_path TEXT NOT NULL,
  pre_image_sha256 TEXT,
  pre_image_size INTEGER NOT NULL DEFAULT 0,
  existed_before INTEGER NOT NULL DEFAULT 0,
  capture_status TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_checkpoint_capture_session
  ON checkpoint_capture_manifest(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_checkpoint_capture_action
  ON checkpoint_capture_manifest(action_id);
"""

# Workstream F / Slice F3 (ZT-5) — scoped standing approvals engine. One grant
# model shared by Workstreams A/C/E: `(principal, action shape, scope pattern,
# risk ceiling, expires_at)`. A grant is created from a critical, human-decided
# action (F6 criterion (d)); it lets a *later*, identical-shape, sub-critical
# AI-proposed action run without a fresh prompt — the actual "frictionless"
# mechanism. Grants are user-owned, scope-bound, expiry-bound (default 7 days),
# revocable, always listed in Security Settings, and can only ever *narrow* from
# the human decision that created them. `risk_ceiling` is strictly below critical
# by construction, so no grant can ever pre-authorize a critical action. Every
# use is logged with the grant id. Only metadata lives here — never a secret,
# token, or payload.
STANDING_GRANTS_MIGRATION_ID = "RAIKER-1301-standing-grants"

STANDING_GRANTS_SQL = """
CREATE TABLE IF NOT EXISTS standing_grants (
  grant_id TEXT PRIMARY KEY,
  principal_id TEXT NOT NULL,
  granted_by TEXT NOT NULL,
  action_type TEXT NOT NULL,
  tool_name TEXT NOT NULL DEFAULT '',
  scope_pattern TEXT NOT NULL DEFAULT '*',
  risk_ceiling TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  revoked INTEGER NOT NULL DEFAULT 0,
  revoked_at TEXT,
  revoked_by TEXT,
  use_count INTEGER NOT NULL DEFAULT 0,
  last_used_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_standing_grants_principal
  ON standing_grants(principal_id, revoked, expires_at);
CREATE INDEX IF NOT EXISTS idx_standing_grants_owner
  ON standing_grants(granted_by, revoked, created_at DESC);
"""

# Critical approval lifecycle (Workstream F / F7, ZT-7): a critical action is
# parked as an approval whose resting state is deny. The `critical` flag marks
# such rows so the metadata-only inbox/relay never treat them as ordinary
# approvals — a critical approval is resolvable *only* by the human-decision
# lifecycle in RuntimeAuthority, never by a decision mode, grant, or subagent.
CRITICAL_APPROVAL_LIFECYCLE_MIGRATION_ID = "RAIKER-1302-critical-approval-lifecycle"

CRITICAL_APPROVAL_LIFECYCLE_SQL = """
ALTER TABLE approvals ADD COLUMN critical INTEGER NOT NULL DEFAULT 0;
"""

# Subagent per-spawn budgets (Workstream C / C1): a subagent's enforced resource
# envelope — step, tool-call, and (estimated) token caps — persists on its
# contract so the bounded run is auditable after the fact. Wall-clock already
# lived in `max_runtime_seconds`; these add the remaining three dimensions.
# Legacy rows default to 0 (unset), never a permissive high cap.
SUBAGENT_BUDGETS_MIGRATION_ID = "RAIKER-1303-subagent-budgets"

SUBAGENT_BUDGETS_SQL = """
ALTER TABLE subagent_contracts ADD COLUMN max_steps INTEGER NOT NULL DEFAULT 0;
ALTER TABLE subagent_contracts ADD COLUMN max_tool_calls INTEGER NOT NULL DEFAULT 0;
ALTER TABLE subagent_contracts ADD COLUMN max_tokens INTEGER NOT NULL DEFAULT 0;
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

# Project context memory is a nearest-ancestor override, not a Boolean default.
# Existing rows retain their explicit legacy choice; new rows can inherit.
PROJECT_MEMORY_INHERITANCE_MIGRATION_ID = "RAIKER-1013-project-memory-inheritance"
PROJECT_MEMORY_INHERITANCE_SQL = """
ALTER TABLE project_contexts ADD COLUMN memory_mode TEXT NOT NULL DEFAULT 'inherit'
  CHECK (memory_mode IN ('inherit', 'enabled', 'disabled'));
UPDATE project_contexts
SET memory_mode = CASE memory_enabled WHEN 1 THEN 'enabled' ELSE 'disabled' END;
"""

PROJECT_SELF_INCLUSIVE_PATH_MIGRATION_ID = "RAIKER-1014-project-self-inclusive-path"

MEMORY_ARCHIVE_MIGRATION_ID = "RAIKER-2003-memory-archive-lifecycle"
MEMORY_ARCHIVE_SQL = """
ALTER TABLE approved_memory ADD COLUMN archived_at TEXT;
CREATE INDEX IF NOT EXISTS idx_approved_memory_active ON approved_memory(scope) WHERE deleted_at IS NULL AND archived_at IS NULL;
"""

EIDETIC_OBSERVATIONS_MIGRATION_ID = "RAIKER-2004-eidetic-observations"
EIDETIC_OBSERVATIONS_SQL = """
CREATE TABLE IF NOT EXISTS eidetic_observations (
  observation_id TEXT PRIMARY KEY, source_event_id TEXT NOT NULL, session_id TEXT NOT NULL,
  summary TEXT NOT NULL, content_sha256 TEXT NOT NULL, retention TEXT NOT NULL,
  artifact_ref TEXT, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_eidetic_observations_session ON eidetic_observations(session_id, created_at);
"""

MEMORY_PURGE_MIGRATION_ID = "RAIKER-2005-memory-purge-preview"
MEMORY_PURGE_SQL = """
CREATE TABLE IF NOT EXISTS memory_purge_records (
  purge_id TEXT PRIMARY KEY, memory_id TEXT NOT NULL, requested_by TEXT NOT NULL,
  confirmed_at TEXT NOT NULL, disposition_json TEXT NOT NULL
);
"""

GIST_MEMORY_MIGRATION_ID = "RAIKER-2006-gist-memory-review"
GIST_MEMORY_SQL = """
CREATE TABLE IF NOT EXISTS gist_memories (
  gist_id TEXT PRIMARY KEY, observation_id TEXT NOT NULL REFERENCES eidetic_observations(observation_id),
  summary TEXT NOT NULL, confidence REAL NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
);
"""

MEMORY_PROJECTIONS_MIGRATION_ID = "RAIKER-2007-memory-projections"
MEMORY_PROJECTIONS_SQL = """
CREATE TABLE IF NOT EXISTS memory_projections (
  memory_id TEXT NOT NULL, projection_type TEXT NOT NULL, projection_id TEXT NOT NULL,
  source_version TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (memory_id, projection_type, projection_id)
);
CREATE INDEX IF NOT EXISTS idx_memory_projections_active ON memory_projections(projection_type, projection_id) WHERE active = 1;
"""

MEMORY_FTS_MIGRATION_ID = "RAIKER-2008-memory-fts"
MEMORY_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS approved_memory_fts USING fts4(
  memory_id UNINDEXED, text, tags
);
INSERT INTO approved_memory_fts(memory_id, text, tags)
SELECT memory_id, text, tags_json FROM approved_memory
WHERE deleted_at IS NULL AND archived_at IS NULL;
"""

MEMORY_SQLCIPHER_FTS_MIGRATION_ID = "RAIKER-2015-sqlcipher-fts4-repair"
MEMORY_SQLCIPHER_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS approved_memory_fts USING fts4(
  memory_id UNINDEXED, text, tags
);
"""

MEMORY_RETRIEVAL_AUTHORITY_MIGRATION_ID = "RAIKER-2009-memory-retrieval-authority"
MEMORY_RETRIEVAL_AUTHORITY_SQL = """
ALTER TABLE approved_memory ADD COLUMN search_enabled INTEGER NOT NULL DEFAULT 1;
ALTER TABLE approved_memory ADD COLUMN expires_at TEXT;
"""

MEMORY_TEMPORAL_EVALUATION_MIGRATION_ID = "RAIKER-2010-memory-temporal-evaluation"
MEMORY_TEMPORAL_EVALUATION_SQL = """
ALTER TABLE approved_memory ADD COLUMN valid_from TEXT;
ALTER TABLE approved_memory ADD COLUMN valid_until TEXT;
ALTER TABLE approved_memory ADD COLUMN supersedes_memory_id TEXT REFERENCES approved_memory(memory_id);
ALTER TABLE approved_memory ADD COLUMN superseded_at TEXT;
ALTER TABLE approved_memory ADD COLUMN remembered_reason TEXT;
UPDATE approved_memory SET valid_from = created_at WHERE valid_from IS NULL;
CREATE INDEX IF NOT EXISTS idx_approved_memory_temporal ON approved_memory(scope, valid_from, valid_until)
  WHERE deleted_at IS NULL AND archived_at IS NULL;
CREATE TABLE IF NOT EXISTS memory_evaluation_runs (
  evaluation_id TEXT PRIMARY KEY, corpus_version TEXT NOT NULL, strategy TEXT NOT NULL,
  case_count INTEGER NOT NULL, precision_at_k REAL NOT NULL, recall_at_k REAL NOT NULL,
  mean_reciprocal_rank REAL NOT NULL, ndcg_at_k REAL NOT NULL, policy_leak_count INTEGER NOT NULL,
  p50_latency_ms REAL NOT NULL, p95_latency_ms REAL NOT NULL, token_count INTEGER NOT NULL,
  compute_cost_usd REAL NOT NULL, storage_bytes INTEGER NOT NULL, created_at TEXT NOT NULL
);
"""

MEMORY_CONTENT_CHECKSUM_MIGRATION_ID = "RAIKER-2016-memory-content-checksum"
MEMORY_CONTENT_CHECKSUM_SQL = """
ALTER TABLE approved_memory ADD COLUMN content_checksum TEXT;
"""

MEMORY_EVALUATION_CONTEXT_MIGRATION_ID = "RAIKER-2017-memory-evaluation-context"
MEMORY_EVALUATION_CONTEXT_SQL = """
ALTER TABLE memory_evaluation_runs ADD COLUMN backend_version TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE memory_evaluation_runs ADD COLUMN scope TEXT NOT NULL DEFAULT 'mixed';
ALTER TABLE memory_evaluation_runs ADD COLUMN workload TEXT NOT NULL DEFAULT 'retrieval_case_set';
ALTER TABLE memory_evaluation_runs ADD COLUMN latency_distribution_json TEXT NOT NULL DEFAULT '{}';
"""

MEMORY_LIFECYCLE_AUDIT_IMMUTABILITY_MIGRATION_ID = "RAIKER-2018-memory-lifecycle-audit-immutability"
MEMORY_LIFECYCLE_AUDIT_IMMUTABILITY_SQL = """
CREATE TRIGGER IF NOT EXISTS prevent_memory_lifecycle_audit_update
BEFORE UPDATE ON memory_lifecycle_audit
BEGIN
  SELECT RAISE(ABORT, 'memory_lifecycle_audit_immutable');
END;
CREATE TRIGGER IF NOT EXISTS prevent_memory_lifecycle_audit_delete
BEFORE DELETE ON memory_lifecycle_audit
BEGIN
  SELECT RAISE(ABORT, 'memory_lifecycle_audit_immutable');
END;
"""

MEMORY_RELATIONSHIP_REVIEW_MIGRATION_ID = "RAIKER-2019-memory-relationship-review"
MEMORY_RELATIONSHIP_REVIEW_SQL = """
CREATE TABLE IF NOT EXISTS memory_relationship_candidates (
  candidate_id TEXT PRIMARY KEY,
  subject_name TEXT NOT NULL, subject_type TEXT NOT NULL, predicate TEXT NOT NULL,
  object_name TEXT NOT NULL, object_type TEXT NOT NULL,
  evidence_memory_id TEXT NOT NULL REFERENCES approved_memory(memory_id),
  confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
  decision TEXT NOT NULL CHECK(decision IN ('needs_user_review', 'approved', 'denied')),
  created_at TEXT NOT NULL, resolved_at TEXT, resolved_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_memory_relationship_candidates_review
  ON memory_relationship_candidates(decision, created_at);
"""

MEMORY_ENTITY_GRAPH_MIGRATION_ID = "RAIKER-2011-memory-entity-graph"
MEMORY_ENTITY_GRAPH_SQL = """
CREATE TABLE IF NOT EXISTS memory_entities (
  entity_id TEXT PRIMARY KEY, normalized_name TEXT NOT NULL, display_name TEXT NOT NULL,
  entity_type TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(normalized_name, entity_type)
);
CREATE TABLE IF NOT EXISTS memory_entity_relationships (
  relationship_id TEXT PRIMARY KEY, subject_entity_id TEXT NOT NULL REFERENCES memory_entities(entity_id),
  predicate TEXT NOT NULL, object_entity_id TEXT NOT NULL REFERENCES memory_entities(entity_id),
  evidence_memory_id TEXT NOT NULL REFERENCES approved_memory(memory_id), confidence REAL NOT NULL,
  created_at TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
  UNIQUE(subject_entity_id, predicate, object_entity_id, evidence_memory_id)
);
CREATE INDEX IF NOT EXISTS idx_memory_entity_relationships_subject ON memory_entity_relationships(subject_entity_id) WHERE active = 1;
CREATE INDEX IF NOT EXISTS idx_memory_entity_relationships_object ON memory_entity_relationships(object_entity_id) WHERE active = 1;
"""

MEMORY_BACKUP_CATALOG_MIGRATION_ID = "RAIKER-2012-memory-backup-catalog"
MEMORY_BACKUP_CATALOG_SQL = """
ALTER TABLE backup_manifests ADD COLUMN encryption_key_id TEXT;
ALTER TABLE backup_manifests ADD COLUMN retention_until TEXT;
ALTER TABLE backup_manifests ADD COLUMN legal_hold INTEGER NOT NULL DEFAULT 0;
ALTER TABLE backup_manifests ADD COLUMN erasure_requested_at TEXT;
ALTER TABLE backup_manifests ADD COLUMN erased_at TEXT;
ALTER TABLE backup_manifests ADD COLUMN restore_verified_at TEXT;
"""

MEMORY_JOBS_MIGRATION_ID = "RAIKER-2013-memory-jobs"
MEMORY_JOBS_SQL = """
CREATE TABLE IF NOT EXISTS memory_jobs (
  job_id TEXT PRIMARY KEY, job_type TEXT NOT NULL, dedup_key TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'retry', 'dead_letter', 'completed')),
  attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 3,
  lease_until TEXT, last_error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(job_type, dedup_key)
);
CREATE INDEX IF NOT EXISTS idx_memory_jobs_ready ON memory_jobs(status, lease_until, created_at);
"""

MEMORY_AUDIT_RATE_LIMIT_MIGRATION_ID = "RAIKER-2014-memory-audit-rate-limit"
MEMORY_AUDIT_RATE_LIMIT_SQL = """
CREATE TABLE IF NOT EXISTS memory_lifecycle_audit (
  audit_id TEXT PRIMARY KEY, memory_id TEXT NOT NULL, action TEXT NOT NULL,
  actor_id TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_lifecycle_audit_memory ON memory_lifecycle_audit(memory_id, created_at);
CREATE TABLE IF NOT EXISTS memory_job_rate_windows (
  job_type TEXT NOT NULL, window_started_at TEXT NOT NULL, count INTEGER NOT NULL,
  PRIMARY KEY(job_type, window_started_at)
);
"""

# Owner isolation for durable prompt inputs.  The columns are additive so an
# existing encrypted workspace can be upgraded in place; SQLiteStore assigns
# old unattributed rows only to the original account during this migration.
OWNED_CONTEXT_DATA_SQL = """
ALTER TABLE approved_memory ADD COLUMN owner_principal_id TEXT;
ALTER TABLE vector_records ADD COLUMN owner_principal_id TEXT;
ALTER TABLE attachments ADD COLUMN owner_principal_id TEXT;
CREATE INDEX IF NOT EXISTS idx_approved_memory_owner ON approved_memory(owner_principal_id, created_at);
CREATE INDEX IF NOT EXISTS idx_vector_records_owner ON vector_records(owner_principal_id, created_at);
CREATE INDEX IF NOT EXISTS idx_attachments_owner ON attachments(owner_principal_id, created_at);
"""

OWNED_MEMORY_METADATA_SQL = """
ALTER TABLE memory_candidates ADD COLUMN owner_principal_id TEXT;
CREATE INDEX IF NOT EXISTS idx_memory_candidates_owner ON memory_candidates(owner_principal_id, created_at);
"""

# Account-scoped control plane. Legacy tables remain readable for the terminal
# client, but authenticated instance users read/write only these keyed rows.
PRINCIPAL_CONTROL_SCOPE_MIGRATION_ID = "RAIKER-2022-principal-control-scope"
PRINCIPAL_CONTROL_SCOPE_SQL = """
CREATE TABLE IF NOT EXISTS principal_model_control (
  principal_id TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL,
  model TEXT,
  reasoning_enabled INTEGER NOT NULL DEFAULT 0,
  reasoning_effort TEXT,
  reasoning_mode TEXT,
  reasoning_budget_tokens INTEGER,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS principal_model_fallback_sequence (
  principal_id TEXT PRIMARY KEY,
  profile_ids_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS principal_model_advisor (
  principal_id TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS principal_runtime_mode_state (
  principal_id TEXT PRIMARY KEY,
  mode_name TEXT NOT NULL,
  status TEXT NOT NULL,
  activated_by TEXT,
  activated_at TEXT,
  reason TEXT,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS principal_capability_gate_state (
  principal_id TEXT NOT NULL,
  capability TEXT NOT NULL,
  state TEXT NOT NULL,
  requested_by TEXT,
  requested_at TEXT,
  activated_by TEXT,
  activated_at TEXT,
  reason TEXT,
  readiness_snapshot_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (principal_id, capability)
);
CREATE TABLE IF NOT EXISTS principal_capability_decision_mode (
  principal_id TEXT NOT NULL,
  capability TEXT NOT NULL,
  decision_mode TEXT NOT NULL,
  set_by TEXT,
  set_at TEXT,
  reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (principal_id, capability)
);
CREATE TABLE IF NOT EXISTS instance_account_guard (
  singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
  principal_id TEXT NOT NULL
);
"""

BRAIN_SOURCES_MIGRATION_ID = "RAIKER-2023-owner-brain-sources"
BRAIN_SOURCES_SQL = """
CREATE TABLE IF NOT EXISTS brain_sources (
  owner_principal_id TEXT NOT NULL,
  path TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (owner_principal_id, path)
);
CREATE INDEX IF NOT EXISTS idx_brain_sources_owner ON brain_sources(owner_principal_id, created_at);
"""

BRAIN_SOURCE_GRANTS_MIGRATION_ID = "RAIKER-2079-brain-source-grants"
BRAIN_SOURCE_GRANTS_SQL = """
CREATE TABLE IF NOT EXISTS brain_source_grants (
  owner_principal_id TEXT NOT NULL,
  root_id TEXT NOT NULL,
  path TEXT NOT NULL,
  label TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (owner_principal_id, root_id)
);
CREATE INDEX IF NOT EXISTS idx_brain_source_grants_owner
  ON brain_source_grants(owner_principal_id, created_at);
"""

BRAIN_PREFERENCES_MIGRATION_ID = "RAIKER-2030-brain-preferences"
BRAIN_PREFERENCES_SQL = """
CREATE TABLE IF NOT EXISTS brain_preferences (
  owner_principal_id TEXT PRIMARY KEY,
  settings_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""

EXECUTION_ENVIRONMENT_CONTROL_MIGRATION_ID = "RAIKER-2031-execution-environment-control"
EXECUTION_ENVIRONMENT_CONTROL_SQL = """
ALTER TABLE remote_execution_profiles ADD COLUMN owner_principal_id TEXT;
UPDATE remote_execution_profiles SET owner_principal_id = created_by WHERE owner_principal_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_remote_execution_profiles_owner
  ON remote_execution_profiles(owner_principal_id, updated_at);
CREATE TABLE IF NOT EXISTS execution_environment_selection (
  owner_principal_id TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL,
  selected_at TEXT NOT NULL
);
"""

MODEL_CAPACITY_CONTROL_MIGRATION_ID = "RAIKER-2032-model-capacity-control"
MODEL_CAPACITY_CONTROL_SQL = """
CREATE TABLE IF NOT EXISTS model_capacity_history (
  capacity_id TEXT PRIMARY KEY,
  owner_principal_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  endpoint_identity TEXT NOT NULL,
  context_window_tokens INTEGER,
  action TEXT NOT NULL,
  reason TEXT,
  recorded_by TEXT NOT NULL,
  recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_model_capacity_history_lookup
  ON model_capacity_history(owner_principal_id, provider, model, recorded_at);
CREATE TABLE IF NOT EXISTS model_capacity_refresh_state (
  owner_principal_id TEXT NOT NULL,
  profile_id TEXT NOT NULL,
  last_refresh_at TEXT,
  next_refresh_at TEXT NOT NULL,
  status TEXT NOT NULL,
  reason_code TEXT,
  PRIMARY KEY (owner_principal_id, profile_id)
);
"""

CODE_REPOS_MIGRATION_ID = "RAIKER-2024-code-workspace-repos"
CODE_REPOS_SQL = """
CREATE TABLE IF NOT EXISTS code_repos (
  repo_id TEXT PRIMARY KEY,
  owner_principal_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  label TEXT NOT NULL,
  local_subpath TEXT,
  github_owner TEXT,
  github_repo TEXT,
  branch TEXT,
  selected INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_code_repos_owner ON code_repos(owner_principal_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_code_repos_local
  ON code_repos(owner_principal_id, local_subpath) WHERE local_subpath IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_code_repos_github
  ON code_repos(owner_principal_id, github_owner, github_repo) WHERE github_owner IS NOT NULL;
"""

MODEL_USAGE_LEDGER_MIGRATION_ID = "RAIKER-2025-model-usage-ledger"
MODEL_USAGE_LEDGER_SQL = """
-- Per-turn token accounting. Counts only: this table never holds prompt or
-- response text, and cost is derived at read time from the resolved price so a
-- price correction re-prices history instead of leaving stale money on disk.
CREATE TABLE IF NOT EXISTS model_usage_ledger (
  usage_id TEXT PRIMARY KEY,
  owner_principal_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  cache_read_tokens INTEGER NOT NULL DEFAULT 0,
  cache_write_tokens INTEGER NOT NULL DEFAULT 0,
  recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_model_usage_session
  ON model_usage_ledger(owner_principal_id, session_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_model_usage_provider
  ON model_usage_ledger(owner_principal_id, provider, model);

-- Owner overrides for per-model prices, and the cached provider-reported facts
-- (context window, and price where the provider publishes one). `source` keeps
-- the two apart so the UI can always name where a number came from.
CREATE TABLE IF NOT EXISTS model_facts_cache (
  owner_principal_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  source TEXT NOT NULL,
  context_window_tokens INTEGER,
  max_output_tokens INTEGER,
  input_price_per_mtok TEXT,
  output_price_per_mtok TEXT,
  currency TEXT,
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (owner_principal_id, provider, model, source)
);
"""


# B2 — a turn parked for approval keeps its working state, so resolving the
# approval resumes the *same* turn instead of forcing the owner to re-prompt.
#
# `messages_json` is the model conversation as it stood when the loop suspended,
# including the assistant message carrying the proposed tool call. It is
# transcript-grade content and never leaves the encrypted store: the resume
# endpoints return only an AgentResponse.
#
# `outcome_json` is written when the approval is resolved and is what the model
# sees as the tool result on resume — the real execution result when the action
# ran, or an honest refusal when it did not.
SUSPENDED_TURNS_MIGRATION_ID = "RAIKER-2026-suspended-turns"
SUSPENDED_TURNS_SQL = """
CREATE TABLE IF NOT EXISTS suspended_turns (
  approval_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  turn_id TEXT NOT NULL,
  request_id TEXT NOT NULL,
  principal_id TEXT NOT NULL,
  action_id TEXT NOT NULL,
  tool_name TEXT NOT NULL,
  call_id TEXT NOT NULL,
  prompt_text TEXT NOT NULL,
  messages_json TEXT NOT NULL,
  options_json TEXT NOT NULL,
  client_json TEXT NOT NULL,
  tool_calls_made INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'suspended',
  outcome_json TEXT,
  created_at TEXT NOT NULL,
  resumed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_suspended_turns_session
  ON suspended_turns(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_suspended_turns_status
  ON suspended_turns(principal_id, status);
"""


# ADD-02 — the rest of the model's batch, parked with the turn.
#
# B2 parked one call. A model that proposes three mutations in one batch has two
# more waiting behind the first approval, and dropping them meant the owner
# decided one action while the other two disappeared with an event and no way
# back. These three columns are the queue:
#
# `pending_calls_json` is the ordered remainder — the calls after the parked one,
# each `{call_id, tool_name, arguments}` — replayed one at a time on resume, each
# re-checked against its own decision mode rather than inheriting the first
# decision. `queue_position` and `queue_total` place the parked call inside the
# batch it came from, which is what lets Approvals say "decision 2 of 3" instead
# of presenting an isolated action.
#
# Defaults describe the pre-ADD-02 world exactly: a row written before this
# migration is a single call, at position 1 of 1, with nothing queued behind it.
SUSPENDED_TURN_QUEUE_MIGRATION_ID = "RAIKER-1036-suspended-turn-queue"
SUSPENDED_TURN_QUEUE_SQL = """
ALTER TABLE suspended_turns ADD COLUMN pending_calls_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE suspended_turns ADD COLUMN queue_position INTEGER NOT NULL DEFAULT 1;
ALTER TABLE suspended_turns ADD COLUMN queue_total INTEGER NOT NULL DEFAULT 1;
"""


# BUG-07 — the file inspector's authorization record.
#
# An uploaded attachment is owned by a principal, but "this account may read
# these bytes" is not the same claim as "this conversation may show them". A
# reference is written only when a prompt turn actually carries the attachment,
# after the prompt route has confirmed both the session and the attachment
# belong to the caller. The preview route reads nothing without a matching row,
# so an attachment id guessed or replayed against a different conversation is a
# 404 rather than a disclosure.
SESSION_ATTACHMENT_REFS_MIGRATION_ID = "RAIKER-2027-session-attachment-refs"
SESSION_ATTACHMENT_REFS_SQL = """
CREATE TABLE IF NOT EXISTS session_attachment_refs (
  session_id TEXT NOT NULL,
  attachment_id TEXT NOT NULL,
  owner_principal_id TEXT NOT NULL,
  turn_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (session_id, attachment_id)
);
CREATE INDEX IF NOT EXISTS idx_session_attachment_refs_owner
  ON session_attachment_refs(owner_principal_id, session_id, created_at);
"""

SESSION_ATTACHMENT_SOURCE_MIGRATION_ID = "RAIKER-2028-session-attachment-source"
SESSION_ATTACHMENT_SOURCE_SQL = """
ALTER TABLE session_attachment_refs ADD COLUMN source TEXT NOT NULL DEFAULT 'uploaded';
"""

SESSION_COMMAND_GRANTS_MIGRATION_ID = "RAIKER-2029-session-command-grants"
SESSION_COMMAND_GRANTS_SQL = """
CREATE TABLE IF NOT EXISTS session_command_grants (
  session_id TEXT NOT NULL,
  principal_id TEXT NOT NULL,
  commands_json TEXT NOT NULL,
  timeout_seconds INTEGER NOT NULL,
  expires_at TEXT NOT NULL,
  revoked INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  PRIMARY KEY (session_id, principal_id)
);
"""


# BUG-10 — where a session came from.
#
# Every chat turn and every task run stores a session, and until now they were
# indistinguishable: the server-owned Inbox session a scheduled task runs in
# appeared in the sidebar's RECENT CHATS beside real conversations. Origin is a
# provenance label — it grants nothing, hides nothing, and changes no gate or
# policy. Task-origin sessions stay fully readable in Sessions and reachable
# from Tasks; they are only excluded from the "recent conversations" list, which
# is a list of conversations the owner actually had.
SESSION_ORIGIN_MIGRATION_ID = "RAIKER-1022-session-origin"
SESSION_ORIGIN_SQL = """
ALTER TABLE sessions ADD COLUMN origin TEXT NOT NULL DEFAULT 'chat';
CREATE INDEX IF NOT EXISTS idx_sessions_owner_origin_updated
  ON sessions(user_id, origin, updated_at DESC);
"""


CONFIGURED_MODELS_MIGRATION_ID = "RAIKER-1030-configured-models"
CONFIGURED_MODELS_SQL = """
CREATE TABLE IF NOT EXISTS principal_configured_models (
  principal_id TEXT NOT NULL,
  profile_id TEXT NOT NULL,
  model TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (principal_id, profile_id, model)
);
CREATE INDEX IF NOT EXISTS idx_principal_configured_models_owner
  ON principal_configured_models(principal_id, created_at, profile_id, model);
"""


TASK_MODEL_CHOICES_MIGRATION_ID = "RAIKER-1031-task-model-choices"
TASK_MODEL_CHOICES_SQL = """
ALTER TABLE tasks ADD COLUMN model_profile TEXT;
ALTER TABLE tasks ADD COLUMN model TEXT;
"""


# BUG-21 — the historical price registry.
#
# Prices are facts with a date, not a current value: a bill produced last month
# must stay reproducible after a provider changes its rates. Rows are therefore
# append-only and effective-dated, one per (owner, provider, exact model id,
# source, effective_from). Nothing is ever overwritten, so `history` is the
# table itself rather than a derived audit log.
#
# `content_hash` is what keeps a 6-hourly sync from writing an identical row
# every cycle: a refresh that observes unchanged rates only moves the sync
# state's timestamps, never the registry.
#
# Cache-write and cache-read rates are stored independently of the input rate
# because providers charge them independently — Anthropic writes cache at 1.25x
# input and reads it at 0.1x — and a registry that folds them into "input"
# cannot answer what a cached turn actually cost.
MODEL_PRICE_REGISTRY_MIGRATION_ID = "RAIKER-1032-model-price-registry"
MODEL_PRICE_REGISTRY_SQL = """
CREATE TABLE IF NOT EXISTS model_price_registry (
  owner_principal_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  source TEXT NOT NULL,
  effective_from TEXT NOT NULL,
  input_per_mtok TEXT NOT NULL,
  output_per_mtok TEXT NOT NULL,
  cache_write_per_mtok TEXT,
  cache_read_per_mtok TEXT,
  currency TEXT NOT NULL DEFAULT 'USD',
  as_of TEXT,
  content_hash TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  recorded_by TEXT,
  reason TEXT,
  PRIMARY KEY (owner_principal_id, provider, model, source, effective_from)
);
CREATE INDEX IF NOT EXISTS idx_model_price_registry_owner
  ON model_price_registry(owner_principal_id, provider, model, effective_from DESC);

CREATE TABLE IF NOT EXISTS model_price_sync_state (
  owner_principal_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  interval_hours INTEGER NOT NULL,
  last_attempt_at TEXT,
  last_success_at TEXT,
  next_refresh_at TEXT,
  last_error TEXT,
  last_good_payload TEXT,
  models_recorded INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (owner_principal_id, provider)
);
"""


# BUG-42 — cumulative cloud execution spend.
#
# These events are append-only. A reservation protects the budget before a
# command starts; a reconciliation replaces that estimate with provider actual
# cost, and a release removes an estimate when execution never began. Keeping
# events rather than a mutable counter preserves the evidence behind every
# admission decision and makes interrupted runs remain conservatively charged.
CLOUD_EXECUTION_COST_LEDGER_MIGRATION_ID = "RAIKER-1033-cloud-execution-cost-ledger"
CLOUD_EXECUTION_COST_LEDGER_SQL = """
CREATE TABLE IF NOT EXISTS cloud_execution_cost_ledger (
  event_id TEXT PRIMARY KEY,
  owner_principal_id TEXT NOT NULL,
  profile_id TEXT NOT NULL,
  action_id TEXT NOT NULL,
  event_type TEXT NOT NULL CHECK(event_type IN ('reserved', 'reconciled', 'released', 'provider_snapshot', 'provider_unavailable')),
  amount TEXT NOT NULL,
  provider_reference TEXT,
  reason TEXT,
  recorded_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_cloud_cost_one_reservation
  ON cloud_execution_cost_ledger(owner_principal_id, profile_id, action_id)
  WHERE event_type = 'reserved';
CREATE INDEX IF NOT EXISTS idx_cloud_cost_profile
  ON cloud_execution_cost_ledger(owner_principal_id, profile_id, recorded_at, event_id);
"""


# Schedule/task prompt attachments use the same validated payload as Chat and
# Build. JSON keeps the prompt shape intact until the scheduler creates its
# governed turn; uploaded bytes remain in the attachment store.
TASK_ATTACHMENTS_MIGRATION_ID = "RAIKER-1034-task-attachments"
TASK_ATTACHMENTS_SQL = """
ALTER TABLE tasks ADD COLUMN attachments_json TEXT NOT NULL DEFAULT '[]';
"""


# Installed skills (SKILL.md documents and *.skill bundles the owner added).
#
# A skill is instruction text, never code Raiker runs, so the row holds the
# validated document, the original archive when one was uploaded, and the four
# facts the Skills tab reports: where it came from, what it hashes to, whether
# it is active, and when it last changed. Unique per (owner, name) so importing
# the same skill twice refreshes one row rather than accumulating duplicates.
SKILLS_MIGRATION_ID = "RAIKER-1035-installed-skills"
SKILLS_SQL = """
CREATE TABLE IF NOT EXISTS skills (
  skill_id TEXT PRIMARY KEY,
  principal_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  version TEXT,
  source TEXT NOT NULL,
  source_ref TEXT,
  checksum TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  skill_md TEXT NOT NULL,
  bundle BLOB,
  files_json TEXT NOT NULL DEFAULT '[]',
  byte_size INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_skills_owner_name ON skills(principal_id, name);
CREATE INDEX IF NOT EXISTS idx_skills_owner ON skills(principal_id, created_at DESC);

-- Which shipped skills this owner has already been offered. Without it, seeding
-- would reinstall a built-in the owner deliberately deleted, every time the
-- Skills tab was opened.
CREATE TABLE IF NOT EXISTS skill_seeds (
  principal_id TEXT NOT NULL,
  name TEXT NOT NULL,
  seeded_at TEXT NOT NULL,
  PRIMARY KEY (principal_id, name)
);
"""


# B6 — the agent's own plan for the work in front of it.
#
# `raiker/tasks` already stores tasks the owner scheduled; this is the sibling
# that exists *inside* a conversation: an ordered list of short steps, each with
# a status, that the model writes with `update_plan` and the workspace renders
# as a live checklist. One row per session, replaced whole on every update —
# the plan is the current intent, not a history, and the durable event log
# already carries how it changed.
#
# It is scoped to a principal as well as a session so a plan can never be read
# across accounts, and it survives a turn: a long change keeps its spine after
# an approval parks the turn, after a failure, and after a reload.
AGENT_PLANS_MIGRATION_ID = "RAIKER-1036-agent-plans"
AGENT_PLANS_SQL = """
CREATE TABLE IF NOT EXISTS agent_plans (
  session_id TEXT NOT NULL,
  principal_id TEXT NOT NULL,
  turn_id TEXT NOT NULL,
  steps_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (session_id, principal_id)
);
CREATE INDEX IF NOT EXISTS idx_agent_plans_owner
  ON agent_plans(principal_id, updated_at DESC);
"""


# B17 / C13 — the owner's two controls over a turn that is already running.
#
# `POST /api/interrupts` has always been able to cancel a *task*; a live Chat or
# Build turn also needs somewhere to leave an instruction the running loop will
# find at its next safe boundary. That is what this table is: one row per
# (session, principal), holding a stop request and/or an ordered list of steer
# messages the owner typed while the turn was streaming.
#
# It is durable rather than in-process on purpose. The request that asks for the
# stop and the loop that honours it need not share a worker, and an owner who
# hits Stop must not depend on which process answered them.
#
# It grants nothing: a stop only ends a turn early, and a steer is the owner's
# own words entering their own conversation as a user message. Everything the
# model does after reading one is governed exactly as it was before.
TURN_CONTROLS_MIGRATION_ID = "RAIKER-1037-turn-controls"
TURN_CONTROLS_SQL = """
CREATE TABLE IF NOT EXISTS turn_controls (
  session_id TEXT NOT NULL,
  principal_id TEXT NOT NULL,
  stop_requested INTEGER NOT NULL DEFAULT 0,
  stop_reason TEXT,
  steer_json TEXT NOT NULL DEFAULT '[]',
  updated_at TEXT NOT NULL,
  PRIMARY KEY (session_id, principal_id)
);
"""


# C6 / C4 — where a turn's answer came from.
#
# A turn that reads an email, a calendar entry, a web page or an attached
# document produced an answer with nothing in the transcript naming the material
# behind it. The owner was asked to trust a claim they could not check, which is
# exactly the provenance failure `source_provenance.py` was written to end for
# memory records.
#
# One row per source a turn actually used, in the order the turn used it. The
# ids (`s1`, `s2`, …) are what the model is handed as `cite_as` markers and what
# the transcript renders as clickable chips, so this table is the single place
# the citation vocabulary is defined — a chip that names `s2` and a marker the
# model wrote as `[s2]` resolve to the same row or to nothing at all.
#
# `passage` is the bounded text the source contributed. It is stored because
# opening a source *at the passage that was used* (C4) needs the text that was
# used, and re-running the tool later would answer a different question. It is
# never written to the durable event log: the streamed record is counts and
# tool names, and the passage is served only over the session-authorized read
# route, to the account that owns the conversation.
TURN_SOURCES_MIGRATION_ID = "RAIKER-1038-turn-sources"
TURN_SOURCES_SQL = """
CREATE TABLE IF NOT EXISTS turn_sources (
  session_id TEXT NOT NULL,
  turn_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  principal_id TEXT NOT NULL,
  ordinal INTEGER NOT NULL,
  kind TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  locator TEXT NOT NULL DEFAULT '',
  tool_name TEXT NOT NULL DEFAULT '',
  detail TEXT NOT NULL DEFAULT '',
  attachment_id TEXT NOT NULL DEFAULT '',
  passage TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  PRIMARY KEY (session_id, turn_id, source_id)
);
CREATE INDEX IF NOT EXISTS idx_turn_sources_turn
  ON turn_sources(session_id, turn_id, ordinal);
"""


# ADD-03 — a cryptographic identity for each agent turn.
#
# The issuer is one active Ed25519 key per workspace database. Its private seed
# is encrypted with Raiker's internal application key; neither it nor a bearer
# attestation is stored on the turn row. The turn row keeps only immutable,
# redacted attribution metadata so approvals and audit evidence can outlive the
# short-lived token that originally proposed the action.
MACHINE_IDENTITIES_MIGRATION_ID = "RAIKER-1039-machine-identities"
MACHINE_IDENTITIES_SQL = """
CREATE TABLE IF NOT EXISTS machine_identity_issuers (
  workspace_id TEXT PRIMARY KEY,
  key_id TEXT NOT NULL UNIQUE,
  public_key BLOB NOT NULL,
  private_key_encrypted BLOB NOT NULL,
  created_at TEXT NOT NULL,
  rotated_at TEXT,
  is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS turn_machine_identities (
  principal_id TEXT PRIMARY KEY,
  owner_principal_id TEXT NOT NULL,
  workspace_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  turn_id TEXT NOT NULL,
  subject TEXT NOT NULL,
  key_id TEXT NOT NULL,
  token_id TEXT NOT NULL,
  issued_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  parent_principal_id TEXT,
  is_active INTEGER NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_turn_machine_identity_context
  ON turn_machine_identities(workspace_id, session_id, turn_id, principal_id);
CREATE INDEX IF NOT EXISTS idx_turn_machine_identity_turn
  ON turn_machine_identities(owner_principal_id, session_id, turn_id);
"""


# ADD-03 -- durable actor/owner attribution for every governed action. The
# signed bearer token is deliberately not stored; these immutable claims are
# sufficient for approvals, audit views, and incident review after expiry.
MACHINE_ACTION_ATTRIBUTION_MIGRATION_ID = "RAIKER-1040-machine-action-attribution"
MACHINE_ACTION_ATTRIBUTION_SQL = """
ALTER TABLE tool_actions ADD COLUMN proposed_by TEXT NOT NULL DEFAULT 'agent_runtime';
ALTER TABLE tool_actions ADD COLUMN owner_principal_id TEXT;
ALTER TABLE tool_actions ADD COLUMN machine_subject TEXT;
ALTER TABLE tool_actions ADD COLUMN machine_token_id TEXT;
CREATE INDEX IF NOT EXISTS idx_tool_actions_actor_time
  ON tool_actions(proposed_by, proposed_at);
CREATE INDEX IF NOT EXISTS idx_tool_actions_owner_time
  ON tool_actions(owner_principal_id, proposed_at);
"""


# ADD-03 -- snapshot the public identity claims on the action itself. A resumed
# turn rotates its bearer token, but an approval must continue to describe the
# exact machine credential that proposed it.
MACHINE_ACTION_IDENTITY_SNAPSHOT_MIGRATION_ID = "RAIKER-1041-machine-action-identity-snapshot"
MACHINE_ACTION_IDENTITY_SNAPSHOT_SQL = """
ALTER TABLE tool_actions ADD COLUMN machine_key_id TEXT;
ALTER TABLE tool_actions ADD COLUMN machine_issued_at TEXT;
ALTER TABLE tool_actions ADD COLUMN machine_expires_at TEXT;
"""


# BUG-69 -- short-lived, exact model reachability observations. Configuration
# and selection are durable intent; these rows are only evidence that the exact
# owner/profile/model/endpoint tuple was reachable recently.
MODEL_READINESS_MIGRATION_ID = "RAIKER-1042-model-readiness"
MODEL_READINESS_SQL = """
CREATE TABLE IF NOT EXISTS model_readiness (
  owner_principal_id TEXT NOT NULL,
  profile_id TEXT NOT NULL,
  model TEXT NOT NULL,
  endpoint_fingerprint TEXT NOT NULL,
  state TEXT NOT NULL,
  checked_at TEXT,
  expires_at TEXT,
  summary TEXT NOT NULL DEFAULT '',
  reason_code TEXT NOT NULL DEFAULT '',
  remediation TEXT NOT NULL DEFAULT '',
  evidence_json TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY (owner_principal_id, profile_id, model, endpoint_fingerprint)
);
CREATE INDEX IF NOT EXISTS idx_model_readiness_owner_profile
  ON model_readiness(owner_principal_id, profile_id);
CREATE INDEX IF NOT EXISTS idx_model_readiness_expiry
  ON model_readiness(expires_at);
"""


# BUG-69 -- resumable first-owner model setup. Existing accounts are backfilled
# complete when the migration lands; an account registered after migration has
# no row and therefore starts in the required state.
MODEL_SETUP_STATE_MIGRATION_ID = "RAIKER-1043-model-setup-state"
MODEL_SETUP_STATE_SQL = """
CREATE TABLE IF NOT EXISTS model_setup_state (
  owner_principal_id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  step TEXT NOT NULL,
  path TEXT,
  selected_profile_id TEXT,
  selected_model TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
INSERT OR IGNORE INTO model_setup_state
  (owner_principal_id, status, step, path, selected_profile_id, selected_model, created_at, updated_at)
SELECT principal_id, 'complete', 'ready', NULL, NULL, NULL, created_at, updated_at
FROM account_credentials;
"""

MODEL_USAGE_ROLLING_WINDOW_MIGRATION_ID = "RAIKER-2041-model-usage-rolling-window"
MODEL_USAGE_ROLLING_WINDOW_SQL = """
-- Attribute every new request to the configured profile that served it and
-- distinguish owner turns from supporting model work such as compaction.
-- Existing rows remain readable as ordinary turns with an unknown profile.
ALTER TABLE model_usage_ledger ADD COLUMN profile_id TEXT;
ALTER TABLE model_usage_ledger ADD COLUMN request_kind TEXT NOT NULL DEFAULT 'turn';
CREATE INDEX IF NOT EXISTS idx_model_usage_profile_window
  ON model_usage_ledger(owner_principal_id, profile_id, recorded_at);

-- An owner budget is advisory Raiker control, not a claim about a provider's
-- subscription quota. Removing a budget removes the row.
CREATE TABLE IF NOT EXISTS model_weekly_budgets (
  owner_principal_id TEXT NOT NULL,
  profile_id TEXT NOT NULL,
  token_budget INTEGER NOT NULL CHECK (token_budget > 0),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (owner_principal_id, profile_id)
);
"""

PROVIDER_USAGE_SNAPSHOTS_MIGRATION_ID = "RAIKER-2042-provider-usage-snapshots"
PROVIDER_USAGE_SNAPSHOTS_SQL = """
-- Five-minute metadata-only cache for provider-native usage. `metrics_json`
-- contains only Raiker's bounded normalized metric contract, never a raw
-- provider response, credential, key label, or account identifier.
CREATE TABLE IF NOT EXISTS provider_usage_snapshots (
  owner_principal_id TEXT NOT NULL,
  profile_id TEXT NOT NULL,
  status TEXT NOT NULL,
  metrics_json TEXT NOT NULL,
  reason_code TEXT,
  checked_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  PRIMARY KEY (owner_principal_id, profile_id)
);
CREATE INDEX IF NOT EXISTS idx_provider_usage_snapshot_expiry
  ON provider_usage_snapshots(owner_principal_id, expires_at);
"""

CONVERSATION_COMPACTIONS_MIGRATION_ID = "RAIKER-2043-conversation-compactions"
CONVERSATION_COMPACTIONS_SQL = """
-- Durable model-context summaries. Transcript turns remain untouched; the
-- exact through-turn boundary determines which originals a future request may
-- replace in provider context.
CREATE TABLE IF NOT EXISTS conversation_compactions (
  compaction_id TEXT PRIMARY KEY,
  owner_principal_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  through_turn_id TEXT,
  summary_text TEXT,
  protected_context TEXT NOT NULL DEFAULT '',
  source_turn_count INTEGER NOT NULL DEFAULT 0,
  estimated_input_tokens_before INTEGER NOT NULL DEFAULT 0,
  estimated_summary_tokens INTEGER NOT NULL DEFAULT 0,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('completed', 'failed')),
  reason_code TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conversation_compactions_session
  ON conversation_compactions(owner_principal_id, session_id, created_at);
"""


SETUP_STATE_MIGRATION_ID = "RAIKER-1049-full-setup-state"
SETUP_STATE_SQL = """
CREATE TABLE IF NOT EXISTS setup_state (
  owner_principal_id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  stage TEXT NOT NULL,
  selected_profile_id TEXT,
  selected_model TEXT,
  model_deferred INTEGER NOT NULL DEFAULT 0,
  privacy_mode TEXT,
  privacy_acknowledged_at TEXT,
  backup_mode TEXT NOT NULL DEFAULT 'later',
  backup_target TEXT,
  backup_verified_at TEXT,
  background_service_enabled INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
INSERT OR IGNORE INTO setup_state
  (owner_principal_id, status, stage, selected_profile_id, selected_model,
   model_deferred, backup_mode, background_service_enabled, created_at, updated_at)
SELECT owner_principal_id,
       CASE WHEN status = 'complete' THEN 'complete' ELSE 'required' END,
       CASE WHEN status = 'complete' THEN 'finish' ELSE 'model' END,
       selected_profile_id, selected_model,
       CASE WHEN status = 'skipped' THEN 1 ELSE 0 END,
       'later', 0, created_at, updated_at
FROM model_setup_state;
"""


MODEL_OPERATIONS_MIGRATION_ID = "RAIKER-1044-model-operations"
MODEL_OPERATIONS_SQL = """
CREATE TABLE IF NOT EXISTS model_operations (
  operation_id TEXT PRIMARY KEY,
  owner_principal_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  target TEXT NOT NULL,
  state TEXT NOT NULL,
  phase TEXT NOT NULL,
  progress_bytes INTEGER NOT NULL DEFAULT 0,
  total_bytes INTEGER,
  progress_percent INTEGER,
  source_url TEXT,
  destination TEXT,
  error_code TEXT,
  error_detail TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_model_operations_owner_time
  ON model_operations(owner_principal_id, created_at DESC);
"""


MODEL_LIBRARY_MIGRATION_ID = "RAIKER-1045-model-library"
MODEL_LIBRARY_SQL = """
CREATE TABLE IF NOT EXISTS model_library_roots (
  owner_principal_id TEXT NOT NULL,
  path TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (owner_principal_id, path)
);
CREATE TABLE IF NOT EXISTS local_models (
  owner_principal_id TEXT NOT NULL,
  root_path TEXT NOT NULL,
  model_id TEXT NOT NULL,
  name TEXT NOT NULL,
  architecture TEXT NOT NULL,
  quantization TEXT,
  primary_path TEXT NOT NULL,
  shard_count INTEGER NOT NULL,
  expected_shards INTEGER NOT NULL,
  complete INTEGER NOT NULL,
  size_bytes INTEGER NOT NULL,
  indexed_at TEXT NOT NULL,
  PRIMARY KEY (owner_principal_id, model_id)
);
CREATE INDEX IF NOT EXISTS idx_local_models_owner_name
  ON local_models(owner_principal_id, name);
"""


# A default model per work surface.
#
# Raiker already had a global default and a model captured on an individual
# task. Neither expresses "Chat on the small local model, Build on the big one":
# the per-turn picker was view state that reset on every reload, so both
# surfaces silently fell back to the same global choice.
#
# One row per owner and surface, replaced rather than accumulated — a surface
# has exactly one default or none. The row is a *preference*: it decides where
# the picker starts, and the turn it produces still carries an explicit profile
# and model that the readiness gate judges on its own terms. Nothing here can
# put work on a model that was never proven.
SURFACE_MODEL_DEFAULT_MIGRATION_ID = "RAIKER-1046-surface-model-defaults"
SURFACE_MODEL_DEFAULT_SQL = """
CREATE TABLE IF NOT EXISTS principal_surface_models (
  principal_id TEXT NOT NULL,
  surface TEXT NOT NULL,
  profile_id TEXT NOT NULL,
  model TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (principal_id, surface)
);
"""


# B9 — the repository code map.
#
# Every turn used to start cold: no symbol index, no map of the tree, so on a
# large repository the agent grepped blind. These four tables are the projection
# that ends that, and each column exists for a stated reason.
#
# `code_map_indexes` is one row per indexed repository *path* rather than per
# `code_repos` row, because the repository a turn works in is the selected folder
# **or the workspace root when nothing is selected** — the same resolution the
# git tools use. Keying on the path means the unselected case has a home instead
# of a special case. `status`, `reason_code` and `limits_hit` are what stop a
# partial scan reading as a complete one.
#
# `sha256` on a file row is what makes a refresh incremental: after an approved
# write, only the paths whose content actually changed are re-parsed.
#
# Nothing here is authoritative. Every row is derived from a file the agent may
# already read, and reading one at the coordinates recorded here still goes
# through `read_file`, workspace containment, and the policy engine. The map
# grants no access; it only says where to look.
CODE_MAP_MIGRATION_ID = "RAIKER-2040-repository-code-map"
CODE_MAP_SQL = """
CREATE TABLE IF NOT EXISTS code_map_indexes (
  owner_principal_id TEXT NOT NULL,
  repo_path TEXT NOT NULL,
  repo_id TEXT NOT NULL DEFAULT '',
  label TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,
  reason_code TEXT NOT NULL DEFAULT '',
  file_count INTEGER NOT NULL DEFAULT 0,
  symbol_count INTEGER NOT NULL DEFAULT 0,
  edge_count INTEGER NOT NULL DEFAULT 0,
  skipped TEXT NOT NULL DEFAULT '{}',
  limits_hit TEXT NOT NULL DEFAULT '',
  languages TEXT NOT NULL DEFAULT '{}',
  schema_version TEXT NOT NULL DEFAULT '1.0',
  built_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (owner_principal_id, repo_path)
);
CREATE TABLE IF NOT EXISTS code_map_files (
  owner_principal_id TEXT NOT NULL,
  repo_path TEXT NOT NULL,
  path TEXT NOT NULL,
  language TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  size_bytes INTEGER NOT NULL DEFAULT 0,
  line_count INTEGER NOT NULL DEFAULT 0,
  symbol_count INTEGER NOT NULL DEFAULT 0,
  title TEXT NOT NULL DEFAULT '',
  extractor TEXT NOT NULL DEFAULT 'none',
  indexed_at TEXT NOT NULL,
  PRIMARY KEY (owner_principal_id, repo_path, path)
);
CREATE INDEX IF NOT EXISTS idx_code_map_files_repo
  ON code_map_files(owner_principal_id, repo_path, symbol_count DESC);
CREATE TABLE IF NOT EXISTS code_map_symbols (
  owner_principal_id TEXT NOT NULL,
  repo_path TEXT NOT NULL,
  path TEXT NOT NULL,
  kind TEXT NOT NULL,
  name TEXT NOT NULL,
  name_lower TEXT NOT NULL,
  qualified_name TEXT NOT NULL,
  line_start INTEGER NOT NULL DEFAULT 1,
  line_end INTEGER NOT NULL DEFAULT 1,
  parent TEXT NOT NULL DEFAULT '',
  signature TEXT NOT NULL DEFAULT '',
  doc TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_code_map_symbols_name
  ON code_map_symbols(owner_principal_id, repo_path, name_lower);
CREATE INDEX IF NOT EXISTS idx_code_map_symbols_path
  ON code_map_symbols(owner_principal_id, repo_path, path);
CREATE TABLE IF NOT EXISTS code_map_edges (
  owner_principal_id TEXT NOT NULL,
  repo_path TEXT NOT NULL,
  from_path TEXT NOT NULL,
  relationship TEXT NOT NULL,
  target TEXT NOT NULL,
  line INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_code_map_edges_from
  ON code_map_edges(owner_principal_id, repo_path, from_path);
CREATE INDEX IF NOT EXISTS idx_code_map_edges_target
  ON code_map_edges(owner_principal_id, repo_path, target);
"""

# Capability-agnostic behaviour monitoring and containment (BUG-76, BUG-77).
#
# Until this migration, anomaly detection, findings and containment existed for
# exactly one capability family — monitored MCP connections. Every other family
# (connectors, plugins, subagents, local execution, providers, tools) had a
# budget and nothing else: a component that failed every call spent its whole
# budget one doomed call at a time, and a component that started misbehaving
# raised no finding and could not be contained short of disabling the whole
# capability.
#
# `capability_activity_log` is the generic sibling of `mcp_session_log`: one
# redacted row per governed capability invocation, keyed by
# `(principal_id, capability, subject_id)`. The same hard invariant holds — only
# counts, hostnames (netloc), classification *labels* and outcome codes are ever
# stored, never a payload, argument value, token, or full URL. Rolling rows form
# each subject's baseline.
#
# `capability_containment` carries the owner-authoritative lifecycle state for a
# subject in the same vocabulary the MCP monitor already uses: `active`,
# `paused` (the revocable circuit breaker — automatic on a high-severity anomaly
# or on a consecutive-failure threshold, and the owner's one-call stop) and
# `killed` (the instant kill switch). Both are revocable: containment is never a
# ban, only what keeps a frictionless default safe. `failure_streak` and
# `probe_after` carry the breaker's own state so a half-open probe is a property
# of the row rather than of a process that may have restarted.
CAPABILITY_MONITORING_MIGRATION_ID = "RAIKER-1047-capability-monitoring"

CAPABILITY_MONITORING_SQL = """
CREATE TABLE IF NOT EXISTS capability_activity_log (
  activity_id TEXT PRIMARY KEY,
  principal_id TEXT NOT NULL,
  capability TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  operation TEXT NOT NULL DEFAULT '',
  hosts_json TEXT,
  tools_json TEXT,
  calls INTEGER NOT NULL DEFAULT 0,
  bytes_in INTEGER NOT NULL DEFAULT 0,
  bytes_out INTEGER NOT NULL DEFAULT 0,
  error_count INTEGER NOT NULL DEFAULT 0,
  outcome TEXT NOT NULL DEFAULT 'ok',
  reason_code TEXT NOT NULL DEFAULT '',
  arg_sensitivity TEXT,
  result_sensitivity TEXT,
  observed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_capability_activity_subject
  ON capability_activity_log(principal_id, capability, subject_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS capability_containment (
  principal_id TEXT NOT NULL,
  capability TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  label TEXT NOT NULL DEFAULT '',
  state TEXT NOT NULL DEFAULT 'active',
  reason TEXT,
  source TEXT NOT NULL DEFAULT 'owner',
  finding_id TEXT,
  failure_streak INTEGER NOT NULL DEFAULT 0,
  last_failure_code TEXT NOT NULL DEFAULT '',
  contained_at TEXT,
  probe_after TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (principal_id, capability, subject_id)
);
CREATE INDEX IF NOT EXISTS idx_capability_containment_state
  ON capability_containment(principal_id, state, updated_at DESC);
"""

# Resumable, cancellable, cleanable model operations (BUG-75).
#
# Ollama pull, Hugging Face download, conversion and managed GGUF deployment all
# start real background workers, but three of their controls were record-only:
# **Retry** reset the durable row to `queued` without reconstructing and
# dispatching the original worker, **Cancel** recorded `cancel_requested` that
# not every worker polled, and **Clear record** removed the row while leaving an
# incomplete destination on disk.
#
# `payload_json` is the secret-safe typed payload a retry needs to dispatch the
# same job again: the repository, revision, model name, quantization and the
# resolved destination — never a token, a credential, or a header. It is stored
# beside the row rather than in it so the API projection can keep showing the
# *redacted* destination while cleanup can still name the exact approved path
# the owner confirms.
MODEL_OPERATION_PAYLOAD_MIGRATION_ID = "RAIKER-1048-model-operation-payload"

MODEL_OPERATION_PAYLOAD_SQL = """
ALTER TABLE model_operations ADD COLUMN payload_json TEXT NOT NULL DEFAULT '{}';
"""


# ── Conversation recall (RAIKER-2020) ────────────────────────────────────────
#
# Chat search used to be `LIKE '%term%'` over `sessions.title`, `turns.prompt_text`
# and `turns.summary`: an unindexed scan of every turn the owner had ever taken,
# returning whole conversations with no indication of *which* exchange matched.
# It answered "which chats mention this" slowly and could not answer "what
# exactly did we decide, and when", which is the question a conversation from
# years ago is actually asked.
#
# `conversation_fts` is a rebuildable projection of the `turns` table — never a
# second source of truth. One row per side of an exchange (`prompt` for what the
# owner typed, `answer` for what the model replied) so a hit can be attributed
# and quoted. `turn_id` carries the row back to the governed record, which is
# where scope, ownership and redaction are still decided; the index itself
# authorises nothing.
CONVERSATION_FTS_MIGRATION_ID = "RAIKER-2020-conversation-fts"

CONVERSATION_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS conversation_fts USING fts4(
  turn_id UNINDEXED, session_id UNINDEXED, role UNINDEXED, text
);
"""


# ── Owner-managed web egress blocklist (RAIKER-2021) ─────────────────────────
#
# Web egress used to be an allowlist that only existed in the process
# environment, on the stated grounds that the last boundary before bytes leave
# the machine should not be editable from a browser session. That reasoning held
# while the list was the *only* thing standing between a model-chosen URL and the
# network. It no longer is: the address guard refuses every private, loopback and
# link-local destination and is not owner-editable at all, so what the owner edits
# here is their own policy about public destinations — which is exactly the kind
# of thing a person should be able to change without editing a service file.
#
# `RAIKER_WEB_EGRESS_BLACKLIST` still applies and is unioned with these rows, so
# a deployment that wants rules the app cannot remove still has them.
WEB_BLOCKLIST_MIGRATION_ID = "RAIKER-2021-web-egress-blocklist"

WEB_BLOCKLIST_SQL = """
CREATE TABLE IF NOT EXISTS web_egress_blocklist (
  rule_id TEXT PRIMARY KEY,
  owner_principal_id TEXT,
  rule TEXT NOT NULL,
  kind TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_web_blocklist_rule
  ON web_egress_blocklist(owner_principal_id, rule);
"""


# ── Session-scoped git credential grants (RAIKER-2022) ───────────────────────
#
# A push needs a credential, and the credential is the owner's. Holding it in the
# process environment for the life of the host means every command the runtime
# ever launches inherits it, and a grant that never expires is one the owner
# cannot meaningfully withdraw. A grant row is the opposite: it names the scope
# (one command, or this session), it carries an expiry, and revoking it is a
# delete rather than a restart.
GIT_CREDENTIAL_GRANT_MIGRATION_ID = "RAIKER-2022-git-credential-grants"

GIT_CREDENTIAL_GRANT_SQL = """
CREATE TABLE IF NOT EXISTS git_credential_grants (
  grant_id TEXT PRIMARY KEY,
  owner_principal_id TEXT NOT NULL,
  session_id TEXT,
  scope TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  reason TEXT NOT NULL DEFAULT '',
  granted_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  consumed_at TEXT,
  revoked_at TEXT,
  uses INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_git_grants_active
  ON git_credential_grants(owner_principal_id, status, expires_at);
"""


# ── Governed command runs (RAIKER-2030) ────────────────────────────────────
#
# Commands are durable governed records, not ephemeral subprocess return
# values. Executable material stays encrypted; query surfaces receive only the
# owner-safe display and its digest. Output is an ordered, owner-scoped stream,
# and a terminal state cannot be published without its immutable receipt.
COMMAND_RUNS_MIGRATION_ID = "RAIKER-2030-command-runs"

COMMAND_RUNS_SQL = """
CREATE TABLE IF NOT EXISTS command_runs (
  run_id TEXT PRIMARY KEY,
  owner_principal_id TEXT NOT NULL,
  acting_principal_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  turn_id TEXT NOT NULL,
  action_id TEXT NOT NULL,
  state TEXT NOT NULL,
  profile_id TEXT NOT NULL,
  backend TEXT NOT NULL DEFAULT '',
  safe_display TEXT NOT NULL,
  template_digest TEXT NOT NULL,
  encrypted_execution_material BLOB NOT NULL,
  isolation_json TEXT NOT NULL DEFAULT '{}',
  encrypted_backend_handle BLOB,
  started_at TEXT,
  completed_at TEXT,
  lease_expires_at TEXT,
  exit_code INTEGER,
  termination_reason TEXT,
  stdout_bytes INTEGER NOT NULL DEFAULT 0,
  stderr_bytes INTEGER NOT NULL DEFAULT 0,
  truncated INTEGER NOT NULL DEFAULT 0,
  redaction_count INTEGER NOT NULL DEFAULT 0,
  receipt_digest TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_command_runs_owner_session
  ON command_runs(owner_principal_id, session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_command_runs_owner_state
  ON command_runs(owner_principal_id, state, updated_at DESC);

CREATE TABLE IF NOT EXISTS command_output_chunks (
  owner_principal_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  stream TEXT NOT NULL,
  text TEXT NOT NULL,
  start_byte_offset INTEGER NOT NULL,
  end_byte_offset INTEGER NOT NULL,
  byte_count INTEGER NOT NULL,
  emitted_at TEXT NOT NULL,
  PRIMARY KEY (run_id, sequence),
  FOREIGN KEY (run_id) REFERENCES command_runs(run_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_command_chunks_owner_run
  ON command_output_chunks(owner_principal_id, run_id, sequence);

CREATE TABLE IF NOT EXISTS command_network_grants (
  grant_id TEXT PRIMARY KEY,
  owner_principal_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  run_id TEXT,
  scope_json TEXT NOT NULL,
  decision_id TEXT NOT NULL,
  status TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  uses INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  revoked_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_command_network_grants_owner
  ON command_network_grants(owner_principal_id, session_id, status, expires_at);

CREATE TABLE IF NOT EXISTS command_network_attempts (
  attempt_id TEXT PRIMARY KEY,
  owner_principal_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  grant_id TEXT NOT NULL,
  requested_host TEXT NOT NULL,
  requested_port INTEGER NOT NULL,
  resolved_address_digest TEXT NOT NULL,
  decision TEXT NOT NULL,
  outcome TEXT NOT NULL,
  bytes_sent INTEGER NOT NULL DEFAULT 0,
  bytes_received INTEGER NOT NULL DEFAULT 0,
  opened_at TEXT NOT NULL,
  closed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_command_network_attempts_owner_run
  ON command_network_attempts(owner_principal_id, run_id, opened_at);

CREATE TABLE IF NOT EXISTS command_receipts (
  run_id TEXT PRIMARY KEY,
  owner_principal_id TEXT NOT NULL,
  receipt_json TEXT NOT NULL,
  digest TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES command_runs(run_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_command_receipts_owner_run
  ON command_receipts(owner_principal_id, run_id);
"""


# Credential-bearing container workers execute against private workspace/cache
# snapshots. Their entire delta remains blocked until an owner resolves it and
# the cleanup saga commits an immutable, owner-scoped receipt.
COMMAND_CREDENTIAL_DELTAS_MIGRATION_ID = "RAIKER-2031-command-credential-deltas"

COMMAND_CREDENTIAL_DELTAS_SQL = """
CREATE TABLE IF NOT EXISTS command_credential_deltas (
  run_id TEXT PRIMARY KEY,
  owner_principal_id TEXT NOT NULL,
  environment_profile_id TEXT NOT NULL,
  state TEXT NOT NULL,
  encrypted_snapshot_handle BLOB NOT NULL,
  encrypted_cleanup_scan_bundle BLOB NOT NULL,
  safe_manifest_json TEXT NOT NULL,
  delta_digest TEXT NOT NULL,
  scan_digest TEXT NOT NULL,
  scan_rule_version TEXT NOT NULL,
  selected_paths_json TEXT,
  decision_id TEXT,
  checkpoint_id TEXT,
  apply_idempotency_key TEXT,
  cleanup_status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_command_deltas_owner_environment
  ON command_credential_deltas(owner_principal_id, environment_profile_id, state, created_at);

CREATE TABLE IF NOT EXISTS command_delta_receipts (
  resolution_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL UNIQUE,
  owner_principal_id TEXT NOT NULL,
  command_receipt_digest TEXT NOT NULL DEFAULT '',
  delta_digest TEXT NOT NULL,
  receipt_json TEXT NOT NULL,
  digest TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_command_delta_receipts_owner_run
  ON command_delta_receipts(owner_principal_id, run_id);
"""


# Public authority evidence lets the owner-facing command surface prove that a
# run entered through an approval or standing grant without decrypting command
# material. Historical rows remain visibly unverified rather than inferred.
COMMAND_AUTHORITY_EVIDENCE_MIGRATION_ID = "RAIKER-2032-command-authority-evidence"

COMMAND_AUTHORITY_EVIDENCE_SQL = """
ALTER TABLE command_runs ADD COLUMN authority_kind TEXT NOT NULL DEFAULT '';
ALTER TABLE command_runs ADD COLUMN authority_id TEXT NOT NULL DEFAULT '';
"""
