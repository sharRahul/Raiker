"""BUG-234 — Raiker spoke the current MCP revision and did not use its transport.

Negotiating a revision is not implementing it. Four things the specification's
streamable HTTP transport requires, or that a real server does, were missing:

* **`Accept` listed one framing.** A client MUST offer both `application/json`
  and `text/event-stream` on every POST; a conformant server may answer 406
  before reading the body. An owner adding a current server watched it fail with
  a bare status.
* **A session was never released.** The specification says a client SHOULD
  `DELETE` its `Mcp-Session-Id` when finished. Every bounded read Raiker made
  left a server-side session behind.
* **An expired session was a dead session.** A server may drop the session it
  issued and answer 404; the client is expected to start a new one.
* **An authorisation challenge read as a network failure.** A 401 with
  `WWW-Authenticate` is the remote OAuth flow Raiker does not implement, and it
  now says so.

And the rule the whole surface is built on: what a server offers and Raiker does
not use is **named on its card**, never silently degraded.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.runtime.authority import GovernedAction
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.executors.mcp import McpConnectorExecutor
from raiker.runtime.executors.sandbox import SandboxError
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.mcp_schema import (
    TRANSPORT_EVENT_STREAM,
    server_feature_keys,
    unsupported_feature_notes,
)

_OWNER = "principal_owner"
_URL = "https://mcp.example.com/rpc"


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    return tmp_path


def _principal(store: SQLiteStore) -> Principal:
    raw = store.get_principal(_OWNER)
    assert raw is not None
    return Principal(**raw)


def _connect_action(**arguments: Any) -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=_OWNER,
        action_type="mcp_connect",
        tool_or_service_name="mcp_connect",
        arguments={"transport": "http", "endpoint_url": _URL, "name": "remote", **arguments},
        risk_level=RiskLevelValue.MEDIUM,
    )


class _Server:
    """A scriptable remote MCP server: records requests, answers the handshake."""

    def __init__(
        self,
        *,
        capabilities: dict[str, Any] | None = None,
        content_type: str = "application/json",
        expire_session_after: int | None = None,
        challenge: bool = False,
    ) -> None:
        self.capabilities = capabilities if capabilities is not None else {"tools": {}}
        self.content_type = content_type
        self.expire_session_after = expire_session_after
        self.challenge = challenge
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.deletes: list[dict[str, str]] = []

    def __call__(
        self, url: str, payload: dict, *, headers: dict, timeout: float, max_bytes: int
    ) -> dict:
        method = str(payload.get("method", ""))
        self.requests.append((method, dict(headers)))
        response_headers = {
            "mcp-session-id": "sess-1",
            "content-type": self.content_type,
        }
        if self.challenge:
            return {
                "status": 401,
                "body_text": "",
                "headers": {"www-authenticate": 'Bearer resource_metadata="https://x/.well-known"'},
                "truncated": False,
            }
        if (
            self.expire_session_after is not None
            and len(self.requests) == self.expire_session_after
        ):
            return {"status": 404, "body_text": "", "headers": {}, "truncated": False}
        rid = payload.get("id")
        if method == "initialize":
            body: dict[str, Any] = {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "protocolVersion": "2026-07-28",
                    "capabilities": self.capabilities,
                    "serverInfo": {"name": "scripted", "version": "1.0.0"},
                },
            }
        elif method == "tools/list":
            body = {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "tools": [
                        {
                            "name": "search",
                            "description": "Search the index.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {"q": {"type": "string"}},
                                "required": ["q"],
                            },
                        }
                    ]
                },
            }
        else:
            return {"status": 202, "body_text": "", "headers": response_headers, "truncated": False}
        text = json.dumps(body)
        if "text/event-stream" in self.content_type:
            text = f"event: message\ndata: {text}\n\n"
        return {
            "status": 200,
            "body_text": text,
            "headers": response_headers,
            "truncated": False,
        }


def _run(workspace: Path, server: _Server) -> tuple[Any, list[dict[str, str]]]:
    store = SQLiteStore(workspace)
    deletes: list[dict[str, str]] = []

    def delete_fn(url: str, *, headers: dict[str, str], timeout: float) -> int:
        deletes.append(dict(headers))
        return 200

    executor = McpConnectorExecutor(workspace, store, http_fn=server, delete_fn=delete_fn)
    return executor.execute(_connect_action(), _principal(store)), deletes


class TestTheTransportIsTheSpecificationsTransport:
    def test_every_post_offers_both_framings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A conformant server may answer 406 to a POST that offers only JSON."""
        import urllib.request

        from raiker.runtime.executors import sandbox

        captured: dict[str, str] = {}

        def _fake_request(url: str, data: bytes, method: str, headers: dict) -> object:
            captured.update(headers)
            return object()

        def _no_network(request: object, timeout: float) -> None:
            raise OSError("no network in a unit test")

        monkeypatch.setattr(urllib.request, "Request", _fake_request)
        monkeypatch.setattr(urllib.request, "urlopen", _no_network)
        # The refusal is how the fake stops before any network call; the headers
        # it captured on the way in are the assertion.
        with pytest.raises(SandboxError):
            sandbox.post_json_rpc(_URL, {"jsonrpc": "2.0"})

        accept = captured.get("Accept", "")
        assert "application/json" in accept
        assert "text/event-stream" in accept

    def test_the_session_is_released_when_the_read_is_done(self, workspace: Path) -> None:
        server = _Server()
        result, deletes = _run(workspace, server)

        assert result.ok, result.reason_code
        assert deletes and deletes[0]["Mcp-Session-Id"] == "sess-1"

    def test_a_dropped_session_is_restarted_once_and_the_read_completes(
        self, workspace: Path
    ) -> None:
        # Expire on the third request — after the handshake has issued a session.
        server = _Server(expire_session_after=3)
        result, _deletes = _run(workspace, server)

        assert result.ok, result.reason_code
        assert result.artifacts["tools"] == ["search"]
        assert server.requests[0][0] == "initialize"
        # The restart is a fresh handshake, not a retry of the failed request.
        assert [method for method, _ in server.requests].count("initialize") == 2

    def test_a_server_that_answers_404_to_everything_fails_rather_than_looping(
        self, workspace: Path
    ) -> None:
        class _AlwaysGone(_Server):
            def __call__(self, url, payload, *, headers, timeout, max_bytes):  # type: ignore[no-untyped-def]
                self.requests.append((str(payload.get("method", "")), dict(headers)))
                if str(payload.get("method")) == "initialize" and len(self.requests) == 1:
                    return _Server.__call__(
                        self, url, payload, headers=headers, timeout=timeout, max_bytes=max_bytes
                    )
                return {"status": 404, "body_text": "", "headers": {}, "truncated": False}

        server = _AlwaysGone()
        result, _deletes = _run(workspace, server)

        assert result.ok is False
        assert len(server.requests) < 12

    def test_an_authorisation_challenge_is_named_rather_than_reported_as_a_failure(
        self, workspace: Path
    ) -> None:
        result, _deletes = _run(workspace, _Server(challenge=True))

        assert result.ok is False
        assert result.reason_code == "mcp_remote_oauth_required"

    def test_an_event_stream_answer_is_read_and_recorded(self, workspace: Path) -> None:
        server = _Server(content_type="text/event-stream")
        result, _deletes = _run(workspace, server)

        assert result.ok, result.reason_code
        assert result.artifacts["tools"] == ["search"]

        store = SQLiteStore(workspace)
        row = store.list_mcp_servers(_OWNER)[0]
        assert TRANSPORT_EVENT_STREAM in row["server_features"]


