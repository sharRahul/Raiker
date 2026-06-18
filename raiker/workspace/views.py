from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from raiker.workspace.inspection import inspect_workspace

SECRET_MARKERS = (
    "secret",
    "token",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "credential",
    "private_key",
)
CLIENT_VIEW_TYPES = ("terminal", "desktop", "web", "dashboard")


def _is_secret_key(key: object) -> bool:
    return isinstance(key, str) and any(marker in key.lower() for marker in SECRET_MARKERS)


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): ("[REDACTED]" if _is_secret_key(key) else _redact(val))
            for key, val in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, list | tuple):
        return [_redact(item) for item in value]
    return value


def _json_safe(value: Any) -> Any:
    redacted = _redact(value)
    json.dumps(redacted, sort_keys=True)
    return redacted


def workspace_view_summary(inspection: Mapping[str, Any]) -> dict[str, Any]:
    """Render shared workspace inspection output into a deterministic read-only view."""
    safe = _json_safe(inspection)
    contract = safe["contract"]
    runtime = safe["runtime_status"]
    return {
        "contract": contract,
        "runtime_status": runtime,
        "counts": {
            "approvals": len(safe["approvals"]),
            "checkpoint_timeline": len(safe["checkpoint_timeline"]),
            "channel_connectors": len(safe["channel_connectors"]),
            "execution_profiles": len(safe["execution_profiles"]),
            "model_profiles": len(safe["model_profiles"]),
            "plugin_registration_plans": len(safe["plugin_registration_plans"]),
            "recent_events": len(safe["recent_events"]),
            "tasks": len(safe["tasks"]),
        },
        "capability_gates": safe["capability_gates"],
        "semantic_memory": safe["semantic_memory"],
        "graph_codemap": safe.get(
            "graph_codemap", {"graph_indexing_enabled": False, "planning_available": True}
        ),
        "semantic_memory_readiness": safe.get(
            "semantic_memory_readiness",
            {
                "semantic_memory_readiness_contract_available": True,
                "semantic_memory_readiness_record_count": 0,
                "metadata_only": True,
                "ready_for_memory_writes": False,
                "semantic_memory_writes_enabled": False,
                "vector_writes_enabled": False,
                "embedding_creation_enabled": False,
                "embedding_storage_enabled": False,
                "vector_indexing_enabled": False,
                "memory_write_jobs_enabled": False,
                "runtime_execution_enabled": False,
                "blocker_count": 0,
            },
        ),
        "graph_codemap_readiness": safe.get(
            "graph_codemap_readiness",
            {
                "graph_readiness_contract_available": True,
                "graph_readiness_record_count": 0,
                "metadata_only": True,
                "ready_for_indexing": False,
                "graph_indexing_enabled": False,
                "graph_writes_enabled": False,
                "runtime_jobs_enabled": False,
            },
        ),
        "execution_profiles": safe["execution_profiles"],
        "plugin_registration_plans": safe["plugin_registration_plans"],
        "approval_audit_summary": safe.get(
            "approval_audit_summary",
            {
                "audit_preview_available": True,
                "audit_record_count": 0,
                "denied_count": 0,
                "approved_for_later_count": 0,
                "execution_blocked_count": 0,
                "execution_enabled": False,
            },
        ),
        "rollback_plan_summary": safe.get(
            "rollback_plan_summary",
            {
                "graph_rollback_plan_available": True,
                "memory_rollback_plan_available": True,
                "rollback_execution_enabled": False,
                "preview_only_mode": True,
            },
        ),
        "storage_lifecycle_retention_summary": safe.get(
            "storage_lifecycle_retention_summary",
            {
                "retention_policy_count": 0,
                "cleanup_preview_count": 0,
                "approval_handoff_count": 0,
                "expired_lifecycle_count": 0,
                "superseded_lifecycle_count": 0,
                "metadata_only": True,
                "cleanup_execution_enabled": False,
                "approval_handoff_execution_enabled": False,
            },
        ),
        "storage_lifecycle_evidence_summary": safe.get(
            "storage_lifecycle_evidence_summary",
            {
                "lifecycle_evidence_bundle_count": 0,
                "lifecycle_policy_simulation_count": 0,
                "latest_evidence_id": None,
                "latest_policy_simulation_id": None,
                "metadata_only": True,
                "export_only": True,
                "simulation_only": True,
                "execution_enabled": False,
                "cleanup_execution_enabled": False,
                "approval_relay_enabled": False,
                "graph_runtime_indexing_enabled": False,
                "semantic_memory_write_enabled": False,
                "vector_write_enabled": False,
                "embedding_write_enabled": False,
                "rollback_execution_enabled": False,
                "plugin_execution_enabled": False,
                "channel_execution_enabled": False,
                "subagent_execution_enabled": False,
                "remote_execution_enabled": False,
                "container_execution_enabled": False,
                "cloud_execution_enabled": False,
            },
        ),
        "storage_lifecycle_summary": safe.get(
            "storage_lifecycle_summary",
            {
                "lifecycle_planning_available": True,
                "lifecycle_record_count": 0,
                "graph_lifecycle_records": 0,
                "memory_lifecycle_records": 0,
                "preview_only_count": 0,
                "runtime_blocked_count": 0,
                "runtime_writes_enabled": False,
                "graph_runtime_writes_enabled": False,
                "semantic_runtime_writes_enabled": False,
            },
        ),
        "approval_preview_summary": safe.get(
            "approval_preview_summary",
            {
                "graph_indexing_preview_available": True,
                "semantic_memory_write_preview_available": True,
                "pending_preview_count": 0,
                "denied_preview_count": 0,
                "preview_only_mode": True,
                "runtime_execution_enabled": False,
            },
        ),
    }


