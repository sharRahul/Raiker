from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from raiker.api.app import create_app

# apps/api/main.py -> repo root is two parents up; the built SPA lives at apps/web/dist.
_DEFAULT_UI_DIR = Path(__file__).resolve().parents[2] / "apps" / "web" / "dist"


def _resolve_ui_dir(cli_value: str | None) -> Path:
    if cli_value:
        return Path(cli_value)
    env_value = os.environ.get("RAIKER_WEB_UI_DIR")
    return Path(env_value) if env_value else _DEFAULT_UI_DIR


def main(argv: list[str] | None = None) -> int:
    """Run the local Raiker API + web dashboard on loopback only.

    Local-first and single-user: the server binds to 127.0.0.1 by default and must not be exposed
    on a public interface. When the built SPA (``apps/web/dist``) is present it is served from this
    same origin, so the dashboard launches with one command and the UI's relative ``/api`` paths
    resolve directly. The UI obtains a token from POST /api/auth/session for the local owner
    principal; all governed reads/mutations go through the same contracts as the CLI.
    """
    parser = argparse.ArgumentParser(
        prog="raiker-web",
        description="Run the local Raiker API + web dashboard (127.0.0.1 only).",
    )
    parser.add_argument("--workspace", default=".", help="Workspace root for local runtime state.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (loopback by default).")
    parser.add_argument("--port", type=int, default=8765, help="Bind port.")
    parser.add_argument(
        "--ui-dir",
        default=None,
        help="Built web dashboard directory (default: apps/web/dist; env RAIKER_WEB_UI_DIR).",
    )
    args = parser.parse_args(argv)

    resolved = _resolve_ui_dir(args.ui_dir)
    ui_dir: Path | None = resolved
    if not (resolved.is_dir() and (resolved / "index.html").is_file()):
        print(
            f"[raiker-web] No built web UI at {resolved}; serving API only. "
            "Build it first: npm --prefix apps/web run build",
        )
        ui_dir = None

    app = create_app(Path(args.workspace), ui_dir=ui_dir)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
