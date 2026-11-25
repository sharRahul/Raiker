"""RU-10 — a proposal names the turn it came from, so Chat can offer it in place."""

from __future__ import annotations

from raiker.api.wire.memory import memory_proposal


def test_a_proposal_names_its_conversation_and_turn() -> None:
    wire = memory_proposal(
        {
            "candidate_id": "memcand_1",
            "text": "My dentist is Dr. Okafor",
            "decision": "deferred",
            "source_session_id": "sess_1",
            "source_turn_id": "turn_1",
            "source_role": "assistant",
        }
    )
    assert wire["source_role"] == "assistant"
    assert wire["source_session_id"] == "sess_1"
    assert wire["source_turn_id"] == "turn_1"


def test_a_correction_or_import_has_no_turn() -> None:
    wire = memory_proposal({"candidate_id": "memcand_2", "text": "x"})
    assert (wire["source_session_id"], wire["source_turn_id"]) == ("", "")
