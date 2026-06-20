"""Dynamic welcome / home screen content for the Rich TUI default layout.

Implements the documented default layout from docs/UI_UX_DESIGN_SPEC.md -> Default Layout:
a compact welcome/workspace view (greeting, logo orb, model/effort, workspace) on the
left, and recent activity plus "Tips for getting started" on the right. Everything is populated from
existing safe paths (model registry, task store, package version) — it never executes
tools, models, sockets, or processes.
"""

from __future__ import annotations

import getpass
import os
from collections.abc import Mapping
from dataclasses import dataclass

from raiker import __version__
from raiker.tui.accessibility import TerminalProfile, ascii_safe


@dataclass(frozen=True)
class ActivityItem:
    """A single recent-activity row. ``marker`` is one of done/active/pending."""

    marker: str
    text: str

# The logo "orb" from docs/UI_UX_DESIGN_SPEC.md (Unicode shaded blocks).
_LOGO_UNICODE: tuple[str, ...] = (
    "        .-----------.        ",
    "      .-░░▒▒░▒▒▒░▒▒░░-.      ",
    "     (░░▒▒▒▒▓▓▓▒▒▒▓▓░░░)     ",
    "    (░░▒▒▒▓▓▓▓▓▓▓▓▒▒▓▓▒░)    ",
    "     (░░▒▒▒▒▓▓▓▒▒▒▓▓░░)      ",
    "      `-░░▒▒░▒▒▒░▒▒░░-'      ",
)

# ASCII fallback orb for low-capability terminals (no shaded block glyphs).
_LOGO_ASCII: tuple[str, ...] = (
    "        .-----------.        ",
    "      .-:::==###==:::-.      ",
    "     (:::====###===##:::)    ",
    "    (:::===########==##::)   ",
    "     (:::====###===##::)     ",
    "      `-:::==###==:::-'      ",
)

# Honest, low-maintenance tips reflecting the current shell state. The home
# screen renders gracefully when this is empty.
TIPS: tuple[str, ...] = (
    "Ask Raiker to help with a task or review a repository.",
    "Use /view <id> or Ctrl+A/T/E to inspect approvals, tasks, and events inline.",
    "Prompt modes: ? side question | / command | ! proposal | @ mention.",
    "Runtime execution remains disabled; inspection views are read-only.",
)


def detect_user(env: Mapping[str, str] | None = None) -> str:
    """Best-effort current user name from environment, falling back to 'there'."""

    env = env if env is not None else os.environ
    for key in ("RAIKER_USER", "USERNAME", "USER", "LOGNAME"):
        value = env.get(key)
        if value:
            return value
    try:
        return getpass.getuser()
    except Exception:
        return "there"


def logo_lines(profile: TerminalProfile) -> tuple[str, ...]:
    return _LOGO_UNICODE if profile.unicode else _LOGO_ASCII


@dataclass(frozen=True)
class WelcomeContent:
    """Inert content bundle for the welcome/home screen."""

    version: str = __version__
    user: str = "there"
    model: str = "unknown"
    effort: str = "default"
    workspace: str = "."
    recent: tuple[ActivityItem, ...] = ()
    whats_new: tuple[str, ...] = TIPS
    returning: bool = False

    @property
    def title(self) -> str:
        return f"Raiker v{self.version}"

    @property
    def greeting(self) -> str:
        return f"Welcome back {self.user}!"


def welcome_left_lines(content: WelcomeContent, profile: TerminalProfile) -> list[str]:
    """Left column: greeting, logo orb, model/effort, workspace (centered-ish)."""

    lines: list[str] = ["", content.greeting, ""]
    lines.extend(logo_lines(profile))
    lines.extend(
        [
            "",
            f"{content.model} • {content.effort}",
            content.workspace,
            "",
        ]
    )
    return [line if profile.unicode else ascii_safe(line) for line in lines]


def _markers(profile: TerminalProfile) -> dict[str, str]:
    if profile.unicode:
        return {"done": "✓", "active": "▶", "pending": "•"}
    return {"done": "v", "active": ">", "pending": "*"}


def recent_activity_lines(content: WelcomeContent, profile: TerminalProfile) -> list[str]:
    markers = _markers(profile)
    lines = ["Recent activity"]
    if content.recent:
        for item in content.recent:
            marker = markers.get(item.marker, markers["pending"])
            lines.append(f"{marker} {item.text}")
    else:
        lines.append("No recent activity")
    return [line if profile.unicode else ascii_safe(line) for line in lines]


def whats_new_lines(content: WelcomeContent, profile: TerminalProfile) -> list[str]:
    lines = ["Tips for getting started"]
    if content.whats_new:
        for item in content.whats_new:
            lines.append(f"  {item}" if profile.unicode else f"  {item}")
    else:
        lines.append("  Ask Raiker to help with a task or review a repository.")
    return [line if profile.unicode else ascii_safe(line) for line in lines]
