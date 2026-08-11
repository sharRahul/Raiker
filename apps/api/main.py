from __future__ import annotations

import argparse
import os
import threading
import webbrowser
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


def _is_loopback(host: str) -> bool:
    return host in {"127.0.0.1", "::1", "localhost"}


def main(argv: list[str] | None = None) -> int:
    """Run the single-user Raiker API + web dashboard.

    Raiker is a single-user agent: every request authenticates as the one owner principal
    (POST /api/auth/session issues the owner's bearer token; all governed reads/mutations go
    through the same contracts as the CLI). It binds to 127.0.0.1 by default. Binding beyond
    loopback (so the owner can reach Raiker from any machine/UI over the internet) is allowed
    only with the explicit ``--allow-public`` opt-in, which also requires a hardened owner token
    via ``RAIKER_OWNER_TOKEN`` and turns on transport guardrails (security headers, rate limit,
    body-size limit, and HSTS). Put a TLS-terminating reverse proxy in front for real exposure.
    """
    parser = argparse.ArgumentParser(
        prog="raiker-web",
        description="Run the single-user Raiker API + web dashboard (loopback by default).",
    )
    parser.add_argument("--workspace", default=".", help="Workspace root for local runtime state.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (loopback by default).")
    parser.add_argument("--port", type=int, default=8765, help="Bind port.")
    parser.add_argument(
        "--allow-public",
        action="store_true",
        help="Permit binding to a non-loopback host for single-user internet access (requires RAIKER_OWNER_TOKEN).",
    )
    parser.add_argument(
        "--rate-limit-per-minute", type=int, default=120, help="Per-IP request budget for /api.",
    )
    parser.add_argument(
        "--ui-dir",
        default=None,
        help="Built web dashboard directory (default: apps/web/dist; env RAIKER_WEB_UI_DIR).",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not auto-open the dashboard in the default browser (loopback only).",
    )
    args = parser.parse_args(argv)

    public = not _is_loopback(args.host)
    if public and not args.allow_public:
        print(
            f"[raiker-web] Refusing to bind to non-loopback host {args.host!r} without --allow-public. "
            "Raiker stays single-user; pass --allow-public to expose it to your other devices.",
        )
        return 2
    if public and not os.environ.get("RAIKER_OWNER_TOKEN", "").strip():
        print(
            "[raiker-web] --allow-public requires a hardened owner token in RAIKER_OWNER_TOKEN "
            "(used to bind the owner session); refusing to expose an unhardened instance.",
        )
        return 2
    if public:
        print(
            f"[raiker-web] Exposing single-user Raiker on {args.host}:{args.port}. "
            "Front this with TLS (reverse proxy). Every request authenticates as the owner.",
        )

    resolved = _resolve_ui_dir(args.ui_dir)
    ui_dir: Path | None = resolved
    if not (resolved.is_dir() and (resolved / "index.html").is_file()):
        print(
            f"[raiker-web] No built web UI at {resolved}; serving API only. "
            "Build it first: npm --prefix apps/web run build",
        )
        ui_dir = None

    app = create_app(
        Path(args.workspace),
        ui_dir=ui_dir,
        rate_limit_per_minute=args.rate_limit_per_minute,
        hsts=public,
        loopback_only=not public,
    )

    # Auto-open the dashboard in the user's default browser for local loopback
    # use. Skipped for --allow-public (the operator is on another machine) and
    # when --no-browser is set (scripted/remote use, or the dev server proxies
    # /api separately and the owner prefers to drive the URL themselves).
    if not public and not args.no_browser and ui_dir is not None:
        url = f"http://{args.host}:{args.port}/"
        threading.Timer(1.2, lambda: webbrowser.open(url, new=1)).start()

    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
