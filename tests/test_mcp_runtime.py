"""Governed local MCP builder + connector runtime (Control Deck plan Task 4).

These tests cover the fail-closed contract for the two new capabilities:

- ``mcp_builder_runtime`` (``mcp_server_create``) writes a reviewed, minimal
  local stdio MCP server template to a validated *workspace-relative* path and
  records an owner-scoped server profile. It never writes outside the workspace
  and never emits file contents in its artifacts.
- ``mcp_connector_runtime`` (``mcp_connect`` / ``mcp_list_tools`` /
  ``mcp_call_tool``) speaks a bounded newline-delimited JSON-RPC stdio session
  with an owner-configured local server whose executable is on a fixed
  allowlist and whose arguments are workspace-relative. Tool output is returned
  as redacted metadata only (length + redaction flag), never raw content.

Remote HTTP transport, OAuth discovery, arbitrary shell commands, and execution
of unreviewed MCP tools are explicitly out of scope and stay fail-closed.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority import GovernedAction, RuntimeAuthority
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors import (
    REAL_EXECUTOR_CAPABILITIES,
    build_default_executor_registry,
)
from raiker.runtime.executors.mcp import (
    McpBuilderExecutor,
    McpConnectorExecutor,
    allowed_mcp_commands,
    available_mcp_templates,
)
from raiker.storage.sqlite import SQLiteStore


def _ws(tmp_path: Path) -> Path:
    ws = tmp_path / "mcp_ws"
    ws.mkdir()
    return ws


def _principal(pid: str = "principal_owner") -> Any:
    # A minimal stand-in; executors only read ``principal_id``. Typed ``Any`` so
    # the direct-execute tests don't need to build a full Principal.
    return SimpleNamespace(principal_id=pid)


def _action(action_type: str, arguments: dict, *, principal_id: str = "principal_owner") -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=principal_id,
        action_type=action_type,
        tool_or_service_name=action_type,
        arguments=arguments,
        risk_level=RiskLevelValue.MEDIUM,
    )


# ── Capability registration / default posture ────────────────────────────────


def test_mcp_capabilities_are_real_and_registered(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    registry = build_default_executor_registry(ws, store)
    for cap in ("mcp_builder_runtime", "mcp_connector_runtime"):
        assert cap in REAL_EXECUTOR_CAPABILITIES, cap
        assert registry.has(cap), cap


def test_mcp_caps_ship_enabled_runtime_by_default() -> None:
    from raiker.phase_gates import ALL_CAPABILITIES, CapabilityState, default_capability_gates

    gates = default_capability_gates()
    for cap in ("mcp_builder_runtime", "mcp_connector_runtime"):
        assert cap in ALL_CAPABILITIES, cap
        assert gates[cap].state == CapabilityState.ENABLED_RUNTIME, cap


def test_mcp_action_types_map_to_capabilities() -> None:
    from raiker.runtime.authority.router import CAPABILITY_GATE_MAP

    assert CAPABILITY_GATE_MAP["mcp_server_create"] == "mcp_builder_runtime"
    for action_type in ("mcp_connect", "mcp_list_tools", "mcp_call_tool"):
        assert CAPABILITY_GATE_MAP[action_type] == "mcp_connector_runtime"


# ── Connector command validation (fail closed) ───────────────────────────────


def test_connect_denies_unallowlisted_command(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    executor = McpConnectorExecutor(ws, store)
    result = executor.execute(
        _action("mcp_connect", {"command": ["cmd.exe", "/c", "whoami"]}), _principal()
    )
    assert result.ok is False
    assert result.reason_code == "mcp_command_not_allowlisted"


def test_connect_denies_empty_command(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    executor = McpConnectorExecutor(ws, store)
    result = executor.execute(_action("mcp_connect", {"command": []}), _principal())
    assert result.ok is False
    assert result.reason_code == "mcp_command_not_allowlisted"


def test_connect_denies_absolute_path_argument(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    executor = McpConnectorExecutor(ws, store)
    result = executor.execute(
        _action("mcp_connect", {"command": ["python", "/etc/passwd"]}), _principal()
    )
    assert result.ok is False
    assert result.reason_code == "mcp_argument_path_not_workspace_relative"


def test_connect_denies_parent_escape_argument(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    executor = McpConnectorExecutor(ws, store)
    result = executor.execute(
        _action("mcp_connect", {"command": ["python", "../evil.py"]}), _principal()
    )
    assert result.ok is False
    assert result.reason_code == "mcp_argument_path_not_workspace_relative"


def test_allowed_commands_exclude_shells() -> None:
    allowed = allowed_mcp_commands()
    assert "python" in allowed
    assert "cmd.exe" not in allowed
    assert "bash" not in allowed
    assert "sh" not in allowed


# ── Builder template creation (workspace-relative, redacted) ─────────────────


def test_builder_creates_server_template_owner_scoped(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    executor = McpBuilderExecutor(ws, store)
    result = executor.execute(
        _action("mcp_server_create", {"name": "echo", "template": "python-stdio-echo"}),
        _principal(),
    )
    assert result.ok is True, result.reason_code
    rel_path = result.artifacts["path"]
    assert not Path(rel_path).is_absolute()
    assert (ws / rel_path).exists()
    # Redacted metadata only — never the generated file's contents.
    blob = json.dumps(result.artifacts)
    assert "def " not in blob and "import" not in blob
    servers = store.list_mcp_servers("principal_owner")
    assert any(s["name"] == "echo" for s in servers)


def test_builder_rejects_unknown_template(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    executor = McpBuilderExecutor(ws, store)
    result = executor.execute(
        _action("mcp_server_create", {"name": "x", "template": "rm-rf-server"}),
        _principal(),
    )
    assert result.ok is False
    assert result.reason_code is not None
    assert result.reason_code.startswith("mcp_unknown_template")


def test_builder_rejects_absolute_output_path(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    executor = McpBuilderExecutor(ws, store)
    result = executor.execute(
        _action(
            "mcp_server_create",
            {"name": "x", "template": "python-stdio-echo", "output_path": "/etc/evil.py"},
        ),
        _principal(),
    )
    assert result.ok is False
    assert result.reason_code == "mcp_output_path_not_workspace_relative"


def test_builder_rejects_parent_escape_output_path(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    executor = McpBuilderExecutor(ws, store)
    result = executor.execute(
        _action(
            "mcp_server_create",
            {"name": "x", "template": "python-stdio-echo", "output_path": "../escape.py"},
        ),
        _principal(),
    )
    assert result.ok is False
    assert result.reason_code == "mcp_output_path_not_workspace_relative"


def test_available_templates_are_known() -> None:
    templates = available_mcp_templates()
    assert "python-stdio-echo" in templates


# ── Owner isolation ──────────────────────────────────────────────────────────


def test_mcp_server_profiles_are_owner_isolated(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    sid = new_id("mcp_")
    store.create_mcp_server(
        server_id=sid,
        principal_id="principal_a",
        name="a-server",
        command=["python", ".raiker/mcp/servers/a.py"],
        template="python-stdio-echo",
        status="created",
    )
    assert any(s["server_id"] == sid for s in store.list_mcp_servers("principal_a"))
    # A different owner sees nothing and cannot resolve the row.
    assert store.list_mcp_servers("principal_b") == []
    assert store.get_mcp_server(sid, "principal_b") is None
    assert store.get_mcp_server(sid, "principal_a") is not None


# ── End-to-end bounded stdio session (real local server, no network) ─────────


def _build_echo_server(ws: Path, store: SQLiteStore) -> str:
    builder = McpBuilderExecutor(ws, store)
    result = builder.execute(
        _action("mcp_server_create", {"name": "echo", "template": "python-stdio-echo"}),
        _principal(),
    )
    assert result.ok is True, result.reason_code
    return str(result.artifacts["path"])


def test_connect_and_list_tools_end_to_end(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    rel = _build_echo_server(ws, store)
    connector = McpConnectorExecutor(ws, store)
    result = connector.execute(
        _action("mcp_connect", {"command": ["python", rel], "name": "echo"}), _principal()
    )
    assert result.ok is True, result.reason_code
    assert result.artifacts["tool_count"] >= 1
    assert "echo" in result.artifacts["tools"]

    listed = connector.execute(
        _action("mcp_list_tools", {"command": ["python", rel]}), _principal()
    )
    assert listed.ok is True, listed.reason_code
    assert "echo" in listed.artifacts["tools"]


def test_call_tool_returns_redacted_output(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    rel = _build_echo_server(ws, store)
    connector = McpConnectorExecutor(ws, store)
    secret = "SENSITIVE-PAYLOAD-9271"
    result = connector.execute(
        _action(
            "mcp_call_tool",
            {"command": ["python", rel], "tool_name": "echo", "tool_arguments": {"text": secret}},
        ),
        _principal(),
    )
    assert result.ok is True, result.reason_code
    assert result.artifacts["content_redacted"] is True
    assert result.artifacts["content_length"] == len(secret)
    # The raw echoed payload must never appear in the (audited) artifacts.
    assert secret not in json.dumps(result.artifacts)


def test_call_unknown_tool_fails_closed(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    store = SQLiteStore(ws)
    rel = _build_echo_server(ws, store)
    connector = McpConnectorExecutor(ws, store)
    result = connector.execute(
        _action(
            "mcp_call_tool",
            {"command": ["python", rel], "tool_name": "not_a_tool", "tool_arguments": {}},
        ),
        _principal(),
    )
    assert result.ok is False
    assert result.reason_code is not None
    assert result.reason_code.startswith("mcp_tool_")


# ── Governed routing (gate + policy) ─────────────────────────────────────────


def _route_ready(ws: Path) -> tuple[RuntimeAuthority, Principal, SQLiteStore]:
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    svc = RuntimeControlService(ws)
    svc.activate_runtime_mode("local_single_user_runtime", None, "test")
    store = SQLiteStore(ws)
    writer = EventLogWriter(store)
    registry = build_default_executor_registry(ws, store)
    authority = RuntimeAuthority(store, writer, executor_registry=registry)
    raw = store.get_principal("principal_owner")
    assert raw is not None
    return authority, Principal(**raw), store


def test_route_action_executes_server_create_when_enabled(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    authority, principal, _store = _route_ready(ws)
    action = _action("mcp_server_create", {"name": "echo", "template": "python-stdio-echo"})
    result = authority.route_action(action, principal)
    assert result.decision == "allow"
    assert result.message == "executed", result.error


def test_route_action_denies_when_gate_disabled(tmp_path: Path) -> None:
    ws = _ws(tmp_path)
    authority, principal, _store = _route_ready(ws)
    svc = RuntimeControlService(ws)
    disabled = svc.set_capability_state("mcp_connector_runtime", "disabled", None, "test")
    assert disabled.ok is True, disabled.reason_code
    action = _action("mcp_connect", {"command": ["python", "server.py"]})
    result = authority.route_action(action, principal)
    assert result.decision == "disabled_by_capability_gate"


def test_mcp_action_types_are_governed_by_policy(tmp_path: Path) -> None:
    from raiker.contracts.models import ToolAction
    from raiker.policy.config import StaticPolicyConfig
    from raiker.policy.engine import PolicyEngine

    engine = PolicyEngine(StaticPolicyConfig(tmp_path))
    for tool in ("mcp_server_create", "mcp_connect", "mcp_list_tools", "mcp_call_tool"):
        decision = engine.review(
            ToolAction(
                action_id=new_id("act_"),
                tool_name=tool,
                arguments={},
                risk_level="medium",
                requires_approval=True,
                proposed_by="model",
            )
        )
        # Must be governed (approval), never silently denied as unknown.
        assert decision.decision == "needs_approval", tool
        assert "unknown_or_denied_tool" not in decision.reasons


# ── Owner-scoped API read ────────────────────────────────────────────────────


def test_api_lists_only_callers_mcp_servers(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from raiker.api.app import create_app

    ws = tmp_path / "api_ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    store = SQLiteStore(ws)
    # The owner's server, plus another principal's server that must stay hidden.
    store.create_mcp_server(
        server_id=new_id("mcp_"),
        principal_id="principal_owner",
        name="mine",
        command=["python", ".raiker/mcp/servers/mine.py"],
        template="python-stdio-echo",
        status="created",
    )
    store.create_mcp_server(
        server_id=new_id("mcp_"),
        principal_id="principal_other",
        name="theirs",
        command=["python", ".raiker/mcp/servers/theirs.py"],
        template="python-stdio-echo",
        status="created",
    )
    client = TestClient(create_app(ws))
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    resp = client.get("/api/mcp/servers", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    names = {row["name"] for row in resp.json()}
    assert names == {"mine"}
    assert resp.json()[0]["command"] == ["python", ".raiker/mcp/servers/mine.py"]


def test_api_mcp_servers_requires_auth(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from raiker.api.app import create_app

    ws = tmp_path / "api_ws2"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    client = TestClient(create_app(ws))
    assert client.get("/api/mcp/servers").status_code == 401


# ── End-to-end management API (Control Deck task 4b) ─────────────────────────


def _mgmt_client(tmp_path: Path, sub: str = "mgmt") -> Any:
    from fastapi.testclient import TestClient

    from raiker.api.app import create_app

    ws = tmp_path / sub
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    client = TestClient(create_app(ws))
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return ws, client


def test_api_create_then_list_mcp_server(tmp_path: Path) -> None:
    ws, client = _mgmt_client(tmp_path)
    resp = client.post("/api/mcp/servers", json={"name": "Echo Server", "template": "python-stdio-echo"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True
    servers = client.get("/api/mcp/servers").json()
    assert len(servers) == 1
    assert servers[0]["template"] == "python-stdio-echo"
    # The generated file exists on disk under the managed dir.
    assert (ws / ".raiker/mcp/servers" / f"{servers[0]['name']}.py").exists()


def test_api_create_rejects_unknown_template(tmp_path: Path) -> None:
    _ws, client = _mgmt_client(tmp_path, "mgmt_tmpl")
    resp = client.post("/api/mcp/servers", json={"name": "x", "template": "danger"})
    assert resp.status_code == 403
    assert resp.json()["detail"]["reason_code"].startswith("mcp_unknown_template")


def test_api_connect_persists_discovered_tools(tmp_path: Path) -> None:
    _ws, client = _mgmt_client(tmp_path, "mgmt_conn")
    client.post("/api/mcp/servers", json={"name": "echo", "template": "python-stdio-echo"})
    server_id = client.get("/api/mcp/servers").json()[0]["server_id"]
    resp = client.post(f"/api/mcp/servers/{server_id}/connect")
    assert resp.status_code == 200, resp.text
    assert "echo" in resp.json()["tools"]
    listed = client.get("/api/mcp/servers").json()[0]
    assert listed["status"] == "connected"
    assert listed["tool_count"] >= 1
    assert "echo" in listed["tools"]


def test_api_rename_mcp_server(tmp_path: Path) -> None:
    _ws, client = _mgmt_client(tmp_path, "mgmt_rename")
    client.post("/api/mcp/servers", json={"name": "echo", "template": "python-stdio-echo"})
    server_id = client.get("/api/mcp/servers").json()[0]["server_id"]
    resp = client.put(f"/api/mcp/servers/{server_id}", json={"name": "renamed-echo"})
    assert resp.status_code == 200, resp.text
    assert client.get("/api/mcp/servers").json()[0]["name"] == "renamed-echo"


def test_api_rename_rejects_empty_name(tmp_path: Path) -> None:
    _ws, client = _mgmt_client(tmp_path, "mgmt_rename_bad")
    client.post("/api/mcp/servers", json={"name": "echo", "template": "python-stdio-echo"})
    server_id = client.get("/api/mcp/servers").json()[0]["server_id"]
    resp = client.put(f"/api/mcp/servers/{server_id}", json={"name": "   "})
    assert resp.status_code == 422
    assert resp.json()["detail"]["reason_code"] == "mcp_invalid_server_name"


def test_api_delete_removes_profile_and_file(tmp_path: Path) -> None:
    ws, client = _mgmt_client(tmp_path, "mgmt_delete")
    client.post("/api/mcp/servers", json={"name": "echo", "template": "python-stdio-echo"})
    server = client.get("/api/mcp/servers").json()[0]
    server_file = ws / ".raiker/mcp/servers" / f"{server['name']}.py"
    assert server_file.exists()
    resp = client.delete(f"/api/mcp/servers/{server['server_id']}")
    assert resp.status_code == 200, resp.text
    assert client.get("/api/mcp/servers").json() == []
    assert not server_file.exists()


def test_api_delete_foreign_server_is_owner_scoped(tmp_path: Path) -> None:
    ws, client = _mgmt_client(tmp_path, "mgmt_iso")
    store = SQLiteStore(ws)
    sid = new_id("mcp_")
    store.create_mcp_server(
        server_id=sid,
        principal_id="principal_other",
        name="theirs",
        command=["python", ".raiker/mcp/servers/theirs.py"],
        template="python-stdio-echo",
        status="created",
    )
    resp = client.delete(f"/api/mcp/servers/{sid}")
    assert resp.status_code == 403
    # The other principal's row is untouched.
    assert store.get_mcp_server(sid, "principal_other") is not None


def test_api_create_denied_when_capability_gate_disabled(tmp_path: Path) -> None:
    ws, client = _mgmt_client(tmp_path, "mgmt_gate")
    RuntimeControlService(ws).set_capability_state("mcp_builder_runtime", "disabled", None, "test")
    resp = client.post("/api/mcp/servers", json={"name": "echo", "template": "python-stdio-echo"})
    assert resp.status_code == 403
    assert resp.json()["detail"]["reason_code"] == "disabled_by_capability_gate"


def test_api_mcp_write_requires_auth(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from raiker.api.app import create_app

    ws = tmp_path / "mgmt_noauth"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    client = TestClient(create_app(ws))
    assert client.post("/api/mcp/servers", json={"name": "x", "template": "python-stdio-echo"}).status_code == 401


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
