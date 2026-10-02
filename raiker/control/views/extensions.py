"""MCP servers and sessions, hooks' handler summaries, connectors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, NotRequired

from typing_extensions import TypedDict

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


class McpToolDeclaration(TypedDict):
    """What one MCP tool said it takes — the argument names, never a schema dump."""

    name: str
    title: str
    description: str
    has_schema: bool
    schema_reason: str
    arguments: list[str]
    required: list[str]


class UnsupportedFeature(TypedDict):
    """Something a server offers that Raiker does not use, in one sentence."""

    feature: str
    note: str


def _declaration_summaries(stored: Any) -> tuple[McpToolDeclaration, ...]:
    """The owner-facing summary of what a server declared for each of its tools.

    Backlog #16 (MCP half). A server whose tools declare no arguments must not
    look identical to one whose tools are fully described, so the owner can
    tell whether the model calls them with real arguments or guesses.

    Re-bounded on the way out (`decode_declarations`), so an older row written
    before those bounds existed is still safe to render, and the *argument
    names* are carried rather than the whole schema: the card answers "what does
    this tool take", not "paste me a JSON Schema".
    """
    from raiker.tools.mcp_schema import decode_declarations

    summaries: list[McpToolDeclaration] = []
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
    tool_declarations: tuple[McpToolDeclaration, ...] = ()
    # BUG-234 — what this server offers that Raiker does not use, one sentence
    # each: capabilities it declared beyond `tools`, and what the transport was
    # observed doing. Empty when a server offers only what Raiker uses. The rule
    # is "supported, or named as unsupported" — never silently degraded.
    unsupported_features: tuple[UnsupportedFeature, ...] = ()
    # Remote (http) connection details. `endpoint_url` is the owner-added URL;
    # `auth_ref` names where the owner token lives (an env var name) — never the
    # token itself. Both are null for a local stdio connection.
    endpoint_url: str | None = None
    auth_ref: str | None = None
    # Containment state (Phase C): `active` | `paused` | `killed`. `paused` is the
    # revocable circuit breaker (auto on a high-severity anomaly, or the owner's
    # one-call stop); `killed` is the instant kill switch. `paused_reason` /
    # `paused_at` are redacted metadata (a rule code + summary, a timestamp).
    monitor_state: Literal["active", "paused", "killed"] = "active"
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


class ChannelEnvRequirement(TypedDict):
    """One environment variable a channel transport declares that it needs."""

    name: str
    description: str
    url: str | None
    secret: bool
    required: bool
    #: Whether it is set. Never what it is set to.
    present: bool


def _env_requirements(raw: dict[str, Any]) -> list[ChannelEnvRequirement]:
    """The environment variables a channel transport declares, and whether each
    is set — never what it is set to."""
    import os as _os

    out: list[ChannelEnvRequirement] = []
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


class McpOffer(TypedDict):
    """An MCP server an installed plugin offers. Inert until the owner adds it (BUG-221)."""

    plugin_id: str
    name: str
    transport: Literal["http", "stdio"]
    description: str
    endpoint_url: NotRequired[str]
    auth_ref: NotRequired[str | None]
    template: NotRequired[str]
    already_added: bool


class HookHandlerView(TypedDict):
    id: str
    type: str
    #: The argv or builtin name, already joined for display.
    target: str
    timeout_ms: int
    decision_authority: bool
    #: False for a builtin this build does not ship, or an ``http`` destination
    #: the owner's egress grant does not cover: the rule matches, nothing runs.
    available: bool
    #: ``egress_not_granted`` or ``builtin_not_in_this_build``; empty when available.
    unavailable_reason: str


class HookRuleView(TypedDict):
    rule_id: str
    event: str
    event_summary: str
    matcher: str
    if_guard: str | None
    scope: str
    source: str | None
    #: False when this build never emits the event, so the rule cannot fire.
    dispatched: bool
    #: True only when the runtime honours the event's decision and a handler holds authority.
    can_decide: bool
    handlers: list[HookHandlerView]


class HookEventView(TypedDict):
    event: str
    summary: str
    dispatched: bool
    can_decide: bool


class HookActivityView(TypedDict):
    event_id: str
    event_type: str
    session_id: str
    timestamp: str
    summary: str | None


class HookSourceView(TypedDict):
    path: str
    scope: str
    exists: bool
    loaded: bool
    rule_count: int
    #: Why the file contributed nothing. Null when it loaded or is absent.
    error: str | None


class HooksView(TypedDict):
    """Configured hooks, whether each can fire or decide, and what they have done."""

    #: False when nothing is configured or the owner turned hooks off.
    active: bool
    disabled: bool
    rule_count: int
    rules: list[HookRuleView]
    sources: list[HookSourceView]
    failed_sources: list[HookSourceView]
    events: list[HookEventView]
    builtins: list[str]
    activity: list[HookActivityView]
    activity_counts: dict[str, int]


class PluginSignatureView(TypedDict):
    """What a plugin manifest's signature actually proved (BUG-79)."""

    level: Literal["verified", "present_only", "unsigned"]
    label: str
    reason: str
    method: str
    verified: bool
    explanation: str
    remediation: str


