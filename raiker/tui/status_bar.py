from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from rich.style import Style
from rich.text import Text

from raiker.tui.theme import ROSE_PINE, RaikerTheme

_VERBS: tuple[str, ...] = (
    "thinking",
    "writing",
    "coding",
    "searching",
    "reading",
    "analyzing",
    "planning",
    "reviewing",
)
_SPINNER_FRAMES: tuple[str, ...] = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")


@dataclass
class StatusContext:
    state: str = "READY"
    task: str = ""
    model: str = ""
    context_used: int = 0
    context_max: int = 0
    turn_elapsed: float = 0.0
    session_elapsed: float = 0.0
    last_turn_ended: float = 0.0
    cwd_label: str = ""
    git_branch: str = ""
    approvals: int = 0
    compressions: int = 0
    network: str = ""


@dataclass
class StatusBarConfig:
    use_blocks: bool = True
    compact_below: int = 100


class StatusBarRenderer:
    VERB_PAD_LEN: ClassVar[int] = max(len(v) for v in _VERBS) + 1

    def __init__(
        self, config: StatusBarConfig | None = None, theme: RaikerTheme | None = None
    ) -> None:
        self.config = config or StatusBarConfig()
        self.theme = theme or ROSE_PINE

    def _fmt_duration(self, seconds: float) -> str:
        mins, secs = divmod(int(seconds), 60)
        hours, mins = divmod(mins, 60)
        if hours:
            return f"{hours}h {mins:02d}m"
        if mins:
            return f"{mins}m {secs:02d}s"
        return f"{secs}s"

    def _context_bar(self, percent: int) -> str:
        filled = round(percent / 100 * 10)
        if self.config.use_blocks:
            return "█" * filled + "░" * (10 - filled)
        return "#" * filled + "-" * (10 - filled)

    def render_status_line(
        self,
        ctx: StatusContext,
        tick: int = 0,
        clock: str | None = None,
        compact: bool = False,
        width: int | None = None,
    ) -> Text:
        w = width or 120
        is_compact = compact or w < self.config.compact_below
        t = self.theme
        segments: list[tuple[str, str]] = []
        busy = ctx.state == "RUNNING"

        if busy:
            spinner = _SPINNER_FRAMES[tick % len(_SPINNER_FRAMES)]
            verb = _VERBS[tick % len(_VERBS)]
            indicator = f"{spinner} {verb}…"
            elapsed = self._fmt_duration(ctx.turn_elapsed)
            segments.append((f"{indicator} {elapsed}", t.primary))
        elif ctx.state == "READY":
            segments.append(("─ READY", t.success))
        else:
            segments.append((ctx.state, t.warn))

        if ctx.model:
            short = ctx.model.split("/")[-1]
            short = short.replace("claude-", "").replace("anthropic-", "")
            short = short.replace("-", " ").replace("  ", ".").strip()
            segments.append((f" {short}", t.muted))

        if ctx.context_max > 0 and ctx.context_used > 0:
            pct = min(100, round(ctx.context_used / ctx.context_max * 100))
            bar = self._context_bar(pct)
            if pct >= 95:
                pct_color = t.status_critical
            elif pct >= 80:
                pct_color = t.status_warn
            else:
                pct_color = t.status_good
            segments.append((f" [{bar}] {pct}%", pct_color))

        if ctx.approvals > 0:
            segments.append((f" approvals:{ctx.approvals}", t.warn))

        if not is_compact:
            if ctx.compressions > 0:
                c = ctx.compressions
                col = t.status_critical if c >= 10 else t.status_warn if c >= 5 else t.muted
                segments.append((f" cmp {c}", col))
            clock_str = clock or datetime.now().strftime("%H:%M")
            segments.append((f" {clock_str}", t.muted))

        left = Text("")
        for text, color in segments:
            left.append(text, style=Style(color=color))

        right_parts: list[str] = []
        if ctx.cwd_label:
            right_parts.append(ctx.cwd_label)
        if ctx.git_branch:
            right_parts.append(ctx.git_branch)
        right_str = " │ ".join(right_parts) if right_parts else ""

        if right_str and not is_compact:
            right_text = Text(f" {right_str}", style=Style(color=t.label))
            total_len = len(left.plain) + len(right_text.plain) + 3
            if total_len < w:
                gap = w - len(left.plain) - len(right_text.plain)
                left.append(" " * gap)
                left.append(right_text)
            else:
                left.append(" ", style=Style(color=t.border))
                left.append(right_text, style=Style(color=t.label))

        return left
