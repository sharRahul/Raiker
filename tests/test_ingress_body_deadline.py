"""DEC-25 — a request body has a deadline as well as a size.

A sender that dribbles bytes never crosses a byte cap, so the body must also
arrive in time: each part within an idle gap, and the whole within a budget
scaled to the route's cap. The deadline ends with the body — a streamed answer
listening for the client to go away is not timed.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import MutableMapping
from typing import Any

from raiker.api.security import MaxBodySizeMiddleware


async def _echo_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
    body = b""
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            raise RuntimeError("client went away")
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": body})


def _run(middleware: MaxBodySizeMiddleware, parts: list[tuple[float, bytes, bool]]) -> tuple[int, bytes]:
    sent: list[dict[str, Any]] = []

    async def go() -> None:
        queue = list(parts)

        async def receive() -> dict[str, Any]:
            if not queue:
                await asyncio.sleep(3600)
            delay, chunk, more = queue.pop(0)
            await asyncio.sleep(delay)
            return {"type": "http.request", "body": chunk, "more_body": more}

        async def send(message: MutableMapping[str, Any]) -> None:
            sent.append(dict(message))

        scope = {"type": "http", "path": "/api/x", "headers": []}
        await middleware(scope, receive, send)

    asyncio.run(go())
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return status, body


def test_a_body_that_arrives_in_time_reaches_the_route() -> None:
    middleware = MaxBodySizeMiddleware(_echo_app, max_bytes=1000, idle_seconds=0.5, base_seconds=1.0)  # type: ignore[arg-type]
    status, body = _run(middleware, [(0.0, b"ab", True), (0.05, b"cd", False)])
    assert (status, body) == (200, b"abcd")


def test_a_sender_that_stops_mid_body_is_answered_408() -> None:
    middleware = MaxBodySizeMiddleware(_echo_app, max_bytes=1000, idle_seconds=0.1, base_seconds=5.0)  # type: ignore[arg-type]
    status, body = _run(middleware, [(0.0, b"ab", True), (1.0, b"cd", False)])
    assert status == 408
    assert json.loads(body)["reason_code"] == "request_body_too_slow"


def test_a_dribbling_sender_runs_out_of_the_whole_body_budget() -> None:
    # Every gap is inside the idle bound; the total is not.
    middleware = MaxBodySizeMiddleware(
        _echo_app,  # type: ignore[arg-type]
        max_bytes=10,
        idle_seconds=0.2,
        base_seconds=0.3,
        min_bytes_per_second=1_000_000,
    )
    parts = [(0.1, b"a", True) for _ in range(8)] + [(0.1, b"b", False)]
    status, body = _run(middleware, parts)
    assert status == 408
    assert json.loads(body)["reason_code"] == "request_body_too_slow"


def test_waiting_for_a_disconnect_after_the_body_is_not_timed() -> None:
    seen: list[str] = []

    async def listening_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        await receive()  # the whole body, in one part
        try:
            await asyncio.wait_for(receive(), timeout=0.3)
        except TimeoutError:
            seen.append("still listening")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = MaxBodySizeMiddleware(listening_app, max_bytes=1000, idle_seconds=0.05, base_seconds=0.05)  # type: ignore[arg-type]
    status, _ = _run(middleware, [(0.0, b"x", False)])
    assert status == 200
    assert seen == ["still listening"]


def test_an_oversized_body_is_still_413() -> None:
    middleware = MaxBodySizeMiddleware(_echo_app, max_bytes=3)  # type: ignore[arg-type]
    status, body = _run(middleware, [(0.0, b"abcd", False)])
    assert status == 413
    assert json.loads(body)["reason_code"] == "request_body_too_large"
