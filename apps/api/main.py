from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from raiker.api.app import create_app


def main(argv: list[str] | None = None) -> int:
    """Run the local Raiker API server (and, once built, the web UI) on loopback only.

    Local-first and single-user: the server binds to 127.0.0.1 by default and must not be exposed
    on a public interface. The web UI obtains a token from POST /api/auth/session for the local
    owner principal; all governed reads/mutations go through the same contracts as the CLI.
    """
    parser = argparse.ArgumentParser(
        prog="raiker-web",
        description="Run the local Raiker API/web server (127.0.0.1 only).",
    )
    parser.add_argument("--workspace", default=".", help="Workspace root for local runtime state.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (loopback by default).")
    parser.add_argument("--port", type=int, default=8765, help="Bind port.")
    args = parser.parse_args(argv)

    app = create_app(Path(args.workspace))
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
