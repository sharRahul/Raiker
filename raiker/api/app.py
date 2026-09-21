from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.routing import Mount
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from raiker.api.instance_runtime import InstanceRuntime
from raiker.api.redaction import redact_response_body
from raiker.api.routes_approvals import router as approvals_router
from raiker.api.routes_attachments import router as attachments_router
from raiker.api.routes_auth import router as auth_router
from raiker.api.routes_channels import router as channels_router
from raiker.api.routes_code_files import router as code_files_router
from raiker.api.routes_commands import router as commands_router
from raiker.api.routes_connectors import router as connectors_router
from raiker.api.routes_context import router as context_router
from raiker.api.routes_control import router as control_router
from raiker.api.routes_dashboard import router as dashboard_router
from raiker.api.routes_egress import router as egress_router
from raiker.api.routes_guide import router as guide_router
from raiker.api.routes_host import router as host_router
from raiker.api.routes_images import router as images_router
from raiker.api.routes_instances import router as instances_router
from raiker.api.routes_knowledge_files import router as knowledge_files_router
from raiker.api.routes_language import router as language_router
from raiker.api.routes_memory import router as memory_router
from raiker.api.routes_models import router as models_router
from raiker.api.routes_project_roots import router as project_roots_router
from raiker.api.routes_prompts import router as prompts_router
from raiker.api.routes_settings import router as settings_router
from raiker.api.routes_setup import router as setup_router
from raiker.api.routes_skills import router as skills_router
from raiker.api.routes_speech import router as speech_router
from raiker.api.routes_tray import router as tray_router
from raiker.api.routes_updates import router as updates_router
from raiker.api.routes_vault import router as vault_router
from raiker.api.security import (
    MaxBodySizeMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    StaticCacheMiddleware,
)
from raiker.build_identity import version as raiker_version
from raiker.control.knowledge_scope import MAX_KNOWLEDGE_UPLOAD_BYTES
from raiker.models.speech_runtime import MAX_AUDIO_BYTES as MAX_SPEECH_AUDIO_BYTES
from raiker.models.transport import close_provider_clients
from raiker.runtime.attachments import MAX_ATTACHMENT_BYTES
from raiker.runtime.executors.registry import ExecutorRegistry
from raiker.skills.package import MAX_BUNDLE_BYTES as MAX_SKILL_BUNDLE_BYTES
from raiker.storage.internal_paths import display_path, internal_io_path
from raiker.storage.sqlite import StoreUnavailableError
from raiker.tasks.wakeup import SchedulerWakeup

_LOG = logging.getLogger(__name__)

# Paths whose responses must not be buffered/redacted by RedactionMiddleware:
# - /api/auth/session returns the owner's bearer token (must reach the client intact);
# - /api/prompts/stream is an SSE stream (buffering would break streaming; it is redacted per-chunk);
# - /api/host/paths returns filesystem paths, which the redactor cannot tell from
#   credentials (BUG-268).
_REDACTION_EXEMPT_PATHS = frozenset(
    {
        "/api/auth/session",
        "/api/auth/register",
        "/api/auth/login",
        "/api/auth/mfa/verify",
        "/api/auth/mfa/enroll",
        "/api/auth/elevate",
        "/api/prompts/stream",
        "/api/tray/session",
        # BUG-268 — the folder picker's listing. A path segment is a
        # high-entropy string with no structure the redactor can distinguish
        # from a token, so a perfectly ordinary directory came back as
        # `/[REDACTED_SECRET]` and the picker handed that to the field. Linux CI
        # found it because its temporary directories look exactly like this;
        # every owner with a hashed or GUID-named folder would have found it too.
        #
        # Exempting is right rather than merely convenient. The route returns
        # directory *names* the owner explicitly asked to browse, on a
        # loopback-only, owner-authenticated read — the same information their
        # file manager shows them. It reads no file content, so there is nothing
        # here for the redactor to protect: its job is to stop a credential
        # leaking out of a payload, not to censor the owner's own directory
        # tree back to them.
        "/api/host/paths",
        # BUG-256 — a dictated transcript, on its way back to the composer the
        # owner dictated it into. It is their own words, produced by a runtime on
        # their own machine, and it goes nowhere else. Passing it through the
        # secret redactor could only turn a sentence into `[REDACTED_SECRET]` in
        # their draft — the exact failure BUG-268 found on the folder picker.
        "/api/speech/transcribe",
    }
)