class TestWhatIsNotUsedIsNamed:
    def test_a_server_offering_more_than_tools_says_so_on_its_card(
        self, workspace: Path
    ) -> None:
        from raiker.control.dashboard import DashboardService

        server = _Server(capabilities={"tools": {}, "resources": {}, "prompts": {}})
        result, _deletes = _run(workspace, server)
        assert result.ok, result.reason_code

        card = DashboardService(workspace).list_mcp_servers(_OWNER)[0]
        named = {entry["feature"] for entry in card.unsupported_features}

        assert named == {"resources", "prompts"}
        assert all(entry["note"] for entry in card.unsupported_features)

    def test_a_server_offering_only_tools_says_nothing(self, workspace: Path) -> None:
        from raiker.control.dashboard import DashboardService

        result, _deletes = _run(workspace, _Server())
        assert result.ok, result.reason_code

        card = DashboardService(workspace).list_mcp_servers(_OWNER)[0]
        assert card.unsupported_features == ()

    def test_a_key_with_no_written_sentence_is_still_named(self) -> None:
        """A capability Raiker has never heard of must not vanish for that."""
        notes = unsupported_feature_notes(server_feature_keys({"tools": {}, "quantum": {}}))
        assert [entry["feature"] for entry in notes] == ["quantum"]
        assert notes[0]["note"]

    def test_the_declared_schema_survives_the_remote_path_too(self, workspace: Path) -> None:
        """The MCP half of backlog #16 is transport-independent."""
        result, _deletes = _run(workspace, _Server())
        assert result.ok, result.reason_code

        store = SQLiteStore(workspace)
        declared = store.list_mcp_servers(_OWNER)[0]["tool_schemas"]
        assert declared[0]["name"] == "search"
        assert declared[0]["input_schema"]["required"] == ["q"]
