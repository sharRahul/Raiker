"""MCP-HOST — a server the owner registers runs as the owner, as in Claude Code and Codex.

Claude Code's sandbox "covers shell commands only"; its local MCP servers "run
with your full access", governed by permission rules on each tool. Codex governs
MCP tools by per-tool approval and allow/deny lists. Raiker now does the same:
an owner-registered stdio server starts with its own command outside the command
sandbox, so it can drive the applications it exists to drive; a server Raiker
generated from a template keeps the sandbox; a shell is never a server.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.runtime.executors import mcp as mcp_executor
from raiker.runtime.executors.mcp import McpConnectorExecutor, run_host_stdio

SERVER = """
import json, sys
for line in sys.stdin:
    msg = json.loads(line)
    if "id" not in msg:
        continue
    if msg["method"] == "initialize":
        result = {"protocolVersion": msg["params"]["protocolVersion"], "capabilities": {"tools": {}},
                  "serverInfo": {"name": "host-probe", "version": "1"}}
    elif msg["method"] == "tools/list":
        result = {"tools": [{"name": "where", "description": "Where am I running",
                             "inputSchema": {"type": "object", "properties": {}}}]}
    else:
        result = {}
    print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}), flush=True)
"""


@pytest.mark.parametrize(
    ("command", "refused"),
    [
        (["python", "server.py"], None),
        (["npx", "-y", "@playwright/mcp@latest"], None),
        ([r"C:\Program Files\Blender Foundation\blender-mcp.exe"], None),
        (["uvx", "blender-mcp"], None),
        (["cmd", "/c", "anything"], "mcp_command_is_a_shell"),
        (["powershell.exe", "-Command", "x"], "mcp_command_is_a_shell"),
        (["/bin/bash", "-c", "x"], "mcp_command_is_a_shell"),
        ([], "mcp_command_not_allowlisted"),
    ],
)
def test_an_owner_server_may_be_any_program_but_a_shell(command: list[str], refused: str | None) -> None:
    assert McpConnectorExecutor.validate_owner_command(command) == refused


def test_a_host_session_runs_the_program_as_the_owner(tmp_path: Path) -> None:
    script = tmp_path / "server.py"
    script.write_text(SERVER, encoding="utf-8")
    payload = (
        b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}\n'
        b'{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}\n'
    )
    session = run_host_stdio(
        [sys.executable, str(script)],
        payload,
        cwd=str(tmp_path),
        env=mcp_executor.mcp_stdio_env(),
        timeout=20,
    )
    assert b'"where"' in session.stdout
    assert not session.timed_out


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    ws = tmp_path / "ws"
    ws.mkdir()
    return TestClient(create_app(ws), client=("127.0.0.1", 50000))


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    body = client.post(
        "/api/auth/register", json={"username": "owner", "password": "correct horse battery staple 1"}
    ).json()
    return {"Authorization": f"Bearer {body['token']}", "X-CSRF-Token": body.get("csrf_token") or ""}


def test_the_owner_registers_a_local_server_by_its_command(
    client: TestClient, headers: dict[str, str]
) -> None:
    resp = client.post(
        "/api/mcp/servers/local",
        json={"name": "blender", "command": "uvx", "args": ["blender-mcp"], "env": {"BLENDER_PORT": "9876"}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["runs_as"] == "owner" and body["transport"] == "stdio"
    servers = client.get("/api/mcp/servers", headers=headers).json()
    rows = servers if isinstance(servers, list) else servers.get("servers", [])
    assert any(row["name"] == "blender" for row in rows)
    secrets = client.get(f"/api/mcp/servers/{body['server_id']}/secrets", headers=headers)
    assert secrets.status_code == 200, secrets.text
    assert "BLENDER_PORT" in secrets.text and "9876" not in secrets.text


def test_a_shell_is_refused_as_a_server(client: TestClient, headers: dict[str, str]) -> None:
    resp = client.post(
        "/api/mcp/servers/local", json={"name": "bad", "command": "bash", "args": ["-c", "id"]}, headers=headers
    )
    assert resp.status_code in {400, 403, 422}, resp.text
    assert "mcp_command_is_a_shell" in resp.text


def test_test_connect_runs_an_owner_server_without_the_command_sandbox(
    tmp_path: Path, client: TestClient, headers: dict[str, str]
) -> None:
    script = tmp_path / "server.py"
    script.write_text(SERVER, encoding="utf-8")
    ack = client.post(
        "/api/capability-gates/mcp_connector_runtime/threat-ack",
        json={"reason": "read the threat model"},
        headers=headers,
    )
    assert ack.status_code == 200, ack.text
    on = client.post(
        "/api/capability-gates/mcp_connector_runtime/set",
        json={"target_state": "enabled_runtime", "reason": "owner turned this on", "confirmation_token": "confirm"},
        headers=headers,
    )
    assert on.status_code == 200, on.text
    created = client.post(
        "/api/mcp/servers/local",
        json={"name": "probe", "command": sys.executable, "args": [str(script)]},
        headers=headers,
    ).json()
    connected = client.post(f"/api/mcp/servers/{created['server_id']}/connect", headers=headers)
    assert connected.status_code == 200, connected.text
    body = connected.json()
    assert "where" in body["tools"] or "where" in body.get("pending", [])


def test_an_owner_server_sees_who_the_user_is_but_no_provider_key() -> None:
    env = mcp_executor.mcp_host_env(
        {"PATH": "/usr/bin", "USERNAME": "owner", "DISPLAY": ":0", "ANTHROPIC_API_KEY": "secret"}
    )
    assert env["USERNAME"] == "owner" and env["DISPLAY"] == ":0"
    assert "ANTHROPIC_API_KEY" not in env
    # A sandboxed server's environment is unchanged.
    assert "USERNAME" not in mcp_executor.mcp_stdio_env({"USERNAME": "owner"})


def test_an_action_cannot_run_another_command_under_an_owner_servers_name(
    tmp_path: Path, client: TestClient, headers: dict[str, str]
) -> None:
    """Only the command the owner registered runs on the host (security review)."""
    from types import SimpleNamespace

    from raiker.storage.sqlite import SQLiteStore

    created = client.post(
        "/api/mcp/servers/local", json={"name": "trusted", "command": "uvx", "args": ["some-server"]}, headers=headers
    ).json()
    store = SQLiteStore(tmp_path / "ws")
    owner = str(store._rows("SELECT principal_id FROM mcp_servers LIMIT 1", ())[0]["principal_id"])  # noqa: SLF001
    executor = McpConnectorExecutor(tmp_path / "ws", store)
    action = SimpleNamespace(
        action_id="act_x",
        arguments={"server_id": created["server_id"], "command": [sys.executable, "-c", "print(1)"]},
    )
    ctx = mcp_executor._SessionCtx(  # noqa: SLF001
        operation="mcp_connect", tool_name="", tool_arguments={}, transport="stdio", started_at=""
    )
    result = executor._execute_stdio(action, owner, ctx, [], 5)  # type: ignore[arg-type]  # noqa: SLF001
    assert result.ok is False and result.reason_code == "mcp_command_mismatch"
    assert executor._owner_command(action, owner) == ["uvx", "some-server"]  # type: ignore[arg-type]  # noqa: SLF001


@pytest.mark.parametrize(("mode", "call_mode", "offered"), [
    ("ask", "ask", False),
    ("ask", "allow", True),
    ("deny", "allow", False),
    ("allow", "ask", True),
])
def test_a_server_the_owner_allows_is_offered_while_others_still_ask(
    tmp_path: Path, mode: str, call_mode: str, offered: bool
) -> None:
    """MCP-HOST — Codex's per-server approval mode, Claude Code's per-server allow rule."""
    from raiker.contracts.ids import new_id
    from raiker.storage.sqlite import SQLiteStore
    from raiker.tools.mcp_tools import mcp_tool_specs
    from tests.test_mcp_agent_tools import _CAP, _OWNER, _enable_gate, bootstrap_owner

    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    store = SQLiteStore(ws)
    ctrl = _enable_gate(ws, store)
    assert ctrl.set_capability_decision_mode(_CAP, mode, _OWNER, "test").ok
    for name, own_mode in (("trusted", call_mode), ("other", "ask")):
        server_id = new_id("mcp_")
        store.create_mcp_server(
            server_id=server_id, principal_id=_OWNER, name=name, command=["uvx", name],
            status="connected", last_connected_at="2026-11-25T00:00:00Z", tools=["look"],
            tool_schemas=[{"name": "look", "description": "Look", "inputSchema": {"type": "object"}}],
        )
        store.set_mcp_server_call_mode(server_id, _OWNER, own_mode)
    names = {spec.name for spec in mcp_tool_specs(ws, store, _OWNER)}
    assert ("mcp__trusted__look" in names) is offered
    assert ("mcp__other__look" in names) is (mode == "allow")
