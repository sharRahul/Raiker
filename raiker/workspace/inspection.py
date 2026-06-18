from __future__ import annotations

from pathlib import Path
from typing import Any

from raiker.approval_audit_registry import approval_audit_summary
from raiker.approval_preview_registry import approval_preview_summary
from raiker.channels.registry import ConnectorRegistry
from raiker.checkpoints.service import CheckpointService
from raiker.contracts.models import ClientMetadata
from raiker.events.query import EventViewer
from raiker.execution.profiles import list_execution_profiles
from raiker.graph.governance import graph_governance_status
from raiker.memory.governance import memory_governance_summary
from raiker.memory.semantic import semantic_memory_status
from raiker.models.registry import ModelProfileRegistry
from raiker.phase_gates import list_capability_states
from raiker.plugins.registry import PluginPlanRegistry
from raiker.rollback_registry import rollback_plan_summary
from raiker.storage.lifecycle_registry import (
    lifecycle_evidence_summary,
    retention_cleanup_handoff_summary,
    storage_lifecycle_summary,
)
from raiker.storage.sqlite import SQLiteStore

INSPECTION_CLIENT_TYPES = {"terminal", "desktop", "web", "dashboard"}
_CLIENT_TYPE_MAP = {
    "terminal": "tui",
    "desktop": "desktop",
    "web": "web_ui",
    "dashboard": "dashboard",
}


def inspection_client(client_type: str) -> ClientMetadata:
    if client_type not in INSPECTION_CLIENT_TYPES:
        raise PermissionError(f"unsupported_inspection_client:{client_type}")
    return ClientMetadata(
        type=_CLIENT_TYPE_MAP[client_type],
        name=f"raiker-{client_type}-inspection",
        version="0.0.0",
        interface_status="equal_primary_when_enabled",
    )


def inspect_workspace(client_type: str, *, workspace_root: str | Path = ".") -> dict[str, Any]:
    client = inspection_client(client_type)
    store = SQLiteStore(workspace_root)
    events = EventViewer(store).list_events(limit=10)
    sessions = store.list_sessions(limit=10)
    checkpoints = CheckpointService(store).list_checkpoints(limit=10)
    approvals = store.list_approvals(status="pending")
    tasks = store.list_tasks()
    model_profiles = ModelProfileRegistry.load().list_profiles()
    connectors = ConnectorRegistry.load().list_profiles()
    memory_candidates = store.list_memory_candidates()
    plugin_plans = PluginPlanRegistry().list_plans()
    return {
        "contract": {
            "service": "workspace_inspection",
            "read_only": True,
            "shared_contract_path": True,
            "client": {
                "type": client.type,
                "name": client.name,
                "version": client.version,
                "interface_status": client.interface_status,
                "privileged": False,
            },
        },
        "runtime_status": {
            "workspace_root": str(store.paths.workspace_root),
            "session_count": len(sessions),
            "latest_session_id": sessions[0].get("session_id") if sessions else None,
        },
        "recent_events": [
            {"event_id": e["event_id"], "event_type": e["event_type"], "timestamp": e["timestamp"]}
            for e in events
        ],
        "checkpoint_timeline": [
            {
                "checkpoint_id": c["checkpoint_id"],
                "created_at": c["created_at"],
                "summary": c.get("summary"),
            }
            for c in checkpoints
        ],
        "tasks": [
            {
                "task_id": t.task_id,
                "title": t.title,
                "status": t.status,
                "progress_percent": t.progress_percent,
            }
            for t in tasks
        ],
        "approvals": [
            {
                "approval_id": a["approval_id"],
                "status": a["status"],
                "risk_level": a.get("risk_level"),
            }
            for a in approvals
        ],
        "model_profiles": [
            {
                "profile_id": p.profile_id,
                "provider": p.provider,
                "model": p.model,
                "default_state": p.default_state,
            }
            for p in model_profiles
        ],
        "channel_connectors": [
            {
                "connector_id": c.connector_id,
                "channel_type": c.channel_type,
                "default_state": c.default_state,
            }
            for c in connectors
        ],
        "capability_gates": list_capability_states(),
        "semantic_memory": semantic_memory_status(len(memory_candidates))
        | memory_governance_summary(workspace_root),
        "graph_codemap": graph_governance_status(),
        "execution_profiles": [
            {
                "profile_id": p.profile_id,
                "kind": p.kind,
                "state": p.default_state,
                "requires_approval": p.requires_approval,
            }
            for p in list_execution_profiles()
        ],
        "plugin_registration_plans": plugin_plans,
        "approval_preview_summary": approval_preview_summary(workspace_root=workspace_root),
        "approval_audit_summary": approval_audit_summary(workspace_root=workspace_root),
        "rollback_plan_summary": rollback_plan_summary(workspace_root=workspace_root),
        "storage_lifecycle_summary": storage_lifecycle_summary(workspace_root=workspace_root),
        "storage_lifecycle_retention_summary": retention_cleanup_handoff_summary(workspace_root=workspace_root),
        "storage_lifecycle_evidence_summary": lifecycle_evidence_summary(workspace_root=workspace_root),
    }
