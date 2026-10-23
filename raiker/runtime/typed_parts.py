"""A turn's answer, as declared parts rather than as characters to guess at.

**Why this exists (BUG-288).** Raiker's renderer already speaks a fair
vocabulary — headings, fenced code, lists, tables, citation chips — and the
product has purpose-built panes beside it. What it did not have was a *typed
channel*. A model's answer was one Markdown string and everything above it was
inferred from the characters: a turn could not say *this part of my answer is a
table of these columns*, only write something that happened to parse as one. And
there was no chart at all, so a turn whose answer was genuinely a shape had to
describe the shape in words.

The order that worked for Design (BUG-277) is the order here: **the channel
first, then the components that draw it.** A chart component with no runtime
producing chart data is the dead-button problem this product refuses everywhere
else.

**The channel.** A turn declares a part by opening a fence with a Raiker type::

    ```raiker:table
    {"caption": "Cost by provider", "columns": ["Provider", "Spend"],
     "rows": [["Anthropic", "$4.10"], ["Ollama", "$0.00"]]}
    ```

The runtime parses it here, validates it the way any action argument is
validated — bounded, typed, and refused rather than coerced — and the response
carries :class:`ContentPart` objects the client renders directly. The fence is
how a model *declares* the type; the part is what the product renders. Those are
different things, and the difference is the whole of the finding: a renderer
guessing from pipes and dashes cannot tell a table from a paragraph that looks
like one, and cannot make it sortable or legible to a screen reader as a table.

**What a malformed block does.** It becomes a ``refused`` part carrying its
reason, and the fence stays in the text exactly as the model wrote it. It is
never dropped: a part that vanishes is a turn whose answer silently lost a
section, and a model that can make a section disappear by writing bad JSON is a
worse failure than a visible refusal.

**Bounds.** Every limit below is a refusal, not a truncation. A table cut to
twenty rows without saying so is a wrong answer presented as a right one.
"""
from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal, cast

from typing_extensions import TypedDict

from raiker.contracts.views import View

# ── Part types ──────────────────────────────────────────────────────────────

#: Ordinary prose. Rendered by the Markdown renderer, exactly as before.
PART_TEXT: Final = "text"
#: A table the product knows is a table: sortable, and announced as one.
PART_TABLE: Final = "table"
#: A series to plot. Bounded and validated like any other model-proposed payload.
PART_CHART: Final = "chart"
#: A declared block the runtime would not accept, with the reason it refused.
PART_REFUSED: Final = "refused"
#: QUI-A04 — up to four headline numbers, each with its unit and what it is of.
PART_FIGURES: Final = "figures"
#: QUI-A05 — items side by side, with the best value per row computed here.
PART_COMPARE: Final = "compare"
#: QUI-A06 — one value on a known scale.
PART_MEASURE: Final = "measure"
#: QUI-A07 — one verdict, warning or recommended action.
PART_CALLOUT: Final = "callout"
#: QUI-A07 — two short lists per option.
PART_PROSCONS: Final = "proscons"
#: QUI-A07 — an ordered or dated sequence.
PART_STEPS: Final = "steps"

#: Every declared block an owner sees as something other than prose.
BLOCK_TYPES = frozenset({
    PART_TABLE, PART_CHART, PART_FIGURES, PART_COMPARE, PART_MEASURE,
    PART_CALLOUT, PART_PROSCONS, PART_STEPS,
})
PART_TYPES = frozenset({PART_TEXT, PART_REFUSED, *BLOCK_TYPES})
PartType = Literal[
    "text", "table", "chart", "refused", "figures", "compare", "measure",
    "callout", "proscons", "steps",
]


class ContentPartView(TypedDict):
    """One declared piece of a turn's answer, as ``raiker.runtime.typed_parts`` serialises it."""

    type: PartType
    text: str
    data: dict[str, Any]
    reason_code: str

#: The chart shapes Raiker draws. Each is a different claim about the data:
#: one measure across items (bar, and hbar when the names are long), change over
#: time (line), a total over time (area), parts of a whole (stacked, drawn as
#: 100% bars instead of a pie) and two measures at once (scatter). A shape
#: nobody can read is not a feature, which is why there is no pie.
CHART_KINDS = ("bar", "hbar", "line", "area", "stacked", "scatter")