def render_workspace_text_summary(inspection: Mapping[str, Any]) -> str:
    view = workspace_view_summary(inspection)
    client = view["contract"]["client"]
    lines = [
        "Workspace view:",
        f"client: {client['type']}",
        f"read_only: {view['contract']['read_only']}",
        f"shared_contract_path: {view['contract']['shared_contract_path']}",
        f"workspace_root: {view['runtime_status']['workspace_root']}",
        f"sessions: {view['runtime_status']['session_count']}",
    ]
    for key, count in view["counts"].items():
        lines.append(f"{key}: {count}")
    disabled_runtime = sorted(
        name for name, gate in view["capability_gates"].items() if gate["runtime_enabled"] is False
    )
    lines.append(f"runtime_disabled: {', '.join(disabled_runtime)}")
    lines.append(
        f"plugin_execution_enabled: {view['capability_gates']['plugin_execution']['runtime_enabled']}"
    )
    lines.append(f"graph_indexing_enabled: {view['graph_codemap']['graph_indexing_enabled']}")
    lines.append(f"graph_planning_available: {view['graph_codemap']['planning_available']}")
    lines.append(
        f"graph_readiness_metadata_only: {view['graph_codemap_readiness']['metadata_only']}"
    )
    lines.append(
        f"graph_readiness_ready_for_indexing: {view['graph_codemap_readiness']['ready_for_indexing']}"
    )
    lines.append(f"semantic_writes_enabled: {view['semantic_memory']['semantic_writes_enabled']}")
    lines.append(f"semantic_memory_readiness_metadata_only: {view['semantic_memory_readiness']['metadata_only']}")
    lines.append(f"semantic_memory_ready_for_writes: {view['semantic_memory_readiness']['ready_for_memory_writes']}")
    lines.append(f"semantic_memory_readiness_latest_id: {view['semantic_memory_readiness']['latest_readiness_id']}")
    lines.append(f"semantic_memory_readiness_blockers: {view['semantic_memory_readiness']['blocker_count']}")
    lines.append(f"semantic_vector_writes_enabled: {view['semantic_memory_readiness']['vector_writes_enabled']}")
    lines.append(f"semantic_embedding_creation_enabled: {view['semantic_memory_readiness']['embedding_creation_enabled']}")
    lines.append(f"semantic_memory_write_jobs_enabled: {view['semantic_memory_readiness']['memory_write_jobs_enabled']}")
    lines.append(
        f"approval_preview_only_mode: {view['approval_preview_summary']['preview_only_mode']}"
    )
    lines.append(
        f"approval_preview_runtime_execution_enabled: {view['approval_preview_summary']['runtime_execution_enabled']}"
    )
    lines.append(
        f"approval_audit_execution_enabled: {view['approval_audit_summary']['execution_enabled']}"
    )
    lines.append(
        f"rollback_execution_enabled: {view['rollback_plan_summary']['rollback_execution_enabled']}"
    )
    lines.append(
        f"storage_lifecycle_records: {view['storage_lifecycle_summary']['lifecycle_record_count']}"
    )
    lines.append(
        f"storage_lifecycle_runtime_writes_enabled: {view['storage_lifecycle_summary']['runtime_writes_enabled']}"
    )
    lines.append(
        f"storage_lifecycle_retention_policies: {view['storage_lifecycle_retention_summary']['retention_policy_count']}"
    )
    lines.append(
        f"storage_lifecycle_cleanup_previews: {view['storage_lifecycle_retention_summary']['cleanup_preview_count']}"
    )
    lines.append(
        f"storage_lifecycle_approval_handoffs: {view['storage_lifecycle_retention_summary']['approval_handoff_count']}"
    )
    lines.append(
        f"storage_lifecycle_evidence_bundles: {view['storage_lifecycle_evidence_summary']['lifecycle_evidence_bundle_count']}"
    )
    lines.append(
        f"storage_lifecycle_policy_simulations: {view['storage_lifecycle_evidence_summary']['lifecycle_policy_simulation_count']}"
    )
    lines.append(
        f"storage_lifecycle_evidence_execution_enabled: {view['storage_lifecycle_evidence_summary']['execution_enabled']}"
    )
    lines.append(
        f"memory_governance_mode: {view['semantic_memory'].get('memory_governance_mode', 'review_queue_only_no_semantic_writes')}"
    )
    return "\n".join(lines)


