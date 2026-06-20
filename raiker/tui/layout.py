"""Single-panel default layout for the interactive Rich TUI.

The Rich TUI is a single-panel, Claude-Code-style transcript flow (docs/UI_UX_DESIGN_SPEC.md
-> Default Layout): a window header, one main transcript panel, an optional live execution
indicator, the input panel, and the configurable status bar. There are no simultaneously
docked side/region panels.

This module is pure presentation. It reads the inert :class:`UISession` and the transcript.
It performs no runtime execution and contacts no tools, models, sockets, or processes.
"""

from __future__ import annotations

import io
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel as RichPanel
from rich.table import Table
from rich.text import Text

from raiker.tui.accessibility import TerminalProfile, ascii_safe
from raiker.tui.session import UISession
from raiker.tui.transcript import ExecutionIndicator
from raiker.tui.welcome import (
    WelcomeContent,
    _markers,
    welcome_left_lines,
)


def _console(profile: TerminalProfile) -> Console:
    return Console(
        file=io.StringIO(),
        width=max(40, profile.width),
        no_color=not profile.color,
        legacy_windows=False,
        emoji=False,
        highlight=False,
    )


def _box(profile: TerminalProfile) -> box.Box:
    return box.SQUARE if profile.unicode else box.ASCII


def _t(line: str, profile: TerminalProfile) -> str:
    return line if profile.unicode else ascii_safe(line)


def _panel(title: str, lines: list[str], profile: TerminalProfile, *, focused: bool = False) -> RichPanel:
    body = "\n".join(_t(line, profile) for line in lines) or "(empty)"
    marker = "» " if (focused and profile.unicode) else ("> " if focused else "")
    return RichPanel(body, title=_t(marker + title, profile), box=_box(profile), expand=True)


def build_welcome_lines(
    content: WelcomeContent,
    profile: TerminalProfile,
    *,
    input_hint: str,
    width: int | None = None,
) -> list[Text]:
    """Build the welcome screen as a list of styled Text lines with custom framing.

    Layout:
      ┌──── Raiker v0.0.0 ────┐
      │ left col   │ right col │
      │            │─── divider┤
      │            │ right col │
      ─────────────────────────
        > input hint
      ─────────────────────────
    """

    W = max(70, width or profile.width)
    u = profile.unicode

    # Box characters
    TL = "┌" if u else "+"
    TR = "┐" if u else "+"
    H = "─" if u else "-"
    V = "│" if u else "|"
    LT = "├" if u else "+"
    RT = "┤" if u else "+"

    header_style = "bold coral3 underline"
    border_style = "dim"
    lines: list[Text] = []

    # ── Top border with title ──────────────────────────────────────────
    title_str = f" {content.title} "
    ld = 8  # left dashes before title
    rd = max(0, W - 2 - ld - len(title_str))
    top = Text()
    top.append(TL + H * ld, style=border_style)
    top.append(title_str, style="bold")
    top.append(H * rd + TR, style=border_style)
    lines.append(top)

    # ── Prepare column content ─────────────────────────────────────────
    left_lines = welcome_left_lines(content, profile)

    # Right column items: (text, is_divider, is_header, is_dim)
    right_items: list[tuple[str, bool, bool, bool]] = []
    right_items.append(("Recent activity", False, True, False))
    markers = _markers(profile)
    if content.recent:
        for item in content.recent:
            m = markers.get(item.marker, markers["pending"])
            right_items.append((f"{m} {item.text}", False, False, False))
    else:
        right_items.append(("No recent activity", False, False, True))

    right_items.append(("", True, False, False))  # internal divider

    right_items.append(("Tips for getting started", False, True, False))
    if content.whats_new:
        for tip in content.whats_new:
            right_items.append((tip, False, False, False))
    else:
        right_items.append(
            ("Ask Raiker to help with a task or review a repository.", False, False, False)
        )

    # ── Render rows ────────────────────────────────────────────────────
    if u:
        lcw = (W - 3) // 2          # left column width (incl. padding)
        rcw = W - 3 - lcw           # right column width (incl. padding)
        liw = max(1, lcw - 2)       # left inner content width
        riw = max(1, rcw - 2)       # right inner content width

        max_h = max(len(left_lines), len(right_items))
        left_lines += [""] * (max_h - len(left_lines))
        right_items += [("", False, False, False)] * (max_h - len(right_items))

        for i in range(max_h):
            lstr = left_lines[i][:liw].ljust(liw)
            rstr, is_div, is_hdr, is_dim = right_items[i]

            row = Text()
            row.append(V + " ", style=border_style)
            row.append(lstr, style="bold" if i == 1 else "")
            row.append(" " + V, style=border_style)

            if is_div:
                row.append(H * rcw + RT, style=border_style)
            else:
                rp = (rstr or "")[:riw].ljust(riw)
                row.append(" ", style=border_style)
                if is_hdr:
                    row.append(rp, style=header_style)
                elif is_dim:
                    row.append(rp, style="dim")
                else:
                    row.append(rp)
                row.append(" " + V, style=border_style)

            lines.append(row)
    else:
        # ASCII / narrow: single column stack
        inner = max(1, W - 4)
        for i, lstr in enumerate(left_lines):
            row = Text()
            row.append(V + " ", style=border_style)
            row.append(lstr[:inner].ljust(inner), style="bold" if i == 1 else "")
            row.append(" " + V, style=border_style)
            lines.append(row)
        lines.append(_ascii_blank_row(V, H, W, border_style))
        for rstr, is_div, is_hdr, is_dim in right_items:
            if is_div:
                row = Text()
                row.append(LT + H * (W - 2) + RT, style=border_style)
                lines.append(row)
            else:
                row = Text()
                row.append(V + " ", style=border_style)
                s = (rstr or "")[:inner].ljust(inner)
                if is_hdr:
                    row.append(s, style=header_style)
                elif is_dim:
                    row.append(s, style="dim")
                else:
                    row.append(s)
                row.append(" " + V, style=border_style)
                lines.append(row)

    # ── Content bottom (no corners, full width) ────────────────────────
    lines.append(Text(H * W, style=border_style))

    # ── Input line ─────────────────────────────────────────────────────
    inp = f"  > {input_hint}"
    if len(inp) > W:
        inp = inp[:W]
    lines.append(Text(inp, style="dim"))

    # ── Final bottom (no corners, full width) ──────────────────────────
    lines.append(Text(H * W, style=border_style))

    return lines


