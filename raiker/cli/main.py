from __future__ import annotations

import argparse
from pathlib import Path

from raiker.tui.app import run_terminal_client


def main(argv: list[str] | None = None) -> int:
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
