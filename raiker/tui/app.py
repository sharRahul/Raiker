"""Terminal entry point for Raiker's Rich TUI default access shell.

``run_terminal_client`` is the public entry used by ``raiker``. It chooses between
non-interactive prompt mode (line-oriented, exits) and the interactive default layout,
and between rich rendering and the plain fallback. Every prompt and slash command is
routed through the existing command handlers — this shell adds no runtime authority and
calls no tools, models, sockets, or processes of its own.
"""

from __future__ import annotations

import sys
from pathlib import Path

from raiker.cli.commands import handle_slash_command, submit_terminal_prompt
from raiker.tui.accessibility import TerminalProfile, ascii_safe, detect_terminal_profile
from raiker.tui.command_palette import render_command_palette
from raiker.tui.render_models import (
    ActivityContent,
    ActivityItem,
    InputContent,
    MainPanelContent,
)
from raiker.tui.status_bar import StatusBarConfig, StatusBarRenderer, StatusContext

WELCOME = "Raiker terminal client. Type /help, /commands, /quit, or a prompt."
_PALETTE_COMMANDS = {"/commands", "/palette"}
_EXIT_COMMANDS = {"/q", "/quit", "/exit"}


def _safe(factory, default):  # type: ignore[no-untyped-def]
    try:
        return factory()
    except Exception:
        return default


def _selected_model(workspace_root: str | Path) -> tuple[str, str]:
    """Return (model_profile_id, reasoning_effort) via existing safe paths only."""

    def _resolve() -> tuple[str, str]:
        from raiker.cli.commands import _selected_profile
        from raiker.models.registry import ModelProfileRegistry
        from raiker.storage.sqlite import SQLiteStore

        registry = ModelProfileRegistry.load()
        profile = _selected_profile(registry, workspace_root)
        effort = "default"
        state = SQLiteStore(workspace_root).load_model_session_state("terminal-local")
        if state is not None and state.reasoning_effort:
            effort = state.reasoning_effort
        return profile.profile_id, effort

    return _safe(_resolve, ("unknown", "default"))


def _approval_count(workspace_root: str | Path) -> str:
    def _count() -> str:
        from raiker.approvals import ApprovalInbox
        from raiker.storage.sqlite import SQLiteStore

        return str(len(ApprovalInbox(SQLiteStore(workspace_root)).list_pending()))

    return _safe(_count, "unknown")


def _last_event(workspace_root: str | Path) -> str:
    def _latest() -> str:
        from raiker.events.query import EventViewer
        from raiker.storage.sqlite import SQLiteStore

        events = EventViewer(SQLiteStore(workspace_root)).list_events(limit=1)
        if not events:
            return "none"
        return str(events[0]["event_type"])

    return _safe(_latest, "none")


def _recent_activity(workspace_root: str | Path) -> tuple[ActivityItem, ...]:
    def _items() -> tuple[ActivityItem, ...]:
        from raiker.events.writer import EventLogWriter
        from raiker.storage.sqlite import SQLiteStore
        from raiker.tasks.manager import TaskManager

        store = SQLiteStore(workspace_root)
        manager = TaskManager(store, EventLogWriter(store))
        marker_map = {
            "completed": "done",
            "succeeded": "done",
            "running": "active",
            "in_progress": "active",
        }
        result: list[ActivityItem] = []
        for task in manager.list_tasks()[:3]:
            result.append(ActivityItem(marker_map.get(task.status, "pending"), task.title))
        return tuple(result)

    return _safe(_items, ())


def _status_config(profile: TerminalProfile) -> StatusBarConfig:
    return StatusBarConfig(use_blocks=profile.unicode)


def build_shell_state(
    workspace_root: str | Path, profile: TerminalProfile
) -> tuple[MainPanelContent, ActivityContent, InputContent, StatusContext]:
    workspace = str(workspace_root)
    model, effort = _selected_model(workspace_root)
    approvals = _approval_count(workspace_root)
    last_event = _last_event(workspace_root)
    recent = _recent_activity(workspace_root)

    main = MainPanelContent(workspace=workspace, model=model, effort=effort)
    activity = ActivityContent(
        workspace=workspace,
        network="blocked",
        approvals=approvals,
        model=model,
        last_event=last_event,
        recent=recent,
    )
    status = StatusContext(
        state="READY",
        task="idle",
        approvals=approvals if approvals.isdigit() else 0,  # type: ignore[arg-type]
        model=model,
        network="blocked",
        last_event=last_event,
    )
    return main, activity, InputContent(), status


def _route_input(line: str, workspace_root: str | Path, profile: TerminalProfile) -> str:
    line = line.strip()
    if line in _PALETTE_COMMANDS:
        return render_command_palette(profile)
    if line.startswith("/"):
        return handle_slash_command(line, workspace_root=workspace_root)
    return submit_terminal_prompt(line, workspace_root=workspace_root)


def _plain(line: str, profile: TerminalProfile) -> str:
    return line if profile.unicode else ascii_safe(line)


def _print_header(workspace_root: str | Path, profile: TerminalProfile) -> StatusContext:
    _main, _activity, _input, status = build_shell_state(workspace_root, profile)
    renderer = StatusBarRenderer(_status_config(profile))
    print(_plain(WELCOME, profile))
    print(_plain(renderer.render(status, compact=profile.narrow, width=profile.width), profile))
    return status


def _run_prompt_mode(
    prompt: str, workspace_root: str | Path, profile: TerminalProfile
) -> int:
    _print_header(workspace_root, profile)
    print(_route_input(prompt, workspace_root, profile))
    return 0


def _run_rich_interactive(workspace_root: str | Path, profile: TerminalProfile) -> int:
    from rich.console import Console

    from raiker.tui.default_layout import render_default_layout
    from raiker.tui.panels import build_result_panel

    console = Console()
    main, activity, input_content, status = build_shell_state(workspace_root, profile)
    status_line = StatusBarRenderer(_status_config(profile)).render(
        status, compact=profile.narrow, width=profile.width
    )
    print(
        render_default_layout(
            main=main,
            activity=activity,
            input_content=input_content,
            status_line=status_line,
            profile=profile,
        )
    )
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("Exiting Raiker.")
            return 0
        if not line:
            continue
        if line in _EXIT_COMMANDS:
            print("Exiting Raiker.")
            return 0
        result = _route_input(line, workspace_root, profile)
        console.print(build_result_panel(result, profile))


def _run_plain_interactive(workspace_root: str | Path, profile: TerminalProfile) -> int:
    _print_header(workspace_root, profile)
    print(_plain(InputContent().hint, profile))
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("Exiting Raiker.")
            return 0
        if not line:
            continue
        if line in _EXIT_COMMANDS:
            print("Exiting Raiker.")
            return 0
        print(_route_input(line, workspace_root, profile))


def run_terminal_client(
    *,
    workspace_root: str | Path = ".",
    prompt: str | None = None,
    profile: TerminalProfile | None = None,
) -> int:
    if profile is None:
        profile = detect_terminal_profile(interactive=sys.stdin.isatty())
    if prompt is not None:
        return _run_prompt_mode(prompt, workspace_root, profile)
    if not profile.interactive:
        _print_header(workspace_root, profile)
        print("Non-interactive input detected; terminal client started and exited safely.")
        return 0
    if profile.use_rich:
        return _run_rich_interactive(workspace_root, profile)
    return _run_plain_interactive(workspace_root, profile)
