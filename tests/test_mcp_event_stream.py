"""BUG-234 — Raiker read an event stream one line at a time and lost the rest.

`_parse_jsonrpc_body` treated every `data:` line as one complete JSON message
and ignored every other field. Two things a conformant server does were
therefore invisible:

* **One event's payload may span several `data:` lines.** The format joins
  them with a newline and dispatches at the blank line, so a sender may break
  wherever the payload already has a newline — which is exactly what a server
  that pretty-prints its JSON-RPC does, and plenty do, because the wire gets
  read by people. Raiker parsed each line on its own; every one of them was a
  fragment, every parse failed, and each was dropped without a word. The read
  then failed as `mcp_initialize_failed` or `mcp_list_tools_failed` about a
  server that had answered correctly — the same shape of wrong reason as the
  server-request defect beside it.
* **`id:` is where to resume from.** The stream carries an id per event so a
  client that loses its place can say where it got to. Raiker dropped it, so the
  one re-handshake it performs after a dropped session (FIXED-378) asked the
  server to do all of its work again.

What this file does not claim: Raiker still reads a bounded response *whole*
rather than incrementally, and holds no connection between turns. That remains
named on the server's card, and this is about reading correctly what it does
read.
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
    McpConnectorExecutor,
    _parse_jsonrpc_body,
    _parse_jsonrpc_messages,
    _parse_sse,
)
from raiker.storage.sqlite import SQLiteStore

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


class TestOneEventMayBeManyDataLines:
    def test_a_split_payload_is_rejoined_before_it_is_parsed(self) -> None:
        body = 'event: message\ndata: {"jsonrpc": "2.0",\ndata:  "id": 1,\ndata:  "result": {}}\n\n'

        messages, _last = _parse_sse(body)

        assert messages == [{"jsonrpc": "2.0", "id": 1, "result": {}}]

    def test_the_old_reading_would_have_dropped_all_three_pieces(self) -> None:
        """Named so the regression is unmistakable: each line alone is not JSON."""
        for piece in ('{"jsonrpc": "2.0",', ' "id": 1,', ' "result": {}}'):
            with pytest.raises(ValueError):
                json.loads(piece)

    def test_events_are_separated_by_the_blank_line_not_by_the_newline(self) -> None:
        body = (
            'event: message\ndata: {"id": 1}\n\n'
            'event: message\ndata: {"id": 2}\n\n'
        )

        messages, _last = _parse_sse(body)

        assert [m["id"] for m in messages] == [1, 2]

    def test_a_final_event_with_no_trailing_blank_line_is_still_read(self) -> None:
        """A bounded read may stop mid-stream, and the last event is still an event."""
        messages, _last = _parse_sse('data: {"id": 9}')

        assert messages == [{"id": 9}]

    def test_a_comment_line_keeps_the_stream_warm_and_contributes_nothing(self) -> None:
        messages, _last = _parse_sse(': keep-alive\n\ndata: {"id": 4}\n\n')

        assert messages == [{"id": 4}]

    def test_one_optional_space_after_the_colon_is_the_separator_not_the_value(self) -> None:
        """`data: x` and `data:x` are the same field; a second space is content."""
        with_space, _a = _parse_sse('data: {"id": 1}\n\n')
        without_space, _b = _parse_sse('data:{"id": 1}\n\n')

        assert with_space == without_space == [{"id": 1}]

    @pytest.mark.parametrize("terminator", ["\n", "\r\n", "\r"])
    def test_every_line_terminator_the_format_allows(self, terminator: str) -> None:
        body = terminator.join(['data: {"id": 3}', "", ""])

        messages, _last = _parse_sse(body)

        assert messages == [{"id": 3}]

    def test_an_array_in_one_event_becomes_its_members(self) -> None:
        messages, _last = _parse_sse('data: [{"id": 1}, {"id": 2}]\n\n')

        assert [m["id"] for m in messages] == [1, 2]


class TestTheStreamSaysWhereToResumeFrom:
    def test_the_last_event_id_is_the_last_one_seen(self) -> None:
        body = (
            'id: 41\ndata: {"id": 1}\n\n'
            'id: 42\ndata: {"id": 2}\n\n'
        )

        _messages, last = _parse_sse(body)

        assert last == "42"

    def test_a_stream_with_no_ids_has_nothing_to_resume_from(self) -> None:
        _messages, last = _parse_sse('data: {"id": 1}\n\n')

        assert last is None

    def test_an_id_carrying_a_null_is_ignored_as_the_format_requires(self) -> None:
        _messages, last = _parse_sse('id: 4\x000\ndata: {"id": 1}\n\n')

        assert last is None

    def test_only_the_event_stream_shape_offers_an_id(self) -> None:
        _messages, last = _parse_jsonrpc_messages('{"id": 1, "result": {}}')

        assert last is None


class TestTheOtherFramingsStillWork:
    @pytest.mark.parametrize(
        ("body", "ids"),
        [
            ('{"id": 1, "result": {}}', [1]),
            ('[{"id": 1}, {"id": 2}]', [1, 2]),
            ('{"id": 1}\n{"id": 2}\n', [1, 2]),
            ("", []),
            ("not json at all", []),
        ],
    )
    def test_a_body_that_is_not_a_stream_is_read_as_it_was(
        self, body: str, ids: list[int]
    ) -> None:
        assert [m["id"] for m in _parse_jsonrpc_body(body)] == ids

    def test_a_bare_json_scalar_contributes_no_messages(self) -> None:
        assert _parse_jsonrpc_body("42") == []


class _SplittingServer:
    """Answers over an event stream, pretty-printing each payload, and numbers
    every event. Drops the session once, to exercise the re-handshake.

    Pretty-printing is the ordinary way a payload comes to span several `data:`
    lines, and it is conformant: the format joins an event's data lines with a
    newline, so a sender may break only where the payload already has one. A
    server that pretty-prints its JSON-RPC — which plenty do, because the wire is
    read by people — was unreadable to Raiker for five revisions.
    """

    def __init__(self, *, expire_after: int | None = None) -> None:
        self.expire_after = expire_after
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.event_number = 0

    def _stream(self, payload: dict[str, Any]) -> str:
        self.event_number += 1
        text = json.dumps(payload, indent=2)
        assert "\n" in text, "the fixture is pointless unless the payload spans lines"
        lines = "".join(f"data: {piece}\n" for piece in text.split("\n"))
        return f"id: {self.event_number}\nevent: message\n{lines}\n"

    def __call__(
        self, url: str, payload: dict, *, headers: dict, timeout: float, max_bytes: int
    ) -> dict:
        method = str(payload.get("method", ""))
        self.requests.append((method, dict(headers)))
        headers_out = {"mcp-session-id": "sess-1", "content-type": "text/event-stream"}
        if self.expire_after is not None and len(self.requests) == self.expire_after:
            return {"status": 404, "body_text": "", "headers": {}, "truncated": False}
        rid = payload.get("id")
        if method == "initialize":
            body = self._stream(
                {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "result": {
                        "protocolVersion": "2026-07-28",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "splitting", "version": "1.0.0"},
                    },
                }
            )
        elif method == "tools/list":
            body = self._stream(
                {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "result": {
                        "tools": [
                            {"name": "search", "description": "Search the index."},
                            {"name": "fetch", "description": "Fetch one record."},
                        ]
                    },
                }
            )
        else:
            return {"status": 202, "body_text": "", "headers": headers_out, "truncated": False}
        return {"status": 200, "body_text": body, "headers": headers_out, "truncated": False}


def _run(workspace: Path, server: Any) -> Any:
    store = SQLiteStore(workspace)
    executor = McpConnectorExecutor(
        workspace, store, http_fn=server, delete_fn=lambda url, **_kwargs: 200
    )
    return executor.execute(_connect_action(), _principal(store))


class TestAConnectionOverASplittingStream:
    def test_the_handshake_and_the_tool_list_both_arrive(self, workspace: Path) -> None:
        result = _run(workspace, _SplittingServer())

        assert result.ok, result.reason_code
        assert result.artifacts["tools"] == ["search", "fetch"]

    def test_the_re_handshake_says_where_it_got_to(self, workspace: Path) -> None:
        """FIXED-378 restarts a dropped session once. It now resumes rather than
        asking the server to repeat everything it had already sent."""
        server = _SplittingServer(expire_after=2)

        result = _run(workspace, server)

        assert result.ok, result.reason_code
        resumed = [headers for method, headers in server.requests if "Last-Event-ID" in headers]
        assert resumed, "the request after the drop carried no resumption point"
        assert resumed[0]["Last-Event-ID"] == "1"

    def test_a_first_request_never_claims_to_be_resuming(self, workspace: Path) -> None:
        server = _SplittingServer()

        _run(workspace, server)

        assert all("Last-Event-ID" not in headers for _m, headers in server.requests)