def _is_project_export_request(scope: Scope, path: str) -> bool:
    parts = path.split("/")
    return (
        scope.get("method") == "POST"
        and len(parts) == 5
        and parts[1:3] == ["api", "projects"]
        and bool(parts[3])
        and parts[4] == "export"
    )


def _is_session_export_request(scope: Scope, path: str) -> bool:
    """BUG-22 — a rendered transcript is a document, not a JSON body.

    It is exempted from the buffering redactor for the same reason the project
    export is: HTML, Markdown and PDF are not JSON, so passing them through the
    JSON redactor achieves nothing and only risks mangling bytes. The transcript
    is redacted at the point it is *built* instead
    (``raiker.sessions.transcript``), which is stricter — the redaction is
    applied to message text before any rendering, and the manifest route states
    the policy to the owner before the file exists.
    """
    parts = path.split("/")
    return (
        scope.get("method") == "POST"
        and len(parts) == 5
        and parts[1:3] == ["api", "sessions"]
        and bool(parts[3])
        and parts[4] == "export"
    )


def _carries_json(start_message: Message) -> bool:
    """Whether this response is something the JSON redactor can act on.

    GCR-44 — the middleware used to decide what to buffer from the *path*
    alone, so a PDF preview and an image or attachment download were each
    copied into a `bytearray`, joined into `bytes`, offered to `json.loads`,
    and then sent out again unchanged. Binary bytes cannot be JSON-redacted, so
    every one of those copies was work that could not change the answer, on the
    largest bodies the product serves.

    A content type Raiker can see is not JSON is therefore streamed straight
    through. A response that declares no content type at all is still buffered:
    the old behaviour is the safe one where the answer is unknown, and it costs
    nothing, because the bodies this is about all declare what they are.
    """
    for key, value in start_message.get("headers", []):
        if key.lower() != b"content-type":
            continue
        media_type = value.split(b";", 1)[0].strip().lower()
        return media_type.endswith((b"/json", b"+json"))
    return True


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
        if (
            not path.startswith("/api")
            or path in _REDACTION_EXEMPT_PATHS
            or _is_project_export_request(scope, path)
            or _is_session_export_request(scope, path)
        ):
            await self.app(scope, receive, send)
            return

        start_message: Message | None = None
        body = bytearray()
        passing_through = False

        async def capture(message: Message) -> None:
            nonlocal start_message, passing_through
            if message["type"] == "http.response.start":
                if _carries_json(message):
                    start_message = message
                    return
                # GCR-44 — nothing here for the redactor to do, so the bytes go
                # out as they arrive: no buffer, no copy, and streaming
                # semantics preserved for the routes that have them.
                passing_through = True
                await send(message)
                return
            if message["type"] != "http.response.body" or passing_through:
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


def _instances_registry(root: Path) -> Path:
    return internal_io_path(root / ".raiker" / "instances.json")


#: GCR-09 — instance creation is serialized here rather than left to whichever
#: threadpool worker FastAPI handed the request to. Two concurrent creates used
#: to read ``instances.json``, each append their own name, and each write the
#: whole list back: the second write lost the first name, and a reader arriving
#: between the two saw a truncated file. Creation is rare and cheap, so one
#: process-wide lock costs nothing and removes the class.
_INSTANCE_LOCK = threading.Lock()


