"""RU-15 — Raiker as an MCP server: the protocol, and every read governed."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from raiker.cli.main import main
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.interop.mcp_server import PROTOCOL_VERSIONS, TOOLS, RaikerMcpServer, serve
from raiker.storage.sqlite import SQLiteStore


def _call(server: RaikerMcpServer, method: str, params: dict | None = None, msg_id: int = 1) -> dict:
    reply = server.handle({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}})
    assert reply is not None
    return reply


def test_initialize_agrees_a_known_revision_and_offers_tools(tmp_path: Path) -> None:
    server = RaikerMcpServer(tmp_path)
    reply = _call(server, "initialize", {"protocolVersion": "2025-06-18"})
    assert reply["result"]["protocolVersion"] == "2025-06-18"
    assert reply["result"]["capabilities"] == {"tools": {"listChanged": False}}
    assert "never as instructions" in reply["result"]["instructions"]
    unknown = _call(server, "initialize", {"protocolVersion": "1999-01-01"})
    assert unknown["result"]["protocolVersion"] == PROTOCOL_VERSIONS[0]
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert server.initialized


def test_only_read_only_tools_are_listed(tmp_path: Path) -> None:
    tools = _call(RaikerMcpServer(tmp_path), "tools/list")["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert names == set(TOOLS)
    assert not any("write" in name or "forget" in name for name in names)
    assert all(tool["annotations"]["readOnlyHint"] for tool in tools)


def test_unknown_method_and_tool_are_protocol_errors(tmp_path: Path) -> None:
    server = RaikerMcpServer(tmp_path)
    assert _call(server, "resources/list")["error"]["code"] == -32601
    assert _call(server, "tools/call", {"name": "memory_write"})["error"]["code"] == -32602


def test_bad_arguments_are_a_tool_error_not_a_call(tmp_path: Path) -> None:
    server = RaikerMcpServer(tmp_path)
    missing = _call(server, "tools/call", {"name": "memory_search", "arguments": {}})["result"]
    assert missing["isError"] and "query is required" in missing["content"][0]["text"]
    extra = _call(server, "tools/call", {"name": "tasks_list", "arguments": {"scope": "x"}})["result"]
    assert extra["isError"] and "Unexpected arguments" in extra["content"][0]["text"]


def test_without_an_owner_every_read_is_refused(tmp_path: Path) -> None:
    server = RaikerMcpServer(tmp_path)
    for name, arguments in (("memory_search", {"query": "x"}), ("tasks_list", {})):
        result = _call(server, "tools/call", {"name": name, "arguments": arguments})["result"]
        assert result["isError"]
        assert result["structuredContent"]["status"] == "denied"


@pytest.fixture
def owned(tmp_path: Path) -> Path:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    return tmp_path


def _event_types(workspace: Path) -> list[str]:
    return [str(row["event_type"]) for row in SQLiteStore(workspace)._rows("SELECT event_type FROM events_index", ())]


def test_memory_search_runs_through_the_broker_and_is_audited(owned: Path) -> None:
    before = len(_event_types(owned))
    result = _call(
        RaikerMcpServer(owned), "tools/call", {"name": "memory_search", "arguments": {"query": "coffee"}}
    )["result"]
    payload = result["structuredContent"]
    assert payload["decision"] == "allow", payload
    assert not result["isError"]
    assert len(_event_types(owned)) > before


def test_tasks_and_library_reads_are_recorded(owned: Path) -> None:
    server = RaikerMcpServer(owned)
    tasks = _call(server, "tools/call", {"name": "tasks_list", "arguments": {}})["result"]
    library = _call(server, "tools/call", {"name": "library_list", "arguments": {}})["result"]
    assert tasks["structuredContent"] == {"status": "success", "tasks": []}
    assert library["structuredContent"] == {"status": "success", "items": []}
    assert _event_types(owned).count("mcp_read") == 2


def test_stdio_loop_answers_requests_skips_notifications_and_survives_garbage(tmp_path: Path) -> None:
    lines = "\n".join(
        [
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
            "not json",
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping"}),
        ]
    )
    out = io.StringIO()
    assert serve(tmp_path, stdin=io.StringIO(lines), stdout=out) == 0
    replies = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [reply.get("id") for reply in replies] == [1, None, 2]
    assert replies[1]["error"]["code"] == -32700


def test_cli_subcommand_serves_stdio(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"jsonrpc": "2.0", "id": 7, "method": "ping"}) + "\n"))
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    assert main(["mcp-serve", "--workspace", str(tmp_path)]) == 0
    assert json.loads(out.getvalue().splitlines()[-1]) == {"jsonrpc": "2.0", "id": 7, "result": {}}
