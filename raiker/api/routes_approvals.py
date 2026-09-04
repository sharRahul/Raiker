from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from raiker.api.auth import AuthMiddleware
from raiker.api.routes_prompts import _record_generated_file_attachments_for_turn, _sse
from raiker.api.schemas import (
    AnswerOwnerQuestionRequest,
    ReplaceApprovalRequest,
    ResolveApprovalRequest,
    serialize_dto,
)
from raiker.api.sessions import ApiSession
from raiker.approvals import ApprovalInbox
from raiker.approvals.execution import (
    ApprovalExecutionBridge,
    approval_arguments,
    executable_capability,
)
from raiker.contracts.ids import utc_now
from raiker.contracts.models import OWNER_QUESTION_TOOL
from raiker.control.dashboard import DashboardService
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.gateway.agent_gateway import AgentGateway
from raiker.runtime.authority.models import Principal
from raiker.runtime.authority.router import RuntimeAuthority
from raiker.runtime.connector_ecosystem import ConnectorInvoker
from raiker.runtime.turn_suspension import (
    TurnSuspensionError,
    approval_outcome,
    deserialize_pending_calls,
    owner_answer_outcome,
)
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.patch_selection import unknown_hunk_ids

router = APIRouter()

# resolve() raises these on bad input; map each to a stable HTTP status + reason_code.
_RESOLVE_ERRORS = {
    "approval_not_found": status.HTTP_404_NOT_FOUND,
    "approval_already_resolved": status.HTTP_409_CONFLICT,
    "approval_payload_tampered": status.HTTP_409_CONFLICT,
    "approval_expired": status.HTTP_409_CONFLICT,
}

# The relay reports the same refusals by reason code rather than by exception, so
# an execution that is turned away maps to the identical status the metadata-only
# path would have returned. Anything else is a conflict carrying its reason code.
_EXECUTION_ERRORS = {
    **_RESOLVE_ERRORS,
    "critical_approval_requires_lifecycle": status.HTTP_400_BAD_REQUEST,
    "posture_degraded:session_revoked": status.HTTP_403_FORBIDDEN,
}


def _ws(request: Request) -> str | Path:
    return request.app.state.workspace_root  # type: ignore[no-any-return]


def _service(request: Request) -> DashboardService:
    return DashboardService(_ws(request))


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    return AuthMiddleware(_ws(request)).authenticate(request)


def _record_resume_outcome(
    request: Request, store: SQLiteStore, approval_id: str, outcome: dict[str, Any]
) -> dict[str, Any]:
    """Attach the decision's outcome to the turn it unblocked, if there is one (B2).

    Returns what the client needs to continue: whether a parked turn exists and,
    if so, which session and turn the continuation belongs to. Not every approval
    has one — a connector-store write has no chat turn behind it, and a turn that
    failed to park is simply not resumable.

    A scheduled run has no client to return this to, so recording the outcome is
    also the moment to tell the host's scheduler that its parked run can move
    (BUG-39).
    """
    row = store.load_suspended_turn(approval_id)
    if row is None or str(row.get("status")) != "suspended":
        return {"resumable": False}
    if not store.record_suspended_turn_outcome(approval_id, json.dumps(outcome, sort_keys=True)):
        return {"resumable": False}
    session_id = str(row["session_id"])
    _nudge_scheduler(request, session_id)
    return {
        "resumable": True,
        "session_id": session_id,
        "turn_id": str(row["turn_id"]),
        # ADD-02 — how many of the turn's calls this decision unblocks. A client
        # that resumes and lands on another approval was told to expect it.
        "queue_position": int(row.get("queue_position") or 1),
        "queue_total": int(row.get("queue_total") or 1),
        "queued_calls": len(deserialize_pending_calls(row.get("pending_calls_json"))),
    }


def _approval_attribution(
    request: Request,
    approval_id: str,
    *,
    user_id: str | None,
    principal_id: str,
) -> dict[str, Any]:
    detail = _service(request).get_approval(
        approval_id, user_id=user_id, principal_id=principal_id
    )
    if detail is None:
        return {"proposed_by": None, "approved_by": None, "machine_identity": None}
    approval = detail.approval
    return {
        "proposed_by": approval.proposed_by.to_dict(),
        "approved_by": (
            approval.approved_by.to_dict() if approval.approved_by is not None else None
        ),
        "machine_identity": (
            approval.machine_identity.to_dict()
            if approval.machine_identity is not None
            else None
        ),
    }