# ── Bounds ──────────────────────────────────────────────────────────────────
#
# A model-proposed payload is a thing a model can propose, so every dimension
# has a stated ceiling and exceeding one is a refusal with a reason.

MAX_PARTS = 12
MAX_COLUMNS = 12
MAX_ROWS = 200
MAX_CELL_CHARS = 500
MAX_CAPTION_CHARS = 200
MAX_SERIES = 8
MAX_POINTS = 500
MAX_LABEL_CHARS = 80
MAX_FIGURES = 4
MAX_COMPARE_ITEMS = 6
MAX_COMPARE_ROWS = 20
MAX_UNIT_CHARS = 24
MAX_SOURCE_CHARS = 200
MAX_TEXT_CHARS = 500
MAX_OPTIONS = 4
MAX_LIST_ITEMS = 8
MAX_STEPS = 12

#: A model sometimes opens the JSON on the fence line itself
#: (```` ```raiker:figures { ````), or writes all of it there; ``head`` keeps
#: that part so the block is still the block it declared rather than a code
#: sample of it. The body is optional and lazy, so a fence whose JSON is all on
#: its first line closes on the next line instead of running into the block
#: after it.
_FENCE = re.compile(
    r"^[ \t]*```[ \t]*raiker:(?P<kind>[a-z_]+)[ \t]*(?P<head>[{\[][^\n]*)?"
    r"(?:\n(?P<body>.*?))??\n[ \t]*```[ \t]*$",
    re.S | re.M,
)


@dataclass(frozen=True)
class ContentPart(View):
    """One declared piece of a turn's answer."""

    type: PartType
    #: `text` only: the Markdown run.
    text: str = ""
    #: `table` and `chart`: the validated payload. Never the model's raw object.
    data: dict[str, Any] = field(default_factory=dict)
    #: `refused` only: why this block was not accepted, in a reason code.
    reason_code: str = ""

    def __post_init__(self) -> None:
        if self.type not in PART_TYPES:
            raise ValueError(f"content_part_type_invalid:{self.type}")


def _text(run: str) -> ContentPart | None:
    """A text part, or ``None`` when the run is only whitespace."""
    return ContentPart(PART_TEXT, text=run) if run.strip() else None


