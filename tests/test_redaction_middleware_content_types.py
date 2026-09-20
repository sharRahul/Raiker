"""What the API redactor buffers, and what it must not (GCR-44).

`RedactionMiddleware` exists to stop a credential leaving in a JSON payload. It
used to decide what to hold on to from the request *path* alone, so every
non-exempt `/api` response was copied into a `bytearray`, joined into `bytes`,
offered to `json.loads`, and — when that failed, as it always does for binary —
sent out again unchanged.

The responses that costs the most are the ones it can do least about: an
attachment download, an image, a PDF preview. Those carry a content type that
says outright they are not JSON, so the decision is now made from what the
response *is* rather than from where it came from. A JSON body is still
buffered and still redacted; nothing about the protection changes.
"""

from __future__ import annotations

import json
from typing import Any

from raiker.api.app import RedactionMiddleware

Message = dict[str, Any]


async def _drive(app: Any, scope: Message) -> list[Message]:
    """Run one ASGI request and collect exactly the messages that were sent."""
    sent: list[Message] = []

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        sent.append(message)

    await app(scope, receive, send)
    return sent


def _responder(content_type: bytes, chunks: list[bytes]) -> Any:
    async def app(scope: Any, receive: Any, send: Any) -> None:
        del scope, receive
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", content_type)],
            }
        )
        for index, chunk in enumerate(chunks):
            await send(
                {
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": index < len(chunks) - 1,
                }
            )

    return app


def _scope(path: str = "/api/attachments/att_1/preview") -> Message:
    return {"type": "http", "path": path, "method": "GET"}


def _run(app: Any, scope: Message) -> list[Message]:
    import asyncio

    return asyncio.run(_drive(app, scope))


class TestBinaryResponsesArePassedThrough:
    def test_a_pdf_preview_is_not_buffered_into_one_body(self) -> None:
        chunks = [b"%PDF-1.7\n", b"x" * 4096, b"%%EOF"]
        sent = _run(RedactionMiddleware(_responder(b"application/pdf", chunks)), _scope())
        bodies = [m for m in sent if m["type"] == "http.response.body"]
        assert [m["body"] for m in bodies] == chunks
        assert [m["more_body"] for m in bodies] == [True, True, False]

    def test_the_bytes_reach_the_client_unchanged(self) -> None:
        chunks = [b"\x89PNG\r\n\x1a\n", bytes(range(256))]
        sent = _run(RedactionMiddleware(_responder(b"image/png", chunks)), _scope())
        body = b"".join(m["body"] for m in sent if m["type"] == "http.response.body")
        assert body == b"".join(chunks)

    def test_the_declared_content_length_is_left_alone(self) -> None:
        async def app(scope: Any, receive: Any, send: Any) -> None:
            del scope, receive
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [
                        (b"content-type", b"application/octet-stream"),
                        (b"content-length", b"5"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": b"bytes", "more_body": False})

        sent = _run(RedactionMiddleware(app), _scope("/api/attachments/att_1/download"))
        headers = dict(sent[0]["headers"])
        assert headers[b"content-length"] == b"5"


class TestJsonIsStillBufferedAndRedacted:
    def test_a_json_body_still_has_its_secrets_removed(self) -> None:
        body = json.dumps({"api_key": "sk-live-0123456789abcdef"}).encode()
        sent = _run(
            RedactionMiddleware(_responder(b"application/json", [body])),
            _scope("/api/models/connections"),
        )
        payload = json.loads(b"".join(m["body"] for m in sent if m["type"] == "http.response.body"))
        assert payload["api_key"] != "sk-live-0123456789abcdef"

    def test_a_json_suffix_content_type_is_treated_as_json(self) -> None:
        body = json.dumps({"password": "hunter2"}).encode()
        sent = _run(
            RedactionMiddleware(_responder(b"application/problem+json", [body])),
            _scope("/api/models/connections"),
        )
        payload = json.loads(b"".join(m["body"] for m in sent if m["type"] == "http.response.body"))
        assert payload["password"] != "hunter2"

    def test_a_response_that_declares_no_content_type_is_still_buffered(self) -> None:
        # Unknown is not a licence to skip the redactor: the old behaviour is
        # the safe one, and it costs nothing, because the bodies this change is
        # about all say what they are.
        async def app(scope: Any, receive: Any, send: Any) -> None:
            del scope, receive
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send(
                {
                    "type": "http.response.body",
                    "body": json.dumps({"token": "abc123def456ghi789"}).encode(),
                    "more_body": False,
                }
            )

        sent = _run(RedactionMiddleware(app), _scope("/api/anything"))
        payload = json.loads(b"".join(m["body"] for m in sent if m["type"] == "http.response.body"))
        assert payload["token"] != "abc123def456ghi789"
