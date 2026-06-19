"""Compose the documented default Rich TUI layout from docs/UI_UX_DESIGN_SPEC.md.

The default layout is exactly four panels: Primary / Main, Activity, Input, and Status
Bar. This module combines the pure panel renderers into a width-adaptive grid and
returns deterministic text (so tests can assert structure under standard, narrow, and
no-colour terminals). It performs no runtime execution and contacts no tools, models,
sockets, or processes.
"""

from __future__ import annotations

import io

from rich.console import Console
from rich.table import Table

from raiker.tui.accessibility import TerminalProfile
from raiker.tui.panels import (
    build_activity_panel,
    build_input_panel,
    build_main_panel,
    build_status_panel,
)
from raiker.tui.render_models import ActivityContent, InputContent, MainPanelContent


def _console(profile: TerminalProfile) -> Console:
    return Console(
        file=io.StringIO(),
        width=max(40, profile.width),
        no_color=not profile.color,
        legacy_windows=False,
        emoji=False,
        highlight=False,
    )


def render_default_layout(
    *,
    main: MainPanelContent,
    activity: ActivityContent,
    input_content: InputContent,
    status_line: str,
    profile: TerminalProfile,
) -> str:
    """Render the four-panel default layout as deterministic text."""

    console = _console(profile)
    main_panel = build_main_panel(main, profile)
    input_panel = build_input_panel(input_content, profile)
    status_panel = build_status_panel(status_line, profile)

    outer = Table.grid(expand=True)
    outer.add_column()

    if profile.narrow:
        # Narrow: stack main panel, compact/collapsed activity, input, then status bar.
        activity_panel = build_activity_panel(activity, profile, compact=True)
        outer.add_row(main_panel)
        outer.add_row(activity_panel)
        outer.add_row(input_panel)
        outer.add_row(status_panel)
    else:
        # Standard: main panel (larger) left, activity panel (smaller) right.
        activity_panel = build_activity_panel(activity, profile)
        top = Table.grid(expand=True)
        top.add_column(ratio=3)
        top.add_column(ratio=2)
        top.add_row(main_panel, activity_panel)
        outer.add_row(top)
        outer.add_row(input_panel)
        outer.add_row(status_panel)

    console.print(outer)
    text: str = console.file.getvalue()  # type: ignore[attr-defined]
    return text
