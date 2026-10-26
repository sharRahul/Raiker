"""BUG-347 / BUG-358 — how other devices reach this Raiker.

Owner's decisions (2026-10-26):

* Raiker's own listener stays on this computer (``127.0.0.1``), always. Other
  devices reach it through **one remote listener**, chosen in Settings →
  Security → Remote access and off by default:

  ``local``    This device only. No remote listener.
  ``private``  A private or VPN address (``10/8``, ``172.16/12``, ``192.168/16``,
               ``100.64/10`` as Tailscale uses, ``fc00::/7``) where Raiker serves
               HTTPS itself with the owner's certificate and key.
  ``proxy``    A listener for a reverse proxy on this computer: ``127.0.0.1``
               on a port of its own, or a Unix domain socket (``0660``). The
               proxy terminates HTTPS; Raiker believes its ``X-Forwarded-Proto``
               on that listener alone.

* **Two-step sign-in is the key, not a shared secret.** ``RAIKER_OWNER_TOKEN``
  is gone. A remote listener opens only while every account has MFA; from
  another device a session needs the password *and* a code; turning MFA off or
  resetting it suspends remote access at once (``raiker.api.auth``).

* **Nothing here is applied silently.** A change is validated, reviewed and
  confirmed with fresh MFA, saved as the *desired* configuration, and takes
  effect when the host restarts. The configuration before it is kept as the
  rollback target, and a start that cannot open the new listener falls back to
  the previous one, or to this device only, and says why. A setting that cannot
  be read starts this device only. Invalid never means exposed.

The listener actually open is what the running host reports
(``app.state.remote_access``); Settings shows that, not what was asked for.
"""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import ssl
import stat
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from raiker.api.proxy_guard import RemoteListener
from raiker.api.server_runner import RemoteSocket
from raiker.contracts.ids import utc_now

Mode = Literal["local", "private", "proxy"]
MODES: tuple[Mode, ...] = ("local", "private", "proxy")
ProxyKind = Literal["port", "socket"]

DEFAULT_PROXY_PORT = 8766
DEFAULT_PRIVATE_PORT = 8443
#: Unix socket paths longer than this do not fit ``sockaddr_un`` on macOS.
MAX_SOCKET_PATH = 100

#: The networks a private-network listener may use. Everything else is either
#: this computer (loopback), every network at once (unspecified) or public.
_PRIVATE_NETWORKS = tuple(
    ipaddress.ip_network(net)
    for net in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10", "fc00::/7")
)

#: How a start went, as Settings and Diagnostics name it.
StartOutcome = Literal[
    "local", "started", "fell_back", "failed", "suspended_mfa", "unreadable"
]


