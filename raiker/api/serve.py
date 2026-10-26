from __future__ import annotations

import argparse
import os
import threading
import webbrowser
from pathlib import Path

import uvicorn

from raiker.api.app import create_app

# raiker/api/serve.py -> repo root is two parents up; the built SPA lives at web/dist.
_DEFAULT_UI_DIR = Path(__file__).resolve().parents[2] / "web" / "dist"


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
        help="Built web dashboard directory (default: web/dist; env RAIKER_WEB_UI_DIR).",
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
    # BUG-347 — a proxy named in RAIKER_TRUSTED_PROXY serves the internet
    # through a loopback bind, so it takes the same hardened token a public
    # bind does; an entry that is not an address refuses rather than trusting
    # nothing (or everything) by accident.
    from raiker.api.proxy_guard import TRUSTED_PROXY_ENV, ProxyConfigError, trusted_proxies

    try:
        proxies = trusted_proxies()
    except ProxyConfigError as exc:
        print(f"[raiker-web] {exc}. Refusing to start.")
        return 2
    if proxies and not public and not os.environ.get("RAIKER_OWNER_TOKEN", "").strip():
        print(
            f"[raiker-web] {TRUSTED_PROXY_ENV} lets requests from the internet reach this host through a proxy; "
            "it requires a hardened owner token in RAIKER_OWNER_TOKEN. Refusing to start.",
        )
        return 2
    if proxies and not public:
        print(
            f"[raiker-web] Trusting the reverse proxy at {', '.join(str(p) for p in proxies)}. Requests it "
            "forwards are treated as remote: rate limited, no recovery, HSTS over HTTPS.",
        )
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
            "Build it first: npm --prefix web run build",
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

    # BUG-342 — record which process serves this workspace, as `raiker-app`
    # does, so a launch for the same workspace joins this host and a launch for
    # another one does not mistake it for its own.
    from raiker.app.host import HostControl

    control = HostControl(Path(args.workspace))
    control.record_start(pid=os.getpid(), port=args.port)
    try:
        # BUG-347 — uvicorn's own proxy-header handling would rewrite the socket
        # peer from X-Forwarded-For whenever the peer is 127.0.0.1, so a header
        # would decide who the client is. Raiker reads the real peer and decides
        # what a forwarded request is itself (raiker/api/proxy_guard.py).
        uvicorn.run(app, host=args.host, port=args.port, proxy_headers=False, forwarded_allow_ips="")
    finally:
        control.clear()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
