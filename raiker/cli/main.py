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


_MARK = {"pass": "ok  ", "warn": "warn", "fail": "FAIL", "info": "info"}


def doctor(argv: list[str]) -> int:
    """RU-08 — ``raiker doctor``: what this machine can do, and what to fix.

    The same local checks the first-run wizard reads (:func:`system_readiness`),
    printed one per line with the fix beside anything that is not passing. It
    contacts nothing and changes nothing; it exits 1 when a mandatory
    requirement is not met, so a script can stop on it.
    """
    parser = argparse.ArgumentParser(
        prog="raiker doctor", description="Check this machine and say what to fix."
    )
    parser.add_argument("--workspace", default=".", help="Raiker's data folder to check.")
    parser.add_argument("--json", action="store_true", help="Print the checks as JSON.")
    args = parser.parse_args(argv)
    from raiker.app.system_check import system_readiness

    report = system_readiness(Path(args.workspace).resolve())
    if args.json:
        import json

        print(json.dumps(report, indent=2, default=str))
        return 0 if report["ready"] else 1
    for check in report["checks"]:
        print(f"[{_MARK.get(check['state'], check['state'])}] {check['label']}: {check['detail']}")
        if check.get("remedy") and check["state"] in {"warn", "fail"}:
            print(f"       Fix: {check['remedy']}")
    if report["ready"]:
        print("Ready: every mandatory requirement is met.")
        return 0
    print("Not ready: fix the lines marked FAIL, then run raiker doctor again.")
    return 1


def mcp_serve(argv: list[str]) -> int:
    """RU-15 — ``raiker mcp-serve``: let another agent read Raiker over MCP (stdio)."""
    parser = argparse.ArgumentParser(
        prog="raiker mcp-serve",
        description="Serve Raiker's memory, notes, conversations, Library and tasks to another agent over MCP (stdio). Read-only.",
    )
    parser.add_argument("--workspace", default=".", help="Raiker's data folder.")
    args = parser.parse_args(argv)
    from raiker.interop.mcp_server import serve

    return serve(Path(args.workspace).resolve())


def main(argv: list[str] | None = None) -> int:
    _use_utf8_output()
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ["doctor"]:
        return doctor(arguments[1:])
    if arguments[:1] == ["mcp-serve"]:
        return mcp_serve(arguments[1:])
    parser = argparse.ArgumentParser(prog="raiker", description="Open the Raiker terminal client.")
    parser.add_argument(
        "--workspace", default=".", help="Workspace root for local Phase 1 runtime state."
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Submit one prompt through the terminal client path and exit.",
    )
    args = parser.parse_args(arguments)
    return run_terminal_client(workspace_root=Path(args.workspace), prompt=args.prompt)


if __name__ == "__main__":
    raise SystemExit(main())