def _nudge_scheduler(request: Request, session_id: str) -> None:
    """Tell the resident scheduler an approval it was waiting on has been decided.

    BUG-39. Chat continues within a second because the tab that resolved the
    approval goes straight on to resume the turn; a scheduler-launched run has no
    tab, so it used to wait for the next 15-second sweep with its card still
    reading *waiting for approval*. This is that missing signal.

    Scoped to the Inbox sessions scheduled work actually runs in: a Chat or Build
    approval is continued by the client that made it and has nothing for the
    scheduler to do. Nudging is best-effort in both directions — an unstarted or
    already-shutting-down host simply falls back to the sweep, and a nudge that
    arrives while a sweep is running is coalesced into the next one.
    """
    if not session_id.startswith("sess_inbox_"):
        return
    wakeup = getattr(request.app.state, "scheduler_wakeup", None)
    if wakeup is not None:
        wakeup.request()


@router.get("/api/approvals")
async def list_approvals(
    request: Request,
    status_filter: str = "pending",
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> list[dict[str, Any]]:
    session, _principal = _auth_data
    user_id = SQLiteStore(_ws(request)).principal_user_id(session.principal_id)
    return serialize_dto(
        _service(request).list_approvals(
            status=status_filter, user_id=user_id, principal_id=session.principal_id
        )
    )


@router.get("/api/approvals/resumable")
async def list_resumable_turns(
    request: Request,
    session_id: str | None = None,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Parked turns this account may continue right now (BUG-24).

    A Chat tab that did not resolve the approval itself has no way to learn that
    another tab did. This is that signal, made authoritative rather than
    inferred: the server already knows which suspended turns have a recorded
    outcome and have not yet been claimed, so a client asks rather than guesses.

    The read is authenticated and principal-scoped, returns ids only, and is
    idempotent — polling it changes nothing. Exactly-once resumption is still
    enforced where it always was, by ``claim_suspended_turn``: a turn listed to
    two tabs can only ever be claimed by one of them.
    """
    session, _principal = _auth_data
    rows = SQLiteStore(_ws(request)).list_resumable_suspended_turns(
        session.principal_id, session_id
    )
    return {
        "session_id": session_id,
        "turns": [
            {
                "approval_id": str(row["approval_id"]),
                "session_id": str(row["session_id"]),
                "turn_id": str(row["turn_id"]),
                "tool_name": str(row.get("tool_name") or ""),
                # The decision itself, so the tab can say "Approved — continuing…"
                # or "Rejected" before the stream produces its first token.
                "outcome_status": _outcome_status(row.get("outcome_json")),
                "created_at": str(row.get("created_at") or ""),
                # ADD-02 — which decision of the batch this was, so a tab that
                # did not make it can say so before the stream starts.
                "queue_position": int(row.get("queue_position") or 1),
                "queue_total": int(row.get("queue_total") or 1),
            }
            for row in rows
        ],
    }


def _outcome_status(outcome_json: Any) -> str:
    """The model-visible status of a resolution, or "unknown" if unreadable."""
    try:
        parsed = json.loads(str(outcome_json))
    except (TypeError, ValueError):
        return "unknown"
    status_value = parsed.get("status") if isinstance(parsed, dict) else None
    return str(status_value) if isinstance(status_value, str) else "unknown"


@router.get("/api/approvals/{approval_id}")
async def get_approval(
    approval_id: str,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, _principal = _auth_data
    user_id = SQLiteStore(_ws(request)).principal_user_id(session.principal_id)
    view = _service(request).get_approval(
        approval_id, user_id=user_id, principal_id=session.principal_id
    )
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown approval: {approval_id}"
        )
    return serialize_dto(view)


#: An owner writing their own answer instead of choosing one. Bounded for the
#: same reason every other free text is: it reaches a model.
MAX_FREE_TEXT_ANSWER_CHARS = 2_000


def _parked_questions(approval_row: dict[str, Any]) -> list[dict[str, Any]]:
    """The questions this approval parked on, as they were validated and stored."""
    raw = approval_row.get("arguments_json") or approval_row.get("arguments") or "{}"
    try:
        arguments = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (TypeError, ValueError):
        arguments = {}
    questions = arguments.get("questions")
    return [item for item in questions if isinstance(item, dict)] if isinstance(questions, list) else []


def _checked_answers(
    questions: list[dict[str, Any]], submitted: dict[str, Any]
) -> dict[str, Any]:
    """Every answer must name a question that was asked and an option that was offered.

    The model wrote the questions and the options; the owner picked among them.
    Accepting a label nobody offered would let whatever posted the answer put
    text of its own into the model's next turn through a field the model already
    trusts — so an unrecognised question or label is refused rather than passed
    through. An owner who wants to say something else has `response`.
    """
    by_text = {str(entry.get("question", "")): entry for entry in questions}
    answers: dict[str, Any] = {}
    for asked, chosen in submitted.items():
        question = by_text.get(str(asked))
        if question is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"ok": False, "reason_code": "unknown_question"},
            )
        offered = {
            str(option.get("label", ""))
            for option in question.get("options", [])
            if isinstance(option, dict)
        }
        picked = chosen if isinstance(chosen, list) else [chosen]
        if not picked:
            continue
        if len(picked) > 1 and not question.get("multiSelect"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"ok": False, "reason_code": "single_select_question"},
            )
        for label in picked:
            if str(label) not in offered:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail={"ok": False, "reason_code": "unknown_option"},
                )
        answers[str(asked)] = [str(label) for label in picked] if len(picked) > 1 else str(picked[0])
    if not answers:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"ok": False, "reason_code": "no_answer_given"},
        )
    return answers


@router.post("/api/approvals/{approval_id}/answer")
async def answer_owner_question(
    approval_id: str,
    body: AnswerOwnerQuestionRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Answer a mid-turn question and let the turn continue (ADD-22).

    The question parked the turn through the approval transport, and this is the
    half that is not an approval: nothing is granted, nothing is executed, and
    the outcome handed back to the model is what the owner chose. An ordinary
    approval cannot be answered here for the mirror of the reason a question
    cannot be approved next door — the two kinds resolve through different doors
    so neither can be mistaken for the other.
    """
    session, _principal = _auth_data
    store = SQLiteStore(_ws(request))
    user_id = store.principal_user_id(session.principal_id)
    approval_row = store.load_approval(approval_id, user_id=user_id)
    if approval_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"ok": False, "reason_code": "approval_not_found"},
        )
    if str(approval_row.get("tool_name", "")) != OWNER_QUESTION_TOOL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"ok": False, "reason_code": "approval_is_not_a_question"},
        )

    questions = _parked_questions(approval_row)
    response = (body.response or "").strip() or None
    if response is None:
        answers = _checked_answers(questions, body.answers)
    else:
        if len(response) > MAX_FREE_TEXT_ANSWER_CHARS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"ok": False, "reason_code": "answer_too_long"},
            )
        answers = {}

    recorded = store.answer_owner_question(
        approval_id,
        answers_json=json.dumps(
            {"answers": answers, "response": response}, ensure_ascii=False, sort_keys=True
        ),
        answered_by=session.principal_id,
        answered_at=utc_now(),
    )
    if not recorded:
        # Already answered. Refused rather than overwritten: the first answer is
        # the one the turn resumed on.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"ok": False, "reason_code": "question_already_answered"},
        )
    EventLogWriter(store).append(
        make_event(
            session_id=str(approval_row.get("session_id") or f"question_{session.principal_id}"),
            turn_id=str(approval_row.get("turn_id") or "") or None,
            event_type="owner_question_answered",
            actor="owner",
            payload={
                "approval_id": approval_id,
                # Which questions were answered and whether the owner used the
                # options or their own words. Never the answer text: it is the
                # owner's, and the model receives it without the audit log
                # keeping a second copy.
                "question_count": len(questions),
                "answered_count": len(answers),
                "free_text": response is not None,
            },
        )
    )
    return {
        "approval_id": approval_id,
        "status": "answered",
        "answered": len(answers),
        "resume": _record_resume_outcome(
            request,
            store,
            approval_id,
            owner_answer_outcome(answers=answers, response=response),
        ),
    }


