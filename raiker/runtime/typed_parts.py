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
from dataclasses import asdict, dataclass, field
from typing import Any

# ── Part types ──────────────────────────────────────────────────────────────

#: Ordinary prose. Rendered by the Markdown renderer, exactly as before.
PART_TEXT = "text"
#: A table the product knows is a table: sortable, and announced as one.
PART_TABLE = "table"
#: A series to plot. Bounded and validated like any other model-proposed payload.
PART_CHART = "chart"
#: A declared block the runtime would not accept, with the reason it refused.
PART_REFUSED = "refused"

PART_TYPES = frozenset({PART_TEXT, PART_TABLE, PART_CHART, PART_REFUSED})

#: The chart shapes Raiker draws. Deliberately three: each is a different claim
#: about the data, and a shape nobody can read is not a fourth feature.
CHART_KINDS = ("bar", "line", "area")

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

_FENCE = re.compile(
    r"^[ \t]*```[ \t]*raiker:(?P<kind>[a-z_]+)[ \t]*\n(?P<body>.*?)\n[ \t]*```[ \t]*$",
    re.S | re.M,
)


@dataclass(frozen=True)
class ContentPart:
    """One declared piece of a turn's answer."""

    type: str
    #: `text` only: the Markdown run.
    text: str = ""
    #: `table` and `chart`: the validated payload. Never the model's raw object.
    data: dict[str, Any] = field(default_factory=dict)
    #: `refused` only: why this block was not accepted, in a reason code.
    reason_code: str = ""

    def __post_init__(self) -> None:
        if self.type not in PART_TYPES:
            raise ValueError(f"content_part_type_invalid:{self.type}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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


_VALIDATORS = {PART_TABLE: _validate_table, PART_CHART: _validate_chart}


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
            payload = json.loads(match.group("body"))
        except json.JSONDecodeError:
            parts.append(ContentPart(PART_REFUSED, reason_code=f"{kind}_not_json"))
            continue
        data, reason = validator(payload)
        if data is None:
            parts.append(ContentPart(PART_REFUSED, reason_code=reason))
            continue
        parts.append(ContentPart(kind, data=data))

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
