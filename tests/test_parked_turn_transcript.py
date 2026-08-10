"""BUG-73 — a transcript must never deny an execution that happened.

One Chat turn on the 2026-08-08 live round proposed ``write_file
live-round.md``. The owner reviewed it, pressed **Approve and execute once**,
and was told "Executed once — wrote live-round.md. The previous contents were
checkpointed." The file was on disk with the reviewed contents and the
conversation carried its chip. The final assistant bubble nonetheless read
"Approval required for local action. No command was executed." — durably, so
reopening the conversation showed the denial again.

The pre-approval sentence is a notice about a *paused state*, not an answer. It
is therefore never persisted as one: the resume overwrites an empty row, and an
interrupted resume leaves the parked approval showing rather than a false claim.
These tests hold that invariant at the layer that writes the transcript, so it
cannot depend on a race being won.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.models import PARKED_FOR_APPROVAL_NOTICE, AgentResponse
from raiker.gateway.agent_gateway import TURN_SUMMARY_MAX_CHARS, AgentGateway
from raiker.storage.sqlite import SQLiteStore


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    return tmp_path


def _response(message: str, status: str = "needs_approval") -> AgentResponse:
    return AgentResponse(
        request_id="req_1",
        session_id="sess_1",
        turn_id="turn_1",
        status=status,
        message=message,
    )


class TestTheNoticeIsNeverStoredAsAnAnswer:
    def test_the_parked_notice_is_not_persisted(self) -> None:
        assert AgentGateway._persisted_summary(_response(PARKED_FOR_APPROVAL_NOTICE)) == ""

    def test_a_real_answer_is_persisted_unchanged(self) -> None:
        assert (
            AgentGateway._persisted_summary(_response("Wrote live-round.md.", "completed"))
            == "Wrote live-round.md."
        )

    def test_a_long_answer_is_still_bounded(self) -> None:
        long_answer = "x" * (TURN_SUMMARY_MAX_CHARS + 500)
        stored = AgentGateway._persisted_summary(_response(long_answer, "completed"))
        assert len(stored) == TURN_SUMMARY_MAX_CHARS

    def test_an_answer_that_merely_mentions_the_notice_is_kept(self) -> None:
        # The guard matches the notice exactly. A model that quotes the sentence
        # while explaining what happened is writing a real answer, and dropping
        # it would be a second way to lose the record.
        message = f"I was told: “{PARKED_FOR_APPROVAL_NOTICE}” — so I waited."
        assert AgentGateway._persisted_summary(_response(message, "completed")) == message


class TestTheStoredTranscriptRowAgreesWithWhatHappened:
    def test_a_parked_turn_stores_no_answer_and_a_resume_writes_the_real_one(
        self, workspace: Path
    ) -> None:
        store = SQLiteStore(workspace)
        store.create_session("sess_1", str(workspace))
        store.insert_turn("sess_1", "turn_1", "write live-round.md")

        # The turn parks. Whatever the client is shown live, the row must not
        # claim anything about execution.
        store.complete_turn(
            "turn_1",
            "needs_approval",
            AgentGateway._persisted_summary(_response(PARKED_FOR_APPROVAL_NOTICE)),
        )
        parked = store.load_turn("turn_1")
        assert parked is not None
        assert (parked["summary"] or "") == ""
        assert PARKED_FOR_APPROVAL_NOTICE not in (parked["summary"] or "")

        # The approval resolves and the same turn resumes, writing the answer
        # over an empty row rather than having to win a race against it.
        store.complete_turn(
            "turn_1",
            "completed",
            AgentGateway._persisted_summary(
                _response(
                    "Wrote live-round.md. The previous contents were checkpointed.",
                    "completed",
                )
            ),
        )
        resumed = store.load_turn("turn_1")
        assert resumed is not None
        assert "Wrote live-round.md." in str(resumed["summary"])

    def test_an_interrupted_resume_leaves_no_claim_either_way(
        self, workspace: Path
    ) -> None:
        # The failure mode BUG-73 actually observed: the resume never completed.
        # The row is then empty, the parked approval still resolves the state for
        # the reader, and nothing durable asserts that no command was executed.
        store = SQLiteStore(workspace)
        store.create_session("sess_2", str(workspace))
        store.insert_turn("sess_2", "turn_2", "write live-round.md")
        store.complete_turn(
            "turn_2",
            "needs_approval",
            AgentGateway._persisted_summary(_response(PARKED_FOR_APPROVAL_NOTICE)),
        )
        row = store.load_turn("turn_2")
        assert row is not None
        assert "No command was executed" not in (row["summary"] or "")
