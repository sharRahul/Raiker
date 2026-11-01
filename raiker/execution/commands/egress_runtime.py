"""Allow-listed downloads for sandboxed commands: one proxy per run.

The native boundary denies all network by default. When the owner turns on
command downloads, each run gets its own authenticated proxy beside Raiker
(:mod:`raiker.execution.commands.egress_proxy`) and the boundary makes that
proxy the command's only route:

* **Linux** — the sandbox keeps its private network namespace; the runner
  bridges the namespace's loopback port to this proxy's Unix socket.
* **macOS** — Seatbelt allows outbound connections to the proxy's loopback
  port only.
* **Windows** — the restricted account's firewall rule blocks every outbound
  destination off the machine; the proxy is on loopback.

The proxy resolves each name itself, refuses any answer containing a
non-public address (DNS rebinding), connects to the exact address it checked,
and accepts only ``CONNECT`` to an allow-listed host and port, so a redirect
to another host is a new, separately checked tunnel. Tools find it through the
standard ``HTTPS_PROXY`` variables with a run-scoped credential; pip, npm,
cargo and Git all honour them. The credential dies with the run.
"""

from __future__ import annotations

import contextlib
import json
import os
import secrets
import socketserver
import sys
import tempfile
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from raiker.execution.commands.egress_policy import EgressPolicy, normalize_domain
from raiker.execution.commands.egress_proxy import (
    EgressProxyController,
    EgressProxyServer,
    ProxyIdentity,
    _ProxyHandler,
)
from raiker.execution.commands.egress_tokens import EgressTokenAuthority, EgressTokenClaims
from raiker.storage.internal_paths import internal_io_path

#: Package registries and source hosts the four supported toolchains fetch from.
DEFAULT_DOWNLOAD_DOMAINS: tuple[str, ...] = (
    "pypi.org",
    "files.pythonhosted.org",
    "registry.npmjs.org",
    "crates.io",
    "index.crates.io",
    "static.crates.io",
    "github.com",
    "codeload.github.com",
    "objects.githubusercontent.com",
)
PROXY_VARIABLES: tuple[str, ...] = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)
#: The loopback port the Linux bridge listens on inside the private namespace.
LINUX_BRIDGE_PORT = 3128
PROFILE_ID = "native_sandbox"


@dataclass(frozen=True)
class CommandEgressSettings:
    """The owner's switch and allow-list. Off until the owner turns it on."""

    enabled: bool = False
    domains: tuple[str, ...] = DEFAULT_DOWNLOAD_DOMAINS

    def policy(self) -> EgressPolicy:
        return EgressPolicy(self.domains, (443,))


def _settings_path(workspace_root: str | Path) -> Path:
    return internal_io_path(Path(workspace_root) / ".raiker" / "command-egress.json")


def load_settings(workspace_root: str | Path) -> CommandEgressSettings:
    try:
        value = json.loads(_settings_path(workspace_root).read_text(encoding="utf-8"))
        domains = tuple(normalize_domain(str(item)) for item in value.get("domains", []))
        return CommandEgressSettings(bool(value.get("enabled")), domains)
    except (OSError, ValueError, TypeError, AttributeError):
        return CommandEgressSettings()


def save_settings(workspace_root: str | Path, enabled: bool, domains: Iterable[str]) -> CommandEgressSettings:
    """Validate and store the owner's choice. An empty list cannot be enabled."""
    normalized = tuple(sorted({normalize_domain(item) for item in domains}))
    if enabled and not normalized:
        raise ValueError("egress_policy_invalid")
    if len(normalized) > 200:
        raise ValueError("egress_domain_limit_exceeded")
    path = _settings_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_suffix(".tmp")
    staged.write_text(json.dumps({"enabled": enabled, "domains": list(normalized)}), encoding="utf-8")
    os.replace(staged, path)
    return CommandEgressSettings(enabled, normalized)


class _RecordingController(EgressProxyController):
    """The proxy's state machine, also noting which destinations it refused."""

    def __init__(self) -> None:
        super().__init__()
        self.denied: list[str] = []

    def check_name(self, run_id: str, host: str, port: int) -> None:
        try:
            super().check_name(run_id, host, port)
        except ValueError:
            self._note(host, port)
            raise

    def authorize(self, run_id: str, host: str, port: int, addresses: tuple[str, ...]) -> Any:
        try:
            return super().authorize(run_id, host, port, addresses)
        except ValueError:
            self._note(host, port)
            raise

    def _note(self, host: str, port: int) -> None:
        label = f"{host}:{port}"
        if label not in self.denied and len(self.denied) < 20:
            self.denied.append(label)


