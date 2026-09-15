"""A turn can say what a part of its answer *is*, and be held to it.

BUG-288. The renderer could already draw a table and highlight code — from
characters that happened to parse. Nothing knew the result was a table, so
nothing could sort it or announce it as one, and there was no chart at all.

The channel is the fence; the deliverable is the validation. A model-proposed
payload is a thing a model can propose, so every dimension is bounded and every
failure is a *refusal with a reason* rather than a repair. These hold that line:
a row short of a cell is refused rather than padded, a series short of a point
is refused rather than aligned by guessing, and nothing is ever truncated
silently.
"""

from __future__ import annotations

import json

import pytest

from raiker.contracts.models import AgentResponse
from raiker.runtime.typed_parts import (
    MAX_CELL_CHARS,
    MAX_PARTS,
    MAX_ROWS,
    MAX_SERIES,
    PART_CHART,
    PART_REFUSED,
    PART_TABLE,
    PART_TEXT,
    content_parts,
    has_typed_part,
)


def _fence(kind: str, payload: object) -> str:
    return f"```raiker:{kind}\n{json.dumps(payload)}\n```"


TABLE = {
    "caption": "Spend by provider",
    "columns": ["Provider", "Spend"],
    "rows": [["Anthropic", "4.10"], ["Ollama", "0.00"]],
}
CHART = {
    "kind": "bar",
    "caption": "Turns per day",
    "y_label": "Turns",
    "labels": ["Mon", "Tue"],
    "series": [{"name": "Chat", "values": [3, 5]}],
}


# ── An ordinary answer is unchanged ─────────────────────────────────────────


def test_an_answer_that_declares_nothing_is_one_text_part() -> None:
    """Most turns. Nothing about them may change, or this is a rewrite of the
    renderer rather than an addition to it."""
    parts = content_parts("Here is a **plain** answer.\n\n| a | b |\n|---|---|\n| 1 | 2 |")
    assert [p.type for p in parts] == [PART_TEXT]
    assert parts[0].text.endswith("| 1 | 2 |")
    assert has_typed_part(parts) is False


def test_a_markdown_table_is_still_only_a_markdown_table() -> None:
    """The finding, stated as a test: pipes and dashes are not a declaration.

    A renderer that promoted this to a typed table would be guessing, which is
    the behaviour the channel exists to replace rather than to formalise.
    """
    parts = content_parts("| Provider | Spend |\n|---|---|\n| Anthropic | 4.10 |")
    assert [p.type for p in parts] == [PART_TEXT]


def test_an_unknown_raiker_type_is_left_in_the_prose() -> None:
    """A newer build's part type degrades to visible text, not to a refusal.

    An owner cannot act on "this build does not know that type yet", and the
    content is still there to read.
    """
    parts = content_parts(f"Before\n\n{_fence('timeline', {'x': 1})}\n\nAfter")
    assert [p.type for p in parts] == [PART_TEXT]
    assert "raiker:timeline" in parts[0].text


# ── A declared part is typed ────────────────────────────────────────────────


def test_a_declared_table_becomes_a_table_between_its_prose() -> None:
    parts = content_parts(f"Spending so far.\n\n{_fence('table', TABLE)}\n\nThat is everything.")
    assert [p.type for p in parts] == [PART_TEXT, PART_TABLE, PART_TEXT]
    assert parts[1].data["columns"] == ["Provider", "Spend"]
    assert parts[1].data["rows"] == [["Anthropic", "4.10"], ["Ollama", "0.00"]]
    assert parts[1].data["caption"] == "Spend by provider"
    assert has_typed_part(parts) is True


def test_a_declared_chart_carries_numbers_and_not_strings() -> None:
    parts = content_parts(_fence("chart", CHART))
    assert [p.type for p in parts] == [PART_CHART]
    assert parts[0].data["series"] == [{"name": "Chat", "values": [3.0, 5.0]}]
    assert parts[0].data["labels"] == ["Mon", "Tue"]


