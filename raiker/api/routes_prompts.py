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
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager

router = APIRouter()

WEB_UI_CLIENT = ClientMetadata(type="web_ui", name="raiker-web", version="0.0.0")
REST_CLIENT = ClientMetadata(type="rest", name="raiker-rest", version="0.0.0")
# Only these origins may be claimed over the API; both are governed identically
# and both authenticate as the single owner. Anything else falls back to web_ui.
_PROMPT_CLIENTS = {"web_ui": WEB_UI_CLIENT, "rest": REST_CLIENT}
_ACTIVE_TASK_STATES = ("queued", "running", "paused")


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


def _build_envelope(body: PromptRequest) -> PromptEnvelope:
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
        user=UserMetadata(),
        prompt=PromptPayload(
            text=body.text,
            attachments=_validated_attachments(body.attachments),
            metadata={"entry_command": client.type},
        ),
        options=options,
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
    try:
        envelope = _build_envelope(body)
    except ContractValidationError as exc:
        return _invalid_response(exc).to_dict()
    gateway = AgentGateway(_ws(request))
    response = await gateway.submit_prompt_async(envelope)
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
    try:
        envelope = _build_envelope(body)
    except ContractValidationError as exc:
        final = _invalid_response(exc)

        async def error_gen() -> AsyncIterator[str]:
            yield _sse(StreamEvent(kind=FINAL, response=final))

        return StreamingResponse(error_gen(), media_type="text/event-stream")

    gateway = AgentGateway(_ws(request))

    async def gen() -> AsyncIterator[str]:
        async for event in gateway.astream_prompt(envelope):
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

    if body.all:
        targets = [
            t for t in manager.list_tasks(session_id=body.session_id)
            if t.status in _ACTIVE_TASK_STATES
        ]
    elif body.task_id:
        one = manager.get_task(body.task_id)
        targets = [one] if one is not None else []
    else:
        targets = []

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
        if body.action_type == "cancel":
            # Emit the task_cancelled audit event via the task manager.
            manager.cancel_task(task.task_id, reason)
        applied.append({"task_id": task.task_id, "result": result})

    return {"applied": applied, "safe_boundary": True}