def _ascii_blank_row(v: str, h: str, w: int, style: str) -> Text:
    row = Text()
    row.append(v, style=style)
    row.append(" " * (w - 2), style=style)
    row.append(v, style=style)
    return row


def _window_header(session: UISession, profile: TerminalProfile) -> str:
    # docs -> Window Header Behaviour: "<view name> (#<session/task id>)"
    header = f"{session.view_name} (#{session.session_id})"
    meta = f"approvals:{session.approval_mode}"
    return _t(f"{header}    {meta}", profile)


def render_home_layout(
    content: WelcomeContent,
    *,
    status_line: str,
    input_hint: str,
    profile: TerminalProfile,
) -> str:
    """Render the documented default welcome/home layout (docs -> Default Layout)."""

    console = _console(profile)
    for line in build_welcome_lines(content, profile, input_hint=input_hint):
        console.print(line)
    if status_line:
        console.print(Text(_t(status_line, profile), style="dim"))
    return console.file.getvalue()  # type: ignore[attr-defined]


def render_full_layout(
    session: UISession,
    *,
    workspace_root: str | Path = ".",
    status_line: str,
    input_hint: str,
    profile: TerminalProfile,
    execution: ExecutionIndicator | None = None,
    transcript_limit: int | None = None,
) -> str:
    """Render the single-panel interactive layout as deterministic text.

    The layout is one main transcript panel (no docked side/region panels), an optional
    live execution indicator, the input panel, and the status bar. ``workspace_root`` is
    accepted for call-site compatibility; the single-panel transcript needs no per-region
    workspace lookups.
    """

    del workspace_root  # single-panel layout does not render per-region panels

    console = _console(profile)

    main_lines = session.transcript.render_lines(profile, limit=transcript_limit)
    main_panel = _panel("Transcript", main_lines, profile)

    outer = Table.grid(expand=True)
    outer.add_column()
    outer.add_row(_panel("", [_window_header(session, profile)], profile))
    outer.add_row(main_panel)

    if execution is not None and execution.active:
        outer.add_row(_panel("", [execution.render(profile)], profile))

    outer.add_row(_panel("Input", [_t(f"> {input_hint}", profile)], profile))
    outer.add_row(RichPanel(_t(status_line, profile), box=_box(profile), expand=True))

    console.print(outer)
    return console.file.getvalue()  # type: ignore[attr-defined]
