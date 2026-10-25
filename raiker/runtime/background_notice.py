"""TOOL-01 — what happened to this conversation's background commands.

A command started with ``run_command`` in the background used to be known to a
later turn only if the model remembered to poll ``background_run``. Each turn
now starts with one system line naming the background commands of this
conversation that finished since the previous turn began, and those still
running, from the durable run rows. It is Raiker's own record, not workspace
data, and it grants nothing: reading a run's log or stopping it still goes
through ``background_run``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore

#: The most runs one notice names.
MAX_NOTICE_RUNS = 5
_ACTIVE = {"queued", "starting", "running", "finalizing"}


def _previous_turn_started(store: SQLiteStore, session_id: str, turn_id: str) -> str | None:
    with store.connect() as connection:
        row = connection.execute(
            "SELECT created_at FROM turns WHERE session_id = ? AND turn_id != ?"
            " ORDER BY created_at DESC LIMIT 1",
            (session_id, turn_id),
        ).fetchone()
    return str(row["created_at"]) if row else None


def background_notice(
    store: SQLiteStore, runs: list[Any], *, session_id: str, turn_id: str
) -> str | None:
    """One system line about earlier turns' background commands, or None."""
    since = _previous_turn_started(store, session_id, turn_id)
    if since is None:
        return None
    finished: list[str] = []
    running: list[str] = []
    for run in runs:
        if getattr(run, "turn_id", "") == turn_id:
            continue
        state = str(getattr(run.state, "value", run.state))
        label = f"`{run.safe_display}` (run {run.run_id})"
        if state in _ACTIVE:
            running.append(label)
        elif run.completed_at and str(run.completed_at) >= since:
            code = f", exit code {run.exit_code}" if run.exit_code is not None else ""
            finished.append(f"{label} {state}{code}")
    if not finished and not running:
        return None
    lines = ["Background commands in this conversation (Raiker's record; read a log with background_run):"]
    lines += [f"- finished since your last turn: {item}" for item in finished[:MAX_NOTICE_RUNS]]
    lines += [f"- still running: {item}" for item in running[:MAX_NOTICE_RUNS]]
    return "\n".join(lines)
