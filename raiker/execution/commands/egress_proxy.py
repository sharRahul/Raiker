"""Authenticated HTTP/CONNECT proxy and per-run revocation control.

The data plane deliberately resolves the requested hostname itself and opens a
socket to the exact address that was checked.  That closes the usual
check-then-resolve DNS-rebinding hole.  The container entry point reads its
key and grant catalogue from read-only files; neither belongs in argv or the
container environment where a command could inspect it.
"""

from __future__ import annotations

import argparse
import base64
import json
import selectors
import socket
import socketserver
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Protocol

from raiker.execution.commands.egress_policy import EgressPolicy
from raiker.execution.commands.egress_tokens import EgressTokenAuthority


class ClosableSocket(Protocol):
    def close(self) -> None: ...


class HeaderReader(Protocol):
    def readline(self, size: int = -1) -> bytes: ...


@dataclass(frozen=True)
class EgressVerdict:
    run_id: str
    host: str
    port: int
    address_set: tuple[str, ...]
    grant_digest: str
    verdict: str


class EgressProxyController:
    """Atomic state machine used by the sidecar's data and control planes."""

    def __init__(self) -> None:
        self._states: dict[str, str] = {}
        self._policies: dict[str, EgressPolicy] = {}
        self._sockets: dict[str, set[ClosableSocket]] = {}
        self._lock = Lock()

    def activate(self, run_id: str, policy: EgressPolicy) -> None:
        with self._lock:
            if self._states.get(run_id) not in {None, "pending"}:
                raise ValueError("egress_grant_state_invalid")
            self._states[run_id] = "active"
            self._policies[run_id] = policy
            self._sockets[run_id] = set()

    def authorize(
        self, run_id: str, host: str, port: int, addresses: tuple[str, ...]
    ) -> EgressVerdict:
        with self._lock:
            if self._states.get(run_id) != "active":
                raise ValueError("egress_grant_not_active")
            policy = self._policies[run_id]
            selected = policy.permits(host, port, addresses)
            return EgressVerdict(
                run_id, host, port, selected, policy.digest, "allowed"
            )

    def register_socket(self, run_id: str, socket: ClosableSocket) -> None:
        with self._lock:
            if self._states.get(run_id) != "active":
                socket.close()
                raise ValueError("egress_grant_not_active")
            self._sockets[run_id].add(socket)

    def unregister_socket(self, run_id: str, value: ClosableSocket) -> None:
        with self._lock:
            self._sockets.get(run_id, set()).discard(value)

    def revoke(self, run_id: str) -> int:
        with self._lock:
            if self._states.get(run_id) != "active":
                raise ValueError("egress_grant_not_active")
            self._states[run_id] = "revoking"
            sockets = tuple(self._sockets.get(run_id, ()))
        failed = False
        for live_socket in sockets:
            try:
                live_socket.close()
            except OSError:
                failed = True
        with self._lock:
            self._sockets[run_id].clear()
            self._states[run_id] = "cleanup_failed" if failed else "revoked"
        if failed:
            raise ValueError("egress_socket_cleanup_failed")
        return len(sockets)

    def state(self, run_id: str) -> str | None:
        with self._lock:
            return self._states.get(run_id)


@dataclass(frozen=True)
class ProxyIdentity:
    owner_principal_id: str
    profile_id: str


