from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.storage.lifecycle import _stable_id, json_safe_metadata, redact_metadata
from raiker.storage.lifecycle_retention import stable_id

DISABLED_EXECUTION_FLAGS: dict[str, bool] = {
    "cleanup_execution_enabled": False,
    "graph_runtime_indexing_enabled": False,
    "graph_writes_enabled": False,
    "semantic_memory_write_enabled": False,
    "vector_write_enabled": False,
    "embedding_write_enabled": False,
    "rollback_execution_enabled": False,
    "plugin_execution_enabled": False,
    "mcp_lsp_plugin_server_startup_enabled": False,
    "monitor_watch_daemon_enabled": False,
    "external_channel_enabled": False,
    "approval_relay_enabled": False,
    "channel_execution_enabled": False,
    "subagent_execution_enabled": False,
    "multi_agent_team_execution_enabled": False,
    "remote_execution_enabled": False,
    "container_execution_enabled": False,
    "cloud_execution_enabled": False,
    "hosted_routines_enabled": False,
    "marketplace_installs_enabled": False,
    "hosted_push_notifications_enabled": False,
    "share_links_enabled": False,
}


def _execution_flags(workspace_id: str) -> dict[str, bool]:
    flags = DISABLED_EXECUTION_FLAGS.copy()
    try:
        from raiker.remote.readiness_registry import remote_readiness_summary

        flags["container_execution_enabled"] = bool(
            remote_readiness_summary(workspace_root=workspace_id).get(
                "container_execution_enabled", False
            )
        )
    except (OSError, ValueError):
        flags["container_execution_enabled"] = False
    return flags


def _safe_ids(values: Sequence[str] | None, field_name: str) -> list[str]:
    ids = sorted({str(value) for value in values or [] if str(value)})
    if values is not None and len(ids) != len([value for value in values if str(value)]):
        raise ValueError(f"duplicate_or_empty_{field_name}")
    return ids


def _json_ready(value: Any) -> Any:
    safe = redact_metadata(value)
    json.dumps(safe, sort_keys=True, default=str)
    return safe


@dataclass(frozen=True)
class StorageLifecycleEvidenceBundle:
    evidence_id: str
    workspace_id: str
    created_at: str
    source_lifecycle_ids: list[str]
    source_retention_policy_ids: list[str]
    source_cleanup_preview_ids: list[str]
    source_approval_handoff_ids: list[str]
    record_counts: dict[str, int]
    status_counts: dict[str, int]
    disabled_execution_flags: dict[str, bool]
    redacted_summary: dict[str, Any]
    metadata_only: bool
    export_only: bool
    can_execute_now: bool
    execution_enabled: bool

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class StorageLifecyclePolicySimulation:
    simulation_id: str
    workspace_id: str
    input_retention_policy_ids: list[str]
    input_cleanup_preview_ids: list[str]
    simulated_outcome: str
    would_expire_count: int
    would_cleanup_count: int
    would_handoff_count: int
    blocked_count: int
    blocked_reasons: list[str]
    required_future_policy: str
    metadata_only: bool
    simulation_only: bool
    can_execute_now: bool
    execution_enabled: bool
    disabled_execution_flags: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def create_evidence_bundle(
    *,
    workspace_id: str,
    source_lifecycle_ids: Sequence[str] | None = None,
    source_retention_policy_ids: Sequence[str] | None = None,
    source_cleanup_preview_ids: Sequence[str] | None = None,
    source_approval_handoff_ids: Sequence[str] | None = None,
    record_counts: Mapping[str, int] | None = None,
    status_counts: Mapping[str, int] | None = None,
    redacted_summary: Mapping[str, Any] | None = None,
    created_at: str | None = None,
) -> StorageLifecycleEvidenceBundle:
    if not workspace_id:
        raise ValueError("workspace_id_required")
    lifecycle_ids = _safe_ids(source_lifecycle_ids, "source_lifecycle_ids")
    policy_ids = _safe_ids(source_retention_policy_ids, "source_retention_policy_ids")
    preview_ids = _safe_ids(source_cleanup_preview_ids, "source_cleanup_preview_ids")
    handoff_ids = _safe_ids(source_approval_handoff_ids, "source_approval_handoff_ids")
    counts = {str(k): int(v) for k, v in sorted((record_counts or {}).items())}
    statuses = {str(k): int(v) for k, v in sorted((status_counts or {}).items())}
    summary = json_safe_metadata(dict(redacted_summary or {}))
    execution_flags = _execution_flags(workspace_id)
    identity = {
        "workspace_id": workspace_id,
        "source_lifecycle_ids": lifecycle_ids,
        "source_retention_policy_ids": policy_ids,
        "source_cleanup_preview_ids": preview_ids,
        "source_approval_handoff_ids": handoff_ids,
        "record_counts": counts,
        "status_counts": statuses,
        "disabled_execution_flags": execution_flags,
        "redacted_summary": summary,
        "metadata_only": True,
        "export_only": True,
        "can_execute_now": False,
        "execution_enabled": False,
    }
    return StorageLifecycleEvidenceBundle(
        evidence_id=_stable_id("sleb_", identity),
        workspace_id=workspace_id,
        created_at=created_at or utc_now(),
        source_lifecycle_ids=lifecycle_ids,
        source_retention_policy_ids=policy_ids,
        source_cleanup_preview_ids=preview_ids,
        source_approval_handoff_ids=handoff_ids,
        record_counts=counts,
        status_counts=statuses,
        disabled_execution_flags=execution_flags,
        redacted_summary=summary,
        metadata_only=True,
        export_only=True,
        can_execute_now=False,
        execution_enabled=False,
    )


