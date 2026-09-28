# mypy: disable-error-code="misc"
"""The schema migration runner: bootstrap, the migration catalogue it applies, and
the one-off data backfills that ride on it (GCR-11).

One part of :class:`raiker.storage.sqlite.SQLiteStore`, which inherits it. Every method
is typed against the whole store (``self: SQLiteStore``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
from typing import TYPE_CHECKING

from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

from raiker.contracts.ids import utc_now
from raiker.storage.migrations import (
    AGENT_PLANS_MIGRATION_ID,
    AGENT_PLANS_SQL,
    API_SESSIONS_MIGRATION_ID,
    API_SESSIONS_SQL,
    APPROVAL_DECISION_SCOPE_MIGRATION_ID,
    APPROVAL_DECISION_SCOPE_SQL,
    ATTACHMENT_STORE_MIGRATION_ID,
    ATTACHMENT_STORE_SQL,
    BACKGROUND_WORKER_HEALTH_MIGRATION_ID,
    BACKGROUND_WORKER_HEALTH_SQL,
    BRAIN_PREFERENCES_MIGRATION_ID,
    BRAIN_PREFERENCES_SQL,
    BRAIN_SOURCE_GRANTS_MIGRATION_ID,
    BRAIN_SOURCE_GRANTS_SQL,
    BRAIN_SOURCES_MIGRATION_ID,
    BRAIN_SOURCES_SQL,
    CALENDAR_EVENTS_MIGRATION_ID,
    CALENDAR_EVENTS_SQL,
    CAPABILITY_DECISION_MODE_MIGRATION_ID,
    CAPABILITY_DECISION_MODE_SQL,
    CAPABILITY_MONITORING_MIGRATION_ID,
    CAPABILITY_MONITORING_SQL,
    CHANNEL_ROUTING_MIGRATION_ID,
    CHANNEL_ROUTING_SQL,
    CHECKPOINT_CAPTURE_HEALTH_MIGRATION_ID,
    CHECKPOINT_CAPTURE_HEALTH_SQL,
    CHECKPOINT_CAPTURE_MANIFEST_MIGRATION_ID,
    CHECKPOINT_CAPTURE_MANIFEST_SQL,
    CLOUD_EXECUTION_COST_LEDGER_MIGRATION_ID,
    CLOUD_EXECUTION_COST_LEDGER_SQL,
    CODE_MAP_MIGRATION_ID,
    CODE_MAP_SQL,
    CODE_REPOS_MIGRATION_ID,
    CODE_REPOS_SQL,
    COMMAND_AUTHORITY_EVIDENCE_MIGRATION_ID,
    COMMAND_AUTHORITY_EVIDENCE_SQL,
    COMMAND_CREDENTIAL_DELTAS_MIGRATION_ID,
    COMMAND_CREDENTIAL_DELTAS_SQL,
    COMMAND_EGRESS_MIGRATION_ID,
    COMMAND_EGRESS_SQL,
    COMMAND_RUNS_MIGRATION_ID,
    COMMAND_RUNS_SQL,
    CONFIGURED_MODELS_MIGRATION_ID,
    CONFIGURED_MODELS_SQL,
    CONNECTOR_ECOSYSTEM_MIGRATION_ID,
    CONNECTOR_ECOSYSTEM_SQL,
    CONNECTOR_INVOCATIONS_MIGRATION_ID,
    CONNECTOR_INVOCATIONS_SQL,
    CONVERSATION_COMPACTIONS_MIGRATION_ID,
    CONVERSATION_COMPACTIONS_SQL,
    CONVERSATION_FTS_MIGRATION_ID,
    CREDENTIAL_SECURITY_MIGRATION_ID,
    CREDENTIAL_SECURITY_SQL,
    CRITICAL_APPROVAL_LIFECYCLE_MIGRATION_ID,
    CRITICAL_APPROVAL_LIFECYCLE_SQL,
    EIDETIC_CAPTURE_MIGRATION_ID,
    EIDETIC_CAPTURE_SQL,
    EIDETIC_OBSERVATIONS_MIGRATION_ID,
    EIDETIC_OBSERVATIONS_SQL,
    EMAIL_DRAFTS_MIGRATION_ID,
    EMAIL_DRAFTS_SQL,
    EXECUTION_ENVIRONMENT_CONTROL_MIGRATION_ID,
    EXECUTION_ENVIRONMENT_CONTROL_SQL,
    GIST_MEMORY_MIGRATION_ID,
    GIST_MEMORY_SQL,
    GIT_CREDENTIAL_GRANT_MIGRATION_ID,
    GIT_CREDENTIAL_GRANT_SQL,
    HOST_NETWORK_CODE_CARRY_OVER_MIGRATION_ID,
    HOST_NETWORK_CODE_CARRY_OVER_SQL,
    IMAGE_GENERATIONS_MIGRATION_ID,
    IMAGE_GENERATIONS_SQL,
    IMAGE_LINEAGE_MIGRATION_ID,
    IMAGE_LINEAGE_SQL,
    LEGACY_ACCOUNT_BOOTSTRAP_ROLES_MIGRATION_ID,
    LOCAL_RUNTIME_PRESENCE_MIGRATION_ID,
    LOCAL_RUNTIME_PRESENCE_SQL,
    LOCK_SCREEN_MIGRATION_ID,
    LOCK_SCREEN_SQL,
    MACHINE_ACTION_ATTRIBUTION_MIGRATION_ID,
    MACHINE_ACTION_ATTRIBUTION_SQL,
    MACHINE_ACTION_IDENTITY_SNAPSHOT_MIGRATION_ID,
    MACHINE_ACTION_IDENTITY_SNAPSHOT_SQL,
    MACHINE_IDENTITIES_MIGRATION_ID,
    MACHINE_IDENTITIES_SQL,
    MANAGED_FILE_CHUNK_FTS_MIGRATION_ID,
    MANAGED_FILE_CHUNK_VECTORS_MIGRATION_ID,
    MANAGED_FILE_CHUNK_VECTORS_SQL,
    MANAGED_FILE_CHUNKS_MIGRATION_ID,
    MANAGED_FILE_CHUNKS_SQL,
    MANAGED_FILES_MIGRATION_ID,
    MANAGED_FILES_SQL,
    MCP_CONTAINMENT_MIGRATION_ID,
    MCP_CONTAINMENT_SQL,
    MCP_MONITORING_MIGRATION_ID,
    MCP_MONITORING_SQL,
    MCP_PROTOCOL_VERSION_MIGRATION_ID,
    MCP_PROTOCOL_VERSION_SQL,
    MCP_REMOTE_ENDPOINT_MIGRATION_ID,
    MCP_REMOTE_ENDPOINT_SQL,
    MCP_SERVER_FEATURES_MIGRATION_ID,
    MCP_SERVER_FEATURES_SQL,
    MCP_SERVER_RUNTIME_MIGRATION_ID,
    MCP_SERVER_RUNTIME_SQL,
    MCP_SERVERS_MIGRATION_ID,
    MCP_SERVERS_SQL,
    MCP_TOOL_SCHEMAS_MIGRATION_ID,
    MCP_TOOL_SCHEMAS_SQL,
    MEMORY_ARCHIVE_MIGRATION_ID,
    MEMORY_ARCHIVE_SQL,
    MEMORY_AUDIT_RATE_LIMIT_MIGRATION_ID,
    MEMORY_AUDIT_RATE_LIMIT_SQL,
    MEMORY_BACKUP_CATALOG_MIGRATION_ID,
    MEMORY_BACKUP_CATALOG_SQL,
    MEMORY_CONTENT_CHECKSUM_MIGRATION_ID,
    MEMORY_CONTENT_CHECKSUM_SQL,
    MEMORY_CONTROLS_MIGRATION_ID,
    MEMORY_CONTROLS_SQL,
    MEMORY_EMBEDDING_BACKEND_MIGRATION_ID,
    MEMORY_EMBEDDING_BACKEND_SQL,
    MEMORY_ENTITY_GRAPH_MIGRATION_ID,
    MEMORY_ENTITY_GRAPH_SQL,
    MEMORY_EVALUATION_CONTEXT_MIGRATION_ID,
    MEMORY_EVALUATION_CONTEXT_SQL,
    MEMORY_FTS_MIGRATION_ID,
    MEMORY_JOBS_MIGRATION_ID,
    MEMORY_JOBS_SQL,
    MEMORY_LIFECYCLE_AUDIT_IMMUTABILITY_MIGRATION_ID,
    MEMORY_LIFECYCLE_AUDIT_IMMUTABILITY_SQL,
    MEMORY_PROJECTIONS_MIGRATION_ID,
    MEMORY_PROJECTIONS_SQL,
    MEMORY_PURGE_MIGRATION_ID,
    MEMORY_PURGE_SQL,
    MEMORY_RELATIONSHIP_EXTRACTION_MIGRATION_ID,
    MEMORY_RELATIONSHIP_EXTRACTION_SQL,
    MEMORY_RELATIONSHIP_REVIEW_MIGRATION_ID,
    MEMORY_RELATIONSHIP_REVIEW_SQL,
    MEMORY_RETRIEVAL_AUTHORITY_MIGRATION_ID,
    MEMORY_RETRIEVAL_AUTHORITY_SQL,
    MEMORY_SQLCIPHER_FTS_MIGRATION_ID,
    MEMORY_TEMPORAL_EVALUATION_MIGRATION_ID,
    MEMORY_TEMPORAL_EVALUATION_SQL,
    MEMORY_VECTOR_SEARCH_REVISION_MIGRATION_ID,
    MEMORY_VECTOR_SEARCH_REVISION_SQL,
    MODEL_ADVISOR_MIGRATION_ID,
    MODEL_ADVISOR_SQL,
    MODEL_CAPACITY_CONTROL_MIGRATION_ID,
    MODEL_CAPACITY_CONTROL_SQL,
    MODEL_FALLBACK_SEQUENCE_MIGRATION_ID,
    MODEL_FALLBACK_SEQUENCE_SQL,
    MODEL_LIBRARY_MIGRATION_ID,
    MODEL_LIBRARY_SQL,
    MODEL_OPERATION_PAYLOAD_MIGRATION_ID,
    MODEL_OPERATION_PAYLOAD_SQL,
    MODEL_OPERATIONS_MIGRATION_ID,
    MODEL_OPERATIONS_SQL,
    MODEL_PRICE_REGISTRY_MIGRATION_ID,
    MODEL_PRICE_REGISTRY_SQL,
    MODEL_READINESS_MIGRATION_ID,
    MODEL_READINESS_SQL,
    MODEL_SESSION_RESOLVED_MODEL_MIGRATION_ID,
    MODEL_SESSION_RESOLVED_MODEL_SQL,
    MODEL_SETUP_STATE_MIGRATION_ID,
    MODEL_SETUP_STATE_SQL,
    MODEL_USAGE_LEDGER_MIGRATION_ID,
    MODEL_USAGE_LEDGER_SQL,
    MODEL_USAGE_ROLLING_WINDOW_MIGRATION_ID,
    MODEL_USAGE_ROLLING_WINDOW_SQL,
    OWNED_CONTEXT_DATA_MIGRATION_ID,
    OWNED_CONTEXT_DATA_SQL,
    OWNED_MEMORY_METADATA_MIGRATION_ID,
    OWNED_MEMORY_METADATA_SQL,
    OWNER_QUESTION_ANSWER_MIGRATION_ID,
    OWNER_QUESTION_ANSWER_SQL,
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
    PRINCIPAL_CONTROL_SCOPE_MIGRATION_ID,
    PRINCIPAL_CONTROL_SCOPE_SQL,
    PROJECT_CONTEXT_MIGRATION_ID,
    PROJECT_CONTEXT_SQL,
    PROJECT_MEMORY_INHERITANCE_MIGRATION_ID,
    PROJECT_MEMORY_INHERITANCE_SQL,
    PROJECT_SELF_INCLUSIVE_PATH_MIGRATION_ID,
    PROJECTS_MIGRATION_ID,
    PROJECTS_NESTING_MIGRATION_ID,
    PROJECTS_NESTING_SQL,
    PROJECTS_SQL,
    PROVIDER_CATALOGUE_MIGRATION_ID,
    PROVIDER_CATALOGUE_SQL,
    PROVIDER_USAGE_SNAPSHOTS_MIGRATION_ID,
    PROVIDER_USAGE_SNAPSHOTS_SQL,
    REMINDERS_MIGRATION_ID,
    REMINDERS_SQL,
    SESSION_ARCHIVE_MIGRATION_ID,
    SESSION_ARCHIVE_SQL,
    SESSION_ATTACHMENT_REFS_MIGRATION_ID,
    SESSION_ATTACHMENT_REFS_SQL,
    SESSION_ATTACHMENT_SOURCE_MIGRATION_ID,
    SESSION_ATTACHMENT_SOURCE_SQL,
    SESSION_COMMAND_GRANTS_MIGRATION_ID,
    SESSION_COMMAND_GRANTS_SQL,
    SESSION_ORIGIN_MIGRATION_ID,
    SESSION_ORIGIN_SQL,
    SESSION_TAGS_MIGRATION_ID,
    SESSION_TAGS_SQL,
    SETUP_STATE_MIGRATION_ID,
    SETUP_STATE_SQL,
    SKILL_COMMANDS_MIGRATION_ID,
    SKILL_COMMANDS_SQL,
    SKILLS_MIGRATION_ID,
    SKILLS_SQL,
    STANDING_GRANTS_MIGRATION_ID,
    STANDING_GRANTS_SQL,
    SUBAGENT_BUDGETS_MIGRATION_ID,
    SUBAGENT_BUDGETS_SQL,
    SURFACE_MODEL_DEFAULT_MIGRATION_ID,
    SURFACE_MODEL_DEFAULT_SQL,
    SUSPENDED_TURN_QUEUE_MIGRATION_ID,
    SUSPENDED_TURN_QUEUE_SQL,
    SUSPENDED_TURNS_MIGRATION_ID,
    SUSPENDED_TURNS_SQL,
    TASK_ATTACHMENTS_MIGRATION_ID,
    TASK_ATTACHMENTS_SQL,
    TASK_MODEL_CHOICES_MIGRATION_ID,
    TASK_MODEL_CHOICES_SQL,
    TASK_SURFACE_MIGRATION_ID,
    TASK_SURFACE_SQL,
    TASK_THREAD_SESSION_MIGRATION_ID,
    TASK_THREAD_SESSION_SQL,
    TELEMETRY_CADENCE_MIGRATION_ID,
    TELEMETRY_CADENCE_SQL,
    TELEMETRY_DESTINATIONS_MIGRATION_ID,
    TELEMETRY_DESTINATIONS_SQL,
    THREAT_MODEL_ACKS_MIGRATION_ID,
    THREAT_MODEL_ACKS_SQL,
    TURN_CONTROLS_MIGRATION_ID,
    TURN_CONTROLS_SQL,
    TURN_MEMORY_PROVENANCE_MIGRATION_ID,
    TURN_MEMORY_PROVENANCE_SQL,
    TURN_REASONING_MIGRATION_ID,
    TURN_REASONING_SQL,
    TURN_RECALL_MIGRATION_ID,
    TURN_RECALL_SQL,
    TURN_SOURCE_ANCHORS_MIGRATION_ID,
    TURN_SOURCE_ANCHORS_SQL,
    TURN_SOURCE_LOCATOR_INDEX_MIGRATION_ID,
    TURN_SOURCE_LOCATOR_INDEX_SQL,
    TURN_SOURCES_MIGRATION_ID,
    TURN_SOURCES_SQL,
    WEB_BLOCKLIST_MIGRATION_ID,
    WEB_BLOCKLIST_SQL,
    conversation_fts_sql,
    managed_file_chunk_fts_sql,
    memory_fts_sql,
    memory_sqlcipher_fts_sql,
)

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


class MigrationRunner:

    def bootstrap(self: SQLiteStore) -> None:
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

            # Read once, before anything in this pass applies, which is what
            # makes it equivalent to asking per migration: an id absent here is
            # applied and then recorded, and `INSERT OR IGNORE` keeps that safe
            # either way.
            self._applied = {
                str(row["migration_id"])
                for row in connection.execute("SELECT migration_id FROM migrations")
            }

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
                connection.execute(
                    "ALTER TABLE sessions ADD COLUMN user_id TEXT REFERENCES users(user_id)"
                )
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
            self._apply_migration(MANAGED_FILES_MIGRATION_ID, MANAGED_FILES_SQL, connection)
            self._apply_migration(
                MANAGED_FILE_CHUNKS_MIGRATION_ID, MANAGED_FILE_CHUNKS_SQL, connection
            )
            self._apply_migration(
                MANAGED_FILE_CHUNK_FTS_MIGRATION_ID,
                managed_file_chunk_fts_sql(self.text_search_engine(connection)),
                connection,
            )
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
                connection.execute(
                    "ALTER TABLE sessions ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0"
                )
            with contextlib.suppress(sqlite3.OperationalError):
                connection.execute(
                    "ALTER TABLE projects ADD COLUMN owner_user_id TEXT REFERENCES users(user_id)"
                )
            # A project's root is now one of two things. `root_kind` says which,
            # and `root_grant_id` names the owner's grant when the root is a
            # folder they already had. Defaulting to 'managed' makes this a
            # no-op for every project that exists today.
            for _root_column in (
                "ALTER TABLE projects ADD COLUMN root_kind TEXT NOT NULL DEFAULT 'managed'",
                "ALTER TABLE projects ADD COLUMN root_grant_id TEXT",
                # Bytes Raiker discovered rather than wrote need a cheap change
                # signal, or every reconcile re-hashes the whole tree.
                "ALTER TABLE managed_files ADD COLUMN source_mtime_ns INTEGER",
            ):
                with contextlib.suppress(sqlite3.OperationalError):
                    connection.execute(_root_column)
            # Two projects over one folder would put a single file inside two
            # mutually exclusive "only this project" boundaries, so the database
            # refuses it rather than trusting every caller to check.
            with contextlib.suppress(sqlite3.OperationalError):
                connection.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_attached_root "
                    "ON projects(root_grant_id) WHERE root_grant_id IS NOT NULL"
                )
            self._apply_migration(LOCK_SCREEN_MIGRATION_ID, LOCK_SCREEN_SQL, connection)
            self._backfill_legacy_account_data_owner(connection)
            self._apply_migration(
                OWNED_CONTEXT_DATA_MIGRATION_ID, OWNED_CONTEXT_DATA_SQL, connection
            )
            self._backfill_owned_context_data(connection)
            self._apply_migration(
                OWNED_MEMORY_METADATA_MIGRATION_ID, OWNED_MEMORY_METADATA_SQL, connection
            )
            self._backfill_owned_memory_metadata(connection)
            self._apply_migration(
                PRINCIPAL_CONTROL_SCOPE_MIGRATION_ID, PRINCIPAL_CONTROL_SCOPE_SQL, connection
            )
            self._apply_migration(BRAIN_SOURCES_MIGRATION_ID, BRAIN_SOURCES_SQL, connection)
            self._apply_migration(
                BRAIN_SOURCE_GRANTS_MIGRATION_ID, BRAIN_SOURCE_GRANTS_SQL, connection
            )
            # The grant stops implying read-only and starts saying what it
            # allows, so one record can serve the Knowledge Map's read-only
            # folders and a project's writable root. Applied here rather than in
            # the projects block above, because that runs before this table
            # exists.
            with contextlib.suppress(sqlite3.OperationalError):
                connection.execute(
                    "ALTER TABLE brain_source_grants "
                    "ADD COLUMN write_enabled INTEGER NOT NULL DEFAULT 0"
                )
            self._apply_migration(BRAIN_PREFERENCES_MIGRATION_ID, BRAIN_PREFERENCES_SQL, connection)
            self._apply_migration(
                EXECUTION_ENVIRONMENT_CONTROL_MIGRATION_ID,
                EXECUTION_ENVIRONMENT_CONTROL_SQL,
                connection,
            )
            self._apply_migration(
                MODEL_CAPACITY_CONTROL_MIGRATION_ID, MODEL_CAPACITY_CONTROL_SQL, connection
            )
            self._backfill_legacy_brain_sources(connection)
            self._backfill_legacy_account_bootstrap_roles(connection)
            self._migrate_legacy_controls_to_original_owner(connection)
            self._apply_migration(MEMORY_CONTROLS_MIGRATION_ID, MEMORY_CONTROLS_SQL, connection)
            self._apply_migration(SESSION_TAGS_MIGRATION_ID, SESSION_TAGS_SQL, connection)
            self._apply_migration(SESSION_ARCHIVE_MIGRATION_ID, SESSION_ARCHIVE_SQL, connection)
            self._apply_migration(PROJECTS_NESTING_MIGRATION_ID, PROJECTS_NESTING_SQL, connection)
            self._apply_migration(
                PROJECT_MEMORY_INHERITANCE_MIGRATION_ID,
                PROJECT_MEMORY_INHERITANCE_SQL,
                connection,
            )
            self._backfill_self_inclusive_project_paths(connection)
            self._apply_migration(MEMORY_ARCHIVE_MIGRATION_ID, MEMORY_ARCHIVE_SQL, connection)
            self._apply_migration(
                EIDETIC_OBSERVATIONS_MIGRATION_ID, EIDETIC_OBSERVATIONS_SQL, connection
            )
            self._apply_migration(EIDETIC_CAPTURE_MIGRATION_ID, EIDETIC_CAPTURE_SQL, connection)
            self._apply_migration(MEMORY_PURGE_MIGRATION_ID, MEMORY_PURGE_SQL, connection)
            self._apply_migration(GIST_MEMORY_MIGRATION_ID, GIST_MEMORY_SQL, connection)
            self._apply_migration(
                MEMORY_PROJECTIONS_MIGRATION_ID, MEMORY_PROJECTIONS_SQL, connection
            )
            engine = self.text_search_engine(connection)
            self._apply_migration(MEMORY_FTS_MIGRATION_ID, memory_fts_sql(engine), connection)
            self._apply_migration(
                MEMORY_SQLCIPHER_FTS_MIGRATION_ID, memory_sqlcipher_fts_sql(engine), connection
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
                MEMORY_CONTENT_CHECKSUM_MIGRATION_ID,
                MEMORY_CONTENT_CHECKSUM_SQL,
                connection,
            )
            self._apply_migration(
                MEMORY_EVALUATION_CONTEXT_MIGRATION_ID,
                MEMORY_EVALUATION_CONTEXT_SQL,
                connection,
            )
            rows = connection.execute(
                "SELECT memory_id, text FROM approved_memory WHERE content_checksum IS NULL"
            ).fetchall()
            connection.executemany(
                "UPDATE approved_memory SET content_checksum = ? WHERE memory_id = ?",
                (
                    (hashlib.sha256(str(row["text"]).encode()).hexdigest(), row["memory_id"])
                    for row in rows
                ),
            )
            self._apply_migration(
                MEMORY_ENTITY_GRAPH_MIGRATION_ID, MEMORY_ENTITY_GRAPH_SQL, connection
            )
            self._apply_migration(
                MEMORY_RELATIONSHIP_REVIEW_MIGRATION_ID, MEMORY_RELATIONSHIP_REVIEW_SQL, connection
            )
            self._apply_migration(
                MEMORY_BACKUP_CATALOG_MIGRATION_ID, MEMORY_BACKUP_CATALOG_SQL, connection
            )
            self._apply_migration(MEMORY_JOBS_MIGRATION_ID, MEMORY_JOBS_SQL, connection)
            self._apply_migration(
                MEMORY_AUDIT_RATE_LIMIT_MIGRATION_ID, MEMORY_AUDIT_RATE_LIMIT_SQL, connection
            )
            self._apply_migration(
                MEMORY_LIFECYCLE_AUDIT_IMMUTABILITY_MIGRATION_ID,
                MEMORY_LIFECYCLE_AUDIT_IMMUTABILITY_SQL,
                connection,
            )
            self._apply_migration(MCP_SERVERS_MIGRATION_ID, MCP_SERVERS_SQL, connection)
            self._apply_migration(
                MCP_SERVER_RUNTIME_MIGRATION_ID, MCP_SERVER_RUNTIME_SQL, connection
            )
            self._apply_migration(
                MCP_REMOTE_ENDPOINT_MIGRATION_ID, MCP_REMOTE_ENDPOINT_SQL, connection
            )
            self._apply_migration(MCP_MONITORING_MIGRATION_ID, MCP_MONITORING_SQL, connection)
            self._apply_migration(MCP_CONTAINMENT_MIGRATION_ID, MCP_CONTAINMENT_SQL, connection)
            self._apply_migration(
                CREDENTIAL_SECURITY_MIGRATION_ID, CREDENTIAL_SECURITY_SQL, connection
            )
            self._apply_migration(
                CHECKPOINT_CAPTURE_MANIFEST_MIGRATION_ID,
                CHECKPOINT_CAPTURE_MANIFEST_SQL,
                connection,
            )
            self._apply_migration(STANDING_GRANTS_MIGRATION_ID, STANDING_GRANTS_SQL, connection)
            self._apply_migration(
                CRITICAL_APPROVAL_LIFECYCLE_MIGRATION_ID,
                CRITICAL_APPROVAL_LIFECYCLE_SQL,
                connection,
            )
            self._apply_migration(SUBAGENT_BUDGETS_MIGRATION_ID, SUBAGENT_BUDGETS_SQL, connection)
            self._apply_migration(CODE_REPOS_MIGRATION_ID, CODE_REPOS_SQL, connection)
            self._apply_migration(CODE_MAP_MIGRATION_ID, CODE_MAP_SQL, connection)
            self._apply_migration(
                CAPABILITY_MONITORING_MIGRATION_ID, CAPABILITY_MONITORING_SQL, connection
            )
            self._apply_migration(
                MODEL_USAGE_LEDGER_MIGRATION_ID, MODEL_USAGE_LEDGER_SQL, connection
            )
            self._apply_migration(
                MODEL_USAGE_ROLLING_WINDOW_MIGRATION_ID,
                MODEL_USAGE_ROLLING_WINDOW_SQL,
                connection,
            )
            self._apply_migration(
                PROVIDER_USAGE_SNAPSHOTS_MIGRATION_ID,
                PROVIDER_USAGE_SNAPSHOTS_SQL,
                connection,
            )
            self._apply_migration(
                CONVERSATION_COMPACTIONS_MIGRATION_ID,
                CONVERSATION_COMPACTIONS_SQL,
                connection,
            )
            self._apply_migration(SUSPENDED_TURNS_MIGRATION_ID, SUSPENDED_TURNS_SQL, connection)
            self._apply_migration(
                SUSPENDED_TURN_QUEUE_MIGRATION_ID, SUSPENDED_TURN_QUEUE_SQL, connection
            )
            self._apply_migration(
                SESSION_ATTACHMENT_REFS_MIGRATION_ID, SESSION_ATTACHMENT_REFS_SQL, connection
            )
            self._apply_migration(
                SESSION_ATTACHMENT_SOURCE_MIGRATION_ID,
                SESSION_ATTACHMENT_SOURCE_SQL,
                connection,
            )
            self._apply_migration(
                SESSION_COMMAND_GRANTS_MIGRATION_ID,
                SESSION_COMMAND_GRANTS_SQL,
                connection,
            )
            self._apply_migration(SESSION_ORIGIN_MIGRATION_ID, SESSION_ORIGIN_SQL, connection)
            self._apply_migration(CONFIGURED_MODELS_MIGRATION_ID, CONFIGURED_MODELS_SQL, connection)
            self._apply_migration(
                PROVIDER_CATALOGUE_MIGRATION_ID, PROVIDER_CATALOGUE_SQL, connection
            )
            self._apply_migration(
                TASK_MODEL_CHOICES_MIGRATION_ID, TASK_MODEL_CHOICES_SQL, connection
            )
            self._apply_migration(
                MODEL_PRICE_REGISTRY_MIGRATION_ID, MODEL_PRICE_REGISTRY_SQL, connection
            )
            self._apply_migration(
                CLOUD_EXECUTION_COST_LEDGER_MIGRATION_ID,
                CLOUD_EXECUTION_COST_LEDGER_SQL,
                connection,
            )
            self._apply_migration(TASK_ATTACHMENTS_MIGRATION_ID, TASK_ATTACHMENTS_SQL, connection)
            self._apply_migration(SKILLS_MIGRATION_ID, SKILLS_SQL, connection)
            self._apply_migration(AGENT_PLANS_MIGRATION_ID, AGENT_PLANS_SQL, connection)
            self._apply_migration(TURN_CONTROLS_MIGRATION_ID, TURN_CONTROLS_SQL, connection)
            self._apply_migration(TURN_SOURCES_MIGRATION_ID, TURN_SOURCES_SQL, connection)
            self._apply_migration(
                TURN_SOURCE_ANCHORS_MIGRATION_ID, TURN_SOURCE_ANCHORS_SQL, connection
            )
            self._apply_migration(TURN_RECALL_MIGRATION_ID, TURN_RECALL_SQL, connection)
            self._apply_migration(
                MACHINE_IDENTITIES_MIGRATION_ID, MACHINE_IDENTITIES_SQL, connection
            )
            self._apply_migration(
                MACHINE_ACTION_ATTRIBUTION_MIGRATION_ID,
                MACHINE_ACTION_ATTRIBUTION_SQL,
                connection,
            )
            self._apply_migration(
                MACHINE_ACTION_IDENTITY_SNAPSHOT_MIGRATION_ID,
                MACHINE_ACTION_IDENTITY_SNAPSHOT_SQL,
                connection,
            )
            self._apply_migration(
                MODEL_READINESS_MIGRATION_ID,
                MODEL_READINESS_SQL,
                connection,
            )
            self._apply_migration(
                MODEL_SETUP_STATE_MIGRATION_ID,
                MODEL_SETUP_STATE_SQL,
                connection,
            )
            self._apply_migration(SETUP_STATE_MIGRATION_ID, SETUP_STATE_SQL, connection)
            self._apply_migration(
                MODEL_OPERATIONS_MIGRATION_ID,
                MODEL_OPERATIONS_SQL,
                connection,
            )
            self._apply_migration(
                MODEL_OPERATION_PAYLOAD_MIGRATION_ID,
                MODEL_OPERATION_PAYLOAD_SQL,
                connection,
            )
            self._apply_migration(
                MODEL_LIBRARY_MIGRATION_ID,
                MODEL_LIBRARY_SQL,
                connection,
            )
            self._apply_migration(
                SURFACE_MODEL_DEFAULT_MIGRATION_ID,
                SURFACE_MODEL_DEFAULT_SQL,
                connection,
            )
            self._apply_migration(
                CONVERSATION_FTS_MIGRATION_ID,
                conversation_fts_sql(self.text_search_engine(connection)),
                connection,
            )
            self._apply_migration(WEB_BLOCKLIST_MIGRATION_ID, WEB_BLOCKLIST_SQL, connection)
            self._apply_migration(
                GIT_CREDENTIAL_GRANT_MIGRATION_ID, GIT_CREDENTIAL_GRANT_SQL, connection
            )
            self._apply_migration(COMMAND_RUNS_MIGRATION_ID, COMMAND_RUNS_SQL, connection)
            self._apply_migration(
                COMMAND_CREDENTIAL_DELTAS_MIGRATION_ID,
                COMMAND_CREDENTIAL_DELTAS_SQL,
                connection,
            )
            self._apply_migration(
                COMMAND_AUTHORITY_EVIDENCE_MIGRATION_ID,
                COMMAND_AUTHORITY_EVIDENCE_SQL,
                connection,
            )
            self._apply_migration(COMMAND_EGRESS_MIGRATION_ID, COMMAND_EGRESS_SQL, connection)
            self._apply_migration(
                CHECKPOINT_CAPTURE_HEALTH_MIGRATION_ID,
                CHECKPOINT_CAPTURE_HEALTH_SQL,
                connection,
            )
            self._apply_migration(
                MEMORY_RELATIONSHIP_EXTRACTION_MIGRATION_ID,
                MEMORY_RELATIONSHIP_EXTRACTION_SQL,
                connection,
            )
            self._apply_migration(
                TURN_MEMORY_PROVENANCE_MIGRATION_ID,
                TURN_MEMORY_PROVENANCE_SQL,
                connection,
            )
            self._apply_migration(
                MCP_PROTOCOL_VERSION_MIGRATION_ID,
                MCP_PROTOCOL_VERSION_SQL,
                connection,
            )
            self._apply_migration(
                MANAGED_FILE_CHUNK_VECTORS_MIGRATION_ID,
                MANAGED_FILE_CHUNK_VECTORS_SQL,
                connection,
            )
            self._apply_migration(
                CHANNEL_ROUTING_MIGRATION_ID, CHANNEL_ROUTING_SQL, connection
            )
            self._apply_migration(
                SKILL_COMMANDS_MIGRATION_ID, SKILL_COMMANDS_SQL, connection
            )
            self._apply_migration(
                OWNER_QUESTION_ANSWER_MIGRATION_ID, OWNER_QUESTION_ANSWER_SQL, connection
            )
            self._apply_migration(
                LOCAL_RUNTIME_PRESENCE_MIGRATION_ID,
                LOCAL_RUNTIME_PRESENCE_SQL,
                connection,
            )
            self._apply_migration(
                TASK_THREAD_SESSION_MIGRATION_ID,
                TASK_THREAD_SESSION_SQL,
                connection,
            )
            self._apply_migration(
                APPROVAL_DECISION_SCOPE_MIGRATION_ID,
                APPROVAL_DECISION_SCOPE_SQL,
                connection,
            )
            self._apply_migration(
                MCP_TOOL_SCHEMAS_MIGRATION_ID,
                MCP_TOOL_SCHEMAS_SQL,
                connection,
            )
            self._apply_migration(
                MCP_SERVER_FEATURES_MIGRATION_ID,
                MCP_SERVER_FEATURES_SQL,
                connection,
            )
            self._apply_migration(
                TELEMETRY_DESTINATIONS_MIGRATION_ID,
                TELEMETRY_DESTINATIONS_SQL,
                connection,
            )
            self._apply_migration(
                TASK_SURFACE_MIGRATION_ID,
                TASK_SURFACE_SQL,
                connection,
            )
            self._apply_migration(
                TELEMETRY_CADENCE_MIGRATION_ID,
                TELEMETRY_CADENCE_SQL,
                connection,
            )
            self._apply_migration(
                IMAGE_GENERATIONS_MIGRATION_ID,
                IMAGE_GENERATIONS_SQL,
                connection,
            )
            self._apply_migration(
                IMAGE_LINEAGE_MIGRATION_ID,
                IMAGE_LINEAGE_SQL,
                connection,
            )
            self._apply_migration(
                BACKGROUND_WORKER_HEALTH_MIGRATION_ID,
                BACKGROUND_WORKER_HEALTH_SQL,
                connection,
            )
            self._apply_migration(TURN_REASONING_MIGRATION_ID, TURN_REASONING_SQL, connection)
            self._apply_migration(
                MEMORY_EMBEDDING_BACKEND_MIGRATION_ID,
                MEMORY_EMBEDDING_BACKEND_SQL,
                connection,
            )
            self._apply_migration(
                TURN_SOURCE_LOCATOR_INDEX_MIGRATION_ID,
                TURN_SOURCE_LOCATOR_INDEX_SQL,
                connection,
            )
            self._apply_migration(
                MEMORY_VECTOR_SEARCH_REVISION_MIGRATION_ID,
                MEMORY_VECTOR_SEARCH_REVISION_SQL,
                connection,
            )
            self._apply_migration(
                HOST_NETWORK_CODE_CARRY_OVER_MIGRATION_ID,
                HOST_NETWORK_CODE_CARRY_OVER_SQL,
                connection,
            )
            # Before the backfills: converting an index and then deciding it is
            # empty enough to need populating is one read, not two rebuilds.
            self._migrate_text_search_engine(connection)
            self._backfill_memory_fts(connection)
            self._backfill_conversation_fts(connection)
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
        # The pass is over; anything that asks again asks the table.
        self._applied = None

    def _migrate_plaintext_database(self: SQLiteStore) -> None:
        """Convert a legacy stdlib-SQLite file before SQLCipher opens it."""
        if not self.db_path.exists() or not self.db_path.read_bytes()[:16].startswith(
            b"SQLite format 3"
        ):
            return
        import sqlite3 as plaintext_sqlite

        legacy_path = self.db_path.with_suffix(".plaintext-backup")
        self.db_path.replace(legacy_path)
        try:
            # `with connection:` commits but does not close, and Windows refuses
            # to unlink/replace a file that still has an open handle. Both
            # connections are therefore closed explicitly before this function
            # touches either file again.
            source = plaintext_sqlite.connect(legacy_path)
            encrypted = self.connect()
            try:
                with source, encrypted:
                    # SQLite dumps do not guarantee parent-before-child INSERT order.
                    # Import under the legacy database's existing integrity state, then
                    # restore enforcement for every normal Raiker connection.
                    encrypted.execute("PRAGMA foreign_keys = OFF")
                    # FTS virtual-table shadow rows are engine-specific. Rebuild this
                    # disposable projection from approved memory after importing,
                    # on whichever engine the destination build has — the source
                    # file's engine is not necessarily available here.
                    engine = self.text_search_engine(encrypted)
                    dump = "\n".join(
                        line for line in source.iterdump() if "approved_memory_fts" not in line
                    )
                    for candidate in ("fts5", "fts4"):
                        dump = dump.replace(f"USING {candidate}(", f"USING {engine}(")
                    encrypted.executescript(dump)
                    encrypted.execute("PRAGMA foreign_keys = ON")
            finally:
                source.close()
                encrypted.close()
            legacy_path.unlink()
        except Exception:
            if self.db_path.exists():
                self.db_path.unlink()
            legacy_path.replace(self.db_path)
            raise

    _ADD_COLUMN_RE = re.compile(
        r"^\s*ALTER\s+TABLE\s+(?P<table>\w+)\s+ADD\s+COLUMN\s+(?P<column>\w+)\b",
        re.IGNORECASE,
    )

    @classmethod
    def _skip_existing_add_columns(cls: type[SQLiteStore], connection: sqlite3.Connection, sql: str) -> str:
        """Drop ADD COLUMN statements whose column is already present.

        SQLite has no ``ADD COLUMN IF NOT EXISTS``, so re-running a migration
        that added columns raises "duplicate column name" on the first one and
        strands every statement after it. Filtering those makes such a script
        idempotent, which is what lets a partially-applied migration resume.
        Splitting on ``;`` is lossless here because the parts are rejoined with
        ``;`` and only whole leading ADD COLUMN statements are dropped.
        """
        kept: list[str] = []
        for statement in sql.split(";"):
            match = cls._ADD_COLUMN_RE.match(statement)
            if match is not None:
                columns = {
                    str(row["name"])
                    for row in connection.execute(
                        f'PRAGMA table_info("{match["table"]}")'
                    ).fetchall()
                }
                if match["column"] in columns:
                    continue
            kept.append(statement)
        return ";".join(kept)

    def _apply_migration(self: SQLiteStore, migration_id: str, sql: str, connection: sqlite3.Connection) -> None:
        if self._applied is not None:
            if migration_id in self._applied:
                return
        else:
            row = connection.execute(
                "SELECT applied_at FROM migrations WHERE migration_id = ?", (migration_id,)
            ).fetchone()
            if row is not None:
                return
        # `executescript` commits implicitly, so a script cannot share a
        # transaction with its own bookkeeping row: a crash between the two is
        # always possible. Idempotency is what makes that safe — the re-run
        # skips whatever already landed and completes the rest. Errors are
        # deliberately not suppressed: a migration whose script did not apply
        # must not be recorded as applied, or it never runs again.
        connection.executescript(self._skip_existing_add_columns(connection, sql))
        connection.execute(
            "INSERT OR IGNORE INTO migrations (migration_id, applied_at) VALUES (?, ?)",
            (migration_id, utc_now()),
        )
        if self._applied is not None:
            self._applied.add(migration_id)

    def _backfill_legacy_account_bootstrap_roles(self: SQLiteStore, connection: sqlite3.Connection) -> None:
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        try:
            if (
                connection.execute(
                    "SELECT 1 FROM migrations WHERE migration_id = ?",
                    (LEGACY_ACCOUNT_BOOTSTRAP_ROLES_MIGRATION_ID,),
                ).fetchone()
                is not None
            ):
                connection.commit()
                return

            principals = connection.execute(
                "SELECT p.principal_id, p.delegated_by_user_id, p.role_ids "
                "FROM principals AS p "
                "JOIN account_credentials AS ac ON ac.principal_id = p.principal_id "
                "JOIN users AS u ON u.user_id = p.delegated_by_user_id "
                "WHERE p.principal_type = 'human' AND p.is_active = 1 AND u.is_active = 1 "
                "AND p.delegated_by_user_id IS NOT NULL AND p.delegated_by_user_id != ''"
            ).fetchall()
            required_role_ids = ("rl_admin", "rl_approver", "rl_rgm")
            for principal in principals:
                role_ids = json.loads(principal["role_ids"] or "[]")
                missing_role_ids = [
                    role_id for role_id in required_role_ids if role_id not in role_ids
                ]
                if missing_role_ids:
                    connection.execute(
                        "UPDATE principals SET role_ids = ? WHERE principal_id = ?",
                        (
                            json.dumps([*role_ids, *missing_role_ids], sort_keys=True),
                            principal["principal_id"],
                        ),
                    )
                for role_id in required_role_ids:
                    assignments = connection.execute(
                        "SELECT assignment_id FROM user_role_assignments "
                        "WHERE user_id = ? AND role_id = ? ORDER BY rowid",
                        (principal["delegated_by_user_id"], role_id),
                    ).fetchall()
                    if assignments:
                        connection.executemany(
                            "DELETE FROM user_role_assignments WHERE assignment_id = ?",
                            [(assignment["assignment_id"],) for assignment in assignments[1:]],
                        )
                        continue
                    connection.execute(
                        "INSERT INTO user_role_assignments "
                        "(assignment_id, user_id, role_id, granted_at, granted_by) VALUES (?, ?, ?, ?, ?)",
                        (
                            f"ura_backfill_{principal['principal_id']}_{role_id}",
                            principal["delegated_by_user_id"],
                            role_id,
                            utc_now(),
                            "legacy_account_role_migration",
                        ),
                    )
            connection.execute(
                "INSERT INTO migrations (migration_id, applied_at) VALUES (?, ?)",
                (LEGACY_ACCOUNT_BOOTSTRAP_ROLES_MIGRATION_ID, utc_now()),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def _migrate_legacy_controls_to_original_owner(self: SQLiteStore, connection: sqlite3.Connection) -> None:
        """Copy shared legacy controls once, exclusively to the oldest account."""
        owner = connection.execute(
            "SELECT principal_id FROM account_credentials ORDER BY created_at, principal_id LIMIT 1"
        ).fetchone()
        if owner is not None:
            connection.execute(
                "INSERT OR IGNORE INTO instance_account_guard (singleton, principal_id) VALUES (1, ?)",
                (owner["principal_id"],),
            )
            self.initialize_principal_controls(str(owner["principal_id"]), connection=connection)

    def _backfill_legacy_account_data_owner(self: SQLiteStore, connection: sqlite3.Connection) -> None:
        principal_id = self._original_owner_from_connection(connection)
        if principal_id is None:
            return
        principal = connection.execute(
            "SELECT delegated_by_user_id FROM principals WHERE principal_id = ?", (principal_id,)
        ).fetchone()
        user_id = (
            str(principal["delegated_by_user_id"] or principal_id.removeprefix("principal_"))
            if principal
            else ""
        )
        if (
            not user_id
            or connection.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone()
            is None
        ):
            return
        connection.execute("UPDATE sessions SET user_id = ? WHERE user_id IS NULL", (user_id,))
        connection.execute(
            "UPDATE projects SET owner_user_id = ? WHERE owner_user_id IS NULL", (user_id,)
        )
        legacy_active = connection.execute(
            "SELECT project_id FROM active_project WHERE scope_id IN ('local_single_user', 'project_scope:legacy') "
            "ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        if legacy_active is not None and legacy_active["project_id"] is not None:
            connection.execute(
                "INSERT OR REPLACE INTO active_project (scope_id, project_id, updated_at) VALUES (?, ?, ?)",
                (f"project_scope:{user_id}", legacy_active["project_id"], utc_now()),
            )

    @staticmethod
    def _backfill_owned_context_data(connection: sqlite3.Connection) -> None:
        """Assign pre-account prompt data to the original account, never a later one.

        Resolution belongs to `_original_owner_from_connection`, which prefers
        the guard row and skips deactivated principals. A local copy of that
        query silently files new data against the owner a recovery replaced.
        """
        from raiker.storage.sqlite import SQLiteStore  # defined after its parts

        owner = SQLiteStore._original_owner_from_connection(connection)
        if owner is None:
            return
        principal_id = owner
        connection.execute(
            "UPDATE approved_memory SET owner_principal_id = ? WHERE owner_principal_id IS NULL",
            (principal_id,),
        )
        connection.execute(
            "UPDATE vector_records SET owner_principal_id = ? WHERE owner_principal_id IS NULL",
            (principal_id,),
        )
        connection.execute(
            "UPDATE attachments SET owner_principal_id = ? WHERE owner_principal_id IS NULL",
            (principal_id,),
        )

    @staticmethod
    def _backfill_owned_memory_metadata(connection: sqlite3.Connection) -> None:
        from raiker.storage.sqlite import SQLiteStore  # defined after its parts

        owner = SQLiteStore._original_owner_from_connection(connection)
        if owner is not None:
            connection.execute(
                "UPDATE memory_candidates SET owner_principal_id = ? WHERE owner_principal_id IS NULL",
                (owner,),
            )

    def _backfill_legacy_brain_sources(self: SQLiteStore, connection: sqlite3.Connection) -> None:
        """Migrate the former shared source list to the original account once."""
        owner = self._original_owner_from_connection(connection)
        legacy_path = self.paths.runtime_dir / "brain-sources.json"
        if owner is None or not legacy_path.exists():
            return
        try:
            raw = json.loads(legacy_path.read_text(encoding="utf-8"))
            sources = [item for item in raw if isinstance(item, str) and item]
        except (OSError, ValueError, TypeError):
            return
        connection.executemany(
            "INSERT OR IGNORE INTO brain_sources (owner_principal_id, path, created_at) VALUES (?, ?, ?)",
            [(owner, source, utc_now()) for source in sources],
        )
        with contextlib.suppress(OSError):
            legacy_path.unlink()

    def _backfill_self_inclusive_project_paths(self: SQLiteStore, connection: sqlite3.Connection) -> None:
        """Derive paths from the authoritative adjacency list once per database."""
        if (
            connection.execute(
                "SELECT 1 FROM migrations WHERE migration_id = ?",
                (PROJECT_SELF_INCLUSIVE_PATH_MIGRATION_ID,),
            ).fetchone()
            is not None
        ):
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
