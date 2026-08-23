from __future__ import annotations

import argparse
import sys
from pathlib import Path

from raiker.terminal.app import run_terminal_client


def _use_utf8_output() -> None:
    """Make the terminal client's own output survive a legacy Windows code page.

    Raiker's command output is full of characters that do not exist in cp1252 —
    an em dash between a label and its value, a middle dot between counts, and
    the empty-set sign the restore preflight uses for a file with no pre-image.
    On Windows, `sys.stdout` falls back to the ANSI code page when the console
    is not UTF-8 or when output is redirected to a file, and encoding one of
    those characters raises `UnicodeEncodeError` **mid-print** — so
    `raiker` piped to a file died on a command that works interactively.

    Reconfiguring here rather than replacing the characters is the fix that
    scales: the alternative is auditing every string the CLI can print, and
    getting it wrong again the next time one is added. `errors="replace"` keeps
    a console that genuinely cannot render a character from taking the command
    down with it.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            # A stream that cannot be reconfigured (already detached, or a
            # non-text wrapper) is left exactly as it was.
            continue


def main(argv: list[str] | None = None) -> int:
    _use_utf8_output()
    parser = argparse.ArgumentParser(prog="raiker", description="Open the Raiker terminal client.")
    parser.add_argument(
        "--workspace", default=".", help="Workspace root for local Phase 1 runtime state."
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Submit one prompt through the terminal client path and exit.",
    )
    args = parser.parse_args(argv)
    return run_terminal_client(workspace_root=Path(args.workspace), prompt=args.prompt)


if __name__ == "__main__":
    raise SystemExit(main())
