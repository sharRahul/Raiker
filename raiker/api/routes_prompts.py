from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from raiker.api.dependencies import authenticate as _auth
from raiker.api.dependencies import refusal, require_human
from raiker.api.dependencies import workspace_root as _ws
from raiker.api.redaction import redact_response_body
from raiker.api.routes_settings import load_composer_approval_mode
from raiker.api.schemas import InterruptRequest, PromptRequest, serialize_dto
from raiker.api.sessions import ApiSession
from raiker.api.wire.sessions import (
    CommandStopRequested,
    InterruptResult,
    StopAllResult,
    StopFailure,
    TaskInterrupted,
    TurnControl,
    TurnStopped,
    WorkInFlight,
)
from raiker.build_identity import version as raiker_version
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
    normalize_input_mode,
    normalize_prompt_surface,
)
from raiker.contracts.streaming import FINAL, StreamEvent
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.gateway.agent_gateway import AgentGateway
from raiker.models.readiness import (
    ModelNotReady,
    ModelReadinessService,
    ProviderCatalogueProbe,
)
from raiker.runtime.attachments import (
    DOCX_MEDIA_TYPE,
    PDF_MEDIA_TYPE,
    XLSX_MEDIA_TYPE,
    AttachmentValidationError,
    store_document,
    store_image,
)
from raiker.runtime.authority.models import Principal
from raiker.runtime.identity.presentation import owner_user_metadata
from raiker.runtime.interrupts import InterruptController
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager
from raiker.tools.filesystem import FilesystemSafetyError, resolve_writable_workspace_path

router = APIRouter()

# GCR-16 — a turn is recorded against the build that ran it. Both of these
# said `0.0.0` on every release, so an audit record could not tell two
# versions of Raiker apart.
WEB_UI_CLIENT = ClientMetadata(type="web_ui", name="raiker-web", version=raiker_version())
REST_CLIENT = ClientMetadata(type="rest", name="raiker-rest", version=raiker_version())
# Only these origins may be claimed over the API; both are governed identically
# and both authenticate as the single owner. Anything else falls back to web_ui.
_PROMPT_CLIENTS = {"web_ui": WEB_UI_CLIENT, "rest": REST_CLIENT}
# Work the owner can still stop. `waiting_for_approval` belongs here: the run is
# unfinished and parked on a decision, so "stop everything" must reach it too.
_ACTIVE_TASK_STATES = (
    "queued", "running", "continuing", "paused", "waiting_for_approval",
    # BUG-220 - a parent parked on its children is unfinished work, so "stop
    # everything" has to reach it. Stopping it does not stop the children; each
    # is its own row and is reached by the same sweep.
    "waiting_for_children",
)


async def _require_model_ready(
    request: Request,
    principal_id: str,
    profile_id: str | None,
    model: str | None,
) -> None:
    """BUG-238 — re-check a model whose observation aged out, rather than refuse.

    The route gate and the gateway gate have to agree, or a turn is refused here
    with `model_not_ready` and would have been admitted one layer down. Both now
    use `require_ready_async`, so an owner who set a model up once is never
    asked to set it up again merely because the TTL passed.
    """
    store = SQLiteStore(_ws(request))
    await ModelReadinessService(
        store, probe=ProviderCatalogueProbe(store)
    ).require_ready_async(
        principal_id,
        profile_id,
        model,
    )


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


