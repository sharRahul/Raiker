"""Configurable status bar for the Rich TUI default access shell.

The status bar is rendered from a list of named status items (not one hard-coded
string), so user/project/policy/terminal configuration can reorder or hide non-safety
fields. Required safety items (``state``, ``approvals``, ``network``) are pinned and can
never be dropped, including in compact/narrow rendering. The clock can be injected for
deterministic tests. This module performs no runtime execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# Items always kept first in compact rendering, in priority order.
_COMPACT_KEEP = ("state", "task", "approvals", "model", "network", "clock")


@dataclass(frozen=True)
class StatusContext:
    state: str = "READY"
    task: str = "idle"
    approvals: int = 0
    model: str = "mock-test"
    context_used: int = 0
    context_max: int = 32000
    memory: str = "project"
    network: str = "blocked"
    execution: str = "local"
    last_event: str = "none"
    cost: str = "$0.00"


@dataclass(frozen=True)
class StatusBarConfig:
    fields: list[str] = field(
        default_factory=lambda: [
            "state",
            "task",
            "approvals",
            "model",
            "context_percent_bar",
            "context",
            "network",
            "last_event",
            "clock",
        ]
    )
    # Safety-critical items that must never be hidden, even during risky work.
    pinned_fields: list[str] = field(
        default_factory=lambda: ["state", "approvals", "network"]
    )
    use_blocks: bool = True
    compact_below: int = 100


class StatusBarRenderer:
    def __init__(self, config: StatusBarConfig | None = None) -> None:
        self.config = config or StatusBarConfig()

    def _context_percent(self, context: StatusContext) -> int:
        if context.context_max <= 0:
            return 0
        return max(0, min(100, round(context.context_used / context.context_max * 100)))

    def _bar(self, percent: int) -> str:
        filled = round(percent / 100 * 14)
        if self.config.use_blocks:
            return "█" * filled + "░" * (14 - filled)
        return "#" * filled + "-" * (14 - filled)

    def render_item(self, item: str, context: StatusContext, *, clock: str | None = None) -> str:
        percent = self._context_percent(context)
        if item == "state":
            return context.state
        if item == "task":
            return f"task:{context.task}"
        if item == "approvals":
            return f"approvals:{context.approvals}"
        if item == "model":
            return f"model:{context.model}"
        if item == "context_percent_bar":
            return f"ctx_bar: {self._bar(percent)} {percent}%"
        if item == "context":
            return f"ctx:{context.context_used // 1000}k/{context.context_max // 1000}k"
        if item == "memory":
            return f"mem:{context.memory}"
        if item == "network":
            return f"net:{context.network}"
        if item == "execution":
            return f"exec:{context.execution}"
        if item == "last_event":
            return f"last:{context.last_event}"
        if item == "cost":
            return f"cost:{context.cost}"
        if item == "clock":
            return clock if clock is not None else datetime.now().strftime("%H:%M")
        return f"{item}:unknown"

    def _compact_fields(self) -> list[str]:
        pinned = set(self.config.pinned_fields)
        keep = set(_COMPACT_KEEP) | pinned
        kept = [item for item in self.config.fields if item in keep]
        # Guarantee every pinned safety field survives even if absent from `fields`.
        for safety in self.config.pinned_fields:
            if safety not in kept:
                kept.append(safety)
        return kept

    def render(
        self,
        context: StatusContext | None = None,
        *,
        clock: str | None = None,
        compact: bool = False,
        width: int | None = None,
    ) -> str:
        ctx = context or StatusContext()
        is_compact = compact or (width is not None and width < self.config.compact_below)
        if is_compact:
            kept = self._compact_fields()
            dropped = [item for item in self.config.fields if item not in kept]
            rendered = [self.render_item(item, ctx, clock=clock) for item in kept]
            if dropped:
                rendered.append(f"+{len(dropped)}")
            return " | ".join(rendered)
        return " | ".join(self.render_item(item, ctx, clock=clock) for item in self.config.fields)
