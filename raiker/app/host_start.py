"""Starting the host, the same way from ``raiker-web`` and ``raiker-app``.

One sequence for both entry points (BUG-358), so the desktop app, a service
and a server started by hand open the same listeners and report them the same
way:

1. bind the local listener on this computer;
2. decide and open the remote listener (``raiker.app.remote_access.prepare``):
   the saved setting, or start options; never opened without two-step sign-in
   on every account; a setting that cannot open falls back and says why;
3. build the app with that listener, and keep what this start did on it, so
   Settings and Diagnostics report the listener that is really open;
4. serve until stopped, and return the exit status Restart asked for.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from raiker.api import server_runner
from raiker.api.proxy_guard import RemoteListener
from raiker.app.remote_access import RemoteAccessConfig, prepare


class HostStartError(RuntimeError):
    pass


def start_host(
    workspace: Path,
    *,
    host: str,
    port: int,
    make_app: Callable[[RemoteListener | None, str], Any],
    override: RemoteAccessConfig | None = None,
    log_prefix: str = "[raiker]",
    before_serve: Callable[[], None] | None = None,
    strict_override: bool = False,
) -> int:
    try:
        local = server_runner.bind_local(host, port)
    except OSError as error:
        raise HostStartError(f"Could not open {host}:{port}: {error.strerror or error}.") from error
    store: Any
    try:
        from raiker.storage.sqlite import SQLiteStore

        store = SQLiteStore(workspace)
    except Exception:  # noqa: BLE001 - a store that will not open starts this device only
        store = None
    plan = prepare(store, local_port=port, override=override)
    if strict_override and override is not None and plan.outcome == "failed":
        local.close()
        raise HostStartError(plan.message or "The remote listener did not start.")
    app = make_app(plan.listener, plan.source)
    app.state.remote_access.startup = plan.summary()
    app.state.local_port = port
    if plan.outcome == "started" and plan.listener is not None:
        print(
            f"{log_prefix} Remote access on {plan.listener.describe()}. Every request there is from another "
            f"device: password and two-step sign-in, HTTPS only. Never point a proxy at port {port}.",
        )
    elif plan.message:
        print(f"{log_prefix} {plan.message}")

    from raiker.app.host import HostControl

    control = HostControl(workspace)
    control.record_start(pid=os.getpid(), port=port)
    if before_serve is not None:
        before_serve()
    try:
        server_runner.serve(app, local, plan.remote)
    finally:
        control.clear()
        local.close()
        if plan.remote is not None:
            plan.remote.sock.close()
            socket_path = plan.config.proxy_socket if plan.config.proxy_kind == "socket" else None
            if plan.config.mode == "proxy" and socket_path:
                Path(socket_path).unlink(missing_ok=True)
    # Set by the Host control's Restart action: a status the platform's service
    # manager is configured to restart on, rather than a clean exit it would
    # (correctly) leave stopped.
    exit_code = getattr(app.state, "exit_code", 0)
    return int(exit_code) if isinstance(exit_code, int) else 0
