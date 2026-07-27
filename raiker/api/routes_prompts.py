from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from raiker.api.auth import AuthMiddleware
from raiker.api.redaction import redact_response_body
from raiker.api.schemas import InterruptRequest, PromptRequest
from raiker.api.sessions import ApiSession
from raiker.contracts.ids import new_id
from raiker.contracts.models import (
    DEFAULT_MAX_TOOL_CALLS,
    AgentResponse,
    ClientMetadata,
    ContractValidationError,
    InterruptAction,
    PromptEnvelope,
    PromptOptions,
    PromptPayload,
    UserMetadata,
)
from raiker.contracts.streaming import FINAL, StreamEvent
from raiker.events.writer import EventLogWriter
from raiker.gateway.agent_gateway import AgentGateway
from raiker.runtime.authority.models import Principal, PrincipalType
from raiker.runtime.interrupts import InterruptController
from raiker.runtime.attachments import (
    DOCX_MEDIA_TYPE,
    PDF_MEDIA_TYPE,
    XLSX_MEDIA_TYPE,
    AttachmentValidationError,
    store_document,
    store_image,
)
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.filesystem import FilesystemSafetyError, resolve_writable_workspace_path
from raiker.tasks.manager import TaskManager

router = APIRouter()

WEB_UI_CLIENT = ClientMetadata(type="web_ui", name="raiker-web", version="0.0.0")
REST_CLIENT = ClientMetadata(type="rest", name="raiker-rest", version="0.0.0")
# Only these origins may be claimed over the API; both are governed identically
# and both authenticate as the single owner. Anything else falls back to web_ui.
_PROMPT_CLIENTS = {"web_ui": WEB_UI_CLIENT, "rest": REST_CLIENT}
# Work the owner can still stop. `waiting_for_approval` belongs here: the run is
# unfinished and parked on a decision, so "stop everything" must reach it too.
_ACTIVE_TASK_STATES = ("queued", "running", "paused", "waiting_for_approval")


def _ws(request: Request) -> str | Path:
    return request.app.state.workspace_root  # type: ignore[no-any-return]


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    return AuthMiddleware(_ws(request)).authenticate(request)


_MAX_ATTACHMENTS = 8


