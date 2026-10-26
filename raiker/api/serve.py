from __future__ import annotations

import argparse
import os
import threading
import webbrowser
from pathlib import Path

from raiker.api.app import create_app
from raiker.api.proxy_guard import RETIRED_TRUSTED_PROXY_ENV

# raiker/api/serve.py -> repo root is two parents up; the built SPA lives at web/dist.
_DEFAULT_UI_DIR = Path(__file__).resolve().parents[2] / "web" / "dist"

#: BUG-358 — the shared secret earlier builds required for remote access. Its
#: value was never read; two-step sign-in replaced it. A stale one is harmless,
#: so it is mentioned once rather than refused.
RETIRED_REMOTE_ENV = "RAIKER_OWNER_TOKEN"


def _resolve_ui_dir(cli_value: str | None) -> Path:
    if cli_value:
        return Path(cli_value)
    env_value = os.environ.get("RAIKER_WEB_UI_DIR")
    return Path(env_value) if env_value else _DEFAULT_UI_DIR


def _is_loopback(host: str) -> bool:
    return host in {"127.0.0.1", "::1", "localhost"}


def main(argv: list[str] | None = None) -> int:
    """Run the single-user Raiker API + web dashboard.

    Raiker's own listener is on this computer only (``127.0.0.1`` by default).
    Other devices reach it through one remote listener (BUG-347, BUG-358): a
    private-network address where Raiker serves HTTPS itself, or a listener for
    a reverse proxy on this computer. It is chosen in Settings → Security →
    Remote access, or here with start options, and it opens only while every
    account has two-step sign-in. Every request on it is remote: it needs a
    session made with the password and a code from another device, and it never
    reaches recovery, host restart or the instance list.
    """
    parser = argparse.ArgumentParser(
        prog="raiker-web",
        description="Run the single-user Raiker API + web dashboard (this computer only by default).",
    )
    parser.add_argument("--workspace", default=".", help="Workspace root for local runtime state.")
    parser.add_argument("--host", default="127.0.0.1", help="The local listener's address (loopback only).")
    parser.add_argument("--port", type=int, default=8765, help="The local listener's port.")
    parser.add_argument(
        "--allow-public",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    remote = parser.add_argument_group(
        "remote access",
        "Open a remote listener for this start only, instead of the one in Settings → Security → Remote access. "
        "It needs two-step sign-in on every account.",
    )
    remote.add_argument("--proxy-port", type=int, default=None,
                        help="A listener on 127.0.0.1:<port> for a reverse proxy that terminates HTTPS.")
    remote.add_argument("--proxy-socket", default=None,
                        help="A Unix socket for a reverse proxy that terminates HTTPS (not on Windows).")
    remote.add_argument("--private-host", default=None,
                        help="This computer's private or VPN address, served over HTTPS by Raiker itself.")
    remote.add_argument("--private-port", type=int, default=None, help="The private listener's port (default 8443).")
    remote.add_argument("--tls-cert", default=None, help="Certificate (PEM) for --private-host.")
    remote.add_argument("--tls-key", default=None, help="Private key (PEM) for --private-host.")
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
        help="Do not auto-open the dashboard in the default browser.",
    )
    args = parser.parse_args(argv)

    if args.allow_public or not _is_loopback(args.host):
        print(
            "[raiker-web] Raiker's own listener stays on this computer, so --host must be a loopback address "
            "and --allow-public is retired. To reach Raiker from other devices, choose Settings → Security → "
            "Remote access, or start with --private-host and --tls-cert/--tls-key (a private or VPN address, "
            "served over HTTPS), or --proxy-port/--proxy-socket (behind a reverse proxy). Refusing to start.",
        )
        return 2
    # BUG-347 — the first fix trusted a proxy by the headers it sent, which a
    # proxy that sends none defeats. That setting is refused rather than read
    # or ignored, so a host configured for it cannot change meaning silently.
    if os.environ.get(RETIRED_TRUSTED_PROXY_ENV, "").strip():
        print(
            f"[raiker-web] {RETIRED_TRUSTED_PROXY_ENV} is no longer read. Point the reverse proxy at a proxy "
            "listener instead (--proxy-port or --proxy-socket) and unset it. Refusing to start.",
        )
        return 2
    if os.environ.get(RETIRED_REMOTE_ENV, "").strip():
        print(
            f"[raiker-web] {RETIRED_REMOTE_ENV} is no longer used and can be removed: remote access is "
            "protected by your password and two-step sign-in.",
        )

    from raiker.app.remote_access import RemoteAccessError, config_from_start_options

    try:
        override = config_from_start_options(
            proxy_port=args.proxy_port,
            proxy_socket=args.proxy_socket,
            private_host=args.private_host,
            private_port=args.private_port,
            tls_cert=args.tls_cert,
            tls_key=args.tls_key,
        )
    except RemoteAccessError as error:
        print(f"[raiker-web] {error.message} Refusing to start.")
        return 2

    resolved = _resolve_ui_dir(args.ui_dir)
    ui_dir: Path | None = resolved
    if not (resolved.is_dir() and (resolved / "index.html").is_file()):
        print(
            f"[raiker-web] No built web UI at {resolved}; serving API only. "
            "Build it first: npm --prefix web run build",
        )
        ui_dir = None

    from raiker.app.host_start import HostStartError, start_host

    def open_dashboard() -> None:
        # Auto-open the dashboard in the user's default browser, unless asked
        # not to (scripted use, or the dev server proxies /api itself).
        if not args.no_browser and ui_dir is not None:
            url = f"http://{args.host}:{args.port}/"
            threading.Timer(1.2, lambda: webbrowser.open(url, new=1)).start()

    try:
        return start_host(
            Path(args.workspace),
            host=args.host,
            port=args.port,
            override=override,
            make_app=lambda listener, source: create_app(
                Path(args.workspace),
                ui_dir=ui_dir,
                rate_limit_per_minute=args.rate_limit_per_minute,
                loopback_only=True,
                proxy_listener=listener,
                remote_source=source,
            ),
            log_prefix="[raiker-web]",
            before_serve=open_dashboard,
            strict_override=True,
        )
    except HostStartError as error:
        print(f"[raiker-web] {error} Refusing to start.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