def _build_envelope(
    body: PromptRequest, principal_id: str = "local_user", workspace: str | Path | None = None
) -> PromptEnvelope:
    prompt_text = body.text
    command_trigger: str | None = None
    if workspace is not None:
        from raiker.skills.service import SkillsService

        prompt_text, command_trigger = SkillsService(workspace).expand_command(
            principal_id, body.text
        )
    options = PromptOptions(
        planning_mode=body.planning_mode or "auto",
        approval_mode=(
            body.approval_mode
            if body.approval_mode is not None
            else load_composer_approval_mode(workspace, principal_id) if workspace is not None else "manual"
        ),
        model_profile=body.model_profile or "",
        model=body.model or "",
        reasoning_effort=body.reasoning_effort,
        max_tool_calls=(
            body.max_tool_calls if body.max_tool_calls is not None else DEFAULT_MAX_TOOL_CALLS
        ),
        capability_modes=body.capability_modes or {},
    )
    client = _PROMPT_CLIENTS.get(body.client_type or "web_ui", WEB_UI_CLIENT)
    metadata: dict[str, Any] = {
        "entry_command": client.type,
        "input_mode": normalize_input_mode(body.input_mode),
        "surface": normalize_prompt_surface(body.surface),
        # Carried on the turn, not looked up later: the boundary a turn
        # ran under has to be part of what the turn recorded.
        "project_id": (body.project_id or "").strip() or None,
    }
    if command_trigger is not None:
        metadata["skill_command"] = command_trigger
    return PromptEnvelope(
        request_id=new_id("req_"),
        session_id=body.session_id or new_id("sess_"),
        turn_id=new_id("turn_"),
        client=client,
        # RR-IDENTITY-01 — the authorisation key *and* the name to address the
        # owner by, resolved server-side. A turn that carries only the key is a
        # turn whose only answer to "who am I talking to" is an internal id.
        user=owner_user_metadata(
            SQLiteStore(workspace) if workspace is not None else None, principal_id
        ),
        prompt=PromptPayload(
            text=prompt_text,
            attachments=_validated_attachments(body.attachments),
            metadata=metadata,
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
    _record_generated_file_attachments_for_turn(
        workspace,
        session_id=envelope.session_id,
        turn_id=envelope.turn_id,
        principal_id=principal_id,
    )


def _record_generated_file_attachments_for_turn(
    workspace: str | Path, *, session_id: str, turn_id: str, principal_id: str
) -> None:
    """Copy this turn's newly generated files into its durable session record.

    File execution happens either before a prompt reaches its final stream event
    or later when the owner approves a parked write. Both lifecycle paths call
    this idempotent recorder so the inspector never depends on which path
    executed the file.
    """
    store = SQLiteStore(workspace)
    # The approval relay executes through the approving API session, while the
    # checkpoint retains the original conversation turn. The turn is therefore
    # the durable join key between an approved write and its Chat/Build session.
    entries = store.list_checkpoint_capture_entries(turn_id=turn_id, limit=200)
    recorded_files = {
        (str(ref["turn_id"]), str(metadata["filename"]), str(metadata["sha256"]))
        for ref in store.list_session_attachment_refs(
            session_id=session_id, owner_principal_id=principal_id
        )
        if (metadata := store.load_attachment_metadata(
            str(ref["attachment_id"]), owner_principal_id=principal_id
        )) is not None
    }
    paths: set[str] = set()
    for entry in entries:
        if (
            entry.get("turn_id") != turn_id
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
            identity = (turn_id, source.name, sha256(data).hexdigest())
            if identity in recorded_files:
                continue
            stored = (
                store_image(store, filename=source.name, media_type=media_type, data=data, owner_principal_id=principal_id)
                if media_type.startswith("image/")
                else store_document(store, filename=source.name, media_type=media_type, data=data, owner_principal_id=principal_id)
            )
        except (AttachmentValidationError, FilesystemSafetyError, OSError):
            continue
        store.save_session_attachment_ref(
            session_id=session_id,
            attachment_id=stored.attachment_id,
            owner_principal_id=principal_id,
            turn_id=turn_id,
        )
        recorded_files.add(identity)


def _invalid_response(exc: Exception) -> AgentResponse:
    return AgentResponse(
        request_id="req_invalid",
        session_id="sess_invalid",
        turn_id="turn_invalid",
        status="failed",
        message=f"Invalid prompt: {exc}",
    )


def _resolve_turn_project(
    body: PromptRequest, workspace: str | Path, principal: Principal
) -> str | None:
    """The project this turn may retrieve inside, or a 422 explaining why not.

    Authenticate first, then resolve: an id naming another account's project is
    reported exactly like an id naming nothing, so the response cannot be used
    to discover which projects exist.
    """
    requested = (body.project_id or "").strip()
    surface = (body.surface or "chat").strip()
    if surface != "build":
        if requested:
            raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "chat_has_no_project_scope")
        return None
    if not requested:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "build_requires_project")
    store = SQLiteStore(workspace)
    if store.load_project(requested, user_id=principal.delegated_by_user_id) is None:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "build_project_not_found")
    return requested


def _bind_session_project(
    workspace: str | Path, session_id: str, project_id: str | None, principal: Principal
) -> None:
    """Record Build's selected project on the session it is working in.

    Retrieval reads the boundary from the turn, so this is bookkeeping for the
    conversation list rather than an authorization step -- but a Build session
    that shows no project while running inside one would be lying about where
    its work lives.
    """
    if not project_id:
        return
    store = SQLiteStore(workspace)
    session = store.load_session(session_id)
    if session is None or str(session.get("project_id") or "") == project_id:
        return
    store.set_session_project(session_id, project_id, user_id=principal.delegated_by_user_id)


