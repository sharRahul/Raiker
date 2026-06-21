from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

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
_SPINNER_FRAMES: tuple[str, ...] = ("-", "\\", "|", "/")


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

    def __init__(self, config: StatusBarConfig | None = None) -> None:
        self.config = config or StatusBarConfig()

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
        return ("#" if not self.config.use_blocks else "█") * filled + ("-" if not self.config.use_blocks else "░") * (10 - filled)

    def render_status_line(
        self,
        ctx: StatusContext,
        tick: int = 0,
        clock: str | None = None,
        compact: bool = False,
        width: int | None = None,
    ) -> str:
        w = width or 120
        is_compact = compact or w < self.config.compact_below
        parts: list[str] = []
        if ctx.state == "RUNNING":
            spinner = _SPINNER_FRAMES[tick % len(_SPINNER_FRAMES)]
            verb = _VERBS[tick % len(_VERBS)]
            parts.append(f"{spinner} {verb} {self._fmt_duration(ctx.turn_elapsed)}")
        elif ctx.state == "READY":
            parts.append("READY")
        else:
            parts.append(ctx.state)
        if ctx.model:
            parts.append(f"model:{ctx.model}")
        if ctx.context_max > 0 and ctx.context_used > 0:
            pct = min(100, round(ctx.context_used / ctx.context_max * 100))
            parts.append(f"ctx:[{self._context_bar(pct)}] {pct}%")
        parts.append(f"approvals:{ctx.approvals}")
        if ctx.network:
            parts.append(f"net:{ctx.network}")
        if not is_compact:
            parts.append(clock or datetime.now().strftime("%H:%M"))
            if ctx.cwd_label:
                parts.append(f"cwd:{ctx.cwd_label}")
            if ctx.git_branch:
                parts.append(f"git:{ctx.git_branch}")
        return " | ".join(parts)
