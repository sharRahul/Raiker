"""TUI-safe dataclasses describing default-layout panel content.

These are inert data carriers for the Rich TUI default access shell. They never
execute tools, call models, mutate files, open sockets, or run processes. Content is
populated by the orchestration layer (``raiker.tui.app``) from existing safe command
and store paths, then handed to the pure panel renderers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Default Input Panel hint, aligned with docs/UI_UX_DESIGN_SPEC.md.
DEFAULT_INPUT_HINT = (
    "? side question | / command | normal prompt | ! command proposal | @ file mention"
)

CLIENT_MODE = "rich_tui_default"
SHELL_MODE_LABEL = "Rich TUI default access shell"
RUNTIME_SAFETY_LABEL = "runtime execution disabled"


@dataclass(frozen=True)
class ActivityItem:
    """A single recent-activity row. ``marker`` is one of done/active/pending."""

    marker: str
    text: str


@dataclass(frozen=True)
class MainPanelContent:
    """Primary / Main Panel content: welcome, workspace, mode, model, and body."""

    title: str = "Raiker v0.0.0"
    welcome: str = "Hello / Welcome back"
    workspace: str = "."
    mode: str = SHELL_MODE_LABEL
    model: str = "unknown"
    effort: str = "default"
    body: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActivityContent:
    """Activity Panel content: a compact, safe summary (not a developer dashboard)."""

    workspace: str = "."
    client_mode: str = CLIENT_MODE
    runtime_safety: str = RUNTIME_SAFETY_LABEL
    network: str = "blocked"
    approvals: str = "0"
    model: str = "unknown"
    last_event: str = "none"
    hint: str = "Use /help or /commands to see every available command."
    recent: tuple[ActivityItem, ...] = ()


@dataclass(frozen=True)
class InputContent:
    """Input Panel content: the documented prompt-mode hint."""

    hint: str = DEFAULT_INPUT_HINT


@dataclass(frozen=True)
class ShellContent:
    """The full default-layout content bundle."""

    main: MainPanelContent = field(default_factory=MainPanelContent)
    activity: ActivityContent = field(default_factory=ActivityContent)
    input: InputContent = field(default_factory=InputContent)
