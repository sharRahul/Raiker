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
        "execution_profiles": safe["execution_profiles"],
        "plugin_registration_plans": safe["plugin_registration_plans"],
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
    lines.append(f"semantic_writes_enabled: {view['semantic_memory']['semantic_writes_enabled']}")
    lines.append(
        f"approval_preview_only_mode: {view['approval_preview_summary']['preview_only_mode']}"
    )
    lines.append(
        f"approval_preview_runtime_execution_enabled: {view['approval_preview_summary']['runtime_execution_enabled']}"
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
        "approval_preview_summary": view["approval_preview_summary"],
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
