"""Running the host: the local listener, and the remote one when there is one.

One process serves both listeners. They differ in a way uvicorn configures per
server, not per socket: the private-network listener speaks HTTPS with the
owner's certificate and the local listener speaks plain HTTP on loopback. So
there are two uvicorn servers on one event loop. The main one owns the
application's lifespan and the process signals; the companion has neither and
stops when the main one does.

Two faults of the plain ``uvicorn.run`` are fixed here, because Restart depends
on them (found while building BUG-358's apply-and-restart):

* **uvicorn re-raises the signal that stopped it.** After a graceful shutdown it
  restores the previous handler and raises SIGTERM again, so the process died
  by signal (status 143) instead of returning. The launcher never reached the
  line that returns Restart's exit status 75, the status systemd and launchd
  are configured to restart on, and systemd's ``Restart=on-failure`` reads a
  SIGTERM death as a clean stop. Raiker stopped and stayed stopped. The
  servers here restore the handlers and return.
* **Restart signalled its own process.** On Windows ``os.kill(pid, SIGTERM)`` is
  ``TerminateProcess``: no graceful shutdown at all. ``request_stop`` on
  ``app.state`` sets the server's own exit flag instead, which works the same
  on every platform.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
import threading
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import uvicorn
from uvicorn.server import HANDLED_SIGNALS


class _MainServer(uvicorn.Server):
    """uvicorn's server, without re-raising the signal that stopped it."""

    @contextmanager
    def capture_signals(self) -> Generator[None, None, None]:
        if threading.current_thread() is not threading.main_thread():
            yield
            return
        original = {sig: signal.signal(sig, self.handle_exit) for sig in HANDLED_SIGNALS}
        try:
            yield
        finally:
            for sig, handler in original.items():
                signal.signal(sig, handler)


class _CompanionServer(uvicorn.Server):
    """The remote listener's server: no signals of its own, no lifespan."""

    @contextmanager
    def capture_signals(self) -> Generator[None, None, None]:
        yield


@dataclass(frozen=True)
class RemoteSocket:
    """An opened remote listener, with the certificate it serves when it is HTTPS."""

    sock: socket.socket
    tls_cert: str | None = None
    tls_key: str | None = None


_log = logging.getLogger(__name__)

#: How often the remote listener looks at its certificate files (BUG-359).
CERTIFICATE_POLL_SECONDS = 30.0


class CertificateReloader:
    """Serve a renewed certificate without a restart (BUG-359, limit 3).

    uvicorn builds one ``SSLContext`` at start and every new handshake reads
    it, so loading the renewed chain into that same context is enough: open
    connections keep the certificate they negotiated, the next one gets the
    new one. A pair that does not load together (a half-written renewal, a key
    that does not match) leaves the old certificate in place and is tried
    again on the next change.
    """

    def __init__(self, context: Any, cert: str, key: str) -> None:
        self._context = context
        self._cert = cert
        self._key = key
        self._seen = self._stamp()
        self.reloads = 0
        self.last_error: str | None = None

    def _stamp(self) -> tuple[float, int, float, int] | None:
        try:
            cert, key = os.stat(self._cert), os.stat(self._key)
        except OSError:
            return None
        return (cert.st_mtime, cert.st_size, key.st_mtime, key.st_size)

    def check(self) -> bool:
        """Reload when either file changed; ``True`` when a new chain was loaded."""
        stamp = self._stamp()
        if stamp is None or stamp == self._seen:
            return False
        try:
            self._context.load_cert_chain(self._cert, self._key)
        except (OSError, ValueError, Exception) as error:  # noqa: BLE001 - keep serving the old one
            self.last_error = error.__class__.__name__
            _log.warning("Remote listener kept its certificate: the renewed pair did not load (%s)", self.last_error)
            self._seen = stamp
            return False
        self._seen = stamp
        self.reloads += 1
        self.last_error = None
        _log.info("Remote listener loaded its renewed certificate")
        return True

    async def watch(self, stop: Any, interval: float = CERTIFICATE_POLL_SECONDS) -> None:
        while not stop():
            await asyncio.sleep(interval)
            self.check()


def _config(app: Any, **options: Any) -> uvicorn.Config:
    # BUG-347 — uvicorn's own proxy-header handling would rewrite the socket
    # peer from X-Forwarded-For whenever the peer is 127.0.0.1, so a header
    # would decide who the client is. Raiker reads the real peer and decides
    # what a forwarded request is itself (raiker/api/proxy_guard.py).
    return uvicorn.Config(app, proxy_headers=False, forwarded_allow_ips="", **options)


def companion_config(app: Any, remote: RemoteSocket) -> uvicorn.Config:
    """The remote listener's configuration, loaded now so a bad certificate fails here."""
    options: dict[str, Any] = {"lifespan": "off"}
    if remote.tls_cert and remote.tls_key:
        options.update(ssl_certfile=remote.tls_cert, ssl_keyfile=remote.tls_key)
    config = _config(app, **options)
    config.load()
    return config


def serve(app: Any, local: socket.socket, remote: RemoteSocket | None = None) -> None:
    """Serve until stopped, by a signal or by ``app.state.request_stop()``."""
    main = _MainServer(_config(app))
    companion = _CompanionServer(companion_config(app, remote)) if remote is not None else None

    def request_stop() -> None:
        main.should_exit = True

    app.state.request_stop = request_stop

    reloader = (
        CertificateReloader(companion.config.ssl, remote.tls_cert, remote.tls_key)
        if companion is not None
        and remote is not None
        and remote.tls_cert
        and remote.tls_key
        and companion.config.ssl is not None
        else None
    )

    async def run() -> None:
        task = (
            asyncio.create_task(companion.serve(sockets=[remote.sock]))
            if companion is not None and remote is not None
            else None
        )
        watcher = (
            asyncio.create_task(reloader.watch(lambda: main.should_exit))
            if reloader is not None
            else None
        )
        try:
            await main.serve(sockets=[local])
        finally:
            if watcher is not None:
                watcher.cancel()
            if companion is not None and task is not None:
                companion.should_exit = True
                await task

    asyncio.run(run())


def bind_local(host: str, port: int) -> socket.socket:
    """The local listener's socket, bound the way uvicorn would bind it."""
    return _config(None, host=host, port=port).bind_socket()
