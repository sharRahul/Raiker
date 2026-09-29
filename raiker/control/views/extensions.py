"""MCP servers and sessions, hooks' handler summaries, connectors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from raiker.contracts.views import View


def _handler_target(handler: Any) -> str:
    """What a hook handler points at, in one line for the rule's card.

    An `http` handler's destination is the URL it posts to — the fact an owner
    needs when the grant does not cover it, because the host in that URL is what
    they have to add.
    """
    if handler.type == "command" and handler.command:
        return " ".join(handler.command)
    if handler.type == "builtin":
        return handler.builtin or ""
    if handler.type == "http":
        return handler.url or ""
    return handler.model or "owner-selected model"


def _declaration_summaries(stored: Any) -> tuple[dict[str, Any], ...]:
    """The owner-facing summary of what a server declared for each of its tools.

    Backlog #16 (MCP half). The card used to show a row of tool-name chips and
    nothing else, so a server whose tools had no declared arguments looked
    identical to one whose tools were fully described — and the owner could not
    tell whether the model was calling them with real arguments or guesses.

    Re-bounded on the way out (`decode_declarations`), so an older row written
    before those bounds existed is still safe to render, and the *argument
    names* are carried rather than the whole schema: the card answers "what does
    this tool take", not "paste me a JSON Schema".
    """
    from raiker.tools.mcp_schema import decode_declarations

    summaries: list[dict[str, Any]] = []
    for declaration in decode_declarations(stored):
        schema = declaration.input_schema or {}
        properties = schema.get("properties") if isinstance(schema, dict) else None
        argument_names = sorted(properties) if isinstance(properties, dict) else []
        required = schema.get("required") if isinstance(schema, dict) else None
        summaries.append(
            {
                "name": declaration.name,
                "title": declaration.title,
                "description": declaration.description,
                "has_schema": declaration.input_schema is not None,
                "schema_reason": declaration.schema_reason,
                "arguments": argument_names,
                "required": sorted(str(item) for item in required) if isinstance(required, list) else [],
            }
        )
    return tuple(summaries)


@dataclass(frozen=True)
class McpServerView(View):
    """Owner-scoped view of one local stdio MCP server profile (Control Deck
    task 4). ``command`` is the argv (interpreter + workspace-relative script);
    it is never a secret or a remote endpoint. Read-only — building or
    connecting a server is a governed runtime action, not a REST mutation."""

    server_id: str
    name: str
    command: tuple[str, ...]
    template: str | None
    transport: str
    status: str
    created_at: str
    last_connected_at: str | None = None
    # Tool names discovered by the last successful handshake (names only —
    # never arguments or output).
    tools: tuple[str, ...] = ()
    tool_count: int = 0
    # Backlog #16 (MCP half) — what each of those tools said it takes, bounded
    # by `raiker.tools.mcp_schema` before it was stored. One entry per tool that
    # declared something: its name, the server's own sentence, and whether the
    # declared argument schema is carried or why it is not. Still never
    # arguments a call passed or output it returned.
    tool_declarations: tuple[dict[str, Any], ...] = ()
    # BUG-234 — what this server offers that Raiker does not use, one sentence
    # each: capabilities it declared beyond `tools`, and what the transport was
    # observed doing. Empty when a server offers only what Raiker uses. The rule
    # is "supported, or named as unsupported" — never silently degraded.
    unsupported_features: tuple[dict[str, str], ...] = ()
    # Remote (http) connection details. `endpoint_url` is the owner-added URL;
    # `auth_ref` names where the owner token lives (an env var name) — never the
    # token itself. Both are null for a local stdio connection.
    endpoint_url: str | None = None
    auth_ref: str | None = None
    # Containment state (Phase C): `active` | `paused` | `killed`. `paused` is the
    # revocable circuit breaker (auto on a high-severity anomaly, or the owner's
    # one-call stop); `killed` is the instant kill switch. `paused_reason` /
    # `paused_at` are redacted metadata (a rule code + summary, a timestamp).
    monitor_state: str = "active"
    paused_reason: str | None = None
    paused_at: str | None = None
    # BUG-234 — the Model Context Protocol revision this server actually
    # negotiated, recorded by the last successful handshake. Null until one has
    # happened; nothing in the product said which revision Raiker speaks, which
    # made "why will this server not connect" unanswerable.
    protocol_version: str | None = None


@dataclass(frozen=True)
class McpSessionView(View):
    """Owner-scoped, redacted monitor row for one MCP connection session."""

    session_row_id: str
    server_id: str
    transport: str
    operation: str
    hosts: tuple[str, ...]
    tool_calls: int
    bytes_in: int
    bytes_out: int
    error_count: int
    outcome: str
    started_at: str
    ended_at: str | None


@dataclass(frozen=True)
class ConnectorView(View):
    """Read-only status of one governed service connector (web-app task 4).

    Every field is derived from stored/config state — this view never reaches
    the network and never exposes a credential value (only whether one is set).
    A connector is usable in chat only when its capability gate is enabled AND
    its decision mode is raised to ``allow`` AND the owner credential is set AND
    its host is on the connector egress allowlist; each condition is reported
    honestly so the owner can see exactly what is still fail-closed.
    """

    connector_id: str
    display_name: str
    capability: str
    gate_state: str
    capability_enabled: bool
    decision_mode: str
    # Owner credential presence only — the value (an API token) is never read out.
    credential_env: str
    credential_configured: bool
    egress_host: str
    egress_allowed: bool
    # Read-only summary of what actions this connector exposes and their kind.
    actions: tuple[str, ...]
    kind: str = "read_only"


@dataclass(frozen=True)
class ConnectionsView(View):
    connectors: tuple[ConnectorView, ...]
    # True when the owner has set RAIKER_CONNECTOR_EGRESS_ALLOWLIST at all.
    connector_egress_allowlist_configured: bool


def _env_requirements(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """The environment variables a channel transport declares, and whether each
    is set — never what it is set to."""
    import os as _os

    out: list[dict[str, Any]] = []
    for key, required in (("requires_env", True), ("optional_env", False)):
        for entry in raw.get(key) or []:
            if not isinstance(entry, dict) or not entry.get("name"):
                continue
            name = str(entry["name"])
            out.append(
                {
                    "name": name,
                    "description": str(entry.get("description") or ""),
                    "url": entry.get("url"),
                    "secret": bool(entry.get("secret")),
                    "required": required,
                    "present": bool(_os.environ.get(name, "").strip()),
                }
            )
    return out
