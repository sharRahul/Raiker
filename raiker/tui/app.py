from __future__ import annotations

import sys
from pathlib import Path

from raiker.cli.commands import handle_slash_command, submit_terminal_prompt
from raiker.tui.status_bar import StatusBarRenderer

WELCOME = "Raiker terminal client. Type /help, /quit, or a prompt."


def run_terminal_client(*, workspace_root: str | Path = ".", prompt: str | None = None) -> int:
    print(WELCOME)
    print(StatusBarRenderer().render())
    if prompt is not None:
        if prompt.startswith("/"):
            print(handle_slash_command(prompt, workspace_root=workspace_root))
        else:
            print(submit_terminal_prompt(prompt, workspace_root=workspace_root))
        return 0
    if not sys.stdin.isatty():
        print("Non-interactive input detected; terminal client started and exited safely.")
        return 0
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("Exiting Raiker.")
            return 0
        if not line:
            continue
        if line in {"/quit", "/exit"}:
            print("Exiting Raiker.")
            return 0
        if line.startswith("/"):
            print(handle_slash_command(line, workspace_root=workspace_root))
        else:
            print(submit_terminal_prompt(line, workspace_root=workspace_root))
