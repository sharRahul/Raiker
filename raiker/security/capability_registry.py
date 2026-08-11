"""What each governed call belongs to, for the capability monitor (BUG-77).

The monitor in :mod:`raiker.security.containment` is deliberately generic: it
knows how to keep a baseline and raise a finding for *any*
``(principal, capability, subject)``. This module is the registration — the map
from a brokered tool call to the capability family and the specific subject that
call exercises, plus the redacted telemetry derived from its result.

Registering here rather than inside each executor is what makes the coverage
complete: every governed tool call in a turn passes one seam
(``RuntimeOrchestrator._aexecute_tool``), so a family added to this map is
monitored on every path — a fresh turn, a parallel read batch, and a call
drained from the approval queue — rather than only where somebody remembered to
add a hook.

The hard invariant is the MCP monitor's: only redacted metadata leaves here.
Hostnames are reduced to netloc, payloads to byte counts, and values to a
*classification label* produced transiently and discarded.
"""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

from raiker.security.containment import (
    CAPABILITY_CONNECTOR,
    CAPABILITY_EXECUTION,
    CAPABILITY_PLUGIN,
    CAPABILITY_SUBAGENT,
    CapabilityTelemetry,
    shape_sensitivity,
)

__all__ = [
    "UNTRUSTED_CONTENT_TOOLS",
    "classify_tool",
    "telemetry_for_call",
    "untrusted_content",
]

# Tools whose result is *outside content* — text the agent read on the owner's
# behalf rather than text the owner wrote. This is the set the prompt-injection
# scanner covers (BUG-81): a page, a message, a connector record, a subagent's
# digest, and anything an owner-registered MCP server returned.
UNTRUSTED_CONTENT_TOOLS = frozenset(
    {
        "web_fetch", "web_search", "github_read", "gmail_read", "gcal_read",
        "slack_read", "connector_read", "spawn_subagent",
    }
)

# Connector-family tools. A subject is the *connector*, not the tool: a Gmail
# read and a Gmail search share a baseline because they share a credential, an
# egress path and a blast radius.
_CONNECTOR_SUBJECTS: dict[str, str] = {
    "github_read": "github",
    "gmail_read": "gmail",
    "gcal_read": "google_calendar",
    "slack_read": "slack",
    "web_fetch": "web",
    "web_search": "web",
}

# Local-execution-family tools, keyed by the executor whose blast radius they
# share rather than by the individual call.
_EXECUTION_SUBJECTS: dict[str, str] = {
    "run_command": "shell",
    "apply_patch": "patch",
    "write_file": "file_write",
    "edit_file": "file_write",
}

_MCP_PREFIX = "mcp__"
_PLUGIN_PREFIX = "plugin__"

# Fields a tool result may carry that name a host. Only the netloc survives.
_HOST_FIELDS = ("final_url", "url", "endpoint", "html_url")

# Result fields whose *shape* is classified. The value is read transiently and
# discarded; only the label is ever returned.
_SHAPE_FIELDS = ("content", "text", "answer", "output", "body")

# A payload this large or larger is what "volume" means for a tool result. The
# serialized length is a byte count, never the bytes.
_MAX_MEASURE_CHARS = 2_000_000


def classify_tool(
    tool_name: str, arguments: dict[str, Any]
) -> tuple[str, str, str] | None:
    """``(capability, subject_id, label)`` for one call, or ``None`` if unmonitored.

    A tool with no capability family here is not an omission to be inferred: it
    is a local read whose blast radius is the workspace the policy engine already
    bounds, and giving it a baseline would produce noise, not signal.
    """
    if tool_name.startswith(_MCP_PREFIX):
        # Monitored MCP connections keep their own richer per-session monitor.
        return None
    if tool_name.startswith(_PLUGIN_PREFIX):
        plugin_id = tool_name[len(_PLUGIN_PREFIX) :].split("__", 1)[0]
        return CAPABILITY_PLUGIN, plugin_id or tool_name, plugin_id or tool_name
    if tool_name == "connector_read":
        connector = str(arguments.get("connector_id", "")).strip() or "connector"
        return CAPABILITY_CONNECTOR, connector, connector
    if tool_name in _CONNECTOR_SUBJECTS:
        subject = _CONNECTOR_SUBJECTS[tool_name]
        return CAPABILITY_CONNECTOR, subject, subject.replace("_", " ").title()
    if tool_name == "spawn_subagent":
        name = str(arguments.get("name", "")).strip() or "research"
        return CAPABILITY_SUBAGENT, name[:64], name[:64]
    if tool_name in _EXECUTION_SUBJECTS:
        subject = _EXECUTION_SUBJECTS[tool_name]
        return CAPABILITY_EXECUTION, subject, subject.replace("_", " ").title()
    return None


