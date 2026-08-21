"""Governed local MCP builder + connector runtime (Control Deck plan Task 4).

Two real, bounded, fail-closed executors:

- :class:`McpBuilderExecutor` (``mcp_builder_runtime`` / ``mcp_server_create``)
  writes a reviewed, dependency-free local **stdio** MCP server template to a
  validated *workspace-relative* path and records an owner-scoped profile.
- :class:`McpConnectorExecutor` (``mcp_connector_runtime`` /
  ``mcp_connect`` / ``mcp_list_tools`` / ``mcp_call_tool``) speaks a bounded
  newline-delimited JSON-RPC stdio session with an owner-configured local
  server. The executable must be on a fixed allowlist and every argument must
  be workspace-relative; tool output is returned as **redacted metadata only**
  (length + redaction flag), never raw content.

Explicitly out of scope (fail closed): remote HTTP/SSE transport, OAuth
discovery, arbitrary shell commands, and execution of unreviewed tools. The
stdio session is implemented directly over the documented MCP JSON-RPC wire
format (no third-party SDK dependency), which keeps the runtime hermetic and
local-only. The generated server template speaks the same wire format, so the
builder + connector are testable end-to-end without any network.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from raiker.contracts.ids import new_id, utc_now
from raiker.runtime.executors.base import ExecutionResult
from raiker.runtime.executors.sandbox import SandboxError, post_json_rpc
from raiker.security.mcp_monitor import (
    McpSessionMonitor,
    McpSessionTelemetry,
    shape_sensitivity,
)
from raiker.storage.internal_paths import internal_io_path

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction
    from raiker.storage.sqlite import SQLiteStore

# Fixed, reviewed registry of interpreters a local stdio MCP server may run
# under. An owner may extend it (never replace it) via the env allowlist; a
# shell (`bash`/`sh`/`cmd.exe`) is never accepted. Matched on the executable's
# basename so an absolute interpreter path (``/usr/bin/python3``) still resolves.
_BUILTIN_MCP_COMMANDS: frozenset[str] = frozenset({"python", "python3", "node"})

MCP_SESSION_TIMEOUT = 20.0
_MAX_TIMEOUT = 60.0
MCP_MAX_OUTPUT_BYTES = 200_000
MCP_PROTOCOL_VERSION = "2024-11-05"

# Default relative directory for owner-built servers, under the workspace.
_MCP_SERVERS_DIR = ".raiker/mcp/servers"


def allowed_mcp_commands() -> frozenset[str]:
    """Fixed interpreter allowlist, optionally extended by the owner.

    ``RAIKER_MCP_COMMAND_ALLOWLIST`` is a comma-separated list of *additional*
    executable basenames. It can only widen the built-in set, never remove a
    built-in and never disable the shell exclusion (a shell is simply never a
    built-in, and the owner adding one is an explicit, auditable choice).
    """
    raw = os.environ.get("RAIKER_MCP_COMMAND_ALLOWLIST", "")
    extra = {part.strip() for part in raw.split(",") if part.strip()}
    return _BUILTIN_MCP_COMMANDS | extra


# ── Server templates ─────────────────────────────────────────────────────────
#
# A template is a self-contained, dependency-free Python stdio MCP server. It
# reads newline-delimited JSON-RPC from stdin and writes responses to stdout,
# implementing initialize / tools/list / tools/call for a small set of safe,
# side-effect-free tools. No network, no filesystem writes, no shell.

_ECHO_SERVER_TEMPLATE = '''\
#!/usr/bin/env python3
"""Raiker-generated local stdio MCP server (python-stdio-echo template).