def test_numbers_and_booleans_become_cells_a_table_can_show() -> None:
    """A cell is text by the time it reaches a browser. Coercing here rather
    than in the renderer keeps one answer to "what is in this cell"."""
    parts = content_parts(
        _fence("table", {"columns": ["n", "ok"], "rows": [[3, True], [4.5, False]]})
    )
    assert parts[0].data["rows"] == [["3", "yes"], ["4.5", "no"]]


# ── Every failure is a refusal with a reason ────────────────────────────────


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({"columns": ["a", "b"], "rows": [["1"]]}, "table_row_width_mismatch"),
        ({"columns": [], "rows": []}, "table_columns_missing"),
        ({"columns": ["a"], "rows": "no"}, "table_rows_missing"),
        ({"columns": ["a"], "rows": [["x"]], "caption": "x" * 400}, "table_caption_invalid"),
        ({"columns": ["a"], "rows": [[{"deep": 1}]]}, "table_cell_not_text"),
        ({"columns": ["a"], "rows": [["y" * (MAX_CELL_CHARS + 1)]]}, "table_cell_not_text"),
        ({"columns": ["a"], "rows": [["x"] for _ in range(MAX_ROWS + 1)]}, "table_too_many_rows"),
        ({"columns": [f"c{i}" for i in range(20)], "rows": []}, "table_too_many_columns"),
    ],
)
def test_a_table_raiker_cannot_stand_behind_is_refused(payload: dict, reason: str) -> None:
    """Refused, not repaired. A padded row is a cell nobody wrote, in a table an
    owner may act on."""
    parts = content_parts(_fence("table", payload))
    assert [p.type for p in parts] == [PART_REFUSED]
    assert parts[0].reason_code == reason


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({"labels": ["a", "b"], "series": [{"name": "s", "values": [1]}]},
         "chart_series_length_mismatch"),
        ({"kind": "pie", "labels": ["a"], "series": [{"name": "s", "values": [1]}]},
         "chart_kind_unsupported"),
        ({"labels": [], "series": []}, "chart_labels_missing"),
        ({"labels": ["a"], "series": [{"name": "s", "values": ["3"]}]},
         "chart_value_not_a_number"),
        ({"labels": ["a"], "series": [{"name": "s", "values": [True]}]},
         "chart_value_not_a_number"),
        ({"labels": ["a"],
          "series": [{"name": f"s{i}", "values": [1]} for i in range(MAX_SERIES + 1)]},
         "chart_too_many_series"),
    ],
)
def test_a_chart_raiker_cannot_stand_behind_is_refused(payload: dict, reason: str) -> None:
    parts = content_parts(_fence("chart", payload))
    assert [p.type for p in parts] == [PART_REFUSED]
    assert parts[0].reason_code == reason


def test_malformed_json_is_refused_and_the_prose_around_it_survives() -> None:
    """The refusal replaces the block, never the answer."""
    parts = content_parts("Here it is.\n\n```raiker:table\n{not json}\n```\n\nAnd that is all.")
    assert [p.type for p in parts] == [PART_TEXT, PART_REFUSED, PART_TEXT]
    assert parts[1].reason_code == "table_not_json"
    assert parts[2].text.strip() == "And that is all."


def test_too_many_declared_parts_are_refused_rather_than_dropped() -> None:
    """A turn that emits a hundred tables is not answering a question, and the
    ceiling says so instead of silently keeping the first twelve."""
    message = "\n\n".join(_fence("table", TABLE) for _ in range(MAX_PARTS + 3))
    parts = content_parts(message)
    assert sum(1 for p in parts if p.type == PART_TABLE) == MAX_PARTS
    refusals = [p for p in parts if p.type == PART_REFUSED]
    assert len(refusals) == 3
    assert {p.reason_code for p in refusals} == {"too_many_parts"}


