"""Pure panel renderers for the Rich TUI default access shell.

These functions build display-only renderables for the four required default panels:
Primary / Main, Activity, Input, and Status Bar. They read only the inert content
dataclasses passed in. They must not import subprocess, socket, requests, urllib, or
httpx; must not call tools, models, plugins, channels, memory/graph writes; must not
mutate files; and must not execute approvals or proposals.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich import box
from rich.panel import Panel as RichPanel

from raiker.tui.accessibility import TerminalProfile, ascii_safe
from raiker.tui.render_models import ActivityContent, InputContent, MainPanelContent

# Activity markers per capability, with ASCII fallback.
_MARKERS_UNICODE = {"done": "✓", "active": "▶", "pending": "•"}
_MARKERS_ASCII = {"done": "v", "active": ">", "pending": "*"}


@dataclass(frozen=True)
class Panel:
    """Lightweight descriptor for the minimum bootable default panels."""

    panel_id: str
    display_name: str
    can_mutate_state: bool = False


DEFAULT_PANELS = [
    Panel("primary", "Primary / Main Panel"),
    Panel("activity", "Activity Panel"),
    Panel("input", "Input Panel"),
    Panel("status_bar", "Status Bar Panel"),
]


def _box(profile: TerminalProfile) -> box.Box:
    return box.SQUARE if profile.unicode else box.ASCII


def _markers(profile: TerminalProfile) -> dict[str, str]:
    return _MARKERS_UNICODE if profile.unicode else _MARKERS_ASCII


def _text(line: str, profile: TerminalProfile) -> str:
    return line if profile.unicode else ascii_safe(line)


def build_main_panel(content: MainPanelContent, profile: TerminalProfile) -> RichPanel:
    lines = [
        content.welcome,
        "",
        f"workspace: {content.workspace}",
        f"mode: {content.mode}",
        f"model: {content.model} • {content.effort}",
    ]
    if content.body:
        lines.append("")
        lines.extend(content.body)
    body = "\n".join(_text(line, profile) for line in lines)
    return RichPanel(body, title=_text(content.title, profile), box=_box(profile), expand=True)


def build_activity_panel(
    content: ActivityContent, profile: TerminalProfile, *, compact: bool = False
) -> RichPanel:
    markers = _markers(profile)
    lines = ["Recent Activity:"]
    recent = content.recent[:3] if (compact or profile.narrow) else content.recent
    if recent:
        for item in recent:
            marker = markers.get(item.marker, markers["pending"])
            lines.append(f"{marker} {item.text}")
    else:
        lines.append("(no recent activity)")
    # Safe summary fields. No raw prompts, file contents, diffs, tool output, or secrets.
    lines.extend(
        [
            "",
            f"workspace: {content.workspace}",
            f"client: {content.client_mode}",
            f"runtime: {content.runtime_safety}",
            f"net: {content.network}",
            f"approvals: {content.approvals}",
            f"model: {content.model}",
        ]
    )
    if not (compact or profile.narrow):
        lines.append(f"last: {content.last_event}")
    lines.extend(["", content.hint])
    body = "\n".join(_text(line, profile) for line in lines)
    return RichPanel(body, title="Activity", box=_box(profile), expand=True)


def build_input_panel(content: InputContent, profile: TerminalProfile) -> RichPanel:
    body = _text(f"> {content.hint}", profile)
    return RichPanel(body, title="Input", box=_box(profile), expand=True)


def build_status_panel(status_line: str, profile: TerminalProfile) -> RichPanel:
    return RichPanel(_text(status_line, profile), box=_box(profile), expand=True)


def build_result_panel(result: str, profile: TerminalProfile, *, title: str = "Result") -> RichPanel:
    """Render command/prompt output text in the Primary / Main panel surface."""

    return RichPanel(_text(result, profile), title=title, box=_box(profile), expand=True)
