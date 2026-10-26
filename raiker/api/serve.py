from __future__ import annotations

import argparse
import os
import socket
import stat
import threading
import webbrowser
from pathlib import Path

import uvicorn

from raiker.api.app import create_app
from raiker.api.proxy_guard import RETIRED_TRUSTED_PROXY_ENV, ProxyListener

# raiker/api/serve.py -> repo root is two parents up; the built SPA lives at web/dist.
_DEFAULT_UI_DIR = Path(__file__).resolve().parents[2] / "web" / "dist"


def _resolve_ui_dir(cli_value: str | None) -> Path:
    if cli_value:
        return Path(cli_value)
    env_value = os.environ.get("RAIKER_WEB_UI_DIR")
    return Path(env_value) if env_value else _DEFAULT_UI_DIR


def _is_loopback(host: str) -> bool:
    return host in {"127.0.0.1", "::1", "localhost"}


def _proxy_listener_problem(args: argparse.Namespace, *, public: bool) -> str | None:
    """Why the proxy listener options cannot start, or None."""
    if args.proxy_port is not None and args.proxy_socket:
        return "Choose one proxy listener: --proxy-port or --proxy-socket, not both."
    if public:
        return (
            "--proxy-port and --proxy-socket are for a host bound to this computer; a host started with "
            "--allow-public already treats every request as remote."
        )
    if args.proxy_socket and not hasattr(socket, "AF_UNIX"):
        return "--proxy-socket needs Unix domain sockets, which this platform does not offer; use --proxy-port."
    if args.proxy_port is not None and not (0 < args.proxy_port < 65536):
        return f"--proxy-port must be a port number, not {args.proxy_port}."
    if args.proxy_port is not None and args.proxy_port == args.port:
        return "--proxy-port must differ from --port: one listener is for this computer, the other for the proxy."
    if not os.environ.get("RAIKER_OWNER_TOKEN", "").strip():
        return (
            "A proxy listener lets requests from the internet reach this host; it requires a hardened owner "
            "token in RAIKER_OWNER_TOKEN."
        )
    return None


def _bind_proxy_listener(listener: ProxyListener) -> socket.socket:
    """Open the proxy listener: 127.0.0.1:<port>, or a Unix socket only its owner and group may use."""
    if listener.socket_path is None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", int(listener.port or 0)))
    else:
        path = Path(listener.socket_path)
        if path.exists() or path.is_symlink():
            # Replace only a stale socket: never a file somebody put there,
            # and never a socket another host is still serving.
            if not stat.S_ISSOCK(path.lstat().st_mode):
                raise OSError(f"{path} exists and is not a socket")
            probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)  # type: ignore[attr-defined,unused-ignore]
            try:
                probe.connect(str(path))
            except OSError:
                path.unlink()
            else:
                raise OSError(f"{path} is in use by another process")
            finally:
                probe.close()
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)  # type: ignore[attr-defined,unused-ignore]
        # Created owner-and-group only from the start, not opened up and then narrowed.
        previous = os.umask(0o117)
        try:
            sock.bind(str(path))
        finally:
            os.umask(previous)
        os.chmod(path, 0o660)
    sock.set_inheritable(True)
    return sock


def main(argv: list[str] | None = None) -> int:
    """Run the single-user Raiker API + web dashboard.

    Raiker is a single-user agent: every request authenticates as the one owner principal
    (POST /api/auth/session issues the owner's bearer token; all governed reads/mutations go
    through the same contracts as the CLI). It binds to 127.0.0.1 by default. Binding beyond
    loopback (so the owner can reach Raiker from any machine/UI over the internet) is allowed
    only with the explicit ``--allow-public`` opt-in, which also requires ``RAIKER_OWNER_TOKEN``
    to be set and turns on transport guardrails (security headers, rate limit, body-size limit,
    and HSTS). A reverse proxy on the same machine gets its own listener (``--proxy-socket`` or
    ``--proxy-port``) where every request is remote (BUG-347). The token's value is not yet read
    by anything (BUG-358); the owner password and MFA are what authenticate a remote browser.
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
        "--proxy-port",
        type=int,
        default=None,
        help="Also listen on 127.0.0.1:<port> for a reverse proxy; every request there is remote "
        "(requires RAIKER_OWNER_TOKEN).",
    )
    parser.add_argument(
        "--proxy-socket",
        default=None,
        help="Also listen on this Unix socket for a reverse proxy; every request there is remote "
        "(requires RAIKER_OWNER_TOKEN).",
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
            "[raiker-web] --allow-public requires RAIKER_OWNER_TOKEN to be set; "
            "refusing to expose an unhardened instance.",
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
    listener: ProxyListener | None = None
    if args.proxy_port is not None or args.proxy_socket:
        problem = _proxy_listener_problem(args, public=public)
        if problem is not None:
            print(f"[raiker-web] {problem} Refusing to start.")
            return 2
        listener = ProxyListener(
            port=args.proxy_port,
            socket_path=str(Path(args.proxy_socket).resolve()) if args.proxy_socket else None,
        )
        print(
            f"[raiker-web] Proxy listener on {listener.describe()}. Every request there is remote: signed in, "
            f"rate limited, no recovery, HSTS over HTTPS. Point the reverse proxy there, never at port {args.port}.",
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
        proxy_listener=listener,
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
        if listener is None:
            uvicorn.run(app, host=args.host, port=args.port, proxy_headers=False, forwarded_allow_ips="")
        else:
            serve_with_proxy_listener(app, host=args.host, port=args.port, listener=listener)
    finally:
        control.clear()
    return 0


def serve_with_proxy_listener(app: object, *, host: str, port: int, listener: ProxyListener) -> None:
    """One server, two listeners: the app tells them apart by the socket a
    connection was accepted on (``scope["server"]``), which no request sets."""
    config = uvicorn.Config(app, host=host, port=port, proxy_headers=False, forwarded_allow_ips="")  # type: ignore[arg-type]
    local = config.bind_socket()
    proxy = _bind_proxy_listener(listener)
    try:
        uvicorn.Server(config).run(sockets=[local, proxy])
    finally:
        proxy.close()
        if listener.socket_path:
            Path(listener.socket_path).unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