def _cell(value: Any) -> str | None:
    """One table cell as a bounded string, or ``None`` when it cannot be one."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value is None:
        return ""
    if isinstance(value, int | float):
        return str(value)
    if not isinstance(value, str):
        return None
    return value if len(value) <= MAX_CELL_CHARS else None


def _validate_table(payload: Any) -> tuple[dict[str, Any] | None, str]:
    """``(data, "")`` or ``(None, reason_code)``.

    Rectangular by construction: a row that is not the width of the header is
    refused rather than padded, because a padded row is a made-up cell and this
    is a table an owner may act on.
    """
    if not isinstance(payload, dict):
        return None, "table_not_an_object"
    columns = payload.get("columns")
    rows = payload.get("rows")
    if not isinstance(columns, list) or not columns:
        return None, "table_columns_missing"
    if len(columns) > MAX_COLUMNS:
        return None, "table_too_many_columns"
    headers: list[str] = []
    for column in columns:
        cell = _cell(column)
        if cell is None:
            return None, "table_column_not_text"
        headers.append(cell)
    if not isinstance(rows, list):
        return None, "table_rows_missing"
    if len(rows) > MAX_ROWS:
        return None, "table_too_many_rows"
    clean: list[list[str]] = []
    for row in rows:
        if not isinstance(row, list):
            return None, "table_row_not_a_list"
        if len(row) != len(headers):
            return None, "table_row_width_mismatch"
        cells: list[str] = []
        for value in row:
            cell = _cell(value)
            if cell is None:
                return None, "table_cell_not_text"
            cells.append(cell)
        clean.append(cells)
    caption = payload.get("caption", "")
    if not isinstance(caption, str) or len(caption) > MAX_CAPTION_CHARS:
        return None, "table_caption_invalid"
    return {"caption": caption, "columns": headers, "rows": clean}, ""


def _validate_chart(payload: Any) -> tuple[dict[str, Any] | None, str]:
    """``(data, "")`` or ``(None, reason_code)``.

    Every series shares the one label axis. Series of differing lengths would
    have to be aligned by guessing which points correspond, and a chart drawn
    from a guess is the thing this channel exists to stop.
    """
    if not isinstance(payload, dict):
        return None, "chart_not_an_object"
    kind = payload.get("kind", "bar")
    if kind not in CHART_KINDS:
        return None, "chart_kind_unsupported"
    labels = payload.get("labels")
    if not isinstance(labels, list) or not labels:
        return None, "chart_labels_missing"
    if len(labels) > MAX_POINTS:
        return None, "chart_too_many_points"
    clean_labels: list[str] = []
    for label in labels:
        cell = _cell(label)
        if cell is None or len(cell) > MAX_LABEL_CHARS:
            return None, "chart_label_invalid"
        clean_labels.append(cell)
    series = payload.get("series")
    if not isinstance(series, list) or not series:
        return None, "chart_series_missing"
    if len(series) > MAX_SERIES:
        return None, "chart_too_many_series"
    clean_series: list[dict[str, Any]] = []
    for entry in series:
        if not isinstance(entry, dict):
            return None, "chart_series_not_an_object"
        name = entry.get("name", "")
        if not isinstance(name, str) or len(name) > MAX_LABEL_CHARS:
            return None, "chart_series_name_invalid"
        values = entry.get("values")
        if not isinstance(values, list) or len(values) != len(clean_labels):
            return None, "chart_series_length_mismatch"
        numbers: list[float] = []
        for value in values:
            if isinstance(value, bool) or not isinstance(value, int | float):
                return None, "chart_value_not_a_number"
            numbers.append(float(value))
        clean_series.append({"name": name, "values": numbers})
    if kind == "scatter" and len(clean_series) != 2:
        # A scatter plots one measure against another, so it is exactly two
        # series: the first is the horizontal axis, the second the vertical.
        return None, "chart_scatter_needs_two_series"
    if kind == "stacked":
        # Parts of a whole: a negative part is not a share of anything, and a
        # label whose parts sum to nothing has no whole to divide.
        if any(value < 0 for entry in clean_series for value in entry["values"]):
            return None, "chart_stacked_negative"
        for index in range(len(clean_labels)):
            if sum(entry["values"][index] for entry in clean_series) <= 0:
                return None, "chart_stacked_empty"
    caption = payload.get("caption", "")
    if not isinstance(caption, str) or len(caption) > MAX_CAPTION_CHARS:
        return None, "chart_caption_invalid"
    y_label = payload.get("y_label", "")
    if not isinstance(y_label, str) or len(y_label) > MAX_LABEL_CHARS:
        return None, "chart_y_label_invalid"
    return {
        "kind": kind,
        "caption": caption,
        "y_label": y_label,
        "labels": clean_labels,
        "series": clean_series,
    }, ""


def _short(value: Any, limit: int, *, required: bool = False) -> str | None:
    """A bounded string, ``""`` when absent and allowed, or ``None`` when unusable."""
    if value is None and not required:
        return ""
    if not isinstance(value, str) or len(value) > limit:
        return None
    if required and not value.strip():
        return None
    return value


def _number_value(value: Any) -> float | None:
    """A real number, or ``None``. ``True`` is not one, whatever Python thinks."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if number == number and abs(number) != float("inf") else None


def _provenance(payload: dict[str, Any], kind: str) -> tuple[dict[str, Any] | None, str]:
    """The block's ``source`` and ``estimate``: where its numbers came from.

    Both are what the owner reads beside the numbers, so both are bounded and
    typed like everything else. Whether a missing source turns the block into
    text is :func:`content_parts`'s decision, not this one's.
    """
    source = _short(payload.get("source"), MAX_SOURCE_CHARS)
    if source is None:
        return None, f"{kind}_source_invalid"
    estimate = payload.get("estimate", False)
    if not isinstance(estimate, bool):
        return None, f"{kind}_estimate_invalid"
    return {"source": source.strip(), "estimate": estimate}, ""


