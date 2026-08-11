from __future__ import annotations

import atexit
import contextlib
import hashlib
import json
import logging
import os
import re
import threading
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlcipher3 import dbapi2 as sqlite3  # type: ignore[import-untyped]

from raiker.auth.app_key import ensure_app_key
from raiker.contracts.ids import new_id, utc_now
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
from raiker.models.library import LocalModel
from raiker.models.local_operations import ModelOperation
from raiker.models.readiness import ModelReadiness, ModelReadinessKey, ModelReadinessState
from raiker.models.session_state import ModelSessionState
from raiker.models.setup import ModelSetupState, SetupState
from raiker.storage.migrations import (
    AGENT_PLANS_MIGRATION_ID,
    AGENT_PLANS_SQL,
    API_SESSIONS_MIGRATION_ID,
    API_SESSIONS_SQL,
    ATTACHMENT_STORE_MIGRATION_ID,
    ATTACHMENT_STORE_SQL,
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
    CHECKPOINT_CAPTURE_MANIFEST_MIGRATION_ID,
    CHECKPOINT_CAPTURE_MANIFEST_SQL,
    CLOUD_EXECUTION_COST_LEDGER_MIGRATION_ID,
    CLOUD_EXECUTION_COST_LEDGER_SQL,
    CODE_MAP_MIGRATION_ID,
    CODE_MAP_SQL,
    CODE_REPOS_MIGRATION_ID,
    CODE_REPOS_SQL,
    CONFIGURED_MODELS_MIGRATION_ID,
    CONFIGURED_MODELS_SQL,
    CONNECTOR_ECOSYSTEM_MIGRATION_ID,
    CONNECTOR_ECOSYSTEM_SQL,
    CONNECTOR_INVOCATIONS_MIGRATION_ID,
    CONNECTOR_INVOCATIONS_SQL,
    CONVERSATION_COMPACTIONS_MIGRATION_ID,
    CONVERSATION_COMPACTIONS_SQL,
    CONVERSATION_FTS_MIGRATION_ID,
    CONVERSATION_FTS_SQL,
    CREDENTIAL_SECURITY_MIGRATION_ID,
    CREDENTIAL_SECURITY_SQL,
    CRITICAL_APPROVAL_LIFECYCLE_MIGRATION_ID,
    CRITICAL_APPROVAL_LIFECYCLE_SQL,
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
    LEGACY_ACCOUNT_BOOTSTRAP_ROLES_MIGRATION_ID,
    LOCK_SCREEN_MIGRATION_ID,
    LOCK_SCREEN_SQL,
    MACHINE_ACTION_ATTRIBUTION_MIGRATION_ID,
    MACHINE_ACTION_ATTRIBUTION_SQL,
    MACHINE_ACTION_IDENTITY_SNAPSHOT_MIGRATION_ID,
    MACHINE_ACTION_IDENTITY_SNAPSHOT_SQL,
    MACHINE_IDENTITIES_MIGRATION_ID,
    MACHINE_IDENTITIES_SQL,
    MCP_CONTAINMENT_MIGRATION_ID,
    MCP_CONTAINMENT_SQL,
    MCP_MONITORING_MIGRATION_ID,
    MCP_MONITORING_SQL,
    MCP_REMOTE_ENDPOINT_MIGRATION_ID,
    MCP_REMOTE_ENDPOINT_SQL,
    MCP_SERVER_RUNTIME_MIGRATION_ID,
    MCP_SERVER_RUNTIME_SQL,
    MCP_SERVERS_MIGRATION_ID,
    MCP_SERVERS_SQL,
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
    MEMORY_ENTITY_GRAPH_MIGRATION_ID,
    MEMORY_ENTITY_GRAPH_SQL,
    MEMORY_EVALUATION_CONTEXT_MIGRATION_ID,
    MEMORY_EVALUATION_CONTEXT_SQL,
    MEMORY_FTS_MIGRATION_ID,
    MEMORY_FTS_SQL,
    MEMORY_JOBS_MIGRATION_ID,
    MEMORY_JOBS_SQL,
    MEMORY_LIFECYCLE_AUDIT_IMMUTABILITY_MIGRATION_ID,
    MEMORY_LIFECYCLE_AUDIT_IMMUTABILITY_SQL,
    MEMORY_PROJECTIONS_MIGRATION_ID,
    MEMORY_PROJECTIONS_SQL,
    MEMORY_PURGE_MIGRATION_ID,
    MEMORY_PURGE_SQL,
    MEMORY_RELATIONSHIP_REVIEW_MIGRATION_ID,
    MEMORY_RELATIONSHIP_REVIEW_SQL,
    MEMORY_RETRIEVAL_AUTHORITY_MIGRATION_ID,
    MEMORY_RETRIEVAL_AUTHORITY_SQL,
    MEMORY_SQLCIPHER_FTS_MIGRATION_ID,
    MEMORY_SQLCIPHER_FTS_SQL,
    MEMORY_TEMPORAL_EVALUATION_MIGRATION_ID,
    MEMORY_TEMPORAL_EVALUATION_SQL,
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
    THREAT_MODEL_ACKS_MIGRATION_ID,
    THREAT_MODEL_ACKS_SQL,
    TURN_CONTROLS_MIGRATION_ID,
    TURN_CONTROLS_SQL,
    TURN_SOURCES_MIGRATION_ID,
    TURN_SOURCES_SQL,
    WEB_BLOCKLIST_MIGRATION_ID,
    WEB_BLOCKLIST_SQL,
)
from raiker.storage.sqlcipher_probe import MemorySecurityProbeResult, probe_memory_security

# SQLCipher performs its key derivation when a connection is opened. API routes
# construct short-lived SQLiteStore objects, so opening in ``connect`` made a
# burst of cheap reads pay that KDF once per request. Keep one keyed connection
# per workspace and worker thread for the host lifetime instead. The connection
# is never shared for query work across threads; ``check_same_thread=False`` only
# allows shutdown/invalidation to close every worker's handle from one place.
#
# BUG-50 — the cache is bounded and evicted least-recently-used. Without a bound
# it grew with the number of *distinct* workspaces a process ever touches: a test
# session opening temporary workspaces, or a long-lived host serving many
# instances, kept every handle until exit and eventually ran out of file
# descriptors.
#
# A thread only ever closes a handle it owns itself, or one whose owning thread
# has exited. ``connect`` has no release point, so a cached connection may be
# mid-query in the thread that owns it, and closing another live worker's handle
# would be a use-after-close. Reaping an exited thread's handles is what keeps the
# bound from drifting upwards with thread churn.
#
# Self-eviction alone would bound the cache only *per thread*, so a request
# threadpool would multiply the bound by its worker count. The allowance a thread
# gives itself is therefore the per-thread limit **or** the process ceiling shared
# between the threads currently holding connections, whichever is smaller — a real
# process-wide bound that still never touches another thread's handle.
#
# BUG-86 — the ceiling used to be expressed as *worker-threads-worth* of the
# per-thread limit (eight of them), so the real bound was the per-thread limit
# multiplied by a thread count the store does not control. Every keyed connection
# holds SQLCipher key material, and on a platform that locks those pages the
# population is spent against a locked-memory allowance measured in a few
# megabytes. The ceiling is therefore an absolute number of key-bearing
# connections: what the process may hold, whatever the server's threadpool does.
_CONNECTION_CACHE_LIMIT_ENV = "RAIKER_SQLITE_CONNECTION_CACHE_LIMIT"
_DEFAULT_CONNECTION_CACHE_LIMIT = 8
_CONNECTION_CACHE_CEILING_ENV = "RAIKER_SQLITE_CONNECTION_CACHE_CEILING"
_DEFAULT_CONNECTION_CACHE_CEILING = 16
_CONNECTIONS: OrderedDict[tuple[Path, int], sqlite3.Connection] = OrderedDict()
_CONNECTIONS_LOCK = threading.RLock()
# Schema/FTS bootstrap uses multiple statements and must not race another store
# instance in this process. SQLite's busy timeout cannot resolve two deferred
# transactions that both try to upgrade to writers.
_BOOTSTRAP_LOCK = threading.RLock()
_LOG = logging.getLogger(__name__)


