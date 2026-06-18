from __future__ import annotations

import copy
import json
from typing import Any

_SECRET_MARKERS = ("secret", "token", "password", "api_key", "apikey", "credential", "private_key")


def _is_secret_key(key: object) -> bool:
    return any(marker in str(key).lower() for marker in _SECRET_MARKERS)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            text_key = str(key)
            redacted[text_key] = "[redacted]" if _is_secret_key(text_key) else _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return value


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(_redact(value), sort_keys=True, default=str))


def _items(summary: dict[str, object], key: str) -> list[Any]:
    value = summary.get(key, [])
    return value if isinstance(value, list) else []


def _mapping(summary: dict[str, object], key: str) -> dict[str, Any]:
    value = summary.get(key, {})
    return value if isinstance(value, dict) else {}


def _client(summary: dict[str, object]) -> dict[str, Any]:
    contract = _mapping(summary, "contract")
    client = contract.get("client", {})
    return client if isinstance(client, dict) else {}


def render_workspace_json_view(summary: dict[str, object]) -> dict[str, object]:
    """Return a deterministic, JSON-safe, redacted copy of workspace inspection output."""
    safe = _json_safe(copy.deepcopy(summary))
    return safe if isinstance(safe, dict) else {}


def render_dashboard_summary(summary: dict[str, object]) -> dict[str, object]:
    """Render counts and safety posture for dashboard clients without privileged access."""
    contract = _mapping(summary, "contract")
    runtime_status = _mapping(summary, "runtime_status")
    semantic_memory = _mapping(summary, "semantic_memory")
    capability_gates = _mapping(summary, "capability_gates")
    plugin_execution = capability_gates.get("plugin_execution", {})
    if not isinstance(plugin_execution, dict):
        plugin_execution = {}
    return render_workspace_json_view(
        {
            "service": contract.get("service", "workspace_inspection"),
            "read_only": contract.get("read_only", True),
            "shared_contract_path": contract.get("shared_contract_path", True),
            "client": _client(summary),
            "workspace_root": runtime_status.get("workspace_root"),
            "counts": {
                "sessions": runtime_status.get("session_count", 0),
                "events": len(_items(summary, "recent_events")),
                "checkpoints": len(_items(summary, "checkpoint_timeline")),
                "tasks": len(_items(summary, "tasks")),
                "pending_approvals": len(_items(summary, "approvals")),
                "plugin_registration_plans": len(_items(summary, "plugin_registration_plans")),
            },
            "safety": {
                "privileged": _client(summary).get("privileged", False),
                "semantic_writes_enabled": semantic_memory.get("semantic_writes_enabled", False),
                "plugin_execution_enabled": plugin_execution.get("runtime_enabled", False),
            },
        }
    )


def render_client_capability_summary(summary: dict[str, object]) -> dict[str, object]:
    """Render equal-interface client capability data from the shared inspection contract."""
    return render_workspace_json_view(
        {
            "client": _client(summary),
            "read_only": _mapping(summary, "contract").get("read_only", True),
            "capability_gates": _mapping(summary, "capability_gates"),
            "channel_connectors": _items(summary, "channel_connectors"),
            "execution_profiles": _items(summary, "execution_profiles"),
        }
    )


def render_plugin_plan_summary(summary: dict[str, object]) -> dict[str, object]:
    """Render inert plugin registration plans without importing or executing plugin code."""
    return render_workspace_json_view(
        {
            "read_only": _mapping(summary, "contract").get("read_only", True),
            "execution_enabled": False,
            "plans": _items(summary, "plugin_registration_plans"),
        }
    )


def render_workspace_text_view(summary: dict[str, object]) -> str:
    """Render a stable terminal summary from the shared inspection contract."""
    dashboard = render_dashboard_summary(summary)
    counts = dashboard.get("counts", {})
    safety = dashboard.get("safety", {})
    if not isinstance(counts, dict):
        counts = {}
    if not isinstance(safety, dict):
        safety = {}
    return "\n".join(
        [
            "Workspace view:",
            f"read_only: {dashboard.get('read_only', True)}",
            f"shared_contract_path: {dashboard.get('shared_contract_path', True)}",
            f"workspace_root: {dashboard.get('workspace_root')}",
            f"sessions: {counts.get('sessions', 0)}",
            f"events: {counts.get('events', 0)}",
            f"checkpoints: {counts.get('checkpoints', 0)}",
            f"tasks: {counts.get('tasks', 0)}",
            f"pending_approvals: {counts.get('pending_approvals', 0)}",
            f"plugin_registration_plans: {counts.get('plugin_registration_plans', 0)}",
            f"privileged: {safety.get('privileged', False)}",
            f"semantic_writes_enabled: {safety.get('semantic_writes_enabled', False)}",
            f"plugin_execution_enabled: {safety.get('plugin_execution_enabled', False)}",
        ]
    )
