from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from raiker.api.redaction import redact_response_body
from raiker.api.routes_control import router as control_router
from raiker.runtime.executors.registry import ExecutorRegistry


class RedactionMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        body_chunks: list[bytes] = []
        send_wrapper = _make_send_wrapper(send, body_chunks)
        await self.app(scope, receive, send_wrapper)


def _make_send_wrapper(send: Send, body_chunks: list[bytes]) -> Send:
    async def send_wrapper(message: Message) -> None:
        if message["type"] == "http.response.body":
            chunk = message.get("body", b"")
            if chunk:
                body_chunks.append(chunk)
            merged = b"".join(body_chunks)
            body_chunks.clear()
            redacted = _try_redact_json_body(merged)
            if redacted is not None:
                new_body = json.dumps(redacted, default=str).encode("utf-8")
                await send({
                    "type": "http.response.body",
                    "body": new_body,
                    "more_body": message.get("more_body", False),
                })
                return
        await send(message)
    return send_wrapper


def _try_redact_json_body(raw: bytes) -> Any | None:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    return redact_response_body(parsed)


def create_app(
    workspace_root: str | Path = ".",
    executor_registry: ExecutorRegistry | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Raiker API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.state.workspace_root = Path(workspace_root).resolve()
    if executor_registry is not None:
        app.state.executor_registry = executor_registry
    app.add_middleware(RedactionMiddleware)
    app.include_router(control_router)
    return app