def telemetry_for_call(
    principal_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    status: str,
    output: dict[str, Any] | None,
    error: dict[str, Any] | None,
) -> CapabilityTelemetry | None:
    """Redacted telemetry for one brokered call, or ``None`` if unmonitored."""
    classified = classify_tool(tool_name, arguments)
    if classified is None:
        return None
    capability, subject_id, label = classified
    payload = output or {}
    ok = status == "success"
    return CapabilityTelemetry(
        principal_id=principal_id,
        capability=capability,
        subject_id=subject_id,
        label=label,
        operation=_operation(tool_name, arguments),
        hosts=_hosts(arguments, payload),
        tools=(_operation(tool_name, arguments),),
        calls=1,
        bytes_in=_measure(arguments),
        bytes_out=_measure(payload),
        error_count=0 if ok else 1,
        outcome="ok" if ok else "error",
        reason_code="" if ok else str((error or {}).get("type", "") or status),
        arg_sensitivity=_shape(arguments),
        result_sensitivity=_shape(payload),
    )


def untrusted_content(tool_name: str, output: dict[str, Any] | None) -> str | None:
    """The outside text one result carried, for scanning; ``None`` when there is none.

    Only tools in :data:`UNTRUSTED_CONTENT_TOOLS` and projected MCP tools qualify.
    A local read is the owner's own workspace: scanning it would attribute a
    finding to the owner's own file rather than to an outside source.
    """
    if not (tool_name in UNTRUSTED_CONTENT_TOOLS or tool_name.startswith(_MCP_PREFIX)):
        return None
    payload = output or {}
    parts = [
        value
        for field in _SHAPE_FIELDS
        if isinstance(value := payload.get(field), str) and value
    ]
    results = payload.get("results")
    if isinstance(results, list):
        parts.extend(
            str(item.get("text") or item.get("snippet") or item.get("title") or "")
            for item in results
            if isinstance(item, dict)
        )
    joined = "\n\n".join(part for part in parts if part)
    return joined or None


def _operation(tool_name: str, arguments: dict[str, Any]) -> str:
    """The operation a call names, for the tool-set-swap rule. Never a value."""
    operation = str(arguments.get("operation_id") or arguments.get("operation") or "")
    return f"{tool_name}:{operation}" if operation else tool_name


def _hosts(arguments: dict[str, Any], output: dict[str, Any]) -> tuple[str, ...]:
    """Netloc only, from either side of the call — never a path, query, or userinfo."""
    hosts: set[str] = set()
    for source in (arguments, output):
        for field in _HOST_FIELDS:
            value = source.get(field)
            if not isinstance(value, str) or not value.strip():
                continue
            parsed = urlsplit(value.strip())
            host = (parsed.hostname or "").casefold()
            if host:
                hosts.add(f"{host}:{parsed.port}" if parsed.port else host)
    return tuple(sorted(hosts))


def _measure(payload: dict[str, Any]) -> int:
    """The size of a payload, as a count. The payload itself is never kept."""
    try:
        return min(len(json.dumps(payload, default=str)), _MAX_MEASURE_CHARS)
    except (TypeError, ValueError):
        return 0


def _shape(payload: dict[str, Any]) -> str | None:
    """Classify the *shape* of a call's text and return only the label."""
    for field in _SHAPE_FIELDS:
        value = payload.get(field)
        if isinstance(value, str) and value:
            label = shape_sensitivity(value[:20_000])
            if label is not None:
                return label
    return None