class StoreUnavailableError(RuntimeError):
    """The encrypted store could not be opened. ``reason`` is a stable code.

    Raised instead of letting a platform-level failure — a locked-memory
    allowance the process cannot satisfy, most of all — surface as a bare
    ``MemoryError`` from inside a request handler. Callers turn it into a named
    condition the owner can act on rather than a generic failure.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail or reason


def connection_cache_limit() -> int:
    """How many keyed connections one worker thread may hold open at once."""
    raw = os.environ.get(_CONNECTION_CACHE_LIMIT_ENV, "").strip()
    if raw:
        with contextlib.suppress(ValueError):
            declared = int(raw)
            if declared > 0:
                return declared
    return _DEFAULT_CONNECTION_CACHE_LIMIT


def connection_cache_ceiling() -> int:
    """The most keyed connections this process will cache, across all threads.

    An absolute count, never a multiple of the thread count: it is what bounds
    the locked pages SQLCipher asks the platform for.
    """
    raw = os.environ.get(_CONNECTION_CACHE_CEILING_ENV, "").strip()
    declared = _DEFAULT_CONNECTION_CACHE_CEILING
    if raw:
        with contextlib.suppress(ValueError):
            parsed = int(raw)
            if parsed > 0:
                declared = parsed
    # A ceiling under the per-thread limit would be self-contradictory; the
    # per-thread limit is what one thread may hold, so it is the floor here.
    return max(connection_cache_limit(), declared)


def cached_connection_count() -> int:
    """Cached connections held by this process, across every worker thread."""
    with _CONNECTIONS_LOCK:
        return len(_CONNECTIONS)


# ── SQLCipher memory security (BUG-86, BUG-46) ───────────────────────────────
#
# SQLCipher can lock the pages that hold key material so they are never paged to
# disk. Locking draws on a per-process allowance the operating system sets, and
# that allowance is small by default — 8 MB on the Linux host where BUG-86 was
# reproduced, a working-set quota on Windows. When it is spent, opening a keyed
# connection fails with ``MemoryError`` and *every* request fails with it,
# because authentication opens the store.
#
# The decision, stated rather than left implicit: **the pragma is set on every
# connection, and it is off unless the owner asks for it.** Two facts decide it,
# and both were measured rather than assumed:
#
# * **Cost.** Memory security makes SQLCipher lock and wipe its buffers around
#   every operation. Opening a workspace and running two hundred reads takes
#   0.17 s with it off and 1.14 s with it on — about seven times. SQLCipher
#   itself defaults it off in 4.x for this reason.
# * **Failure mode.** When the platform's locked-memory allowance runs out the
#   failure is not degraded performance, it is `MemoryError` on *every* request,
#   because authentication opens the store. That is BUG-86, and BUG-46 before it.
#
# So Raiker does not lock key pages by default, and says so rather than leaving
# it to whatever SQLCipher was built with: `GET /api/health` reports the setting,
# the reason, and the allowance the platform would have given. An owner who wants
# the stronger posture sets ``RAIKER_SQLCIPHER_MEMORY_SECURITY=on``, and because
# that is their decision it is honoured exactly — a refused lock then fails
# **closed**, by name, instead of surfacing as a bare ``MemoryError``.
_MEMORY_SECURITY_ENV = "RAIKER_SQLCIPHER_MEMORY_SECURITY"
_MEMORY_SECURITY_LOCK = threading.Lock()
_MEMORY_SECURITY: tuple[bool, str] | None = None
_MEMORY_SECURITY_PROBE: MemorySecurityProbeResult | None = None
_MEMORY_SECURITY_MODE = "auto"


def memlock_allowance_bytes() -> int | None:
    """The process's locked-memory allowance, or ``None`` where unreadable.

    Reported so an owner deciding whether to turn memory security on can see
    what the platform would actually give them. ``-1`` from ``getrlimit`` means
    unlimited. Windows reports nothing here, which is itself worth showing.
    """
    try:
        import resource  # noqa: PLC0415 - POSIX only, imported where it is used
    except ImportError:
        return None
    getrlimit = getattr(resource, "getrlimit", None)
    memlock = getattr(resource, "RLIMIT_MEMLOCK", None)
    if not callable(getrlimit) or memlock is None:
        return None
    try:
        soft, _hard = getrlimit(memlock)
    except (OSError, ValueError):
        return None
    if soft < 0:
        return -1 if soft == -1 else None
    return int(soft)


def resolve_memory_security(
    workspace_root: str | Path | None = None, *, refresh: bool = False
) -> tuple[bool, str]:
    """``(enabled, reason)`` for ``PRAGMA cipher_memory_security``.

    Off unless the owner asks for it, for the two reasons in the note above:
    locking costs roughly seven times on every store operation, and when the
    platform's allowance runs out the failure is a total lockout rather than
    slow work. Resolved once per process and reported verbatim on the health
    endpoint. ``refresh`` re-resolves it, which only tests need.
    """
    global _MEMORY_SECURITY, _MEMORY_SECURITY_MODE, _MEMORY_SECURITY_PROBE
    with _MEMORY_SECURITY_LOCK:
        if _MEMORY_SECURITY is not None and not refresh:
            return _MEMORY_SECURITY
        declared = os.environ.get(_MEMORY_SECURITY_ENV, "").strip().casefold()
        if declared in {"off", "0", "false", "no"}:
            _MEMORY_SECURITY_MODE = "off"
            _MEMORY_SECURITY_PROBE = None
            resolved = (False, "requested_off")
        else:
            _MEMORY_SECURITY_MODE = "on" if declared in {"on", "1", "true", "yes"} else "auto"
            probe_root = Path(workspace_root or Path.cwd())
            _MEMORY_SECURITY_PROBE = probe_memory_security(probe_root)
            if _MEMORY_SECURITY_PROBE.supported:
                resolved = (True, "requested_on" if _MEMORY_SECURITY_MODE == "on" else "auto_probe_supported")
            elif _MEMORY_SECURITY_MODE == "on":
                resolved = (
                    False,
                    f"required_but_unavailable_{_MEMORY_SECURITY_PROBE.reason_code}",
                )
            else:
                resolved = (False, f"auto_probe_{_MEMORY_SECURITY_PROBE.reason_code}")
        _MEMORY_SECURITY = resolved
        if not resolved[0]:
            # Recorded, not silent: running without locked key pages is a real
            # posture, and the owner is entitled to see which one they are on.
            _LOG.info(
                "SQLCipher memory security is off (%s); workspace key pages are "
                "not locked into RAM. Set %s=on to change that.",
                resolved[1],
                _MEMORY_SECURITY_ENV,
            )
        return resolved


def memory_security_posture(workspace_root: str | Path | None = None) -> dict[str, Any]:
    """What the health endpoint and the security posture page both read."""
    enabled, reason = resolve_memory_security(workspace_root)
    probe = _MEMORY_SECURITY_PROBE
    return {
        "cipher_memory_security": "on" if enabled else "off",
        # Deliberately not "reason": the store's own reason travels beside this
        # one on the health view, and two keys of the same name would let the
        # posture overwrite the failure — the kind of quiet contradiction this
        # bug is about.
        "memory_security_reason": reason,
        "memory_security_mode": _MEMORY_SECURITY_MODE,
        "memory_security_probe": (
            "not_run" if probe is None else "supported" if probe.supported else "failed"
        ),
        "memory_security_checked_at": probe.checked_at if probe is not None else None,
        "sqlcipher_version": probe.sqlcipher_version if probe is not None else None,
        # -1 means unlimited; null means the platform would not say.
        "memlock_allowance_bytes": memlock_allowance_bytes(),
        "connection_ceiling": connection_cache_ceiling(),
    }


def store_health(workspace_root: str | Path) -> dict[str, Any]:
    """Whether the encrypted store can actually be opened and read, right now.

    BUG-86 — the health probe used to answer "ok" without touching the store,
    so the lock screen could report the runtime operational in the same breath
    as refusing every sign-in. This is the one probe both statements read.
    """
    posture = memory_security_posture(workspace_root)
    try:
        SQLiteStore(workspace_root).connect().execute("SELECT 1")
    except StoreUnavailableError as exc:
        return {"store": "unavailable", "reason": exc.reason, "detail": exc.detail, **posture}
    except MemoryError:
        return {
            "store": "unavailable",
            "reason": "store_memory_lock_unavailable",
            "detail": "This machine would not give SQLCipher the memory it needs to "
            "open the workspace database.",
            **posture,
        }
    except Exception as exc:  # noqa: BLE001 - any open failure is one condition here
        return {
            "store": "unavailable",
            "reason": "store_open_failed",
            "detail": type(exc).__name__,
            **posture,
        }
    return {"store": "ok", "reason": "", "detail": "", **posture}


def _evictable_locked(owner: int) -> list[sqlite3.Connection]:
    """Handles this thread may close: its own stalest, plus any dead thread's.

    Called with ``_CONNECTIONS_LOCK`` held; the caller closes what it returns
    outside the lock, exactly as invalidation does.
    """
    live = {thread.ident for thread in threading.enumerate() if thread.ident is not None}
    evicted: list[sqlite3.Connection] = []
    orphans = [key for key in _CONNECTIONS if key[1] != owner and key[1] not in live]
    for key in orphans:
        evicted.append(_CONNECTIONS.pop(key))
    owners = {key[1] for key in _CONNECTIONS} | {owner}
    allowance = max(1, min(connection_cache_limit(), connection_cache_ceiling() // len(owners)))
    # ``_CONNECTIONS`` is ordered least-recently-used first, so walking it in
    # order drops this thread's stalest workspaces before its warm ones.
    mine = [key for key in _CONNECTIONS if key[1] == owner]
    for key in mine[: max(len(mine) - allowance, 0)]:
        evicted.append(_CONNECTIONS.pop(key))
    return evicted


def _releasable_locked(owner: int) -> list[sqlite3.Connection]:
    """Every handle this thread is allowed to close, under memory pressure.

    Its own — it holds none of them mid-query, since it is here — plus any
    belonging to a thread that has exited. Another live worker's handle is
    still never touched: closing one would be a use-after-close in that worker.
    Called with ``_CONNECTIONS_LOCK`` held.
    """
    live = {thread.ident for thread in threading.enumerate() if thread.ident is not None}
    doomed = [key for key in _CONNECTIONS if key[1] == owner or key[1] not in live]
    return [_CONNECTIONS.pop(key) for key in doomed]


def invalidate_workspace_connections(workspace_root: str | Path) -> None:
    """Close every cached SQLCipher connection for one workspace."""
    root = Path(workspace_root).resolve()
    with _CONNECTIONS_LOCK:
        doomed = [key for key in _CONNECTIONS if key[0] == root]
        connections = [_CONNECTIONS.pop(key) for key in doomed]
    for connection in connections:
        with contextlib.suppress(Exception):
            connection.close()


def close_cached_connections() -> None:
    """Close all keyed connections during process shutdown."""
    with _CONNECTIONS_LOCK:
        connections = list(_CONNECTIONS.values())
        _CONNECTIONS.clear()
    for connection in connections:
        with contextlib.suppress(Exception):
            connection.close()


atexit.register(close_cached_connections)


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
        with _BOOTSTRAP_LOCK:
            self.bootstrap()

    def _open_keyed(self) -> sqlite3.Connection:
        """Open one keyed connection under the resolved memory-security policy."""
        connection = sqlite3.connect(str(self.db_path), timeout=5.0, check_same_thread=False)
        try:
            memory_security, reason = resolve_memory_security(self.paths.workspace_root)
            if reason.startswith("required_but_unavailable_"):
                raise StoreUnavailableError(
                    "store_memory_lock_unavailable",
                    "This machine could not prove that SQLCipher can lock key-bearing "
                    "memory pages while RAIKER_SQLCIPHER_MEMORY_SECURITY=on is required.",
                )
            # Set before the key: the pragma governs how the key material about
            # to be derived is held, so afterwards would be too late.
            connection.execute(
                f"PRAGMA cipher_memory_security = {'ON' if memory_security else 'OFF'}"
            )
            key_hex = hashlib.sha256(ensure_app_key(self.paths.workspace_root)).hexdigest()
            connection.execute(f"PRAGMA key = \"x'{key_hex}'\"")
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
        except BaseException:
            with contextlib.suppress(Exception):
                connection.close()
            raise
        return connection

    def connect(self) -> sqlite3.Connection:
        owner = threading.get_ident()
        cache_key = (self.paths.workspace_root, owner)
        with _CONNECTIONS_LOCK:
            connection = _CONNECTIONS.get(cache_key)
            if connection is not None:
                try:
                    connection.execute("SELECT 1")
                    _CONNECTIONS.move_to_end(cache_key)
                    return connection
                except (sqlite3.Error, MemoryError):
                    # A cached handle whose key pages the platform has taken
                    # back answers this probe with MemoryError, not sqlite3.
                    # Either way it is unusable and is replaced, not returned.
                    _CONNECTIONS.pop(cache_key, None)
                    with contextlib.suppress(Exception):
                        connection.close()
            try:
                connection = self._open_keyed()
            except MemoryError as exc:
                # The platform refused the locked pages SQLCipher asked for. Give
                # back everything this thread may release and try once more; if
                # the policy was Raiker's own choice rather than the owner's,
                # fall back to running without memory security and record it.
                connection = self._reopen_after_memory_error(exc)
            # A fresh key, so this appends: the newest connection is the most
            # recently used one and the last thing eviction would reach for.
            _CONNECTIONS[cache_key] = connection
            evicted = _evictable_locked(owner)
        for stale in evicted:
            with contextlib.suppress(Exception):
                stale.close()
        return connection

    def _reopen_after_memory_error(self, error: MemoryError) -> sqlite3.Connection:
        """Recover a keyed connection after a memory refusal, or fail named.

        Give back every handle this thread may release — the population of
        key-bearing connections is the thing most likely to have exhausted the
        allowance — and try once more. If it still refuses, the condition is
        named rather than left as a bare ``MemoryError`` escaping a request
        handler. Called with ``_CONNECTIONS_LOCK`` held.
        """
        for stale in _releasable_locked(threading.get_ident()):
            with contextlib.suppress(Exception):
                stale.close()
        with contextlib.suppress(MemoryError, sqlite3.Error):
            return self._open_keyed()
        enabled, _reason = resolve_memory_security(self.paths.workspace_root)
        detail = (
            "This machine would not lock the memory pages SQLCipher holds the "
            "workspace key in. Memory security is on because "
            f"{_MEMORY_SECURITY_ENV}=on was set; unset it to run without locked "
            "key pages."
            if enabled
            else "This machine would not give SQLCipher the memory it needs to "
            "open the workspace database."
        )
        raise StoreUnavailableError("store_memory_lock_unavailable", detail) from error

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
            with contextlib.suppress(sqlite3.OperationalError):
                connection.execute("ALTER TABLE projects ADD COLUMN owner_user_id TEXT REFERENCES users(user_id)")
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
            self._apply_migration(
                BRAIN_PREFERENCES_MIGRATION_ID, BRAIN_PREFERENCES_SQL, connection
            )
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
            self._apply_migration(
                MEMORY_CONTROLS_MIGRATION_ID, MEMORY_CONTROLS_SQL, connection
            )
            self._apply_migration(
                SESSION_TAGS_MIGRATION_ID, SESSION_TAGS_SQL, connection
            )
            self._apply_migration(
                SESSION_ARCHIVE_MIGRATION_ID, SESSION_ARCHIVE_SQL, connection
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
                ((hashlib.sha256(str(row["text"]).encode()).hexdigest(), row["memory_id"]) for row in rows),
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
            self._apply_migration(
                MCP_CONTAINMENT_MIGRATION_ID, MCP_CONTAINMENT_SQL, connection
            )
            self._apply_migration(
                CREDENTIAL_SECURITY_MIGRATION_ID, CREDENTIAL_SECURITY_SQL, connection
            )
            self._apply_migration(
                CHECKPOINT_CAPTURE_MANIFEST_MIGRATION_ID,
                CHECKPOINT_CAPTURE_MANIFEST_SQL,
                connection,
            )
            self._apply_migration(
                STANDING_GRANTS_MIGRATION_ID, STANDING_GRANTS_SQL, connection
            )
            self._apply_migration(
                CRITICAL_APPROVAL_LIFECYCLE_MIGRATION_ID,
                CRITICAL_APPROVAL_LIFECYCLE_SQL,
                connection,
            )
            self._apply_migration(
                SUBAGENT_BUDGETS_MIGRATION_ID, SUBAGENT_BUDGETS_SQL, connection
            )
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
            self._apply_migration(
                SUSPENDED_TURNS_MIGRATION_ID, SUSPENDED_TURNS_SQL, connection
            )
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
            self._apply_migration(
                CONFIGURED_MODELS_MIGRATION_ID, CONFIGURED_MODELS_SQL, connection
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
            self._apply_migration(
                TASK_ATTACHMENTS_MIGRATION_ID, TASK_ATTACHMENTS_SQL, connection
            )
            self._apply_migration(SKILLS_MIGRATION_ID, SKILLS_SQL, connection)
            self._apply_migration(AGENT_PLANS_MIGRATION_ID, AGENT_PLANS_SQL, connection)
            self._apply_migration(TURN_CONTROLS_MIGRATION_ID, TURN_CONTROLS_SQL, connection)
            self._apply_migration(TURN_SOURCES_MIGRATION_ID, TURN_SOURCES_SQL, connection)
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
                CONVERSATION_FTS_SQL,
                connection,
            )
            self._apply_migration(WEB_BLOCKLIST_MIGRATION_ID, WEB_BLOCKLIST_SQL, connection)
            self._apply_migration(
                GIT_CREDENTIAL_GRANT_MIGRATION_ID, GIT_CREDENTIAL_GRANT_SQL, connection
            )
            self._rebuild_memory_fts(connection)
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

    def _migrate_plaintext_database(self) -> None:
        """Convert a legacy stdlib-SQLite file before SQLCipher opens it."""
        if not self.db_path.exists() or not self.db_path.read_bytes()[:16].startswith(b"SQLite format 3"):
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
                    # disposable projection from approved memory after importing.
                    dump = "\n".join(
                        line for line in source.iterdump() if "approved_memory_fts" not in line
                    ).replace("USING fts5(", "USING fts4(")
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
    def _skip_existing_add_columns(cls, connection: sqlite3.Connection, sql: str) -> str:
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
                    for row in connection.execute(f'PRAGMA table_info("{match["table"]}")').fetchall()
                }
                if match["column"] in columns:
                    continue
            kept.append(statement)
        return ";".join(kept)

    def _apply_migration(self, migration_id: str, sql: str, connection: sqlite3.Connection) -> None:
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

    def _backfill_legacy_account_bootstrap_roles(
        self, connection: sqlite3.Connection
    ) -> None:
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        try:
            if connection.execute(
                "SELECT 1 FROM migrations WHERE migration_id = ?",
                (LEGACY_ACCOUNT_BOOTSTRAP_ROLES_MIGRATION_ID,),
            ).fetchone() is not None:
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
                missing_role_ids = [role_id for role_id in required_role_ids if role_id not in role_ids]
                if missing_role_ids:
                    connection.execute(
                        "UPDATE principals SET role_ids = ? WHERE principal_id = ?",
                        (json.dumps([*role_ids, *missing_role_ids], sort_keys=True), principal["principal_id"]),
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

    def _migrate_legacy_controls_to_original_owner(self, connection: sqlite3.Connection) -> None:
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

    def _backfill_legacy_account_data_owner(self, connection: sqlite3.Connection) -> None:
        principal_id = self._original_owner_from_connection(connection)
        if principal_id is None:
            return
        principal = connection.execute(
            "SELECT delegated_by_user_id FROM principals WHERE principal_id = ?", (principal_id,)
        ).fetchone()
        user_id = str(principal["delegated_by_user_id"] or principal_id.removeprefix("principal_")) if principal else ""
        if not user_id or connection.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone() is None:
            return
        connection.execute("UPDATE sessions SET user_id = ? WHERE user_id IS NULL", (user_id,))
        connection.execute("UPDATE projects SET owner_user_id = ? WHERE owner_user_id IS NULL", (user_id,))
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
        owner = SQLiteStore._original_owner_from_connection(connection)
        if owner is not None:
            connection.execute(
                "UPDATE memory_candidates SET owner_principal_id = ? WHERE owner_principal_id IS NULL",
                (owner,),
            )

    @staticmethod
    def _original_owner_from_connection(connection: sqlite3.Connection) -> str | None:
        """The live principal that owns this instance's unattributed data.

        The guard row is the authority: it names the instance's sole account and
        recovery repoints it, so it survives an owner replacement. The role scan
        is the fallback for databases predating the guard, and only ever
        considers *active* principals — recovery deactivates the old owner but
        leaves its ``rl_owner`` role and its earlier ``created_at``, so an
        unfiltered scan would keep resolving to the dead principal and file all
        new data against it.
        """
        # The backfills call this during bootstrap, before the migration that
        # creates the guard has run, so its absence is expected here.
        guard_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'instance_account_guard'"
        ).fetchone() is not None
        row = connection.execute(
            "SELECT g.principal_id FROM instance_account_guard g "
            "JOIN principals p ON p.principal_id = g.principal_id "
            "WHERE g.singleton = 1 AND p.is_active = 1"
        ).fetchone() if guard_exists else None
        if row is None:
            row = connection.execute(
                "SELECT principal_id FROM principals WHERE role_ids LIKE '%rl_owner%' "
                "AND is_active = 1 ORDER BY created_at, principal_id LIMIT 1"
            ).fetchone()
        if row is None:
            row = connection.execute(
                "SELECT c.principal_id FROM account_credentials c "
                "JOIN principals p ON p.principal_id = c.principal_id "
                "WHERE p.is_active = 1 ORDER BY c.created_at, c.principal_id LIMIT 1"
            ).fetchone()
        return str(row["principal_id"]) if row is not None else None

    def assign_legacy_data_to_original_owner(self) -> None:
        with self.connect() as connection:
            self._backfill_legacy_account_data_owner(connection)
            self._backfill_owned_context_data(connection)
            self._backfill_owned_memory_metadata(connection)

    def list_brain_sources(self, owner_principal_id: str) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT path FROM brain_sources WHERE owner_principal_id = ? ORDER BY created_at, path",
                (owner_principal_id,),
            ).fetchall()
        return [str(row["path"]) for row in rows]

    def add_brain_source(self, owner_principal_id: str, path: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO brain_sources (owner_principal_id, path, created_at) VALUES (?, ?, ?)",
                (owner_principal_id, path, utc_now()),
            )

    # ── Knowledge Map folder grants ─────────────────────────────────────
    # A grant is the owner naming a folder on this machine that the Knowledge
    # Map may read *where it is*. It is stored so it can be shown back and
    # revoked; nothing is copied into the workspace by recording one.

    def list_brain_source_grants(self, owner_principal_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT root_id, path, label, created_at FROM brain_source_grants "
                "WHERE owner_principal_id = ? ORDER BY created_at, path",
                (owner_principal_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_brain_source_grant(
        self, owner_principal_id: str, root_id: str, path: str, label: str
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO brain_source_grants "
                "(owner_principal_id, root_id, path, label, created_at) VALUES (?, ?, ?, ?, ?)",
                (owner_principal_id, root_id, path, label, utc_now()),
            )

    def remove_brain_source_grant(self, owner_principal_id: str, root_id: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM brain_source_grants WHERE owner_principal_id = ? AND root_id = ?",
                (owner_principal_id, root_id),
            )
            # Revoking the grant revokes what was indexed under it: leaving the
            # sources behind would keep reading a folder the owner just said
            # Raiker may not read.
            connection.execute(
                "DELETE FROM brain_sources WHERE owner_principal_id = ? "
                "AND (path = ? OR path LIKE ?)",
                (owner_principal_id, root_id, f"{root_id}/%"),
            )

    def load_brain_preferences(self, owner_principal_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT settings_json FROM brain_preferences WHERE owner_principal_id = ?",
                (owner_principal_id,),
            ).fetchone()
        if row is None:
            return {}
        try:
            value = json.loads(row["settings_json"])
        except (TypeError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}

    def save_brain_preferences(
        self, owner_principal_id: str, settings: dict[str, Any]
    ) -> str:
        updated_at = utc_now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO brain_preferences (owner_principal_id, settings_json, updated_at)
                VALUES (?, ?, ?) ON CONFLICT(owner_principal_id) DO UPDATE SET
                settings_json = excluded.settings_json, updated_at = excluded.updated_at""",
                (owner_principal_id, json.dumps(settings, sort_keys=True), updated_at),
            )
        return updated_at

    def _backfill_legacy_brain_sources(self, connection: sqlite3.Connection) -> None:
        """Migrate the former shared source list to the original account once."""
        owner = self._original_owner_from_connection(connection)
        legacy_path = self.paths.workspace_root / ".raiker" / "brain-sources.json"
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

    def remove_brain_source(self, owner_principal_id: str, path: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM brain_sources WHERE owner_principal_id = ? AND path = ?",
                (owner_principal_id, path),
            )

    # ── Code workspace repositories ─────────────────────────────────────
    # Account-scoped references the Build workspace points a coding chat at: a
    # workspace-contained local folder, or a `owner/repo` GitHub coordinate read
    # through the governed `github_read` tool. A row is a reference only — it
    # holds no credential and grants no capability.

    def list_code_repos(self, owner_principal_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM code_repos WHERE owner_principal_id = ? ORDER BY created_at, repo_id",
                (owner_principal_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def load_code_repo(self, owner_principal_id: str, repo_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM code_repos WHERE owner_principal_id = ? AND repo_id = ?",
                (owner_principal_id, repo_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def insert_code_repo(
        self,
        *,
        repo_id: str,
        owner_principal_id: str,
        kind: str,
        label: str,
        local_subpath: str | None = None,
        github_owner: str | None = None,
        github_repo: str | None = None,
        branch: str | None = None,
    ) -> bool:
        """Store one repository reference, or return False if it already exists.

        The unique indexes make "already connected" a storage-layer fact, so the
        duplicate is reported as a value rather than surfacing a driver exception
        to the service layer.
        """
        with self.connect() as connection:
            return bool(
                connection.execute(
                    """INSERT OR IGNORE INTO code_repos
                       (repo_id, owner_principal_id, kind, label, local_subpath,
                        github_owner, github_repo, branch, selected, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                    (
                        repo_id,
                        owner_principal_id,
                        kind,
                        label,
                        local_subpath,
                        github_owner,
                        github_repo,
                        branch,
                        utc_now(),
                    ),
                ).rowcount
            )

    def delete_code_repo(self, owner_principal_id: str, repo_id: str) -> bool:
        with self.connect() as connection:
            return bool(
                connection.execute(
                    "DELETE FROM code_repos WHERE owner_principal_id = ? AND repo_id = ?",
                    (owner_principal_id, repo_id),
                ).rowcount
            )

    def select_code_repo(self, owner_principal_id: str, repo_id: str | None) -> None:
        """Point the account's Build workspace at one repository, or none."""
        with self.connect() as connection:
            connection.execute(
                "UPDATE code_repos SET selected = 0 WHERE owner_principal_id = ?",
                (owner_principal_id,),
            )
            if repo_id is not None:
                connection.execute(
                    "UPDATE code_repos SET selected = 1 WHERE owner_principal_id = ? AND repo_id = ?",
                    (owner_principal_id, repo_id),
                )

    # ── Repository code map (B9) ────────────────────────────────────────────
    # A derived projection of files the agent may already read: what each file
    # is and what it declares, keyed by owner and by the workspace-relative
    # repository path the turn works in. It is storage for *coordinates* — the
    # rows say where to look, and looking still goes through `read_file`, the
    # workspace containment check, and the policy engine.

    def load_code_map_index(
        self, owner_principal_id: str, repo_path: str
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM code_map_indexes WHERE owner_principal_id = ? AND repo_path = ?",
                (owner_principal_id, repo_path),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_code_map_indexes(self, owner_principal_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM code_map_indexes WHERE owner_principal_id = ? ORDER BY repo_path",
                (owner_principal_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_code_map_index(
        self,
        *,
        owner_principal_id: str,
        repo_path: str,
        repo_id: str,
        label: str,
        status: str,
        reason_code: str,
        file_count: int,
        symbol_count: int,
        edge_count: int,
        skipped: str,
        limits_hit: str,
        languages: str,
        schema_version: str,
    ) -> None:
        """Write the index's own state row, preserving the first ``built_at``."""
        now = utc_now()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT built_at FROM code_map_indexes WHERE owner_principal_id = ? AND repo_path = ?",
                (owner_principal_id, repo_path),
            ).fetchone()
            built_at = str(existing["built_at"]) if existing is not None else now
            connection.execute(
                """INSERT INTO code_map_indexes
                   (owner_principal_id, repo_path, repo_id, label, status, reason_code,
                    file_count, symbol_count, edge_count, skipped, limits_hit, languages,
                    schema_version, built_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(owner_principal_id, repo_path) DO UPDATE SET
                     repo_id=excluded.repo_id, label=excluded.label, status=excluded.status,
                     reason_code=excluded.reason_code, file_count=excluded.file_count,
                     symbol_count=excluded.symbol_count, edge_count=excluded.edge_count,
                     skipped=excluded.skipped, limits_hit=excluded.limits_hit,
                     languages=excluded.languages, schema_version=excluded.schema_version,
                     updated_at=excluded.updated_at""",
                (
                    owner_principal_id, repo_path, repo_id, label, status, reason_code,
                    file_count, symbol_count, edge_count, skipped, limits_hit, languages,
                    schema_version, built_at, now,
                ),
            )

    def replace_code_map(
        self,
        *,
        owner_principal_id: str,
        repo_path: str,
        files: list[tuple[Any, ...]],
        symbols: list[tuple[Any, ...]],
        edges: list[tuple[Any, ...]],
    ) -> None:
        """Swap a repository's whole map in one transaction.

        All-or-nothing on purpose: a half-written map would answer some searches
        from the new scan and some from the old one, and nothing in the result
        would say which.
        """
        with self.connect() as connection:
            self._delete_code_map_rows(connection, owner_principal_id, repo_path)
            self._insert_code_map_rows(connection, owner_principal_id, repo_path, files, symbols, edges)

    def refresh_code_map_paths(
        self,
        *,
        owner_principal_id: str,
        repo_path: str,
        paths: list[str],
        files: list[tuple[Any, ...]],
        symbols: list[tuple[Any, ...]],
        edges: list[tuple[Any, ...]],
    ) -> None:
        """Replace the rows for exactly *paths*, in one transaction.

        A path in *paths* with no row in *files* was deleted or became
        unreadable, so its rows go and nothing replaces them.
        """
        if not paths:
            return
        with self.connect() as connection:
            for path in paths:
                connection.execute(
                    "DELETE FROM code_map_files WHERE owner_principal_id = ? AND repo_path = ? AND path = ?",
                    (owner_principal_id, repo_path, path),
                )
                connection.execute(
                    "DELETE FROM code_map_symbols WHERE owner_principal_id = ? AND repo_path = ? AND path = ?",
                    (owner_principal_id, repo_path, path),
                )
                connection.execute(
                    "DELETE FROM code_map_edges WHERE owner_principal_id = ? AND repo_path = ? AND from_path = ?",
                    (owner_principal_id, repo_path, path),
                )
            self._insert_code_map_rows(connection, owner_principal_id, repo_path, files, symbols, edges)

    def delete_code_map(self, owner_principal_id: str, repo_path: str) -> None:
        with self.connect() as connection:
            self._delete_code_map_rows(connection, owner_principal_id, repo_path)
            connection.execute(
                "DELETE FROM code_map_indexes WHERE owner_principal_id = ? AND repo_path = ?",
                (owner_principal_id, repo_path),
            )

    @staticmethod
    def _delete_code_map_rows(
        connection: sqlite3.Connection, owner_principal_id: str, repo_path: str
    ) -> None:
        for table in ("code_map_files", "code_map_symbols", "code_map_edges"):
            connection.execute(
                f"DELETE FROM {table} WHERE owner_principal_id = ? AND repo_path = ?",  # noqa: S608 — fixed table names
                (owner_principal_id, repo_path),
            )

    @staticmethod
    def _insert_code_map_rows(
        connection: sqlite3.Connection,
        owner_principal_id: str,
        repo_path: str,
        files: list[tuple[Any, ...]],
        symbols: list[tuple[Any, ...]],
        edges: list[tuple[Any, ...]],
    ) -> None:
        now = utc_now()
        connection.executemany(
            """INSERT OR REPLACE INTO code_map_files
               (owner_principal_id, repo_path, path, language, sha256, size_bytes,
                line_count, symbol_count, title, extractor, indexed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(owner_principal_id, repo_path, *row, now) for row in files],
        )
        connection.executemany(
            """INSERT INTO code_map_symbols
               (owner_principal_id, repo_path, path, kind, name, name_lower,
                qualified_name, line_start, line_end, parent, signature, doc)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(owner_principal_id, repo_path, *row) for row in symbols],
        )
        connection.executemany(
            """INSERT INTO code_map_edges
               (owner_principal_id, repo_path, from_path, relationship, target, line)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [(owner_principal_id, repo_path, *row) for row in edges],
        )

    def code_map_file_hashes(self, owner_principal_id: str, repo_path: str) -> dict[str, str]:
        """``path -> sha256`` for every indexed file, so a refresh can skip the unchanged."""
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT path, sha256 FROM code_map_files WHERE owner_principal_id = ? AND repo_path = ?",
                (owner_principal_id, repo_path),
            ).fetchall()
        return {str(row["path"]): str(row["sha256"]) for row in rows}

    def match_code_map_symbols(
        self, owner_principal_id: str, repo_path: str, term: str, *, limit: int = 200
    ) -> list[dict[str, Any]]:
        """Candidate symbol rows for one search term. Ranking happens above this."""
        like = f"%{term.lower()}%"
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM code_map_symbols
                   WHERE owner_principal_id = ? AND repo_path = ?
                     AND (name_lower LIKE ? OR LOWER(qualified_name) LIKE ? OR LOWER(doc) LIKE ?)
                   ORDER BY LENGTH(name), path, line_start
                   LIMIT ?""",
                (owner_principal_id, repo_path, like, like, like, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def match_code_map_files(
        self, owner_principal_id: str, repo_path: str, term: str, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        like = f"%{term.lower()}%"
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM code_map_files
                   WHERE owner_principal_id = ? AND repo_path = ?
                     AND (LOWER(path) LIKE ? OR LOWER(title) LIKE ?)
                   ORDER BY symbol_count DESC, path
                   LIMIT ?""",
                (owner_principal_id, repo_path, like, like, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_code_map_files(
        self, owner_principal_id: str, repo_path: str, *, limit: int = 5000
    ) -> list[dict[str, Any]]:
        """Every indexed file of one map, largest first.

        The set a reference scan is allowed to read: exactly the files the owner's
        indexing run already accepted, so a scan can never reach outside what the
        map itself covers.
        """
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT path, language, line_count, size_bytes FROM code_map_files
                   WHERE owner_principal_id = ? AND repo_path = ?
                   ORDER BY symbol_count DESC, path LIMIT ?""",
                (owner_principal_id, repo_path, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def code_map_declarations(
        self, owner_principal_id: str, repo_path: str, name: str, *, limit: int = 200
    ) -> list[dict[str, Any]]:
        """Exact-name declarations, so a reference scan can exclude them."""
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT path, name, kind, qualified_name, line_start, line_end, signature
                   FROM code_map_symbols
                   WHERE owner_principal_id = ? AND repo_path = ? AND name_lower = ?
                   ORDER BY path, line_start LIMIT ?""",
                (owner_principal_id, repo_path, name.lower(), limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def top_code_map_files(
        self, owner_principal_id: str, repo_path: str, *, limit: int = 12
    ) -> list[dict[str, Any]]:
        """The files with the most declarations — the overview when nothing matched."""
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM code_map_files
                   WHERE owner_principal_id = ? AND repo_path = ?
                   ORDER BY symbol_count DESC, path LIMIT ?""",
                (owner_principal_id, repo_path, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def code_map_totals(self, owner_principal_id: str, repo_path: str) -> dict[str, Any]:
        """File/symbol totals and a language histogram, aggregated in SQL.

        An incremental refresh has to re-derive the index's counts, and doing
        that by loading every file row would make a one-file write cost a scan of
        the whole table.
        """
        with self.connect() as connection:
            row = connection.execute(
                """SELECT COUNT(*) AS files, COALESCE(SUM(symbol_count), 0) AS symbols
                   FROM code_map_files WHERE owner_principal_id = ? AND repo_path = ?""",
                (owner_principal_id, repo_path),
            ).fetchone()
            languages = connection.execute(
                """SELECT language, COUNT(*) AS files FROM code_map_files
                   WHERE owner_principal_id = ? AND repo_path = ?
                   GROUP BY language""",
                (owner_principal_id, repo_path),
            ).fetchall()
        return {
            "file_count": int(row["files"]) if row else 0,
            "symbol_count": int(row["symbols"]) if row else 0,
            "languages": {str(item["language"]): int(item["files"]) for item in languages},
        }

    def code_map_file_symbols(
        self, owner_principal_id: str, repo_path: str, path: str, *, limit: int = 40
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM code_map_symbols
                   WHERE owner_principal_id = ? AND repo_path = ? AND path = ?
                   ORDER BY line_start LIMIT ?""",
                (owner_principal_id, repo_path, path, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def code_map_dependents(
        self, owner_principal_id: str, repo_path: str, target: str, *, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Files whose imports name *target* — the impact-analysis question."""
        like = f"%{target}%"
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT DISTINCT from_path, relationship, target FROM code_map_edges
                   WHERE owner_principal_id = ? AND repo_path = ? AND target LIKE ?
                   ORDER BY from_path LIMIT ?""",
                (owner_principal_id, repo_path, like, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def original_account_principal_id(self) -> str | None:
        """Return the sole destination for unattributed legacy data, if one exists."""
        with self.connect() as connection:
            return self._original_owner_from_connection(connection)

    @staticmethod
    def _principal_user_id_from_connection(
        connection: sqlite3.Connection, principal_id: str
    ) -> str | None:
        """Resolve a principal's user id on an existing connection.

        A CLI-bootstrapped owner is created with no ``delegated_by_user_id``, so
        the delegation column alone resolves to NULL and every user-keyed query
        silently matches nothing. The ``principal_<user_id>`` naming convention
        is the fallback, confirmed against ``users`` so an unrelated principal id
        cannot conjure a user that does not exist.
        """
        row = connection.execute(
            "SELECT delegated_by_user_id FROM principals WHERE principal_id = ?", (principal_id,)
        ).fetchone()
        if row is None:
            return None
        delegated = row["delegated_by_user_id"]
        if delegated:
            return str(delegated)
        inferred = principal_id.removeprefix("principal_")
        exists = connection.execute(
            "SELECT 1 FROM users WHERE user_id = ?", (inferred,)
        ).fetchone()
        return inferred if exists is not None else None

    def principal_user_id(self, principal_id: str) -> str | None:
        with self.connect() as connection:
            return self._principal_user_id_from_connection(connection, principal_id)

    def initialize_principal_controls(
        self, principal_id: str, *, connection: sqlite3.Connection | None = None
    ) -> None:
        """Seed only the original account from legacy global controls.

        Later accounts intentionally receive no rows: missing gate/model rows are
        interpreted as disabled/unselected by scoped callers.
        """
        owns_connection = connection is None
        if connection is None:
            connection = self.connect()
        try:
            owner = connection.execute(
                "SELECT principal_id FROM account_credentials ORDER BY created_at, principal_id LIMIT 1"
            ).fetchone()
            if owner is None:
                owner = connection.execute(
                    "SELECT principal_id FROM instance_account_guard WHERE singleton = 1"
                ).fetchone()
            if owner is None or str(owner["principal_id"]) != principal_id:
                return
            connection.execute(
                """INSERT OR IGNORE INTO principal_model_control
                SELECT ?, profile_id, model, reasoning_enabled, reasoning_effort, reasoning_mode,
                       reasoning_budget_tokens, updated_at
                FROM model_session_state WHERE session_id = 'terminal-local'""",
                (principal_id,),
            )
            connection.execute(
                """INSERT OR IGNORE INTO principal_model_fallback_sequence
                SELECT ?, profile_ids_json, updated_at FROM model_fallback_sequence
                WHERE session_id = 'terminal-local'""",
                (principal_id,),
            )
            connection.execute(
                """INSERT OR IGNORE INTO principal_model_advisor
                SELECT ?, profile_id, updated_at FROM model_advisor WHERE session_id = 'terminal-local'""",
                (principal_id,),
            )
            connection.execute(
                """INSERT OR IGNORE INTO principal_runtime_mode_state
                SELECT ?, mode_name, status, activated_by, activated_at, reason, updated_at
                FROM runtime_mode_state WHERE status = 'active' ORDER BY created_at DESC LIMIT 1""",
                (principal_id,),
            )
            connection.execute(
                """INSERT OR IGNORE INTO principal_capability_gate_state
                SELECT ?, capability, state, requested_by, requested_at, activated_by, activated_at,
                       reason, readiness_snapshot_json, created_at, updated_at
                FROM capability_gate_state""",
                (principal_id,),
            )
            connection.execute(
                """INSERT OR IGNORE INTO principal_capability_decision_mode
                SELECT ?, capability, decision_mode, set_by, set_at, reason, created_at, updated_at
                FROM capability_decision_mode""",
                (principal_id,),
            )
        finally:
            if owns_connection:
                connection.commit()
                connection.close()

    def claim_initial_account(self, principal_id: str) -> bool:
        """Atomically reserve this instance's sole local account."""
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO instance_account_guard (singleton, principal_id) VALUES (1, ?)",
                (principal_id,),
            )
            return cursor.rowcount == 1

    def create_initial_account_atomic(
        self, *, user: User, principal_id: str, role_ids: tuple[str, ...], max_runtime_mode: str,
        username: str | None = None, password_hash: str | None = None, hash_algo: str | None = None,
        fail_after: str | None = None,
    ) -> bool:
        """Create the sole account and all identity state in one transaction."""
        def checkpoint(phase: str) -> None:
            if fail_after == phase:
                raise RuntimeError(f"injected_failure:{phase}")

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                claimed = connection.execute(
                    "INSERT OR IGNORE INTO instance_account_guard (singleton, principal_id) VALUES (1, ?)",
                    (principal_id,),
                )
                if claimed.rowcount != 1:
                    connection.rollback()
                    return False
                checkpoint("guard")
                connection.execute(
                    "INSERT INTO users (user_id, display_name, email, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (user.user_id, user.display_name, user.email, int(user.is_active), user.created_at, user.updated_at),
                )
                checkpoint("user")
                connection.execute(
                    """INSERT INTO principals (principal_id, principal_type, display_name, delegated_by_user_id,
                    role_ids, domain_scopes, max_runtime_mode, created_at, is_active)
                    VALUES (?, 'human', ?, ?, ?, '[]', ?, ?, 1)""",
                    (principal_id, user.display_name, user.user_id, json.dumps(list(role_ids)), max_runtime_mode, user.created_at),
                )
                checkpoint("principal")
                connection.executemany(
                    "INSERT INTO user_role_assignments (assignment_id, user_id, role_id, granted_at, granted_by) VALUES (?, ?, ?, ?, ?)",
                    [(new_id("ura_"), user.user_id, role_id, user.created_at, "lock_screen_registration") for role_id in role_ids],
                )
                if username is not None and password_hash is not None and hash_algo is not None:
                    connection.execute(
                        "INSERT INTO account_credentials (principal_id, username, password_hash, hash_algo, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (principal_id, username, password_hash, hash_algo, user.created_at, user.updated_at),
                    )
                checkpoint("credential")
                self._backfill_legacy_account_data_owner(connection)
                self._backfill_owned_context_data(connection)
                self._backfill_owned_memory_metadata(connection)
                self.initialize_principal_controls(principal_id, connection=connection)
                checkpoint("migration")
                connection.commit()
                return True
            except Exception:
                connection.rollback()
                raise

    def recover_owner_atomic(
        self, *, user: User, principal_id: str, role_ids: tuple[str, ...],
        old_principal_ids: list[str], credential_owner_id: str | None, max_runtime_mode: str,
        fail_after: str | None = None,
    ) -> None:
        """Transfer the sole credential and guard to a replacement owner atomically.

        ``credential_owner_id`` is None when no owner has a credential row to
        move — a CLI-bootstrapped owner never has one, and a fresh workspace has
        no owner at all. The principal, guard, and data transfer still run; only
        the credential move is skipped.
        """
        def checkpoint(phase: str) -> None:
            if fail_after == phase:
                raise RuntimeError(f"injected_failure:{phase}")

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                if (
                    credential_owner_id is not None
                    and connection.execute("SELECT 1 FROM account_credentials WHERE principal_id = ?", (credential_owner_id,)).fetchone() is None
                ):
                    raise ValueError("credential_owner_not_found")
                connection.execute(
                    "INSERT INTO users (user_id, display_name, email, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (user.user_id, user.display_name, user.email, int(user.is_active), user.created_at, user.updated_at),
                )
                checkpoint("user")
                connection.execute(
                    """INSERT INTO principals (principal_id, principal_type, display_name, delegated_by_user_id,
                    role_ids, domain_scopes, max_runtime_mode, created_at, is_active)
                    VALUES (?, 'human', ?, ?, ?, '[]', ?, ?, 1)""",
                    (principal_id, user.display_name, user.user_id, json.dumps(list(role_ids)), max_runtime_mode, user.created_at),
                )
                connection.executemany(
                    "INSERT INTO user_role_assignments (assignment_id, user_id, role_id, granted_at, granted_by) VALUES (?, ?, ?, ?, ?)",
                    [(new_id("ura_"), user.user_id, role_id, user.created_at, "owner_recovery") for role_id in role_ids],
                )
                checkpoint("principal")
                old_users = connection.execute(
                    f"SELECT delegated_by_user_id FROM principals WHERE principal_id IN ({','.join('?' for _ in old_principal_ids)})",
                    old_principal_ids,
                ).fetchall() if old_principal_ids else []
                self._transfer_owner_scoped_data(
                    connection, old_principal_ids, [str(row["delegated_by_user_id"]) for row in old_users if row["delegated_by_user_id"]],
                    principal_id, user.user_id,
                )
                if credential_owner_id is not None:
                    connection.execute("UPDATE account_credentials SET principal_id = ? WHERE principal_id = ?", (principal_id, credential_owner_id))
                # The guard names this instance's sole account either way, and
                # is what the original-owner pointer resolves through.
                connection.execute(
                    "INSERT INTO instance_account_guard (singleton, principal_id) VALUES (1, ?) "
                    "ON CONFLICT(singleton) DO UPDATE SET principal_id = excluded.principal_id",
                    (principal_id,),
                )
                checkpoint("credential")
                if old_principal_ids:
                    marks = ",".join("?" for _ in old_principal_ids)
                    connection.execute(f"UPDATE principals SET is_active = 0 WHERE principal_id IN ({marks})", old_principal_ids)
                    connection.execute(f"UPDATE api_sessions SET revoked = 1 WHERE principal_id IN ({marks})", old_principal_ids)
                self.initialize_principal_controls(principal_id, connection=connection)
                checkpoint("finalize")
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _transfer_owner_scoped_data(
        connection: sqlite3.Connection, old_principal_ids: list[str], old_user_ids: list[str],
        principal_id: str, user_id: str,
    ) -> None:
        """Move owner-scoped rows without rewriting immutable audit/event history."""
        excluded = {"account_credentials", "api_sessions", "instance_account_guard", "migrations", "principals", "users"}
        tables = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        for row in tables:
            table = str(row["name"])
            if table.startswith("sqlite_") or table in excluded:
                continue
            columns = {str(column["name"]) for column in connection.execute(f'PRAGMA table_info("{table}")').fetchall()}
            for column in ("owner_principal_id", "principal_id"):
                if column in columns and old_principal_ids:
                    marks = ",".join("?" for _ in old_principal_ids)
                    connection.execute(
                        f'UPDATE "{table}" SET "{column}" = ? WHERE "{column}" IN ({marks})',
                        [principal_id, *old_principal_ids],
                    )
            for column in ("owner_user_id", "user_id"):
                if column in columns and old_user_ids:
                    marks = ",".join("?" for _ in old_user_ids)
                    connection.execute(
                        f'UPDATE "{table}" SET "{column}" = ? WHERE "{column}" IN ({marks})',
                        [user_id, *old_user_ids],
                    )

    def rollback_initial_registration(self, principal_id: str, user_id: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM user_role_assignments WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM account_credentials WHERE principal_id = ?", (principal_id,))
            connection.execute("DELETE FROM principals WHERE principal_id = ?", (principal_id,))
            connection.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            connection.execute(
                "DELETE FROM instance_account_guard WHERE singleton = 1 AND principal_id = ?",
                (principal_id,),
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

    def create_session(
        self,
        session_id: str,
        project_root: str,
        title: str | None = None,
        user_id: str | None = None,
        origin: str = "chat",
    ) -> None:
        now = utc_now()
        # New sessions are stamped with the active project (if any) so project
        # scoping needs no caller changes — an organizing label, not authority.
        project_id = self.get_active_project(user_id)
        # `origin` records where the session came from ("chat" for a typed
        # conversation, "task" for the server-owned session a task runs in). A
        # provenance label only: it grants nothing and hides nothing, it just
        # lets a "recent conversations" list mean conversations (BUG-10).
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO sessions
                (session_id, project_root, created_at, updated_at, status, title, user_id, project_id, origin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, project_root, now, now, "open", title, user_id, project_id, origin),
            )

    def set_session_origin(self, session_id: str, origin: str) -> None:
        """Stamp an existing session's provenance.

        ``create_session`` is an INSERT OR IGNORE, so a session that predates the
        origin column (or this caller) keeps the default 'chat'. Task creation
        calls this so an Inbox created before the fix stops reading as a
        conversation. Provenance only — no gate, policy, or visibility changes.
        """
        with self.connect() as connection:
            connection.execute(
                "UPDATE sessions SET origin = ? WHERE session_id = ?", (origin, session_id)
            )

    # ── Projects (web-app task 5: named organizing scopes, governance-neutral) ──

    ACTIVE_PROJECT_SCOPE = "project_scope:"

    def create_project(self, project_id: str, name: str, root_subpath: str, parent_id: str | None = None, owner_user_id: str | None = None) -> None:
        if owner_user_id is None:
            original = self.original_account_principal_id()
            owner_user_id = self.principal_user_id(original) if original else None
        with self.connect() as connection:
            if parent_id:
                parent = connection.execute("SELECT path FROM projects WHERE project_id = ?", (parent_id,)).fetchone()
                parent_path = parent["path"] if parent else "/"
                path = f"{parent_path}{project_id}/"
            else:
                path = f"/{project_id}/"
            connection.execute(
                "INSERT INTO projects (project_id, name, root_subpath, created_at, parent_id, path, is_archived, archived_at, owner_user_id) VALUES (?, ?, ?, ?, ?, ?, 0, NULL, ?)",
                (project_id, name, root_subpath, utc_now(), parent_id, path, owner_user_id),
            )

    def load_project(self, project_id: str, user_id: str | None = None) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE project_id = ?" + (" AND owner_user_id = ?" if user_id else ""),
                (project_id, user_id) if user_id else (project_id,),
            ).fetchone()
        return dict(row) if row else None

    def load_project_by_name(self, name: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE name = ?", (name,)
            ).fetchone()
        return dict(row) if row else None

    def load_project_context(self, project_id: str, *, user_id: str | None = None) -> dict[str, Any]:
        if user_id is not None and self.load_project(project_id, user_id=user_id) is None:
            return {"instructions": "", "attachment_ids": [], "memory_enabled": False, "memory_mode": "inherit"}
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
        owner_principal_id: str | None = None,
    ) -> None:
        mode = memory_mode or ("enabled" if memory_enabled else "disabled")
        if mode not in {"inherit", "enabled", "disabled"}:
            raise ValueError("invalid_memory_mode")
        if owner_principal_id is not None and any(
            self.load_attachment_metadata(attachment_id, owner_principal_id=owner_principal_id) is None
            for attachment_id in attachment_ids
        ):
            raise ValueError("unknown_project_attachment")
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

    def list_projects(self, user_id: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT projects.*, COUNT(sessions.session_id) AS session_count
                FROM projects
                LEFT JOIN sessions ON sessions.project_id = projects.project_id
                """ + (" WHERE projects.owner_user_id = ? " if user_id else "") + """
                GROUP BY projects.project_id
                ORDER BY projects.created_at DESC
                """, (user_id,) if user_id else ()
            ).fetchall()
        return [dict(row) for row in rows]

    def get_active_project(self, user_id: str | None = None) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT project_id FROM active_project WHERE scope_id = ?",
                (f"{self.ACTIVE_PROJECT_SCOPE}{user_id or 'legacy'}",),
            ).fetchone()
            if row is None and user_id is None:
                owner = self._original_owner_from_connection(connection)
                if owner is not None:
                    principal = connection.execute(
                        "SELECT delegated_by_user_id FROM principals WHERE principal_id = ?", (owner,)
                    ).fetchone()
                    owner_user_id = str(principal["delegated_by_user_id"] or owner.removeprefix("principal_")) if principal else ""
                    if owner_user_id:
                        row = connection.execute(
                            "SELECT project_id FROM active_project WHERE scope_id = ?",
                            (f"{self.ACTIVE_PROJECT_SCOPE}{owner_user_id}",),
                        ).fetchone()
        project_id = str(row["project_id"]) if row is not None and row["project_id"] else None
        if project_id is not None and user_id is not None and self.load_project(project_id, user_id) is None:
            return None
        return project_id

    def save_active_project(self, project_id: str | None, user_id: str | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO active_project (scope_id, project_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(scope_id) DO UPDATE SET project_id = excluded.project_id, updated_at = excluded.updated_at
                """,
                (f"{self.ACTIVE_PROJECT_SCOPE}{user_id or 'legacy'}", project_id, utc_now()),
            )

    def load_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_sessions(
        self,
        limit: int = 10,
        project_id: str | None = None,
        user_id: str | None = None,
        include_archived: bool = False,
        origin: str | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM sessions"
        params: list[Any] = []
        conditions: list[str] = []
        if origin is not None:
            # Provenance filter (BUG-10): "chat" is the owner's conversations.
            # Legacy rows written before the column existed default to 'chat'.
            conditions.append("origin = ?")
            params.append(origin)
        if not include_archived:
            # Default listing surfaces active sessions only; archived rows stay
            # retrievable by an explicit ``include_archived`` request.
            conditions.append("archived = 0")
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
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def search_sessions(
        self, query: str, user_id: str | None = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        """Conversations matching *query*, each carrying the exchange that matched.

        RAIKER-2020: the title still matches on its own, but the message-body half
        now goes through ``conversation_fts`` instead of an unindexed
        ``LIKE '%term%'`` over every turn the owner has ever taken. The row keeps
        the shape it had and gains ``match_snippet`` / ``match_turn_id``, so the
        result list can say *why* a conversation matched rather than only that it
        did — which is the difference between finding a chat from years ago and
        recognising it.
        """
        stripped = query.strip()
        if not stripped:
            return []
        matched: dict[str, dict[str, Any]] = {}
        for hit in self.search_conversation_turns(stripped, user_id=user_id, limit=limit):
            matched.setdefault(
                str(hit["session_id"]),
                {"turn_id": str(hit["turn_id"]), "snippet": str(hit.get("snippet") or "")},
            )
        placeholders = ",".join("?" * len(matched)) if matched else "SELECT NULL"
        conditions = [f"(sessions.title LIKE ? OR sessions.session_id IN ({placeholders}))"]
        params: list[Any] = [f"%{stripped}%", *sorted(matched)]
        if user_id is not None:
            conditions.append("(sessions.user_id = ? OR sessions.user_id IS NULL)")
            params.append(user_id)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT sessions.* FROM sessions WHERE "
                + " AND ".join(conditions)
                + " ORDER BY sessions.updated_at DESC LIMIT ?",
                [*params, limit],
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            record = dict(row)
            hit = matched.get(str(record.get("session_id")), {})
            record["match_snippet"] = " ".join(str(hit.get("snippet", "")).split())[:300]
            record["match_turn_id"] = hit.get("turn_id", "")
            results.append(record)
        return results

    # ── Governed local MCP server profiles (Control Deck task 4) ─────────────
    # Every row is owner-scoped by ``principal_id``: an account can only list,
    # resolve, or mutate the MCP servers it created. ``command`` is stored as a
    # JSON argv array (interpreter + workspace-relative script) — never a secret
    # and never a remote endpoint. Reads decode it back to a list.

    @staticmethod
    def _mcp_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        for key in ("command", "tools"):
            raw = data.get(key)
            try:
                data[key] = json.loads(raw) if isinstance(raw, str) else []
            except (TypeError, ValueError):
                data[key] = []
        return data

    def create_mcp_server(
        self,
        *,
        server_id: str,
        principal_id: str,
        name: str,
        command: list[str],
        template: str | None = None,
        transport: str = "stdio",
        status: str = "created",
        last_connected_at: str | None = None,
        tools: list[str] | None = None,
        endpoint_url: str | None = None,
        auth_ref: str | None = None,
    ) -> str:
        """Upsert one owner-scoped MCP server profile.

        Keyed by ``server_id`` (INSERT OR REPLACE), and additionally unique per
        ``(principal_id, name)`` so re-building the same-named server for the
        same owner refreshes the single profile instead of accumulating rows.
        ``tools`` is the JSON-encoded list of tool names from the last successful
        handshake (names only — never arguments or output). ``endpoint_url`` is
        the remote HTTP URL for an ``http`` transport; ``auth_ref`` names where
        the owner token lives (never the token itself).
        """
        tool_list = list(tools) if tools is not None else None
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO mcp_servers
                   (server_id, principal_id, name, command, template, transport,
                    status, created_at, last_connected_at, tools, tool_count,
                    endpoint_url, auth_ref)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    server_id,
                    principal_id,
                    name,
                    json.dumps(list(command)),
                    template,
                    transport,
                    status,
                    utc_now(),
                    last_connected_at,
                    json.dumps(tool_list) if tool_list is not None else None,
                    len(tool_list) if tool_list is not None else 0,
                    endpoint_url,
                    auth_ref,
                ),
            )
        return server_id

    def update_mcp_server_runtime(
        self,
        server_id: str,
        principal_id: str,
        *,
        status: str,
        tools: list[str] | None = None,
        last_connected_at: str | None = None,
    ) -> bool:
        """Owner-scoped update of only the *runtime* fields of a profile — status,
        discovered tool names, and last-connected time — without touching its
        identity/transport/endpoint columns (so a re-test never wipes a stored
        remote endpoint or auth reference). Returns False if the row is missing
        or owned by another principal.

        ``tools=None`` means "this operation discovered nothing", not "this
        server has no tools": a `tools/call` session never enumerates, so it
        leaves the stored list alone. Overwriting it emptied the profile after
        every call — visible as `TOOLS (0)` on a connected server, and fatal to
        the projected tool set, which is built from exactly that list (BUG-12).
        """
        tool_list = list(tools) if tools is not None else None
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE mcp_servers
                   SET status = ?,
                       last_connected_at = ?,
                       tools = COALESCE(?, tools),
                       tool_count = COALESCE(?, tool_count)
                   WHERE server_id = ? AND principal_id = ?""",
                (
                    status,
                    last_connected_at,
                    json.dumps(tool_list) if tool_list is not None else None,
                    len(tool_list) if tool_list is not None else None,
                    server_id,
                    principal_id,
                ),
            )
            return cursor.rowcount > 0

    def rename_mcp_server(self, server_id: str, principal_id: str, name: str) -> bool:
        """Owner-scoped rename of one MCP server profile. Returns False if the
        row is missing / owned by another principal, or if the new name is
        already taken by another of the caller's servers (unique per owner)."""
        with self.connect() as connection:
            clash = connection.execute(
                "SELECT 1 FROM mcp_servers WHERE principal_id = ? AND name = ? AND server_id != ?",
                (principal_id, name, server_id),
            ).fetchone()
            if clash is not None:
                return False
            cursor = connection.execute(
                "UPDATE mcp_servers SET name = ? WHERE server_id = ? AND principal_id = ?",
                (name, server_id, principal_id),
            )
            return cursor.rowcount > 0

    def delete_mcp_server(self, server_id: str, principal_id: str) -> bool:
        """Owner-scoped delete of one MCP server profile. Returns False if the
        row is missing or owned by another principal (isolation)."""
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM mcp_servers WHERE server_id = ? AND principal_id = ?",
                (server_id, principal_id),
            )
            return cursor.rowcount > 0

    def list_mcp_servers(self, principal_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM mcp_servers WHERE principal_id = ? ORDER BY created_at DESC",
                (principal_id,),
            ).fetchall()
        return [self._mcp_row(row) for row in rows]

    def get_mcp_server(self, server_id: str, principal_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM mcp_servers WHERE server_id = ? AND principal_id = ?",
                (server_id, principal_id),
            ).fetchone()
        return self._mcp_row(row) if row else None

    def get_mcp_server_by_name(self, principal_id: str, name: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM mcp_servers WHERE principal_id = ? AND name = ?",
                (principal_id, name),
            ).fetchone()
        return self._mcp_row(row) if row else None

    def set_mcp_server_status(
        self,
        server_id: str,
        principal_id: str,
        status: str,
        last_connected_at: str | None = None,
    ) -> bool:
        """Owner-scoped status update. Returns False if the row is missing or is
        owned by another principal (isolation), so a status write can never
        touch another owner's server."""
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE mcp_servers SET status = ?, last_connected_at = ?
                   WHERE server_id = ? AND principal_id = ?""",
                (status, last_connected_at, server_id, principal_id),
            )
            return cursor.rowcount > 0

    def set_mcp_monitor_state(
        self,
        server_id: str,
        principal_id: str,
        monitor_state: str,
        *,
        paused_reason: str | None = None,
        paused_at: str | None = None,
    ) -> bool:
        """Owner-scoped transition of a connection's monitoring/lifecycle state
        (``active`` | ``paused`` | ``killed``). Returns False if the row is
        missing or owned by another principal (isolation), so a containment
        write can never touch another owner's connection. ``paused_reason`` /
        ``paused_at`` are redacted metadata (a rule code + summary, a timestamp)
        — never a payload."""
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE mcp_servers
                   SET monitor_state = ?, paused_reason = ?, paused_at = ?
                   WHERE server_id = ? AND principal_id = ?""",
                (monitor_state, paused_reason, paused_at, server_id, principal_id),
            )
            return cursor.rowcount > 0

    # ── Installed skills (SKILL.md documents and *.skill bundles) ────────────

    @staticmethod
    def _skill_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        data = dict(row)
        raw = data.get("files_json")
        try:
            data["files"] = json.loads(raw) if isinstance(raw, str) else []
        except (TypeError, ValueError):
            data["files"] = []
        data["active"] = bool(data.get("active", 0))
        return data

    def upsert_skill(
        self,
        *,
        skill_id: str,
        principal_id: str,
        name: str,
        description: str,
        checksum: str,
        skill_md: str,
        source: str,
        source_ref: str | None = None,
        version: str | None = None,
        bundle: bytes | None = None,
        files: list[str] | None = None,
        byte_size: int = 0,
        active: bool = True,
    ) -> str:
        """Insert or refresh one owner-scoped skill, keyed by ``(owner, name)``.

        Re-importing the same skill replaces the stored document in place — its
        ``skill_id``, its created-at, and the owner's active/inactive choice all
        survive the refresh, so an update never silently re-enables a skill the
        owner had turned off.
        """
        now = utc_now()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT skill_id, created_at, active FROM skills WHERE principal_id = ? AND name = ?",
                (principal_id, name),
            ).fetchone()
            resolved_id = str(existing["skill_id"]) if existing else skill_id
            created_at = str(existing["created_at"]) if existing else now
            resolved_active = bool(existing["active"]) if existing else active
            connection.execute(
                """INSERT OR REPLACE INTO skills
                   (skill_id, principal_id, name, description, version, source, source_ref,
                    checksum, active, skill_md, bundle, files_json, byte_size,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    resolved_id,
                    principal_id,
                    name,
                    description,
                    version,
                    source,
                    source_ref,
                    checksum,
                    1 if resolved_active else 0,
                    skill_md,
                    bundle,
                    json.dumps(list(files or [])),
                    int(byte_size),
                    created_at,
                    now,
                ),
            )
        return resolved_id

    def list_skills(self, principal_id: str) -> list[dict[str, Any]]:
        """Owner-scoped list, newest first. Bundles are excluded — the archive is
        only read on an explicit download."""
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT skill_id, principal_id, name, description, version, source,
                          source_ref, checksum, active, skill_md, files_json, byte_size,
                          created_at, updated_at
                   FROM skills WHERE principal_id = ? ORDER BY created_at DESC""",
                (principal_id,),
            ).fetchall()
        return [row for row in (self._skill_row(r) for r in rows) if row is not None]

    def get_skill(self, skill_id: str, principal_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM skills WHERE skill_id = ? AND principal_id = ?",
                (skill_id, principal_id),
            ).fetchone()
        return self._skill_row(row)

    def get_skill_by_name(self, principal_id: str, name: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM skills WHERE principal_id = ? AND name = ?",
                (principal_id, name),
            ).fetchone()
        return self._skill_row(row)

    def rename_skill(self, skill_id: str, principal_id: str, name: str) -> bool:
        """Owner-scoped rename. False when the row is missing, owned by another
        principal, or the new name is already taken by another of the owner's
        skills (names are the prompt handle, so they stay unique per owner)."""
        with self.connect() as connection:
            clash = connection.execute(
                "SELECT 1 FROM skills WHERE principal_id = ? AND name = ? AND skill_id != ?",
                (principal_id, name, skill_id),
            ).fetchone()
            if clash is not None:
                return False
            cursor = connection.execute(
                "UPDATE skills SET name = ?, updated_at = ? WHERE skill_id = ? AND principal_id = ?",
                (name, utc_now(), skill_id, principal_id),
            )
            return cursor.rowcount > 0

    def set_skill_active(self, skill_id: str, principal_id: str, active: bool) -> bool:
        """Owner-scoped activate/deactivate. A deactivated skill stays stored but
        is withheld from every turn's context."""
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE skills SET active = ?, updated_at = ? WHERE skill_id = ? AND principal_id = ?",
                (1 if active else 0, utc_now(), skill_id, principal_id),
            )
            return cursor.rowcount > 0

    def seeded_skill_names(self, principal_id: str) -> set[str]:
        """Shipped skills this owner has already been offered, installed or not."""
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT name FROM skill_seeds WHERE principal_id = ?", (principal_id,)
            ).fetchall()
        return {str(row["name"]) for row in rows}

    def record_skill_seed(self, principal_id: str, name: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO skill_seeds (principal_id, name, seeded_at) VALUES (?, ?, ?)",
                (principal_id, name, utc_now()),
            )

    def delete_skill(self, skill_id: str, principal_id: str) -> bool:
        """Owner-scoped delete. False when the row is missing or owned by another
        principal (isolation)."""
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM skills WHERE skill_id = ? AND principal_id = ?",
                (skill_id, principal_id),
            )
            return cursor.rowcount > 0

    # ── MCP monitoring: redacted per-session log + shared findings ───────────

    @staticmethod
    def _mcp_session_log_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        raw = data.get("hosts_json")
        try:
            data["hosts"] = json.loads(raw) if isinstance(raw, str) else []
        except (TypeError, ValueError):
            data["hosts"] = []
        return data

    def insert_mcp_session_log(
        self,
        *,
        server_id: str | None,
        principal_id: str,
        transport: str,
        operation: str,
        hosts: list[str],
        tool_calls: int,
        bytes_in: int,
        bytes_out: int,
        error_count: int,
        outcome: str,
        started_at: str,
        ended_at: str | None = None,
    ) -> str:
        """Append one redacted per-session monitoring row for a connection.

        Stores only metadata — the tool-call count, the hosts contacted (netloc
        only), byte counts, error count, and outcome. No payload, token, or host
        secret is ever written here. Owner-scoped by ``principal_id``.
        """
        session_row_id = new_id("mses_")
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO mcp_session_log
                   (session_row_id, server_id, principal_id, transport, operation,
                    hosts_json, tool_calls, bytes_in, bytes_out, error_count,
                    outcome, started_at, ended_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_row_id,
                    server_id,
                    principal_id,
                    transport,
                    operation,
                    json.dumps(list(hosts)),
                    int(tool_calls),
                    int(bytes_in),
                    int(bytes_out),
                    int(error_count),
                    outcome,
                    started_at,
                    ended_at,
                ),
            )
        return session_row_id

    def list_mcp_session_logs(
        self, server_id: str | None, principal_id: str, *, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Owner-scoped, most-recent-first session rows for one connection. A
        different owner (or a null server_id) resolves nothing, so a baseline can
        never be read across owners."""
        if not server_id:
            return []
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM mcp_session_log
                   WHERE principal_id = ? AND server_id = ?
                   ORDER BY started_at DESC, rowid DESC LIMIT ?""",
                (principal_id, server_id, int(limit)),
            ).fetchall()
        return [self._mcp_session_log_row(row) for row in rows]

    @staticmethod
    def _security_finding_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        raw = data.get("redacted_detail_json")
        try:
            data["redacted_detail"] = json.loads(raw) if isinstance(raw, str) else {}
        except (TypeError, ValueError):
            data["redacted_detail"] = {}
        return data

    def insert_security_finding(
        self,
        *,
        principal_id: str,
        source: str,
        severity: str,
        code: str,
        summary: str,
        redacted_detail: dict[str, Any] | None = None,
        subject_id: str | None = None,
        state: str = "open",
    ) -> str:
        """Persist one redacted finding. ``redacted_detail`` must already contain
        redacted metadata only (labels/counts/hostnames) — never a raw value.
        Owner-scoped by ``principal_id``; shared substrate across monitors."""
        finding_id = new_id("find_")
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO security_findings
                   (finding_id, principal_id, source, severity, code, summary,
                    redacted_detail_json, subject_id, state, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    finding_id,
                    principal_id,
                    source,
                    severity,
                    code,
                    summary,
                    json.dumps(dict(redacted_detail or {})),
                    subject_id,
                    state,
                    utc_now(),
                ),
            )
        return finding_id

    def list_security_findings(
        self,
        principal_id: str,
        *,
        source: str | None = None,
        subject_id: str | None = None,
        state: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Owner-scoped findings, newest first, optionally filtered by source,
        subject, or state. A different owner resolves nothing (isolation)."""
        conditions = ["principal_id = ?"]
        params: list[Any] = [principal_id]
        if source is not None:
            conditions.append("source = ?")
            params.append(source)
        if subject_id is not None:
            conditions.append("subject_id = ?")
            params.append(subject_id)
        if state is not None:
            conditions.append("state = ?")
            params.append(state)
        params.append(int(limit))
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM security_findings WHERE {' AND '.join(conditions)} "
                "ORDER BY created_at DESC, rowid DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._security_finding_row(row) for row in rows]

    # ── Owner-facing notifications (shared substrate) ────────────────────────

    def insert_notification(
        self,
        *,
        principal_id: str,
        kind: str,
        title: str,
        body: str,
        finding_id: str | None = None,
        subject_id: str | None = None,
    ) -> str:
        """Persist one owner-facing notification. ``title`` / ``body`` are already
        redacted human-readable copy (never a raw payload or token). Owner-scoped
        by ``principal_id``; shared across sources (findings + containment)."""
        notification_id = new_id("ntf_")
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO notifications
                   (notification_id, principal_id, kind, title, body, finding_id,
                    subject_id, read, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                (
                    notification_id,
                    principal_id,
                    kind,
                    title,
                    body,
                    finding_id,
                    subject_id,
                    utc_now(),
                ),
            )
        return notification_id

    def list_notifications(
        self, principal_id: str, *, unread_only: bool = False, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Owner-scoped notifications, newest first. ``unread_only`` filters to
        the unread ones. A different owner resolves nothing (isolation)."""
        conditions = ["principal_id = ?"]
        params: list[Any] = [principal_id]
        if unread_only:
            conditions.append("read = 0")
        params.append(int(limit))
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM notifications WHERE {' AND '.join(conditions)} "
                "ORDER BY created_at DESC, rowid DESC LIMIT ?",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_notification_read(self, notification_id: str, principal_id: str) -> bool:
        """Owner-scoped mark-as-read. Returns False if the row is missing or owned
        by another principal (isolation)."""
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE notifications SET read = 1 WHERE notification_id = ? AND principal_id = ?",
                (notification_id, principal_id),
            )
            return cursor.rowcount > 0

    # â”€â”€ Credential lifecycle + security-monitor state (Control Deck Task 5) â”€â”€

    def upsert_credential_lifecycle(
        self,
        principal_id: str,
        provider: str,
        *,
        verified_at: str,
        due_at: str,
        status: str,
    ) -> dict[str, Any]:
        credential_id = new_id("cred_")
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO credential_lifecycle
                   (credential_id, principal_id, provider, rotated_at, verified_at, due_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(principal_id, provider) DO UPDATE SET
                     rotated_at=excluded.rotated_at, verified_at=excluded.verified_at,
                     due_at=excluded.due_at, status=excluded.status""",
                (credential_id, principal_id, provider, verified_at, verified_at, due_at, status),
            )
        row = self.get_credential_lifecycle(principal_id, provider)
        assert row is not None
        return row

    def get_credential_lifecycle(self, principal_id: str, provider: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM credential_lifecycle WHERE principal_id = ? AND provider = ?",
                (principal_id, provider),
            ).fetchone()
        return dict(row) if row else None

    def list_credential_lifecycle(self, principal_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM credential_lifecycle WHERE principal_id = ? ORDER BY provider",
                (principal_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def has_connector_credential(self, principal_id: str, connector_id: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM connector_credentials WHERE principal_id = ? AND connector_id = ?",
                (principal_id, connector_id),
            ).fetchone()
        return row is not None

    def get_security_monitor_state(
        self, principal_id: str, source: str, subject_id: str, code: str
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM security_monitor_state
                   WHERE principal_id = ? AND source = ? AND subject_id = ? AND code = ?""",
                (principal_id, source, subject_id, code),
            ).fetchone()
        return dict(row) if row else None

    def set_security_monitor_state(
        self,
        principal_id: str,
        source: str,
        subject_id: str,
        code: str,
        *,
        state: str,
        finding_id: str | None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO security_monitor_state
                   (principal_id, source, subject_id, code, state, finding_id, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(principal_id, source, subject_id, code) DO UPDATE SET
                     state=excluded.state, finding_id=excluded.finding_id, updated_at=excluded.updated_at""",
                (principal_id, source, subject_id, code, state, finding_id, utc_now()),
            )

    def set_security_finding_state(self, finding_id: str, principal_id: str, state: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE security_findings SET state = ? WHERE finding_id = ? AND principal_id = ?",
                (state, finding_id, principal_id),
            )
        return cursor.rowcount > 0

    def list_security_monitor_state(self, principal_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM security_monitor_state WHERE principal_id = ? ORDER BY updated_at DESC",
                (principal_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    # ── Capability-agnostic behaviour monitoring and containment (BUG-76/77) ──
    # The generic sibling of the MCP monitor's storage: one redacted activity row
    # per governed capability invocation, and one containment row per subject.
    # Owner-scoped throughout — every read and write is keyed by `principal_id`,
    # so one owner's monitor can never see or contain another owner's subject.

    def insert_capability_activity(
        self,
        *,
        principal_id: str,
        capability: str,
        subject_id: str,
        operation: str = "",
        hosts: list[str] | None = None,
        tools: list[str] | None = None,
        calls: int = 0,
        bytes_in: int = 0,
        bytes_out: int = 0,
        error_count: int = 0,
        outcome: str = "ok",
        reason_code: str = "",
        arg_sensitivity: str | None = None,
        result_sensitivity: str | None = None,
        observed_at: str | None = None,
    ) -> str:
        activity_id = new_id("cact_")
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO capability_activity_log
                   (activity_id, principal_id, capability, subject_id, operation, hosts_json,
                    tools_json, calls, bytes_in, bytes_out, error_count, outcome, reason_code,
                    arg_sensitivity, result_sensitivity, observed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    activity_id, principal_id, capability, subject_id, operation,
                    json.dumps(sorted(hosts or [])), json.dumps(sorted(tools or [])),
                    int(calls), int(bytes_in), int(bytes_out), int(error_count), outcome,
                    reason_code, arg_sensitivity, result_sensitivity, observed_at or utc_now(),
                ),
            )
        return activity_id

    def list_capability_activity(
        self, principal_id: str, capability: str, subject_id: str, *, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Most-recent-first activity rows forming one subject's rolling baseline."""
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM capability_activity_log
                   WHERE principal_id = ? AND capability = ? AND subject_id = ?
                   ORDER BY observed_at DESC, rowid DESC LIMIT ?""",
                (principal_id, capability, subject_id, int(limit)),
            ).fetchall()
        return [
            {
                **dict(row),
                "hosts": json.loads(row["hosts_json"] or "[]"),
                "tools": json.loads(row["tools_json"] or "[]"),
            }
            for row in rows
        ]

    def get_capability_containment(
        self, principal_id: str, capability: str, subject_id: str
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM capability_containment
                   WHERE principal_id = ? AND capability = ? AND subject_id = ?""",
                (principal_id, capability, subject_id),
            ).fetchone()
        return dict(row) if row else None

    def list_capability_containment(
        self, principal_id: str, *, capability: str | None = None
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM capability_containment WHERE principal_id = ?"
        params: list[Any] = [principal_id]
        if capability:
            query += " AND capability = ?"
            params.append(capability)
        with self.connect() as connection:
            rows = connection.execute(
                query + " ORDER BY updated_at DESC", tuple(params)
            ).fetchall()
        return [dict(row) for row in rows]

    def set_capability_containment(
        self,
        principal_id: str,
        capability: str,
        subject_id: str,
        *,
        state: str,
        label: str = "",
        reason: str | None = None,
        source: str = "owner",
        finding_id: str | None = None,
        failure_streak: int | None = None,
        last_failure_code: str | None = None,
        contained_at: str | None = None,
        probe_after: str | None = None,
    ) -> dict[str, Any]:
        """Upsert one subject's containment row and return the stored result.

        ``failure_streak``/``last_failure_code``/``probe_after`` are only written
        when supplied, so a containment transition never silently resets the
        breaker's own counters and a counter update never rewrites the owner's
        stated reason.
        """
        now = utc_now()
        existing = self.get_capability_containment(principal_id, capability, subject_id) or {}
        row = {
            "label": label or str(existing.get("label") or ""),
            "state": state,
            "reason": reason,
            "source": source,
            "finding_id": finding_id,
            "failure_streak": (
                int(failure_streak)
                if failure_streak is not None
                else int(existing.get("failure_streak") or 0)
            ),
            "last_failure_code": (
                last_failure_code
                if last_failure_code is not None
                else str(existing.get("last_failure_code") or "")
            ),
            "contained_at": contained_at,
            "probe_after": probe_after,
        }
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO capability_containment
                   (principal_id, capability, subject_id, label, state, reason, source,
                    finding_id, failure_streak, last_failure_code, contained_at, probe_after,
                    updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(principal_id, capability, subject_id) DO UPDATE SET
                     label=excluded.label, state=excluded.state, reason=excluded.reason,
                     source=excluded.source, finding_id=excluded.finding_id,
                     failure_streak=excluded.failure_streak,
                     last_failure_code=excluded.last_failure_code,
                     contained_at=excluded.contained_at, probe_after=excluded.probe_after,
                     updated_at=excluded.updated_at""",
                (
                    principal_id, capability, subject_id, row["label"], row["state"],
                    row["reason"], row["source"], row["finding_id"], row["failure_streak"],
                    row["last_failure_code"], row["contained_at"], row["probe_after"], now,
                ),
            )
        return {
            "principal_id": principal_id,
            "capability": capability,
            "subject_id": subject_id,
            **row,
            "updated_at": now,
        }

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

    def list_project_tree(self, include_archived: bool = False, user_id: str | None = None) -> list[dict[str, Any]]:
        """Return nested tree of projects (active by default)."""
        conditions = [] if include_archived else ["is_archived = 0"]
        params: list[Any] = []
        if user_id is not None:
            conditions.append("owner_user_id = ?")
            params.append(user_id)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        with self.connect() as conn:
            rows = conn.execute(f"""
                SELECT * FROM projects {where} ORDER BY path, created_at
            """, params).fetchall()
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

    def get_ancestor_contexts(self, project_id: str, *, user_id: str | None = None) -> list[dict[str, Any]]:
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
                """ + (" AND p.owner_user_id = ?" if user_id is not None else "") + """
                ORDER BY LENGTH(p.path) ASC
            """, (path, project_id, *([user_id] if user_id is not None else []))).fetchall()
        return [dict(r) for r in rows]

    def load_effective_project_context(self, project_id: str, *, user_id: str | None = None) -> dict[str, Any]:
        """Return the project's context merged with every active ancestor's.

        Instructions concatenate root→leaf so the nearest folder speaks last;
        attachment ids union in the same order; ``memory_enabled`` is the
        leaf's own value (an ancestor cannot opt a child into project memory).
        Archived ancestors contribute nothing. This is the single merge used by
        both the live context gatherer and the dashboard read path.
        """
        own = self.load_project_context(project_id, user_id=user_id)
        instructions: list[str] = []
        attachment_ids: list[str] = []
        memory_mode = "inherit"
        for ancestor in self.get_ancestor_contexts(project_id, user_id=user_id):
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

    def _update_owned_session(
        self, session_id: str, user_id: str | None, assignments: dict[str, Any]
    ) -> bool:
        """Apply column assignments to one session under the owner check shared
        by every session mutator. Returns False when the session does not exist
        or is owned by another account (legacy unowned sessions stay writable by
        any authenticated account, mirroring set_session_pinned). ``updated_at``
        is always refreshed. Column names come only from trusted call sites."""
        if not assignments:
            return False
        with self.connect() as connection:
            exists, owner = self._session_owner(connection, session_id)
            if not exists:
                return False
            if user_id is not None and owner is not None and str(owner) != user_id:
                return False
            columns = ", ".join(f"{column} = ?" for column in assignments)
            connection.execute(
                f"UPDATE sessions SET {columns}, updated_at = ? WHERE session_id = ?",
                (*assignments.values(), utc_now(), session_id),
            )
        return True

    def rename_session(
        self, session_id: str, title: str, user_id: str | None = None
    ) -> bool:
        """Set one session's title. The caller supplies the already-normalized
        title. Returns False if the session does not exist or is owned by
        another account (isolation mirrors set_session_pinned)."""
        return self._update_owned_session(session_id, user_id, {"title": title})

    def set_session_archived(
        self, session_id: str, archived: bool, user_id: str | None = None
    ) -> bool:
        """Soft-archive (or restore) one session — a reversible organizing state
        that never deletes transcripts, events, checkpoints, or permissions.
        ``archived_at`` records the archive time and clears on restore. Returns
        False if the session does not exist or is owned by another account
        (isolation mirrors set_session_pinned)."""
        return self._update_owned_session(
            session_id,
            user_id,
            {"archived": int(archived), "archived_at": utc_now() if archived else None},
        )

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
            if project_id is not None:
                project = connection.execute(
                    "SELECT owner_user_id FROM projects WHERE project_id = ?", (project_id,)
                ).fetchone()
                if project is None or project["owner_user_id"] != owner:
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
            # Session-keyed rows added after this cascade was written, each of
            # which holds conversation content or state that must not outlive the
            # conversation: the source ledger and its recorded passages (C6/C4),
            # the agent's standing plan (B6), and any parked stop/steer (B17/C13).
            "turn_sources", "agent_plans", "turn_controls",
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

    def is_memory_incognito(self, owner_principal_id: str | None = None) -> bool:
        scope_id = f"{self.MEMORY_SETTINGS_SCOPE}:{owner_principal_id}" if owner_principal_id else self.MEMORY_SETTINGS_SCOPE
        with self.connect() as connection:
            row = connection.execute(
                "SELECT incognito FROM memory_settings WHERE scope_id = ?",
                (scope_id,),
            ).fetchone()
            if row is None and owner_principal_id is None:
                original = self._original_owner_from_connection(connection)
                if original is not None:
                    row = connection.execute(
                        "SELECT incognito FROM memory_settings WHERE scope_id = ?",
                        (f"{self.MEMORY_SETTINGS_SCOPE}:{original}",),
                    ).fetchone()
        return bool(row["incognito"]) if row is not None else False

    def set_memory_incognito(self, incognito: bool, owner_principal_id: str | None = None) -> None:
        if owner_principal_id is None:
            owner_principal_id = self.original_account_principal_id()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO memory_settings (scope_id, incognito, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(scope_id) DO UPDATE SET incognito = excluded.incognito, updated_at = excluded.updated_at
                """,
                (f"{self.MEMORY_SETTINGS_SCOPE}:{owner_principal_id}" if owner_principal_id else self.MEMORY_SETTINGS_SCOPE, 1 if incognito else 0, utc_now()),
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
        title = " ".join(prompt_text.split())[:80].rstrip()
        if len(title) == 80:
            title = f"{title[:-1]}…"
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO turns
                (turn_id, session_id, turn_type, status, prompt_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (turn_id, session_id, "prompt", status, prompt_text, utc_now()),
            )
            # Keep a human-readable conversation name without replacing a
            # title that was explicitly supplied or generated earlier.
            connection.execute(
                """
                UPDATE sessions SET title = CASE
                    WHEN (title IS NULL OR TRIM(title) = '') AND ? != '' THEN ?
                    ELSE title
                END, updated_at = ?
                WHERE session_id = ?
                """,
                (title, title, utc_now(), session_id),
            )
            self._sync_conversation_fts(connection, turn_id)

    def complete_turn(self, turn_id: str, status: str, summary: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE turns SET status = ?, completed_at = ?, summary = ? WHERE turn_id = ?",
                (status, utc_now(), summary, turn_id),
            )
            self._sync_conversation_fts(connection, turn_id)

    # ── Conversation recall (RAIKER-2020) ────────────────────────────────────
    #
    # `conversation_fts` is a projection of `turns`, rebuilt from it and never
    # read as an authority. Every search below carries its hits back to the
    # `turns`/`sessions` rows so ownership is still decided by `sessions.user_id`
    # — the index narrows the candidate set, it does not widen who may see one.

    @staticmethod
    def _sync_conversation_fts(connection: sqlite3.Connection, turn_id: str) -> None:
        with contextlib.suppress(sqlite3.OperationalError):
            connection.execute("DELETE FROM conversation_fts WHERE turn_id = ?", (turn_id,))
            connection.execute(
                """INSERT INTO conversation_fts(turn_id, session_id, role, text)
                   SELECT turn_id, session_id, 'prompt', prompt_text FROM turns
                   WHERE turn_id = ? AND prompt_text IS NOT NULL AND TRIM(prompt_text) != ''""",
                (turn_id,),
            )
            connection.execute(
                """INSERT INTO conversation_fts(turn_id, session_id, role, text)
                   SELECT turn_id, session_id, 'answer', summary FROM turns
                   WHERE turn_id = ? AND summary IS NOT NULL AND TRIM(summary) != ''""",
                (turn_id,),
            )

    @staticmethod
    def _backfill_conversation_fts(connection: sqlite3.Connection) -> None:
        """Populate the index once, for the turns that predate it.

        Deliberately *not* a rebuild on every open: a workspace carrying years of
        conversation would pay a full re-index to start the app. New turns keep
        themselves in sync through ``_sync_conversation_fts``; a workspace that
        needs a repair gets one from ``rebuild_conversation_fts`` on request.
        """
        with contextlib.suppress(sqlite3.OperationalError):
            # `LIMIT 1`, not `COUNT(*)`: counting an FTS4 table scans its whole
            # content table, and a workspace carrying years of conversation would
            # pay that on every start — the exact case this index exists for.
            if connection.execute("SELECT 1 FROM conversation_fts LIMIT 1").fetchone():
                return
            SQLiteStore._rebuild_conversation_fts(connection)

    @staticmethod
    def _rebuild_conversation_fts(connection: sqlite3.Connection) -> None:
        connection.execute("DELETE FROM conversation_fts")
        connection.execute(
            """INSERT INTO conversation_fts(turn_id, session_id, role, text)
               SELECT turn_id, session_id, 'prompt', prompt_text FROM turns
               WHERE prompt_text IS NOT NULL AND TRIM(prompt_text) != ''"""
        )
        connection.execute(
            """INSERT INTO conversation_fts(turn_id, session_id, role, text)
               SELECT turn_id, session_id, 'answer', summary FROM turns
               WHERE summary IS NOT NULL AND TRIM(summary) != ''"""
        )

    # ── Web egress blocklist (RAIKER-2021) ───────────────────────────────────

    def list_web_blocklist_rules(self, *, principal_id: str | None = None) -> list[str]:
        """Just the rule strings, for the policy layer to compile."""
        return [str(row["rule"]) for row in self.list_web_blocklist(principal_id=principal_id)]

    def list_web_blocklist(self, *, principal_id: str | None = None) -> list[dict[str, Any]]:
        """Owner rules, plus any that predate per-owner scoping.

        A row with a NULL owner is included for everyone: it was written before
        the column existed, and dropping it silently would *unblock* something.
        """
        sql = "SELECT * FROM web_egress_blocklist"
        params: list[Any] = []
        if principal_id:
            sql += " WHERE owner_principal_id = ? OR owner_principal_id IS NULL"
            params.append(principal_id)
        sql += " ORDER BY created_at DESC"
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]

    def add_web_blocklist_rule(
        self, rule: str, kind: str, *, principal_id: str | None = None,
        note: str = "", created_by: str = "",
    ) -> str:
        rule_id = new_id("wbl_")
        with self.connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO web_egress_blocklist
                   (rule_id, owner_principal_id, rule, kind, note, created_at, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (rule_id, principal_id, rule, kind, note[:500], utc_now(), created_by),
            )
        return rule_id

    def delete_web_blocklist_rule(self, rule_id: str, *, principal_id: str | None = None) -> bool:
        sql = "DELETE FROM web_egress_blocklist WHERE rule_id = ?"
        params: list[Any] = [rule_id]
        if principal_id:
            sql += " AND (owner_principal_id = ? OR owner_principal_id IS NULL)"
            params.append(principal_id)
        with self.connect() as connection:
            return connection.execute(sql, params).rowcount > 0

    # ── Git credential grants (RAIKER-2022) ──────────────────────────────────

    def create_git_credential_grant(
        self, *, principal_id: str, scope: str, expires_at: str,
        session_id: str | None = None, reason: str = "",
    ) -> dict[str, Any]:
        """Record one owner decision to lend the git credential.

        ``scope`` is ``once`` or ``session``. Creating a grant supersedes any
        active one for the same principal: two live grants would mean the owner
        could not tell which decision was in force, and revoking one would leave
        the other standing.
        """
        grant_id = new_id("grant_")
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """UPDATE git_credential_grants SET status = 'superseded', revoked_at = ?
                   WHERE owner_principal_id = ? AND status = 'active'""",
                (now, principal_id),
            )
            connection.execute(
                """INSERT INTO git_credential_grants
                   (grant_id, owner_principal_id, session_id, scope, status, reason,
                    granted_at, expires_at)
                   VALUES (?, ?, ?, ?, 'active', ?, ?, ?)""",
                (grant_id, principal_id, session_id, scope, reason[:500], now, expires_at),
            )
        return {
            "grant_id": grant_id, "scope": scope, "status": "active",
            "granted_at": now, "expires_at": expires_at, "session_id": session_id,
        }

    def active_git_credential_grant(
        self, principal_id: str, *, session_id: str | None = None, now: str | None = None
    ) -> dict[str, Any] | None:
        """The grant that would authorise a git command right now, if any.

        Expiry is evaluated here rather than by a sweep: a grant the owner set to
        last an hour must stop working an hour later whether or not anything has
        run since.
        """
        moment = now or utc_now()
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM git_credential_grants
                   WHERE owner_principal_id = ? AND status = 'active' AND expires_at > ?
                   ORDER BY granted_at DESC LIMIT 1""",
                (principal_id, moment),
            ).fetchone()
        if row is None:
            return None
        grant = dict(row)
        # A session grant is exactly that: it does not carry into another chat.
        if (
            str(grant.get("scope")) == "session"
            and grant.get("session_id")
            and session_id is not None
            and str(grant["session_id"]) != session_id
        ):
            return None
        return grant

    def consume_git_credential_grant(self, grant_id: str) -> None:
        """Count a use, and close a one-shot grant behind it."""
        with self.connect() as connection:
            connection.execute(
                """UPDATE git_credential_grants
                   SET uses = uses + 1,
                       consumed_at = COALESCE(consumed_at, ?),
                       status = CASE WHEN scope = 'once' THEN 'consumed' ELSE status END
                   WHERE grant_id = ?""",
                (utc_now(), grant_id),
            )

    def revoke_git_credential_grants(self, principal_id: str) -> int:
        with self.connect() as connection:
            return connection.execute(
                """UPDATE git_credential_grants SET status = 'revoked', revoked_at = ?
                   WHERE owner_principal_id = ? AND status = 'active'""",
                (utc_now(), principal_id),
            ).rowcount

    def rebuild_conversation_fts(self) -> int:
        """Owner-started repair. Returns the number of indexed rows."""
        with self.connect() as connection:
            self._rebuild_conversation_fts(connection)
            return int(connection.execute("SELECT COUNT(*) FROM conversation_fts").fetchone()[0] or 0)

    @staticmethod
    def _match_terms(query: str) -> list[str]:
        """FTS4-safe terms. Operators and punctuation are stripped, not escaped."""
        cleaned = "".join(character if character.isalnum() else " " for character in query)
        return [term for term in cleaned.split() if len(term) >= 3][:12]

    def search_conversation_turns(
        self,
        query: str,
        *,
        user_id: str | None = None,
        limit: int = 10,
        session_id: str | None = None,
        after: str | None = None,
        before: str | None = None,
    ) -> list[dict[str, Any]]:
        """Exchanges matching *query*, newest first, scoped to one owner.

        The index answers "which exchanges mention this"; the join answers "and
        may this caller see them". ``after``/``before`` are ISO timestamps, which
        is what makes an old conversation reachable at all: without them a bounded
        result set is always the recent one.
        """
        if limit < 1:
            return []
        terms = self._match_terms(query)
        conditions = ["turns.turn_id IS NOT NULL"]
        params: list[Any] = []
        if terms:
            source = (
                "conversation_fts JOIN turns ON turns.turn_id = conversation_fts.turn_id "
                "JOIN sessions ON sessions.session_id = turns.session_id"
            )
            selected = (
                "conversation_fts.role AS role, "
                "snippet(conversation_fts, '', '', '…', -1, 18) AS snippet"
            )
            conditions.append("conversation_fts MATCH ?")
            params.append(" ".join(terms))
        else:
            # Terms shorter than the index tokenizer's floor (an identifier such
            # as `q3`) still have to be findable, so a substring scan stands in.
            # The role has to be decided by which side actually matched, or a hit
            # in an answer is reported as a prompt and read back from the wrong
            # column.
            source = "turns JOIN sessions ON sessions.session_id = turns.session_id"
            selected = (
                "CASE WHEN turns.prompt_text LIKE ? THEN 'prompt' ELSE 'answer' END AS role, "
                "SUBSTR(CASE WHEN turns.prompt_text LIKE ? THEN turns.prompt_text "
                "ELSE COALESCE(turns.summary, '') END, 1, 220) AS snippet"
            )
            like = f"%{query.strip()}%"
            params.extend([like, like])
            conditions.append("(turns.prompt_text LIKE ? OR turns.summary LIKE ?)")
            params.extend([like, like])
        if user_id is not None:
            conditions.append("(sessions.user_id = ? OR sessions.user_id IS NULL)")
            params.append(user_id)
        if session_id is not None:
            conditions.append("turns.session_id = ?")
            params.append(session_id)
        if after:
            conditions.append("turns.created_at >= ?")
            params.append(after)
        if before:
            conditions.append("turns.created_at <= ?")
            params.append(before)
        params.append(limit)
        sql = (
            f"SELECT turns.turn_id AS turn_id, turns.session_id AS session_id, "
            f"turns.created_at AS created_at, turns.prompt_text AS prompt_text, "
            f"turns.summary AS summary, sessions.title AS session_title, "
            f"sessions.origin AS origin, {selected} FROM {source} "
            f"WHERE {' AND '.join(conditions)} "
            f"ORDER BY turns.created_at DESC LIMIT ?"
        )
        with self.connect() as connection:
            try:
                rows = connection.execute(sql, params).fetchall()
            except sqlite3.OperationalError:
                return []
        return [dict(row) for row in rows]

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
        self,
        action: ToolAction,
        session_id: str,
        turn_id: str | None,
        status: str,
        *,
        owner_principal_id: str | None = None,
        machine_subject: str | None = None,
        machine_token_id: str | None = None,
        machine_key_id: str | None = None,
        machine_issued_at: str | None = None,
        machine_expires_at: str | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                  INSERT OR REPLACE INTO tool_actions
                  (action_id, session_id, turn_id, task_id, tool_name, arguments_json,
                   risk_level, status, proposed_at, completed_at, proposed_by,
                   owner_principal_id, machine_subject, machine_token_id,
                   machine_key_id, machine_issued_at, machine_expires_at)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                          COALESCE((SELECT proposed_at FROM tool_actions WHERE action_id = ?), ?),
                          ?, ?,
                          COALESCE(?, (SELECT owner_principal_id FROM tool_actions WHERE action_id = ?)),
                          COALESCE(?, (SELECT machine_subject FROM tool_actions WHERE action_id = ?)),
                          COALESCE(?, (SELECT machine_token_id FROM tool_actions WHERE action_id = ?)),
                          COALESCE(?, (SELECT machine_key_id FROM tool_actions WHERE action_id = ?)),
                          COALESCE(?, (SELECT machine_issued_at FROM tool_actions WHERE action_id = ?)),
                          COALESCE(?, (SELECT machine_expires_at FROM tool_actions WHERE action_id = ?)))
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
                      action.proposed_by,
                      owner_principal_id,
                      action.action_id,
                      machine_subject,
                      action.action_id,
                      machine_token_id,
                      action.action_id,
                      machine_key_id,
                      action.action_id,
                      machine_issued_at,
                      action.action_id,
                      machine_expires_at,
                      action.action_id,
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
        self,
        approval_id: str,
        action: ToolAction | str,
        status: str = "pending",
        *,
        ttl_hours: float | None = 24.0,
        critical: bool = False,
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
        # The approval carries an immutable intent snapshot: the SHA-256 of the
        # proposed action's canonical payload (TOCTOU defense) plus a bounded
        # lifetime. A pending approval that is never resolved expires — its
        # resting state becomes "expired", so a stale grant can never execute.
        created = datetime.now(UTC).replace(microsecond=0)
        created_at = created.isoformat().replace("+00:00", "Z")
        expires_at: str | None = None
        if ttl_hours is not None and ttl_hours > 0:
            expires_at = (
                (created + timedelta(hours=ttl_hours)).isoformat().replace("+00:00", "Z")
            )
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO approvals
                (approval_id, action_id, status, approval_scope, created_at, expires_at, action_payload_sha256, critical)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval_id,
                    action_id,
                    status,
                    "critical" if critical else "action",
                    created_at,
                    expires_at,
                    payload_hash,
                    1 if critical else 0,
                ),
            )

    def expire_approval(self, approval_id: str) -> bool:
        """Resolve a still-pending approval to ``expired``.

        Returns True when this call performed the transition. The
        ``status = 'pending'`` guard makes it a no-op (returning False) once the
        approval has already been approved, denied, or expired, so an expiry
        sweep can never clobber a real human decision.
        """
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE approvals SET status = 'expired', resolved_at = ? "
                "WHERE approval_id = ? AND status = 'pending'",
                (utc_now(), approval_id),
            )
        return cursor.rowcount == 1

    def claim_approval_for_execution(self, approval_id: str) -> bool:
        """Atomically claim a pending approval for execution (pending → executing).

        Returns True only for the single caller that wins the race. The
        ``WHERE status = 'pending'`` guard on a single UPDATE is the
        single-execution primitive: two concurrent relays cannot both claim the
        same approval, so an approved action executes at most once.
        """
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE approvals SET status = 'executing' "
                "WHERE approval_id = ? AND status = 'pending'",
                (approval_id,),
            )
        return cursor.rowcount == 1

    def finalize_approval_execution(
        self, approval_id: str, *, status: str, resolved_by: str
    ) -> bool:
        """Resolve a claimed approval to a terminal outcome (executing → status).

        ``status`` is the terminal state — ``executed`` on success or
        ``execution_failed`` when the target executor ran but failed. The
        ``executing`` guard means only a claimed approval can be finalized.
        """
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE approvals SET status = ?, approved_by = ?, resolved_at = ? "
                "WHERE approval_id = ? AND status = 'executing'",
                (status, resolved_by, utc_now(), approval_id),
            )
        return cursor.rowcount == 1

    def release_approval_claim(self, approval_id: str) -> bool:
        """Return a claimed approval to ``pending`` (executing → pending).

        Used only when the re-governed action was blocked *before* any executor
        ran (gate disabled, policy deny, no executor), so nothing was committed
        and a later retry — after the owner fixes the gate — is safe. Clears the
        claim's bookkeeping so the approval looks untouched.
        """
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE approvals SET status = 'pending', approved_by = NULL, resolved_at = NULL "
                "WHERE approval_id = ? AND status = 'executing'",
                (approval_id,),
            )
        return cursor.rowcount == 1

    # ── agent plan (B6 — the turn's visible spine) ────────────────────────────

    def save_agent_plan(
        self, *, session_id: str, principal_id: str, turn_id: str, steps_json: str
    ) -> str:
        """Replace this conversation's plan with *steps_json*; returns ``updated_at``.

        The plan is current intent, not a history, so one row per
        (session, principal) is replaced whole. ``created_at`` is preserved
        across updates so the workspace can say how long the plan has stood.
        """
        now = utc_now()
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT created_at FROM agent_plans WHERE session_id = ? AND principal_id = ?",
                (session_id, principal_id),
            ).fetchone()
            created_at = str(existing["created_at"]) if existing is not None else now
            connection.execute(
                """INSERT OR REPLACE INTO agent_plans
                   (session_id, principal_id, turn_id, steps_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, principal_id, turn_id, steps_json, created_at, now),
            )
        return now

    def load_agent_plan(self, session_id: str, principal_id: str) -> dict[str, Any] | None:
        """This conversation's plan, or None. Owner-scoped: never cross-account."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM agent_plans WHERE session_id = ? AND principal_id = ?",
                (session_id, principal_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def clear_agent_plan(self, session_id: str, principal_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM agent_plans WHERE session_id = ? AND principal_id = ?",
                (session_id, principal_id),
            )
            return cursor.rowcount > 0

    # ── turn sources (C6/C4 — where a turn's answer came from) ───────────────

    def record_turn_sources(
        self, *, session_id: str, turn_id: str, principal_id: str, rows: list[dict[str, Any]]
    ) -> None:
        """Append this turn's newly used sources, keeping the order they arrived.

        ``INSERT OR IGNORE`` rather than ``REPLACE``: a source id is assigned
        once per turn and a re-run of the same turn (a resumed one, say) must
        not rewrite the row a chip is already pointing at.
        """
        if not rows:
            return
        now = utc_now()
        with self.connect() as connection:
            connection.executemany(
                """INSERT OR IGNORE INTO turn_sources
                   (session_id, turn_id, source_id, principal_id, ordinal, kind, title,
                    locator, tool_name, detail, attachment_id, passage, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        session_id,
                        turn_id,
                        str(row["source_id"]),
                        principal_id,
                        int(row["ordinal"]),
                        str(row.get("kind", "")),
                        str(row.get("title", "")),
                        str(row.get("locator", "")),
                        str(row.get("tool_name", "")),
                        str(row.get("detail", "")),
                        str(row.get("attachment_id", "")),
                        str(row.get("passage", "")),
                        now,
                    )
                    for row in rows
                ],
            )

    def count_turn_sources(self, session_id: str, turn_id: str, principal_id: str) -> int:
        """How many sources this turn has already recorded, for the next id."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS n FROM turn_sources "
                "WHERE session_id = ? AND turn_id = ? AND principal_id = ?",
                (session_id, turn_id, principal_id),
            ).fetchone()
        return int(row["n"]) if row is not None else 0

    def load_turn_sources(
        self, session_id: str, principal_id: str, turn_id: str | None = None
    ) -> list[dict[str, Any]]:
        """This conversation's recorded sources. Owner-scoped: never cross-account."""
        query = (
            "SELECT * FROM turn_sources WHERE session_id = ? AND principal_id = ?"
        )
        params: list[Any] = [session_id, principal_id]
        if turn_id:
            query += " AND turn_id = ?"
            params.append(turn_id)
        query += " ORDER BY created_at ASC, ordinal ASC"
        with self.connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def load_turn_source(
        self, session_id: str, turn_id: str, source_id: str, principal_id: str
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM turn_sources WHERE session_id = ? AND turn_id = ? "
                "AND source_id = ? AND principal_id = ?",
                (session_id, turn_id, source_id, principal_id),
            ).fetchone()
        return dict(row) if row is not None else None

    # ── turn controls (B17/C13 — stop or steer a turn that is running) ───────

    def request_turn_stop(
        self, session_id: str, principal_id: str, *, reason: str
    ) -> str:
        """Ask the turn running in this conversation to stop at its next boundary."""
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO turn_controls
                     (session_id, principal_id, stop_requested, stop_reason, steer_json, updated_at)
                   VALUES (?, ?, 1, ?, '[]', ?)
                   ON CONFLICT(session_id, principal_id) DO UPDATE SET
                     stop_requested = 1, stop_reason = excluded.stop_reason,
                     updated_at = excluded.updated_at""",
                (session_id, principal_id, reason, now),
            )
        return now

    def queue_turn_steer(self, session_id: str, principal_id: str, *, text: str) -> int:
        """Append one owner instruction for the running turn; returns the queue depth.

        Appending rather than replacing is deliberate: an owner who types two
        corrections while a turn runs meant both of them.
        """
        now = utc_now()
        with self.connect() as connection:
            row = connection.execute(
                "SELECT steer_json FROM turn_controls WHERE session_id = ? AND principal_id = ?",
                (session_id, principal_id),
            ).fetchone()
            queued: list[str] = []
            if row is not None:
                try:
                    parsed = json.loads(str(row["steer_json"]))
                    if isinstance(parsed, list):
                        queued = [str(item) for item in parsed]
                except ValueError:
                    queued = []
            queued.append(text)
            connection.execute(
                """INSERT INTO turn_controls
                     (session_id, principal_id, stop_requested, stop_reason, steer_json, updated_at)
                   VALUES (?, ?, 0, NULL, ?, ?)
                   ON CONFLICT(session_id, principal_id) DO UPDATE SET
                     steer_json = excluded.steer_json, updated_at = excluded.updated_at""",
                (session_id, principal_id, json.dumps(queued), now),
            )
        return len(queued)

    def take_turn_control(self, session_id: str, principal_id: str) -> dict[str, Any]:
        """Read and clear this conversation's pending controls, atomically.

        Consuming on read is what keeps a control from applying twice: a stop the
        loop has honoured must not also end the *next* turn, and a steer must
        reach the model once.
        """
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM turn_controls WHERE session_id = ? AND principal_id = ?",
                (session_id, principal_id),
            ).fetchone()
            if row is None:
                return {"stop_requested": False, "stop_reason": None, "steer_texts": []}
            connection.execute(
                "DELETE FROM turn_controls WHERE session_id = ? AND principal_id = ?",
                (session_id, principal_id),
            )
        try:
            parsed = json.loads(str(row["steer_json"]))
            steer = [str(item) for item in parsed] if isinstance(parsed, list) else []
        except ValueError:
            steer = []
        return {
            "stop_requested": bool(row["stop_requested"]),
            "stop_reason": row["stop_reason"],
            "steer_texts": steer,
        }

    def clear_turn_control(self, session_id: str, principal_id: str) -> None:
        """Drop anything left over before a new turn starts.

        A stop or steer that arrived between turns had no turn to act on; keeping
        it would apply the owner's decision to work they had not yet asked for.
        """
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM turn_controls WHERE session_id = ? AND principal_id = ?",
                (session_id, principal_id),
            )

    # ── suspended turns (B2 — resume the same turn after an approval) ─────────

    def insert_suspended_turn(self, record: dict[str, Any]) -> None:
        """Park one turn's working state against the approval that blocked it.

        ``INSERT OR REPLACE`` keyed on ``approval_id``: an approval blocks exactly
        one turn, and re-suspending the same approval is a re-park, not a second
        row.
        """
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO suspended_turns
                   (approval_id, session_id, turn_id, request_id, principal_id, action_id,
                    tool_name, call_id, prompt_text, messages_json, options_json, client_json,
                    tool_calls_made, status, outcome_json, created_at, resumed_at,
                    pending_calls_json, queue_position, queue_total)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'suspended', NULL, ?, NULL,
                           ?, ?, ?)""",
                (
                    record["approval_id"], record["session_id"], record["turn_id"],
                    record["request_id"], record["principal_id"], record["action_id"],
                    record["tool_name"], record["call_id"], record["prompt_text"],
                    record["messages_json"], record["options_json"], record["client_json"],
                    int(record.get("tool_calls_made", 0)), utc_now(),
                    # ADD-02 — the rest of the batch travels with the turn. A
                    # caller that parks a single call writes the defaults, which
                    # are exactly the pre-queue behaviour.
                    str(record.get("pending_calls_json") or "[]"),
                    int(record.get("queue_position", 1)),
                    int(record.get("queue_total", 1)),
                ),
            )

    def load_suspended_turn(
        self, approval_id: str, *, principal_id: str | None = None
    ) -> dict[str, Any] | None:
        """Load a parked turn. Scoping by principal keeps turns owner-isolated."""
        query = "SELECT * FROM suspended_turns WHERE approval_id = ?"
        params: tuple[Any, ...] = (approval_id,)
        if principal_id is not None:
            query += " AND principal_id = ?"
            params = (approval_id, principal_id)
        with self.connect() as connection:
            row = connection.execute(query, params).fetchone()
        return dict(row) if row is not None else None

    def list_resumable_suspended_turns(
        self, principal_id: str, session_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Parked turns whose approval has been resolved and which may resume (BUG-24).

        A turn qualifies only when it is still ``suspended`` *and* carries an
        ``outcome_json`` — that outcome is written when the approval is resolved,
        so its presence is exactly the "this approval has been decided" signal a
        Chat tab in another window needs. A turn already claimed by a resuming
        client has moved to ``resuming`` and is not listed, so two tabs polling
        together cannot both start the same continuation.

        Owner-scoped by principal: this can never reveal another account's turn.
        No conversation state is returned — ids and metadata only.
        """
        query = (
            "SELECT approval_id, session_id, turn_id, tool_name, outcome_json, created_at, "
            "queue_position, queue_total "
            "FROM suspended_turns WHERE principal_id = ? AND status = 'suspended' "
            "AND outcome_json IS NOT NULL"
        )
        params: tuple[Any, ...] = (principal_id,)
        if session_id is not None:
            query += " AND session_id = ?"
            params = (principal_id, session_id)
        query += " ORDER BY created_at ASC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def list_pending_suspended_turns(
        self, principal_id: str, session_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Metadata for unresolved parked turns, scoped to their owner (BUG-34)."""
        query = (
            "SELECT approval_id, session_id, turn_id, tool_name, created_at, "
            "queue_position, queue_total "
            "FROM suspended_turns WHERE principal_id = ? AND status = 'suspended' "
            "AND outcome_json IS NULL"
        )
        params: tuple[Any, ...] = (principal_id,)
        if session_id is not None:
            query += " AND session_id = ?"
            params = (principal_id, session_id)
        query += " ORDER BY created_at ASC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def suspended_turn_queue_positions(
        self, approval_ids: Sequence[str]
    ) -> dict[str, tuple[int, int]]:
        """Where each approval sits in the batch its turn parked on (ADD-02).

        Approvals themselves know nothing about batching — an approval is one
        action. The batch is a property of the parked turn, so this is the join
        that lets the Approvals list say "decision 2 of 3" without teaching the
        approvals table about tool-call queues. Metadata only: two integers, no
        conversation state, and an approval with no parked turn is simply absent.
        """
        ids = [str(approval_id) for approval_id in approval_ids if approval_id]
        if not ids:
            return {}
        positions: dict[str, tuple[int, int]] = {}
        with self.connect() as connection:
            # Chunked so a long pending list cannot exceed SQLite's variable limit.
            for start in range(0, len(ids), 400):
                chunk = ids[start : start + 400]
                placeholders = ",".join("?" for _ in chunk)
                rows = connection.execute(
                    "SELECT approval_id, queue_position, queue_total FROM suspended_turns "
                    f"WHERE approval_id IN ({placeholders})",
                    chunk,
                ).fetchall()
                for row in rows:
                    positions[str(row["approval_id"])] = (
                        int(row["queue_position"] or 1),
                        int(row["queue_total"] or 1),
                    )
        return positions

    def record_suspended_turn_outcome(self, approval_id: str, outcome_json: str) -> bool:
        """Attach the resolution outcome the model will see as its tool result.

        Guarded on ``suspended`` so a resumed (or abandoned) turn cannot have its
        outcome rewritten after the model has already acted on it.
        """
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE suspended_turns SET outcome_json = ? "
                "WHERE approval_id = ? AND status = 'suspended'",
                (outcome_json, approval_id),
            )
        return cursor.rowcount == 1

    def claim_suspended_turn(self, approval_id: str) -> bool:
        """Atomically claim a parked turn for resumption (suspended → resuming).

        The single-resumption primitive: a turn's working state may be replayed
        into the model exactly once, so a double-click or a racing client cannot
        run the continuation twice.
        """
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE suspended_turns SET status = 'resuming', resumed_at = ? "
                "WHERE approval_id = ? AND status = 'suspended'",
                (utc_now(), approval_id),
            )
        return cursor.rowcount == 1

    def finalize_suspended_turn(self, approval_id: str, *, status: str) -> bool:
        """Resolve a claimed turn to a terminal state (resuming → status)."""
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE suspended_turns SET status = ? WHERE approval_id = ? AND status = 'resuming'",
                (status, approval_id),
            )
        return cursor.rowcount == 1

    # ── scoped standing approval grants (Workstream F / F3, ZT-5) ─────────────

    def insert_standing_grant(self, record: dict[str, Any]) -> None:
        """Persist a scoped standing grant. All fields are metadata only.

        The caller (the grant engine) is responsible for the invariants — a
        human ``granted_by``, a sub-critical ``risk_ceiling``, and a mandatory
        ``expires_at``. This method only writes the row it is given.
        """
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO standing_grants
                (grant_id, principal_id, granted_by, action_type, tool_name,
                 scope_pattern, risk_ceiling, reason, created_at, expires_at,
                 revoked, revoked_at, revoked_by, use_count, last_used_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, NULL, 0, NULL)
                """,
                (
                    record["grant_id"],
                    record["principal_id"],
                    record["granted_by"],
                    record["action_type"],
                    record.get("tool_name", ""),
                    record.get("scope_pattern", "*"),
                    record["risk_ceiling"],
                    record.get("reason", ""),
                    record["created_at"],
                    record["expires_at"],
                ),
            )

    def load_standing_grant(self, grant_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM standing_grants WHERE grant_id = ?", (grant_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_standing_grants(
        self, *, granted_by: str | None = None, include_inactive: bool = True
    ) -> list[dict[str, Any]]:
        """Grants for Security Settings, newest first.

        ``granted_by`` scopes to a single owner (isolation). ``include_inactive``
        controls whether revoked/expired grants are listed — the Security
        Settings surface lists everything so the owner sees the full history.
        """
        conditions: list[str] = []
        params: list[Any] = []
        if granted_by is not None:
            conditions.append("granted_by = ?")
            params.append(granted_by)
        if not include_inactive:
            conditions.append("revoked = 0")
            conditions.append("expires_at > ?")
            params.append(utc_now())
        where = f"WHERE {' AND '.join(conditions)} " if conditions else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM standing_grants {where}ORDER BY created_at DESC, rowid DESC",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def find_active_standing_grants(
        self, principal_id: str, action_type: str
    ) -> list[dict[str, Any]]:
        """Active (non-revoked, unexpired) grants for a principal + action type."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM standing_grants
                WHERE principal_id = ? AND action_type = ?
                  AND revoked = 0 AND expires_at > ?
                ORDER BY created_at DESC
                """,
                (principal_id, action_type, utc_now()),
            ).fetchall()
        return [dict(row) for row in rows]

    def revoke_standing_grant(
        self, grant_id: str, *, revoked_by: str, granted_by: str | None = None
    ) -> bool:
        """Owner-scoped revoke. Returns False if missing, already revoked, or
        owned by another principal (isolation)."""
        conditions = ["grant_id = ?", "revoked = 0"]
        params: list[Any] = [utc_now(), revoked_by, grant_id]
        if granted_by is not None:
            conditions.append("granted_by = ?")
            params.append(granted_by)
        with self.connect() as connection:
            cursor = connection.execute(
                f"UPDATE standing_grants SET revoked = 1, revoked_at = ?, revoked_by = ? "
                f"WHERE {' AND '.join(conditions)}",
                params,
            )
        return cursor.rowcount == 1

    def record_standing_grant_use(self, grant_id: str) -> None:
        """Increment a grant's use counter (every use is logged with the id)."""
        with self.connect() as connection:
            connection.execute(
                "UPDATE standing_grants SET use_count = use_count + 1, last_used_at = ? "
                "WHERE grant_id = ?",
                (utc_now(), grant_id),
            )

    def load_api_session(self, session_id: str) -> dict[str, Any] | None:
        """Best-effort lookup of an API session row by id (posture snapshots)."""
        if not session_id:
            return None
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM api_sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return dict(row) if row else None

    def principal_mfa_enrolled(self, principal_id: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT mfa_enrolled FROM account_credentials WHERE principal_id = ?",
                (principal_id,),
            ).fetchone()
        return bool(row["mfa_enrolled"]) if row else False

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

    def insert_checkpoint_capture_entry(
        self,
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
        self,
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
                (task_id, session_id, parent_turn_id, parent_task_id, title, objective, status, current_step, progress_percent, created_at, updated_at, completed_at, priority, scheduled_at, recurrence, reminder_at, project_id, model_profile, model, attachments_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    task.model_profile,
                    task.model,
                    json.dumps(task.attachments, sort_keys=True),
                ),
            )

    @staticmethod
    def _task_from_row(row: Any) -> TaskRecord:
        data = dict(row)
        raw_attachments = data.pop("attachments_json", "[]")
        try:
            attachments = json.loads(raw_attachments or "[]")
        except (TypeError, ValueError):
            attachments = []
        data["attachments"] = attachments if isinstance(attachments, list) else []
        return TaskRecord(**data)

    def load_task(self, task_id: str) -> TaskRecord | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        return self._task_from_row(row)

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
        return [self._task_from_row(row) for row in rows]

    def claim_due_tasks(self, now: str, limit: int = 10) -> list[TaskRecord]:
        """Atomically claim scheduled work so two host ticks cannot run it twice."""
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM tasks WHERE status = 'queued' AND scheduled_at IS NOT NULL
                   AND scheduled_at <= ? ORDER BY scheduled_at ASC LIMIT ?""",
                (now, limit),
            ).fetchall()
            claimed: list[TaskRecord] = []
            for row in rows:
                if connection.execute(
                    "UPDATE tasks SET status = 'running', current_step = ?, updated_at = ? WHERE task_id = ? AND status = 'queued'",
                    ("Starting scheduled run", now, row["task_id"]),
                ).rowcount:
                    claimed.append(self._task_from_row(row))
        return claimed

    def schedule_task_now(
        self, task_id: str, *, user_id: str | None
    ) -> tuple[TaskRecord | None, str | None]:
        """Atomically make one owner-visible parked task due (BUG-64)."""
        now = utc_now()
        with self.connect() as connection:
            params: list[Any] = [task_id]
            ownership = ""
            if user_id is not None:
                ownership = (
                    " AND session_id IN (SELECT session_id FROM sessions "
                    "WHERE user_id = ? OR user_id IS NULL)"
                )
                params.append(user_id)
            row = connection.execute(
                f"SELECT * FROM tasks WHERE task_id = ?{ownership}", params
            ).fetchone()
            if row is None:
                return None, "task_not_found"
            if row["scheduled_at"] is not None:
                return None, "task_already_scheduled"
            if row["status"] != "queued":
                return None, "task_not_runnable"
            updated = connection.execute(
                "UPDATE tasks SET scheduled_at = ?, updated_at = ?, current_step = ? "
                "WHERE task_id = ? AND status = 'queued' AND scheduled_at IS NULL",
                (now, now, "Ready to start", task_id),
            )
            if updated.rowcount != 1:
                return None, "task_not_runnable"
            scheduled = connection.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
        return self._task_from_row(scheduled), None

    def reschedule_task(self, task_id: str, scheduled_at: str, summary: str) -> None:
        self._update_task(task_id, status="queued", scheduled_at=scheduled_at, current_step="Waiting for next scheduled run", progress_percent=0, completed_at=None, summary=summary)

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

    def resume_task_after_approval(self, task_id: str, current_step: str) -> None:
        """Move a parked task back to running as its continuation starts (BUG-25).

        Guarded on ``waiting_for_approval`` so a task the owner cancelled, or one
        another continuation already picked up, is never dragged back to running.
        """
        with self.connect() as connection:
            connection.execute(
                "UPDATE tasks SET status = 'continuing', current_step = ?, summary = NULL, "
                "updated_at = ? WHERE task_id = ? AND status = 'waiting_for_approval'",
                (current_step, utc_now(), task_id),
            )

    def block_task_on_approval(self, task_id: str, reason: str) -> None:
        """A run reached an approval boundary: blocked, not finished.

        No ``completed_at`` is stamped — the work is unfinished and the owner's
        decision is what moves it. Recording it as `failed` (BUG-09) told the
        owner the run had gone wrong when nothing had.
        """
        self._update_task(
            task_id,
            status="waiting_for_approval",
            current_step="Waiting for your approval",
            summary=reason,
        )

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
        query = """
            SELECT events_index.*, machine.principal_id AS proposed_by,
                   machine.subject AS machine_subject,
                   machine.key_id AS machine_key_id,
                   machine.issued_at AS machine_issued_at,
                   machine.expires_at AS machine_expires_at,
                   machine.is_active AS machine_is_active,
                   proposer.principal_type AS proposer_principal_type,
                   proposer.display_name AS proposer_display_name
            FROM events_index
            LEFT JOIN turn_machine_identities AS machine
              ON machine.principal_id = (
                SELECT identity.principal_id
                FROM turn_machine_identities AS identity
                WHERE identity.session_id = events_index.session_id
                  AND identity.turn_id = events_index.turn_id
                ORDER BY identity.issued_at DESC LIMIT 1
              )
            LEFT JOIN principals AS proposer
              ON proposer.principal_id = machine.principal_id
        """
        params: list[Any] = []
        conditions: list[str] = []
        if session_id is not None:
            conditions.append("events_index.session_id = ?")
            params.append(session_id)
        if turn_id is not None:
            conditions.append("events_index.turn_id = ?")
            params.append(turn_id)
        if task_id is not None:
            conditions.append("events_index.task_id = ?")
            params.append(task_id)
        if event_type is not None:
            conditions.append("events_index.event_type = ?")
            params.append(event_type)
        if project_id is not None:
            conditions.append(
                "events_index.session_id IN (SELECT session_id FROM sessions WHERE project_id = ?)"
            )
            params.append(project_id)
        if apply_user_visibility_filter:
            if user_id is None:
                conditions.append(
                    "events_index.session_id IN (SELECT session_id FROM sessions WHERE user_id IS NULL)"
                )
            else:
                conditions.append(
                    "events_index.session_id IN (SELECT session_id FROM sessions "
                    "WHERE user_id = ? OR user_id IS NULL)"
                )
                params.append(user_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY events_index.timestamp DESC, events_index.rowid DESC LIMIT ?"
        params.append(str(limit))
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def all_session_ids(self) -> set[str]:
        """Every conversation session id in this workspace, whoever owns it.

        Read by the audit log (BUG-87) to tell a runtime channel — an event
        recorded outside any conversation — from another user's conversation.
        It carries no ownership, so it is never used to decide what to *show*,
        only what is not a conversation in the first place.
        """
        with self.connect() as connection:
            rows = connection.execute("SELECT session_id FROM sessions").fetchall()
        return {str(row["session_id"]) for row in rows}

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

    def count_pending_approvals(self, session_id: str | None = None) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS cnt FROM approvals WHERE status = 'pending'"
                + (" AND action_id IN (SELECT action_id FROM tool_actions WHERE session_id = ?)" if session_id else ""),
                (session_id,) if session_id else (),
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

    def list_approvals(
        self,
        status: str | None = None,
        *,
        user_id: str | None = None,
        principal_id: str | None = None,
    ) -> list[dict[str, Any]]:
        # Most approvals inherit their owner through a chat session. Connector
        # store writes are deliberately sessionless, so their immutable intent
        # binds ownership to the proposing principal instead.
        query = """
            SELECT approvals.*, tool_actions.session_id, tool_actions.turn_id,
                   tool_actions.tool_name, tool_actions.arguments_json,
                   tool_actions.risk_level, tool_actions.proposed_by,
                   tool_actions.owner_principal_id, tool_actions.machine_subject,
                   tool_actions.machine_token_id,
                   proposer.principal_type AS proposer_principal_type,
                   proposer.display_name AS proposer_display_name,
                   tool_actions.machine_key_id,
                   tool_actions.machine_issued_at,
                   tool_actions.machine_expires_at,
                   machine.is_active AS machine_is_active,
                   authorizer.principal_type AS authorizer_principal_type,
                   authorizer.display_name AS authorizer_display_name
            FROM approvals
            JOIN tool_actions ON approvals.action_id = tool_actions.action_id
            LEFT JOIN principals AS proposer
              ON proposer.principal_id = tool_actions.proposed_by
            LEFT JOIN turn_machine_identities AS machine
              ON machine.principal_id = tool_actions.proposed_by
            LEFT JOIN principals AS authorizer
              ON authorizer.principal_id = approvals.approved_by
        """
        params: list[Any] = []
        clauses: list[str] = []
        if principal_id is not None:
            query += """
                LEFT JOIN sessions ON tool_actions.session_id = sessions.session_id
                LEFT JOIN connector_write_intents
                    ON connector_write_intents.approval_id = approvals.approval_id
            """
            if user_id is None:
                clauses.append("connector_write_intents.principal_id = ?")
                params.append(principal_id)
            else:
                clauses.append("(sessions.user_id = ? OR connector_write_intents.principal_id = ?)")
                params.extend((user_id, principal_id))
        elif user_id is not None:
            query += " JOIN sessions ON tool_actions.session_id = sessions.session_id AND sessions.user_id = ?"
            params.append(user_id)
        if status is not None:
            clauses.append("approvals.status = ?")
            params.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY approvals.created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def load_approval(
        self,
        approval_id: str,
        *,
        user_id: str | None = None,
        principal_id: str | None = None,
    ) -> dict[str, Any] | None:
        # The normal owner filter is session-based. Connector-store writes have
        # no session row, so their immutable intent is the owner binding.
        owner_join = ""
        owner_filter = ""
        params: tuple[Any, ...]
        if principal_id is not None:
            owner_join = """
                LEFT JOIN sessions ON tool_actions.session_id = sessions.session_id
                LEFT JOIN connector_write_intents
                    ON connector_write_intents.approval_id = approvals.approval_id
            """
            if user_id is None:
                owner_filter = " AND connector_write_intents.principal_id = ?"
                params = (approval_id, principal_id)
            else:
                owner_filter = " AND (sessions.user_id = ? OR connector_write_intents.principal_id = ?)"
                params = (approval_id, user_id, principal_id)
        elif user_id is not None:
            owner_join = (
                " JOIN sessions ON tool_actions.session_id = sessions.session_id"
                " AND sessions.user_id = ?"
            )
            params = (user_id, approval_id)
        else:
            params = (approval_id,)
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT approvals.*, tool_actions.session_id, tool_actions.turn_id,
                       tool_actions.tool_name, tool_actions.arguments_json,
                       tool_actions.risk_level, tool_actions.proposed_by,
                       tool_actions.owner_principal_id, tool_actions.machine_subject,
                       tool_actions.machine_token_id,
                       proposer.principal_type AS proposer_principal_type,
                       proposer.display_name AS proposer_display_name,
                       tool_actions.machine_key_id,
                       tool_actions.machine_issued_at,
                       tool_actions.machine_expires_at,
                       machine.is_active AS machine_is_active,
                       authorizer.principal_type AS authorizer_principal_type,
                       authorizer.display_name AS authorizer_display_name
                FROM approvals
                JOIN tool_actions ON approvals.action_id = tool_actions.action_id
                LEFT JOIN principals AS proposer
                  ON proposer.principal_id = tool_actions.proposed_by
                LEFT JOIN turn_machine_identities AS machine
                  ON machine.principal_id = tool_actions.proposed_by
                LEFT JOIN principals AS authorizer
                  ON authorizer.principal_id = approvals.approved_by
                """ + owner_join + """
                WHERE approvals.approval_id = ?
                """ + owner_filter,
                params,
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

    def insert_memory_candidate(self, candidate: Any, *, owner_principal_id: str | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO memory_candidates
                (candidate_id, source_event_id, memory_type, scope, text, sensitivity, confidence, decision, created_at, owner_principal_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    owner_principal_id,
                ),
            )

    def list_memory_candidates(self, decision: str | None = None, *, owner_principal_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM memory_candidates"
        params: list[Any] = []
        if decision is not None:
            query += " WHERE decision = ?"
            params.append(decision)
        if owner_principal_id is not None:
            query += " AND" if params else " WHERE"
            query += " owner_principal_id = ?"
            params.append(owner_principal_id)
        query += " ORDER BY created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_memory_candidate(
        self, candidate_id: str, *, owner_principal_id: str
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM memory_candidates WHERE candidate_id = ? AND owner_principal_id = ?",
                (candidate_id, owner_principal_id),
            ).fetchone()
        return dict(row) if row else None

    def resolve_memory_candidate(
        self,
        candidate_id: str,
        *,
        owner_principal_id: str,
        expected_decision: str,
        decision: str,
        reason: str | None,
        resolved_at: str,
    ) -> bool:
        """Resolve exactly one proposal without allowing stale double decisions."""
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE memory_candidates
                SET decision = ?, reason = ?, resolved_at = ?
                WHERE candidate_id = ? AND owner_principal_id = ? AND decision = ?""",
                (
                    decision,
                    reason,
                    resolved_at,
                    candidate_id,
                    owner_principal_id,
                    expected_decision,
                ),
            )
        return cursor.rowcount == 1

    def insert_approved_memory(self, entry: Any) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO approved_memory
                (memory_id, text, scope, sensitivity, source_event_id, memory_type, created_at, tags_json, source, provenance_json, confidence, trust_score, retention, approval_state, created_by, updated_at, deleted_at, archived_at, search_enabled, expires_at, valid_from, valid_until, supersedes_memory_id, superseded_at, remembered_reason, content_checksum, owner_principal_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    hashlib.sha256(entry.text.encode()).hexdigest(),
                    entry.owner_principal_id,
                ),
            )
            self._sync_memory_fts(connection, entry.memory_id)
            self._sync_memory_projection_eligibility(connection, entry.memory_id)

    def update_approved_memory(self, entry: Any) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE approved_memory SET text = ?, content_checksum = ?, scope = ?, sensitivity = ?, tags_json = ?, updated_at = ?,
                search_enabled = ?, expires_at = ?, valid_from = ?, valid_until = ?,
                supersedes_memory_id = ?, superseded_at = ?, remembered_reason = ?
                WHERE memory_id = ? AND deleted_at IS NULL"""
                + (" AND owner_principal_id = ?" if entry.owner_principal_id else ""),
                (
                    entry.text,
                    hashlib.sha256(entry.text.encode()).hexdigest(),
                    entry.scope,
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
                    *([entry.owner_principal_id] if entry.owner_principal_id else []),
                ),
            )
            self._sync_memory_fts(connection, entry.memory_id)
            self._sync_memory_projection_eligibility(connection, entry.memory_id)
        return cursor.rowcount > 0

    def supersede_approved_memory(
        self, memory_id: str, replacement_id: str, *, at: str, owner_principal_id: str | None = None
    ) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE approved_memory SET approval_state = 'superseded', valid_until = ?, superseded_at = ?,
                updated_at = ? WHERE memory_id = ? AND deleted_at IS NULL AND superseded_at IS NULL"""
                + (" AND owner_principal_id = ?" if owner_principal_id else ""),
                (at, at, at, memory_id, *([owner_principal_id] if owner_principal_id else [])),
            )
            self._sync_memory_fts(connection, memory_id)
            self._sync_memory_projection_eligibility(connection, memory_id)
            connection.execute(
                "UPDATE approved_memory SET supersedes_memory_id = ? WHERE memory_id = ?"
                + (" AND owner_principal_id = ?" if owner_principal_id else ""),
                (memory_id, replacement_id, *([owner_principal_id] if owner_principal_id else [])),
            )
        return cursor.rowcount > 0

    def create_memory_evaluation_run(self, report: Any, *, strategy: str | None = None) -> str:
        from raiker.contracts.ids import new_id

        evaluation_id = new_id("mev_")
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO memory_evaluation_runs (
                    evaluation_id, corpus_version, strategy, case_count, precision_at_k,
                    recall_at_k, mean_reciprocal_rank, ndcg_at_k, policy_leak_count,
                    p50_latency_ms, p95_latency_ms, token_count, compute_cost_usd,
                    storage_bytes, created_at, backend_version, scope, workload,
                    latency_distribution_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (evaluation_id, report.corpus_version, strategy or report.strategy, report.case_count, report.precision_at_k,
                 report.recall_at_k, report.mean_reciprocal_rank, report.ndcg_at_k,
                 report.policy_leak_count, report.p50_latency_ms, report.p95_latency_ms,
                 report.token_count, report.compute_cost_usd, report.storage_bytes, utc_now(),
                 report.backend_version, report.scope, report.workload,
                 json.dumps(report.latency_distribution, sort_keys=True)),
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

    def create_memory_relationship_candidate(
        self, candidate_id: str, *, subject_name: str, subject_type: str, predicate: str,
        object_name: str, object_type: str, evidence_memory_id: str, confidence: float,
    ) -> None:
        if not all(value.strip() for value in (subject_name, subject_type, predicate, object_name, object_type)):
            raise ValueError("invalid_memory_relationship_candidate")
        if not 0 <= confidence <= 1 or self.get_active_approved_memory(evidence_memory_id) is None:
            raise ValueError("invalid_memory_relationship_candidate")
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO memory_relationship_candidates VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                'needs_user_review', ?, NULL, NULL)""",
                (candidate_id, subject_name.strip(), subject_type.strip(), predicate.strip(), object_name.strip(),
                 object_type.strip(), evidence_memory_id, confidence, utc_now()),
            )

    def get_memory_relationship_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM memory_relationship_candidates WHERE candidate_id = ?", (candidate_id,)
            ).fetchone()
        return dict(row) if row else None

    def resolve_memory_relationship_candidate(
        self, candidate_id: str, *, decision: str, resolved_by: str,
    ) -> bool:
        if decision not in {"approved", "denied"} or not resolved_by.strip():
            raise ValueError("invalid_memory_relationship_resolution")
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE memory_relationship_candidates SET decision = ?, resolved_at = ?, resolved_by = ?
                WHERE candidate_id = ? AND decision = 'needs_user_review'""",
                (decision, utc_now(), resolved_by, candidate_id),
            )
        return cursor.rowcount > 0

    def list_memory_entity_neighborhood(
        self, entity_id: str, scope: str | None = None, *, owner_principal_id: str | None = None
    ) -> list[dict[str, Any]]:
        now = utc_now()
        query = """SELECT r.*, s.display_name AS subject_name, o.display_name AS object_name
        FROM memory_entity_relationships r JOIN memory_entities s ON s.entity_id = r.subject_entity_id
        JOIN memory_entities o ON o.entity_id = r.object_entity_id
        JOIN approved_memory m ON m.memory_id = r.evidence_memory_id
        WHERE r.active = 1 AND (r.subject_entity_id = ? OR r.object_entity_id = ?)
          AND m.deleted_at IS NULL AND m.archived_at IS NULL AND m.search_enabled = 1
          AND m.sensitivity NOT IN ('secret_like', 'credential_like')
          AND (m.expires_at IS NULL OR m.expires_at > ?)
          AND (m.valid_from IS NULL OR m.valid_from <= ?)
          AND (m.valid_until IS NULL OR m.valid_until > ?) AND m.superseded_at IS NULL"""
        params: list[Any] = [entity_id, entity_id, now, now, now]
        if owner_principal_id:
            query += " AND m.owner_principal_id = ?"
            params.append(owner_principal_id)
        if scope:
            query += " AND m.scope = ?"
            params.append(scope)
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def mark_approved_memory_forgotten(
        self, memory_id: str, *, deleted_at: str, updated_at: str,
        owner_principal_id: str | None = None,
    ) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE approved_memory
                SET approval_state = ?, deleted_at = ?, updated_at = ?
                WHERE memory_id = ? AND deleted_at IS NULL"""
                + (" AND owner_principal_id = ?" if owner_principal_id else ""),
                ("forgotten", deleted_at, updated_at, memory_id, *([owner_principal_id] if owner_principal_id else [])),
            )
            self._sync_memory_fts(connection, memory_id)
            self._sync_memory_projection_eligibility(connection, memory_id)
        return cursor.rowcount > 0

    def set_approved_memory_archived(self, memory_id: str, *, archived_at: str | None, updated_at: str | None, owner_principal_id: str | None = None) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE approved_memory SET archived_at = ?, updated_at = ? WHERE memory_id = ? AND deleted_at IS NULL"
                + (" AND owner_principal_id = ?" if owner_principal_id else ""),
                (archived_at, updated_at, memory_id, *([owner_principal_id] if owner_principal_id else [])),
            )
            self._sync_memory_fts(connection, memory_id)
            self._sync_memory_projection_eligibility(connection, memory_id)
        return cursor.rowcount > 0

    def create_memory_purge_record(self, purge_id: str, memory_id: str, requested_by: str, confirmed_at: str, disposition: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute("INSERT INTO memory_purge_records (purge_id, memory_id, requested_by, confirmed_at, disposition_json) VALUES (?, ?, ?, ?, ?)", (purge_id, memory_id, requested_by, confirmed_at, json.dumps(disposition, sort_keys=True)))

    def deactivate_memory_projections(self, memory_id: str) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE memory_projections SET active = 0 WHERE memory_id = ?", (memory_id,))

    def set_memory_projections_active(self, memory_id: str, active: bool) -> None:
        with self.connect() as connection:
            self._sync_memory_projection_eligibility(connection, memory_id, enabled=active)

    @staticmethod
    def _sync_memory_projection_eligibility(
        connection: sqlite3.Connection, memory_id: str, *, enabled: bool = True
    ) -> None:
        now = utc_now()
        connection.execute(
            """UPDATE memory_projections SET active = CASE WHEN ? = 1 AND EXISTS (
                SELECT 1 FROM approved_memory m WHERE m.memory_id = memory_projections.memory_id
                AND m.deleted_at IS NULL AND m.archived_at IS NULL AND m.search_enabled = 1
                AND (m.expires_at IS NULL OR m.expires_at > ?)
                AND (m.valid_from IS NULL OR m.valid_from <= ?)
                AND (m.valid_until IS NULL OR m.valid_until > ?) AND m.superseded_at IS NULL
            ) THEN 1 ELSE 0 END WHERE memory_id = ?""",
            (int(enabled), now, now, now, memory_id),
        )

    def link_memory_projection(self, memory_id: str, projection_type: str, projection_id: str, source_version: str, *, owner_principal_id: str | None = None) -> None:
        if projection_type not in {"fts", "vector", "graph"}:
            raise ValueError("invalid_memory_projection_type")
        with self.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM approved_memory WHERE memory_id = ?" + (" AND owner_principal_id = ?" if owner_principal_id else ""),
                (memory_id, *([owner_principal_id] if owner_principal_id else [])),
            ).fetchone()
            if row is None:
                raise ValueError("unknown_memory")
            connection.execute(
                "INSERT OR REPLACE INTO memory_projections (memory_id, projection_type, projection_id, source_version, active) VALUES (?, ?, ?, ?, ?)",
                (memory_id, projection_type, projection_id, source_version, 0),
            )
            self._sync_memory_projection_eligibility(connection, memory_id)

    def list_memory_projections(self, memory_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM memory_projections WHERE memory_id = ? ORDER BY projection_type, projection_id", (memory_id,)).fetchall()
        return [dict(row) for row in rows]

    def get_active_approved_memory(
        self, memory_id: str, *, owner_principal_id: str | None = None
    ) -> dict[str, Any] | None:
        now = utc_now()
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM approved_memory WHERE memory_id = ? AND deleted_at IS NULL
                AND archived_at IS NULL AND search_enabled = 1
                AND sensitivity NOT IN ('secret_like', 'credential_like')
                AND (expires_at IS NULL OR expires_at > ?)
                AND (valid_from IS NULL OR valid_from <= ?)
                AND (valid_until IS NULL OR valid_until > ?) AND superseded_at IS NULL"""
                + (" AND owner_principal_id = ?" if owner_principal_id else ""),
                (memory_id, now, now, now, *([owner_principal_id] if owner_principal_id else [])),
            ).fetchone()
        return dict(row) if row else None

    def reconcile_memory_projections(self, *, owner_principal_id: str | None = None) -> dict[str, int]:
        with self.connect() as connection:
            now = utc_now()
            cursor = connection.execute(
                """UPDATE memory_projections SET active = CASE WHEN EXISTS (
                    SELECT 1 FROM approved_memory m WHERE m.memory_id = memory_projections.memory_id
                    AND m.deleted_at IS NULL AND m.archived_at IS NULL AND m.search_enabled = 1
                    AND m.sensitivity NOT IN ('secret_like', 'credential_like')
                    AND (m.expires_at IS NULL OR m.expires_at > ?)
                    AND (m.valid_from IS NULL OR m.valid_from <= ?)
                    AND (m.valid_until IS NULL OR m.valid_until > ?) AND m.superseded_at IS NULL
                ) THEN 1 ELSE 0 END"""
                + (" WHERE memory_id IN (SELECT memory_id FROM approved_memory WHERE owner_principal_id = ?)" if owner_principal_id else ""),
                (now, now, now, *([owner_principal_id] if owner_principal_id else [])),
            )
            if owner_principal_id is None:
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
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower():
                raise
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

    def search_approved_memory(
        self, query: str, scope: str | None = None, limit: int = 20,
        *, owner_principal_id: str | None = None,
    ) -> list[dict[str, Any]]:
        terms = [term for term in query.replace('"', " ").replace("-", " ").split() if len(term) >= 3]
        if not terms:
            return []
        sql = """SELECT m.* FROM approved_memory_fts f JOIN approved_memory m ON m.memory_id = f.memory_id
        WHERE approved_memory_fts MATCH ? AND m.deleted_at IS NULL AND m.archived_at IS NULL
          AND m.search_enabled = 1 AND m.sensitivity NOT IN ('secret_like', 'credential_like')
          AND (m.expires_at IS NULL OR m.expires_at > ?)
          AND (m.valid_from IS NULL OR m.valid_from <= ?) AND (m.valid_until IS NULL OR m.valid_until > ?)
          AND m.superseded_at IS NULL"""
        now = utc_now()
        params: list[Any] = [" ".join(terms), now, now, now]
        if scope is not None:
            sql += " AND m.scope = ?"
            params.append(scope)
        if owner_principal_id:
            sql += " AND m.owner_principal_id = ?"
            params.append(owner_principal_id)
        sql += " ORDER BY m.created_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def delete_approved_memory(self, memory_id: str, *, owner_principal_id: str | None = None) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM approved_memory_fts WHERE memory_id = ?", (memory_id,))
            connection.execute(
                "DELETE FROM approved_memory WHERE memory_id = ?"
                + (" AND owner_principal_id = ?" if owner_principal_id else ""),
                (memory_id, *([owner_principal_id] if owner_principal_id else [])),
            )

    def list_approved_memory(
        self, scope: str | None = None, limit: int = 50, *, include_search_disabled: bool = False,
        owner_principal_id: str | None = None,
    ) -> list[dict[str, Any]]:
        now = utc_now()
        query = """SELECT * FROM approved_memory WHERE deleted_at IS NULL AND archived_at IS NULL
        AND (expires_at IS NULL OR expires_at > ?)
        AND (valid_from IS NULL OR valid_from <= ?) AND (valid_until IS NULL OR valid_until > ?)
        AND superseded_at IS NULL"""
        params: list[Any] = [now, now, now]
        if not include_search_disabled:
            query += " AND search_enabled = 1"
        if scope is not None:
            query += " AND scope = ?"
            params.append(scope)
        if owner_principal_id:
            query += " AND owner_principal_id = ?"
            params.append(owner_principal_id)
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

    def load_model_setup_state(self, owner_principal_id: str) -> ModelSetupState:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM model_setup_state WHERE owner_principal_id = ?",
                (owner_principal_id,),
            ).fetchone()
        if row is None:
            return ModelSetupState(owner_principal_id=owner_principal_id)
        return ModelSetupState(**dict(row))

    def save_model_operation(self, operation: ModelOperation) -> ModelOperation:
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO model_operations
                (operation_id, owner_principal_id, kind, target, state, phase,
                 progress_bytes, total_bytes, progress_percent, source_url, destination,
                 error_code, error_detail, created_at, updated_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                tuple(operation.to_row().values()),
            )
        return operation

    def save_model_library_root(self, owner_principal_id: str, path: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO model_library_roots (owner_principal_id, path, created_at) VALUES (?, ?, ?)",
                (owner_principal_id, path, utc_now()),
            )

    def list_model_library_roots(self, owner_principal_id: str) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT path FROM model_library_roots WHERE owner_principal_id = ? ORDER BY path",
                (owner_principal_id,),
            ).fetchall()
        return [str(row["path"]) for row in rows]

    def delete_model_library_root(self, owner_principal_id: str, path: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM model_library_roots WHERE owner_principal_id = ? AND path = ?",
                (owner_principal_id, path),
            )
            connection.execute(
                "DELETE FROM local_models WHERE owner_principal_id = ? AND root_path = ?",
                (owner_principal_id, path),
            )
        return cursor.rowcount == 1

    def replace_local_models(self, owner_principal_id: str, models: list[LocalModel]) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM local_models WHERE owner_principal_id = ?", (owner_principal_id,))
            connection.executemany(
                """INSERT INTO local_models
                (owner_principal_id, root_path, model_id, name, architecture, quantization,
                 primary_path, shard_count, expected_shards, complete, size_bytes, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(
                    model.owner_principal_id, model.root_path, model.model_id, model.name,
                    model.architecture, model.quantization, model.primary_path, model.shard_count,
                    model.expected_shards, int(model.complete), model.size_bytes, model.indexed_at,
                ) for model in models],
            )

    def list_local_models(self, owner_principal_id: str) -> list[LocalModel]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM local_models WHERE owner_principal_id = ? ORDER BY name, model_id",
                (owner_principal_id,),
            ).fetchall()
        return [LocalModel(**(dict(row) | {"complete": bool(row["complete"])})) for row in rows]

    def list_model_operations(self, owner_principal_id: str) -> list[ModelOperation]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM model_operations WHERE owner_principal_id = ? ORDER BY created_at DESC",
                (owner_principal_id,),
            ).fetchall()
        return [ModelOperation(**dict(row)) for row in rows]

    def require_model_operation(self, owner_principal_id: str, operation_id: str) -> ModelOperation:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM model_operations WHERE owner_principal_id = ? AND operation_id = ?",
                (owner_principal_id, operation_id),
            ).fetchone()
        if row is None:
            raise KeyError("model_operation_not_found")
        return ModelOperation(**dict(row))

    def update_model_operation(self, operation_id: str, **updates: Any) -> None:
        allowed = {"state", "phase", "progress_bytes", "total_bytes", "progress_percent", "error_code", "error_detail"}
        fields = {key: value for key, value in updates.items() if key in allowed}
        if not fields:
            return
        fields["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = ?" for key in fields)
        with self.connect() as connection:
            connection.execute(
                f"UPDATE model_operations SET {assignments} WHERE operation_id = ?",  # noqa: S608 -- allowlisted column names only
                (*fields.values(), operation_id),
            )

    def fail_running_model_operations(self) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE model_operations SET state = 'failed', phase = 'recovery',
                error_code = 'host_restarted', error_detail = 'The host stopped before this operation completed.',
                updated_at = ? WHERE state IN ('running', 'cancel_requested')""",
                (utc_now(),),
            )
        return cursor.rowcount

    def delete_model_operation(self, owner_principal_id: str, operation_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM model_operations WHERE owner_principal_id = ? AND operation_id = ?",
                (owner_principal_id, operation_id),
            )
        return cursor.rowcount == 1

    def save_model_setup_state(self, state: ModelSetupState) -> ModelSetupState:
        now = utc_now()
        created_at = state.created_at or now
        saved = ModelSetupState(
            owner_principal_id=state.owner_principal_id,
            status=state.status,
            step=state.step,
            path=state.path,
            selected_profile_id=state.selected_profile_id,
            selected_model=state.selected_model,
            created_at=created_at,
            updated_at=now,
        )
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO model_setup_state
                (owner_principal_id, status, step, path, selected_profile_id, selected_model, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    saved.owner_principal_id, saved.status, saved.step, saved.path,
                    saved.selected_profile_id, saved.selected_model, saved.created_at, saved.updated_at,
                ),
            )
        return saved

    def load_setup_state(self, owner_principal_id: str) -> SetupState:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM setup_state WHERE owner_principal_id = ?",
                (owner_principal_id,),
            ).fetchone()
        if row is None:
            return SetupState(owner_principal_id=owner_principal_id)
        values = dict(row)
        values["model_deferred"] = bool(values["model_deferred"])
        values["background_service_enabled"] = bool(values["background_service_enabled"])
        return SetupState(**values)

    def save_setup_state(self, state: SetupState) -> SetupState:
        now = utc_now()
        saved = SetupState(**(state.to_dict() | {"created_at": state.created_at or now, "updated_at": now}))
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO setup_state
                (owner_principal_id, status, stage, selected_profile_id, selected_model,
                 model_deferred, privacy_mode, privacy_acknowledged_at, backup_mode,
                 backup_target, backup_verified_at, background_service_enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    saved.owner_principal_id, saved.status, saved.stage,
                    saved.selected_profile_id, saved.selected_model, int(saved.model_deferred),
                    saved.privacy_mode, saved.privacy_acknowledged_at, saved.backup_mode,
                    saved.backup_target, saved.backup_verified_at,
                    int(saved.background_service_enabled), saved.created_at, saved.updated_at,
                ),
            )
        return saved

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
        self.record_memory_lifecycle_event(
            f"backup:{manifest.manifest_id}", "backup_access", manifest.created_by, {"operation": "catalog_register"}
        )

    def list_backup_manifests(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM backup_manifests ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def request_backup_erasure(self, manifest_id: str, actor_id: str = "system") -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE backup_manifests SET erasure_requested_at = ? WHERE manifest_id = ? AND legal_hold = 0 AND erased_at IS NULL",
                (utc_now(), manifest_id),
            )
        changed = cursor.rowcount > 0
        if changed:
            self.record_memory_lifecycle_event(
                f"backup:{manifest_id}", "backup_access", actor_id, {"operation": "erasure_requested"}
            )
        return changed

    def record_backup_erased(self, manifest_id: str, actor_id: str = "system") -> bool:
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

    def record_backup_restore_verified(self, manifest_id: str, actor_id: str = "system") -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE backup_manifests SET restore_verified_at = ? WHERE manifest_id = ? AND erased_at IS NULL",
                (utc_now(), manifest_id),
            )
        changed = cursor.rowcount > 0
        if changed:
            self.record_memory_lifecycle_event(
                f"backup:{manifest_id}", "backup_access", actor_id, {"operation": "restore_verified"}
            )
        return changed

    def set_backup_legal_hold(self, manifest_id: str, legal_hold: bool, actor_id: str) -> bool:
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

    def memory_job_metrics(self) -> dict[str, int | float]:
        """Return aggregate, non-sensitive queue and worker health metrics."""
        with self.connect() as connection:
            counts = {
                str(row["status"]): int(row["count"])
                for row in connection.execute(
                    "SELECT status, COUNT(*) AS count FROM memory_jobs GROUP BY status"
                ).fetchall()
            }
            completed = connection.execute(
                """SELECT AVG((julianday(updated_at) - julianday(created_at)) * 86400000.0) AS latency_ms
                FROM memory_jobs WHERE status = 'completed'"""
            ).fetchone()
        return {
            "queue_depth": counts.get("queued", 0) + counts.get("retry", 0),
            "running_count": counts.get("running", 0),
            "completed_count": counts.get("completed", 0),
            "dead_letter_count": counts.get("dead_letter", 0),
            "average_completion_latency_ms": float(completed["latency_ms"] or 0.0),
        }

    def record_memory_lifecycle_event(self, memory_id: str, action: str, actor_id: str, details: dict[str, Any] | None = None) -> str:
        from raiker.contracts.ids import new_id

        if action not in {
            "archive", "restore", "forget", "purge", "correct", "export", "import", "recall",
            "approve", "reject", "edit", "pin", "unpin", "scope_change", "expiry_change",
            "legal_hold", "backup_access", "admin_access",
        }:
            raise ValueError("invalid_memory_lifecycle_action")
        audit_id = new_id("mla_")
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO memory_lifecycle_audit VALUES (?, ?, ?, ?, ?, ?)",
                (audit_id, memory_id, action, actor_id, json.dumps(details or {}, sort_keys=True), utc_now()),
            )
        return audit_id

    def list_memory_lifecycle_events(
        self, memory_id: str, *, owner_principal_id: str
    ) -> list[dict[str, Any]]:
        """Return immutable history only while the caller still owns the record."""
        with self.connect() as connection:
            owned = connection.execute(
                "SELECT 1 FROM approved_memory WHERE memory_id = ? AND owner_principal_id = ?",
                (memory_id, owner_principal_id),
            ).fetchone()
            if owned is None:
                return []
            rows = connection.execute(
                """SELECT audit_id, memory_id, action, actor_id, details_json, created_at
                FROM memory_lifecycle_audit WHERE memory_id = ? ORDER BY created_at DESC, audit_id DESC""",
                (memory_id,),
            ).fetchall()
        return [
            {**dict(row), "details": json.loads(row["details_json"] or "{}")}
            for row in rows
        ]

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
                (subagent_id, parent_task_id, name, mode, allowed_tools_json, max_depth, max_runtime_seconds, max_cost, created_by, created_at, status, max_steps, max_tool_calls, max_tokens)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (contract.subagent_id, contract.parent_task_id, contract.name, contract.mode, contract.allowed_tools_json, contract.max_depth, contract.max_runtime_seconds, contract.max_cost, contract.created_by, contract.created_at, contract.status, contract.max_steps, contract.max_tool_calls, contract.max_tokens),
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
                (profile_id, profile_type, name, config_json, enabled, created_by, created_at, updated_at, owner_principal_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (profile.profile_id, profile.profile_type, profile.name, profile.config_json, int(profile.enabled), profile.created_by, profile.created_at, profile.updated_at, profile.created_by),
            )

    def list_remote_execution_profiles(self, enabled_only: bool = False, *, owner_principal_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM remote_execution_profiles"
        params: list[Any] = []
        conditions: list[str] = []
        if enabled_only:
            conditions.append("enabled = 1")
        if owner_principal_id is not None:
            conditions.append("owner_principal_id = ?")
            params.append(owner_principal_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def load_remote_execution_profile(
        self, profile_id: str, *, owner_principal_id: str
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM remote_execution_profiles WHERE profile_id = ? AND owner_principal_id = ?",
                (profile_id, owner_principal_id),
            ).fetchone()
        return dict(row) if row else None

    def select_execution_environment(self, owner_principal_id: str, profile_id: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO execution_environment_selection VALUES (?, ?, ?)
                ON CONFLICT(owner_principal_id) DO UPDATE SET profile_id = excluded.profile_id,
                selected_at = excluded.selected_at""",
                (owner_principal_id, profile_id, utc_now()),
            )

    def selected_execution_environment(self, owner_principal_id: str) -> str:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT profile_id FROM execution_environment_selection WHERE owner_principal_id = ?",
                (owner_principal_id,),
            ).fetchone()
        return str(row["profile_id"]) if row else "local_native"

    @staticmethod
    def _cloud_cost_totals(rows: list[Any]) -> tuple[Decimal, Decimal, Decimal, list[dict[str, Any]]]:
        actions: dict[str, dict[str, Any]] = {}
        provider_snapshots: list[Decimal] = []
        history: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                amount = Decimal(str(item["amount"]))
            except (InvalidOperation, ValueError):
                amount = Decimal("0")
            event_type = str(item["event_type"])
            if event_type == "provider_snapshot":
                provider_snapshots.append(amount)
                action = None
            else:
                action = actions.setdefault(
                    str(item["action_id"]),
                    {"estimated": Decimal("0"), "actual": None, "released": False, "status": "pending"},
                )
            if event_type == "reserved":
                assert action is not None
                action.update(estimated=amount, status="reserved")
            elif event_type == "reconciled":
                assert action is not None
                action.update(actual=amount, status="reconciled")
            elif event_type == "released":
                assert action is not None
                action.update(released=True, status="released")
            elif event_type == "provider_unavailable" and action is not None and action["status"] == "reserved":
                action["status"] = "provider_unavailable"
            history.append(
                {
                    "event_id": str(item["event_id"]),
                    "action_id": str(item["action_id"]),
                    "event_type": event_type,
                    "amount": float(amount),
                    "provider_reference": item.get("provider_reference"),
                    "reason": item.get("reason"),
                    "recorded_at": str(item["recorded_at"]),
                }
            )
        actual = sum(
            (entry["actual"] for entry in actions.values() if entry["actual"] is not None),
            Decimal("0"),
        )
        reserved = sum(
            (
                entry["estimated"]
                for entry in actions.values()
                if entry["actual"] is None and not entry["released"]
            ),
            Decimal("0"),
        )
        provider_spend = (
            max(provider_snapshots[-1] - provider_snapshots[0], Decimal("0"))
            if len(provider_snapshots) >= 2 else Decimal("0")
        )
        return actual, reserved, provider_spend, history

    def reserve_cloud_execution_cost(
        self,
        *,
        owner_principal_id: str,
        profile_id: str,
        action_id: str,
        estimated_cost: float,
        max_cost: float,
    ) -> bool:
        """Atomically reserve cumulative budget before Daytona execution."""
        estimate = Decimal(str(max(estimated_cost, 0)))
        limit = Decimal(str(max(max_cost, 0)))
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """SELECT * FROM cloud_execution_cost_ledger
                WHERE owner_principal_id = ? AND profile_id = ?
                ORDER BY rowid""",
                (owner_principal_id, profile_id),
            ).fetchall()
            if any(str(row["action_id"]) == action_id and row["event_type"] == "reserved" for row in rows):
                return False
            actual, reserved, provider_spend, _history = self._cloud_cost_totals(list(rows))
            if limit <= 0 or max(actual, provider_spend) + reserved + estimate > limit:
                return False
            connection.execute(
                """INSERT INTO cloud_execution_cost_ledger
                (event_id, owner_principal_id, profile_id, action_id, event_type, amount,
                 provider_reference, reason, recorded_at)
                VALUES (?, ?, ?, ?, 'reserved', ?, NULL, NULL, ?)""",
                (new_id("cost_"), owner_principal_id, profile_id, action_id, str(estimate), utc_now()),
            )
        return True

    def record_cloud_execution_cost(
        self,
        *,
        owner_principal_id: str,
        profile_id: str,
        action_id: str,
        event_type: str,
        amount: float,
        provider_reference: str | None = None,
        reason: str | None = None,
    ) -> None:
        if event_type not in {"reconciled", "released", "provider_snapshot", "provider_unavailable"}:
            raise ValueError("invalid_cloud_cost_event")
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO cloud_execution_cost_ledger
                (event_id, owner_principal_id, profile_id, action_id, event_type, amount,
                 provider_reference, reason, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    new_id("cost_"), owner_principal_id, profile_id, action_id, event_type,
                    str(Decimal(str(max(amount, 0)))), provider_reference, reason, utc_now(),
                ),
            )

    def cloud_execution_cost_summary(
        self, owner_principal_id: str, profile_id: str, *, max_cost: float | None = None
    ) -> dict[str, Any]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM cloud_execution_cost_ledger
                WHERE owner_principal_id = ? AND profile_id = ?
                ORDER BY rowid""",
                (owner_principal_id, profile_id),
            ).fetchall()
        actual, reserved, provider_spend, history = self._cloud_cost_totals(list(rows))
        limit = Decimal(str(max_cost)) if max_cost is not None else None
        committed = max(actual, provider_spend) + reserved
        return {
            "actual_cost": float(actual),
            "provider_cost": float(provider_spend),
            "reserved_cost": float(reserved),
            "committed_cost": float(committed),
            "remaining_cost": float(max(limit - committed, Decimal("0"))) if limit is not None else None,
            "reconciliation_status": (
                "provider_unavailable" if any(item["event_type"] == "provider_unavailable" for item in history)
                and reserved > 0 else "reconciled" if history and reserved == 0 else "reserved" if reserved > 0 else "not_started"
            ),
            "history": history,
        }

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
                (vector_id, content_hash, content_preview, embedding_model, dimensions, scope, sensitivity, embedding, created_at, owner_principal_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (record.vector_id, record.content_hash, record.content_preview, record.embedding_model, record.dimensions, record.scope, record.sensitivity, record.embedding, record.created_at, record.owner_principal_id),
            )

    def list_vector_records(self, scope: str | None = None, limit: int = 50, *, owner_principal_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM vector_records"
        params: list[Any] = []
        conditions: list[str] = []
        if scope:
            conditions.append("scope = ?")
            params.append(scope)
        if owner_principal_id:
            conditions.append("owner_principal_id = ?")
            params.append(owner_principal_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_vector_record(self, vector_id: str, *, owner_principal_id: str | None = None) -> dict[str, Any] | None:
        """Return one vector record by id (or ``None``). Includes the stored preview."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM vector_records WHERE vector_id = ?"
                + (" AND owner_principal_id = ?" if owner_principal_id else ""),
                (vector_id, *([owner_principal_id] if owner_principal_id else [])),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_vector_embeddings(
        self, embedding_model: str, scope: str | None = None, *, owner_principal_id: str | None = None
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
        if owner_principal_id:
            query += " AND owner_principal_id = ?"
            params.append(owner_principal_id)
        query += " ORDER BY created_at"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def list_active_memory_vector_embeddings(
        self, embedding_model: str, scope: str | None = None, *, owner_principal_id: str | None = None
    ) -> list[dict[str, Any]]:
        now = utc_now()
        query = """SELECT v.vector_id, v.embedding, p.memory_id FROM vector_records v
        JOIN memory_projections p ON p.projection_id = v.vector_id
          AND p.projection_type = 'vector' AND p.active = 1
        JOIN approved_memory m ON m.memory_id = p.memory_id
        WHERE v.embedding_model = ? AND v.embedding IS NOT NULL
          AND m.deleted_at IS NULL AND m.archived_at IS NULL AND m.search_enabled = 1
          AND m.sensitivity NOT IN ('secret_like', 'credential_like')
          AND (m.expires_at IS NULL OR m.expires_at > ?)
          AND (m.valid_from IS NULL OR m.valid_from <= ?)
          AND (m.valid_until IS NULL OR m.valid_until > ?) AND m.superseded_at IS NULL"""
        params: list[Any] = [embedding_model, now, now, now]
        if scope:
            query += " AND m.scope = ?"
            params.append(scope)
        if owner_principal_id:
            query += " AND m.owner_principal_id = ? AND v.owner_principal_id = ?"
            params.extend((owner_principal_id, owner_principal_id))
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

    def save_principal_model_state(self, principal_id: str, state: ModelSessionState) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO principal_model_control
                (principal_id, profile_id, model, reasoning_enabled, reasoning_effort, reasoning_mode,
                 reasoning_budget_tokens, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (principal_id, state.profile_id, state.model, int(state.reasoning_enabled),
                 state.reasoning_effort, state.reasoning_mode, state.reasoning_budget_tokens, utc_now()),
            )

    def load_principal_model_state(self, principal_id: str) -> ModelSessionState | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM principal_model_control WHERE principal_id = ?", (principal_id,)
            ).fetchone()
        if row is None:
            return None
        return ModelSessionState(
            session_id=principal_id, profile_id=str(row["profile_id"]),
            model=str(row["model"]) if row["model"] else None,
            reasoning_enabled=bool(row["reasoning_enabled"]),
            reasoning_effort=row["reasoning_effort"], reasoning_mode=row["reasoning_mode"],
            reasoning_budget_tokens=row["reasoning_budget_tokens"],
        )

    def save_configured_model(self, principal_id: str, profile_id: str, model: str) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO principal_configured_models
                (principal_id, profile_id, model, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(principal_id, profile_id, model)
                DO UPDATE SET updated_at = excluded.updated_at""",
                (principal_id, profile_id, model, now, now),
            )

    def save_model_readiness(self, readiness: ModelReadiness) -> None:
        """Persist redacted reachability evidence for one exact model target."""

        def redact(value: Any) -> Any:
            if isinstance(value, dict):
                return {
                    str(key): (
                        "[redacted]"
                        if any(
                            marker in str(key).casefold()
                            for marker in ("authorization", "api_key", "apikey", "secret", "token", "credential")
                        )
                        else redact(item)
                    )
                    for key, item in value.items()
                }
            if isinstance(value, list):
                return [redact(item) for item in value]
            return value

        key = readiness.key
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO model_readiness
                (owner_principal_id, profile_id, model, endpoint_fingerprint,
                 state, checked_at, expires_at, summary, reason_code, remediation, evidence_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(owner_principal_id, profile_id, model, endpoint_fingerprint)
                DO UPDATE SET state = excluded.state,
                  checked_at = excluded.checked_at,
                  expires_at = excluded.expires_at,
                  summary = excluded.summary,
                  reason_code = excluded.reason_code,
                  remediation = excluded.remediation,
                  evidence_json = excluded.evidence_json""",
                (
                    key.owner_principal_id,
                    key.profile_id,
                    key.model,
                    key.endpoint_fingerprint,
                    readiness.state.value,
                    readiness.checked_at,
                    readiness.expires_at,
                    readiness.summary,
                    readiness.reason_code,
                    readiness.remediation,
                    json.dumps(redact(readiness.evidence), sort_keys=True, separators=(",", ":")),
                ),
            )

    @staticmethod
    def _model_readiness_from_row(row: sqlite3.Row) -> ModelReadiness:
        try:
            evidence = json.loads(str(row["evidence_json"]))
        except (TypeError, ValueError):
            evidence = {}
        return ModelReadiness(
            key=ModelReadinessKey(
                owner_principal_id=str(row["owner_principal_id"]),
                profile_id=str(row["profile_id"]),
                model=str(row["model"]),
                endpoint_fingerprint=str(row["endpoint_fingerprint"]),
            ),
            state=ModelReadinessState(str(row["state"])),
            checked_at=str(row["checked_at"]) if row["checked_at"] else None,
            expires_at=str(row["expires_at"]) if row["expires_at"] else None,
            summary=str(row["summary"]),
            reason_code=str(row["reason_code"]),
            remediation=str(row["remediation"]),
            evidence=evidence if isinstance(evidence, dict) else {},
        )

    def load_model_readiness(self, key: ModelReadinessKey) -> ModelReadiness | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM model_readiness
                WHERE owner_principal_id = ? AND profile_id = ? AND model = ?
                  AND endpoint_fingerprint = ?""",
                (
                    key.owner_principal_id,
                    key.profile_id,
                    key.model,
                    key.endpoint_fingerprint,
                ),
            ).fetchone()
        return self._model_readiness_from_row(row) if row is not None else None

    def list_model_readiness(
        self,
        owner_principal_id: str,
        profile_id: str | None = None,
    ) -> list[ModelReadiness]:
        query = "SELECT * FROM model_readiness WHERE owner_principal_id = ?"
        params: list[str] = [owner_principal_id]
        if profile_id is not None:
            query += " AND profile_id = ?"
            params.append(profile_id)
        query += " ORDER BY profile_id, model, endpoint_fingerprint"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._model_readiness_from_row(row) for row in rows]

    def invalidate_model_readiness(
        self,
        owner_principal_id: str,
        profile_id: str,
        *,
        reason_code: str = "readiness_invalidated",
    ) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE model_readiness
                SET state = ?, expires_at = ?, reason_code = ?,
                    summary = ?, remediation = ?
                WHERE owner_principal_id = ? AND profile_id = ?""",
                (
                    ModelReadinessState.STALE.value,
                    utc_now(),
                    reason_code,
                    "This model connection must be checked again.",
                    "Check this model again before sending.",
                    owner_principal_id,
                    profile_id,
                ),
            )
        return int(cursor.rowcount)

    def save_surface_model_default(
        self, principal_id: str, surface: str, profile_id: str, model: str
    ) -> None:
        """Remember which model a work surface should start on.

        A preference, not an authority: the turn this produces still carries an
        explicit profile and model, and the readiness gate judges that pair.
        """
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO principal_surface_models
                (principal_id, surface, profile_id, model, updated_at)
                VALUES (?, ?, ?, ?, ?)""",
                (principal_id, surface, profile_id, model, utc_now()),
            )

    def load_surface_model_default(
        self, principal_id: str, surface: str
    ) -> tuple[str, str] | None:
        """The surface's default, or None when it has no opinion of its own."""
        with self.connect() as connection:
            row = connection.execute(
                """SELECT profile_id, model FROM principal_surface_models
                WHERE principal_id = ? AND surface = ?""",
                (principal_id, surface),
            ).fetchone()
        return None if row is None else (str(row["profile_id"]), str(row["model"]))

    def list_surface_model_defaults(self, principal_id: str) -> list[tuple[str, str, str]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT surface, profile_id, model FROM principal_surface_models
                WHERE principal_id = ? ORDER BY surface""",
                (principal_id,),
            ).fetchall()
        return [
            (str(row["surface"]), str(row["profile_id"]), str(row["model"])) for row in rows
        ]

    def clear_surface_model_default(self, principal_id: str, surface: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM principal_surface_models WHERE principal_id = ? AND surface = ?",
                (principal_id, surface),
            )

    def list_configured_models(self, principal_id: str) -> list[tuple[str, str]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT profile_id, model FROM principal_configured_models
                WHERE principal_id = ?
                ORDER BY created_at, profile_id, model""",
                (principal_id,),
            ).fetchall()
        return [(str(row["profile_id"]), str(row["model"])) for row in rows]

    def is_configured_model(self, principal_id: str, profile_id: str, model: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT 1 FROM principal_configured_models
                WHERE principal_id = ? AND profile_id = ? AND model = ?""",
                (principal_id, profile_id, model),
            ).fetchone()
        return row is not None

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

    def save_principal_model_fallback_sequence(self, principal_id: str, profile_ids: list[str]) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO principal_model_fallback_sequence
                (principal_id, profile_ids_json, updated_at) VALUES (?, ?, ?)""",
                (principal_id, json.dumps(list(profile_ids)), utc_now()),
            )

    def load_principal_model_fallback_sequence(self, principal_id: str) -> list[str]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT profile_ids_json FROM principal_model_fallback_sequence WHERE principal_id = ?",
                (principal_id,),
            ).fetchone()
        try:
            value = json.loads(row["profile_ids_json"]) if row else []
        except (TypeError, ValueError):
            value = []
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

    def save_principal_model_advisor(self, principal_id: str, profile_id: str | None) -> None:
        with self.connect() as connection:
            if not profile_id:
                connection.execute("DELETE FROM principal_model_advisor WHERE principal_id = ?", (principal_id,))
                return
            connection.execute(
                """INSERT OR REPLACE INTO principal_model_advisor (principal_id, profile_id, updated_at)
                VALUES (?, ?, ?)""", (principal_id, profile_id, utc_now())
            )

    def load_principal_model_advisor(self, principal_id: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT profile_id FROM principal_model_advisor WHERE principal_id = ?", (principal_id,)
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
        owner_principal_id: str | None = None,
    ) -> None:
        """Persist validated attachment bytes. Validation is the caller's job
        (``raiker.runtime.attachments``) — this layer only stores what it is given."""
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO attachments
                (attachment_id, kind, filename, media_type, byte_size, sha256, data, created_at, owner_principal_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (attachment_id, kind, filename, media_type, len(data), sha256, data, utc_now(), owner_principal_id),
            )

    def load_attachment(self, attachment_id: str, *, owner_principal_id: str | None = None) -> dict[str, Any] | None:
        """Return the stored attachment (metadata + raw bytes), or None if unknown."""
        # ``None`` means "no owner scoping requested"; an empty string is a
        # caller bug that must fail closed (match nothing), never drop the
        # predicate and expose every owner's bytes.
        scoped = owner_principal_id is not None
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM attachments WHERE attachment_id = ?"
                + (" AND owner_principal_id = ?" if scoped else ""),
                (attachment_id, *([owner_principal_id] if scoped else [])),
            ).fetchone()
        if row is None:
            return None
        record = dict(row)
        record["data"] = bytes(record["data"])
        return record

    def load_attachment_metadata(self, attachment_id: str, *, owner_principal_id: str | None = None) -> dict[str, Any] | None:
        """Return attachment metadata only — the bytes never ride this path."""
        # ``None`` disables owner scoping; an empty string fails closed rather
        # than dropping the predicate (see ``load_attachment``).
        scoped = owner_principal_id is not None
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT attachment_id, kind, filename, media_type, byte_size, sha256, created_at
                FROM attachments WHERE attachment_id = ?
                """ + (" AND owner_principal_id = ?" if scoped else ""),
                (attachment_id, *([owner_principal_id] if scoped else [])),
            ).fetchone()
        return dict(row) if row is not None else None

    # ── Session attachment references (BUG-07: the file inspector's grant) ──

    def save_session_attachment_ref(
        self, *, session_id: str, attachment_id: str, owner_principal_id: str,
        turn_id: str, source: str = "uploaded",
    ) -> None:
        """Record that one attachment was carried by one session's prompt turn.

        The caller must already have confirmed that both the session and the
        attachment belong to ``owner_principal_id`` — this layer only writes the
        reference the preview route later requires.
        """
        if not (session_id and attachment_id and owner_principal_id):
            return
        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO session_attachment_refs
                (session_id, attachment_id, owner_principal_id, turn_id, created_at, source)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, attachment_id, owner_principal_id, turn_id, utc_now(), source),
            )

    def session_attachment_ref_exists(
        self, *, session_id: str, attachment_id: str, owner_principal_id: str
    ) -> bool:
        """True only when this owner attached this file to this conversation."""
        # Every predicate is required: an empty owner, session, or attachment id
        # matches nothing rather than widening the query (fail closed).
        if not (session_id and attachment_id and owner_principal_id):
            return False
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM session_attachment_refs
                WHERE session_id = ? AND attachment_id = ? AND owner_principal_id = ?
                """,
                (session_id, attachment_id, owner_principal_id),
            ).fetchone()
        return row is not None

    def list_session_attachment_refs(
        self, *, session_id: str, owner_principal_id: str
    ) -> list[dict[str, Any]]:
        """Return this owner's attachment references for one session, oldest first."""
        if not (session_id and owner_principal_id):
            return []
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT attachment_id, turn_id, created_at, source FROM session_attachment_refs
                WHERE session_id = ? AND owner_principal_id = ?
                ORDER BY created_at, rowid
                """,
                (session_id, owner_principal_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def put_session_command_grant(
        self, *, session_id: str, principal_id: str, commands: list[list[str]],
        timeout_seconds: int, expires_at: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO session_command_grants
                   (session_id, principal_id, commands_json, timeout_seconds, expires_at, revoked, created_at)
                   VALUES (?, ?, ?, ?, ?, 0, ?)
                   ON CONFLICT(session_id, principal_id) DO UPDATE SET
                   commands_json=excluded.commands_json,
                   timeout_seconds=excluded.timeout_seconds,
                   expires_at=excluded.expires_at, revoked=0, created_at=excluded.created_at""",
                (session_id, principal_id, json.dumps(commands), timeout_seconds, expires_at, utc_now()),
            )

    def load_session_command_grant(
        self, *, session_id: str, principal_id: str
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM session_command_grants
                   WHERE session_id=? AND principal_id=? AND revoked=0 AND expires_at>?""",
                (session_id, principal_id, utc_now()),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["commands"] = json.loads(str(result.pop("commands_json")))
        return result

    def revoke_session_command_grant(self, *, session_id: str, principal_id: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE session_command_grants SET revoked=1 WHERE session_id=? AND principal_id=?",
                (session_id, principal_id),
            )

    # ── Phase 10: Runtime Authority (Principals + Risk Acceptance) ──

    def get_active_machine_issuer_key(self) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM machine_identity_issuers
                   WHERE is_active=1 ORDER BY created_at, key_id LIMIT 1"""
            ).fetchone()
        return dict(row) if row is not None else None

    def get_machine_issuer_key(self, key_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM machine_identity_issuers WHERE key_id=? AND is_active=1",
                (key_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def create_machine_issuer_key_if_absent(
        self,
        *,
        workspace_id: str,
        key_id: str,
        public_key: bytes,
        private_key_encrypted: bytes,
    ) -> dict[str, Any]:
        """Atomically install the one active embedded issuer for this workspace."""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT * FROM machine_identity_issuers
                   WHERE is_active=1 ORDER BY created_at, key_id LIMIT 1"""
            ).fetchone()
            if row is None:
                connection.execute(
                    """INSERT INTO machine_identity_issuers
                       (workspace_id, key_id, public_key, private_key_encrypted,
                        created_at, rotated_at, is_active)
                       VALUES (?, ?, ?, ?, ?, NULL, 1)""",
                    (
                        workspace_id,
                        key_id,
                        public_key,
                        private_key_encrypted,
                        utc_now(),
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM machine_identity_issuers WHERE key_id=?", (key_id,)
                ).fetchone()
            assert row is not None
            return dict(row)

    def list_active_machine_issuer_keys(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM machine_identity_issuers
                   WHERE is_active=1 ORDER BY created_at, key_id"""
            ).fetchall()
        return [dict(row) for row in rows]

    def insert_turn_machine_identity(self, identity: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO turn_machine_identities
                   (principal_id, owner_principal_id, workspace_id, session_id,
                    turn_id, subject, key_id, token_id, issued_at, expires_at,
                    parent_principal_id, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (
                    identity["principal_id"],
                    identity["owner_principal_id"],
                    identity["workspace_id"],
                    identity["session_id"],
                    identity["turn_id"],
                    identity["subject"],
                    identity["key_id"],
                    identity["token_id"],
                    identity["issued_at"],
                    identity["expires_at"],
                    identity.get("parent_principal_id"),
                ),
            )

    def get_turn_machine_identity(self, principal_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM turn_machine_identities WHERE principal_id=?",
                (principal_id,),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["is_active"] = bool(result["is_active"])
        return result

    def get_turn_machine_identity_for_turn(
        self, *, owner_principal_id: str, session_id: str, turn_id: str
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM turn_machine_identities
                   WHERE owner_principal_id=? AND session_id=? AND turn_id=?
                   ORDER BY issued_at DESC LIMIT 1""",
                (owner_principal_id, session_id, turn_id),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["is_active"] = bool(result["is_active"])
        return result

    def rotate_turn_machine_identity(
        self, principal_id: str, *, token_id: str, issued_at: str, expires_at: str
    ) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE turn_machine_identities
                   SET token_id=?, issued_at=?, expires_at=?, is_active=1
                   WHERE principal_id=?""",
                (token_id, issued_at, expires_at, principal_id),
            )
        return cursor.rowcount == 1

    def reactivate_machine_principal(self, principal_id: str, *, expires_at: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE principals SET expires_at=?, is_active=1 WHERE principal_id=?",
                (expires_at, principal_id),
            )
        return cursor.rowcount == 1

    def deactivate_turn_machine_identity(self, principal_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE turn_machine_identities SET is_active=0 WHERE principal_id=?",
                (principal_id,),
            )
        return cursor.rowcount == 1

    def insert_principal(self, principal_id: str, principal_type: str, display_name: str,
                         delegated_by_user_id: str | None = None,
                         model_profile_id: str | None = None,
                         session_id: str | None = None,
                         role_ids: tuple[str, ...] = (),
                         domain_scopes: tuple[str, ...] = (),
                         max_runtime_mode: str = "raiker_runtime",
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
    def record_threat_model_ack(
        self, capability: str, acked_by: str, acked_at: str, doc_ref: str = ""
    ) -> None:
        """Record (idempotently) that a human acknowledged a capability's threat model.

        This is the persisted precondition for activating threat-ack-gated
        capabilities (e.g. hosted model runtimes). Recording an acknowledgement
        grants nothing on its own — it only satisfies one activation requirement;
        the transition still runs through the full governed gate.
        """
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO threat_model_acks (capability, acked_by, acked_at, doc_ref)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(capability) DO UPDATE SET
                     acked_by=excluded.acked_by,
                     acked_at=excluded.acked_at,
                     doc_ref=excluded.doc_ref""",
                (capability, acked_by, acked_at, doc_ref),
            )

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

    def account_scope(self, principal_id: str | None) -> str | None:
        """Resolve a real local account for a human or delegated machine actor.

        Reads are owner-scoped for accounts and unscoped otherwise. The terminal
        client sends ``UserMetadata``'s default ``local_user``, which is truthy
        but is not a principal — scoping on mere truthiness silently hides the
        CLI's own project, connectors, memory, and model selection.
        """
        if not principal_id:
            return None
        if self.get_account(principal_id) is not None:
            return principal_id
        principal = self.get_principal(principal_id)
        if principal is None or principal.get("principal_type") != "ai_agent":
            return None
        user_id = principal.get("delegated_by_user_id")
        if not user_id:
            return None
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT account_credentials.principal_id
                   FROM account_credentials
                   JOIN principals
                     ON principals.principal_id = account_credentials.principal_id
                   WHERE principals.delegated_by_user_id = ?
                   ORDER BY account_credentials.principal_id LIMIT 2""",
                (user_id,),
            ).fetchall()
        return str(rows[0]["principal_id"]) if len(rows) == 1 else None

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

    @staticmethod
    def _delete_rows_orphaned_by_purge(connection: sqlite3.Connection) -> None:
        """Remove rows whose parent the purge sweep just deleted.

        The sweep can only match tables carrying an owner/session/project column.
        A child that references a swept parent but carries none of those columns
        is unreachable by it and is left pointing at a deleted row, which fails
        the deferred foreign-key check at COMMIT. Five such edges exist today
        (`policy_decisions` and `approvals` -> `tool_actions`, `gist_memories` ->
        `eidetic_observations`, and both `*_relationship*` tables ->
        `approved_memory`), and hardcoding them would rot the next time a table
        is added — so let SQLite name the orphans its own deletes created.

        Callers must hold a transaction whose starting state had no violations,
        or this removes pre-existing orphans too. `purge_account` is such a
        caller: the workspaces it runs against are foreign-key-clean.
        """
        # Deleting an orphan can orphan its own child, so iterate to a fixed
        # point. Bounded because each pass strictly shrinks the FK depth still
        # to be resolved; the cap only stops a pathological cycle from spinning.
        for _ in range(8):
            violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            if not violations:
                return
            for violation in violations:
                connection.execute(
                    f'DELETE FROM "{violation[0]}" WHERE rowid = ?', (violation[1],)
                )
        raise RuntimeError("purge_orphan_cleanup_did_not_converge")

    def purge_account(self, principal_id: str) -> None:
        """Irreversibly remove an account and all its per-principal data."""
        with self.connect() as connection:
            # The sweep below walks `sqlite_master`, which is table-creation
            # order — parent before child. `sessions` is created before `turns`,
            # and `turns.session_id` references it, so deleting the owner's
            # sessions raises `FOREIGN KEY constraint failed` on any account that
            # ever held a conversation. Defer enforcement to COMMIT instead of
            # topologically sorting 87 tables: order stops mattering, and a purge
            # that really would orphan a row still fails, just at commit.
            #
            # The pragma only holds for the transaction it is set in — SQLite
            # resets it at each COMMIT/ROLLBACK, and setting it outside a
            # transaction is silently undone when the first DELETE opens one.
            # BEGIN first, so it applies to the sweep and cannot leak past it.
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("PRAGMA defer_foreign_keys = ON")
            # Captured before the deletes below: approved_memory_fts and
            # memory_projections are keyed only by memory_id (no owner column),
            # so the owner-keyed sweep never matches them and the FTS row would
            # keep the purged memory's full plaintext. The markdown exports are
            # not rows at all and are unlinked after the transaction commits.
            memory_ids = [
                str(row["memory_id"])
                for row in connection.execute(
                    "SELECT memory_id FROM approved_memory WHERE owner_principal_id = ?",
                    (principal_id,),
                ).fetchall()
            ]
            user_id = self._principal_user_id_from_connection(connection, principal_id)
            session_ids = [str(row["session_id"]) for row in connection.execute(
                "SELECT session_id FROM sessions WHERE user_id = ?", (user_id,)
            ).fetchall()] if user_id else []
            project_ids = [str(row["project_id"]) for row in connection.execute(
                "SELECT project_id FROM projects WHERE owner_user_id = ?", (user_id,)
            ).fetchall()] if user_id else []
            excluded = {"account_credentials", "api_sessions", "instance_account_guard", "migrations", "principals", "users"}
            for table_row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall():
                table = str(table_row["name"])
                if table.startswith("sqlite_") or table in excluded:
                    continue
                columns = {str(column["name"]) for column in connection.execute(f'PRAGMA table_info("{table}")').fetchall()}
                for column, values in (
                    ("owner_principal_id", [principal_id]), ("principal_id", [principal_id]),
                    ("owner_user_id", [user_id] if user_id else []), ("user_id", [user_id] if user_id else []),
                    ("session_id", session_ids), ("project_id", project_ids),
                ):
                    if column in columns and values:
                        marks = ",".join("?" for _ in values)
                        connection.execute(f'DELETE FROM "{table}" WHERE "{column}" IN ({marks})', values)
            for sql in (
                "DELETE FROM account_credentials WHERE principal_id = ?",
                "DELETE FROM user_settings WHERE principal_id = ?",
                "DELETE FROM trusted_contacts WHERE principal_id = ?",
                "DELETE FROM connector_credentials WHERE principal_id = ?",
                "DELETE FROM connector_installations WHERE principal_id = ?",
                "DELETE FROM api_sessions WHERE principal_id = ?",
                "DELETE FROM principal_model_control WHERE principal_id = ?",
                "DELETE FROM principal_configured_models WHERE principal_id = ?",
                "DELETE FROM principal_model_fallback_sequence WHERE principal_id = ?",
                "DELETE FROM principal_model_advisor WHERE principal_id = ?",
                "DELETE FROM principal_runtime_mode_state WHERE principal_id = ?",
                "DELETE FROM principal_capability_gate_state WHERE principal_id = ?",
                "DELETE FROM principal_capability_decision_mode WHERE principal_id = ?",
            ):
                connection.execute(sql, (principal_id,))
            connection.executemany(
                "DELETE FROM approved_memory_fts WHERE memory_id = ?",
                [(memory_id,) for memory_id in memory_ids],
            )
            connection.executemany(
                "DELETE FROM memory_projections WHERE memory_id = ?",
                [(memory_id,) for memory_id in memory_ids],
            )
            connection.execute(
                "UPDATE principals SET is_active = 0 WHERE principal_id = ?", (principal_id,)
            )
            if user_id:
                connection.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            self._delete_rows_orphaned_by_purge(connection)
            if connection.execute("SELECT 1 FROM account_credentials LIMIT 1").fetchone() is None:
                connection.execute("DELETE FROM instance_account_guard WHERE singleton = 1")
        # Durable markdown exports are plaintext on disk and outlive the rows.
        memory_dir = self.paths.workspace_root / ".raiker" / "memory"
        for memory_id in memory_ids:
            with contextlib.suppress(OSError):
                (memory_dir / f"{memory_id}.md").unlink(missing_ok=True)

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

    def get_latest_runtime_mode(self) -> dict[str, Any] | None:
        """The most recent runtime state row, active or not.

        ``get_active_runtime_mode`` filters on ``status = 'active'``, so it
        cannot tell "never configured" from "the owner switched the runtime
        off" — both come back as ``None``. With one runtime that distinction is
        the whole of the remaining runtime question, so the authority reads the
        latest row and looks at its status itself.
        """
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM runtime_mode_state ORDER BY created_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def get_principal_runtime_mode(self, principal_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM principal_runtime_mode_state WHERE principal_id = ?", (principal_id,)
            ).fetchone()
        return dict(row) if row else None

    def upsert_principal_runtime_mode(self, principal_id: str, record: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO principal_runtime_mode_state
                (principal_id, mode_name, status, activated_by, activated_at, reason, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (principal_id, record["mode_name"], record["status"], record.get("activated_by"),
                 record.get("activated_at"), record.get("reason"), record["updated_at"]),
            )

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

    def get_principal_capability_gate_state(
        self, principal_id: str, capability: str
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM principal_capability_gate_state WHERE principal_id = ? AND capability = ?",
                (principal_id, capability),
            ).fetchone()
        return dict(row) if row else None

    def list_principal_capability_gate_states(self, principal_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM principal_capability_gate_state WHERE principal_id = ? ORDER BY capability",
                (principal_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_principal_capability_gate_state(self, principal_id: str, record: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO principal_capability_gate_state
                (principal_id, capability, state, requested_by, requested_at, activated_by, activated_at,
                 reason, readiness_snapshot_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (principal_id, record["capability"], record["state"], record.get("requested_by"),
                 record.get("requested_at"), record.get("activated_by"), record.get("activated_at"),
                 record.get("reason"), record.get("readiness_snapshot_json"), record["created_at"],
                 record["updated_at"]),
            )

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

    def get_principal_capability_decision_mode(self, principal_id: str, capability: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT decision_mode FROM principal_capability_decision_mode "
                "WHERE principal_id = ? AND capability = ?", (principal_id, capability)
            ).fetchone()
        return str(row["decision_mode"]) if row else None

    def list_principal_capability_decision_modes(self, principal_id: str) -> dict[str, str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT capability, decision_mode FROM principal_capability_decision_mode WHERE principal_id = ?",
                (principal_id,),
            ).fetchall()
        return {str(row["capability"]): str(row["decision_mode"]) for row in rows}

    def upsert_principal_capability_decision_mode(
        self, principal_id: str, record: dict[str, Any]
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO principal_capability_decision_mode
                (principal_id, capability, decision_mode, set_by, set_at, reason, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (principal_id, record["capability"], record["decision_mode"], record.get("set_by"),
                 record.get("set_at"), record.get("reason"), record["created_at"], record["updated_at"]),
            )

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
