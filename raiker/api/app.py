from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from raiker.api.redaction import redact_response_body
from raiker.api.routes_approvals import router as approvals_router
from raiker.api.routes_control import router as control_router
from raiker.api.routes_dashboard import router as dashboard_router
from raiker.api.routes_prompts import router as prompts_router
from raiker.api.security import (
    MaxBodySizeMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from raiker.runtime.executors.registry import ExecutorRegistry

# Paths whose responses must not be buffered/redacted by RedactionMiddleware:
# - /api/auth/session returns the owner's bearer token (must reach the client intact);
# - /api/prompts/stream is an SSE stream (buffering would break streaming; it is redacted per-chunk).
_REDACTION_EXEMPT_PATHS = frozenset({"/api/auth/session", "/api/prompts/stream"})


class RedactionMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        # Only governed JSON API responses are buffered + redacted. Everything else (the static
        # web UI: index.html, hashed JS/CSS assets) is served untouched — no buffering, and no risk
        # of the redactor mangling a bundle that happens to contain a secret-like literal.
        if not path.startswith("/api") or path in _REDACTION_EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        start_message: Message | None = None
        body = bytearray()

        async def capture(message: Message) -> None:
            nonlocal start_message
            if message["type"] == "http.response.start":
                start_message = message
                return
            if message["type"] != "http.response.body":
                await send(message)
                return
            body.extend(message.get("body", b""))
            if message.get("more_body", False):
                return
            await _emit_redacted(send, start_message, bytes(body))

        await self.app(scope, receive, capture)


async def _emit_redacted(send: Send, start_message: Message | None, raw: bytes) -> None:
    if start_message is None:
        await send({"type": "http.response.body", "body": raw, "more_body": False})
        return
    redacted = _try_redact_json_body(raw)
    out = json.dumps(redacted, default=str).encode("utf-8") if redacted is not None else raw
    # Re-serialized JSON changes byte length; recompute Content-Length or the body is truncated
    # over real HTTP (uvicorn). Other headers are preserved.
    headers: list[tuple[bytes, bytes]] = [
        (key, value)
        for (key, value) in start_message.get("headers", [])
        if key.lower() != b"content-length"
    ]
    headers.append((b"content-length", str(len(out)).encode("latin-1")))
    new_start: dict[str, Any] = {**start_message, "headers": headers}
    await send(new_start)
    await send({"type": "http.response.body", "body": out, "more_body": False})


def _try_redact_json_body(raw: bytes) -> Any | None:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    return redact_response_body(parsed)


def create_app(
    workspace_root: str | Path = ".",
    executor_registry: ExecutorRegistry | None = None,
    ui_dir: str | Path | None = None,
    *,
    rate_limit_per_minute: int = 120,
    max_body_bytes: int = 1_000_000,
    hsts: bool = False,
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
    # Transport hardening for single-user internet exposure. Added after
    # RedactionMiddleware so these wrap it (outermost = SecurityHeaders), and so
    # a rate-limit/oversize rejection still carries the security headers.
    app.add_middleware(MaxBodySizeMiddleware, max_bytes=max_body_bytes)
    app.add_middleware(RateLimitMiddleware, max_requests=rate_limit_per_minute, window_seconds=60.0)
    app.add_middleware(SecurityHeadersMiddleware, hsts=hsts)
    app.include_router(control_router)
    app.include_router(dashboard_router)
    app.include_router(prompts_router)
    app.include_router(approvals_router)
    # Serve the built local web dashboard (apps/web/dist) from the same loopback origin, so the
    # dashboard launches with one command and the SPA's relative /api paths resolve directly.
    # Mounted LAST so the /api routes above keep precedence; skipped when no build is present
    # (API-only mode is unchanged). The SPA uses hash routing, so html=True at "/" is sufficient.
    if ui_dir is not None:
        ui_path = Path(ui_dir)
        if ui_path.is_dir() and (ui_path / "index.html").is_file():
            app.mount("/", StaticFiles(directory=ui_path, html=True), name="web-ui")
    return app
