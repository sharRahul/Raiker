"""Interactive Rich TUI session state (single default layout).

``UISession`` is the inert, in-memory state for one interactive Rich TUI run. The TUI is
a single-panel, Claude-Code-style transcript flow: there are no simultaneously docked
side panels, regions, or focus cycling. The session holds the approval mode, the
streaming transcript, the side-question log, and the latest status context.

It is a pure state container. It must not import subprocess, socket, requests, urllib,
or httpx; must not call tools, models, plugins, channels, or memory/graph writes; and
must not execute approvals or proposals. All it does is record what the user asked the
shell to display, so the layout renderer and the app loop can read consistent state.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from raiker.tui.status_bar import StatusContext
from raiker.tui.transcript import Transcript

# Approval modes (docs/UI_UX_DESIGN_SPEC.md -> Approval Mode System).
APPROVAL_MODES: tuple[str, ...] = ("manual", "auto-accept")


@dataclass(frozen=True)
class SideQuestion:
    """A recorded side question and its answer, kept separate from task state."""

    question: str
    answer: str


@dataclass
class UISession:
    """Mutable in-memory state for one interactive Rich TUI session."""

    session_id: str = "terminal-local"
    view_name: str = "Raiker Session"
    approval_mode: str = "manual"
    # The welcome/home screen is shown until the user's first interaction (or /home).
    show_home: bool = True
    transcript: Transcript = field(default_factory=Transcript)
    side_questions: list[SideQuestion] = field(default_factory=list)
    status: StatusContext = field(default_factory=StatusContext)

    def cycle_approval_mode(self) -> str:
        idx = APPROVAL_MODES.index(self.approval_mode)
        self.approval_mode = APPROVAL_MODES[(idx + 1) % len(APPROVAL_MODES)]
        return self.approval_mode