class EgressProxyServer(socketserver.ThreadingTCPServer):
    """Small explicit proxy; it is not a general forwarder or SOCKS server."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        *,
        identity: ProxyIdentity,
        authority: EgressTokenAuthority,
        controller: EgressProxyController,
    ) -> None:
        self.identity = identity
        self.authority = authority
        self.controller = controller
        super().__init__(address, _ProxyHandler)


class _ProxyHandler(socketserver.StreamRequestHandler):
    timeout = 15

    def handle(self) -> None:
        request_line = self.rfile.readline(8193)
        if not request_line or len(request_line) > 8192:
            return
        try:
            method, target, _version = request_line.decode("ascii").strip().split(" ", 2)
            headers = _read_headers(self.rfile)
            asserted_run_id = headers.pop("x-raiker-run-id", "")
            authorization = headers.pop("proxy-authorization")
            run_id, token = _proxy_credential(authorization, asserted_run_id)
            claims = self.server.authority.verify(  # type: ignore[attr-defined]
                token,
                owner_principal_id=self.server.identity.owner_principal_id,  # type: ignore[attr-defined]
                profile_id=self.server.identity.profile_id,  # type: ignore[attr-defined]
                run_id=run_id,
            )
            if method.upper() != "CONNECT":
                raise ValueError("egress_proxy_connect_required")
            host, port = _parse_authority(target)
            addresses = _resolve_public(host, port)
            verdict = self.server.controller.authorize(  # type: ignore[attr-defined]
                run_id, host, port, addresses
            )
            if claims.grant_digest != verdict.grant_digest:
                raise ValueError("egress_token_policy_mismatch")
            upstream = _connect_pinned(verdict.address_set, port)
        except (KeyError, OSError, UnicodeError, ValueError):
            self.wfile.write(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
            return
        controller: EgressProxyController = self.server.controller  # type: ignore[attr-defined]
        controller.register_socket(run_id, upstream)
        try:
            self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self.wfile.flush()
            _tunnel(self.connection, upstream)
        finally:
            controller.unregister_socket(run_id, upstream)
            upstream.close()


def _read_headers(reader: HeaderReader) -> dict[str, str]:
    headers: dict[str, str] = {}
    for _ in range(64):
        line = reader.readline(8193)
        if len(line) > 8192:
            raise ValueError("egress_header_too_large")
        if line in {b"\r\n", b"\n"}:
            return headers
        name, separator, value = line.decode("latin-1").partition(":")
        if not separator or not name:
            raise ValueError("egress_header_invalid")
        key = name.strip().lower()
        if key in headers:
            raise ValueError("egress_header_duplicate")
        headers[key] = value.strip()
    raise ValueError("egress_headers_too_many")


def _parse_authority(value: str) -> tuple[str, int]:
    if value.startswith("["):
        close = value.find("]")
        if close < 0 or value[close + 1 : close + 2] != ":":
            raise ValueError("egress_authority_invalid")
        host, raw_port = value[1:close], value[close + 2 :]
    else:
        host, separator, raw_port = value.rpartition(":")
        if not separator:
            raise ValueError("egress_authority_invalid")
    port = int(raw_port)
    if not host or not 1 <= port <= 65535:
        raise ValueError("egress_authority_invalid")
    return host, port


def _proxy_credential(value: str, asserted_run_id: str) -> tuple[str, str]:
    if value.startswith("Bearer "):
        if not asserted_run_id:
            raise ValueError("egress_run_id_required")
        return asserted_run_id, value[7:]
    if value.startswith("Basic "):
        try:
            decoded = base64.b64decode(value[6:], validate=True).decode("utf-8")
            username, separator, password = decoded.partition(":")
        except (ValueError, UnicodeError) as exc:
            raise ValueError("egress_token_invalid") from exc
        if not separator or (asserted_run_id and username != asserted_run_id):
            raise ValueError("egress_token_scope_mismatch")
        return username, password
    raise ValueError("egress_token_invalid")


def _resolve_public(host: str, port: int) -> tuple[str, ...]:
    values: set[str] = {
        str(item[4][0])
        for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    }
    return tuple(sorted(values))


def _connect_pinned(addresses: tuple[str, ...], port: int) -> socket.socket:
    last_error: OSError | None = None
    for address in addresses:
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        candidate = socket.socket(family, socket.SOCK_STREAM)
        candidate.settimeout(15)
        try:
            candidate.connect((address, port))
            candidate.settimeout(None)
            return candidate
        except OSError as exc:
            candidate.close()
            last_error = exc
    raise last_error or OSError("egress_connect_failed")


def _tunnel(client: socket.socket, upstream: socket.socket) -> None:
    selector = selectors.DefaultSelector()
    selector.register(client, selectors.EVENT_READ, upstream)
    selector.register(upstream, selectors.EVENT_READ, client)
    try:
        while True:
            events = selector.select(timeout=30)
            if not events:
                return
            for key, _ in events:
                source, destination = key.fileobj, key.data
                if not isinstance(source, socket.socket) or not isinstance(
                    destination, socket.socket
                ):
                    raise TypeError("egress_proxy_selector_state_invalid")
                data = source.recv(65536)
                if not data:
                    return
                destination.sendall(data)
    finally:
        selector.close()


def load_proxy_server(config_path: Path) -> EgressProxyServer:
    """Load only non-secret policy plus an instance key from a protected file."""
    value = json.loads(config_path.read_text(encoding="utf-8"))
    key = base64.b64decode(value["hmac_key"], validate=True)
    controller = EgressProxyController()
    for grant in value.get("grants", []):
        controller.activate(
            str(grant["run_id"]),
            EgressPolicy(tuple(grant["domains"]), tuple(grant["ports"])),
        )
    return EgressProxyServer(
        (str(value.get("listen_host", "0.0.0.0")), int(value.get("listen_port", 8080))),
        identity=ProxyIdentity(str(value["owner_principal_id"]), str(value["profile_id"])),
        authority=EgressTokenAuthority(key),
        controller=controller,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("/run/raiker/egress.json"))
    args = parser.parse_args()
    with load_proxy_server(args.config) as server:
        server.serve_forever(poll_interval=0.2)


if __name__ == "__main__":
    main()