@dataclass(frozen=True)
class _PreparedTurn:
    """A turn that passed every check and is ready to hand to the gateway."""

    envelope: PromptEnvelope
    gateway: AgentGateway
    workspace: str | Path
    principal_id: str


@dataclass(frozen=True)
class _TurnRefusal:
    """Why a turn will not start, in one shape both transports can render.

    ``kind`` is ``invalid`` (the request did not validate) or ``not_ready`` (no
    model can answer it). ``response`` is the final response the turn would
    have ended with; ``detail`` is the readiness payload for ``not_ready``.
    """

    kind: str
    response: AgentResponse
    detail: dict[str, object] | None = None


async def _prepare_turn(
    body: PromptRequest, request: Request, session: ApiSession, principal: Principal
) -> _PreparedTurn | _TurnRefusal:
    """GCR-12 — everything a turn needs before its first token, done once.

    ``/api/prompts`` and ``/api/prompts/stream`` each carried their own copy of
    this sequence — session ownership, project resolution, envelope, project
    binding, model readiness, attachment references, gateway — and the copies
    had already begun to differ. The *order* is the contract: ownership first
    (a stranger's session is a 404 before anything is written), the envelope
    before the project is bound (an invalid request binds nothing), readiness
    before attachments are recorded (a refused turn records nothing).

    What stays different is only how each transport *says* a refusal, which is
    genuinely a transport question: JSON answers ``invalid`` in the body and
    ``not_ready`` as ``409``; a stream has already sent ``200`` by the time it
    could, so both arrive as its final event. Neither decides anything here.
    """
    workspace = _ws(request)
    if body.session_id:
        existing = SQLiteStore(workspace).load_session(body.session_id)
        if existing is not None and existing.get("user_id") != principal.delegated_by_user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown session")
    turn_project_id = _resolve_turn_project(body, workspace, principal)
    try:
        envelope = _build_envelope(body, session.principal_id, workspace)
    except ContractValidationError as exc:
        return _TurnRefusal(kind="invalid", response=_invalid_response(exc))
    _bind_session_project(workspace, envelope.session_id, turn_project_id, principal)
    try:
        await _require_model_ready(request, session.principal_id, body.model_profile, body.model)
    except ModelNotReady as exc:
        return _TurnRefusal(
            kind="not_ready",
            response=AgentResponse(
                request_id=envelope.request_id,
                session_id=envelope.session_id,
                turn_id=envelope.turn_id,
                status="failed",
                message=exc.readiness.summary,
            ),
            detail=exc.detail(),
        )
    _record_attachment_refs(workspace, envelope, session.principal_id)
    return _PreparedTurn(
        envelope=envelope,
        gateway=AgentGateway(workspace, principal_id=session.principal_id),
        workspace=workspace,
        principal_id=session.principal_id,
    )


@router.post("/api/prompts")
async def submit_prompt(
    body: PromptRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, principal = _auth_data
    prepared = await _prepare_turn(body, request, session, principal)
    if isinstance(prepared, _TurnRefusal):
        if prepared.kind == "not_ready":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=prepared.detail)
        refused: AgentResponse = prepared.response
        return serialize_dto(refused)
    response: AgentResponse = await prepared.gateway.submit_prompt_async(prepared.envelope)
    _record_generated_file_attachments(prepared.workspace, prepared.envelope, prepared.principal_id)
    return serialize_dto(response)


