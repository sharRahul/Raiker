"""DEC-25 — how many large bodies may be in flight at once is bounded too.

The upload routes accept tens of megabytes each, and a route holds its body
while it decodes it. A cap on one body bounded nothing about five of them, so
the routes with a larger cap admit a fixed number at a time; one more is
answered 503 ``request_body_concurrency_limited`` with ``Retry-After`` before
any of it is read. Ordinary routes are not counted.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import MutableMapping
from typing import Any

from raiker.api.security import MaxBodySizeMiddleware


def _middleware(release: asyncio.Event, entered: list[str], limit: int = 2) -> MaxBodySizeMiddleware:
    async def slow_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        entered.append(str(scope["path"]))
        await release.wait()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    return MaxBodySizeMiddleware(
        slow_app,  # type: ignore[arg-type]
        max_bytes=1000,
        path_overrides={"/api/attachments": 10_000},
        max_large_bodies=limit,
    )


async def _request(
    middleware: MaxBodySizeMiddleware, path: str, method: str = "POST"
) -> tuple[int, dict[bytes, bytes], bytes]:
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"x", "more_body": False}

    async def send(message: MutableMapping[str, Any]) -> None:
        sent.append(dict(message))

    await middleware({"type": "http", "path": path, "method": method, "headers": []}, receive, send)
    start = next(m for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return int(start["status"]), dict(start.get("headers", [])), body


def test_one_upload_past_the_bound_is_refused_with_retry_after() -> None:
    async def scenario() -> None:
        release = asyncio.Event()
        entered: list[str] = []
        middleware = _middleware(release, entered)
        running = [asyncio.create_task(_request(middleware, "/api/attachments")) for _ in range(2)]
        await asyncio.sleep(0.01)
        status, headers, body = await _request(middleware, "/api/attachments")
        assert status == 503
        assert headers[b"retry-after"] == b"2"
        assert json.loads(body)["reason_code"] == "request_body_concurrency_limited"
        assert entered == ["/api/attachments", "/api/attachments"]
        release.set()
        assert [result[0] for result in await asyncio.gather(*running)] == [200, 200]

    asyncio.run(scenario())


def test_a_finished_upload_frees_its_place() -> None:
    async def scenario() -> None:
        release = asyncio.Event()
        release.set()
        middleware = _middleware(release, [], limit=1)
        for _ in range(3):
            assert (await _request(middleware, "/api/attachments"))[0] == 200

    asyncio.run(scenario())


def test_ordinary_routes_and_reads_are_not_counted() -> None:
    async def scenario() -> None:
        release = asyncio.Event()
        entered: list[str] = []
        middleware = _middleware(release, entered, limit=1)
        held = asyncio.create_task(_request(middleware, "/api/attachments"))
        await asyncio.sleep(0.01)
        others = [
            asyncio.create_task(_request(middleware, "/api/prompts")),
            asyncio.create_task(_request(middleware, "/api/attachments", method="GET")),
        ]
        await asyncio.sleep(0.01)
        assert sorted(entered) == ["/api/attachments", "/api/attachments", "/api/prompts"]
        release.set()
        assert [r[0] for r in await asyncio.gather(held, *others)] == [200, 200, 200]

    asyncio.run(scenario())
