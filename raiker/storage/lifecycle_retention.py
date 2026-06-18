from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from raiker.storage.lifecycle import redact_metadata

ALLOWED_TARGET_TYPES = {
    "graph_codemap_indexing",
    "semantic_memory_writes",
    "approval_preview_metadata",
    "approval_audit_metadata",
    "rollback_plan_metadata",
    "storage_lifecycle_metadata",
}
ALLOWED_RETENTION_CLASSES = {"ephemeral", "short_term", "audit_metadata", "manual_hold"}
ALLOWED_EXPIRY_RULES = {
    "none",
    "expire_after_30_days",
    "expire_after_90_days",
    "supersede_on_newer_preview",
    "manual_review_required",
}


def stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return f"{prefix}{hashlib.sha256(encoded).hexdigest()[:24]}"


def json_safe(value: Any) -> Any:
    safe = redact_metadata(value)
    json.dumps(safe, sort_keys=True, default=str)
    return safe


def _safe_list(values: Sequence[str] | None) -> list[str]:
    return sorted({str(v) for v in values or []})


@dataclass(frozen=True)
class StorageLifecycleRetentionPolicy:
    policy_id: str
    lifecycle_target_type: str
    retention_class: str
    expiry_rule: str
    cleanup_eligible: bool
    legal_hold: bool
    manual_hold: bool
    redacted_reason_summary: str
    metadata_only: bool
    can_execute_now: bool
    execution_enabled: bool
    runtime_execution_enabled: bool
    cleanup_execution_enabled: bool
    graph_indexing_enabled: bool
    semantic_memory_writes_enabled: bool
    vector_writes_enabled: bool
    embedding_creation_enabled: bool
    rollback_execution_enabled: bool
    plugin_execution_enabled: bool
    mcp_lsp_plugin_server_startup_enabled: bool
    monitor_watch_daemon_enabled: bool
    external_channel_enabled: bool
    approval_relay_enabled: bool
    channel_execution_enabled: bool
    subagent_execution_enabled: bool
    multi_agent_team_execution_enabled: bool
    remote_execution_enabled: bool
    container_execution_enabled: bool
    cloud_execution_enabled: bool
    hosted_routines_enabled: bool
    marketplace_installs_enabled: bool
    hosted_push_notifications_enabled: bool
    share_links_enabled: bool
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def create_retention_policy(
    *,
    lifecycle_target_type: str,
    retention_class: str,
    expiry_rule: str,
    cleanup_eligible: bool = False,
    legal_hold: bool = False,
    manual_hold: bool = False,
    reason_summary: str = "metadata-only retention planning",
    metadata: Mapping[str, Any] | None = None,
) -> StorageLifecycleRetentionPolicy:
    if lifecycle_target_type not in ALLOWED_TARGET_TYPES:
        raise ValueError(f"invalid_lifecycle_target_type:{lifecycle_target_type}")
    if retention_class not in ALLOWED_RETENTION_CLASSES:
        raise ValueError(f"invalid_retention_class:{retention_class}")
    if expiry_rule not in ALLOWED_EXPIRY_RULES:
        raise ValueError(f"invalid_expiry_rule:{expiry_rule}")
    safe_meta = json_safe(dict(metadata or {}))
    reason = str(json_safe(reason_summary))
    identity = {
        "lifecycle_target_type": lifecycle_target_type,
        "retention_class": retention_class,
        "expiry_rule": expiry_rule,
        "cleanup_eligible": bool(cleanup_eligible),
        "legal_hold": bool(legal_hold),
        "manual_hold": bool(manual_hold),
        "reason": reason,
        "metadata": safe_meta,
    }
    return StorageLifecycleRetentionPolicy(
        policy_id=stable_id("slrp_", identity),
        lifecycle_target_type=lifecycle_target_type,
        retention_class=retention_class,
        expiry_rule=expiry_rule,
        cleanup_eligible=bool(cleanup_eligible) and not legal_hold and not manual_hold,
        legal_hold=bool(legal_hold),
        manual_hold=bool(manual_hold),
        redacted_reason_summary=reason,
        metadata_only=True,
        can_execute_now=False,
        execution_enabled=False,
        runtime_execution_enabled=False,
        cleanup_execution_enabled=False,
        graph_indexing_enabled=False,
        semantic_memory_writes_enabled=False,
        vector_writes_enabled=False,
        embedding_creation_enabled=False,
        rollback_execution_enabled=False,
        plugin_execution_enabled=False,
        mcp_lsp_plugin_server_startup_enabled=False,
        monitor_watch_daemon_enabled=False,
        external_channel_enabled=False,
        approval_relay_enabled=False,
        channel_execution_enabled=False,
        subagent_execution_enabled=False,
        multi_agent_team_execution_enabled=False,
        remote_execution_enabled=False,
        container_execution_enabled=False,
        cloud_execution_enabled=False,
        hosted_routines_enabled=False,
        marketplace_installs_enabled=False,
        hosted_push_notifications_enabled=False,
        share_links_enabled=False,
        metadata=safe_meta,
    )