A minimal, dependency-free MCP server that speaks newline-delimited JSON-RPC
over stdin/stdout. It exposes only safe, side-effect-free tools. Review and
extend this file before pointing anything sensitive at it.
"""
import json
import sys

PROTOCOL_VERSION = "2024-11-05"

TOOLS = [
    {
        "name": "echo",
        "description": "Echo back the provided text.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "workspace_ping",
        "description": "Return a fixed liveness token.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _send(message):
    sys.stdout.write(json.dumps(message) + "\\n")
    sys.stdout.flush()


def _result(request_id, result):
    _send({"jsonrpc": "2.0", "id": request_id, "result": result})


def _error(request_id, code, message):
    _send({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        method = msg.get("method")
        request_id = msg.get("id")
        if method == "initialize":
            _result(request_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "raiker-echo-mcp", "version": "1.0.0"},
            })
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            _result(request_id, {"tools": TOOLS})
        elif method == "tools/call":
            params = msg.get("params") or {}
            name = params.get("name")
            args = params.get("arguments") or {}
            if name == "echo":
                text = str(args.get("text", ""))
                _result(request_id, {"content": [{"type": "text", "text": text}], "isError": False})
            elif name == "workspace_ping":
                _result(request_id, {"content": [{"type": "text", "text": "pong"}], "isError": False})
            else:
                _error(request_id, -32602, "unknown tool")
        elif request_id is not None:
            _error(request_id, -32601, "method not found")


if __name__ == "__main__":
    main()
'''

_TEMPLATES: dict[str, str] = {
    "python-stdio-echo": _ECHO_SERVER_TEMPLATE,
}


def available_mcp_templates() -> tuple[str, ...]:
    return tuple(sorted(_TEMPLATES))


# ── Shared path validation ───────────────────────────────────────────────────


def _safe_workspace_relative(workspace_root: Path, candidate: str) -> Path | None:
    """Resolve ``candidate`` under ``workspace_root``.

    Returns the resolved absolute path only when it stays inside the workspace;
    returns None for an absolute path or any ``..`` escape.
    """
    raw = Path(candidate)
    if raw.is_absolute():
        return None
    resolved = (workspace_root / raw).resolve()
    root = workspace_root.resolve()
    if resolved != root and root not in resolved.parents:
        return None
    return resolved


def _normalize_server_name(name: str) -> str | None:
    normalized = re.sub(r"[^A-Za-z0-9._-]", "", name.strip())
    normalized = normalized.strip(".")
    if not normalized or len(normalized) > 64:
        return None
    return normalized


# ── Builder ──────────────────────────────────────────────────────────────────


class McpBuilderExecutor:
    """Real executor for ``mcp_builder_runtime`` — one governed template write.

    Reached only through ``route_action`` (capability gate + per-capability
    decision mode + approval already applied). It writes a reviewed local stdio
    MCP server template to a validated workspace-relative path and records an
    owner-scoped profile. Artifacts are metadata only — never the file contents.
    """

    capability = "mcp_builder_runtime"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._ws = Path(workspace_root).resolve()
        self._store = store

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        principal_id = principal.principal_id if principal is not None else action.principal_id
        args = action.arguments
        template = str(args.get("template", "")).strip()
        if template not in _TEMPLATES:
            return self._fail(action.action_id, f"mcp_unknown_template:{template or 'missing'}")

        name = _normalize_server_name(str(args.get("name", "")))
        if name is None:
            return self._fail(action.action_id, "mcp_invalid_server_name")

        output_path = str(args.get("output_path", "")).strip() or f"{_MCP_SERVERS_DIR}/{name}.py"
        ordinary_resolved = _safe_workspace_relative(self._ws, output_path)
        if ordinary_resolved is None:
            return self._fail(action.action_id, "mcp_output_path_not_workspace_relative")
        rel_path = ordinary_resolved.relative_to(self._ws).as_posix()
        resolved = (
            internal_io_path(ordinary_resolved)
            if rel_path == ".raiker" or rel_path.startswith(".raiker/")
            else ordinary_resolved
        )

        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(_TEMPLATES[template], encoding="utf-8")
        except OSError as exc:
            return self._fail(action.action_id, f"mcp_write_failed:{type(exc).__name__}")

        command = ["python", rel_path]
        existing = self._store.get_mcp_server_by_name(principal_id, name)
        server_id = str(existing["server_id"]) if existing else new_id("mcp_")
        self._store.create_mcp_server(
            server_id=server_id,
            principal_id=principal_id,
            name=name,
            command=command,
            template=template,
            transport="stdio",
            status="created",
        )
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary=f"Local MCP server template '{name}' created; contents withheld (metadata only).",
            artifacts={
                "server_id": server_id,
                "name": name,
                "template": template,
                "transport": "stdio",
                "path": rel_path,
                "bytes_written": resolved.stat().st_size,
                "content_redacted": True,
            },
        )

    def _fail(self, action_id: str, reason_code: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action_id,
            reason_code=reason_code,
            summary="MCP builder runtime failed closed.",
            artifacts={},
        )


# ── Connector ────────────────────────────────────────────────────────────────


HttpFn = Callable[..., dict[str, Any]]


@dataclass
class _SessionCtx:
    """Bundles the request context for one governed MCP session, so telemetry can
    be assembled without threading many parameters through the transport paths."""

    operation: str
    tool_name: str | None
    tool_arguments: dict[str, Any]
    transport: str
    command: list[str] = field(default_factory=list)
    endpoint_url: str | None = None
    started_at: str = ""


def _default_http_fn(
    url: str, payload: dict[str, Any], *, headers: dict[str, str], timeout: float, max_bytes: int
) -> dict[str, Any]:
    return post_json_rpc(url, payload, headers=headers, timeout=timeout, max_bytes=max_bytes)


class McpConnectorExecutor:
    """Real executor for ``mcp_connector_runtime`` — a bounded MCP session.

    Reached only through ``route_action`` (gate + decision mode + approval
    already applied). Two transports:

    - ``stdio`` (default): validates the command against the interpreter
      allowlist and the workspace-relative argument rule, then runs a bounded
      local JSON-RPC stdio session.
    - ``http``: connects to an owner-added remote MCP endpoint (URL + optional
      owner token) and runs a bounded JSON-RPC-over-HTTP session. The owner
      adding the URL is the authorization — the connection is *monitored*, not
      allowlist-blocked (see the Security Philosophy).

    Either way, tool output is returned as redacted metadata only — the raw
    content, and any owner token, never enter the artifacts or the audit event.
    """

    capability = "mcp_connector_runtime"

    def __init__(
        self,
        workspace_root: str | Path,
        store: SQLiteStore,
        *,
        http_fn: HttpFn | None = None,
        monitor: McpSessionMonitor | None = None,
        content_sink: Callable[[str], None] | None = None,
    ) -> None:
        self._ws = Path(workspace_root).resolve()
        self._store = store
        # Injectable so the remote path is testable without a live network.
        self._http_fn: HttpFn = http_fn or _default_http_fn
        # Every governed session hands redacted telemetry to the monitor, which
        # records a session-log row and raises redacted findings on anomalies.
        self._monitor = monitor or McpSessionMonitor(store)
        # BUG-12 — a tool result the *calling model* is meant to read goes to
        # this in-process sink and nowhere else. Artifacts, the audit event, and
        # the session log keep carrying metadata only, exactly as before: the
        # content never becomes a stored record. Unset (the default) preserves
        # the original behaviour, where the content is dropped entirely.
        self._content_sink = content_sink

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        principal_id = principal.principal_id if principal is not None else action.principal_id
        started_at = utc_now()
        # Containment gate: a paused/killed connection refuses the session before
        # it runs, with a clear, non-fabricated reason (missing-prerequisite
        # honesty, not an owner-facing ban — the owner can resume it any time).
        contained = self._containment_reason(action, principal_id)
        if contained is not None:
            return self._fail(action.action_id, contained)
        try:
            requested = float(action.arguments.get("timeout", MCP_SESSION_TIMEOUT))
        except (TypeError, ValueError):
            requested = MCP_SESSION_TIMEOUT
        timeout = min(max(requested, 1.0), _MAX_TIMEOUT)
        operation = action.action_type

        # Build the JSON-RPC request set for this operation.
        tool_name: str | None = None
        tool_arguments: dict[str, Any] = {}
        if operation == "mcp_call_tool":
            tool_name = str(action.arguments.get("tool_name", "")).strip()
            if not tool_name:
                return self._fail(action.action_id, "mcp_tool_name_required")
            raw_arguments = action.arguments.get("tool_arguments") or {}
            if not isinstance(raw_arguments, dict):
                return self._fail(action.action_id, "mcp_tool_arguments_invalid")
            tool_arguments = raw_arguments
            requests = [
                _initialize_rpc(),
                _notification("notifications/initialized"),
                _rpc(3, "tools/call", {"name": tool_name, "arguments": tool_arguments}),
            ]
        else:  # mcp_connect / mcp_list_tools both initialize + enumerate tools.
            requests = [
                _initialize_rpc(),
                _notification("notifications/initialized"),
                _rpc(2, "tools/list", {}),
            ]

        transport = str(action.arguments.get("transport", "stdio")).strip() or "stdio"
        ctx = _SessionCtx(
            operation=operation,
            tool_name=tool_name,
            tool_arguments=tool_arguments,
            transport=transport,
            started_at=started_at,
        )
        if transport == "http":
            return self._execute_http(action, principal_id, ctx, requests, timeout)
        return self._execute_stdio(action, principal_id, ctx, requests, timeout)

    # ── transport dispatch ──
    def _execute_stdio(
        self,
        action: GovernedAction,
        principal_id: str,
        ctx: _SessionCtx,
        requests: list[dict[str, Any]],
        timeout: float,
    ) -> ExecutionResult:
        command = [str(part) for part in action.arguments.get("command", [])]
        ctx.command = command
        reason = self._validate_command(command)
        if reason is not None:
            return self._fail(action.action_id, reason)
        try:
            responses, bytes_in, bytes_out = self._run_session(command, requests, timeout)
        except SandboxError as exc:
            self._observe_failure(action, principal_id, ctx)
            return self._fail(action.action_id, str(exc))
        return self._finish(action, principal_id, ctx, responses, bytes_in, bytes_out)

    def _execute_http(
        self,
        action: GovernedAction,
        principal_id: str,
        ctx: _SessionCtx,
        requests: list[dict[str, Any]],
        timeout: float,
    ) -> ExecutionResult:
        endpoint_url = str(action.arguments.get("endpoint_url", "")).strip()
        if urlparse(endpoint_url).scheme not in ("http", "https") or not urlparse(endpoint_url).netloc:
            return self._fail(action.action_id, "mcp_remote_invalid_endpoint")
        ctx.endpoint_url = endpoint_url
        token, token_error = self._resolve_remote_token(
            str(action.arguments.get("auth_ref", "")).strip() or None
        )
        if token_error is not None:
            return self._fail(action.action_id, token_error)
        try:
            responses, bytes_in, bytes_out = self._run_http_session(
                endpoint_url, token, requests, timeout
            )
        except SandboxError as exc:
            self._observe_failure(action, principal_id, ctx)
            return self._fail(action.action_id, str(exc))
        return self._finish(action, principal_id, ctx, responses, bytes_in, bytes_out)

    @staticmethod
    def _resolve_remote_token(auth_ref: str | None) -> tuple[str | None, str | None]:
        """Resolve the owner token for a remote endpoint from the env var named
        by ``auth_ref``. ``None`` auth_ref means an open server (no token). A
        named-but-absent env var fails closed (missing prerequisite)."""
        if not auth_ref:
            return None, None
        token = os.environ.get(auth_ref)
        if not token:
            return None, "mcp_remote_token_missing"
        return token, None

    # ── result interpretation (shared by both transports) ──
    def _finish(
        self,
        action: GovernedAction,
        principal_id: str,
        ctx: _SessionCtx,
        responses: dict[Any, dict[str, Any]],
        bytes_in: int,
        bytes_out: int,
    ) -> ExecutionResult:
        if ctx.operation == "mcp_call_tool":
            reason, blocks, length = _extract_call(responses)
            if reason is not None:
                # A session that reached the server but errored still counts
                # toward the error/refusal-burst rule.
                self._observe_failure(action, principal_id, ctx, bytes_in, bytes_out)
                return self._fail(action.action_id, reason)
            # Classify the argument/result *shape* transiently — only the label
            # crosses into the monitor; the raw value is dropped here.
            arg_label = shape_sensitivity(_safe_json(ctx.tool_arguments))
            text = _call_result_text(responses)
            result_label = shape_sensitivity(text)
            if self._content_sink is not None:
                self._content_sink(text)
            self._observe(
                self._build_telemetry(
                    action, principal_id, ctx, outcome="ok",
                    bytes_in=bytes_in, bytes_out=bytes_out,
                    arg_label=arg_label, result_label=result_label,
                )
            )
            self._record_connection(
                action, principal_id, transport=ctx.transport,
                command=ctx.command, endpoint_url=ctx.endpoint_url,
            )
            return ExecutionResult(
                ok=True,
                capability=self.capability,
                action_id=action.action_id,
                summary=f"MCP tool '{ctx.tool_name}' returned {length} char(s); content withheld.",
                artifacts={
                    "tool_name": ctx.tool_name,
                    "content_blocks": blocks,
                    "content_length": length,
                    "content_redacted": True,
                },
            )
        reason, tool_names, init_result = _extract_tools(responses)
        if reason is not None:
            self._observe_failure(action, principal_id, ctx, bytes_in, bytes_out)
            return self._fail(action.action_id, reason)
        server_info = init_result.get("serverInfo") or {}
        self._observe(
            self._build_telemetry(
                action, principal_id, ctx, outcome="ok",
                bytes_in=bytes_in, bytes_out=bytes_out, tools=tuple(tool_names),
            )
        )
        self._record_connection(
            action, principal_id, transport=ctx.transport,
            command=ctx.command, endpoint_url=ctx.endpoint_url, tools=tool_names,
        )
        label = "remote HTTP" if ctx.transport == "http" else "stdio"
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary=f"MCP {label} session listed {len(tool_names)} tool(s); payloads withheld.",
            artifacts={
                "server_name": str(server_info.get("name", "")),
                "protocol_version": str(init_result.get("protocolVersion", "")),
                "transport": ctx.transport,
                "tool_count": len(tool_names),
                "tools": tool_names,
                "content_redacted": True,
            },
        )

    # ── monitoring: hand redacted telemetry to the session monitor ──
    def _observe(self, telemetry: McpSessionTelemetry) -> None:
        """Best-effort: a monitoring hiccup must never turn a successful governed
        session into a failure, so storage/event errors are swallowed. A raised
        finding is still visible through the finding store + audit event."""
        try:
            self._monitor.observe(telemetry)
        except Exception:  # noqa: BLE001 - monitoring must not fail the session
            return

    def _observe_failure(
        self,
        action: GovernedAction,
        principal_id: str,
        ctx: _SessionCtx,
        bytes_in: int = 0,
        bytes_out: int = 0,
    ) -> None:
        self._observe(
            self._build_telemetry(
                action, principal_id, ctx, outcome="error",
                bytes_in=bytes_in, bytes_out=bytes_out, error_count=1,
            )
        )

    def _build_telemetry(
        self,
        action: GovernedAction,
        principal_id: str,
        ctx: _SessionCtx,
        *,
        outcome: str,
        bytes_in: int,
        bytes_out: int,
        tools: tuple[str, ...] = (),
        arg_label: str | None = None,
        result_label: str | None = None,
        error_count: int = 0,
    ) -> McpSessionTelemetry:
        hosts: tuple[str, ...] = ()
        if ctx.transport == "http" and ctx.endpoint_url:
            # Redacted: the host (netloc) only — never the path, query, or token.
            netloc = urlparse(ctx.endpoint_url).netloc
            if netloc:
                hosts = (netloc,)
        return McpSessionTelemetry(
            principal_id=principal_id,
            server_id=self._resolve_server_id(action, principal_id, ctx.command),
            transport=ctx.transport,
            operation=ctx.operation,
            hosts=hosts,
            tool_calls=1 if ctx.operation == "mcp_call_tool" else 0,
            tools=tools,
            bytes_in=bytes_in,
            bytes_out=bytes_out,
            error_count=error_count,
            outcome=outcome,
            arg_sensitivity=arg_label,
            result_sensitivity=result_label,
            started_at=ctx.started_at,
            ended_at=utc_now(),
        )

    def _containment_reason(self, action: GovernedAction, principal_id: str) -> str | None:
        """Resolve the connection this session belongs to and refuse it if the
        owner (or the auto-pause circuit breaker) has contained it. Returns a
        redacted reason code (``mcp_connection_paused`` / ``mcp_connection_killed``)
        or ``None`` when the connection is active or unknown (an ad-hoc session
        with no stored profile has nothing to contain)."""
        command = [str(part) for part in action.arguments.get("command", [])]
        server_id = self._resolve_server_id(action, principal_id, command)
        if not server_id:
            return None
        server = self._store.get_mcp_server(server_id, principal_id)
        if server is None:
            return None
        state = str(server.get("monitor_state") or "active")
        if state == "killed":
            return "mcp_connection_killed"
        if state == "paused":
            return "mcp_connection_paused"
        return None

    def _resolve_server_id(
        self, action: GovernedAction, principal_id: str, command: list[str]
    ) -> str | None:
        """Resolve the owner-scoped server_id this session belongs to, the same
        way ``_record_connection`` does (server_id arg → name → command stem), so
        the session log and any finding attach to the right connection."""
        server_id_arg = str(action.arguments.get("server_id", "")).strip()
        if server_id_arg and self._store.get_mcp_server(server_id_arg, principal_id) is not None:
            return server_id_arg
        name = _normalize_server_name(str(action.arguments.get("name", "")))
        if name:
            row = self._store.get_mcp_server_by_name(principal_id, name)
            if row is not None:
                return str(row["server_id"])
        if command:
            fallback = _normalize_server_name(Path(command[-1]).stem)
            if fallback:
                row = self._store.get_mcp_server_by_name(principal_id, fallback)
                if row is not None:
                    return str(row["server_id"])
        return None

    # ── validation ──
    def _validate_command(self, command: list[str]) -> str | None:
        if not command or Path(command[0]).name not in allowed_mcp_commands():
            return "mcp_command_not_allowlisted"
        for part in command[1:]:
            # Reject absolute paths and any parent-directory escape so a server
            # argument can only reference something inside the workspace.
            if Path(part).is_absolute() or _safe_workspace_relative(self._ws, part) is None:
                return "mcp_argument_path_not_workspace_relative"
        return None

    # ── remote HTTP session ──
    def _run_http_session(
        self, endpoint_url: str, token: str | None, requests: list[dict[str, Any]], timeout: float
    ) -> tuple[dict[Any, dict[str, Any]], int, int]:
        """Run a bounded JSON-RPC-over-HTTP session against an owner-added MCP
        endpoint. The owner token (if any) is sent as a bearer header and never
        stored or returned. An ``Mcp-Session-Id`` from the initialize response
        is carried to later requests. Raises :class:`SandboxError` with a
        redacted reason on any transport failure. Returns the id-keyed responses
        plus the wire byte totals (in/out) for monitoring — sizes only, never
        content."""
        responses: dict[Any, dict[str, Any]] = {}
        session_id: str | None = None
        bytes_in = 0
        bytes_out = 0
        for req in requests:
            bytes_out += len(json.dumps(req).encode("utf-8"))
            headers: dict[str, str] = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            if session_id:
                headers["Mcp-Session-Id"] = session_id
            result = self._http_fn(
                endpoint_url, req, headers=headers, timeout=timeout, max_bytes=MCP_MAX_OUTPUT_BYTES,
            )
            if result.get("truncated"):
                raise SandboxError("mcp_response_too_large")
            body_text = str(result.get("body_text", ""))
            bytes_in += len(body_text.encode("utf-8"))
            sid = result.get("headers", {}).get("mcp-session-id")
            if sid:
                session_id = str(sid)
            for message in _parse_jsonrpc_body(body_text):
                if isinstance(message, dict) and "id" in message:
                    responses[message["id"]] = message
        return responses, bytes_in, bytes_out

    # ── stdio session ──
    def _run_session(
        self, command: list[str], requests: list[dict[str, Any]], timeout: float
    ) -> tuple[dict[Any, dict[str, Any]], int, int]:
        """Run a bounded, non-interactive JSON-RPC stdio session.

        All requests are written up front; stdin is then closed so the local
        server drains, responds, and exits. Responses are matched back by id.
        Raises :class:`SandboxError` with a redacted reason code on any failure.
        Returns the id-keyed responses plus the wire byte totals (in/out) for
        monitoring — sizes only, never content.
        """
        payload = "".join(json.dumps(req) + "\n" for req in requests)
        bytes_out = len(payload.encode("utf-8"))
        try:
            proc = subprocess.Popen(  # noqa: S603 - argv is allowlist-validated, no shell
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self._ws),
                text=True,
            )
        except FileNotFoundError:
            raise SandboxError("mcp_command_not_found") from None
        except OSError:
            raise SandboxError("mcp_spawn_failed") from None
        try:
            stdout, _stderr = proc.communicate(input=payload, timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise SandboxError("mcp_session_timeout") from None

        if len(stdout) > MCP_MAX_OUTPUT_BYTES:
            raise SandboxError("mcp_response_too_large")
        bytes_in = len(stdout.encode("utf-8"))

        responses: dict[Any, dict[str, Any]] = {}
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if isinstance(message, dict) and "id" in message:
                responses[message["id"]] = message
        return responses, bytes_in, bytes_out

    def _record_connection(
        self,
        action: GovernedAction,
        principal_id: str,
        *,
        transport: str,
        command: list[str],
        endpoint_url: str | None,
        tools: list[str] | None = None,
    ) -> None:
        """Persist/refresh an owner-scoped 'connected' profile, including the tool
        names the handshake discovered (names only).

        Best-effort bookkeeping only — a storage hiccup must never turn a
        successful governed read into a failure, so this swallows write errors.
        An existing profile (addressed by ``server_id`` or name) has only its
        *runtime* fields refreshed, so a re-test never wipes a stored endpoint or
        auth reference. A missing profile (the stdio ad-hoc direct-executor path)
        is created.
        """
        server_id_arg = str(action.arguments.get("server_id", "")).strip()
        existing = (
            self._store.get_mcp_server(server_id_arg, principal_id) if server_id_arg else None
        )
        name = _normalize_server_name(str(action.arguments.get("name", "")))
        if existing is None and name is not None:
            existing = self._store.get_mcp_server_by_name(principal_id, name)
        try:
            if existing is not None:
                self._store.update_mcp_server_runtime(
                    str(existing["server_id"]), principal_id,
                    # `tools=None` (a tools/call session) leaves the stored list
                    # alone; only an enumerating session rewrites it.
                    status="connected", tools=tools, last_connected_at=utc_now(),
                )
                return
            fallback = (
                name
                or (_normalize_server_name(Path(command[-1]).stem) if command else None)
                or "mcp-server"
            )
            self._store.create_mcp_server(
                server_id=new_id("mcp_"),
                principal_id=principal_id,
                name=fallback,
                command=command,
                template=None,
                transport=transport,
                status="connected",
                last_connected_at=utc_now(),
                tools=tools or [],
                endpoint_url=endpoint_url,
            )
        except Exception:  # noqa: BLE001 - bookkeeping must not fail the read
            return

    def _fail(self, action_id: str, reason_code: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False,
            capability=self.capability,
            action_id=action_id,
            reason_code=reason_code,
            summary="MCP connector runtime failed closed.",
            artifacts={},
        )


def _rpc(request_id: int, method: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}


def _notification(method: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "method": method}


def _initialize_rpc() -> dict[str, Any]:
    return _rpc(1, "initialize", {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "raiker", "version": "1.0.0"},
    })


def _extract_tools(
    responses: dict[Any, dict[str, Any]],
) -> tuple[str | None, list[str], dict[str, Any]]:
    """Interpret an initialize + tools/list exchange. Returns
    (error_reason_or_None, tool_names, initialize_result)."""
    init = responses.get(1)
    if init is None or "result" not in init:
        return "mcp_initialize_failed", [], {}
    tools_resp = responses.get(2)
    if tools_resp is None or "result" not in tools_resp:
        return "mcp_list_tools_failed", [], {}
    tools = tools_resp["result"].get("tools") or []
    names = [str(t.get("name", "")) for t in tools if isinstance(t, dict)]
    return None, names, init["result"]


def _extract_call(responses: dict[Any, dict[str, Any]]) -> tuple[str | None, int, int]:
    """Interpret an initialize + tools/call exchange. Returns
    (error_reason_or_None, content_block_count, content_length). The tool's raw
    content never leaves this function — only its size."""
    init = responses.get(1)
    if init is None or "result" not in init:
        return "mcp_initialize_failed", 0, 0
    call = responses.get(3)
    if call is None:
        return "mcp_tool_call_no_response", 0, 0
    if "error" in call:
        return "mcp_tool_error", 0, 0
    result = call.get("result") or {}
    if result.get("isError"):
        return "mcp_tool_reported_error", 0, 0
    content = result.get("content") or []
    length = sum(len(str(b.get("text", ""))) for b in content if isinstance(b, dict))
    return None, len(content), length


def _safe_json(value: Any) -> str:
    """Serialise a value to text for *transient* shape classification only. The
    result is fed to the sensitivity classifier and then discarded — it is never
    stored, returned, or logged."""
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return str(value)


def _call_result_text(responses: dict[Any, dict[str, Any]]) -> str:
    """Concatenate a tools/call result's text blocks.

    Used for transient shape classification, and — when the caller supplied a
    ``content_sink`` — handed to that caller so a model can read what the tool
    it called returned (BUG-12). It is never stored: artifacts, the audit event,
    and the session log keep carrying counts and labels only.
    """
    call = responses.get(3)
    if not isinstance(call, dict):
        return ""
    result = call.get("result") or {}
    content = result.get("content") or []
    return "".join(str(b.get("text", "")) for b in content if isinstance(b, dict))


def _parse_jsonrpc_body(body: str) -> list[dict[str, Any]]:
    """Parse a JSON-RPC HTTP response body into messages, tolerating a single
    object, a JSON array, SSE ``data:`` framing, or newline-delimited JSON."""
    body = body.strip()
    if not body:
        return []
    stripped = body.lstrip()
    if stripped.startswith(("event:", "data:", ":")):
        out: list[dict[str, Any]] = []
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                with contextlib.suppress(ValueError):
                    out.append(json.loads(line[5:].strip()))
        return out
    try:
        parsed = json.loads(body)
    except ValueError:
        parsed = None
    if isinstance(parsed, dict):
        return [parsed]
    if isinstance(parsed, list):
        return [m for m in parsed if isinstance(m, dict)]
    out = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        with contextlib.suppress(ValueError):
            out.append(json.loads(line))
    return out
