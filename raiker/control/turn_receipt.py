# SPDX-License-Identifier: Apache-2.0
"""QUI-F16 — a turn's receipt, from the records the runtime already wrote.

One line at the end of a task: which model answered and roughly what it cost,
what was read, what was changed or sent and when it was approved, and what
left this computer. Every field is read from the turn's own audit events; none
is assembled from what the model said it did. A call that did not succeed is
not on the receipt, because it did not happen.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from raiker.models.tool_registry import (
    READ_SHAPED_TOOL_NAMES,
    TOOL_FAMILY_BY_TOOL,
    TOOL_LABEL_BY_TOOL,
)

#: What a successful read is counted as, by tool family.
_READ_NOUNS: dict[str, str] = {
    "file-read": "file",
    "web": "web page",
    "connector": "message",
    "memory": "memory",
    "repository": "repository read",
}

#: Read-shaped tools that are bookkeeping rather than reading the owner's things.
#: `help_read` (TOOL-46) reads the help this install ships, not the owner's files.
_NOT_COUNTED: frozenset[str] = frozenset({"tool_search", "update_plan", "skill_load", "help_read"})

#: Families whose successful calls reach a service off this computer.
_SERVICE_BY_FAMILY: dict[str, str] = {"web": "the web"}

#: Tools whose successful calls reach a named service.
_SERVICE_BY_TOOL: dict[str, str] = {
    "gmail_read": "Gmail",
    "gcal_read": "Google Calendar",
    "slack_read": "Slack",
    "github_read": "GitHub",
    "github_write": "GitHub",
    "git_push": "the Git remote",
    "git_fetch": "the Git remote",
    "git_clone": "the Git remote",
    "cloud_execute": "the cloud runner",
    "remote_execute": "the remote runner",
}


def _payload(event: Mapping[str, Any]) -> Mapping[str, Any]:
    value = event.get("payload")
    return value if isinstance(value, Mapping) else {}


def build_turn_receipt(
    turn_id: str,
    events: Iterable[Mapping[str, Any]],
    *,
    local_providers: frozenset[str],
) -> dict[str, Any]:
    """Everything but the price, which needs the profile (see the caller)."""
    tool_by_action: dict[str, str] = {}
    connector_by_action: dict[str, str] = {}
    approved_at: dict[str, str] = {}
    completed: list[str] = []
    model: str | None = None
    provider: str | None = None
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0}

    for event in events:
        kind = str(event.get("event_type") or "")
        payload = _payload(event)
        if kind == "model_request_started":
            model = str(payload.get("model") or "") or model
            provider = str(payload.get("provider") or "") or provider
        elif kind == "model_request_completed":
            counts = payload.get("usage")
            if isinstance(counts, Mapping):
                for key in usage:
                    value = counts.get(key)
                    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                        usage[key] += value
        elif kind == "action_proposed":
            action = payload.get("action")
            if isinstance(action, Mapping):
                action_id = str(action.get("action_id") or "")
                tool_by_action[action_id] = str(action.get("tool_name") or "")
                arguments = action.get("arguments")
                if isinstance(arguments, Mapping) and arguments.get("connector"):
                    connector_by_action[action_id] = str(arguments.get("connector"))
        elif kind == "approval_received":
            action_id = str(payload.get("action_id") or "")
            if action_id:
                approved_at[action_id] = str(event.get("timestamp") or "")
        elif kind in ("tool_completed", "approval_executed"):
            output = payload.get("output")
            status = payload.get("status") or (output.get("status") if isinstance(output, Mapping) else None)
            action_id = str(payload.get("action_id") or "")
            if action_id and status in ("success", "executed", "completed") and action_id not in completed:
                completed.append(action_id)

    reads: dict[str, int] = {}
    changes: list[dict[str, Any]] = []
    services: list[str] = []
    for action_id in completed:
        tool = tool_by_action.get(action_id, "")
        if not tool or tool in _NOT_COUNTED:
            continue
        family = TOOL_FAMILY_BY_TOOL.get(tool, "")
        service = _SERVICE_BY_TOOL.get(tool) or _SERVICE_BY_FAMILY.get(family)
        if tool.startswith("connector_") and action_id in connector_by_action:
            service = connector_by_action[action_id].replace("_", " ").title()
        if service and service not in services:
            services.append(service)
        if tool in READ_SHAPED_TOOL_NAMES and family in _READ_NOUNS:
            noun = _READ_NOUNS[family]
            reads[noun] = reads.get(noun, 0) + 1
        elif tool not in READ_SHAPED_TOOL_NAMES:
            changes.append({
                "label": TOOL_LABEL_BY_TOOL.get(tool, tool.replace("_", " ")),
                "approved_at": approved_at.get(action_id),
            })

    local = provider in local_providers if provider else False
    return {
        "turn_id": turn_id,
        "model": model,
        "provider": provider,
        "local": local,
        "reads": reads,
        "changes": changes,
        "left_computer": services,
        "_usage": usage,
    }
