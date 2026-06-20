from __future__ import annotations

from raiker.tui.accessibility import (
    SAFETY_LABELS,
    TerminalProfile,
    ascii_safe,
    detect_terminal_profile,
)
from raiker.tui.layout import render_full_layout
from raiker.tui.session import UISession
from raiker.tui.status_bar import StatusBarConfig, StatusBarRenderer, StatusContext


def _render(profile: TerminalProfile) -> str:
    status = StatusBarRenderer(StatusBarConfig(use_blocks=profile.unicode)).render(
        StatusContext(model="qwen", approvals=1, network="blocked"), clock="09:00"
    )
    session = UISession()
    session.transcript.add_result("prompt", "hello")
    return render_full_layout(
        session,
        status_line=status,
        input_hint="? side question | / command",
        profile=profile,
    )


def test_no_colour_rendering_keeps_all_safety_labels() -> None:
    out = _render(TerminalProfile(width=120, color=False))
    assert "READY" in out  # state label
    assert "net:blocked" in out  # network label
    assert "approvals:1" in out  # approvals label
    assert "Transcript" in out  # single main panel


def test_state_network_approvals_labels_are_text_not_colour_only() -> None:
    out = _render(TerminalProfile(width=120, color=False))
    # state value is rendered as a literal word, not a colour
    assert "READY" in out
    assert "net:" in out
    assert "approvals:" in out
    assert set(SAFETY_LABELS) == {"state", "approvals", "net"}


def test_ascii_fallback_replaces_unicode_decoration() -> None:
    assert ascii_safe("███░░░") == "###..."
    assert ascii_safe("✓ done") == "v done"
    assert ascii_safe("▶ active") == "> active"
    assert "│" not in ascii_safe("│ pipe")


def test_ascii_profile_layout_has_no_box_unicode() -> None:
    out = _render(TerminalProfile(width=120, unicode=False, color=False))
    for unicode_char in ("│", "─", "┌", "█", "✓", "▶", "•"):
        assert unicode_char not in out
    assert "Transcript" in out
    assert "net:blocked" in out


def test_narrow_no_colour_rendering_does_not_crash() -> None:
    out = _render(TerminalProfile(width=58, color=False, unicode=False))
    assert "READY" in out
    assert "net:blocked" in out
    assert "approvals:1" in out


def test_detect_terminal_profile_plain_forces_ascii_and_no_colour() -> None:
    profile = detect_terminal_profile(
        env={"RAIKER_TUI": "plain"}, interactive=True, width=120, rich_available=True
    )
    assert profile.force_plain is True
    assert profile.color is False
    assert profile.unicode is False
    assert profile.use_rich is False  # plain disables rich rendering


def test_detect_terminal_profile_no_color_env() -> None:
    profile = detect_terminal_profile(
        env={"NO_COLOR": "1"}, interactive=False, width=120, rich_available=True
    )
    assert profile.color is False
    assert profile.use_rich is False  # non-interactive never enters rich app


def test_detect_terminal_profile_rich_when_interactive() -> None:
    profile = detect_terminal_profile(
        env={"RAIKER_TUI": "rich", "LANG": "en_US.UTF-8"},
        interactive=True,
        width=120,
        rich_available=True,
    )
    assert profile.use_rich is True
    assert profile.unicode is True