def _unix_proxy_server(
    path: str,
    *,
    identity: ProxyIdentity,
    authority: EgressTokenAuthority,
    controller: EgressProxyController,
) -> Any:
    """The proxy on a Unix socket, the only thing the Linux bridge can reach."""

    class _UnixProxyServer(socketserver.ThreadingUnixStreamServer):  # type: ignore[name-defined,misc]
        daemon_threads = True

    server: Any = _UnixProxyServer(path, _ProxyHandler, bind_and_activate=False)
    server.identity = identity
    server.authority = authority
    server.controller = controller
    server.server_bind()
    server.server_activate()
    return server


@dataclass
class EgressRun:
    """One run's proxy, credential and boundary fields; closed with the run."""

    run_id: str
    owner_principal_id: str
    settings: CommandEgressSettings
    policy_fields: dict[str, Any] = field(default_factory=dict)
    environment: dict[str, str] = field(default_factory=dict)
    _server: Any = None
    _controller: _RecordingController | None = None
    _socket_dir: Path | None = None
    _closed: bool = False

    def start(self, deadline_seconds: float) -> EgressRun:
        policy = self.settings.policy()
        authority = EgressTokenAuthority(secrets.token_bytes(32))
        controller = _RecordingController()
        controller.activate(self.run_id, policy)
        identity = ProxyIdentity(self.owner_principal_id, PROFILE_ID)
        token = authority.issue(
            EgressTokenClaims(
                owner_principal_id=self.owner_principal_id,
                profile_id=PROFILE_ID,
                run_id=self.run_id,
                grant_digest=policy.digest,
                nonce=secrets.token_hex(16),
                expires_at=int(time.time() + deadline_seconds + 60),
            )
        )
        if sys.platform.startswith("linux"):
            # A short private path: Unix socket names are limited to ~108 bytes.
            self._socket_dir = Path(tempfile.mkdtemp(prefix="rk-egress-"))
            socket_path = self._socket_dir / "egress.sock"
            server: Any = _unix_proxy_server(
                str(socket_path), identity=identity, authority=authority, controller=controller
            )
            port = LINUX_BRIDGE_PORT
            self.policy_fields = {
                "network": f"proxy:127.0.0.1:{port}",
                "proxy_socket": str(socket_path),
            }
        else:
            server = EgressProxyServer(
                ("127.0.0.1", 0), identity=identity, authority=authority, controller=controller
            )
            port = int(server.server_address[1])
            self.policy_fields = {"network": f"proxy:127.0.0.1:{port}"}
        url = f"http://{self.run_id}:{token}@127.0.0.1:{port}"
        self.environment = {name: url for name in PROXY_VARIABLES}
        self._server = server
        self._controller = controller
        threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True
        ).start()
        return self

    def close(self) -> list[str]:
        """Stop the proxy and revoke the run; returns refused destinations."""
        if self._closed:
            return []
        self._closed = True
        denied = list(self._controller.denied) if self._controller else []
        if self._controller is not None:
            with contextlib.suppress(ValueError):
                self._controller.revoke(self.run_id)
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._socket_dir is not None:
            for child in self._socket_dir.iterdir():
                with contextlib.suppress(OSError):
                    child.unlink()
            with contextlib.suppress(OSError):
                self._socket_dir.rmdir()
        return denied


class EgressSink:
    """A sink that closes the run's proxy as the run completes.

    Refused destinations are appended as a system line, so the agent (and the
    owner reading the run) learns which host to ask the owner to allow rather
    than seeing only a tool's connection error.
    """

    def __init__(self, sink: Any, egress: EgressRun) -> None:
        self._sink = sink
        self._egress = egress

    def __getattr__(self, name: str) -> Any:
        return getattr(self._sink, name)

    def complete(self, state: Any, returncode: int | None) -> None:
        denied = self._egress.close()
        if denied:
            note = (
                "\n[raiker] network access refused (not on the download allow-list): "
                + ", ".join(denied)
                + "\n"
            )
            self._sink.append_safe("system", note.encode())
        self._sink.complete(state, returncode)
