"""Default layout tests for the single-panel Rich TUI.

The Rich TUI is a single-panel, Claude-Code-style transcript flow: a window header, one
main transcript panel, the input panel, and the configurable status bar. There are no
simultaneously docked side/region panels. These tests assert the default layout renders
that single panel under standard, narrow, and no-colour terminals.
"""

from __future__ import annotations

from raiker.tui.accessibility import TerminalProfile
from raiker.tui.layout import render_full_layout, render_home_layout
from raiker.tui.render_models import ActivityItem
from raiker.tui.session import UISession
from raiker.tui.status_bar import StatusBarRenderer, StatusContext
from raiker.tui.welcome import WelcomeContent


def _status() -> str:
    return StatusBarRenderer().render(StatusContext(model="qwen", approvals=2), clock="13:42")


def _session() -> UISession:
    s = UISession()
    s.transcript.add_result("prompt", "Hello from Raiker")
    return s


def _render(profile: TerminalProfile) -> str:
    return render_full_layout(
        _session(),
        status_line=_status(),
        input_hint="? side question | / command | ! command proposal | @ file mention",
        profile=profile,
    )


def test_default_layout_renders_single_transcript_panel() -> None:
    out = _render(TerminalProfile(width=120))
    assert "Raiker Session (#terminal-local)" in out  # window header
    assert "Transcript" in out
    assert "Hello from Raiker" in out


def test_default_layout_renders_input_panel() -> None:
    out = _render(TerminalProfile(width=120))
    assert "Input" in out
    assert "? side question" in out
    assert "/ command" in out
    assert "! command proposal" in out
    assert "@ file mention" in out


def test_default_layout_renders_status_bar() -> None:
    out = _render(TerminalProfile(width=120))
    assert "READY" in out
    assert "approvals:2" in out
    assert "net:blocked" in out
    assert "13:42" in out


def test_default_layout_has_no_docked_side_panels() -> None:
    out = _render(TerminalProfile(width=120))
    # Single-panel flow: no Activity / Approvals / Tool-Event drawers rendered alongside.
    for docked in (
        "Activity / Panels",
        "Approvals",
        "Tool / Event Stream",
        "Checkpoint Timeline",
        "Diff Viewer",
    ):
        assert docked not in out


def test_default_layout_narrow_does_not_crash_and_keeps_safety() -> None:
    out = _render(TerminalProfile(width=64))
    assert "Transcript" in out
    assert "READY" in out
    assert "net:blocked" in out


def test_default_layout_ascii_fallback_uses_no_box_drawing() -> None:
    out = _render(TerminalProfile(width=120, unicode=False, color=False))
    assert "│" not in out
    assert "┌" not in out


def test_home_layout_is_single_welcome_panel() -> None:
    welcome = WelcomeContent(
        user="Rahul",
        model="qwen9b",
        effort="medium",
        workspace="/ws",
        recent=(ActivityItem("done", "Inspect specs"),),
        returning=True,
    )
    out = render_home_layout(
        welcome,
        status_line=_status(),
        input_hint="? side question | / command",
        profile=TerminalProfile(width=120),
    )
    assert "Raiker v0.0.0" in out
    assert "Welcome back Rahul!" in out
    assert "qwen9b • medium" in out
    assert "Recent activity" in out
    assert "Inspect specs" in out