def _validate_figures(payload: Any) -> tuple[dict[str, Any] | None, str]:
    """QUI-A04. Up to four headline numbers, each with a unit and a label.

    The unit is required: "18" is not a figure an owner can act on, "18 h" is.
    """
    if not isinstance(payload, dict):
        return None, "figures_not_an_object"
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return None, "figures_items_missing"
    if len(items) > MAX_FIGURES:
        return None, "figures_too_many"
    clean: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            return None, "figures_item_not_an_object"
        label = _short(item.get("label"), MAX_LABEL_CHARS, required=True)
        if label is None:
            return None, "figures_label_invalid"
        value = _number_value(item.get("value"))
        if value is None:
            return None, "figures_value_not_a_number"
        unit = _short(item.get("unit"), MAX_UNIT_CHARS, required=True)
        if unit is None:
            return None, "figures_unit_missing"
        owner = _short(item.get("of"), MAX_LABEL_CHARS)
        if owner is None:
            return None, "figures_of_invalid"
        estimate = item.get("estimate", False)
        if not isinstance(estimate, bool):
            return None, "figures_estimate_invalid"
        clean.append(
            {"label": label, "value": value, "unit": unit, "of": owner, "estimate": estimate}
        )
    caption = _short(payload.get("caption"), MAX_CAPTION_CHARS)
    if caption is None:
        return None, "figures_caption_invalid"
    provenance, reason = _provenance(payload, "figures")
    if provenance is None:
        return None, reason
    return {"caption": caption, "items": clean, **provenance}, ""


def _best(values: list[Any], better: str) -> list[int]:
    """The indexes holding the best value in a row; every index on a tie."""
    numbers = [value for value in values if isinstance(value, float)]
    if not numbers or better not in ("higher", "lower"):
        return []
    target = max(numbers) if better == "higher" else min(numbers)
    best = [index for index, value in enumerate(values) if value == target]
    # A row where every item ties has no best, and saying "Best" on all of
    # them would mark a difference that is not there.
    return [] if len(best) == len(values) else best


def _validate_compare(payload: Any) -> tuple[dict[str, Any] | None, str]:
    """QUI-A05. Items as columns, criteria as rows, the best per row computed here.

    The model states the rule (``better``: higher or lower) and the values; the
    runtime picks the winner. A ``best`` the model sent is never read, because
    a model choosing which item to crown is a model choosing the answer.
    """
    if not isinstance(payload, dict):
        return None, "compare_not_an_object"
    items = payload.get("items")
    if not isinstance(items, list) or len(items) < 2:
        return None, "compare_items_missing"
    if len(items) > MAX_COMPARE_ITEMS:
        return None, "compare_too_many_items"
    names: list[str] = []
    for item in items:
        name = _short(item, MAX_LABEL_CHARS, required=True)
        if name is None:
            return None, "compare_item_invalid"
        names.append(name)
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        return None, "compare_rows_missing"
    if len(rows) > MAX_COMPARE_ROWS:
        return None, "compare_too_many_rows"
    clean: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            return None, "compare_row_not_an_object"
        label = _short(row.get("label"), MAX_LABEL_CHARS, required=True)
        if label is None:
            return None, "compare_row_label_invalid"
        unit = _short(row.get("unit"), MAX_UNIT_CHARS)
        if unit is None:
            return None, "compare_unit_invalid"
        better = row.get("better", "")
        if better not in ("", "higher", "lower"):
            return None, "compare_better_invalid"
        values = row.get("values")
        if not isinstance(values, list) or len(values) != len(names):
            return None, "compare_row_width_mismatch"
        cells: list[Any] = []
        for value in values:
            number = _number_value(value)
            if number is not None:
                cells.append(number)
                continue
            cell = _cell(value)
            if cell is None or (isinstance(value, int | float) and not isinstance(value, bool)):
                return None, "compare_value_invalid"
            cells.append(cell)
        if better and not all(isinstance(cell, float) for cell in cells):
            # "Lower is better" over text has no answer, and guessing one is
            # exactly the mark this block exists to keep honest.
            return None, "compare_better_needs_numbers"
        clean.append({
            "label": label, "unit": unit, "better": better, "values": cells,
            "best": _best(cells, better),
        })
    caption = _short(payload.get("caption"), MAX_CAPTION_CHARS)
    if caption is None:
        return None, "compare_caption_invalid"
    provenance, reason = _provenance(payload, "compare")
    if provenance is None:
        return None, reason
    return {"caption": caption, "items": names, "rows": clean, **provenance}, ""