def _validated_attachments(raw: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Validate prompt attachments fail-closed before a turn starts.

    Accepted shapes: ``{"type": "path", "path": <non-empty str>}`` (workspace
    path), ``{"type": "image", "attachment_id": <non-empty str>}`` (an image
    already uploaded through POST /api/attachments), and
    ``{"type": "document", "attachment_id": <non-empty str>}`` (an uploaded text
    document). Anything else rejects the whole prompt honestly rather than
    silently dropping data. Path *safety* (workspace containment) is enforced
    later by the workspace-scoped filesystem layer during context gathering.
    """
    if not raw:
        return []
    if len(raw) > _MAX_ATTACHMENTS:
        raise ContractValidationError(f"too_many_attachments:{len(raw)}>{_MAX_ATTACHMENTS}")
    cleaned: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ContractValidationError("invalid_attachment:not_object")
        kind = entry.get("type")
        if kind == "path":
            path = entry.get("path")
            if not isinstance(path, str) or not path.strip():
                raise ContractValidationError("invalid_attachment:missing_path")
            cleaned.append({"type": "path", "path": path.strip()})
            continue
        if kind in ("image", "document"):
            # Uploaded-attachment reference: the bytes were already validated and
            # stored via POST /api/attachments; the prompt carries only the id.
            attachment_id = entry.get("attachment_id")
            if not isinstance(attachment_id, str) or not attachment_id.strip():
                raise ContractValidationError("invalid_attachment:missing_attachment_id")
            cleaned.append({"type": kind, "attachment_id": attachment_id.strip()})
            continue
        raise ContractValidationError(f"invalid_attachment_type:{kind}")
    return cleaned


def _build_envelope(body: PromptRequest, principal_id: str = "local_user") -> PromptEnvelope:
    options = PromptOptions(
        planning_mode=body.planning_mode or "auto",
        approval_mode=body.approval_mode or "interactive",
        model_profile=body.model_profile or "",
        model=body.model or "",
        max_tool_calls=(
            body.max_tool_calls if body.max_tool_calls is not None else DEFAULT_MAX_TOOL_CALLS
        ),
    )
    client = _PROMPT_CLIENTS.get(body.client_type or "web_ui", WEB_UI_CLIENT)
    return PromptEnvelope(
        request_id=new_id("req_"),
        session_id=body.session_id or new_id("sess_"),
        turn_id=new_id("turn_"),
        client=client,
        user=UserMetadata(id=principal_id),
        prompt=PromptPayload(
            text=body.text,
            attachments=_validated_attachments(body.attachments),
            metadata={"entry_command": client.type},
        ),
        options=options,
    )


def _record_attachment_refs(
    workspace: str | Path, envelope: PromptEnvelope, principal_id: str
) -> None:
    """Bind this turn's uploaded attachments to its session (BUG-07).

    The reference is what later authorizes the file inspector to show the file
    back, so it is written only for attachments this principal actually owns —
    an id naming someone else's upload stores nothing and previews nothing. The
    turn itself is unaffected either way; context gathering does its own
    owner-scoped lookup.
    """
    store = SQLiteStore(workspace)
    for entry in envelope.prompt.attachments:
        attachment_id = str(entry.get("attachment_id", "")).strip()
        if not attachment_id:
            continue
        if store.load_attachment_metadata(attachment_id, owner_principal_id=principal_id) is None:
            continue
        store.save_session_attachment_ref(
            session_id=envelope.session_id,
            attachment_id=attachment_id,
            owner_principal_id=principal_id,
            turn_id=envelope.turn_id,
        )


_GENERATED_FILE_MEDIA_TYPES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".csv": "text/csv",
    ".pdf": PDF_MEDIA_TYPE,
    ".docx": DOCX_MEDIA_TYPE,
    ".xlsx": XLSX_MEDIA_TYPE,
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def _record_generated_file_attachments(
    workspace: str | Path, envelope: PromptEnvelope, principal_id: str
) -> None:
    """Make files newly written by this chat turn available to its inspector.

    A capture entry names a governed mutation without ever containing its
    contents. Once the turn has written a *new* supported file, validate and
    copy its bytes into the owner-scoped attachment store, then bind that
    attachment to the originating session and turn. Existing files are not
    copied: an unsuccessful edit must never turn a stale workspace file into a
    chat download, and this feature is for generated outputs rather than a
    general workspace browser.
    """
    store = SQLiteStore(workspace)
    entries = store.list_checkpoint_capture_entries(session_id=envelope.session_id, limit=200)
    paths: set[str] = set()
    for entry in entries:
        if (
            entry.get("turn_id") != envelope.turn_id
            or entry.get("capability") not in {"file_write_execution", "patch_apply_execution"}
            or bool(entry.get("existed_before"))
        ):
            continue
        paths.add(str(entry.get("workspace_path", "")))

    for workspace_path in paths:
        media_type = _GENERATED_FILE_MEDIA_TYPES.get(Path(workspace_path).suffix.lower())
        if media_type is None:
            continue
        try:
            source = resolve_writable_workspace_path(workspace, workspace_path)
            if not source.is_file():
                continue
            data = source.read_bytes()
            stored = (
                store_image(store, filename=source.name, media_type=media_type, data=data, owner_principal_id=principal_id)
                if media_type.startswith("image/")
                else store_document(store, filename=source.name, media_type=media_type, data=data, owner_principal_id=principal_id)
            )
        except (AttachmentValidationError, FilesystemSafetyError, OSError):
            continue
        store.save_session_attachment_ref(
            session_id=envelope.session_id,
            attachment_id=stored.attachment_id,
            owner_principal_id=principal_id,
            turn_id=envelope.turn_id,
        )


def _invalid_response(exc: Exception) -> AgentResponse:
    return AgentResponse(
        request_id="req_invalid",
        session_id="sess_invalid",
        turn_id="turn_invalid",
        status="failed",
        message=f"Invalid prompt: {exc}",
    )


@router.post("/api/prompts")
async def submit_prompt(
    body: PromptRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, principal = _auth_data
    if body.session_id:
        existing = SQLiteStore(_ws(request)).load_session(body.session_id)
        if existing is not None and existing.get("user_id") != principal.delegated_by_user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown session")
    try:
        envelope = _build_envelope(body, session.principal_id)
    except ContractValidationError as exc:
        return _invalid_response(exc).to_dict()
    _record_attachment_refs(_ws(request), envelope, session.principal_id)
    gateway = AgentGateway(_ws(request), principal_id=session.principal_id)
    response = await gateway.submit_prompt_async(envelope)
    _record_generated_file_attachments(_ws(request), envelope, session.principal_id)
    return response.to_dict()


def _sse(event: StreamEvent) -> str:
    data = {
        "kind": event.kind,
        "text": event.text,
        "event_type": event.event_type,
        "payload": event.payload,
        "response": event.response.to_dict() if event.response is not None else None,
    }
    # Per-chunk redaction keeps the SSE stream scrubbed without buffering (the buffering
    # RedactionMiddleware is bypassed for this path so streaming works).
    return f"data: {json.dumps(redact_response_body(data), default=str)}\n\n"


@router.post("/api/prompts/stream")
async def stream_prompt(
    body: PromptRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> StreamingResponse:
    session, principal = _auth_data
    if body.session_id:
        existing = SQLiteStore(_ws(request)).load_session(body.session_id)
        if existing is not None and existing.get("user_id") != principal.delegated_by_user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown session")
    try:
        envelope = _build_envelope(body, session.principal_id)
    except ContractValidationError as exc:
        final = _invalid_response(exc)

        async def error_gen() -> AsyncIterator[str]:
            yield _sse(StreamEvent(kind=FINAL, response=final))

        return StreamingResponse(error_gen(), media_type="text/event-stream")

    _record_attachment_refs(_ws(request), envelope, session.principal_id)
    gateway = AgentGateway(_ws(request), principal_id=session.principal_id)

    async def gen() -> AsyncIterator[str]:
        async for event in gateway.astream_prompt(envelope):
            if event.kind == FINAL:
                _record_generated_file_attachments(_ws(request), envelope, session.principal_id)
            yield _sse(event)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/api/interrupts")
async def interrupts(
    body: InterruptRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    _session, principal = _auth_data
    # STOP / interrupts are human-only, like runtime-gate changes.
    if principal.principal_type != PrincipalType.HUMAN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": "human_principal_required"},
        )
    store = SQLiteStore(_ws(request))
    writer = EventLogWriter(store)
    controller = InterruptController(store, writer)
    manager = TaskManager(store, writer)
    user_id = store.principal_user_id(principal.principal_id)
    session = store.load_session(body.session_id)
    if session is None or session.get("user_id") != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"ok": False, "reason_code": "interrupt_target_not_found"})

    if body.all:
        targets = [
            t for t in store.list_tasks(session_id=body.session_id, user_id=user_id)
            if t.status in _ACTIVE_TASK_STATES
        ]
    elif body.task_id:
        one = manager.get_task(body.task_id)
        targets = [one] if one is not None and one.session_id == body.session_id and session.get("user_id") == user_id else []
    else:
        targets = []

    if body.task_id and not targets:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"ok": False, "reason_code": "interrupt_target_not_found"})
    reason = body.reason or "user requested stop"
    applied: list[dict[str, str]] = []
    for task in targets:
        action = InterruptAction(
            action_id=new_id("act_"),
            task_id=task.task_id,
            session_id=body.session_id,
            action_type=body.action_type,
            reason=reason,
            steer_text=body.steer_text,
        )
        # Governed safe-boundary interrupt: emits interrupt_received + safe_boundary_reached.
        result = controller.apply_at_safe_boundary(action)
        applied.append({"task_id": task.task_id, "result": result})

    return {"applied": applied, "safe_boundary": True}
