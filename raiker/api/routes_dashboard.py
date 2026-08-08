from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import FileResponse, Response

from raiker.api.auth import AuthMiddleware
from raiker.api.routes_instances import _require_loopback
from raiker.api.schemas import (
    AuthSessionRequest,
    BrainSourceRequest,
    BreachCheckRequest,
    BulkDeleteSessionsRequest,
    ConnectCodeRepoRequest,
    ContainMcpServerRequest,
    CreateMcpServerRequest,
    CreateProjectRequest,
    CreateRemoteMcpServerRequest,
    ExportSessionRequest,
    ModelConnectionRequest,
    ModelPriceRequest,
    MoveProjectRequest,
    RenameMcpServerRequest,
    RenameSessionRequest,
    SaveProjectContextRequest,
    SelectCodeRepoRequest,
    SelectProjectRequest,
    SessionCommandGrantRequest,
    SetModelAdvisorRequest,
    SetModelFallbackRequest,
    SetModelSelectionRequest,
    SetSessionPinnedRequest,
    SetSessionProjectRequest,
    SetSessionTagsRequest,
    TaskCreateRequest,
    serialize_dto,
)
from raiker.api.sessions import ApiSession
from raiker.auth.vault_key_file import ensure_vault_key
from raiker.control.dashboard import AuthSessionView, DashboardService
from raiker.control.web_read_models import WebReadModels
from raiker.models.connections import clear_model_connection, put_model_connection
from raiker.models.factory import ModelProviderFactory
from raiker.models.policy_state import provider_runtime_policy_from_gates
from raiker.models.registry import ModelProfileRegistry
from raiker.runtime.authority.models import Principal
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()


def _service(request: Request) -> DashboardService:
    ws: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    return DashboardService(ws)


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    ws: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    return AuthMiddleware(ws).authenticate(request)


def _ws(request: Request) -> str | Path:
    ws: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    return ws


@router.put("/api/sessions/{session_id}/command-grant")
def put_session_command_grant(
    session_id: str,
    body: SessionCommandGrantRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, object]:
    """Owner-defined, expiry-bound command prefixes for one conversation."""
    from datetime import UTC, datetime, timedelta

    session, _principal = auth_data
    store = SQLiteStore(request.app.state.workspace_root)
    row = store.load_session(session_id)
    user_id = store.principal_user_id(session.principal_id)
    if row is None or row.get("user_id") not in {None, user_id}:
        raise HTTPException(status_code=404, detail="Unknown session")
    commands = [
        [str(part) for part in command]
        for command in body.commands[:20]
        if command and len(command) <= 20 and all(str(part).strip() for part in command)
    ]
    if (
        not commands
        or body.timeout_seconds not in range(1, 601)
        or body.ttl_minutes not in range(1, 1441)
    ):
        raise HTTPException(status_code=400, detail={"reason_code": "invalid_command_grant"})
    expires_at = (datetime.now(UTC) + timedelta(minutes=body.ttl_minutes)).isoformat()
    store.put_session_command_grant(
        session_id=session_id,
        principal_id=session.principal_id,
        commands=commands,
        timeout_seconds=body.timeout_seconds,
        expires_at=expires_at,
    )
    return {
        "session_id": session_id,
        "commands": commands,
        "expires_at": expires_at,
        "revocable": True,
    }


@router.delete("/api/sessions/{session_id}/command-grant")
def revoke_session_command_grant(
    session_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, object]:
    session, _principal = auth_data
    store = SQLiteStore(request.app.state.workspace_root)
    row = store.load_session(session_id)
    user_id = store.principal_user_id(session.principal_id)
    if row is None or row.get("user_id") not in {None, user_id}:
        raise HTTPException(status_code=404, detail="Unknown session")
    store.revoke_session_command_grant(
        session_id=session_id, principal_id=session.principal_id
    )
    return {"session_id": session_id, "revoked": True}


# ── Auth: first-run local token mint ──────────────────────────────────────────
# Loopback-only, human-owner bootstrap. Available ONLY before the first lock-screen
# account is registered; once any account exists, this fails closed and callers
# must authenticate through /api/auth/login (+ MFA). This preserves the owner
# bootstrap path without leaving an unauthenticated entry to a configured system.
@router.post("/api/auth/session")
async def mint_session(body: AuthSessionRequest, request: Request) -> dict[str, Any]:
    from raiker.storage.sqlite import SQLiteStore

    _require_loopback(request)
    ws: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    if SQLiteStore(ws).list_accounts():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": "login_required"},
        )
    service = _service(request)
    result = service.mint_owner_session(body.as_principal)
    if not isinstance(result, AuthSessionView):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return serialize_dto(result)


