"""BUG-234 — a server-initiated request was filed as an answer to Raiker's own.

Both transports sorted messages by one test:

```python
if isinstance(message, dict) and "id" in message:
    responses[message["id"]] = message
```

JSON-RPC is bidirectional, and a request the *server* sends carries an ``id``
from the **server's** numbering space. Raiker's initialize is id 1 and its
tools/list is id 2; a server that pings the client during the handshake, or asks
it to elicit, commonly numbers its own first request 1. That message landed on
top of Raiker's answer, and the read failed as ``mcp_initialize_failed`` — a
reason that names Raiker's request and blames the server for not answering it,
about a server that had answered correctly and gone on to ask a question.

The request was also never answered, so a conformant server sat waiting for a
reply that was never coming and spent its own timeout on it.

Three things this file holds to:

* **Direction is read from ``method``, never from the id.** An id says what a
  message is about; only ``method`` says which way it is going.
* **A refusal is an answer.** Raiker declares no client capabilities, so
  ``-32601`` is the truthful reply — and a *complete* one, which silence is not.
* **What was asked for is named on the card.** A server whose feature quietly
  does nothing has to say so, which is the rule the whole MCP surface is built
  on.
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
from raiker.runtime.executors.mcp import (
    JSONRPC_METHOD_NOT_FOUND,
    McpConnectorExecutor,
    classify_jsonrpc,
    server_request_answer,
)
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.mcp_schema import ASKED_PREFIX, server_feature_keys, unsupported_feature_notes

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


def _connect_action() -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=_OWNER,
        action_type="mcp_connect",
        tool_or_service_name="mcp_connect",
        arguments={"transport": "http", "endpoint_url": _URL, "name": "remote"},
        risk_level=RiskLevelValue.MEDIUM,
    )


class _AskingServer:
    """A server that answers correctly *and* asks Raiker for something.

    The request it interleaves is numbered 1 — the id Raiker's own initialize
    uses — because that collision is the defect, not a contrivance: a server
    numbering its first request 1 is doing the ordinary thing.
    """

    def __init__(self, *, method: str = "elicitation/create", stream: bool = True) -> None:
        self.method = method
        self.stream = stream
        self.posted: list[dict[str, Any]] = []

    def __call__(
        self, url: str, payload: dict, *, headers: dict, timeout: float, max_bytes: int
    ) -> dict:
        self.posted.append(dict(payload))
        method = str(payload.get("method", ""))
        rid = payload.get("id")
        content_type = "text/event-stream" if self.stream else "application/json"
        response_headers = {"mcp-session-id": "sess-1", "content-type": content_type}
        if method == "initialize":
            answer: dict[str, Any] = {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "protocolVersion": "2026-07-28",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "asking", "version": "1.0.0"},
                },
            }
            # The server's own request, in the same stream, numbered 1.
            ask = {"jsonrpc": "2.0", "id": 1, "method": self.method, "params": {}}
            if self.stream:
                body = (
                    f"event: message\ndata: {json.dumps(answer)}\n\n"
                    f"event: message\ndata: {json.dumps(ask)}\n\n"
                )
            else:
                body = json.dumps([answer, ask])
        elif method == "tools/list":
            answer = {"jsonrpc": "2.0", "id": rid, "result": {"tools": [{"name": "search"}]}}
            body = (
                f"event: message\ndata: {json.dumps(answer)}\n\n"
                if self.stream
                else json.dumps(answer)
            )
        else:
            # Raiker's answer to the server's request lands here.
            return {"status": 202, "body_text": "", "headers": response_headers, "truncated": False}
        return {
            "status": 200,
            "body_text": body,
            "headers": response_headers,
            "truncated": False,
        }


def _run(workspace: Path, server: Any) -> Any:
    store = SQLiteStore(workspace)
    executor = McpConnectorExecutor(
        workspace, store, http_fn=server, delete_fn=lambda url, **_kwargs: 200
    )
    return executor.execute(_connect_action(), _principal(store))


class TestDirectionIsReadFromMethod:
    @pytest.mark.parametrize(
        ("message", "expected"),
        [
            ({"jsonrpc": "2.0", "id": 1, "method": "ping"}, "request"),
            ({"jsonrpc": "2.0", "id": 1, "result": {}}, "response"),
            ({"jsonrpc": "2.0", "id": 1, "error": {"code": -1}}, "response"),
            ({"jsonrpc": "2.0", "method": "notifications/progress"}, "notification"),
            ({"jsonrpc": "2.0"}, "invalid"),
            ("not a message", "invalid"),
        ],
    )
    def test_every_shape_is_told_apart(self, message: Any, expected: str) -> None:
        assert classify_jsonrpc(message) == expected

    def test_an_id_alone_never_decides(self) -> None:
        """The same id is a request one way and a response the other."""
        assert classify_jsonrpc({"id": 1, "method": "ping"}) == "request"
        assert classify_jsonrpc({"id": 1, "result": {}}) == "response"


class TestARefusalIsAnAnswer:
    def test_ping_is_answered_with_an_empty_result(self) -> None:
        answer = server_request_answer({"jsonrpc": "2.0", "id": 7, "method": "ping"})

        assert answer == {"jsonrpc": "2.0", "id": 7, "result": {}}

    @pytest.mark.parametrize(
        "method", ["elicitation/create", "sampling/createMessage", "roots/list", "made/up"]
    )
    def test_an_undeclared_capability_is_refused_by_its_own_code(self, method: str) -> None:
        answer = server_request_answer({"jsonrpc": "2.0", "id": 3, "method": method})

        assert answer["id"] == 3
        assert answer["error"]["code"] == JSONRPC_METHOD_NOT_FOUND
        assert method in answer["error"]["message"]
        assert "result" not in answer


class TestTheHandshakeSurvivesAServerThatAsks:
    def test_a_server_request_numbered_one_no_longer_eats_the_initialize_answer(
        self, workspace: Path
    ) -> None:
        """The defect, reproduced end to end: this read used to fail closed."""
        result = _run(workspace, _AskingServer())

        assert result.ok, result.reason_code
        assert result.artifacts["tools"] == ["search"]

    def test_the_same_holds_when_the_answer_arrives_as_a_json_array(
        self, workspace: Path
    ) -> None:
        result = _run(workspace, _AskingServer(stream=False))

        assert result.ok, result.reason_code

    def test_the_request_is_answered_rather_than_left_waiting(self, workspace: Path) -> None:
        server = _AskingServer()
        _run(workspace, server)

        answers = [p for p in server.posted if "method" not in p and p.get("id") == 1]
        assert len(answers) == 1
        assert answers[0]["error"]["code"] == JSONRPC_METHOD_NOT_FOUND

    def test_a_ping_gets_a_result_not_a_refusal(self, workspace: Path) -> None:
        server = _AskingServer(method="ping")
        _run(workspace, server)

        answers = [p for p in server.posted if "method" not in p and p.get("id") == 1]
        assert answers and answers[0]["result"] == {}


class TestTheCardNamesWhatWasAsked:
    def test_the_connection_stores_the_method_the_server_asked_for(
        self, workspace: Path
    ) -> None:
        server = _AskingServer()
        _run(workspace, server)

        store = SQLiteStore(workspace)
        profiles = store.list_mcp_servers(_OWNER)
        stored = profiles[0]["server_features"]
        assert f"{ASKED_PREFIX}elicitation/create" in stored

    def test_the_key_becomes_a_sentence_that_says_it_was_refused(self) -> None:
        notes = unsupported_feature_notes([f"{ASKED_PREFIX}elicitation/create"])

        assert len(notes) == 1
        assert "Refused" in notes[0]["note"]
        assert "question" in notes[0]["note"]

    def test_a_method_nobody_wrote_a_sentence_for_is_still_named(self) -> None:
        notes = unsupported_feature_notes([f"{ASKED_PREFIX}vendor/experiment"])

        assert "vendor/experiment" in notes[0]["note"]

    def test_ping_reads_as_answered_rather_than_refused(self) -> None:
        notes = unsupported_feature_notes([f"{ASKED_PREFIX}ping"])

        assert "Answered" in notes[0]["note"]

    def test_the_keys_are_bounded_and_deduplicated(self) -> None:
        keys = server_feature_keys(
            {"tools": {}}, server_requests=["ping", "ping", "elicitation/create"]
        )

        assert keys.count(f"{ASKED_PREFIX}ping") == 1
        assert f"{ASKED_PREFIX}elicitation/create" in keys


class TestTheStdioSessionMakesTheSameDistinction:
    """A local server can ask too, and a bounded stdio session cannot answer.

    Every request is written up front and stdin is closed so the server drains
    and exits — that is what makes the session bounded. Holding stdin open to
    reply would make it neither bounded nor non-interactive, so the message is
    kept out of the response map and named, and the server is told nothing
    rather than told the wrong thing.
    """

    def test_a_local_server_request_does_not_displace_the_handshake(
        self, workspace: Path, tmp_path: Path
    ) -> None:
        server_path = workspace / "asking_server.py"
        server_path.write_text(
            "import json, sys\n"
            "for line in sys.stdin:\n"
            "    line = line.strip()\n"
            "    if not line:\n"
            "        continue\n"
            "    msg = json.loads(line)\n"
            "    if msg.get('method') == 'initialize':\n"
            "        print(json.dumps({'jsonrpc': '2.0', 'id': msg['id'], 'result': {\n"
            "            'protocolVersion': '2026-07-28', 'capabilities': {'tools': {}},\n"
            "            'serverInfo': {'name': 'asking', 'version': '1.0'}}}), flush=True)\n"
            "        print(json.dumps({'jsonrpc': '2.0', 'id': 1,\n"
            "            'method': 'roots/list', 'params': {}}), flush=True)\n"
            "    elif msg.get('method') == 'tools/list':\n"
            "        print(json.dumps({'jsonrpc': '2.0', 'id': msg['id'],\n"
            "            'result': {'tools': [{'name': 'local_search'}]}}), flush=True)\n",
            encoding="utf-8",
        )
        store = SQLiteStore(workspace)
        executor = McpConnectorExecutor(workspace, store)
        action = GovernedAction(
            action_id=new_id("act_"),
            principal_id=_OWNER,
            action_type="mcp_connect",
            tool_or_service_name="mcp_connect",
            arguments={
                "transport": "stdio",
                "command": ["python3", "asking_server.py"],
                "name": "local-asking",
            },
            risk_level=RiskLevelValue.MEDIUM,
        )

        result = executor.execute(action, _principal(store))

        assert result.ok, result.reason_code
        assert result.artifacts["tools"] == ["local_search"]
        profiles = [p for p in store.list_mcp_servers(_OWNER) if p["name"] == "local-asking"]
        stored = profiles[0]["server_features"]
        assert f"{ASKED_PREFIX}roots/list" in stored
