"""Structured streaming transcript for the Rich TUI.

The transcript panel is a structured event system, not plain chat
(docs/UI_UX_DESIGN_SPEC.md -> Transcript / Event Stream Behaviour). Each entry is an
atomic, traceable event with a visual indicator, an optional summary, optional
collapsible detail, and optional inline diff. Large detail is collapsed by default and
shows summary metadata.

This module is pure presentation/state. It records what already happened (command
results, prompt responses, side questions) and renders it. It never executes tools,
models, approvals, or proposals, and never opens sockets or processes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from raiker.tui.accessibility import TerminalProfile, ascii_safe

# Visual indicators (docs/UI_UX_DESIGN_SPEC.md -> Visual Indicators).
_INDICATORS_UNICODE = {
    "action": "●",  # successful tool/action
    "reasoning": "○",  # reasoning/explanation step
    "warning": "⚠",  # warning or risk state
    "failure": "✖",  # failure state
}
_INDICATORS_ASCII = {
    "action": "*",
    "reasoning": "o",
    "warning": "!",
    "failure": "x",
}

# Above this many detail lines, collapse by default and show a summary metadata hint.
_COLLAPSE_THRESHOLD = 8


@dataclass
class TranscriptEvent:
    """One atomic, traceable transcript event."""

    kind: str  # action | reasoning | warning | failure
    title: str
    summary: str = ""
    detail: tuple[str, ...] = ()
    diff: tuple[str, ...] = ()
    side_question: bool = False
    expanded: bool = False
    event_id: str | None = None

    @property
    def collapsible(self) -> bool:
        return len(self.detail) > _COLLAPSE_THRESHOLD or bool(self.diff)


def classify_result(result: str, *, side_question: bool = False) -> str:
    """Pick a transcript indicator kind from a plain command/prompt result string."""

    lowered = result.lower()
    if side_question:
        return "reasoning"
    if result.startswith("Unknown command") or "failed" in lowered or "error" in lowered:
        return "failure"
    if "risk" in lowered or "approval card" in lowered or "warning" in lowered:
        return "warning"
    return "action"


class Transcript:
    """An ordered list of transcript events with deterministic rendering."""

    def __init__(self, max_events: int = 200) -> None:
        self._events: list[TranscriptEvent] = []
        self._max_events = max_events

    def __len__(self) -> int:
        return len(self._events)

    @property
    def events(self) -> tuple[TranscriptEvent, ...]:
        return tuple(self._events)

    def add(self, event: TranscriptEvent) -> TranscriptEvent:
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events :]
        return event

    def add_result(
        self,
        title: str,
        result: str,
        *,
        side_question: bool = False,
        kind: str | None = None,
    ) -> TranscriptEvent:
        """Record a command/prompt result, splitting it into summary + detail."""

        lines = result.splitlines() or [result]
        summary = lines[0] if lines else ""
        detail = tuple(lines[1:])
        diff = tuple(line for line in lines if line[:1] in {"+", "-"} and line[:2] != "--")
        event = TranscriptEvent(
            kind=kind or classify_result(result, side_question=side_question),
            title=title,
            summary=summary,
            detail=detail,
            diff=diff,
            side_question=side_question,
        )
        return self.add(event)

    def toggle_last(self) -> bool:
        """Expand/collapse the most recent collapsible event (ctrl+r equivalent)."""

        for event in reversed(self._events):
            if event.collapsible:
                event.expanded = not event.expanded
                return True
        return False

    # -- rendering ---------------------------------------------------------

    def render_lines(self, profile: TerminalProfile, *, limit: int | None = None) -> list[str]:
        indicators = _INDICATORS_UNICODE if profile.unicode else _INDICATORS_ASCII
        cont = "│" if profile.unicode else "|"
        branch = "├" if profile.unicode else "|-"
        last_branch = "└" if profile.unicode else "|_"

        events = self._events if limit is None else self._events[-limit:]
        lines: list[str] = []
        for event in events:
            marker = indicators.get(event.kind, indicators["action"])
            prefix = "  (side) " if event.side_question else ""
            header = f"{prefix}{marker} {event.title}"
            if event.summary:
                header += f" — {event.summary}"
            lines.append(header)

            body = list(event.detail)
            if event.diff and not event.detail:
                body = list(event.diff)

            if not body:
                continue

            if event.collapsible and not event.expanded:
                meta = f"{len(event.detail)} lines"
                if event.diff:
                    added = sum(1 for line in event.diff if line.startswith("+"))
                    removed = sum(1 for line in event.diff if line.startswith("-"))
                    meta = f"{added} additions, {removed} removals"
                hint = "ctrl+r" if profile.unicode else "expand"
                lines.append(f"{last_branch} {meta} ({hint} to expand)")
                continue

            for i, detail_line in enumerate(body):
                connector = last_branch if i == len(body) - 1 else branch
                lines.append(f"{connector} {detail_line}")
            lines.append(cont)

        if not lines:
            lines = ["(transcript is empty — submit a prompt or command)"]
        if not profile.unicode:
            lines = [ascii_safe(line) for line in lines]
        return lines


@dataclass
class ExecutionIndicator:
    """Live execution indicator shown above the input (docs -> Live Execution Indicator)."""

    label: str = "Idle"
    elapsed_s: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    active: bool = False
    interrupt_hint: str = "esc to interrupt"
    _spinner: str = field(default="☁", repr=False)

    def render(self, profile: TerminalProfile) -> str:
        if not self.active:
            return ""
        spinner = self._spinner if profile.unicode else "*"
        up = "↑" if profile.unicode else "^"
        down = "↓" if profile.unicode else "v"
        text = (
            f"{spinner} {self.label}... ({self.elapsed_s}s • "
            f"{up} {self.tokens_in} {down} {self.tokens_out} tokens • {self.interrupt_hint})"
        )
        return text if profile.unicode else ascii_safe(text)
