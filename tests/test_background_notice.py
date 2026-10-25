"""TOOL-01 — a turn hears about earlier turns' background commands."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from raiker.runtime.background_notice import background_notice
from raiker.storage.sqlite import SQLiteStore


def _run(run_id: str, turn_id: str, state: str, completed_at: str | None, exit_code: int | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        run_id=run_id, turn_id=turn_id, state=SimpleNamespace(value=state),
        safe_display=f"pytest {run_id}", completed_at=completed_at, exit_code=exit_code,
    )


def test_finished_since_the_last_turn_and_still_running_are_named(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.create_session("s1", str(tmp_path), title="t")
    with store.connect() as connection:
        for turn, at in (("t1", "2026-10-25T10:00:00Z"), ("t2", "2026-10-25T11:00:00Z"), ("t3", "2026-10-25T12:00:00Z")):
            connection.execute(
                "INSERT INTO turns (turn_id, session_id, turn_type, status, prompt_text, created_at)"
                " VALUES (?, ?, 'prompt', 'completed', '', ?)",
                (turn, "s1", at),
            )
    runs = [
        _run("r_old", "t1", "succeeded", "2026-10-25T10:30:00Z", 0),  # before the previous turn: already known
        _run("r_new", "t2", "failed", "2026-10-25T11:30:00Z", 2),
        _run("r_live", "t2", "running", None),
        _run("r_here", "t3", "running", None),  # this turn's own run
    ]
    notice = background_notice(store, runs, session_id="s1", turn_id="t3")
    assert notice is not None
    assert "finished since your last turn: `pytest r_new` (run r_new) failed, exit code 2" in notice
    assert "still running: `pytest r_live`" in notice
    assert "r_old" not in notice and "r_here" not in notice


def test_a_first_turn_or_nothing_to_say_is_silent(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.create_session("s1", str(tmp_path), title="t")
    assert background_notice(store, [], session_id="s1", turn_id="t1") is None