# BUG-271 — a reviewer could narrow a change and could not correct one.
#
# Per-hunk accept and reject ship (B14/FIXED-369). *Edit then accept* — the
# reviewer changing a line in the proposed diff and approving the result — did
# not, and the reason is the distinction the approval boundary is built on:
#
# * a **narrowing** is a subset of what was approved. `select_hunks` copies
#   bytes out of the approved patch and copies nothing else in, so the A1
#   immutable-intent hash still covers the whole approved change and what runs
#   is provably inside it;
# * an **edit** is a *different action*. Its bytes were never approved, so it
#   cannot ride that hash, and the one thing the relay must never do is execute
#   arguments no human read.
#
# So an edit does not amend a decision. It becomes a new proposal with its own
# preview, its own hash and its own approval, and the original resolves as
# denied with the replacement named. The owner reads their own text and approves
# it exactly as they would read the model's — which is the point: the bytes that
# execute are always bytes a human approved after seeing them.

#: The tools whose proposal is a patch, and so can be replaced by an edited one.
_PATCH_TOOLS = frozenset({"apply_patch"})


@router.post("/api/approvals/{approval_id}/replace")
async def replace_approval_with_edit(
    approval_id: str,
    body: ReplaceApprovalRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Deny a proposed patch and raise the reviewer's own in its place.

    Executes nothing. It records one denial and one fresh proposal, and returns
    the new approval id; the edited patch runs only if the owner then approves
    it, through the same relay, gate, policy review and posture check any other
    proposal passes.
    """
    from raiker.contracts.ids import new_id
    from raiker.contracts.models import ToolAction
    from raiker.tools.patch_selection import patch_target_paths

    session, _principal = _auth_data
    store = SQLiteStore(_ws(request))
    user_id = store.principal_user_id(session.principal_id)
    approval_row = store.load_approval(approval_id, user_id=user_id)
    if approval_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"ok": False, "reason_code": "approval_not_found"},
        )
    if str(approval_row.get("status", "")) != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"ok": False, "reason_code": "approval_already_resolved"},
        )
    # A critical approval keeps the human-only, step-up lifecycle. Replacing one
    # here would route it around that floor, so it is refused rather than
    # quietly downgraded.
    if approval_row.get("critical"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "reason_code": "critical_approval_requires_lifecycle"},
        )
    tool_name = str(approval_row.get("tool_name", ""))
    original = approval_arguments(approval_row)
    if tool_name not in _PATCH_TOOLS or not str(original.get("patch", "")).strip():
        # Only a patch can be edited as text. Offering the control on anything
        # else would be a control with nothing behind it.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"ok": False, "reason_code": "action_is_not_a_patch"},
        )

    edited = body.patch
    if not edited.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "reason_code": "replacement_patch_empty"},
        )
    original_targets = patch_target_paths(str(original.get("patch", "")))
    edited_targets = patch_target_paths(edited)
    if not edited_targets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "reason_code": "replacement_patch_unreadable"},
        )
    # A correction changes the same files. This is not the authority boundary —
    # the new approval is — but a "replacement" that reaches a file the review
    # never mentioned is a different change wearing a review's clothes, and the
    # owner should propose that as one rather than through this door.
    widened = sorted(set(edited_targets) - set(original_targets))
    if widened:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "ok": False,
                "reason_code": "replacement_widens_targets",
                "unexpected_paths": widened,
            },
        )
    if edited == str(original.get("patch", "")):
        # Nothing was corrected, so there is nothing to replace. Denying and
        # re-raising an identical proposal would only churn the audit trail.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"ok": False, "reason_code": "replacement_unchanged"},
        )

    session_id = str(approval_row.get("session_id", ""))
    turn_id = str(approval_row.get("turn_id", "")) or None
    action = ToolAction(
        action_id=new_id("act_"),
        tool_name=tool_name,
        # The reviewer's patch replaces the proposed one entirely. Nothing from
        # the original is merged in: a half-merged diff would be a third change
        # neither party wrote.
        arguments={**original, "patch": edited},
        risk_level=str(approval_row.get("risk_level", "medium")),
        requires_approval=True,
        proposed_by=session.principal_id,
    )
    # The replacement is raised *before* the denial, so the denial can name it.
    # If the denial then loses a race the owner is left with one extra pending
    # proposal — the one they just wrote, visible and refusable, running
    # nothing. The other order would leave a denial pointing at an id that does
    # not exist, which is a record that lies.
    replacement_id = new_id("appr_")
    store.insert_tool_action(action, session_id, turn_id, "approval_required")
    store.insert_approval(replacement_id, action)

    inbox = ApprovalInbox(store, EventLogWriter(store))
    reason = (body.reason or "").strip() or "Replaced by the reviewer's own edit."
    try:
        inbox.resolve(
            approval_id,
            approve=False,
            resolved_by=session.principal_id,
            reason=f"{reason} (replaced by {replacement_id})",
            user_id=user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=_RESOLVE_ERRORS.get(str(exc), status.HTTP_409_CONFLICT),
            detail={"ok": False, "reason_code": str(exc)},
        ) from exc

    EventLogWriter(store).append(
        make_event(
            session_id=session_id or f"approval_{session.principal_id}",
            turn_id=turn_id,
            event_type="approval_replaced_by_edit",
            actor="approval_api",
            payload={
                "approval_id": approval_id,
                "replacement_approval_id": replacement_id,
                "action_id": action.action_id,
                # Positions and counts, never the diff: the patch itself is on
                # the action row, redacted by the same path every other proposal
                # takes, and does not belong duplicated in the event log.
                "paths": len(edited_targets),
                "executes_action": False,
            },
        )
    )
    outcome = _record_resume_outcome(
        request,
        store,
        approval_id,
        approval_outcome(approved=False, executed=False, replaced=True),
    )
    return {
        "ok": True,
        "approval_id": approval_id,
        "status": "denied",
        "replacement_approval_id": replacement_id,
        "action_id": action.action_id,
        "executes_action": False,
        **outcome,
    }


@router.post("/api/approvals/{approval_id}/resolve")
async def resolve_approval(
    approval_id: str,
    body: ResolveApprovalRequest,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    session, principal = _auth_data
    store = SQLiteStore(_ws(request))
    inbox = ApprovalInbox(store, EventLogWriter(store))
    user_id = store.principal_user_id(session.principal_id)
    with store.connect() as connection:
        pending_intent_row = connection.execute(
            "SELECT * FROM connector_write_intents WHERE approval_id=?", (approval_id,)
        ).fetchone()
    if pending_intent_row is not None and pending_intent_row["principal_id"] != session.principal_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"ok": False, "reason_code": "connector_intent_principal_mismatch"},
        )
    # A connector-store write is owned by the principal named on its intent
    # (checked above), not by a chat session: those actions are recorded against
    # the synthetic "connector_store" session id, which has no sessions row to
    # scope by. Everything else is owned via its session's user.
    owner_user_id = None if pending_intent_row is not None else user_id
    approval_row = store.load_approval(approval_id, user_id=owner_user_id)
    if approval_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"ok": False, "reason_code": "approval_not_found"})
    # ADD-22 — a question is not an approval and cannot be approved. Refused
    # here rather than tolerated, because "approve" on a question would have to
    # mean something, and every meaning it could have is wrong: it grants
    # nothing, so approving it is empty, and answering it with a yes/no would
    # put words in the owner's mouth that they did not choose.
    if str(approval_row.get("tool_name", "")) == OWNER_QUESTION_TOOL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"ok": False, "reason_code": "approval_is_a_question"},
        )

    # B14 — the owner accepted part of the change set. Recorded as a decision
    # before anything runs, so what executes is decided by a row rather than by
    # an argument travelling beside a request, and validated here against the
    # approval's own patch so a selection can only ever name hunks that were
    # already approved.
    if body.accepted_hunks is not None:
        if not body.approve:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"ok": False, "reason_code": "hunk_selection_requires_approval"},
            )
        approved_patch = str(approval_arguments(approval_row).get("patch", ""))
        if not approved_patch.strip():
            # Only a patch has hunks. Offering a selection on anything else
            # would be a control with nothing behind it.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"ok": False, "reason_code": "action_has_no_hunks"},
            )
        unknown = unknown_hunk_ids(approved_patch, body.accepted_hunks)
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "ok": False,
                    "reason_code": "unknown_hunk_selection",
                    "unknown_hunks": unknown,
                },
            )
        if not body.accepted_hunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"ok": False, "reason_code": "no_hunk_accepted"},
            )
        store.save_approval_decision_scope(approval_id, body.accepted_hunks)

    # BUG-06 — an approved file mutation is actually performed. The relay needs
    # the approval still `pending` (it claims it atomically), so this runs
    # *before* the metadata-only inbox would resolve it. Everything the inbox
    # checks — critical lifecycle, TTL, payload hash, single resolution — the
    # relay re-checks itself, and it adds the posture check and a fresh gate +
    # policy review of the target at execution time.
    bridge = ApprovalExecutionBridge(store, EventLogWriter(store))
    if (
        body.approve
        and pending_intent_row is None
        and bridge.executes_on_resolution(
            str(approval_row.get("tool_name", "")),
            session.principal_id,
            critical=bool(approval_row.get("critical")),
        )
    ):
        execution = bridge.execute(
            approval_row, principal, session_id=session.session_id, reason=body.reason
        )
        if not execution.ok:
            raise HTTPException(
                status_code=_EXECUTION_ERRORS.get(
                    execution.reason_code or "", status.HTTP_409_CONFLICT
                ),
                detail={"ok": False, "reason_code": execution.reason_code},
            )
        _record_generated_file_attachments_for_turn(
            _ws(request),
            session_id=str(approval_row.get("session_id", "")),
            turn_id=str(approval_row.get("turn_id", "")),
            principal_id=session.principal_id,
        )
        artifacts = {k: v for k, v in execution.artifacts.items() if v is not None}
        return {
            "approval_id": approval_id,
            "action_id": str(approval_row.get("action_id", "")),
            "status": execution.status,
            "executes_action": True,
            "reason": body.reason,
            **_approval_attribution(
                request,
                approval_id,
                user_id=owner_user_id,
                principal_id=session.principal_id,
            ),
            "execution": {
                "capability": execution.capability,
                "path": execution.artifacts.get("path"),
                **{
                    key: execution.artifacts[key]
                    for key in (
                        "returncode",
                        "stdout_bytes",
                        "stderr_bytes",
                        "stdout",
                        "stderr",
                        "truncated",
                        "output_redacted",
                        # BUG-62 — where the thing the owner just approved now
                        # lives, so the surface that took the decision can link
                        # to it instead of saying only that it ran.
                        "receipt",
                        # B11 — what the execution did, in one sentence, for a
                        # capability whose result is neither a file nor a row:
                        # the branch that now exists, the commit that was made.
                        "summary",
                        "checkpoint_capture",
                    )
                    if key in execution.artifacts
                },
            },
            "resume": _record_resume_outcome(
                request,
                store,
                approval_id,
                approval_outcome(
                    approved=True,
                    executed=True,
                    capability=execution.capability,
                    artifacts=artifacts,
                ),
            ),
        }

    try:
        resolution = inbox.resolve(
            approval_id,
            approve=body.approve,
            resolved_by=session.principal_id,
            reason=body.reason,
            user_id=owner_user_id,
        )
    except ValueError as exc:
        code = str(exc)
        raise HTTPException(
            status_code=_RESOLVE_ERRORS.get(code, status.HTTP_400_BAD_REQUEST),
            detail={"ok": False, "reason_code": code},
        ) from exc
    # Connector write intents are the deliberately narrow exception to Raiker's
    # metadata-only approval resolution. The intent is immutable, principal-
    # bound, single-use, and executes only after this exact approval is accepted.
    if pending_intent_row is not None:
        intent = dict(pending_intent_row)
        if not body.approve:
            with store.connect() as connection:
                connection.execute(
                    "UPDATE connector_write_intents SET status='denied' WHERE intent_id=? AND status='pending_approval'",
                    (intent["intent_id"],),
                )
        else:
            with store.connect() as connection:
                claimed = connection.execute(
                    "UPDATE connector_write_intents SET status='executing' WHERE intent_id=? AND status='pending_approval'",
                    (intent["intent_id"],),
                )
            if claimed.rowcount != 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"ok": False, "reason_code": "connector_intent_already_consumed"},
                )
            try:
                output = await ConnectorInvoker(store).invoke(
                    session.principal_id,
                    str(intent["connector_id"]),
                    str(intent["operation_id"]),
                    json.loads(intent["arguments_json"]),
                )
            except (ValueError, json.JSONDecodeError) as exc:
                with store.connect() as connection:
                    connection.execute(
                        "UPDATE connector_write_intents SET status='failed', executed_at=? WHERE intent_id=?",
                        (utc_now(), intent["intent_id"]),
                    )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"ok": False, "reason_code": str(exc)},
                ) from exc
            with store.connect() as connection:
                connection.execute(
                    "UPDATE connector_write_intents SET status='executed', executed_at=? WHERE intent_id=?",
                    (utc_now(), intent["intent_id"]),
                )
            return {
                "approval_id": resolution.approval_id,
                "action_id": resolution.action_id,
                "status": "executed",
                "executes_action": True,
                "reason": body.reason,
                **_approval_attribution(
                    request,
                    approval_id,
                    user_id=owner_user_id,
                    principal_id=session.principal_id,
                ),
                "connector_result": output,
                "resume": _record_resume_outcome(
                    request,
                    store,
                    approval_id,
                    approval_outcome(
                        approved=True, executed=True, capability="connector_write"
                    ),
                ),
            }
    return {
        "approval_id": resolution.approval_id,
        "action_id": resolution.action_id,
        "status": resolution.status,
        "executes_action": resolution.executes_action,
        "reason": body.reason,
        **_approval_attribution(
            request,
            approval_id,
            user_id=owner_user_id,
            principal_id=session.principal_id,
        ),
        # B2 — the decision closes the tool call the model is still waiting on,
        # so a parked turn can pick up from here. Rejection is carried through as
        # a refusal rather than silence, which is what lets the model react.
        "resume": _record_resume_outcome(
            request,
            store,
            approval_id,
            approval_outcome(
                approved=body.approve,
                executed=False,
                capability=executable_capability(str(approval_row.get("tool_name", "")))
                or str(approval_row.get("tool_name", "")),
            ),
        ),
    }


# B2 — resolving an approval unblocks the turn that proposed the action; these
# two routes are how it picks up again. The parked conversation itself never
# leaves the machine: both return an AgentResponse, exactly like a fresh turn.
_RESUME_ERRORS = {
    "suspended_turn_not_found": status.HTTP_404_NOT_FOUND,
    "suspended_turn_already_resumed": status.HTTP_409_CONFLICT,
    "approval_not_resolved": status.HTTP_409_CONFLICT,
    "suspended_turn_unreadable": status.HTTP_409_CONFLICT,
}


def _resume_error(exc: TurnSuspensionError) -> HTTPException:
    code = str(exc)
    return HTTPException(
        status_code=_RESUME_ERRORS.get(code, status.HTTP_409_CONFLICT),
        detail={"ok": False, "reason_code": code},
    )


@router.post("/api/approvals/{approval_id}/resume")
async def resume_after_approval(
    approval_id: str,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Continue the turn this approval blocked, once it has been resolved."""
    session, _principal = _auth_data
    gateway = AgentGateway(_ws(request), principal_id=session.principal_id)
    try:
        response = await gateway.aresume_after_approval(approval_id)
    except TurnSuspensionError as exc:
        raise _resume_error(exc) from exc
    return response.to_dict()


@router.post("/api/approvals/{approval_id}/resume/stream")
async def stream_resume_after_approval(
    approval_id: str,
    request: Request,
    _auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> StreamingResponse:
    """Stream the continuation, so it lands in the transcript as it happens."""
    session, _principal = _auth_data
    gateway = AgentGateway(_ws(request), principal_id=session.principal_id)
    try:
        stream = gateway.astream_resume_after_approval(approval_id)
        first = await stream.__anext__()
    except TurnSuspensionError as exc:
        raise _resume_error(exc) from exc
    except StopAsyncIteration:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"ok": False, "reason_code": "suspended_turn_produced_no_events"},
        ) from None

    async def gen() -> AsyncIterator[str]:
        yield _sse(first)
        async for event in stream:
            yield _sse(event)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/api/approvals/{approval_id}/resolve-critical")
async def resolve_critical_approval(
    approval_id: str,
    body: ResolveApprovalRequest,
    request: Request,
) -> dict[str, Any]:
    """Resolve a critical approval only through a fresh elevated API session."""
    session, principal = AuthMiddleware(_ws(request)).authenticate(request, required_scope="elevated")
    store = SQLiteStore(_ws(request))
    user_id = store.principal_user_id(session.principal_id)
    approval = store.load_approval(approval_id, user_id=user_id)
    if approval is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"ok": False, "reason_code": "approval_not_found"},
        )
    if not approval.get("critical"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "reason_code": "not_a_critical_approval"},
        )

    result = RuntimeAuthority(store, EventLogWriter(store)).resolve_critical_approval(
        approval_id,
        principal,
        approve=body.approve,
        step_up_verified=True,
        session_id=session.session_id,
        reason=body.reason,
    )
    current = store.load_approval(approval_id, user_id=user_id)
    return {
        "approval_id": approval_id,
        "status": str((current or approval).get("status", "pending")),
        "decision": result.decision,
        "message": result.message,
        "executes_action": result.message == "critical_action_executed",
    }