class RemoteAccessError(ValueError):
    """A configuration that cannot be used, with a code the UI can explain."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class RemoteAccessConfig:
    mode: Mode = "local"
    proxy_kind: ProxyKind = "port"
    proxy_port: int | None = None
    proxy_socket: str | None = None
    private_host: str | None = None
    private_port: int | None = None
    tls_cert: str | None = None
    tls_key: str | None = None

    @classmethod
    def from_dict(cls, raw: Any) -> RemoteAccessConfig:
        """Read a stored or submitted configuration; anything malformed refuses."""
        if not isinstance(raw, dict):
            raise RemoteAccessError("config_malformed", "The remote-access setting is not readable.")
        mode = raw.get("mode", "local")
        if mode not in MODES:
            raise RemoteAccessError("config_malformed", f"Unknown connection mode {mode!r}.")
        raw_kind = raw.get("proxy_kind") or "port"
        if raw_kind not in ("port", "socket"):
            raise RemoteAccessError("config_malformed", f"Unknown proxy listener kind {raw_kind!r}.")
        kind: ProxyKind = "socket" if raw_kind == "socket" else "port"

        def port(name: str) -> int | None:
            value = raw.get(name)
            if value is None or value == "":
                return None
            if isinstance(value, bool) or not isinstance(value, int):
                raise RemoteAccessError("config_malformed", f"{name} must be a number.")
            return value

        def text(name: str) -> str | None:
            value = raw.get(name)
            if value is None:
                return None
            if not isinstance(value, str):
                raise RemoteAccessError("config_malformed", f"{name} must be text.")
            value = value.strip()
            return value or None

        return cls(
            mode=mode,
            proxy_kind=kind,
            proxy_port=port("proxy_port"),
            proxy_socket=text("proxy_socket"),
            private_host=text("private_host"),
            private_port=port("private_port"),
            tls_cert=text("tls_cert"),
            tls_key=text("tls_key"),
        ).normalized()

    def normalized(self) -> RemoteAccessConfig:
        """Only the fields the chosen mode uses."""
        if self.mode == "local":
            return RemoteAccessConfig()
        if self.mode == "proxy":
            if self.proxy_kind == "socket":
                return RemoteAccessConfig(mode="proxy", proxy_kind="socket", proxy_socket=self.proxy_socket)
            return RemoteAccessConfig(mode="proxy", proxy_kind="port", proxy_port=self.proxy_port)
        return RemoteAccessConfig(
            mode="private",
            private_host=self.private_host,
            private_port=self.private_port,
            tls_cert=self.tls_cert,
            tls_key=self.tls_key,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def listener(self) -> RemoteListener | None:
        if self.mode == "proxy":
            if self.proxy_kind == "socket":
                return RemoteListener(kind="proxy", socket_path=self.proxy_socket)
            return RemoteListener(kind="proxy", port=self.proxy_port)
        if self.mode == "private":
            return RemoteListener(kind="private", host=self.private_host, port=self.private_port)
        return None


@dataclass(frozen=True)
class Check:
    """One validation result, in words the owner can act on."""

    code: str
    ok: bool
    message: str
    field: str | None = None
    severity: Literal["error", "warning", "info"] = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def blocking(checks: list[Check]) -> list[Check]:
    return [check for check in checks if not check.ok and check.severity == "error"]


# --- validation ---------------------------------------------------------------


def _port_checks(port: int | None, field_name: str, *, local_port: int) -> list[Check]:
    if port is None:
        return [Check("port_missing", False, "Choose a port.", field_name)]
    if not 1024 <= port <= 65535:
        return [Check("port_range", False, "Choose a port between 1024 and 65535.", field_name)]
    if port == local_port:
        return [
            Check(
                "port_conflict_local",
                False,
                f"Port {port} is Raiker's own listener for this computer. Choose another one.",
                field_name,
            )
        ]
    return []


def _claim_port(sock: socket.socket) -> None:
    """Bind options that never share a port another program holds.

    On Windows ``SO_REUSEADDR`` lets a second socket bind a port that is in use,
    so a probe would pass and a listener could take another program's port;
    ``SO_EXCLUSIVEADDRUSE`` is the option that means what Raiker needs there.
    Elsewhere ``SO_REUSEADDR`` only allows rebinding a port in ``TIME_WAIT``.
    """
    if sys.platform == "win32":
        exclusive = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
        if exclusive is not None:
            sock.setsockopt(socket.SOL_SOCKET, exclusive, 1)
        return
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


def _bind_probe(family: int, address: Any) -> OSError | None:
    probe = socket.socket(family, socket.SOCK_STREAM)
    try:
        if family != getattr(socket, "AF_UNIX", -1):
            _claim_port(probe)
        probe.bind(address)
        return None
    except OSError as error:
        return error
    finally:
        probe.close()


def _socket_in_use(path: Path) -> bool:
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)  # type: ignore[attr-defined,unused-ignore]
    try:
        probe.connect(str(path))
        return True
    except OSError:
        return False
    finally:
        probe.close()


def _is_private(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(address in network for network in _PRIVATE_NETWORKS)


def _tls_checks(config: RemoteAccessConfig) -> list[Check]:
    checks: list[Check] = []
    if not config.tls_cert or not config.tls_key:
        return [
            Check(
                "tls_missing",
                False,
                "Choose the certificate and private key Raiker serves HTTPS with. Other devices are "
                "only ever answered over HTTPS.",
                "tls_cert",
            )
        ]
    cert, key = Path(config.tls_cert), Path(config.tls_key)
    for path, name in ((cert, "tls_cert"), (key, "tls_key")):
        if not path.is_absolute():
            checks.append(Check("tls_path_relative", False, f"Give the full path to {path.name}.", name))
        elif not path.is_file():
            checks.append(Check("tls_unreadable", False, f"{path} does not exist or is not a file.", name))
        elif not os.access(path, os.R_OK):
            checks.append(Check("tls_unreadable", False, f"Raiker cannot read {path}.", name))
    if checks:
        return checks
    if sys.platform != "win32":
        mode = stat.S_IMODE(key.stat().st_mode)
        if mode & 0o077:
            checks.append(
                Check(
                    "tls_key_exposed",
                    False,
                    f"Other users on this computer can read the private key (mode {mode:o}). "
                    f"Run: chmod 600 {key}",
                    "tls_key",
                )
            )
    try:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(str(cert), str(key))
    except (ssl.SSLError, OSError, ValueError) as error:
        checks.append(
            Check(
                "tls_invalid",
                False,
                f"The certificate and key do not load together ({error.__class__.__name__}). Check that "
                "both are PEM files and that the key belongs to the certificate.",
                "tls_cert",
            )
        )
        return checks
    checks.extend(_certificate_dates_and_names(cert, config.private_host))
    return checks


def _certificate_dates_and_names(cert: Path, host: str | None) -> list[Check]:
    try:
        from cryptography import x509

        loaded = x509.load_pem_x509_certificate(cert.read_bytes())
    except Exception:  # noqa: BLE001 - a chain that loaded but does not parse here is reported, not fatal
        return [Check("tls_unparsed", True, "The certificate's dates could not be read.", "tls_cert", "warning")]
    now = datetime.now(UTC)
    checks: list[Check] = []
    if loaded.not_valid_after_utc <= now:
        checks.append(Check("tls_expired", False, "The certificate has expired. Renew it first.", "tls_cert"))
    elif loaded.not_valid_before_utc > now:
        checks.append(Check("tls_not_yet_valid", False, "The certificate is not valid yet.", "tls_cert"))
    if host:
        names: list[str] = []
        addresses: list[str] = []
        try:
            san = loaded.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
            names = [str(name) for name in san.get_values_for_type(x509.DNSName)]
            addresses = [str(address) for address in san.get_values_for_type(x509.IPAddress)]
        except x509.ExtensionNotFound:
            pass
        if host not in addresses:
            shown = ", ".join(names + addresses) or "no names"
            checks.append(
                Check(
                    "tls_name_mismatch",
                    True,
                    f"The certificate is for {shown}, not {host}. Browsers will warn unless you open "
                    "Raiker by one of those names.",
                    "tls_cert",
                    "warning",
                )
            )
    return checks


def validate(
    config: RemoteAccessConfig,
    *,
    local_port: int,
    running: RemoteListener | None = None,
    bind_test: bool = True,
) -> list[Check]:
    """Everything that would stop this configuration working, before it is saved.

    ``running`` is the remote listener this host has open now: a port or
    socket it already holds is not "in use by something else".
    """
    if config.mode == "local":
        return []
    checks: list[Check] = []
    listener = config.listener()
    already_held = running is not None and listener == running
    if config.mode == "proxy" and config.proxy_kind == "port":
        checks += _port_checks(config.proxy_port, "proxy_port", local_port=local_port)
        if not checks and bind_test and not already_held:
            failure = _bind_probe(socket.AF_INET, ("127.0.0.1", int(config.proxy_port or 0)))
            if failure is not None:
                checks.append(
                    Check(
                        "port_in_use",
                        False,
                        f"Port {config.proxy_port} on 127.0.0.1 is already in use by another program.",
                        "proxy_port",
                    )
                )
    elif config.mode == "proxy":
        checks += _socket_checks(config.proxy_socket, already_held=already_held, bind_test=bind_test)
    else:
        checks += _private_checks(config, local_port=local_port, already_held=already_held, bind_test=bind_test)
    return checks


def _socket_checks(raw: str | None, *, already_held: bool, bind_test: bool) -> list[Check]:
    if not hasattr(socket, "AF_UNIX") or sys.platform == "win32":
        return [
            Check(
                "socket_unsupported",
                False,
                "A Unix socket is not available on Windows. Use a port on 127.0.0.1 instead.",
                "proxy_socket",
            )
        ]
    if not raw:
        return [Check("socket_missing", False, "Choose where to create the socket.", "proxy_socket")]
    path = Path(raw)
    if not path.is_absolute():
        return [Check("socket_path_relative", False, "Give the socket's full path, starting with /.", "proxy_socket")]
    if len(str(path)) > MAX_SOCKET_PATH:
        return [
            Check(
                "socket_path_too_long",
                False,
                f"Socket paths longer than {MAX_SOCKET_PATH} characters do not work on every system. Choose a shorter one, such as /run/raiker/proxy.sock.",
                "proxy_socket",
            )
        ]
    parent = path.parent
    if not parent.is_dir():
        return [Check("socket_parent_missing", False, f"The folder {parent} does not exist. Create it first.", "proxy_socket")]
    if not os.access(parent, os.W_OK | os.X_OK):
        return [Check("socket_parent_not_writable", False, f"Raiker cannot create files in {parent}.", "proxy_socket")]
    if path.exists() or path.is_symlink():
        if not stat.S_ISSOCK(path.lstat().st_mode):
            return [Check("socket_path_taken", False, f"{path} exists and is not a socket. Raiker will not replace it.", "proxy_socket")]
        if bind_test and not already_held and _socket_in_use(path):
            return [Check("socket_in_use", False, f"{path} is in use by another program.", "proxy_socket")]
    return [
        Check(
            "socket_permissions",
            True,
            "The socket is created for Raiker's user and group only (0660). Add the proxy's user to that group.",
            "proxy_socket",
            "info",
        )
    ]


def _private_checks(
    config: RemoteAccessConfig, *, local_port: int, already_held: bool, bind_test: bool
) -> list[Check]:
    checks: list[Check] = []
    host = config.private_host
    try:
        address = ipaddress.ip_address(host or "")
    except ValueError:
        return [
            Check(
                "private_host_invalid",
                False,
                "Enter this computer's address on your private network or VPN, such as 100.101.102.103 or 192.168.1.20.",
                "private_host",
            )
        ]
    if address.is_unspecified:
        return [
            Check(
                "private_host_unspecified",
                False,
                f"{address} would listen on every network, public ones included. Choose one private address.",
                "private_host",
            )
        ]
    if address.is_loopback:
        return [Check("private_host_loopback", False, "That is this computer's own loopback address. Choose its private-network address.", "private_host")]
    if not _is_private(address):
        return [
            Check(
                "private_host_public",
                False,
                f"{address} is not a private-network address. Raiker never listens on a public address; "
                "use a reverse proxy for that.",
                "private_host",
            )
        ]
    checks += _port_checks(config.private_port, "private_port", local_port=local_port)
    if not checks and bind_test and not already_held:
        family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
        failure = _bind_probe(family, (str(address), int(config.private_port or 0)))
        if failure is not None:
            in_use = getattr(failure, "errno", None) in {48, 98, 10048}
            checks.append(
                Check(
                    "port_in_use" if in_use else "private_host_not_here",
                    False,
                    f"Port {config.private_port} on {address} is already in use by another program."
                    if in_use
                    else f"{address} is not an address of this computer. Check the address your VPN or network gave it.",
                    "private_port" if in_use else "private_host",
                )
            )
    checks += _tls_checks(config)
    return checks


# --- persistence ----------------------------------------------------------------


@dataclass
class RemoteAccessState:
    desired: RemoteAccessConfig = field(default_factory=RemoteAccessConfig)
    previous: RemoteAccessConfig | None = None
    last_start: dict[str, Any] | None = None
    updated_at: str | None = None
    updated_by: str | None = None
    unreadable: str | None = None


_SELECT_STATE = (
    "SELECT desired_json, previous_json, last_start_json, updated_at, updated_by "
    "FROM remote_access_settings WHERE settings_id = 1"
)
_UPSERT_STATE = (
    "INSERT INTO remote_access_settings (settings_id, desired_json, previous_json, last_start_json, "
    "updated_at, updated_by) VALUES (1, ?, ?, ?, ?, ?) ON CONFLICT(settings_id) DO UPDATE SET "
    "desired_json = excluded.desired_json, previous_json = excluded.previous_json, "
    "last_start_json = excluded.last_start_json, updated_at = excluded.updated_at, "
    "updated_by = excluded.updated_by"
)
_INSERT_EVENT = "INSERT INTO remote_access_events (at, kind, detail_json) VALUES (?, ?, ?)"
_RECENT_EVENTS = (
    "SELECT event_id, at, kind, detail_json FROM remote_access_events "
    "ORDER BY event_id DESC LIMIT ?"
)
_COUNT_EVENTS = "SELECT COUNT(*) FROM remote_access_events WHERE kind = ? AND at >= ?"


def load_state(store: Any) -> RemoteAccessState:
    """The stored settings. Anything unreadable is this device only, said as such."""
    try:
        with store.connect() as connection:
            row = connection.execute(_SELECT_STATE).fetchone()
    except Exception as error:  # noqa: BLE001 - an unreadable setting is "local", never "open"
        return RemoteAccessState(unreadable=error.__class__.__name__)
    if row is None:
        return RemoteAccessState()
    try:
        desired = RemoteAccessConfig.from_dict(json.loads(row["desired_json"]))
        previous = (
            RemoteAccessConfig.from_dict(json.loads(row["previous_json"])) if row["previous_json"] else None
        )
    except (RemoteAccessError, ValueError, TypeError) as error:
        return RemoteAccessState(unreadable=getattr(error, "code", "config_malformed"))
    last_start: dict[str, Any] | None = None
    if row["last_start_json"]:
        try:
            loaded = json.loads(row["last_start_json"])
            last_start = loaded if isinstance(loaded, dict) else None
        except ValueError:
            last_start = None
    return RemoteAccessState(
        desired=desired,
        previous=previous,
        last_start=last_start,
        updated_at=row["updated_at"],
        updated_by=row["updated_by"],
    )


def _write_state(store: Any, state: RemoteAccessState) -> None:
    with store.connect() as connection:
        connection.execute(
            _UPSERT_STATE,
            (
                json.dumps(state.desired.to_dict()),
                json.dumps(state.previous.to_dict()) if state.previous is not None else None,
                json.dumps(state.last_start) if state.last_start is not None else None,
                state.updated_at or utc_now(),
                state.updated_by,
            ),
        )


def save_desired(store: Any, config: RemoteAccessConfig, *, by: str) -> RemoteAccessState:
    """Make ``config`` what the next start opens; the one it replaces becomes the rollback."""
    state = load_state(store)
    if state.unreadable is not None:
        state = RemoteAccessState()
    config = config.normalized()
    if config != state.desired:
        state.previous = state.desired
    state.desired = config
    state.updated_at = utc_now()
    state.updated_by = by
    _write_state(store, state)
    return state


def rollback(store: Any, *, by: str) -> RemoteAccessState:
    """Go back to the configuration before the last change."""
    state = load_state(store)
    if state.previous is None:
        raise RemoteAccessError("nothing_to_roll_back", "There is no earlier remote-access setting to go back to.")
    state.desired, state.previous = state.previous, state.desired
    state.updated_at = utc_now()
    state.updated_by = by
    _write_state(store, state)
    return state


def record_start(store: Any, last_start: dict[str, Any], *, desired: RemoteAccessConfig | None = None) -> None:
    state = load_state(store)
    if state.unreadable is not None:
        return
    state.last_start = last_start
    if desired is not None and desired != state.desired:
        # A start that fell back to the previous configuration makes it the
        # desired one again, so Settings does not keep promising the one that
        # failed; the failed one stays as the rollback target to retry.
        state.previous, state.desired = state.desired, desired
    _write_state(store, state)


def record_event(store: Any, kind: str, **detail: Any) -> None:
    """Append one remote-access event. Never raises: the event is a record, not the action."""
    safe = {key: value for key, value in detail.items() if isinstance(value, (str, int, float, bool)) or value is None}
    try:
        with store.connect() as connection:
            connection.execute(_INSERT_EVENT, (utc_now(), kind, json.dumps(safe)))
    except Exception:  # noqa: BLE001
        return


def recent_events(store: Any, limit: int = 20) -> list[dict[str, Any]]:
    try:
        with store.connect() as connection:
            rows = connection.execute(_RECENT_EVENTS, (limit,)).fetchall()
    except Exception:  # noqa: BLE001
        return []
    events = []
    for row in rows:
        try:
            detail = json.loads(row["detail_json"])
        except ValueError:
            detail = {}
        events.append({"at": row["at"], "kind": row["kind"], "detail": detail if isinstance(detail, dict) else {}})
    return events


def count_events(store: Any, kind: str, since: str) -> int:
    try:
        with store.connect() as connection:
            row = connection.execute(_COUNT_EVENTS, (kind, since)).fetchone()
    except Exception:  # noqa: BLE001
        return 0
    return int(row[0]) if row is not None else 0


def mfa_readiness(store: Any) -> dict[str, Any]:
    """Whether remote access may be on: every account has two-step sign-in."""
    try:
        accounts = store.list_accounts()
    except Exception:  # noqa: BLE001
        return {"ready": False, "accounts": 0, "without_mfa": 0}
    without = [account for account in accounts if not account.get("mfa_enrolled")]
    return {"ready": bool(accounts) and not without, "accounts": len(accounts), "without_mfa": len(without)}


# --- opening the listener and starting -------------------------------------------


def open_listener(config: RemoteAccessConfig) -> RemoteSocket:
    """Bind the remote listener this configuration describes, or refuse with a reason."""
    listener = config.listener()
    if listener is None:
        raise RemoteAccessError("no_listener", "This device only has no remote listener.")
    if config.mode == "proxy" and config.proxy_kind == "socket":
        return RemoteSocket(sock=_bind_unix_socket(Path(str(config.proxy_socket))))
    if config.mode == "proxy":
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _claim_port(sock)
        try:
            sock.bind(("127.0.0.1", int(config.proxy_port or 0)))
        except OSError as error:
            sock.close()
            raise RemoteAccessError("port_in_use", f"Could not open 127.0.0.1:{config.proxy_port}: {error.strerror}") from error
        sock.set_inheritable(True)
        return RemoteSocket(sock=sock)
    tls = [check for check in _tls_checks(config) if not check.ok and check.severity == "error"]
    if tls:
        raise RemoteAccessError(tls[0].code, tls[0].message)
    address = ipaddress.ip_address(str(config.private_host))
    if not _is_private(address) or address.is_loopback:
        raise RemoteAccessError("private_host_public", f"{address} is not a private-network address.")
    family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    _claim_port(sock)
    try:
        sock.bind((str(address), int(config.private_port or 0)))
    except OSError as error:
        sock.close()
        raise RemoteAccessError("private_host_not_here", f"Could not open {address}:{config.private_port}: {error.strerror}") from error
    sock.set_inheritable(True)
    return RemoteSocket(sock=sock, tls_cert=config.tls_cert, tls_key=config.tls_key)


def _bind_unix_socket(path: Path) -> socket.socket:
    if not hasattr(socket, "AF_UNIX") or sys.platform == "win32":
        raise RemoteAccessError("socket_unsupported", "A Unix socket is not available on Windows.")
    if path.exists() or path.is_symlink():
        # Replace only a stale socket: never a file somebody put there, and
        # never a socket another host is still serving.
        if not stat.S_ISSOCK(path.lstat().st_mode):
            raise RemoteAccessError("socket_path_taken", f"{path} exists and is not a socket.")
        if _socket_in_use(path):
            raise RemoteAccessError("socket_in_use", f"{path} is in use by another process.")
        path.unlink()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)  # type: ignore[attr-defined,unused-ignore]
    # Created owner-and-group only from the start, not opened up and then narrowed.
    previous = os.umask(0o117)
    try:
        sock.bind(str(path))
    except OSError as error:
        sock.close()
        raise RemoteAccessError("socket_parent_not_writable", f"Could not create {path}: {error.strerror}") from error
    finally:
        os.umask(previous)
    os.chmod(path, 0o660)
    sock.set_inheritable(True)
    return sock


@dataclass
class StartPlan:
    """What this start opens, and what to tell the owner about it."""

    config: RemoteAccessConfig
    outcome: StartOutcome
    source: Literal["settings", "start_options"] = "settings"
    reason: str | None = None
    message: str | None = None
    remote: RemoteSocket | None = None
    attempted: RemoteAccessConfig | None = None

    @property
    def listener(self) -> RemoteListener | None:
        return self.config.listener() if self.remote is not None else None

    def summary(self) -> dict[str, Any]:
        return {
            "at": utc_now(),
            "outcome": self.outcome,
            "source": self.source,
            "reason": self.reason,
            "message": self.message,
            "config": self.config.to_dict(),
            "attempted": self.attempted.to_dict() if self.attempted is not None else None,
            "listener": self.listener.describe() if self.listener is not None else None,
        }


def prepare(
    store: Any,
    *,
    local_port: int,
    override: RemoteAccessConfig | None = None,
) -> StartPlan:
    """Decide and open this start's remote listener. Fails closed, never open.

    ``override`` is a configuration given as start options (``raiker-web
    --proxy-port`` and friends); it is used as given and not saved. Otherwise
    the saved setting is used, and a saved configuration that cannot open falls
    back to the previous one, then to this device only.
    """
    source: Literal["settings", "start_options"] = "start_options" if override is not None else "settings"
    if store is None:
        return StartPlan(RemoteAccessConfig(), "unreadable", source, "store_unavailable",
                         "Raiker's data could not be read, so it started for this device only.")
    state = load_state(store)
    if override is None and state.unreadable is not None:
        plan = StartPlan(RemoteAccessConfig(), "unreadable", source, state.unreadable,
                         "The remote-access setting could not be read, so Raiker started for this device only.")
        record_event(store, "start_failed", reason=state.unreadable)
        return plan
    wanted = override if override is not None else state.desired
    if wanted.mode == "local":
        plan = StartPlan(RemoteAccessConfig(), "local", source)
        _finish(store, plan, override)
        return plan
    readiness = mfa_readiness(store)
    if not readiness["ready"]:
        plan = StartPlan(
            RemoteAccessConfig(), "suspended_mfa", source, "mfa_required",
            "Remote access is suspended: turn on two-step sign-in, then restart Raiker.",
            attempted=wanted,
        )
        record_event(store, "suspended", reason="mfa_required", at_start=True)
        _finish(store, plan, override, keep_desired=True)
        return plan
    try:
        remote = _open_checked(wanted, local_port=local_port)
    except RemoteAccessError as error:
        record_event(store, "start_failed", reason=error.code, mode=wanted.mode)
        fallback = state.previous if override is None else None
        if fallback is not None and fallback.mode != "local" and fallback != wanted:
            try:
                remote = _open_checked(fallback, local_port=local_port)
            except RemoteAccessError:
                pass
            else:
                plan = StartPlan(
                    fallback, "fell_back", source, error.code,
                    f"The new remote-access setting did not start ({error.message}) Raiker went back to the previous one.",
                    remote=remote, attempted=wanted,
                )
                record_event(store, "rolled_back", reason=error.code, automatic=True)
                _finish(store, plan, override, desired=fallback)
                return plan
        plan = StartPlan(
            RemoteAccessConfig(), "failed", source, error.code,
            f"Remote access did not start: {error.message} Raiker is reachable from this device only.",
            attempted=wanted,
        )
        _finish(store, plan, override, keep_desired=True)
        return plan
    plan = StartPlan(wanted, "started", source, remote=remote)
    record_event(store, "started", mode=wanted.mode, listener=plan.listener.describe() if plan.listener else None)
    _finish(store, plan, override)
    return plan


def _open_checked(config: RemoteAccessConfig, *, local_port: int) -> RemoteSocket:
    errors = blocking(validate(config, local_port=local_port, bind_test=False))
    if errors:
        raise RemoteAccessError(errors[0].code, errors[0].message)
    return open_listener(config)


def _finish(
    store: Any,
    plan: StartPlan,
    override: RemoteAccessConfig | None,
    *,
    desired: RemoteAccessConfig | None = None,
    keep_desired: bool = False,
) -> None:
    if override is not None:
        # Start options are not saved: the next plain start uses Settings again.
        record_start(store, plan.summary())
        return
    record_start(store, plan.summary(), desired=None if keep_desired else desired)


def config_from_start_options(
    *,
    proxy_port: int | None,
    proxy_socket: str | None,
    private_host: str | None,
    private_port: int | None,
    tls_cert: str | None,
    tls_key: str | None,
) -> RemoteAccessConfig | None:
    """The configuration ``raiker-web``'s start options describe, or None for Settings."""
    chosen = [
        name
        for name, value in (("--proxy-port", proxy_port), ("--proxy-socket", proxy_socket), ("--private-host", private_host))
        if value
    ]
    if not chosen:
        if any((private_port, tls_cert, tls_key)):
            raise RemoteAccessError(
                "start_options_incomplete", "--private-port, --tls-cert and --tls-key go with --private-host."
            )
        return None
    if len(chosen) > 1:
        raise RemoteAccessError("start_options_conflict", f"Choose one remote listener, not {' and '.join(chosen)}.")
    if proxy_port is not None:
        return RemoteAccessConfig(mode="proxy", proxy_kind="port", proxy_port=proxy_port)
    if proxy_socket:
        return RemoteAccessConfig(mode="proxy", proxy_kind="socket", proxy_socket=str(Path(proxy_socket).resolve()))
    return RemoteAccessConfig(
        mode="private",
        private_host=private_host,
        private_port=private_port or DEFAULT_PRIVATE_PORT,
        tls_cert=str(Path(tls_cert).resolve()) if tls_cert else None,
        tls_key=str(Path(tls_key).resolve()) if tls_key else None,
    )
