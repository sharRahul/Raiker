from __future__ import annotations

from raiker.tui.accessibility import TerminalProfile
from raiker.tui.default_layout import render_default_layout
from raiker.tui.render_models import (
    ActivityContent,
    ActivityItem,
    InputContent,
    MainPanelContent,
)
from raiker.tui.status_bar import StatusBarRenderer, StatusContext


def _content() -> tuple[MainPanelContent, ActivityContent, InputContent]:
    main = MainPanelContent(workspace="/ws", model="qwen", effort="medium")
    activity = ActivityContent(
        workspace="/ws",
        approvals="2",
        model="qwen",
        last_event="tool_completed",
        recent=(
            ActivityItem("done", "Inspect specs"),
            ActivityItem("active", "Update architecture"),
            ActivityItem("pending", "Verify docs"),
        ),
    )
    return main, activity, InputContent()


def _render(profile: TerminalProfile) -> str:
    main, activity, input_content = _content()
    status = StatusBarRenderer().render(StatusContext(model="qwen", approvals=2), clock="13:42")
    return render_default_layout(
        main=main,
        activity=activity,
        input_content=input_content,
        status_line=status,
        profile=profile,
    )


def test_default_layout_renders_main_panel() -> None:
    out = _render(TerminalProfile(width=120))
    assert "Raiker v0.0.0" in out
    assert "Hello / Welcome back" in out
    assert "workspace: /ws" in out
    assert "Rich TUI default access shell" in out


def test_default_layout_renders_activity_panel() -> None:
    out = _render(TerminalProfile(width=120))
    assert "Activity" in out
    assert "Recent Activity:" in out
    assert "Inspect specs" in out
    assert "rich_tui_default" in out
    assert "runtime execution disabled" in out


def test_default_layout_renders_input_panel() -> None:
    out = _render(TerminalProfile(width=120))
    assert "Input" in out
    assert "? side question" in out
    assert "/ command" in out
    assert "! command proposal" in out
    assert "@ file mention" in out


def test_default_layout_renders_status_bar_panel() -> None:
    out = _render(TerminalProfile(width=120))
    assert "READY" in out
    assert "approvals:2" in out
    assert "net:blocked" in out
    assert "13:42" in out


def test_default_layout_uses_documented_default_language() -> None:
    out = _render(TerminalProfile(width=120))
    # Documented default-layout vocabulary, not an invented dashboard.
    for marker in ("Recent Activity:", "? side question", "Rich TUI default access shell"):
        assert marker in out


def test_default_layout_does_not_render_advanced_developer_panels() -> None:
    out = _render(TerminalProfile(width=120))
    for advanced in (
        "Diff Viewer",
        "Checkpoint Timeline",
        "Security/Policy Panel",
        "Tool / Event Stream",
        "Graph / Codemap",
        "Storage Panel",
        "Diagnostics Panel",
    ):
        assert advanced not in out


def test_default_layout_narrow_does_not_crash_and_keeps_panels() -> None:
    out = _render(TerminalProfile(width=64))
    assert "Raiker v0.0.0" in out
    assert "Recent Activity:" in out
    assert "? side question" in out
    assert "READY" in out
    assert "net:blocked" in out


def test_default_layout_only_four_default_panels() -> None:
    main, activity, input_content = _content()
    from raiker.tui.panels import DEFAULT_PANELS

    ids = {p.panel_id for p in DEFAULT_PANELS}
    assert ids == {"primary", "activity", "input", "status_bar"}
    assert all(p.can_mutate_state is False for p in DEFAULT_PANELS)