def _validate_measure(payload: Any) -> tuple[dict[str, Any] | None, str]:
    """QUI-A06. One value on a known scale: 4.2 of 5, 31 of 40 checks."""
    if not isinstance(payload, dict):
        return None, "measure_not_an_object"
    label = _short(payload.get("label"), MAX_LABEL_CHARS, required=True)
    if label is None:
        return None, "measure_label_invalid"
    value = _number_value(payload.get("value"))
    if value is None:
        return None, "measure_value_not_a_number"
    raw_min = payload.get("min", 0)
    low = _number_value(raw_min)
    high = _number_value(payload.get("max"))
    if low is None or high is None or high <= low:
        return None, "measure_scale_invalid"
    if not low <= value <= high:
        # Off the scale is a different claim from "full", and drawing it as a
        # full bar would hide that.
        return None, "measure_value_off_scale"
    unit = _short(payload.get("unit"), MAX_UNIT_CHARS)
    if unit is None:
        return None, "measure_unit_invalid"
    provenance, reason = _provenance(payload, "measure")
    if provenance is None:
        return None, reason
    return {"label": label, "value": value, "min": low, "max": high, "unit": unit, **provenance}, ""


CALLOUT_TONES = ("verdict", "warning", "action")


def _validate_callout(payload: Any) -> tuple[dict[str, Any] | None, str]:
    """QUI-A07. One verdict, warning or recommended action, in a sentence or two."""
    if not isinstance(payload, dict):
        return None, "callout_not_an_object"
    tone = payload.get("tone", "verdict")
    if tone not in CALLOUT_TONES:
        return None, "callout_tone_invalid"
    text = _short(payload.get("text"), MAX_TEXT_CHARS, required=True)
    if text is None:
        return None, "callout_text_invalid"
    return {"tone": tone, "text": text}, ""


def _short_list(value: Any) -> list[str] | None:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_LIST_ITEMS:
        return None
    out: list[str] = []
    for entry in value:
        text = _short(entry, MAX_CELL_CHARS, required=True)
        if text is None:
            return None
        out.append(text)
    return out


def _validate_proscons(payload: Any) -> tuple[dict[str, Any] | None, str]:
    """QUI-A07. Two short lists per option."""
    if not isinstance(payload, dict):
        return None, "proscons_not_an_object"
    options = payload.get("options")
    if not isinstance(options, list) or not options:
        return None, "proscons_options_missing"
    if len(options) > MAX_OPTIONS:
        return None, "proscons_too_many_options"
    clean: list[dict[str, Any]] = []
    for option in options:
        if not isinstance(option, dict):
            return None, "proscons_option_not_an_object"
        name = _short(option.get("name"), MAX_LABEL_CHARS, required=True)
        if name is None:
            return None, "proscons_name_invalid"
        pros = _short_list(option.get("pros"))
        cons = _short_list(option.get("cons"))
        if pros is None or cons is None:
            return None, "proscons_list_invalid"
        if not pros and not cons:
            return None, "proscons_option_empty"
        clean.append({"name": name, "pros": pros, "cons": cons})
    caption = _short(payload.get("caption"), MAX_CAPTION_CHARS)
    if caption is None:
        return None, "proscons_caption_invalid"
    return {"caption": caption, "options": clean}, ""