# ── The response carries them, and cannot disagree with itself ──────────────


def test_a_response_derives_its_parts_from_its_own_message() -> None:
    """Derived in `AgentResponse.__post_init__` rather than at each of the six
    sites that build one: a site that forgot would ship a turn whose typed half
    silently disappeared."""
    response = AgentResponse(
        request_id="req_1",
        session_id="sess_1",
        turn_id="turn_1",
        status="completed",
        message=f"Costs:\n\n{_fence('table', TABLE)}",
    )
    kinds = [part["type"] for part in response.content_parts]
    assert kinds == [PART_TEXT, PART_TABLE]
    assert response.content_parts[1]["data"]["columns"] == ["Provider", "Spend"]


def test_an_ordinary_response_carries_exactly_one_text_part() -> None:
    response = AgentResponse(
        request_id="req_1",
        session_id="sess_1",
        turn_id="turn_1",
        status="completed",
        message="A plain answer.",
    )
    assert [part["type"] for part in response.content_parts] == [PART_TEXT]
    assert response.content_parts[0]["text"] == "A plain answer."


def test_the_model_is_told_the_channel_exists() -> None:
    """A mechanism a model is not told about is one it does not use — the same
    reason `tool_search` and `update_plan` are named in the prompt."""
    from raiker.runtime.orchestrator import _SYSTEM_PROMPT

    assert "raiker:table" in _SYSTEM_PROMPT
    assert "raiker:chart" in _SYSTEM_PROMPT


def test_a_surface_that_renders_parts_takes_the_typed_route_for_a_refusal() -> None:
    """BUG-300 — the refusal is the difference between the two predicates.

    ``has_typed_part`` answers "is there content here", and a refusal is not
    content: nothing was accepted. ``renders_as_parts`` answers the question
    every reopening surface actually asks — "do I render the parts or the raw
    text" — and there a refusal must count, or a surface silently prints the
    fence the runtime already refused.
    """
    from raiker.runtime.typed_parts import renders_as_parts

    refused = content_parts(_fence("table", {"columns": ["a"], "rows": [["x", "y"]]}))
    assert [part.type for part in refused] == [PART_REFUSED]
    assert has_typed_part(refused) is False
    assert renders_as_parts(refused) is True

    plain = content_parts("Nothing declared here.")
    assert renders_as_parts(plain) is False


class TestAStoredTurnIsReopenedAsThePartsItDeclared:
    """BUG-300 — a reopened turn answers in the shapes it answered in.

    ``AgentResponse`` derives the parts, so a *live* turn always carried them.
    Every surface that reads the record — a reloaded conversation, the Sessions
    inspector — held a string, and printed the fence with its JSON where the
    conversation had shown a table. The split is the runtime's either way.
    """

    def test_a_stored_answer_that_declared_a_table_carries_its_parts(self) -> None:
        from raiker.control.dashboard import _stored_content_parts

        parts = _stored_content_parts(f"Spending so far.\n\n{_fence('table', TABLE)}")
        assert [part["type"] for part in parts] == [PART_TEXT, PART_TABLE]
        assert parts[1]["data"]["columns"] == ["Provider", "Spend"]

    def test_a_stored_answer_that_declared_nothing_carries_nothing(self) -> None:
        """An ordinary turn's payload is what it always was, byte for byte."""
        from raiker.control.dashboard import _stored_content_parts

        assert _stored_content_parts("A plain answer.") == ()
        assert _stored_content_parts(None) == ()
        assert _stored_content_parts("") == ()

    def test_a_stored_refusal_is_carried_rather_than_printed_as_a_fence(self) -> None:
        from raiker.control.dashboard import _stored_content_parts

        parts = _stored_content_parts(_fence("chart", {"kind": "pie", "labels": ["a"]}))
        assert [part["type"] for part in parts] == [PART_REFUSED]
        assert parts[0]["reason_code"] == "chart_kind_unsupported"