def _sse(event: StreamEvent, *, session_id: str | None = None, turn_id: str | None = None) -> str:
    data = {
        "kind": event.kind,
        "text": event.text,
        "event_type": event.event_type,
        "payload": event.payload,
        "response": event.response.to_dict() if event.response is not None else None,
        # B17/C13 — which conversation and turn this chunk belongs to, on every
        # chunk. A brand-new chat has no session id until its first turn ends, so
        # without this the owner could not stop or steer the very turn most worth
        # stopping. It names work the caller is already streaming; it exposes
        # nothing they could not already see.
        "session_id": session_id,
        "turn_id": turn_id,
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
    prepared = await _prepare_turn(body, request, session, principal)
    if isinstance(prepared, _TurnRefusal):
        refusal = prepared

        async def refusal_gen() -> AsyncIterator[str]:
            if refusal.kind == "not_ready":
                yield _sse(
                    StreamEvent(
                        kind=FINAL,
                        event_type="model_not_ready",
                        payload=refusal.detail or {},
                        response=refusal.response,
                    )
                )
            else:
                yield _sse(StreamEvent(kind=FINAL, response=refusal.response))

        return StreamingResponse(refusal_gen(), media_type="text/event-stream")

    async def gen() -> AsyncIterator[str]:
        async for event in prepared.gateway.astream_prompt(prepared.envelope):
            if event.kind == FINAL:
                _record_generated_file_attachments(
                    prepared.workspace, prepared.envelope, prepared.principal_id
                )
            yield _sse(
                event,
                session_id=prepared.envelope.session_id,
                turn_id=prepared.envelope.turn_id,
            )

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/api/interrupts")
async def interrupts(
    body: InterruptRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    _session, principal = _auth_data
    # STOP / interrupts are human-only, like runtime-gate changes.
    require_human(principal)
    store = SQLiteStore(_ws(request))
    writer = EventLogWriter(store)
    controller = InterruptController(store, writer)
    manager = TaskManager(store, writer)
    user_id = store.principal_user_id(principal.principal_id)
    session = store.load_session(body.session_id)
    if session is None or session.get("user_id") != user_id:
        raise refusal(status.HTTP_404_NOT_FOUND, "interrupt_target_not_found")

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
        raise refusal(status.HTTP_404_NOT_FOUND, "interrupt_target_not_found")
    reason = body.reason or "user requested stop"
    applied: list[TaskInterrupted] = []
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
        # DEC-12 step 7 — carried to the tasks this one delegated, within this
        # account's own sessions.
        result = controller.apply_at_safe_boundary(action, user_id=user_id)
        applied.append({"task_id": task.task_id, "result": result})

    # B17/C13 — the same governed request also reaches the *turn* streaming in
    # this conversation, which is not a task the owner scheduled and so was never
    # in `targets`. Cancelling a task could only ever stop background work; this
    # is what lets the owner stop or steer the answer they are watching.
    #
    # It stays on this endpoint rather than growing a second one because it is
    # the same decision under the same rules: human principals only, owner's own
    # session only, applied at a safe boundary and never as a force-kill.
    turn_control: TurnControl | None = None
    if not body.task_id:
        if body.action_type == "steer" and (body.steer_text or "").strip():
            queued = store.queue_turn_steer(
                body.session_id, principal.principal_id, text=(body.steer_text or "").strip()
            )
            turn_control = {"action": "steer", "queued": queued}
        elif body.action_type == "cancel":
            store.request_turn_stop(body.session_id, principal.principal_id, reason=reason)
            turn_control = {"action": "stop", "queued": 0}
        if turn_control is not None:
            writer.append(
                make_event(
                    session_id=body.session_id,
                    turn_id=None,
                    event_type="interrupt_received",
                    actor="runtime",
                    payload={
                        "target": "live_turn",
                        "action_type": body.action_type,
                        "reason": reason,
                        # The steer text itself is the owner's message to their own
                        # conversation; the audit trail keeps its size, not its words.
                        "steer_chars": len((body.steer_text or "").strip()),
                    },
                )
            )

    answer: InterruptResult = {"applied": applied, "safe_boundary": True, "turn_control": turn_control}
    return serialize_dto(answer)


# ── Stop everything (GEP-02) ─────────────────────────────────────────────────
#
# The owner's decision, 2026-09-27: the stop switch stops *all* the work in
# progress — the answer being written in Chat, a Build turn, a routine, a task,
# a command — whether or not that work leaves the machine. `/api/interrupts`
# stays what it is, one conversation's controls; this is the switch's own call.
#
# Every part is the control that already existed for that kind of work, applied
# to every instance of it the owner has: a task gets the governed safe-boundary
# interrupt, a turn gets the turn stop its own Stop button writes, a command run
# gets the stop the Commands panel sends. Nothing new is allowed to stop work,
# and nothing is force-killed that was not already.

_LIVE_COMMAND_STATES = frozenset({"queued", "starting", "running", "finalizing"})


def _owned_live_turns(
    workspace: str | Path, store: SQLiteStore, principal: Principal
) -> list[Any]:
    from raiker.runtime.live_turns import live_turns

    user_id = store.principal_user_id(principal.principal_id)
    owned: list[Any] = []
    for turn in live_turns(workspace):
        if turn.control_principal_id in {principal.principal_id, user_id}:
            owned.append(turn)
            continue
        session = store.load_session(turn.session_id)
        if session is not None and session.get("user_id") == user_id:
            owned.append(turn)
    return owned


def _live_command_runs(request: Request, principal: Principal) -> list[Any]:
    from raiker.api.routes_commands import _service as command_service

    service = command_service(request)
    return [
        run
        for run in service.store.list_runs(principal.principal_id)
        if str(run.state) in _LIVE_COMMAND_STATES
    ]


def _in_flight(request: Request, principal: Principal) -> dict[str, Any]:
    workspace = _ws(request)
    store = SQLiteStore(workspace)
    user_id = store.principal_user_id(principal.principal_id)
    active = [
        task for task in store.list_tasks(user_id=user_id) if task.status in _ACTIVE_TASK_STATES
    ]
    # Every Chat turn runs under an internal governance task (`parent_turn_id`
    # set) that the task list deliberately hides, because it *is* the turn. It is
    # stopped with the turn and counted as the turn — found live on 2026-09-28,
    # when one stopped answer was reported as "1 answer being written and 1 task".
    tasks = [task for task in active if not task.parent_turn_id]
    turn_tasks = [task for task in active if task.parent_turn_id]
    turns = _owned_live_turns(workspace, store, principal)
    try:
        commands = _live_command_runs(request, principal)
    except Exception:  # noqa: BLE001 — a command store that cannot be read is reported, not hidden
        commands = None
    return {
        "store": store,
        "tasks": tasks,
        "turn_tasks": turn_tasks,
        "turns": turns,
        "commands": commands,
    }


@router.get("/api/work-in-flight")
async def work_in_flight(
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """What the stop switch would reach, counted the way it would reach it."""
    _session, principal = _auth_data
    found = _in_flight(request, principal)
    commands = found["commands"]
    turn_ids = {turn.turn_id for turn in found["turns"]} | {
        str(task.parent_turn_id) for task in found["turn_tasks"]
    }
    answer: WorkInFlight = {
        "tasks": len(found["tasks"]),
        "turns": len(turn_ids),
        # `None` when the command store could not be read: unknown, not zero.
        "commands": None if commands is None else len(commands),
        "turn_sessions": sorted(
            {turn.session_id for turn in found["turns"]}
            | {task.session_id for task in found["turn_tasks"]}
        ),
    }
    return serialize_dto(answer)


@router.post("/api/stop-all")
async def stop_all(
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    _session, principal = _auth_data
    require_human(principal)
    found = _in_flight(request, principal)
    store: SQLiteStore = found["store"]
    writer = EventLogWriter(store)
    controller = InterruptController(store, writer)
    reason = "owner pressed stop (all work)"

    def cancel(task: Any) -> str:
        # Every active task is in the sweep already, children included, so
        # the cascade would only cancel each child twice.
        return controller.apply_at_safe_boundary(
            InterruptAction(
                action_id=new_id("act_"),
                task_id=task.task_id,
                session_id=task.session_id,
                action_type="cancel",
                reason=reason,
                steer_text=None,
            ),
            propagate=False,
        )

    tasks: list[TaskInterrupted] = [
        {"task_id": task.task_id, "result": cancel(task)} for task in found["tasks"]
    ]

    # A turn's own governance task is cancelled too — the stream checks it on
    # every event, so it is the quickest of the two stops to be seen — and it
    # is reported as the turn it belongs to, never as a second piece of work.
    turns: list[TurnStopped] = []
    reached: set[str] = set()
    for task in found["turn_tasks"]:
        cancel(task)
        reached.add(str(task.parent_turn_id))
        turns.append({"session_id": task.session_id, "turn_id": str(task.parent_turn_id)})
    for turn in found["turns"]:
        store.request_turn_stop(turn.session_id, turn.control_principal_id, reason=reason)
        writer.append(
            make_event(
                session_id=turn.session_id,
                turn_id=turn.turn_id,
                event_type="interrupt_received",
                actor="runtime",
                payload={"target": "live_turn", "action_type": "cancel", "reason": reason},
            )
        )
        if turn.turn_id not in reached:
            turns.append({"session_id": turn.session_id, "turn_id": turn.turn_id})

    commands: list[CommandStopRequested] = []
    failed: list[StopFailure] = []
    if found["commands"] is None:
        failed.append({"kind": "commands", "reason_code": "command_store_unreadable"})
    else:
        from raiker.api.routes_commands import _service as command_service

        service = command_service(request)
        for run in found["commands"]:
            try:
                stopped = service.stop(principal.principal_id, run.run_id)
            except Exception as exc:  # noqa: BLE001 — one run that will not stop must not hide the rest
                failed.append({"kind": "command", "run_id": run.run_id, "reason_code": type(exc).__name__})
                continue
            commands.append({"run_id": run.run_id, "state": str(stopped.state)})

    reached_all: StopAllResult = {
        "tasks": tasks,
        "turns": turns,
        "commands": commands,
        "failed": failed,
        "safe_boundary": True,
    }
    return serialize_dto(reached_all)
