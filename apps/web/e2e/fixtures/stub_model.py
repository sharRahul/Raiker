"""Deterministic OpenAI-compatible model for Raiker's live browser scenarios.

Only the upstream model is replaced. The API, orchestration, policy, approval,
suspension, resume, and UI paths exercised by the Playwright specs remain the
real application.
"""

from __future__ import annotations

import argparse
import json
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

MODEL_ID = "raiker-batch-stub"
MAX_BODY_BYTES = 1024 * 1024


def _tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments, separators=(",", ":"))},
    }


def _batch_for(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    if any(message.get("role") == "tool" for message in messages):
        return (
            "The policy refused that one call; the other requested work was handled separately.",
            [],
        )

    user_text = "\n".join(
        str(message.get("content", ""))
        for message in messages
        if message.get("role") == "user"
    ).lower()
    if "write one.md, two.md and three.md" in user_text:
        return (
            "I’ll prepare the three files.",
            [
                _tool_call("call_one", "write_file", {"path": "one.md", "content": "# One\n"}),
                _tool_call("call_two", "write_file", {"path": "two.md", "content": "# Two\n"}),
                _tool_call(
                    "call_three", "write_file", {"path": "three.md", "content": "# Three\n"}
                ),
            ],
        )
    if "../escape.md" in user_text and "write" in user_text:
        return (
            "I’ll inspect the path and prepare both files.",
            [
                _tool_call("call_outside", "read_file", {"path": "../escape.md"}),
                _tool_call("call_one", "write_file", {"path": "one.md", "content": "# One\n"}),
                _tool_call(
                    "call_three", "write_file", {"path": "three.md", "content": "# Three\n"}
                ),
            ],
        )
    if "../escape.md" in user_text and ("list" in user_text or "workspace" in user_text):
        return (
            "I’ll inspect both locations.",
            [
                _tool_call("call_outside", "read_file", {"path": "../escape.md"}),
                _tool_call("call_list", "list_directory", {"path": "."}),
            ],
        )
    return ("The deterministic Raiker test model received the request.", [])


def _completion(payload: dict[str, Any]) -> dict[str, Any]:
    raw_messages = payload.get("messages")
    messages = raw_messages if isinstance(raw_messages, list) else []
    content, tool_calls = _batch_for(
        [message for message in messages if isinstance(message, dict)]
    )
    finish_reason = "tool_calls" if tool_calls else "stop"
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "id": "chatcmpl-raiker-stub",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL_ID,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 24, "completion_tokens": 12, "total_tokens": 36},
    }


class _LoopbackServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:
        # Never let test prompts, tool arguments, or credentials reach logs.
        return

    def _send_json(self, status: HTTPStatus, body: dict[str, Any]) -> None:
        encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        if self.path.rstrip("/") != "/v1/models":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": {"message": "not found"}})
            return
        self._send_json(
            HTTPStatus.OK,
            {
                "object": "list",
                "data": [
                    {
                        "id": MODEL_ID,
                        "object": "model",
                        "created": 0,
                        "owned_by": "raiker-e2e",
                    }
                ],
            },
        )

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        if self.path.rstrip("/") != "/v1/chat/completions":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": {"message": "not found"}})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY_BYTES:
            self._send_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"error": {"message": "request body too large"}},
            )
            return
        try:
            raw = self.rfile.read(length)
            payload = json.loads(raw or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": {"message": "invalid json"}})
            return
        if not isinstance(payload, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": {"message": "invalid payload"}})
            return

        completion = _completion(payload)
        if not payload.get("stream"):
            self._send_json(HTTPStatus.OK, completion)
            return
        self._send_stream(completion)

    def _send_stream(self, completion: dict[str, Any]) -> None:
        message = completion["choices"][0]["message"]
        finish_reason = completion["choices"][0]["finish_reason"]
        delta: dict[str, Any] = {"role": "assistant", "content": message.get("content", "")}
        if "tool_calls" in message:
            delta["tool_calls"] = [
                {"index": index, **tool_call}
                for index, tool_call in enumerate(message["tool_calls"])
            ]
        chunks = [
            {
                "id": completion["id"],
                "object": "chat.completion.chunk",
                "created": completion["created"],
                "model": MODEL_ID,
                "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
            },
            {
                "id": completion["id"],
                "object": "chat.completion.chunk",
                "created": completion["created"],
                "model": MODEL_ID,
                "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
                "usage": completion["usage"],
            },
        ]
        body = "".join(
            f"data: {json.dumps(chunk, separators=(',', ':'))}\n\n" for chunk in chunks
        ) + "data: [DONE]\n\n"
        encoded = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(encoded)


def serve(port: int = 8811) -> None:
    """Serve the deterministic model on loopback until the process exits."""

    with _LoopbackServer(("127.0.0.1", port), _Handler) as server:
        server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", nargs="?", type=int, default=8811)
    args = parser.parse_args()
    serve(args.port)


if __name__ == "__main__":
    main()
