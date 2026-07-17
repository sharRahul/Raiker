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

import json
import os
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import new_id, utc_now
from raiker.runtime.executors.base import ExecutionResult
from raiker.runtime.executors.sandbox import SandboxError

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
        resolved = _safe_workspace_relative(self._ws, output_path)
        if resolved is None:
            return self._fail(action.action_id, "mcp_output_path_not_workspace_relative")

        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(_TEMPLATES[template], encoding="utf-8")
        except OSError as exc:
            return self._fail(action.action_id, f"mcp_write_failed:{type(exc).__name__}")

        rel_path = resolved.relative_to(self._ws).as_posix()
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


class McpConnectorExecutor:
    """Real executor for ``mcp_connector_runtime`` — a bounded local stdio call.

    Reached only through ``route_action`` (gate + decision mode + approval
    already applied). It validates the command against the interpreter
    allowlist and the workspace-relative argument rule, then runs a bounded
    JSON-RPC stdio session (initialize → tools/list or tools/call). Tool output
    is returned as redacted metadata only — the raw content never enters the
    artifacts (and therefore never the audit event).
    """

    capability = "mcp_connector_runtime"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._ws = Path(workspace_root).resolve()
        self._store = store

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        principal_id = principal.principal_id if principal is not None else action.principal_id
        command = [str(part) for part in action.arguments.get("command", [])]

        reason = self._validate_command(command)
        if reason is not None:
            return self._fail(action.action_id, reason)

        try:
            requested = float(action.arguments.get("timeout", MCP_SESSION_TIMEOUT))
        except (TypeError, ValueError):
            requested = MCP_SESSION_TIMEOUT
        timeout = min(max(requested, 1.0), _MAX_TIMEOUT)
        operation = action.action_type

        if operation == "mcp_call_tool":
            tool_name = str(action.arguments.get("tool_name", "")).strip()
            if not tool_name:
                return self._fail(action.action_id, "mcp_tool_name_required")
            tool_arguments = action.arguments.get("tool_arguments") or {}
            if not isinstance(tool_arguments, dict):
                return self._fail(action.action_id, "mcp_tool_arguments_invalid")
            return self._call_tool(action, principal_id, command, tool_name, tool_arguments, timeout)

        # mcp_connect and mcp_list_tools both initialize + enumerate tools.
        return self._connect_or_list(action, principal_id, command, timeout)

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

    # ── operations ──
    def _connect_or_list(
        self,
        action: GovernedAction,
        principal_id: str,
        command: list[str],
        timeout: float,
    ) -> ExecutionResult:
        requests = [
            _rpc(1, "initialize", {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "raiker", "version": "1.0.0"},
            }),
            _notification("notifications/initialized"),
            _rpc(2, "tools/list", {}),
        ]
        try:
            responses = self._run_session(command, requests, timeout)
        except SandboxError as exc:
            return self._fail(action.action_id, str(exc))

        init = responses.get(1)
        if init is None or "result" not in init:
            return self._fail(action.action_id, "mcp_initialize_failed")
        tools_resp = responses.get(2)
        if tools_resp is None or "result" not in tools_resp:
            return self._fail(action.action_id, "mcp_list_tools_failed")
        tools = tools_resp["result"].get("tools") or []
        tool_names = [str(t.get("name", "")) for t in tools if isinstance(t, dict)]
        server_info = init["result"].get("serverInfo") or {}

        self._record_connection(action, principal_id, command)
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary=f"MCP stdio session listed {len(tool_names)} tool(s); payloads withheld.",
            artifacts={
                "server_name": str(server_info.get("name", "")),
                "protocol_version": str(init["result"].get("protocolVersion", "")),
                "tool_count": len(tool_names),
                "tools": tool_names,
                "content_redacted": True,
            },
        )

    def _call_tool(
        self,
        action: GovernedAction,
        principal_id: str,
        command: list[str],
        tool_name: str,
        tool_arguments: dict[str, Any],
        timeout: float,
    ) -> ExecutionResult:
        requests = [
            _rpc(1, "initialize", {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "raiker", "version": "1.0.0"},
            }),
            _notification("notifications/initialized"),
            _rpc(3, "tools/call", {"name": tool_name, "arguments": tool_arguments}),
        ]
        try:
            responses = self._run_session(command, requests, timeout)
        except SandboxError as exc:
            return self._fail(action.action_id, str(exc))

        init = responses.get(1)
        if init is None or "result" not in init:
            return self._fail(action.action_id, "mcp_initialize_failed")
        call = responses.get(3)
        if call is None:
            return self._fail(action.action_id, "mcp_tool_call_no_response")
        if "error" in call:
            # Redact the server's message; keep only that it was a tool error.
            return self._fail(action.action_id, "mcp_tool_error")
        result = call.get("result") or {}
        if result.get("isError"):
            return self._fail(action.action_id, "mcp_tool_reported_error")
        content = result.get("content") or []
        content_length = sum(
            len(str(block.get("text", ""))) for block in content if isinstance(block, dict)
        )
        self._record_connection(action, principal_id, command)
        return ExecutionResult(
            ok=True,
            capability=self.capability,
            action_id=action.action_id,
            summary=f"MCP tool '{tool_name}' returned {content_length} char(s); content withheld.",
            artifacts={
                "tool_name": tool_name,
                "content_blocks": len(content),
                "content_length": content_length,
                "content_redacted": True,
            },
        )

    # ── stdio session ──
    def _run_session(
        self, command: list[str], requests: list[dict[str, Any]], timeout: float
    ) -> dict[Any, dict[str, Any]]:
        """Run a bounded, non-interactive JSON-RPC stdio session.

        All requests are written up front; stdin is then closed so the local
        server drains, responds, and exits. Responses are matched back by id.
        Raises :class:`SandboxError` with a redacted reason code on any failure.
        """
        payload = "".join(json.dumps(req) + "\n" for req in requests)
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
        return responses

    def _record_connection(
        self, action: GovernedAction, principal_id: str, command: list[str]
    ) -> None:
        """Persist/refresh an owner-scoped 'connected' profile for the command.

        Best-effort bookkeeping only — a storage hiccup must never turn a
        successful governed read into a failure, so this swallows write errors.
        """
        name = _normalize_server_name(str(action.arguments.get("name", ""))) or Path(
            command[-1]
        ).stem
        name = _normalize_server_name(name) or "mcp-server"
        try:
            existing = self._store.get_mcp_server_by_name(principal_id, name)
            server_id = str(existing["server_id"]) if existing else new_id("mcp_")
            template = existing.get("template") if existing else None
            self._store.create_mcp_server(
                server_id=server_id,
                principal_id=principal_id,
                name=name,
                command=command,
                template=template,
                transport="stdio",
                status="connected",
                last_connected_at=utc_now(),
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
