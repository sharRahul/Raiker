"""Sessions, turns, their events and checkpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from raiker.contracts.views import View
from raiker.control.views.security import IdentityView
from raiker.runtime.typed_parts import ContentPartView


@dataclass(frozen=True)
class SessionView(View):
    session_id: str
    title: str | None
    status: str
    created_at: str
    updated_at: str
    turn_count: int
    # Conversation organisation: a per-session pin/bookmark flag. Organizing
    # label only — grants nothing and changes no authority.
    pinned: bool = False
    # Conversation organisation remainder: per-session tags. Organizing labels
    # only — like `pinned` and `projects`, they grant nothing and change no
    # gate, policy, or authority. The tuple is the normalized, ordered set
    # (deduplicated, lowercase, length/count-capped).
    tags: tuple[str, ...] = ()
    # The organizing project this chat currently sits in, or None. A chat can
    # be moved in or out; the project grants nothing and only bounds the
    # context the chat receives.
    project_id: str | None = None
    # RAIKER-2020 — when this row came from a search, the exchange that matched
    # and the turn it belongs to. Empty on a plain listing. It is what lets a
    # result say *why* it matched rather than only that it did, which is the
    # difference between finding a chat from years ago and recognising it.
    match_snippet: str = ""
    match_turn_id: str = ""
    # Soft-archive state (Control Deck task 3). Archiving is a reversible
    # organizing action — it moves a chat out of the default active list but
    # never deletes transcripts, events, checkpoints, or permissions.
    archived: bool = False
    archived_at: str | None = None
    # Where the session came from: "chat" for a conversation the owner typed,
    # "task" for the server-owned session a task runs in (BUG-10). Provenance
    # only — it grants nothing and hides nothing; a task session stays fully
    # readable here and from Tasks.
    origin: str = "chat"


def _stored_content_parts(summary: Any) -> tuple[ContentPartView, ...]:
    """A stored answer's declared parts, or nothing when it declared none.

    BUG-300. A live turn carries ``content_parts`` because the response object
    derives them; a turn read back from the record is just a string, and every
    surface that reopened one showed the raw ``raiker:table`` fence with its
    JSON. The splitter is pure, so the answer is the same answer split the same
    way — what this adds is that the surfaces reading the record get it too.

    Empty when the answer declared nothing, so the payload for an ordinary turn
    is byte-for-byte what it was and a client that ignores the field sees what
    it always saw.
    """
    from raiker.runtime.typed_parts import content_parts, renders_as_parts

    if not isinstance(summary, str) or not summary:
        return ()
    parts = content_parts(summary)
    if not renders_as_parts(parts):
        return ()
    return tuple(cast(ContentPartView, part.to_dict()) for part in parts)


@dataclass(frozen=True)
class TurnView(View):
    turn_id: str
    session_id: str
    turn_type: str
    status: str
    prompt_text: str | None
    created_at: str
    completed_at: str | None
    summary: str | None
    # BUG-215 — how much working this turn produced, and the working itself when
    # the owner has asked for it to be kept. `reasoning_chars > 0` with
    # `reasoning is None` is the honest "it thought, and that was not kept" case
    # a re-opened turn has to be able to state.
    reasoning_chars: int = 0
    reasoning: str | None = None
    # Backlog #25 - the per-turn tool rows, rebuilt from the durable record.
    # Live, these arrive on the stream and the client assembles them; a reload
    # had no stream and so lost half of what the turn said it did. Rebuilt
    # server-side through the same `raiker.tools.presentation` function the live
    # path uses, so a reloaded row can never say more than the one it replaces.
    tool_rows: tuple[dict[str, Any], ...] = ()
    # BUG-300 - the parts this answer declared, so a turn reopened from the
    # record renders as the table it was rather than as the fence that declared
    # one. Derived here rather than in the browser for the same reason the tool
    # rows above are: the split is part of what the runtime decided the answer
    # was, and two implementations of it would eventually disagree. Empty for
    # every answer that declared nothing, which is nearly all of them.
    content_parts: tuple[ContentPartView, ...] = ()


@dataclass(frozen=True)
class SessionDetailView(View):
    session: SessionView
    turns: tuple[TurnView, ...]


@dataclass(frozen=True)
class EventView(View):
    event_id: str
    session_id: str
    turn_id: str | None
    event_type: str
    actor: str
    timestamp: str
    risk_level: str | None
    summary: str | None
    machine_identity: IdentityView | None = None


@dataclass(frozen=True)
class TurnDetailView(View):
    turn: TurnView
    events: tuple[EventView, ...]


@dataclass(frozen=True)
class CheckpointView(View):
    checkpoint_id: str
    session_id: str
    turn_id: str | None
    task_id: str | None
    checkpoint_type: str
    created_at: str
    summary: str | None
    last_event_id: str | None
    # "Rewind metadata" — flags only; restore execution is not implemented in this runtime.
    can_restore_state: bool
    can_restore_files: bool
