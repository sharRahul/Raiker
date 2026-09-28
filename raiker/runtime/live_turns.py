"""The turns running in this process right now (GEP-02).

**Why this exists.** The owner's answer to GEP-02 (2026-09-27): the stop switch
stops *everything currently being performed* — a chat answer being written, a
Build turn, a routine, a task — whether or not the work leaves the machine.

Tasks were always reachable: they are rows with a status. A turn is not. A
chat or Build turn runs inside the request that asked for it, and the only way
to stop one was to name its conversation — so the stop switch, which reads the
task list, could not see the answer the owner was watching stream and could
never stop it.

This registry is that list. A turn enters when the agent loop starts and leaves
when the loop ends, however it ends — finished, failed, stopped, or abandoned by
a client that disconnected. Nothing here stops anything: the stop is still the
governed turn control the conversation's own Stop button writes, honoured at the
turn's next safe boundary. This only answers *which conversations have a turn to
stop*.

Keyed by workspace, because one process can host several instances and a stop
pressed in one must not reach another's turns.
"""
from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from raiker.contracts.ids import utc_now

__all__ = ["LiveTurn", "live_turn", "live_turns"]


@dataclass(frozen=True)
class LiveTurn:
    workspace: str
    session_id: str
    turn_id: str
    #: The principal whose turn controls this turn reads — the one a stop must
    #: be written under for the turn to see it.
    control_principal_id: str
    started_at: str


_LOCK = threading.Lock()
_LIVE: dict[tuple[str, str, str], LiveTurn] = {}


def _key(workspace: str | Path) -> str:
    return str(Path(workspace).resolve())


@contextmanager
def live_turn(
    workspace: str | Path, session_id: str, turn_id: str, control_principal_id: str
) -> Iterator[LiveTurn]:
    turn = LiveTurn(
        workspace=_key(workspace),
        session_id=session_id,
        turn_id=turn_id,
        control_principal_id=control_principal_id,
        started_at=utc_now(),
    )
    ident = (turn.workspace, session_id, turn_id)
    with _LOCK:
        _LIVE[ident] = turn
    try:
        yield turn
    finally:
        with _LOCK:
            # Only remove the entry this context put there: a resumed turn can
            # re-enter under the same identity while the first is unwinding.
            if _LIVE.get(ident) is turn:
                del _LIVE[ident]


def live_turns(workspace: str | Path) -> list[LiveTurn]:
    """Every turn running in *workspace*, oldest first."""
    key = _key(workspace)
    with _LOCK:
        turns = [turn for turn in _LIVE.values() if turn.workspace == key]
    return sorted(turns, key=lambda turn: turn.started_at)
