# SPDX-License-Identifier: Apache-2.0
"""BUG-302 — an event's summary says what that event did.

The defect was not a rendering one. Four events that close a turn each carried
the first two hundred characters of the answer, so the Sessions turn inspector
drew four near-identical rows of one borrowed sentence — for a turn that
declared a table, four copies of the same JSON payload — in a list whose job is
to say what happened, in order.

These tests hold the rule rather than the wording: exactly one of the four
carries the answer, and the other three describe themselves.
"""

from __future__ import annotations

from raiker.events.summaries import (
    ANSWER_BEARING_EVENTS,
    checkpoint_created_summary,
    response_created_summary,
    task_completed_summary,
    turn_closed_summary,
)
from raiker.tasks.history import derive_attempts


def _event(event_type: str, timestamp: str, **payload: object) -> dict[str, object]:
    return {
        "event_id": f"evt_{event_type}_{timestamp}",
        "event_type": event_type,
        "timestamp": timestamp,
        "actor": "test",
        "payload": {"task_id": "t", **payload},
    }


class TestOneEventCarriesTheAnswer:
    def test_only_response_created_is_answer_bearing(self) -> None:
        assert set(ANSWER_BEARING_EVENTS) == {"response_created"}

    def test_response_created_keeps_the_answer_verbatim(self) -> None:
        answer = 'raiker:table {"caption": "City Populations", "columns": ["City", "People"]}'
        assert response_created_summary(answer) == answer

    def test_response_created_is_still_bounded(self) -> None:
        assert len(response_created_summary("x" * 5_000)) == 200

    # The point of the fix, stated as the thing that must not be true again:
    # one answer, four events, four identical rows.
    def test_the_four_closing_events_do_not_say_the_same_thing(self) -> None:
        answer = "The population of Lisbon is about 545,000."
        summaries = [
            response_created_summary(answer),
            checkpoint_created_summary("CLOSED"),
            turn_closed_summary("completed"),
            task_completed_summary("Nightly digest"),
        ]
        assert len(set(summaries)) == 4
        assert sum(1 for line in summaries if answer in line) == 1


class TestEachSummarySaysWhatItDid:
    def test_a_checkpoint_names_the_state_a_restore_would_return_to(self) -> None:
        assert checkpoint_created_summary("CLOSED") == (
            "Recorded a restore point for this turn at CLOSED."
        )

    def test_a_closed_turn_repeats_the_runtime_s_own_word(self) -> None:
        assert turn_closed_summary("failed") == "Turn closed as failed."

    # The event type already says "Task completed"; the summary's job is to name
    # *which* task, which is the convention `raiker.events.otlp` states.
    def test_a_completed_task_names_the_task_rather_than_the_event(self) -> None:
        assert task_completed_summary("Nightly digest") == 'Completed the task \u201cNightly digest\u201d.'
        assert task_completed_summary("") == "Completed an untitled task."

    # A blank fact is a fact this runtime did not have, and the sentence says so
    # rather than reading as a finished sentence with a hole in it.
    def test_a_missing_status_is_named_rather_than_left_blank(self) -> None:
        assert turn_closed_summary("  ") == "Turn closed as an unstated status."
        assert checkpoint_created_summary("") == (
            "Recorded a restore point for this turn at an unnamed state."
        )


class TestTheTaskTimelineStillReadsTheOutcome:
    """The outcome did not move out of reach; it moved out of the wrong column."""

    def test_a_completion_s_outcome_is_the_timeline_s_detail(self) -> None:
        attempts = derive_attempts(
            [
                _event("task_started", "2026-09-18T09:00:00Z"),
                _event(
                    "task_completed",
                    "2026-09-18T09:05:00Z",
                    summary=task_completed_summary("Nightly digest"),
                    outcome_summary="Filed three findings and opened one approval.",
                ),
            ]
        )
        assert attempts[-1].summary == "Filed three findings and opened one approval."

    def test_a_completion_with_no_outcome_still_says_something(self) -> None:
        attempts = derive_attempts(
            [
                _event("task_started", "2026-09-18T09:00:00Z"),
                _event(
                    "task_completed",
                    "2026-09-18T09:05:00Z",
                    summary=task_completed_summary("Nightly digest"),
                    outcome_summary="",
                ),
            ]
        )
        assert attempts[-1].summary == 'Completed the task \u201cNightly digest\u201d.'
