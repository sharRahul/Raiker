"""The visual answer vocabulary: each block validated, refused with a reason, or shown as text.

Quiet UI plan 04 (QUI-A01 to A07). Every new block follows the path the table
and chart already take — fence, runtime validation, ``ContentPart``, component —
and these hold the rules the plan adds on top: the runtime, not the model,
marks the best value in a comparison; every figure has a unit; numbers with no
source are shown as text; and a small local model is asked once to correct a
block the runtime refused.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from raiker.contracts.models import ContractValidationError, PromptOptions
from raiker.models.contracts import ModelResponse
from raiker.runtime.orchestrator import _SYSTEM_PROMPT, _system_messages
from raiker.runtime.typed_parts import (
    PART_CALLOUT,
    PART_CHART,
    PART_COMPARE,
    PART_FIGURES,
    PART_MEASURE,
    PART_PROSCONS,
    PART_REFUSED,
    PART_STEPS,
    PART_TEXT,
    UNSOURCED_NOTE,
    as_text,
    content_parts,
    renders_as_parts,
)
from raiker.sessions.transcript import _block_table, render_markdown
from tests.test_model_tool_call_loop import FakeRouter, _envelope, _events, _handle, _orchestrator


def _fence(kind: str, payload: object) -> str:
    return f"```raiker:{kind}\n{json.dumps(payload)}\n```"


def _one(kind: str, payload: object):  # type: ignore[no-untyped-def]
    parts = content_parts(f"Intro.\n\n{_fence(kind, payload)}\n\nOutro.")
    assert len(parts) == 3, parts
    return parts[1]


FIGURES = {
    "items": [
        {"label": "Longest battery", "value": 18, "unit": "h", "of": "MacBook Air"},
        {"label": "Lightest", "value": 1.09, "unit": "kg", "of": "X1 Carbon", "estimate": True},
    ],
    "source": "Manufacturer spec pages, checked 23 Oct 2026",
}
COMPARE = {
    "caption": "Laptops for working on the move",
    "items": ["MacBook Air 13", "Dell XPS 13", "ThinkPad X1"],
    "rows": [
        {"label": "Battery", "unit": "h", "better": "higher", "values": [18, 13, 15]},
        {"label": "Weight", "unit": "kg", "better": "lower", "values": [1.24, 1.19, 1.09]},
        {"label": "Price", "unit": "£", "better": "lower", "values": [999, 999, 1399]},
        {"label": "Ports", "values": ["2 × USB-C", "2 × USB-C", "HDMI, USB-A"]},
    ],
    "source": "Manufacturer spec pages",
}


# ── Key figures (QUI-A04) ───────────────────────────────────────────────────


def test_key_figures_carry_their_units_and_owners() -> None:
    part = _one("figures", FIGURES)
    assert part.type == PART_FIGURES
    assert part.data["items"][0] == {
        "label": "Longest battery", "value": 18.0, "unit": "h", "of": "MacBook Air",
        "estimate": False,
    }
    assert part.data["items"][1]["estimate"] is True
    assert part.data["source"].startswith("Manufacturer")


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({"items": []}, "figures_items_missing"),
        ({"items": [{"label": "x", "value": 1, "unit": "h"}] * 5}, "figures_too_many"),
        ({"items": [{"label": "Battery", "value": 18}]}, "figures_unit_missing"),
        ({"items": [{"label": "Battery", "value": 18, "unit": " "}]}, "figures_unit_missing"),
        ({"items": [{"label": "Battery", "value": "18", "unit": "h"}]}, "figures_value_not_a_number"),
        ({"items": [{"label": "Battery", "value": True, "unit": "h"}]}, "figures_value_not_a_number"),
        ({"items": [{"label": "", "value": 1, "unit": "h"}]}, "figures_label_invalid"),
        ({"items": [{"label": "a", "value": 1, "unit": "h"}], "source": 3}, "figures_source_invalid"),
    ],
)
def test_a_figure_without_what_makes_it_a_figure_is_refused(payload: dict, reason: str) -> None:
    part = _one("figures", {"source": "s", **payload})
    assert (part.type, part.reason_code) == (PART_REFUSED, reason)


# ── Comparison (QUI-A05) ────────────────────────────────────────────────────


def test_the_runtime_marks_the_best_value_from_the_stated_rule() -> None:
    part = _one("compare", COMPARE)
    assert part.type == PART_COMPARE
    rows = part.data["rows"]
    assert rows[0]["best"] == [0]  # higher battery is better
    assert rows[1]["best"] == [2]  # lower weight is better
    assert rows[2]["best"] == [0, 1]  # a tie marks both
    assert rows[3]["best"] == []  # no rule, no winner


def test_a_model_cannot_crown_a_winner_itself() -> None:
    payload = json.loads(json.dumps(COMPARE))
    payload["rows"][0]["best"] = [1]
    payload["rows"][3]["best"] = [2]
    part = _one("compare", payload)
    assert part.data["rows"][0]["best"] == [0]
    assert part.data["rows"][3]["best"] == []


def test_a_row_where_every_item_ties_has_no_best() -> None:
    payload = {**COMPARE, "rows": [{"label": "RAM", "unit": "GB", "better": "higher", "values": [16, 16, 16]}]}
    assert _one("compare", payload).data["rows"][0]["best"] == []


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"items": ["Only one"]}, "compare_items_missing"),
        ({"items": [f"i{n}" for n in range(7)]}, "compare_too_many_items"),
        ({"rows": [{"label": "Battery", "values": [1, 2]}]}, "compare_row_width_mismatch"),
        ({"rows": [{"label": "Battery", "better": "best", "values": [1, 2, 3]}]}, "compare_better_invalid"),
        ({"rows": [{"label": "Ports", "better": "higher", "values": ["a", 2, 3]}]}, "compare_better_needs_numbers"),
        ({"rows": [{"label": "Odd", "values": [{"x": 1}, 2, 3]}]}, "compare_value_invalid"),
    ],
)
def test_a_comparison_raiker_cannot_stand_behind_is_refused(change: dict, reason: str) -> None:
    part = _one("compare", {**COMPARE, **change})
    assert (part.type, part.reason_code) == (PART_REFUSED, reason)


# ── Measure, callout, pros and cons, steps (QUI-A06, A07) ───────────────────


def test_a_measure_is_one_value_on_its_scale() -> None:
    part = _one("measure", {"label": "Checks passed", "value": 31, "max": 40, "source": "This run"})
    assert part.type == PART_MEASURE
    assert part.data == {
        "label": "Checks passed", "value": 31.0, "min": 0.0, "max": 40.0, "unit": "",
        "source": "This run", "estimate": False,
    }


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({"label": "Rating", "value": 6, "max": 5}, "measure_value_off_scale"),
        ({"label": "Rating", "value": 4, "max": 0}, "measure_scale_invalid"),
        ({"label": "Rating", "value": 4}, "measure_scale_invalid"),
    ],
)
def test_a_measure_off_its_scale_is_refused(payload: dict, reason: str) -> None:
    part = _one("measure", {"source": "s", **payload})
    assert (part.type, part.reason_code) == (PART_REFUSED, reason)


def test_a_callout_names_its_tone() -> None:
    part = _one("callout", {"tone": "warning", "text": "Battery figures are manufacturer claims."})
    assert (part.type, part.data["tone"]) == (PART_CALLOUT, "warning")
    assert _one("callout", {"tone": "shout", "text": "x"}).reason_code == "callout_tone_invalid"
    assert _one("callout", {"tone": "verdict", "text": ""}).reason_code == "callout_text_invalid"


def test_pros_and_cons_and_steps_validate() -> None:
    pros = _one("proscons", {"options": [{"name": "Air", "pros": ["Battery"], "cons": ["Ports"]}]})
    assert pros.type == PART_PROSCONS
    assert _one("proscons", {"options": [{"name": "Air"}]}).reason_code == "proscons_option_empty"
    steps = _one("steps", {"steps": [{"label": "Order", "when": "Mon"}, {"label": "Set up"}]})
    assert steps.type == PART_STEPS
    assert steps.data["steps"][1] == {"label": "Set up", "when": "", "text": ""}
    assert _one("steps", {"steps": [{"label": str(n)} for n in range(13)]}).reason_code == "steps_too_many"


# ── New chart kinds (QUI-A01 to A03) ────────────────────────────────────────


def _chart(kind: str, series: list[dict]) -> dict:
    return {"kind": kind, "caption": "c", "labels": ["A", "B"], "series": series}


def test_the_new_chart_kinds_are_accepted() -> None:
    for kind in ("hbar", "stacked"):
        assert _one("chart", _chart(kind, [{"name": "s", "values": [1, 2]}])).type == PART_CHART
    scatter = _chart("scatter", [{"name": "Price", "values": [999, 1399]}, {"name": "Battery", "values": [18, 15]}])
    assert _one("chart", scatter).data["kind"] == "scatter"


@pytest.mark.parametrize(
    ("kind", "series", "reason"),
    [
        ("scatter", [{"name": "x", "values": [1, 2]}], "chart_scatter_needs_two_series"),
        ("stacked", [{"name": "x", "values": [1, -2]}], "chart_stacked_negative"),
        ("stacked", [{"name": "x", "values": [1, 0]}], "chart_stacked_empty"),
        ("pie", [{"name": "x", "values": [1, 2]}], "chart_kind_unsupported"),
    ],
)
def test_a_new_chart_kind_holds_its_own_shape(kind: str, series: list[dict], reason: str) -> None:
    part = _one("chart", _chart(kind, series))
    assert (part.type, part.reason_code) == (PART_REFUSED, reason)


# ── Units and sources (04, Rules) ───────────────────────────────────────────


def test_numbers_with_no_source_are_shown_as_text() -> None:
    payload = {k: v for k, v in FIGURES.items() if k != "source"}
    part = _one("figures", payload)
    assert part.type == PART_TEXT
    assert "Longest battery: 18 h (MacBook Air)" in part.text
    assert "1.09 kg (X1 Carbon) (≈ estimate)" in part.text
    assert UNSOURCED_NOTE in part.text


def test_a_text_only_comparison_needs_no_source() -> None:
    payload = {"items": ["A", "B"], "rows": [{"label": "Ports", "values": ["USB-C", "HDMI"]}]}
    assert _one("compare", payload).type == PART_COMPARE


def test_every_block_has_one_text_form() -> None:
    compare = _one("compare", COMPARE)
    text = as_text(compare)
    assert "Battery: MacBook Air 13 18 h (best); Dell XPS 13 13 h; ThinkPad X1 15 h" in text
    assert "Price: MacBook Air 13 £999 (best); Dell XPS 13 £999 (best); ThinkPad X1 £1399" in text
    assert as_text(_one("callout", {"tone": "action", "text": "Buy it."})) == "> **Next step:** Buy it."
    measure = _one("measure", {"label": "Rating", "value": 4.2, "max": 5, "source": "s", "estimate": True})
    assert as_text(measure) == "**Rating**: 4.2 of 5 (≈ estimate)"


def test_an_export_keeps_figures_and_comparisons_as_tables() -> None:
    title, columns, rows = _block_table(_one("compare", COMPARE)) or ("", [], [])
    assert title.startswith("Laptops for working on the move")
    assert columns == ["", "MacBook Air 13", "Dell XPS 13", "ThinkPad X1"]
    assert rows[0] == ["Battery (h)", "18 — Best", "13", "15"]
    assert _block_table(_one("callout", {"tone": "verdict", "text": "x"})) is None


def test_a_surface_takes_the_typed_route_for_every_new_block() -> None:
    for kind, payload in (("figures", FIGURES), ("compare", COMPARE), ("callout", {"text": "x"})):
        assert renders_as_parts(content_parts(_fence(kind, payload)))


def test_markdown_export_renders_new_blocks() -> None:
    from raiker.sessions.transcript import Transcript, TranscriptMessage

    text = _fence("compare", COMPARE) + "\n\n" + _fence("steps", {"steps": [{"label": "Order"}]})
    message = TranscriptMessage(role="raiker", text=text, timestamp="", parts=tuple(content_parts(text)))
    transcript = Transcript(
        session_id="sess_1", title="T", created_at=None, exported_at="now", messages=(message,), files=(),
    )
    out = render_markdown(transcript)
    assert "| Battery (h) | 18 — Best | 13 | 15 |" in out
    assert "1. Order" in out
    assert "raiker:compare" not in out


# ── Answer style and the model's instructions ───────────────────────────────


def test_the_model_is_told_the_whole_vocabulary_and_its_rules() -> None:
    for word in ("raiker:figures", "raiker:compare", "raiker:measure", "raiker:callout",
                 "raiker:proscons", "raiker:steps", "hbar", "scatter", "stacked",
                 "at most three blocks", "source"):
        assert word in _SYSTEM_PROMPT


def test_answer_style_adds_one_sentence_and_auto_adds_none() -> None:
    assert _system_messages("chat", "auto") == [_SYSTEM_PROMPT]
    assert "mostly text" in _system_messages("chat", "text")[-1]
    assert "visual where it helps" in _system_messages("build", "visual")[-1]
    with pytest.raises(ContractValidationError):
        PromptOptions(answer_style="loud")


# ── One corrected block for a local model ───────────────────────────────────

BROKEN = "Here you go.\n\n```raiker:figures\n{\"items\": [{\"label\": \"Battery\", \"value\": 18}]}\n```"
FIXED = "Here you go.\n\n" + _fence("figures", {**FIGURES})


def test_a_local_model_is_asked_once_to_correct_a_refused_block(tmp_path: Path) -> None:
    router = FakeRouter([ModelResponse(text=BROKEN), ModelResponse(text=FIXED)])
    orchestrator = _orchestrator(tmp_path, router)
    orchestrator._turn_provider = lambda envelope: ("ollama", "llama3.2")  # type: ignore[method-assign]
    envelope = _envelope("Compare laptops")
    response = _handle(orchestrator, envelope)
    assert router.calls == 2
    assert "figures_unit_missing" in router.seen_messages[1][-1].content
    assert response.message == FIXED
    assert [part["type"] for part in response.content_parts] == ["text", "figures"]
    assert "typed_block_retry" in _events(orchestrator, envelope.session_id)


def test_the_correction_is_asked_only_once(tmp_path: Path) -> None:
    router = FakeRouter([ModelResponse(text=BROKEN)])
    orchestrator = _orchestrator(tmp_path, router)
    orchestrator._turn_provider = lambda envelope: ("ollama", "llama3.2")  # type: ignore[method-assign]
    response = _handle(orchestrator, _envelope("Compare laptops"))
    assert router.calls == 2
    assert response.content_parts[-1]["type"] == PART_REFUSED


def test_a_hosted_model_is_not_asked_again(tmp_path: Path) -> None:
    router = FakeRouter([ModelResponse(text=BROKEN), ModelResponse(text=FIXED)])
    orchestrator = _orchestrator(tmp_path, router)
    orchestrator._turn_provider = lambda envelope: ("anthropic", "claude")  # type: ignore[method-assign]
    response = _handle(orchestrator, _envelope("Compare laptops"))
    assert router.calls == 1
    assert response.content_parts[-1]["type"] == PART_REFUSED


# ── Answer style as an account setting ──────────────────────────────────────


def test_the_settings_route_keeps_only_an_offered_answer_style(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from raiker.api.app import create_app
    from raiker.api.routes_settings import load_answer_style
    from raiker.cli.principal_resolver import bootstrap_owner

    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    client = TestClient(create_app(tmp_path))
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert load_answer_style(tmp_path, "principal_owner") == "auto"
    refused = client.put("/api/settings", json={"settings": {"chat.answer_style": "loud"}}, headers=headers)
    assert (refused.status_code, refused.json()["detail"]) == (422, "invalid_answer_style")
    saved = client.put("/api/settings", json={"settings": {"chat.answer_style": "visual"}}, headers=headers)
    assert saved.status_code == 200, saved.text
    assert load_answer_style(tmp_path, "principal_owner") == "visual"


def test_a_block_whose_json_opens_on_the_fence_line_is_still_the_block() -> None:
    """Found live (RT-QUI-37): Haiku wrote ```raiker:figures { on one line, and
    the block was drawn as a code sample of itself."""
    text = 'Intro.\n\n```raiker:callout {\n"tone": "verdict", "text": "Pick the Air."\n}\n```\n\nOutro.'
    parts = content_parts(text)
    assert [part.type for part in parts] == [PART_TEXT, PART_CALLOUT, PART_TEXT]
    assert parts[1].data["text"] == "Pick the Air."


def test_blocks_written_entirely_on_their_fence_lines_stay_separate() -> None:
    """Found live (RT-QUI-37, second round): every block's JSON on its fence
    line, closing fence straight after. The first match ran into the next block
    and the whole answer was refused as invalid JSON."""
    text = (
        '```raiker:callout {"tone": "verdict", "text": "One."}\n```\n\n'
        '```raiker:callout {"tone": "warning", "text": "Two."}\n```'
    )
    parts = content_parts(text)
    assert [(part.type, part.data.get("text")) for part in parts] == [
        (PART_CALLOUT, "One."), (PART_CALLOUT, "Two."),
    ]
