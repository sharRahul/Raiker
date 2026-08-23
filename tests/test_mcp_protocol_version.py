"""BUG-234 — the MCP revision Raiker offers, accepts, and refuses.

Raiker negotiated `2024-11-05` for five revisions. That is not merely dated: a
server implementing only the current revision refuses the older handshake, so it
could not be connected at all. The specification's backward-compatibility rule is
that the client offers its preferred revision and the server answers with the one
it will speak — so the client has to *offer* the current one and *accept* an
older answer, and refuse a revision it does not implement rather than continuing
on a framing it cannot trust.
"""

from __future__ import annotations

from pathlib import Path

from raiker.runtime.executors.mcp import (
    MCP_LEGACY_PROTOCOL_VERSION,
    MCP_PROTOCOL_VERSION,
    MCP_SUPPORTED_PROTOCOL_VERSIONS,
    _extract_call,
    _extract_tools,
    _initialize_rpc,
    negotiated_protocol_version,
)


def _init_response(version: str | None) -> dict:
    result: dict = {"capabilities": {"tools": {}}, "serverInfo": {"name": "s", "version": "1"}}
    if version is not None:
        result["protocolVersion"] = version
    return {"jsonrpc": "2.0", "id": 1, "result": result}


def test_raiker_offers_the_current_revision() -> None:
    assert MCP_PROTOCOL_VERSION == "2026-07-28"
    assert _initialize_rpc()["params"]["protocolVersion"] == MCP_PROTOCOL_VERSION


def test_the_older_handshake_is_still_accepted() -> None:
    """A server on the old revision keeps working — that is the whole point."""
    assert MCP_LEGACY_PROTOCOL_VERSION == "2024-11-05"
    assert MCP_LEGACY_PROTOCOL_VERSION in MCP_SUPPORTED_PROTOCOL_VERSIONS
    assert {"2025-06-18", "2025-03-26"} <= MCP_SUPPORTED_PROTOCOL_VERSIONS


def test_an_omitted_version_reads_as_the_one_offered() -> None:
    """That is what the handshake means; it is not an unknown."""
    assert negotiated_protocol_version({}) == MCP_PROTOCOL_VERSION


def test_a_supported_answer_is_accepted() -> None:
    responses = {
        1: _init_response(MCP_LEGACY_PROTOCOL_VERSION),
        2: {"jsonrpc": "2.0", "id": 2, "result": {"tools": [{"name": "echo"}]}},
    }
    reason, names, init = _extract_tools(responses)

    assert reason is None
    assert names == ["echo"]
    assert negotiated_protocol_version(init) == MCP_LEGACY_PROTOCOL_VERSION


def test_an_unsupported_answer_fails_closed_and_names_the_revision() -> None:
    responses = {
        1: _init_response("2099-01-01"),
        2: {"jsonrpc": "2.0", "id": 2, "result": {"tools": [{"name": "echo"}]}},
    }
    reason, names, _init = _extract_tools(responses)

    assert reason == "mcp_protocol_version_unsupported:2099-01-01"
    assert names == [], "no tool is enumerated from a session Raiker cannot frame"


def test_a_tool_call_refuses_an_unsupported_revision_too() -> None:
    """Not only the enumerating path — a `tools/call` session refuses as well."""
    responses = {
        1: _init_response("2099-01-01"),
        3: {"jsonrpc": "2.0", "id": 3, "result": {"content": [{"text": "hi"}]}},
    }
    reason, blocks, length = _extract_call(responses)

    assert reason == "mcp_protocol_version_unsupported:2099-01-01"
    assert (blocks, length) == (0, 0)


def test_the_generated_server_template_speaks_the_current_revision() -> None:
    from raiker.runtime.executors.mcp import _ECHO_SERVER_TEMPLATE

    assert 'PROTOCOL_VERSION = "2026-07-28"' in _ECHO_SERVER_TEMPLATE
    # And echoes back an older revision a client asks for, which is what a
    # server is supposed to do rather than forcing its own.
    assert "SUPPORTED_PROTOCOL_VERSIONS" in _ECHO_SERVER_TEMPLATE
    assert '"protocolVersion": agreed' in _ECHO_SERVER_TEMPLATE


def test_the_negotiated_revision_is_persisted_per_server(tmp_path: Path) -> None:
    """Extensions → MCP states it, so the store has to keep it."""
    from raiker.storage.sqlite import SQLiteStore

    store = SQLiteStore(tmp_path)
    store.create_mcp_server(
        server_id="mcp_1",
        principal_id="principal_owner",
        name="echo",
        command=["python", "server.py"],
        protocol_version=MCP_PROTOCOL_VERSION,
    )
    row = store.get_mcp_server("mcp_1", "principal_owner")
    assert row is not None
    assert row["protocol_version"] == MCP_PROTOCOL_VERSION

    store.update_mcp_server_runtime(
        "mcp_1", "principal_owner", status="connected",
        protocol_version=MCP_LEGACY_PROTOCOL_VERSION,
    )
    row = store.get_mcp_server("mcp_1", "principal_owner")
    assert row is not None
    assert row["protocol_version"] == MCP_LEGACY_PROTOCOL_VERSION

    # A session that does not renegotiate leaves the stored value alone.
    store.update_mcp_server_runtime("mcp_1", "principal_owner", status="connected")
    row = store.get_mcp_server("mcp_1", "principal_owner")
    assert row is not None
    assert row["protocol_version"] == MCP_LEGACY_PROTOCOL_VERSION
