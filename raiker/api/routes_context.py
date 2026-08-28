"""Owner-guided compaction: summarise this conversation up to a turn I picked.

Compaction already existed, and it was the threshold's decision. A conversation
crossed 90% of the model's context window and Raiker summarised the oldest
exchanges it was allowed to. That is the right default and the wrong *only*
option: the owner is the one who knows that the first forty turns were a
digression and the last four are the work.

This route is the same operation with a different reason for starting. It shares
:class:`ConversationCompactor` with the turn path rather than reimplementing the
summarise-and-record step, so `PreCompact` still decides, the transcript is still
framed as untrusted data, the summary is still bound to an exact turn id, and the
usage is still recorded. A second implementation here would be the second route
into a governed action that `REFERENCE_PLATFORM_COMPATIBILITY.md` §4.5 refuses.

**What it does not do.** It does not delete anything. Compaction changes only the
messages a model is sent; the transcript rows remain the source of truth, so a
range that was summarised is still readable on screen, still exportable, and
still the thing a branch is taken from.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raiker.api.auth import AuthMiddleware
from raiker.api.schemas import CompactConversationRequest
from raiker.api.sessions import ApiSession
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.hooks.factory import dispatcher_for_workspace
from raiker.models.owner_runtime import owner_model_runtime
from raiker.runtime.authority.models import Principal
from raiker.runtime.conversation_compaction import (
    ContextBudgetPlanner,
    ContextCompactionStore,
    ConversationCompactor,
)
from raiker.storage.sqlite import SQLiteStore

router = APIRouter()


def _auth(request: Request) -> tuple[ApiSession, Principal]:
    return AuthMiddleware(request.app.state.workspace_root).authenticate(request)


def _context_capacity(
    store: SQLiteStore, principal_id: str, provider: str, model: str
) -> int | None:
    """What the chosen model advertises, when Raiker knows it."""
    try:
        from raiker.runtime.model_facts_store import ModelFactsStore

        facts_store = ModelFactsStore(store)
        owner_capacity = facts_store.owner_context_capacity(principal_id, provider, model)
        if owner_capacity is not None:
            return owner_capacity[0]
        facts = facts_store.provider_facts(principal_id, provider, model)
    except Exception:  # noqa: BLE001 — an unknown capacity is not a failure
        return None
    return facts.context_window_tokens if facts is not None else None


def _emit_for(
    writer: EventLogWriter, session_id: str
) -> Callable[[str, dict[str, Any]], None]:
    """The same two events the turn path writes, under the same session.

    `actor` and `started_by` are what tell the two apart in the audit log: a
    compaction the owner asked for and one the threshold decided on must both be
    readable, and distinguishable, after the fact.
    """

    def emit(event_type: str, payload: dict[str, Any]) -> None:
        writer.append(
            make_event(
                session_id=session_id,
                turn_id=None,
                event_type=event_type,
                actor="owner",
                payload={**payload, "started_by": "owner"},
            )
        )

    return emit


@router.post("/api/sessions/{session_id}/compact")
async def compact_conversation(
    session_id: str,
    body: CompactConversationRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Summarise everything up to and including ``through_turn_id``.

    Answers 200 with ``compacted: false`` and a reason code when there is nothing
    to do — a mark already covered by an earlier boundary, or one naming no
    completed turn of this conversation. That is a state rather than an error: an
    owner who asks for something already true has not made a bad request.
    """
    session, _principal = auth_data
    store = SQLiteStore(request.app.state.workspace_root)
    row = store.load_session(session_id)
    user_id = store.principal_user_id(session.principal_id)
    if row is None or row.get("user_id") not in {None, user_id}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown session")

    principal_id = session.principal_id
    writer = EventLogWriter(store)
    router_, (provider, model) = owner_model_runtime(store, principal_id, writer)
    capacity = _context_capacity(store, principal_id, provider, model)
    compactions = ContextCompactionStore(store)
    active = compactions.active(principal_id, session_id)
    plan = ContextBudgetPlanner().plan_through(
        store=store,
        session_id=session_id,
        capacity_tokens=capacity,
        # No turn is running, so there are no system messages and no prompt to
        # add. The estimate is therefore of the stored conversation alone, which
        # is what the owner is choosing to shorten.
        fixed_messages=(),
        current_prompt="",
        latest_compaction=active,
        through_turn_id=body.through_turn_id,
    )
    if not plan.should_compact:
        return {
            "session_id": session_id,
            "compacted": False,
            "reason_code": "nothing_to_summarise",
        }

    outcome = await ConversationCompactor(
        store,
        router_,
        hook_dispatcher=dispatcher_for_workspace(
            store, writer=writer, acting_principal_id=principal_id
        ),
        # The same two events the turn path writes, under the same session, with
        # the actor naming who asked. A compaction the owner started and one the
        # threshold started must be equally readable in the audit log.
        emit=_emit_for(writer, session_id),
    ).run(
        owner_principal_id=principal_id,
        session_id=session_id,
        turn_id=None,
        client=None,
        provider=provider,
        model=model,
        capacity_tokens=capacity,
        plan=plan,
        active=active,
    )
    if outcome.record is None:
        # The reason is the owner's to see: a hook refused, or the model did not
        # answer. Both are recorded as a failed compaction either way.
        return {
            "session_id": session_id,
            "compacted": False,
            "reason_code": outcome.reason_code or "compaction_unavailable",
        }
    return {
        "session_id": session_id,
        "compacted": True,
        "through_turn_id": outcome.record.through_turn_id,
        "source_turn_count": outcome.record.source_turn_count,
        "estimated_summary_tokens": outcome.record.estimated_summary_tokens,
        "provider": outcome.record.provider,
        "model": outcome.record.model,
        "created_at": outcome.record.created_at,
    }


__all__ = ["router"]
