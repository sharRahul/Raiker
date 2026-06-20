"""Plain line-oriented fallback terminal client for Raiker.

This is the non-Textual path. It is used when:
  * ``RAIKER_TUI=plain`` is set,
  * ``--prompt`` submits one prompt and exits,
  * stdin is non-interactive.

The interactive default is the native Raiker TUI (Textual) in
``raiker.tui.textual_app``. This module is deliberately minimal and reliable:
no rich panels, no docked regions, no overlays. It prints a one-line status
header and routes prompts/commands through the existing handlers.

This shell adds no runtime authority. Prompts route through
``submit_terminal_prompt`` and slash commands route through
``handle_slash_command``. No tool, model, plugin, channel, socket, or process
is opened directly from this module.
"""

from __future__ import annotations

import sys
from pathlib import Path

from raiker.cli.commands import handle_slash_command, submit_terminal_prompt
from raiker.tui.accessibility import TerminalProfile, ascii_safe, detect_terminal_profile
from raiker.tui.command_palette import render_command_palette
from raiker.tui.status_bar import StatusBarConfig, StatusBarRenderer, StatusContext

WELCOME = "Raiker terminal client. Type /help, /commands, /quit, or a prompt."
_PALETTE_COMMANDS = {"/commands", "/palette"}
_EXIT_COMMANDS = {"/q", "/quit", "/exit"}


def _safe(factory, default):  # type: ignore[no-untyped-def]
    try:
        return factory()
    except Exception:
        return default


def _selected_model(workspace_root: str | Path) -> str:
    def _resolve() -> str:
        from raiker.cli.commands import _selected_profile
        from raiker.models.registry import ModelProfileRegistry

        registry = ModelProfileRegistry.load()
        return _selected_profile(registry, workspace_root).profile_id

    return _safe(_resolve, "unknown")


def _approval_count(workspace_root: str | Path) -> int:
    def _count() -> int:
        from raiker.approvals import ApprovalInbox
        from raiker.storage.sqlite import SQLiteStore

        return len(ApprovalInbox(SQLiteStore(workspace_root)).list_pending())

    return _safe(_count, 0)


def _status_context(workspace_root: str | Path) -> StatusContext:
    return StatusContext(
        state="READY",
        task="idle",
        approvals=_approval_count(workspace_root),
        model=_selected_model(workspace_root),
        network="blocked",
        cwd_label=str(workspace_root),
        git_branch="",
    )


def _status_config(profile: TerminalProfile) -> StatusBarConfig:
    return StatusBarConfig(use_blocks=profile.unicode)


def _route_input(line: str, workspace_root: str | Path, profile: TerminalProfile) -> str:
    line = line.strip()
    if line in _PALETTE_COMMANDS:
        return render_command_palette(profile)
    if line.startswith("/"):
        return handle_slash_command(line, workspace_root=workspace_root)
    return submit_terminal_prompt(line, workspace_root=workspace_root)


def _plain(line: str, profile: TerminalProfile) -> str:
    return line if profile.unicode else ascii_safe(line)


def _print_header(workspace_root: str | Path, profile: TerminalProfile) -> None:
    status = _status_context(workspace_root)
    renderer = StatusBarRenderer(_status_config(profile))
    print(_plain(WELCOME, profile))
    rendered_text = renderer.render_status_line(status, compact=profile.narrow, width=profile.width)
    rendered_str = rendered_text.plain if hasattr(rendered_text, "plain") else str(rendered_text)
    print(_plain(rendered_str, profile))


def _run_prompt_mode(
    prompt: str, workspace_root: str | Path, profile: TerminalProfile
) -> int:
    _print_header(workspace_root, profile)
    print(_route_input(prompt, workspace_root, profile))
    return 0


def _run_plain_interactive(workspace_root: str | Path, profile: TerminalProfile) -> int:
    _print_header(workspace_root, profile)
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
    if profile.force_plain:
        return _run_plain_interactive(workspace_root, profile)
    return _run_textual_interactive(workspace_root, profile)


def _run_textual_interactive(workspace_root: str | Path, profile: TerminalProfile) -> int:
    from raiker.tui.textual_app import run_textual_tui

    return run_textual_tui(workspace_root=workspace_root, profile=profile)