def _stored_instance_names(root: Path) -> list[str]:
    try:
        raw = json.loads(_instances_registry(root).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    return [name for name in raw if isinstance(name, str) and name]


def _write_instance_names(root: Path, names: list[str]) -> None:
    """Publish the registry atomically, so no reader ever sees half of it.

    GCR-09 — ``write_text`` truncates and then writes. A reader that opened the
    file in between got an empty or partial document and concluded the host had
    no instances, which on the next boot means none of them are mounted. Write a
    neighbouring temporary file and rename it: on every platform Raiker supports
    that replacement is atomic, so the registry is either the old list or the new
    one.
    """
    registry = _instances_registry(root)
    registry.parent.mkdir(parents=True, exist_ok=True)
    staging = registry.with_name(f"{registry.name}.{os.getpid()}.tmp")
    try:
        staging.write_text(json.dumps(names), encoding="utf-8")
        os.replace(staging, registry)
    finally:
        with suppress(OSError):
            staging.unlink()


def _mount_instance(app: FastAPI, name: str, workspace: Path) -> FastAPI | None:
    """Publish one instance's ASGI app under ``/instances/<name>``.

    Returns the child application, or ``None`` when the route was already
    published. The caller needs it: routing is only half of an instance, and the
    other half is the :class:`InstanceRuntime` the root lifespan starts over it.
    """
    instances: dict[str, FastAPI] = app.state.instance_apps
    if name in instances:
        return None
    if any(getattr(route, "path", "") == f"/instances/{name}" for route in app.router.routes):
        return None
    ui_dir = getattr(app.state, "instance_ui_dir", None)
    instance = create_app(
        workspace,
        ui_dir=ui_dir,
        loopback_only=bool(getattr(app.state, "loopback_only", True)),
    )
    route = Mount(f"/instances/{name}", app=instance, name=f"instance-{name}")
    static_index = next(
        (
            index
            for index, item in enumerate(app.router.routes)
            if getattr(item, "name", "") == "web-ui"
        ),
        len(app.router.routes),
    )
    app.router.routes.insert(static_index, route)
    instances[name] = instance
    return instance


async def create_and_mount_instance(
    app: FastAPI,
    name: str,
    root: Path,
    *,
    register_account: Callable[[Path], None] | None = None,
) -> Path:
    """Create one isolated workspace and mount its independent ASGI app.

    GCR-08 — this used to create the directory, publish the registry entry and
    mount the route, and only then let the route try to register the first
    account. A registration that failed returned an error and left all three
    behind, so the retry the owner was invited to make answered
    ``instance_already_exists`` about an instance that had never worked. The
    account is now created in the staged workspace *before* anything is
    published, and a failure at any point removes the staged directory and
    re-raises: an instance either exists completely or does not exist at all.
    """
    internal_workspace = internal_io_path(root / ".raiker" / "instances" / name)
    workspace = Path(display_path(internal_workspace))
    loop = asyncio.get_running_loop()

    def staged() -> Path:
        # GCR-09 — the whole create/publish sequence under one lock, so two
        # requests cannot both find the directory absent and both create it.
        with _INSTANCE_LOCK:
            if internal_workspace.exists() or name in app.state.instance_apps:
                raise FileExistsError(name)
            internal_workspace.mkdir(parents=True)
            try:
                if register_account is not None:
                    register_account(workspace)
            except BaseException:
                # Nothing has been published yet, so the rollback is the staged
                # directory and nothing else.
                shutil.rmtree(internal_workspace, ignore_errors=True)
                raise
            _write_instance_names(root, [*_stored_instance_names(root), name])
        return workspace

    # The staging above is filesystem and SQLCipher work; the publication below
    # mutates ``app.router.routes`` and starts asyncio tasks. GCR-09 asks for the
    # second to happen on the event loop that serves requests, and this function
    # is a coroutine, so it already does.
    await loop.run_in_executor(None, staged)
    instance = _mount_instance(app, name, workspace)
    if instance is not None and getattr(app.state, "runtime_started", False):
        # GCR-07 — an instance created while the host is already running needs
        # its background services now, not at the next restart.
        runtime = InstanceRuntime(instance, name=name)
        app.state.instance_runtimes[name] = runtime
        await runtime.start()
    return workspace


def create_app(
    workspace_root: str | Path = ".",
    executor_registry: ExecutorRegistry | None = None,
    ui_dir: str | Path | None = None,
    *,
    rate_limit_per_minute: int = 120,
    max_body_bytes: int = 1_000_000,
    hsts: bool = False,
    tray_bootstrap_secret: str | None = None,
    loopback_only: bool = True,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Start and stop the background work of this workspace *and its instances*.

        GCR-07 — Starlette runs a lifespan for the top-level application only, so
        the child app mounted at ``/instances/<name>`` never entered its own. A
        secondary instance therefore served requests with no task tick, no
        approval-continuation worker, no telemetry cadence and no attached-root
        watcher. Mounting is routing; the lifecycle belongs to whoever owns the
        process, which is this application. Each instance still gets its own
        :class:`InstanceRuntime` over its own workspace — nothing is shared
        between them but the moment they start and stop.
        """
        runtimes = [InstanceRuntime(app)]
        for name, instance in sorted(getattr(app.state, "instance_apps", {}).items()):
            runtimes.append(InstanceRuntime(instance, name=name))
        app.state.instance_runtimes = {runtime.name: runtime for runtime in runtimes}
        app.state.runtime_started = True
        for runtime in runtimes:
            await runtime.start()
        try:
            yield
        finally:
            app.state.runtime_started = False
            # Newest first, so an instance mounted during the run is stopped
            # before the workspace that holds it.
            for runtime in reversed(list(app.state.instance_runtimes.values())):
                with suppress(Exception):
                    await runtime.aclose()
            app.state.instance_runtimes = {}
            # GCR-14 — the provider connections this process kept open, closed
            # once and after every workspace has stopped using them rather than
            # per instance: the pool is keyed by endpoint, and two instances
            # talking to one provider share a socket and no credential.
            with suppress(Exception):
                await close_provider_clients()

    app = FastAPI(
        title="Raiker API",
        # GCR-16 — the declared API version is this build's identity rather
        # than a fifth independent number. A client reading
        # ``/api/openapi.json`` and an owner reading Settings now see the
        # same release.
        version=raiker_version(),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.workspace_root = Path(workspace_root).resolve()
    app.state.tray_bootstrap_digest = (
        hashlib.sha256(tray_bootstrap_secret.encode()).hexdigest()
        if tray_bootstrap_secret is not None
        else None
    )
    # A fresh owner may spend as long as needed in setup before the native tray
    # can mint its host-control-only session. The secret is random, loopback-only
    # and one-time, so validity ends on first use or process exit rather than an
    # arbitrary wizard timer.
    app.state.tray_bootstrap_expires = float("inf") if tray_bootstrap_secret else 0.0
    app.state.tray_bootstrap_used = False
    # BUG-39 — created here rather than in the lifespan so a route can nudge the
    # scheduler even in the tests and embedded hosts that never start one. With
    # no worker waiting the nudge is simply a set flag nobody reads, which costs
    # nothing and keeps the resolve path free of "is the host running?" branches.
    app.state.scheduler_wakeup = SchedulerWakeup()
    app.state.loopback_only = loopback_only
    from raiker.models.local_runtime import ManagedLlamaRuntime
    from raiker.models.mlx_runtime import ManagedMlxRuntime

    app.state.managed_llama_runtime = ManagedLlamaRuntime()
    app.state.managed_mlx_runtime = ManagedMlxRuntime()
    app.state.instance_ui_dir = Path(ui_dir) if ui_dir is not None else None
    # GCR-07 — the child applications this one mounts, and the background
    # services this one runs for them. Routing lives in ``app.router.routes``;
    # these two say who owns the lifecycle of what is behind each route.
    app.state.instance_apps = {}
    app.state.instance_runtimes = {}
    app.state.runtime_started = False
    # Boot key material: ensure the internal app key exists (encrypts MFA seeds)
    # and load the connector vault key-file into the environment when the env var
    # is unset. The vault key remains fail-closed if neither is present.
    from raiker.auth.app_key import ensure_app_key

    ensure_app_key(app.state.workspace_root)
    if executor_registry is not None:
        app.state.executor_registry = executor_registry

    # BUG-86 — a store that will not open is a named condition, not a generic
    # failure. Without this the platform refusing SQLCipher's locked pages
    # reached the client as a bare 500, and the lock screen could only say
    # "verification failed" while its own status strip called the runtime
    # operational. 503 plus a reason code lets both say the same true thing.
    @app.exception_handler(StoreUnavailableError)
    async def _store_unavailable(  # pyright: ignore[reportUnusedFunction]
        _request: Request, exc: StoreUnavailableError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"ok": False, "reason_code": exc.reason, "detail": exc.detail},
        )

    app.add_middleware(RedactionMiddleware)
    # Transport hardening for single-user internet exposure. Added after
    # RedactionMiddleware so these wrap it (outermost = SecurityHeaders), and so
    # a rate-limit/oversize rejection still carries the security headers.
    # The attachment-upload route alone accepts a larger (still hard-capped)
    # body: a base64-encoded attachment up to the store's largest cap (images
    # 5 MB, documents 32 MB). Every other route keeps the tight default.
    app.add_middleware(
        MaxBodySizeMiddleware,
        max_bytes=max_body_bytes,
        path_overrides={
            "/api/attachments": (MAX_ATTACHMENT_BYTES * 4) // 3 + 4096,
            # A skill upload is a base64 `*.skill` archive, capped far tighter
            # than an attachment (2 MB of bundle) but still above the default.
            "/api/skills": (MAX_SKILL_BUNDLE_BYTES * 4) // 3 + 4096,
            # A Knowledge Map upload is one base64 text document, capped at the
            # service's own 5 MB before it is written anywhere.
            "/api/brain/sources/upload": (MAX_KNOWLEDGE_UPLOAD_BYTES * 4) // 3 + 4096,
            # BUG-256 — one dictated clip, as raw 16 kHz mono PCM rather than
            # base64, capped by the speech runtime's own limit. The default body
            # size would have cut a dictation off after about thirty seconds.
            "/api/speech/transcribe": MAX_SPEECH_AUDIO_BYTES + 8192,
        },
    )
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=rate_limit_per_minute,
        window_seconds=60.0,
        loopback_only=loopback_only,
    )
    app.add_middleware(SecurityHeadersMiddleware, hsts=hsts)
    app.include_router(auth_router)
    app.include_router(instances_router)
    app.include_router(vault_router)
    app.include_router(settings_router)
    app.include_router(speech_router)
    app.include_router(control_router)
    app.include_router(host_router)
    app.include_router(updates_router)
    app.include_router(dashboard_router)
    app.include_router(context_router)
    app.include_router(images_router)
    app.include_router(knowledge_files_router)
    app.include_router(project_roots_router)
    app.include_router(code_files_router)
    app.include_router(memory_router)
    app.include_router(models_router)
    app.include_router(setup_router)
    app.include_router(tray_router)
    app.include_router(prompts_router)
    app.include_router(attachments_router)
    app.include_router(approvals_router)
    app.include_router(channels_router)
    app.include_router(commands_router)
    app.include_router(connectors_router)
    app.include_router(skills_router)
    app.include_router(language_router)
    app.include_router(egress_router)
    app.include_router(guide_router)
    # Serve the built local web dashboard (web/dist) from the same loopback origin, so the
    # dashboard launches with one command and the SPA's relative /api paths resolve directly.
    # Mounted LAST so the /api routes above keep precedence; skipped when no build is present
    # (API-only mode is unchanged). The SPA uses hash routing, so html=True at "/" is sufficient.
    # StaticCacheMiddleware sets Cache-Control so a rebuilt index.html is always revalidated
    # (the HTML shell must not be heuristically cached, or the browser keeps loading the old
    # hashed JS bundle after a rebuild).
    if ui_dir is not None:
        ui_path = Path(ui_dir)
        if ui_path.is_dir() and (ui_path / "index.html").is_file():
            app.mount(
                "/", StaticCacheMiddleware(StaticFiles(directory=ui_path, html=True)), name="web-ui"
            )
    for instance_name in _stored_instance_names(app.state.workspace_root):
        workspace = app.state.workspace_root / ".raiker" / "instances" / instance_name
        if workspace.is_dir():
            _mount_instance(app, instance_name, workspace)
    return app
