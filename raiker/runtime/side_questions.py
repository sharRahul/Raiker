from __future__ import annotations

from raiker.contracts.ids import new_id
from raiker.contracts.models import SideQuestionTurn
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter


class SideQuestionRuntime:
    def __init__(self, writer: EventLogWriter | None = None) -> None:
        self.writer = writer

    def answer_read_only(self, *, session_id: str, parent_turn_id: str, question: str, answer: str) -> SideQuestionTurn:
        turn = SideQuestionTurn(new_id("turn_"), parent_turn_id, session_id, question, answer)
        if self.writer:
            self.writer.append(make_event(session_id=session_id, turn_id=turn.child_turn_id, event_type="side_question_received", actor="runtime", payload={"parent_turn_id": parent_turn_id, "read_only": True}))
            self.writer.append(make_event(session_id=session_id, turn_id=turn.child_turn_id, event_type="side_question_answered", actor="runtime", payload=turn.to_dict()))
        return turn