@dataclass(frozen=True)
class StorageLifecycleCleanupPreview:
    preview_id: str
    linked_lifecycle_ids: list[str]
    expired_candidate_count: int
    superseded_candidate_count: int
    redacted_summaries: list[str]
    can_cleanup_now: bool
    cleanup_execution_enabled: bool
    graph_execution_enabled: bool
    memory_execution_enabled: bool
    vector_execution_enabled: bool
    embedding_execution_enabled: bool
    rollback_execution_enabled: bool
    plugin_execution_enabled: bool
    mcp_lsp_plugin_server_startup_enabled: bool
    monitor_watch_daemon_enabled: bool
    external_channel_enabled: bool
    approval_relay_enabled: bool
    channel_execution_enabled: bool
    subagent_execution_enabled: bool
    multi_agent_team_execution_enabled: bool
    remote_execution_enabled: bool
    container_execution_enabled: bool
    cloud_execution_enabled: bool
    hosted_routines_enabled: bool
    marketplace_installs_enabled: bool
    hosted_push_notifications_enabled: bool
    share_links_enabled: bool
    metadata_only: bool

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def create_cleanup_preview(
    *,
    linked_lifecycle_ids: Sequence[str],
    expired_candidate_count: int = 0,
    superseded_candidate_count: int = 0,
    summaries: Sequence[str] | None = None,
) -> StorageLifecycleCleanupPreview:
    links = _safe_list(linked_lifecycle_ids)
    redacted = [str(json_safe(s)) for s in _safe_list(summaries)]
    identity = {
        "linked_lifecycle_ids": links,
        "expired": expired_candidate_count,
        "superseded": superseded_candidate_count,
        "summaries": redacted,
    }
    return StorageLifecycleCleanupPreview(
        stable_id("slcp_", identity),
        links,
        int(expired_candidate_count),
        int(superseded_candidate_count),
        redacted,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        True,
    )


ALLOWED_HANDOFF_STATES = {"handoff_planned", "blocked", "requires_future_policy"}


@dataclass(frozen=True)
class StorageLifecycleApprovalHandoff:
    handoff_id: str
    linked_lifecycle_ids: list[str]
    source_preview_ids: list[str]
    source_audit_ids: list[str]
    source_rollback_plan_ids: list[str]
    target_capability: str
    approval_state: str
    can_execute_now: bool
    execution_enabled: bool
    cleanup_execution_enabled: bool
    graph_indexing_enabled: bool
    semantic_memory_writes_enabled: bool
    vector_writes_enabled: bool
    embedding_creation_enabled: bool
    rollback_execution_enabled: bool
    plugin_execution_enabled: bool
    mcp_lsp_plugin_server_startup_enabled: bool
    monitor_watch_daemon_enabled: bool
    external_channel_enabled: bool
    approval_relay_enabled: bool
    channel_execution_enabled: bool
    subagent_execution_enabled: bool
    multi_agent_team_execution_enabled: bool
    remote_execution_enabled: bool
    container_execution_enabled: bool
    cloud_execution_enabled: bool
    hosted_routines_enabled: bool
    marketplace_installs_enabled: bool
    hosted_push_notifications_enabled: bool
    share_links_enabled: bool
    redacted_summary: str
    metadata_only: bool

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def create_approval_handoff(
    *,
    linked_lifecycle_ids: Sequence[str],
    target_capability: str,
    approval_state: str = "handoff_planned",
    source_preview_ids: Sequence[str] | None = None,
    source_audit_ids: Sequence[str] | None = None,
    source_rollback_plan_ids: Sequence[str] | None = None,
    summary: str = "approval handoff planned as metadata only",
) -> StorageLifecycleApprovalHandoff:
    if target_capability not in ALLOWED_TARGET_TYPES:
        raise ValueError(f"invalid_handoff_target_capability:{target_capability}")
    if approval_state not in ALLOWED_HANDOFF_STATES:
        raise ValueError(f"invalid_handoff_approval_state:{approval_state}")
    links = _safe_list(linked_lifecycle_ids)
    previews = _safe_list(source_preview_ids)
    audits = _safe_list(source_audit_ids)
    rollbacks = _safe_list(source_rollback_plan_ids)
    safe_summary = str(json_safe(summary))
    identity = {
        "linked_lifecycle_ids": links,
        "source_preview_ids": previews,
        "source_audit_ids": audits,
        "source_rollback_plan_ids": rollbacks,
        "target_capability": target_capability,
        "approval_state": approval_state,
        "summary": safe_summary,
    }
    return StorageLifecycleApprovalHandoff(
        handoff_id=stable_id("slah_", identity),
        linked_lifecycle_ids=links,
        source_preview_ids=previews,
        source_audit_ids=audits,
        source_rollback_plan_ids=rollbacks,
        target_capability=target_capability,
        approval_state=approval_state,
        can_execute_now=False,
        execution_enabled=False,
        cleanup_execution_enabled=False,
        graph_indexing_enabled=False,
        semantic_memory_writes_enabled=False,
        vector_writes_enabled=False,
        embedding_creation_enabled=False,
        rollback_execution_enabled=False,
        plugin_execution_enabled=False,
        mcp_lsp_plugin_server_startup_enabled=False,
        monitor_watch_daemon_enabled=False,
        external_channel_enabled=False,
        approval_relay_enabled=False,
        channel_execution_enabled=False,
        subagent_execution_enabled=False,
        multi_agent_team_execution_enabled=False,
        remote_execution_enabled=False,
        container_execution_enabled=False,
        cloud_execution_enabled=False,
        hosted_routines_enabled=False,
        marketplace_installs_enabled=False,
        hosted_push_notifications_enabled=False,
        share_links_enabled=False,
        redacted_summary=safe_summary,
        metadata_only=True,
    )
