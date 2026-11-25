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