def render_workspace_json_summary(inspection: Mapping[str, Any]) -> dict[str, Any]:
    return workspace_view_summary(inspection)


def render_workspace_dashboard_summary(inspection: Mapping[str, Any]) -> dict[str, Any]:
    view = workspace_view_summary(inspection)
    return {
        "workspace": view["runtime_status"],
        "counts": view["counts"],
        "capabilities": view["capability_gates"],
        "semantic_memory": view["semantic_memory"],
        "graph_codemap": view["graph_codemap"],
        "semantic_memory_readiness": view["semantic_memory_readiness"],
        "approval_preview_summary": view["approval_preview_summary"],
        "approval_audit_summary": view["approval_audit_summary"],
        "rollback_plan_summary": view["rollback_plan_summary"],
        "storage_lifecycle_summary": view["storage_lifecycle_summary"],
        "storage_lifecycle_retention_summary": view["storage_lifecycle_retention_summary"],
        "storage_lifecycle_evidence_summary": view["storage_lifecycle_evidence_summary"],
    }


def render_client_capability_summary(inspection: Mapping[str, Any]) -> dict[str, Any]:
    view = workspace_view_summary(inspection)
    return {
        "client": view["contract"]["client"],
        "read_only": view["contract"]["read_only"],
        "shared_contract_path": view["contract"]["shared_contract_path"],
        "capabilities": view["capability_gates"],
    }


def render_plugin_plan_summary(inspection: Mapping[str, Any]) -> dict[str, Any]:
    view = workspace_view_summary(inspection)
    return {
        "plugin_registration_plans": view["plugin_registration_plans"],
        "plugin_execution": view["capability_gates"].get("plugin_execution"),
    }


def render_workspace_view(
    *, workspace_root: str | Path = ".", client_type: str = "terminal"
) -> str:
    return render_workspace_text_summary(
        inspect_workspace(client_type, workspace_root=workspace_root)
    )
