# 04 Visual answers

Part of the [Quiet UI redesign plan](README.md). Proposed, 2026-10-21.

## Status

**Shipped 2026-10-23**
([FIXED-1136](../FIXED_ITEMS.md#fixed-1136--a-turn-could-not-say-these-are-the-headline-numbers-qui-a04)
to [FIXED-1149](../FIXED_ITEMS.md#fixed-1149--a-chart-in-a-transcript-bubble-was-too-small-to-read-and-its-legend-had-no-colours-04-screenshot-review);
live cases RT-QUI-35 to RT-QUI-43 in
[WEB_APP_LIVE_TEST.md](../../architecture/WEB_APP_LIVE_TEST.md)).

| Item | State |
|---|---|
| QUI-A01 | **Done.** Chart kind `hbar`, axis from zero, labels on the left. |
| QUI-A02 | **Done.** Chart kind `stacked`: 100% horizontal bars, shares printed on each part; negative or empty parts are refused. |
| QUI-A03 | **Done.** Chart kind `scatter`: exactly two series (across, then up); labels name the points. |
| QUI-A04 | **Done.** `raiker:figures`, up to four, unit required, *≈ estimate* in words. |
| QUI-A05 | **Done.** `raiker:compare`; the runtime computes `best` from `better`, and a `best` the model sends is ignored. A tie marks every tied item; a row where all tie has no mark. |
| QUI-A06 | **Done.** `raiker:measure`; a value off its scale is refused. |
| QUI-A07 | **Done.** `raiker:proscons`, `raiker:steps` (on the path line) and `raiker:callout` (*Verdict*, *Warning*, *Next step*). |
| QUI-A08 | **Later**, as planned. Mermaid would be the UI's first bundled diagram library. |
| Rules | **Done.** Units required on figures. Figures, measures and comparisons that contain numbers but give no `source` are shown as text, with a line saying why; tables and charts keep their earlier behaviour (deviation: the rule names "a block", and applying it to charts would have changed every existing chart answer). At most three blocks is guidance to the model; more than three offers **Create document**, which puts the request in the composer rather than sending it. Small local models get one corrected-block retry (Ollama, LM Studio, llama.cpp, MLX, vLLM, local GGUF); hosted models do not, because a second paid call is not the owner's choice. |
| Answer style | **Done** in **Settings › General › Answers** (*Auto · Mostly text · Visual where it helps*), read by the runtime for every turn. Deviation: *More* does not exist yet ([03, QUI-C04](03_WELCOME_HOME_AND_CHAT.md#status)), so it is an account setting rather than a composer choice. |
| Block toolbar | **Done**: **Chart · Table** on charts, **Show as text** on every block, **Copy**, **CSV** for grids, **PNG** for charts. Open: **Pin to project**, which needs the Library ([06, QUI-F15](06_FEATURES_AND_IMPROVEMENTS.md#qui-f15--library)). |
| Acceptance | **Met.** Each block has a validator with refusal reasons, a component and a table or text fallback; every number reaches a screen reader (charts keep their table in the page; the measure is a `<meter>`); a malformed block leaves its prose and a visible refusal. Exports keep figures and comparisons as tables and the rest as text. |

## What exists

The typed answer channel already ships (BUG-288):

* `raiker/runtime/typed_parts.py` parses `raiker:table` and `raiker:chart`
  fences, validates them like any model-proposed argument (bounded, typed,
  refused rather than truncated) and returns `ContentPart` objects.
* `raiker/runtime/orchestrator.py` tells the model when and how to declare them.
* `web/src/lib/components/AnswerParts.svelte`, `DataTable.svelte` and
  `DataChart.svelte` draw them. Bar charts start at zero; every chart has a real
  table behind it for screen readers; a malformed block is shown as refused,
  never dropped.
* Chart kinds today: bar, line, area.

This plan widens the vocabulary and adds rules for when to use it. Every new
block follows the same path: fence → runtime validation → `ContentPart` →
component.

## Example: a comparison answer

> Compare the MacBook Air 13, Dell XPS 13 and ThinkPad X1 Carbon for working on
> the move: battery, weight and price.

1. Steps group: "Searched 3 sites · Read 3 spec pages".
2. One summary sentence.
3. **Key figures**: Longest battery 18 h (MacBook Air) · Lightest 1.09 kg (X1
   Carbon) · Lowest price £999 (MacBook Air).
4. **Comparison**: items as columns, criteria as rows, the best value per row
   marked "Best" in words.
5. **Horizontal bar**: battery life in hours, axis from zero.
6. **Callout**: "Pick by what matters most…"
7. Sources with the date checked, and a note that battery figures are
   manufacturer claims.

(Figures are illustrative.)

## Blocks

| ID | Block | Use when | Status |
|---|---|---|---|
| — | Table | Several items × several attributes | Exists |
| — | Chart: bar, line, area | One measure across items; change over time; a total over time | Exists |
| QUI-A01 | Horizontal bar | Rankings and comparisons with long names | New chart kind |
| QUI-A02 | Stacked 100% bar | Parts of a whole (used instead of a pie chart) | New chart kind |
| QUI-A03 | Scatter | Two measures at once, such as price against battery | New chart kind |
| QUI-A04 | Key figures | Up to four headline numbers, each with unit, label and owner | New |
| QUI-A05 | Comparison | A table with a stated "best" rule per row (higher or lower is better) | New |
| QUI-A06 | Measure | One value on a known scale: 4.2 of 5, 72% of budget, 31 of 40 checks | New |
| QUI-A07 | Pros and cons; Steps and timeline; Callout | Two short lists per option; a dated or ordered sequence (uses the path line); one verdict, warning or recommended action | New |
| QUI-A08 | Diagram | Flows and structures (Mermaid), for Build and technical answers | Later |

Suggested payloads follow the existing style, for example:

```
raiker:figures   {"items": [{"label": "Longest battery", "value": 18, "unit": "h", "of": "MacBook Air"}]}
raiker:compare   {"caption": …, "items": [...], "rows": [{"label": "Weight", "unit": "kg", "better": "lower", "values": [...]}]}
raiker:measure   {"label": "Checks passed", "value": 31, "max": 40}
raiker:callout   {"tone": "verdict" | "warning" | "action", "text": …}
```

The runtime computes "Best" from `better` and the values; the model does not get
to mark a winner itself.

## Rules

* **Data, not pictures.** The model sends numbers; Raiker draws them. The model
  never draws an image of a chart.
* **Units and sources.** Every figure has a unit. Estimates are marked
  "≈ estimate". A block with no source for its numbers is shown as text.
* **Zero-based bars**, as `DataChart.svelte` already enforces. Axes labelled.
* **Table one click away** on every chart. "Best" marked in words, never colour
  alone.
* **Refused, never dropped**, as today.
* **When not to visualise**: fewer than three values, or values that cannot be
  compared; opinions and explanations (prose, a callout at most).
* **At most three blocks per answer** unless the owner asked for a report; then
  *Create document* is offered.
* **Answer style** in More: *Auto · Mostly text · Visual where it helps*. "Show
  as text" on every block.
* **Small local models** are less reliable at producing valid data. Raiker asks
  once for a corrected block, then falls back to prose.

## Block toolbar

Table · Chart · Copy · CSV or PNG · **Pin to project** (saves the block into the
project's Files & links and the Library, [06, QUI-F15](06_FEATURES_AND_IMPROVEMENTS.md)).

## Order

Key figures, comparison, horizontal bar and callout first; together they cover
most "compare X and Y" questions. Then measure, stacked bar, scatter, pros and
cons, steps, and the Answer style setting. Diagrams last.

## Acceptance

* Each new block has a validator in `typed_parts.py` with refusal reasons, a
  component, and a table fallback.
* A screen reader reaches every number in every block.
* An answer with a malformed block still shows its prose and a visible refusal.
