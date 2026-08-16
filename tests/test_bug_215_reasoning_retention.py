"""BUG-215 — reasoning was shown live and then forgotten.

With **Thinking** on, a turn streamed the model's own working into a collapsed
block above the answer. Re-open the conversation and the block was gone: the
answer was there, and nothing said working had ever been produced. The turn
rendered from stored messages, and there was nowhere for reasoning to be stored.

Persisting it is a *retention* decision before it is a rendering one — the
model's working can restate anything the prompt contained — so these tests hold
the posture as well as the plumbing:

* **How much** working a turn produced is always recorded. It is a count, not
  content, and it is what lets a re-opened turn say the working was not kept
  rather than imply the turn never thought.
* **The working itself** is written only when the owner turned retention on.
* Retained working never becomes searchable conversation content, and never
  leaves in an exported transcript.
"""

from __future__ import annotations

import json
from pathlib import Path

from raiker.contracts.ids import new_id, utc_now
from raiker.sessions.transcript import build_transcript
from raiker.storage.sqlite import SQLiteStore


def _turn(store: SQLiteStore) -> tuple[str, str]:
    session_id = new_id("sess_")
    turn_id = new_id("turn_")
    store.create_session(session_id, str(store.paths.workspace_root))
    store.insert_turn(session_id, turn_id, "Plan the migration")
    store.complete_turn(turn_id, "completed", "Here is the plan.")
    return session_id, turn_id


def test_a_turn_that_produced_no_working_records_none(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    _session_id, turn_id = _turn(store)

    row = store.load_turn(turn_id)

    assert row is not None
    assert row["reasoning_chars"] == 0
    assert row["reasoning_text"] is None


def test_the_amount_of_working_is_recorded_even_when_the_text_is_not(
    tmp_path: Path,
) -> None:
    """The honest middle case: it thought, and that thinking was not kept."""
    store = SQLiteStore(tmp_path)
    _session_id, turn_id = _turn(store)

    store.record_turn_reasoning(turn_id, chars=420, text=None)

    row = store.load_turn(turn_id)
    assert row is not None
    assert row["reasoning_chars"] == 420
    assert row["reasoning_text"] is None


def test_retention_is_off_until_the_owner_turns_it_on(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    principal_id = "prin_owner"

    assert store.reasoning_retention_enabled(principal_id) is False

    store.put_user_settings(principal_id, json.dumps({"general.language": "en-GB"}), utc_now())
    assert store.reasoning_retention_enabled(principal_id) is False

    store.put_user_settings(
        principal_id, json.dumps({"privacy.retain_reasoning": True}), utc_now()
    )
    assert store.reasoning_retention_enabled(principal_id) is True


def test_a_nested_privacy_object_is_read_as_well_as_the_flat_key(tmp_path: Path) -> None:
    """Both shapes exist in the blob; a setting must not be invisible to one reader."""
    store = SQLiteStore(tmp_path)
    store.put_user_settings(
        "prin_owner", json.dumps({"privacy": {"retain_reasoning": True}}), utc_now()
    )

    assert store.reasoning_retention_enabled("prin_owner") is True


def test_unreadable_settings_fail_closed_towards_not_retaining(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    store.put_user_settings("prin_owner", "{not json", utc_now())

    assert store.reasoning_retention_enabled("prin_owner") is False


def test_kept_working_survives_a_reload(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    _session_id, turn_id = _turn(store)

    store.record_turn_reasoning(turn_id, chars=17, text="I should check the schema first.")

    row = SQLiteStore(tmp_path).load_turn(turn_id)
    assert row is not None
    assert row["reasoning_text"] == "I should check the schema first."


def test_kept_working_is_never_indexed_as_conversation_text(tmp_path: Path) -> None:
    """Retention is not a decision to make the working searchable."""
    store = SQLiteStore(tmp_path)
    session_id, turn_id = _turn(store)
    store.record_turn_reasoning(
        turn_id, chars=40, text="The user mentioned a hovercraft full of eels."
    )
    # A later status change re-syncs the index; the working must still not enter it.
    store.complete_turn(turn_id, "completed", "Here is the plan.")

    with store.connect() as connection:
        rows = connection.execute(
            "SELECT text FROM conversation_fts WHERE turn_id = ?", (turn_id,)
        ).fetchall()

    indexed = " ".join(str(row["text"]) for row in rows)
    assert "hovercraft" not in indexed
    assert "Plan the migration" in indexed
    assert session_id


def test_kept_working_never_leaves_in_an_exported_transcript(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    session_id, turn_id = _turn(store)
    store.record_turn_reasoning(turn_id, chars=40, text="Internal working, not for export.")

    transcript = build_transcript(
        session_id=session_id,
        title="Migration",
        created_at=utc_now(),
        turns=store.list_turns(session_id),
    )

    rendered = json.dumps(transcript.manifest())
    assert "Internal working" not in rendered
    assert "Here is the plan." in rendered


def test_a_resumed_turn_keeps_both_halves_of_its_working(tmp_path: Path) -> None:
    """A parked turn re-enters the same loop under the same turn id.

    The owner watched the reasoning that produced the proposal they approved, and
    the reasoning that followed the decision. Replacing would keep only the
    second half and quietly drop the first.
    """
    store = SQLiteStore(tmp_path)
    _session_id, turn_id = _turn(store)

    store.record_turn_reasoning(turn_id, chars=20, text="Before the approval.")
    store.record_turn_reasoning(turn_id, chars=19, text="After the approval.")

    row = store.load_turn(turn_id)
    assert row is not None
    assert row["reasoning_chars"] == 39
    assert row["reasoning_text"] == "Before the approval.\n\nAfter the approval."


def test_a_resumed_turn_that_thought_only_before_the_decision_keeps_that(
    tmp_path: Path,
) -> None:
    """The second half producing nothing must not erase the first."""
    store = SQLiteStore(tmp_path)
    _session_id, turn_id = _turn(store)
    store.record_turn_reasoning(turn_id, chars=20, text="Before the approval.")

    store.record_turn_reasoning(turn_id, chars=0, text=None)

    row = store.load_turn(turn_id)
    assert row is not None
    assert row["reasoning_chars"] == 20
    assert row["reasoning_text"] == "Before the approval."


def test_the_count_still_grows_when_the_text_is_not_kept(tmp_path: Path) -> None:
    """Retention off, twice: the amount is cumulative and the text stays absent."""
    store = SQLiteStore(tmp_path)
    _session_id, turn_id = _turn(store)

    store.record_turn_reasoning(turn_id, chars=100, text=None)
    store.record_turn_reasoning(turn_id, chars=250, text=None)

    row = store.load_turn(turn_id)
    assert row is not None
    assert row["reasoning_chars"] == 350
    assert row["reasoning_text"] is None
