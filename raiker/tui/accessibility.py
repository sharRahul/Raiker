"""Accessibility and terminal-capability helpers for the Rich TUI default access shell.

This module is a pure presentation helper. It must not import subprocess, socket,
requests, urllib, httpx, or any model/tool/network/process runtime. It only inspects
declared environment hints and rewrites text for low-capability terminals.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass

# Safety-critical status labels that must remain visible in every rendering mode,
# including no-colour, ASCII, and narrow terminals.
SAFETY_LABELS: tuple[str, ...] = ("state", "approvals", "net")

# Default column width below which the shell renders compact/narrow variants.
DEFAULT_COMPACT_BELOW = 100

# Unicode decoration -> ASCII fallback. Keeps meaning as text, never colour-only.
_ASCII_FALLBACK = {
    "█": "#",
    "░": ".",
    "▒": ":",
    "▓": "=",
    "│": "|",
    "─": "-",
    "┌": "+",
    "┐": "+",
    "└": "+",
    "┘": "+",
    "├": "+",
    "┤": "+",
    "┬": "+",
    "┴": "+",
    "┼": "+",
    "╭": "+",
    "╮": "+",
    "╰": "+",
    "╯": "+",
    "▶": ">",
    "✓": "v",
    "✔": "v",
    "✖": "x",
    "•": "*",
    "→": "->",
    "↑": "^",
    "↓": "v",
    "☁": "*",
    "⚠": "!",
    "●": "*",
    "○": "o",
}


@dataclass(frozen=True)
class TerminalProfile:
    """Declared rendering capabilities for the current terminal."""

    width: int = DEFAULT_COMPACT_BELOW
    color: bool = True
    unicode: bool = True
    interactive: bool = False
    rich_available: bool = True
    force_plain: bool = False
    compact_below: int = DEFAULT_COMPACT_BELOW

    @property
    def narrow(self) -> bool:
        return self.width < self.compact_below

    @property
    def use_rich(self) -> bool:
        """Rich rendering only when available, allowed, and interactive."""
        return self.rich_available and not self.force_plain and self.interactive


def _rich_importable() -> bool:
    try:
        import rich  # noqa: F401
    except Exception:
        return False
    return True


def detect_terminal_profile(
    *,
    env: Mapping[str, str] | None = None,
    interactive: bool | None = None,
    width: int | None = None,
    rich_available: bool | None = None,
) -> TerminalProfile:
    """Detect a :class:`TerminalProfile` from environment hints.

    ``RAIKER_TUI=plain`` forces the plain/ASCII fallback. ``RAIKER_TUI=rich``
    requests rich rendering. ``NO_COLOR`` disables colour. Nothing here launches a
    process, opens a socket, or contacts a model.
    """

    env = env if env is not None else os.environ
    mode = env.get("RAIKER_TUI", "").strip().lower()
    force_plain = mode == "plain"
    if width is None:
        width = shutil.get_terminal_size((DEFAULT_COMPACT_BELOW, 24)).columns
    if rich_available is None:
        rich_available = _rich_importable()
    no_color = bool(env.get("NO_COLOR")) or force_plain
    unicode_ok = not force_plain and _terminal_supports_unicode(env)
    return TerminalProfile(
        width=int(width),
        color=not no_color,
        unicode=unicode_ok,
        interactive=bool(interactive),
        rich_available=bool(rich_available),
        force_plain=force_plain,
    )


def _terminal_supports_unicode(env: Mapping[str, str]) -> bool:
    encoding = (env.get("LC_ALL") or env.get("LC_CTYPE") or env.get("LANG") or "").lower()
    if not encoding:
        # Assume UTF-8 capable when no locale hint is present; fall back is still ASCII-safe.
        return True
    return "utf" in encoding


def ascii_safe(text: str) -> str:
    """Rewrite decorative Unicode to ASCII so plain terminals stay readable."""

    for unicode_char, fallback in _ASCII_FALLBACK.items():
        text = text.replace(unicode_char, fallback)
    return text


def safe_lines(lines: list[str], profile: TerminalProfile) -> list[str]:
    """Apply ASCII fallback to every line when the terminal lacks Unicode support."""

    if profile.unicode:
        return list(lines)
    return [ascii_safe(line) for line in lines]