def create_policy_simulation(
    *,
    workspace_id: str,
    input_retention_policy_ids: Sequence[str] | None = None,
    input_cleanup_preview_ids: Sequence[str] | None = None,
    would_expire_count: int = 0,
    would_cleanup_count: int = 0,
    would_handoff_count: int = 0,
    blocked_reasons: Sequence[str] | None = None,
    required_future_policy: str = "future_cleanup_execution_policy_required",
) -> StorageLifecyclePolicySimulation:
    if not workspace_id:
        raise ValueError("workspace_id_required")
    policy_ids = _safe_ids(input_retention_policy_ids, "input_retention_policy_ids")
    preview_ids = _safe_ids(input_cleanup_preview_ids, "input_cleanup_preview_ids")
    reasons = sorted({str(_json_ready(reason)) for reason in blocked_reasons or []})
    if not reasons:
        reasons = ["runtime_execution_disabled", "metadata_only_simulation"]
    blocked_count = len(reasons)
    outcome = "blocked_metadata_only_simulation"
    identity = {
        "workspace_id": workspace_id,
        "input_retention_policy_ids": policy_ids,
        "input_cleanup_preview_ids": preview_ids,
        "simulated_outcome": outcome,
        "would_expire_count": int(would_expire_count),
        "would_cleanup_count": int(would_cleanup_count),
        "would_handoff_count": int(would_handoff_count),
        "blocked_count": blocked_count,
        "blocked_reasons": reasons,
        "required_future_policy": str(_json_ready(required_future_policy)),
        "disabled_execution_flags": DISABLED_EXECUTION_FLAGS,
        "metadata_only": True,
        "simulation_only": True,
        "can_execute_now": False,
        "execution_enabled": False,
    }
    return StorageLifecyclePolicySimulation(
        simulation_id=stable_id("slps_", identity),
        workspace_id=workspace_id,
        input_retention_policy_ids=policy_ids,
        input_cleanup_preview_ids=preview_ids,
        simulated_outcome=outcome,
        would_expire_count=int(would_expire_count),
        would_cleanup_count=int(would_cleanup_count),
        would_handoff_count=int(would_handoff_count),
        blocked_count=blocked_count,
        blocked_reasons=reasons,
        required_future_policy=str(_json_ready(required_future_policy)),
        metadata_only=True,
        simulation_only=True,
        can_execute_now=False,
        execution_enabled=False,
        disabled_execution_flags=DISABLED_EXECUTION_FLAGS.copy(),
    )
