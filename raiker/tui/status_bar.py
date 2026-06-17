from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


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
    use_blocks: bool = True


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
            return "#" * filled + "-" * (14 - filled)
        return "#" * filled + "-" * (14 - filled)

    def render_item(self, item: str, context: StatusContext) -> str:
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
            return datetime.now().strftime("%H:%M")
        return f"{item}:unknown"

    def render(self, context: StatusContext | None = None) -> str:
        ctx = context or StatusContext()
        return " | ".join(self.render_item(item, ctx) for item in self.config.fields)