class PluginContributions(TypedDict):
    """What a plugin provides, read from the files the runtime loads (BUG-221)."""

    hooks: int
    events: list[str]
    skills: int
    skill_names: list[str]
    mcp_servers: int
    mcp_server_names: list[str]
    #: ``unreadable`` when a contributed file exists and could not be parsed.
    error: str | None


class PluginCodeRuntime(TypedDict):
    """BUG-308 — where this plugin's own code would run on this machine."""

    where: Literal["not_enabled", "isolated", "host_network"]
    summary: str


class InstalledPlugin(TypedDict):
    record_id: str
    plugin_id: str
    version: str
    trust_level: str
    status: str
    source_url: str | None
    installed_at: str
    installed_by: str
    checksum_present: bool
    code_runtime: PluginCodeRuntime
    signature: PluginSignatureView
    contributions: PluginContributions


class PluginSigning(TypedDict):
    configured: bool
    hmac_key_set: bool
    publisher_key_set: bool
    summary: str
    remediation: str


class PluginContributionKind(TypedDict):
    """A kind of contribution, and whether this build accepts it yet."""

    kind: str
    available: bool
    summary: str


class PluginsView(TypedDict):
    plugins: list[InstalledPlugin]
    signing: PluginSigning
    contribution_kinds: list[PluginContributionKind]


ChannelRoutingMode = Literal["record_only", "new_turn", "side_question", "interrupt"]


class ChannelProfile(TypedDict):
    """One connector profile, and each separate fact about it (BUG-225)."""

    connector_id: str
    channel_type: str
    display_name: str
    transport: str
    auth_method: str
    default_state: str
    requires_pairing: bool
    requires_sender_allowlist: bool
    requires_network: bool
    #: Is there a pairing at all.
    linked: bool
    #: Is that pairing switched on. Linked is not enabled.
    enabled: bool
    pairing_id: str | None
    display_label: str | None
    sender_count: int
    #: The owner's own allowlist, returned to the owner so routing can name one.
    senders: list[str]
    routing_mode: ChannelRoutingMode
    target_session_id: str | None
    owner_sender_id: str | None
    approval_relay_enabled: bool
    supports_side_questions: bool
    supports_interrupts: bool
    supports_approvals: bool
    env_requirements: list[ChannelEnvRequirement]


class ChannelsOutbound(TypedDict):
    """Empty when the connector registry could not be read."""

    capability: NotRequired[str]
    gate_state: NotRequired[str]
    runtime_enabled: NotRequired[bool]
    #: RAIKER_CHANNEL_EGRESS_ALLOWLIST names at least one host. Fail-closed.
    egress_configured: NotRequired[bool]
    egress_host_count: NotRequired[int]
    #: RAIKER_CHANNEL_OUTBOUND_SECRET is set, so deliveries carry an HMAC.
    signing_configured: NotRequired[bool]


class ChannelsInbound(TypedDict):
    """Empty when the connector registry could not be read."""

    #: RAIKER_CHANNEL_INBOUND_SECRET is set. Without it the receiver refuses.
    secret_configured: NotRequired[bool]
    #: Messages per sender per minute.
    rate_limit_per_minute: NotRequired[int]
    quarantined: NotRequired[bool]
    instructions_inert: NotRequired[bool]


class ChannelsView(TypedDict):
    profiles: list[ChannelProfile]
    error: str | None
    outbound: ChannelsOutbound
    inbound: ChannelsInbound