# ── Read-only governed views (Bearer required) ────────────────────────────────
@router.get("/api/sessions")
async def list_sessions(
    request: Request,
    limit: int = 50,
    project_id: str | None = None,
    include_archived: bool = False,
    origin: str | None = None,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    """List the authenticated account's sessions.

    Defaults to active sessions only; ``include_archived=true`` also returns the
    caller's archived sessions. ``origin=chat`` narrows the list to conversations
    the owner typed, leaving out the server-owned sessions task runs execute in
    (BUG-10); omitting it lists every session. Listing is always owner-scoped —
    neither flag ever widens visibility beyond the caller's own sessions.
    """
    user_id = auth_data[1].delegated_by_user_id
    return serialize_dto(
        _service(request).list_sessions(
            limit=limit,
            project_id=project_id,
            user_id=user_id,
            include_archived=include_archived,
            origin=origin,
        )
    )


@router.get("/api/mcp/servers")
async def list_mcp_servers(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    """List the authenticated principal's local MCP server profiles.

    Owner-scoped by the acting principal (the creator) — an account never sees
    another account's servers.
    """
    return serialize_dto(_service(request).list_mcp_servers(auth_data[0].principal_id))


@router.get("/api/mcp/agent-access")
async def get_mcp_agent_access(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Whether this owner's connected MCP tools can actually be called in a turn.

    Two owner controls stand between a connected server and the model — the
    capability gate and the decision mode — and until now the MCP page reported
    only the handshake. A server could read `connected · 2 tool(s)` while every
    call was withheld, which is a claim the product could not keep.
    """
    from raiker.tools.mcp_tools import mcp_agent_access

    principal_id = auth_data[0].principal_id
    return mcp_agent_access(_ws(request), SQLiteStore(_ws(request)), principal_id)


@router.get("/api/sessions/{session_id}/plan")
async def get_session_plan(
    session_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """The agent's standing plan for one conversation (B6), or an empty plan.

    Owner-scoped: the row is keyed by (session, principal), so one account can
    never read another's plan. Read-only — a plan is written by the model
    through the governed `update_plan` tool, never by this surface.
    """
    from raiker.runtime.agent_plan import load_plan

    principal_id = auth_data[0].principal_id
    plan = load_plan(SQLiteStore(_ws(request)), session_id, principal_id)
    return plan if plan is not None else {"session_id": session_id, "steps": []}


def _mcp_result(result: Any) -> dict[str, Any]:
    """Map a ControlResult onto an HTTP response, translating the governed
    reason into a status: 422 for invalid input, 403 for a disabled gate /
    authorization / ownership failure."""
    if result.ok:
        return {"ok": True, **result.data}
    reason = result.reason_code or ""
    if (
        reason.startswith("mcp_invalid_server_name")
        or reason.startswith("mcp_remote_invalid_endpoint")
        or reason.startswith("invalid")
    ):
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
    else:
        code = status.HTTP_403_FORBIDDEN
    raise HTTPException(status_code=code, detail={"ok": False, "reason_code": result.reason_code})


@router.post("/api/mcp/servers")
async def create_mcp_server(
    body: CreateMcpServerRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Build a local stdio MCP server from a reviewed template.

    Runs through the governed ``mcp_builder_runtime`` capability — the gate,
    policy, decision mode, and audit event all apply. A disabled gate returns
    403 with ``disabled_by_capability_gate`` so the client can point the owner
    at Capabilities rather than silently failing.
    """
    return _mcp_result(
        _service(request).create_mcp_server(auth_data[0].principal_id, body.name, body.template)
    )


@router.post("/api/mcp/servers/remote")
async def create_remote_mcp_server(
    body: CreateRemoteMcpServerRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Add a remote (HTTP) MCP connection (owner-added, monitored — not
    allowlist-blocked). The owner token is never stored; ``auth_ref`` names the
    env var that holds it. Test-connect (governed) makes the actual reach."""
    return _mcp_result(
        _service(request).create_remote_mcp_server(
            auth_data[0].principal_id, body.name, body.endpoint_url, body.auth_ref
        )
    )


@router.post("/api/mcp/servers/{server_id}/connect")
async def connect_mcp_server(
    server_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Test-connect one stored server: run the governed stdio handshake and
    persist the discovered tool names. Owner-scoped."""
    return _mcp_result(
        _service(request).connect_mcp_server(auth_data[0].principal_id, server_id)
    )


@router.put("/api/mcp/servers/{server_id}")
async def rename_mcp_server(
    server_id: str,
    body: RenameMcpServerRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Rename one owner-scoped MCP server profile (human-only)."""
    return _mcp_result(
        _service(request).rename_mcp_server(auth_data[0].principal_id, server_id, body.name)
    )


@router.delete("/api/mcp/servers/{server_id}")
async def delete_mcp_server(
    server_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Delete one owner-scoped MCP server profile and its generated template
    file (human-only)."""
    return _mcp_result(
        _service(request).delete_mcp_server(auth_data[0].principal_id, server_id)
    )


# ── Containment: kill switch + revocable pause + findings/notifications ───────
@router.post("/api/mcp/servers/{server_id}/pause")
async def pause_mcp_server(
    server_id: str,
    request: Request,
    body: ContainMcpServerRequest | None = None,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Owner's one-call stop: pause a monitored connection (revocable). Refuses
    further sessions until resumed. Human-only, owner-scoped."""
    reason = body.reason if body is not None else None
    return _mcp_result(
        _service(request).pause_mcp_server(auth_data[0].principal_id, server_id, reason)
    )


@router.post("/api/mcp/servers/{server_id}/resume")
async def resume_mcp_server(
    server_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Revoke containment: resume a paused/killed connection back to active.
    Human-only, owner-scoped."""
    return _mcp_result(
        _service(request).resume_mcp_server(auth_data[0].principal_id, server_id)
    )


@router.post("/api/mcp/servers/{server_id}/kill")
async def kill_mcp_server(
    server_id: str,
    request: Request,
    body: ContainMcpServerRequest | None = None,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Instant kill switch: refuse all sessions for a connection (revocable via
    resume). Human-only, owner-scoped."""
    reason = body.reason if body is not None else None
    return _mcp_result(
        _service(request).kill_mcp_server(auth_data[0].principal_id, server_id, reason)
    )


@router.get("/api/mcp/servers/{server_id}/findings")
async def list_mcp_findings(
    server_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    """Owner-scoped redacted findings for one connection (newest first)."""
    return serialize_dto(
        _service(request).list_mcp_findings(auth_data[0].principal_id, server_id)
    )


@router.get("/api/mcp/servers/{server_id}/sessions")
async def list_mcp_sessions(
    server_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    """Owner-scoped, redacted recent monitor sessions for one connection."""
    return serialize_dto(
        _service(request).list_mcp_sessions(auth_data[0].principal_id, server_id)
    )


@router.get("/api/notifications")
async def list_notifications(
    request: Request,
    unread_only: bool = False,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    """Owner-scoped notifications (newest first). ``unread_only`` filters to the
    unread ones."""
    return serialize_dto(
        _service(request).list_notifications(auth_data[0].principal_id, unread_only)
    )


@router.post("/api/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Owner-scoped mark-as-read for one notification."""
    return _mcp_result(
        _service(request).mark_notification_read(notification_id, auth_data[0].principal_id)
    )


@router.get("/api/security/credentials")
async def list_security_credentials(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> list[dict[str, Any]]:
    return serialize_dto(_service(request).list_security_credentials(auth_data[0].principal_id))


@router.post("/api/security/credentials/{provider}/verify")
async def verify_security_credential(
    provider: str, request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> dict[str, Any]:
    try:
        return serialize_dto(_service(request).verify_security_credential(auth_data[0].principal_id, provider))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from None


@router.get("/api/security/findings")
async def list_security_findings(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> list[dict[str, Any]]:
    return serialize_dto(_service(request).list_security_findings(auth_data[0].principal_id))


@router.post("/api/security/scan")
async def scan_security(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> list[dict[str, Any]]:
    return serialize_dto(_service(request).scan_security(auth_data[0].principal_id))


@router.get("/api/security/health")
async def list_security_health(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> list[dict[str, Any]]:
    return _service(request).list_security_health(auth_data[0].principal_id)


@router.post("/api/security/health-check")
async def check_security_health(
    request: Request, auth_data: tuple[ApiSession, Principal] = Depends(_auth)
) -> list[dict[str, Any]]:
    return _service(request).check_security_health(auth_data[0].principal_id)


@router.post("/api/security/breach-check")
async def check_password_breach(
    body: BreachCheckRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    return serialize_dto(
        _service(request).check_password_breach(auth_data[0].principal_id, body.password, enabled=body.enabled)
    )


@router.get("/api/chat-search")
async def search_chat_history(
    q: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    return serialize_dto(_service(request).search_sessions(q, auth_data[1].delegated_by_user_id))


@router.get("/api/sessions/{session_id}")
async def get_session(
    session_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    view = _service(request).get_session(session_id, user_id=auth_data[1].delegated_by_user_id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown session: {session_id}")
    body = serialize_dto(view)
    # BUG-34: transcript restoration carries the metadata-only approval link
    # for unresolved parked turns. Conversation/model state remains encrypted
    # server-side; the projection is scoped to the authenticated principal.
    body["parked_approvals"] = [
        {
            "approval_id": str(row["approval_id"]),
            "turn_id": str(row["turn_id"]),
            "tool_name": str(row["tool_name"]),
            "created_at": str(row["created_at"]),
        }
        for row in _service(request).store.list_pending_suspended_turns(
            auth_data[0].principal_id, session_id
        )
    ]
    return body


@router.get("/api/sessions/{session_id}/export/manifest")
async def get_session_export_manifest(
    session_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """What an export of this conversation would contain (BUG-22).

    Read before choosing a format, so the owner reviews the exact messages, the
    exact files, and the redaction policy that will be applied — rather than
    discovering them in a downloaded document.
    """
    session, principal = auth_data
    transcript = _service(request).build_session_transcript(
        session_id,
        user_id=principal.delegated_by_user_id,
        principal_id=session.principal_id,
    )
    if transcript is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"ok": False, "reason_code": "session_not_found"},
        )
    return dict(transcript.manifest())


@router.post("/api/sessions/{session_id}/export")
async def export_session_transcript(
    session_id: str,
    body: ExportSessionRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> Response:
    """Render this conversation as a downloadable file.

    Authorised by the session boundary, redacted before rendering, audited after
    it succeeds. The response is the document itself; nothing about the request
    grants access the caller did not already have.
    """
    from raiker.sessions.transcript import EXPORT_FORMATS, render, safe_filename

    session, principal = auth_data
    export_format = (body.format or "html").lower()
    if export_format not in EXPORT_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "reason_code": "export_format_unsupported"},
        )
    service = _service(request)
    transcript = service.build_session_transcript(
        session_id,
        user_id=principal.delegated_by_user_id,
        principal_id=session.principal_id,
    )
    if transcript is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"ok": False, "reason_code": "session_not_found"},
        )
    payload, media_type = render(transcript, export_format)
    service.record_transcript_export(
        session_id,
        acting_principal_id=session.principal_id,
        export_format=export_format,
        message_count=transcript.message_count,
        file_count=len(transcript.files),
        byte_size=len(payload),
    )
    filename = safe_filename(transcript.title, session_id, export_format)
    return Response(
        content=payload,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put("/api/sessions/{session_id}/pin")
async def set_session_pinned(
    session_id: str,
    body: SetSessionPinnedRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Pin (or unpin) a session for the authenticated local human.

    Pinning is an organizing label only — it surfaces the session first in the
    Sessions list and grants nothing. Human-only; an account cannot pin another
    account's session.
    """
    result = _service(request).set_session_pinned(
        session_id, body.pinned, auth_data[0].principal_id
    )
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.put("/api/sessions/{session_id}/rename")
async def rename_session(
    session_id: str,
    body: RenameSessionRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Rename one session for the authenticated local human.

    The title is an organizing label only — it grants nothing. The server
    normalizes the title (trim, collapse whitespace, length cap) and rejects
    invalid input with 422. Human-only; an account cannot rename another
    account's session.
    """
    result = _service(request).rename_session(
        session_id, body.title, auth_data[0].principal_id
    )
    if not result.ok:
        reason = result.reason_code or ""
        if reason.startswith("invalid_title"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"ok": False, "reason_code": result.reason_code},
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.put("/api/sessions/{session_id}/archive")
async def archive_session(
    session_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Soft-archive one session (human-only).

    Archiving moves a chat out of the default active list and is fully
    reversible via unarchive; it never deletes transcripts, events, checkpoints,
    or permissions. An account cannot archive another account's session.
    """
    result = _service(request).set_session_archived(
        session_id, True, auth_data[0].principal_id
    )
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.put("/api/sessions/{session_id}/unarchive")
async def unarchive_session(
    session_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Restore one archived session to the active list (human-only).

    An account cannot unarchive another account's session.
    """
    result = _service(request).set_session_archived(
        session_id, False, auth_data[0].principal_id
    )
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.delete("/api/sessions/bulk")
async def delete_sessions(
    body: BulkDeleteSessionsRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    result = _service(request).delete_sessions(body.session_ids, auth_data[0].principal_id)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.delete("/api/sessions/{session_id}")
async def delete_session(
    session_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
    x_session_delete_confirm: str | None = Header(default=None),
) -> dict[str, Any]:
    """Permanently delete one session and its cascaded rows (human-only).

    Requires an explicit confirmation header matching the session id (mirrors
    project deletion). Respects user/session visibility — an account cannot
    delete another account's session.
    """
    if x_session_delete_confirm != session_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"ok": False, "reason_code": "session_delete_confirmation_required"},
        )
    result = _service(request).delete_session(session_id, auth_data[0].principal_id)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.put("/api/sessions/{session_id}/project")
async def set_session_project(
    session_id: str,
    body: SetSessionProjectRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Move one chat into a project, or out of every project (human-only).

    A project is an organizing scope — the move grants nothing and changes no
    gate, policy, or authority. It changes only the bounded context the chat
    receives on its next turn: project instructions, shared attachments, and
    the opt-in approved-memory boundary. A null `project_id` moves the chat
    out, removing all of that. Respects user/session visibility — an account
    cannot move another account's chat.
    """
    result = _service(request).set_session_project(
        session_id, body.project_id, auth_data[0].principal_id
    )
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.put("/api/sessions/{session_id}/tags")
async def set_session_tags(
    session_id: str,
    body: SetSessionTagsRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Replace the tag set for one session (human-only).

    Tags are organizing labels only — they surface as chips on the session
    row and grant nothing. The server normalizes the list (trim, lowercase,
    dedupe, length/count caps) and rejects invalid input with 422. Respects
    user/session visibility — an account cannot retag another account's session.
    """
    result = _service(request).set_session_tags(
        session_id, body.tags, auth_data[0].principal_id
    )
    if not result.ok:
        reason = result.reason_code or ""
        if reason.startswith("invalid_tag"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"ok": False, "reason_code": result.reason_code},
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.get("/api/turns/{turn_id}")
async def get_turn(
    turn_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    view = _service(request).get_turn(turn_id, user_id=auth_data[1].delegated_by_user_id)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown turn: {turn_id}")
    return serialize_dto(view)


@router.get("/api/events")
async def list_events(
    request: Request,
    session_id: str | None = None,
    turn_id: str | None = None,
    event_type: str | None = None,
    limit: int = 100,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    service = _service(request)
    user_id = auth_data[1].delegated_by_user_id
    if session_id is not None and service.get_session(session_id, user_id=user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown session")
    if turn_id is not None and service.get_turn(turn_id, user_id=user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown turn")
    return serialize_dto(
        service.list_events(
            session_id=session_id, turn_id=turn_id, event_type=event_type, limit=limit, user_id=user_id
        )
    )


@router.get("/api/brain")
async def get_brain(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Return the authenticated user's redacted runtime relationship graph."""
    session, principal = auth_data
    return serialize_dto(
        _service(request).brain_view(
            principal_id=session.principal_id,
            user_id=principal.delegated_by_user_id,
        )
    )


@router.post("/api/brain/sources")
async def add_brain_source(
    body: BrainSourceRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Add one explicit workspace-relative file or folder to the Brain graph."""
    try:
        return _service(request).add_brain_source(body.path, owner_principal_id=auth_data[0].principal_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"ok": False, "reason_code": str(exc)},
        ) from exc


@router.get("/api/brain/sources/browse")
async def browse_brain_sources(
    request: Request,
    path: str = ".",
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    del auth_data
    try:
        return _service(request).browse_brain_sources(path)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"ok": False, "reason_code": str(exc)},
        ) from exc


@router.post("/api/brain/sources/review")
async def review_brain_source(
    body: BrainSourceRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    del auth_data
    try:
        return _service(request).review_brain_source(body.path)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"ok": False, "reason_code": str(exc)},
        ) from exc


@router.get("/api/brain/settings")
async def get_brain_preferences(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    return _service(request).get_brain_preferences(auth_data[0].principal_id)


@router.put("/api/brain/settings")
async def save_brain_preferences(
    body: dict[str, Any],
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    try:
        settings = body.get("settings", {})
        if not isinstance(settings, dict):
            raise ValueError("invalid_brain_preferences")
        return _service(request).save_brain_preferences(
            settings, owner_principal_id=auth_data[0].principal_id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"ok": False, "reason_code": str(exc)},
        ) from exc


@router.delete("/api/brain/sources")
async def remove_brain_source(
    path: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    return _service(request).remove_brain_source(path, owner_principal_id=auth_data[0].principal_id)


@router.get("/api/execution-environments")
async def get_execution_environments(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    return _service(request).execution_environments(auth_data[0].principal_id)


@router.put("/api/execution-environments/configure")
async def configure_execution_environment(
    body: dict[str, Any],
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    raw_config = body.get("config", {})
    if not isinstance(raw_config, dict):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"ok": False, "reason_code": "invalid_execution_config"})
    result = _service(request).configure_execution_environment(
        profile_id=str(body["profile_id"]) if body.get("profile_id") else None,
        kind=str(body.get("kind", "")), name=str(body.get("name", "")),
        config=raw_config, enabled=bool(body.get("enabled", False)),
        owner_principal_id=auth_data[0].principal_id,
    )
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"ok": False, "reason_code": result.reason_code})
    return {"ok": True, **result.data}


@router.put("/api/execution-environments/selection")
async def select_execution_environment(
    body: dict[str, Any],
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    result = _service(request).select_execution_environment(
        str(body.get("profile_id", "")), auth_data[0].principal_id
    )
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"ok": False, "reason_code": result.reason_code})
    return {"ok": True, **result.data}


@router.get("/api/code/repos")
async def list_code_repos(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Repositories this account's Build workspace can point a coding chat at.

    References only: a local folder stays workspace-contained, and a GitHub
    coordinate carries no credential. The response also reports the
    ``connector_github_runtime`` gate state and decision mode so the interface
    can say whether a connected GitHub repository is actually readable — it is
    disabled and fails closed until the owner enables it.
    """
    return serialize_dto(
        _service(request).list_code_repos(owner_principal_id=auth_data[0].principal_id)
    )


@router.post("/api/code/repos", status_code=status.HTTP_201_CREATED)
async def connect_code_repo(
    body: ConnectCodeRepoRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Connect a workspace-contained folder or a GitHub `owner/repo` coordinate.

    Never reaches the network and grants no capability. A local path that
    resolves outside the workspace, a missing folder, or a malformed GitHub
    coordinate is refused (fail closed).
    """
    session, principal = auth_data
    service = _service(request)
    if body.kind == "local":
        if not body.path:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"ok": False, "reason_code": "repo_path_required"},
            )
        result = service.connect_local_repo(
            body.path,
            owner_principal_id=session.principal_id,
            user_id=principal.delegated_by_user_id,
        )
    else:
        if not body.owner or not body.repo:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"ok": False, "reason_code": "github_owner_and_repo_required"},
            )
        result = service.connect_github_repo(
            body.owner,
            body.repo,
            body.branch,
            owner_principal_id=session.principal_id,
            user_id=principal.delegated_by_user_id,
        )
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.put("/api/code/repos/selection")
async def select_code_repo(
    body: SelectCodeRepoRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Point the Build workspace at one repository, or at none with ``null``."""
    result = _service(request).select_code_repo(
        body.repo_id, owner_principal_id=auth_data[0].principal_id
    )
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.get("/api/code/map")
async def get_code_map_status(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """B9 — the code map's state for the repository Build is pointed at.

    Metadata only: the gate, the decision mode, the repository, and the counts.
    Never a path, never a symbol, so the status call cannot become a listing of
    the owner's tree over a route meant to describe an index.
    """
    return _service(request).code_map_status(owner_principal_id=auth_data[0].principal_id)


@router.post("/api/code/map/rebuild")
async def rebuild_code_map(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Re-scan the selected repository. Fails closed when the gate is off."""
    session, principal = auth_data
    result = _service(request).rebuild_code_map(
        owner_principal_id=session.principal_id,
        user_id=principal.delegated_by_user_id,
    )
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.delete("/api/code/repos/{repo_id}")
async def disconnect_code_repo(
    repo_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Forget one repository reference. Never touches the folder or the remote."""
    session, principal = auth_data
    result = _service(request).disconnect_code_repo(
        repo_id,
        owner_principal_id=session.principal_id,
        user_id=principal.delegated_by_user_id,
    )
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.get("/api/checkpoints")
async def list_checkpoints(
    request: Request,
    session_id: str | None = None,
    limit: int = 50,
    project_id: str | None = None,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    return serialize_dto(
        _service(request).list_checkpoints(
            session_id=session_id, limit=limit, project_id=project_id, user_id=auth_data[1].delegated_by_user_id
        )
    )


# ── Projects (web-app task 5: organizing scopes, governance-neutral) ──────────
@router.get("/api/projects")
async def list_projects(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    return serialize_dto(_service(request).list_projects(auth_data[1].delegated_by_user_id))


@router.post("/api/projects")
async def create_project(
    body: CreateProjectRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Create a named project for the authenticated local human.

    The project root is derived server-side and always contained inside the
    workspace; a project grants no authority.
    """
    session, _principal = auth_data
    result = _service(request).create_project(body.name, session.principal_id, parent_id=body.parent_id)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.put("/api/projects/selection")
async def select_project(
    body: SelectProjectRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Set (or clear) the active project for the authenticated local human.

    New sessions are stamped with the active project; selecting grants nothing.
    """
    session, _principal = auth_data
    result = _service(request).select_project(body.project_id, session.principal_id)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.get("/api/projects/tree")
async def list_project_tree(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict]:
    """Return the full project tree (active, non-archived only)."""
    return _service(request).list_project_tree(auth_data[1].delegated_by_user_id)


@router.get("/api/projects/{project_id}")
async def get_project(
    project_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    view = _service(request).get_project(project_id, auth_data[1].delegated_by_user_id)
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown project: {project_id}"
        )
    return serialize_dto(view)


@router.post("/api/projects/{project_id}/export")
async def export_project(
    project_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> Response:
    result = _service(request).export_project(project_id, auth_data[0].principal_id)
    if not result.ok:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if result.reason_code == f"unknown_project:{project_id}"
            else status.HTTP_403_FORBIDDEN
        )
        raise HTTPException(
            status_code=status_code,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    export_path = result.data["export_path"]
    if export_path is not None:
        return FileResponse(
            export_path,
            media_type="application/x-ndjson",
            filename="project-export.ndjson",
        )
    return Response(
        content=b"",
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="project-export.ndjson"'},
    )


@router.put("/api/projects/{project_id}/context")
async def save_project_context(
    project_id: str,
    body: SaveProjectContextRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    result = _service(request).save_project_context(
        project_id,
        instructions=body.instructions,
        attachment_ids=body.attachment_ids,
        memory_enabled=body.memory_enabled,
        memory_mode=body.memory_mode,
        acting_principal_id=auth_data[0].principal_id,
    )
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.delete("/api/projects/{project_id}")
async def delete_project(
    project_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
    x_project_delete_confirm: str | None = Header(default=None),
) -> dict[str, Any]:
    if x_project_delete_confirm != project_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"ok": False, "reason_code": "project_delete_confirmation_required"},
        )
    result = _service(request).delete_project(project_id, auth_data[0].principal_id, confirm=True)
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"ok": False, "reason_code": result.reason_code})
    return {"ok": True, **result.data}


@router.put("/api/projects/{project_id}/move")
async def move_project(
    project_id: str,
    body: MoveProjectRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Move a project to a new parent folder (human-only).
    
    ``body.parent_id`` may be null to reparent to root. A cycle check is
    performed server-side — a descendant cannot become its own ancestor.
    """
    result = _service(request).move_project(project_id, body.parent_id, auth_data[0].principal_id)
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"ok": False, "reason_code": result.reason_code})
    return {"ok": True, **result.data}


@router.put("/api/projects/{project_id}/archive")
async def archive_project(
    project_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Soft-delete a project subtree (human-only)."""
    result = _service(request).archive_project(project_id, auth_data[0].principal_id)
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"ok": False, "reason_code": result.reason_code})
    return {"ok": True, **result.data}


@router.get("/api/checkpoints/{checkpoint_id}")
async def get_checkpoint(
    checkpoint_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    view = _service(request).get_checkpoint(checkpoint_id, auth_data[1].delegated_by_user_id)
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown checkpoint: {checkpoint_id}"
        )
    return serialize_dto(view)


@router.get("/api/tasks")
async def list_tasks(
    request: Request,
    session_id: str | None = None,
    task_status: str | None = None,
    project_id: str | None = None,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    """List tasks/schedules visible to the account. `project_id` scopes the
    list to one project's schedules; omitting it lists every visible task."""
    return serialize_dto(
        _service(request).list_tasks(
            session_id=session_id,
            status=task_status,
            user_id=auth_data[1].delegated_by_user_id,
            project_id=project_id,
        )
    )


@router.post("/api/tasks", status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreateRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, principal = auth_data
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="task_title_required")
    # Project-scoped schedules: an explicit project_id wins; otherwise the task
    # is stamped with the active project so project work stays project-scoped.
    try:
        view = _service(request).create_task(
            title=title,
            objective=body.description.strip(),
            user_id=principal.delegated_by_user_id,
            principal_id=session.principal_id,
            priority=body.priority,
            scheduled_at=body.scheduled_at,
            recurrence=body.recurrence,
            reminder_at=body.reminder_at,
            parent_task_id=body.parent_task_id,
            project_id=body.project_id,
            model_profile=body.model_profile,
            model=body.model,
            attachments=body.attachments,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"ok": False, "reason_code": str(exc)},
        ) from exc
    return serialize_dto(view)


@router.post("/api/tasks/{task_id}/resume")
async def resume_task(
    task_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Continue one parked scheduled run whose approval has been granted (BUG-25).

    The scheduler already does this on its own tick; this is the owner saying
    "try that again" when automatic continuation could not proceed — a browser
    tab won the claim, the host was down when the decision landed, the
    continuation threw. It runs exactly the same code path, so it can never
    continue something the automatic pass would have refused, and exactly-once
    is still the store's atomic claim rather than anything added here.
    """
    from raiker.tasks.scheduler import TaskScheduler

    session, _principal = auth_data
    workspace: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    result = await TaskScheduler(workspace).resume_task(task_id, session.principal_id)
    if result.get("reason_code") == "task_not_found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"ok": False, "reason_code": "task_not_found"},
        )
    return result


@router.get("/api/models")
async def get_models(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = auth_data
    return serialize_dto(_service(request).get_models(session.principal_id))


@router.get("/api/connections")
async def get_connections(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Read-only status of governed service connectors (web-app task 4).

    Reports each connector's capability gate state, decision mode, whether the
    owner credential env is set, and whether its host is on the connector egress
    allowlist. Never reaches the network and never exposes a credential value.
    Enabling a connector is done through the capability-gate + decision-mode
    control plane (gate-manager only), not here.
    """
    session, _principal = auth_data
    return serialize_dto(_service(request).get_connections(session.principal_id))


@router.get("/api/models/{profile_id}/provider-models")
async def list_provider_models(
    profile_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """On-demand listing of the models a provider serves for one profile.

    User-initiated read; provider policy (gates, egress allowlist, API key) is
    enforced before any network contact, and failures return an honest empty
    list — model names are never fabricated.
    """
    session, _principal = auth_data
    view = await _service(request).list_provider_models(profile_id, session.principal_id)
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown model profile: {profile_id}"
        )
    return serialize_dto(view)


@router.get("/api/sessions/{session_id}/context-usage")
async def get_session_context_usage(
    session_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Token usage and API cost for one conversation, plus the provider total.

    Owner-scoped: the ledger is queried by the authenticated principal, so one
    account can never read another's spend. Every figure is optional and names
    its source; nothing is estimated server-side.
    """
    session, _principal = auth_data
    return serialize_dto(_service(request).get_context_usage(session_id, session.principal_id))


@router.put("/api/models/{profile_id}/price")
async def set_model_price(
    profile_id: str,
    body: ModelPriceRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Set or clear the owner's price override for one model on one profile.

    An owner price outranks both the provider-published price and the shipped
    list price, and re-prices history immediately because cost is derived at
    read time rather than stored.
    """
    session, _principal = auth_data
    result = _service(request).set_model_price(
        profile_id,
        body.model,
        input_per_mtok=body.input_per_mtok,
        output_per_mtok=body.output_per_mtok,
        cache_write_per_mtok=body.cache_write_per_mtok,
        cache_read_per_mtok=body.cache_read_per_mtok,
        currency=body.currency or "USD",
        effective_from=body.effective_from,
        reason=body.reason,
        acting_principal_id=session.principal_id,
    )
    if not result.ok:
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
                if result.reason_code == "not_authorized_gate_manager"
                else status.HTTP_400_BAD_REQUEST
            ),
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.get("/api/models/pricing")
async def get_model_pricing(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """The normalised price registry for this owner (BUG-21).

    One read answers everything the pricing surface must state: the exact model
    id each rate belongs to, which source supplied it, when it took effect, the
    individual input/output/cache-write/cache-read components, the full change
    history, and each provider's synchronisation state including staleness.
    """
    session, _principal = auth_data
    return serialize_dto(_service(request).list_model_pricing(session.principal_id))


@router.post("/api/models/pricing/refresh")
async def refresh_model_pricing(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Run the reviewed-documentation adapters now, bypassing the cadence.

    No provider connection is opened here: a provider's own catalogue feeds the
    registry only through the user-initiated model listing.
    """
    session, _principal = auth_data
    result = _service(request).refresh_model_pricing(session.principal_id)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.get("/api/models/capacities")
async def get_model_capacities(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    result = _service(request).model_capacity_status(auth_data[0].principal_id)
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"ok": False, "reason_code": result.reason_code})
    return {"ok": True, **result.data}


@router.post("/api/models/capacities/refresh")
async def refresh_model_capacities(
    request: Request,
    force: bool = False,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    result = await _service(request).refresh_local_model_capacities(
        auth_data[0].principal_id, force=force
    )
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"ok": False, "reason_code": result.reason_code})
    return {"ok": True, **result.data}


@router.put("/api/models/{profile_id}/capacity")
async def set_model_capacity(
    profile_id: str,
    body: dict[str, Any],
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    raw_tokens = body.get("tokens")
    try:
        tokens = None if raw_tokens in (None, "") else int(str(raw_tokens))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "reason_code": "model_context_capacity_invalid"},
        ) from exc
    result = _service(request).set_model_context_capacity(
        profile_id, str(body.get("model", "")), tokens,
        str(body.get("reason", "")), auth_data[0].principal_id,
    )
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN if result.reason_code == "not_authorized_gate_manager" else status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.put("/api/model-selection")
async def set_model_selection(
    body: SetModelSelectionRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Persist the operator's model selection (human gate-manager only).

    Placeholder profiles require a concrete model; provider policy is validated
    fail-closed before the selection is saved.
    """
    session, _principal = auth_data
    result = await _service(request).set_model_selection(
        body.profile_id, body.model, session.principal_id
    )
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.put("/api/models/{profile_id}/connection")
async def set_model_connection(
    profile_id: str,
    body: ModelConnectionRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Save one user's encrypted provider endpoint/key without exposing either."""
    session, _principal = auth_data
    store = SQLiteStore(request.app.state.workspace_root)  # type: ignore[attr-defined]
    try:
        profile = ModelProfileRegistry.load().resolve_profile_id(profile_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail={"reason_code": "unknown_model_profile"}) from exc
    values = {
        key: value.strip()
        for key, value in {"endpoint": body.endpoint or "", "api_key": body.api_key or ""}.items()
        if value.strip()
    }
    if not values:
        clear_model_connection(store, session.principal_id, profile_id)
        return {"ok": True, "connection_configured": False}
    # The vault key encrypts what we are about to store. It is a local
    # encryption key, not a secret the owner has to invent, so requiring them to
    # go and generate one before they may save an API key is friction with no
    # security benefit — the key would be identical either way. Provision it on
    # demand; Settings keeps the controls to view, rotate, and clear it.
    ensure_vault_key(request.app.state.workspace_root)  # type: ignore[attr-defined]
    try:
        ModelProviderFactory(
            policy=provider_runtime_policy_from_gates(
                store, session.principal_id, configuring_profile_id=profile_id
            ),
            connection=values,
        ).create(profile, require_model=False)
        put_model_connection(store, session.principal_id, profile_id, values)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail={"reason_code": str(exc)}) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=403, detail={"reason_code": str(exc)}) from exc
    return {"ok": True, "connection_configured": True}


@router.put("/api/model-advisor")
async def set_model_advisor(
    body: SetModelAdvisorRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Persist (or clear) the user-owned advisor model profile (gate-manager only).

    Selecting an advisor grants nothing: the consult path is gated by the
    advisor_model_runtime capability, its decision mode (default ask), and
    provider policy (hosted/private gate + egress allowlist + key) per call.
    """
    session, _principal = auth_data
    result = _service(request).set_model_advisor(body.profile_id, session.principal_id)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.put("/api/model-fallback")
async def set_model_fallback(
    body: SetModelFallbackRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Set the user-owned ordered model fallback sequence (human gate-manager only)."""
    session, _principal = auth_data
    result = _service(request).set_model_fallback_sequence(body.profile_ids, session.principal_id)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": result.reason_code},
        )
    return {"ok": True, **result.data}


@router.get("/api/diagnostics")
async def get_diagnostics(
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    _session, principal = _auth_data
    return serialize_dto(_service(request).get_diagnostics(principal.principal_id))


# ── Web workbench read models (plan phases 3 and 4) ───────────────────────────
# Read-only aggregates. None of these mutate the runtime, reach the network,
# read a credential value, or return workspace file content.
def _read_models(request: Request) -> WebReadModels:
    ws: str | Path = request.app.state.workspace_root  # type: ignore[attr-defined]
    return WebReadModels(ws)


@router.get("/api/extensions")
async def get_extensions(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Extension lifecycle as four independent facts per row.

    ``installed``, ``connected``, ``enabled``, and ``usable`` are reported
    separately so the interface never presents an extension as available on
    metadata alone; ``blocked_reason`` names the first unmet condition.
    """
    session, principal = auth_data
    return serialize_dto(
        _read_models(request).extensions_overview(
            acting_principal_id=session.principal_id,
            user_id=principal.delegated_by_user_id,
        )
    )


@router.get("/api/checkpoints/{checkpoint_id}/restore-plan")
async def get_checkpoint_restore_plan(
    checkpoint_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Metadata-only preflight for restoring to a checkpoint.

    Computing the plan changes nothing. It reports which files a restore would
    rewrite, delete, or skip, and whether any of them were last changed by a
    different principal. Executing a restore still goes through the governed
    approval path — this endpoint never performs one.
    """
    session, principal = auth_data
    plan = _read_models(request).checkpoint_restore_plan(
        checkpoint_id,
        principal_id=session.principal_id,
        user_id=principal.delegated_by_user_id,
    )
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown checkpoint: {checkpoint_id}"
        )
    return plan


@router.get("/api/projects/{project_id}/files")
async def get_project_files(
    project_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """List a project's files as metadata plus governed-write provenance.

    File *content* is never served to the browser. Each entry carries a
    workspace-relative path, size, and modification time; ``provenance`` links a
    path to the turns and actions that wrote it, so the owner can trace a change
    back to the approval that allowed it.
    """
    _session, principal = auth_data
    view = _read_models(request).project_files(
        project_id, user_id=principal.delegated_by_user_id
    )
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown project: {project_id}"
        )
    return serialize_dto(view)


@router.get("/api/diagnostics/export")
async def get_diagnostics_export(
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """A copyable, redacted support bundle of the runtime's readiness facts."""
    _session, principal = auth_data
    return _read_models(request).diagnostics_export(acting_principal_id=principal.principal_id)