def _validate_steps(payload: Any) -> tuple[dict[str, Any] | None, str]:
    """QUI-A07. An ordered or dated sequence, in the order given."""
    if not isinstance(payload, dict):
        return None, "steps_not_an_object"
    steps = payload.get("steps")
    if not isinstance(steps, list) or not steps:
        return None, "steps_missing"
    if len(steps) > MAX_STEPS:
        return None, "steps_too_many"
    clean: list[dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            return None, "steps_step_not_an_object"
        label = _short(step.get("label"), MAX_CAPTION_CHARS, required=True)
        if label is None:
            return None, "steps_label_invalid"
        when = _short(step.get("when"), MAX_LABEL_CHARS)
        text = _short(step.get("text"), MAX_TEXT_CHARS)
        if when is None or text is None:
            return None, "steps_detail_invalid"
        clean.append({"label": label, "when": when, "text": text})
    caption = _short(payload.get("caption"), MAX_CAPTION_CHARS)
    if caption is None:
        return None, "steps_caption_invalid"
    return {"caption": caption, "steps": clean}, ""


_VALIDATORS = {
    PART_TABLE: _validate_table,
    PART_CHART: _validate_chart,
    PART_FIGURES: _validate_figures,
    PART_COMPARE: _validate_compare,
    PART_MEASURE: _validate_measure,
    PART_CALLOUT: _validate_callout,
    PART_PROSCONS: _validate_proscons,
    PART_STEPS: _validate_steps,
}

#: Blocks whose numbers are claims about the world. Without a stated source
#: Raiker shows them as text rather than as a figure an owner may trust.
SOURCED_TYPES = frozenset({PART_FIGURES, PART_COMPARE, PART_MEASURE})


def _has_numbers(kind: str, data: dict[str, Any]) -> bool:
    if kind == PART_COMPARE:
        return any(isinstance(v, float) for row in data["rows"] for v in row["values"])
    return True


#: Units written before the number, the way a price is read: £999, not 999 £.
PREFIX_UNITS = frozenset({"£", "$", "€", "¥", "₹", "US$", "A$", "C$"})


def _figure(value: float, unit: str = "") -> str:
    text = str(int(value)) if value.is_integer() else f"{value:g}"
    if unit in PREFIX_UNITS:
        return f"-{unit}{text[1:]}" if text.startswith("-") else f"{unit}{text}"
    return f"{text} {unit}".strip() if unit else text


def as_text(part: ContentPart) -> str:
    """A block as the Markdown an owner would read if it were not drawn.

    The one text form every surface shares: an unsourced block becomes it, an
    export can print it, and *Show as text* in the browser says the same thing.
    """
    data = part.data
    estimate = " (≈ estimate)" if data.get("estimate") else ""
    if part.type == PART_FIGURES:
        lines = [f"**{data['caption']}**", ""] if data.get("caption") else []
        for item in data["items"]:
            owner = f" ({item['of']})" if item.get("of") else ""
            mark = " (≈ estimate)" if item.get("estimate") or data.get("estimate") else ""
            lines.append(f"- {item['label']}: {_figure(item['value'], item['unit'])}{owner}{mark}")
        return "\n".join(lines)
    if part.type == PART_COMPARE:
        lines = [f"**{data['caption']}**{estimate}", ""] if data.get("caption") else []
        for row in data["rows"]:
            cells = []
            for index, (name, value) in enumerate(zip(data["items"], row["values"], strict=True)):
                shown = _figure(value, row["unit"]) if isinstance(value, float) else str(value)
                best = " (best)" if index in row["best"] else ""
                cells.append(f"{name} {shown}{best}")
            lines.append(f"- {row['label']}: " + "; ".join(cells))
        return "\n".join(lines)
    if part.type == PART_MEASURE:
        low = "" if data["min"] == 0 else f"{_figure(data['min'])}–"
        return (
            f"**{data['label']}**: {_figure(data['value'], data['unit'])} "
            f"of {low}{_figure(data['max'], data['unit'])}{estimate}"
        )
    if part.type == PART_CALLOUT:
        lead = {"verdict": "Verdict", "warning": "Warning", "action": "Next step"}[data["tone"]]
        return f"> **{lead}:** {data['text']}"
    if part.type == PART_PROSCONS:
        lines = [f"**{data['caption']}**", ""] if data.get("caption") else []
        for option in data["options"]:
            lines.append(f"**{option['name']}**")
            lines += [f"- Pro: {entry}" for entry in option["pros"]]
            lines += [f"- Con: {entry}" for entry in option["cons"]]
            lines.append("")
        return "\n".join(lines).rstrip()
    if part.type == PART_STEPS:
        lines = [f"**{data['caption']}**", ""] if data.get("caption") else []
        for number, step in enumerate(data["steps"], start=1):
            when = f" ({step['when']})" if step.get("when") else ""
            detail = f" — {step['text']}" if step.get("text") else ""
            lines.append(f"{number}. {step['label']}{when}{detail}")
        return "\n".join(lines)
    return part.text


#: Said under an unsourced block shown as text, so the owner knows why.
UNSOURCED_NOTE = "_No source was given for these numbers, so Raiker shows them as text._"


def content_parts(message: str) -> list[ContentPart]:
    """Split an answer into declared parts, validating each one it declares.

    An answer with no declared block returns a single text part — which is the
    behaviour every turn had before this channel existed, so nothing about an
    ordinary answer changes.

    Over :data:`MAX_PARTS` declared blocks, the rest are refused rather than
    rendered: a turn that emits a hundred tables is not answering a question,
    and the ceiling is stated in the refusal.
    """
    if not message:
        return []
    parts: list[ContentPart] = []
    cursor = 0
    declared = 0
    for match in _FENCE.finditer(message):
        kind = match.group("kind")
        validator = _VALIDATORS.get(kind)
        if validator is None:
            # Not a type this runtime knows. Left in the prose untouched, so a
            # future type added by a newer build degrades to visible text rather
            # than to a refusal an owner cannot act on.
            continue
        run = _text(message[cursor : match.start()])
        if run is not None:
            parts.append(run)
        cursor = match.end()
        declared += 1
        if declared > MAX_PARTS:
            parts.append(ContentPart(PART_REFUSED, reason_code="too_many_parts"))
            continue
        try:
            payload = json.loads((match.group("head") or "") + "\n" + (match.group("body") or ""))
        except json.JSONDecodeError:
            parts.append(ContentPart(PART_REFUSED, reason_code=f"{kind}_not_json"))
            continue
        data, reason = validator(payload)
        if data is None:
            parts.append(ContentPart(PART_REFUSED, reason_code=reason))
            continue
        part = ContentPart(cast(PartType, kind), data=data)
        if kind in SOURCED_TYPES and not data["source"] and _has_numbers(kind, data):
            # Units and sources (04, Rules): numbers with no stated source are
            # shown, but as text — never drawn as figures that look checked.
            parts.append(ContentPart(PART_TEXT, text=f"{as_text(part)}\n\n{UNSOURCED_NOTE}"))
            continue
        parts.append(part)

    tail = _text(message[cursor:])
    if tail is not None:
        parts.append(tail)
    if not parts:
        # Whitespace either side of nothing the runtime accepted. The answer is
        # still the answer, so it is returned as the one text part it is.
        return [ContentPart(PART_TEXT, text=message)]
    return parts


def has_typed_part(parts: list[ContentPart]) -> bool:
    """True when at least one part is something other than prose or a refusal."""
    return any(part.type in _VALIDATORS for part in parts)


def renders_as_parts(parts: Sequence[ContentPart]) -> bool:
    """True when a surface should render the parts rather than the raw answer.

    The difference from :func:`has_typed_part` is the refusal (BUG-300). A
    refusal is not *content* — nothing was accepted — but it is something the
    answer declared and a reader has to see, so any surface that renders parts
    at all has to take the typed route when one is present. Every surface that
    reopens an answer asks this one question, so they all get the same answer to
    it: an export, a reopened thread and a live turn agree on when a turn had
    parts.
    """
    return any(part.type in _VALIDATORS or part.type == PART_REFUSED for part in parts)
