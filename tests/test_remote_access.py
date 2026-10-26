"""BUG-347 / BUG-358 — the remote-access configuration, its checks and its starts.

What these hold:

* every field is checked before anything is saved, in words the owner can act
  on: ports, the local listener's port, ports in use, a private address that is
  public, unspecified or not this computer's, TLS files, key permissions, Unix
  sockets and their platform;
* the saved setting survives a restart, and a start opens exactly it;
* a start never exposes the host by accident: no MFA, an unreadable setting or a
  listener that will not open all start this device only, and say why;
* a new setting that will not open falls back to the previous one, which a
  manual roll back also restores;
* Settings reports the listener the running host has open, not the one asked for.
"""

from __future__ import annotations

import json
import os
import socket
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pyotp
import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.app import remote_access as ra
from raiker.storage.sqlite import SQLiteStore

USER, PASSWORD = "owner", "a-long-password-1"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture()
def short_dir() -> Iterator[Path]:
    """A directory short enough for a Unix socket path on macOS (104 bytes)."""
    import shutil
    import tempfile

    path = Path(tempfile.mkdtemp(dir="/tmp" if os.name != "nt" else None, prefix="rk"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _codes(checks: list[ra.Check]) -> list[str]:
    return [check.code for check in ra.blocking(checks)]


def _store_with_mfa(tmp_path: Path) -> tuple[SQLiteStore, TestClient, dict[str, str], pyotp.TOTP]:
    client = TestClient(create_app(tmp_path))
    token = client.post("/api/auth/register", json={"username": USER, "password": PASSWORD}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    secret = client.post("/api/auth/mfa/enroll", headers=headers).json()["secret"]
    totp = pyotp.TOTP(secret)
    assert client.post("/api/auth/mfa/activate", json={"code": totp.now()}, headers=headers).status_code == 200
    return SQLiteStore(tmp_path), client, headers, totp


def _self_signed(tmp_path: Path, host: str = "10.1.2.3", *, days: int = 30) -> tuple[Path, Path]:
    import ipaddress

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1) if days > 0 else now - timedelta(days=10))
        .not_valid_after(now + timedelta(days=days) if days > 0 else now - timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(host))]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = tmp_path / "raiker.crt", tmp_path / "raiker.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    key_path.chmod(0o600)
    return cert_path, key_path


# --- the configuration itself -------------------------------------------------


def test_a_malformed_configuration_is_refused_not_guessed() -> None:
    for raw in ({"mode": "public"}, {"mode": "proxy", "proxy_port": "8766"}, {"mode": "proxy", "proxy_kind": "pipe"}, "x"):
        with pytest.raises(ra.RemoteAccessError):
            ra.RemoteAccessConfig.from_dict(raw)
    # Only the chosen mode's fields are kept.
    config = ra.RemoteAccessConfig.from_dict({"mode": "proxy", "proxy_port": 8766, "tls_cert": "/x"})
    assert config == ra.RemoteAccessConfig(mode="proxy", proxy_kind="port", proxy_port=8766)


@pytest.mark.parametrize(
    ("port", "code"),
    [(None, "port_missing"), (80, "port_range"), (70000, "port_range"), (8765, "port_conflict_local")],
)
def test_proxy_ports_are_checked(port: int | None, code: str) -> None:
    config = ra.RemoteAccessConfig(mode="proxy", proxy_port=port)
    assert _codes(ra.validate(config, local_port=8765)) == [code]


def test_a_port_in_use_is_named() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen(1)
        taken = busy.getsockname()[1]
        config = ra.RemoteAccessConfig(mode="proxy", proxy_port=taken)
        assert _codes(ra.validate(config, local_port=8765)) == ["port_in_use"]
        # The listener this host already holds is not "in use by another program".
        assert _codes(ra.validate(config, local_port=8765, running=config.listener())) == []


@pytest.mark.parametrize(
    ("host", "code"),
    [
        ("not-an-address", "private_host_invalid"),
        ("0.0.0.0", "private_host_unspecified"),
        ("::", "private_host_unspecified"),
        ("127.0.0.1", "private_host_loopback"),
        ("8.8.8.8", "private_host_public"),
        ("192.0.2.2", "private_host_public"),
    ],
)
def test_a_private_listener_never_takes_a_public_or_every_address(host: str, code: str) -> None:
    config = ra.RemoteAccessConfig(mode="private", private_host=host, private_port=8443)
    assert _codes(ra.validate(config, local_port=8765))[:1] == [code]


def test_an_address_that_is_not_this_computers_is_named(tmp_path: Path) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("10.254.254.254", 0))
        except OSError:
            pass
        else:
            pytest.skip("10.254.254.254 is an address of this machine")
    cert, key = _self_signed(tmp_path)
    config = ra.RemoteAccessConfig(mode="private", private_host="10.254.254.254", private_port=_free_port(), tls_cert=str(cert), tls_key=str(key))
    assert "private_host_not_here" in _codes(ra.validate(config, local_port=8765))


def test_tls_files_are_checked(tmp_path: Path) -> None:
    base = {"mode": "private", "private_host": "10.1.2.3", "private_port": 8443}
    missing = ra.RemoteAccessConfig.from_dict(base)
    assert "tls_missing" in _codes(ra._tls_checks(missing))
    cert, key = _self_signed(tmp_path)
    good = ra.RemoteAccessConfig.from_dict({**base, "tls_cert": str(cert), "tls_key": str(key)})
    assert _codes(ra._tls_checks(good)) == []
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    _other_cert, other_key = _self_signed(other_dir)
    mismatched = ra.RemoteAccessConfig.from_dict({**base, "tls_cert": str(cert), "tls_key": str(other_key)})
    assert "tls_invalid" in _codes(ra._tls_checks(mismatched))
    expired_dir = tmp_path / "expired"
    expired_dir.mkdir()
    old_cert, old_key = _self_signed(expired_dir, days=-1)
    expired = ra.RemoteAccessConfig.from_dict({**base, "tls_cert": str(old_cert), "tls_key": str(old_key)})
    assert "tls_expired" in _codes(ra._tls_checks(expired))
    named_for_other = ra.RemoteAccessConfig.from_dict({**base, "private_host": "10.9.9.9", "tls_cert": str(cert), "tls_key": str(key)})
    warnings = [check.code for check in ra._tls_checks(named_for_other) if check.severity == "warning"]
    assert warnings == ["tls_name_mismatch"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_a_private_key_others_can_read_is_refused(tmp_path: Path) -> None:
    cert, key = _self_signed(tmp_path)
    key.chmod(0o644)
    config = ra.RemoteAccessConfig(mode="private", private_host="10.1.2.3", private_port=8443, tls_cert=str(cert), tls_key=str(key))
    assert "tls_key_exposed" in _codes(ra._tls_checks(config))


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX") or sys.platform == "win32", reason="Unix sockets")
def test_unix_socket_paths_are_checked(short_dir: Path) -> None:
    tmp_path = short_dir
    def codes(path: str) -> list[str]:
        return _codes(ra.validate(ra.RemoteAccessConfig(mode="proxy", proxy_kind="socket", proxy_socket=path), local_port=8765))

    assert codes("relative.sock") == ["socket_path_relative"]
    assert codes(str(tmp_path / "missing" / "proxy.sock")) == ["socket_parent_missing"]
    assert codes("/" + "x" * 120) == ["socket_path_too_long"]
    taken = tmp_path / "taken.sock"
    taken.write_text("a file")
    assert codes(str(taken)) == ["socket_path_taken"]
    assert codes(str(tmp_path / "proxy.sock")) == []


def test_unix_sockets_are_refused_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    config = ra.RemoteAccessConfig(mode="proxy", proxy_kind="socket", proxy_socket="C:/raiker.sock")
    assert _codes(ra.validate(config, local_port=8765)) == ["socket_unsupported"]


# --- persistence, starts and rollback ------------------------------------------


def test_the_setting_survives_a_restart_and_opens_as_saved(tmp_path: Path) -> None:
    store, *_ = _store_with_mfa(tmp_path)
    config = ra.RemoteAccessConfig(mode="proxy", proxy_port=_free_port())
    ra.save_desired(store, config, by="test")
    # A new process reads it back from the store.
    plan = ra.prepare(SQLiteStore(tmp_path), local_port=8765)
    try:
        assert plan.outcome == "started"
        assert plan.listener == config.listener()
        assert ra.load_state(SQLiteStore(tmp_path)).last_start["outcome"] == "started"  # type: ignore[index]
    finally:
        assert plan.remote is not None
        plan.remote.sock.close()


def test_no_mfa_means_no_listener(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    client.post("/api/auth/register", json={"username": USER, "password": PASSWORD})
    store = SQLiteStore(tmp_path)
    ra.save_desired(store, ra.RemoteAccessConfig(mode="proxy", proxy_port=_free_port()), by="test")
    plan = ra.prepare(store, local_port=8765)
    assert plan.outcome == "suspended_mfa"
    assert plan.remote is None and plan.listener is None
    # What was asked for is kept, to open once MFA is on.
    assert ra.load_state(store).desired.mode == "proxy"


def test_an_unreadable_setting_starts_this_device_only(tmp_path: Path) -> None:
    store, *_ = _store_with_mfa(tmp_path)
    ra.save_desired(store, ra.RemoteAccessConfig(mode="proxy", proxy_port=_free_port()), by="test")
    with store.connect() as connection:
        connection.execute("UPDATE remote_access_settings SET desired_json = '{\"mode\": \"public\"}'")
    plan = ra.prepare(store, local_port=8765)
    assert plan.outcome == "unreadable" and plan.remote is None
    assert ra.prepare(None, local_port=8765).outcome == "unreadable"


def test_a_setting_that_will_not_open_falls_back_to_the_previous_one(tmp_path: Path) -> None:
    store, *_ = _store_with_mfa(tmp_path)
    good = ra.RemoteAccessConfig(mode="proxy", proxy_port=_free_port())
    ra.save_desired(store, good, by="test")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen(1)
        broken = ra.RemoteAccessConfig(mode="proxy", proxy_port=busy.getsockname()[1])
        ra.save_desired(store, broken, by="test")
        plan = ra.prepare(store, local_port=8765)
    try:
        assert plan.outcome == "fell_back"
        assert plan.listener == good.listener()
        assert plan.attempted == broken
        state = ra.load_state(store)
        assert state.desired == good and state.previous == broken
        kinds = [event["kind"] for event in ra.recent_events(store)]
        assert "start_failed" in kinds and "rolled_back" in kinds
    finally:
        assert plan.remote is not None
        plan.remote.sock.close()


def test_a_setting_that_will_not_open_with_nothing_to_fall_back_to_is_closed(tmp_path: Path) -> None:
    store, *_ = _store_with_mfa(tmp_path)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen(1)
        ra.save_desired(store, ra.RemoteAccessConfig(mode="proxy", proxy_port=busy.getsockname()[1]), by="test")
        plan = ra.prepare(store, local_port=8765)
    assert plan.outcome == "failed" and plan.remote is None
    assert "this device only" in (plan.message or "")


def test_manual_rollback_restores_the_previous_setting(tmp_path: Path) -> None:
    store, *_ = _store_with_mfa(tmp_path)
    first = ra.RemoteAccessConfig(mode="proxy", proxy_port=_free_port())
    second = ra.RemoteAccessConfig(mode="proxy", proxy_port=_free_port())
    ra.save_desired(store, first, by="test")
    ra.save_desired(store, second, by="test")
    state = ra.rollback(store, by="test")
    assert state.desired == first and state.previous == second
    with pytest.raises(ra.RemoteAccessError):
        ra.rollback(SQLiteStore(tmp_path / "empty"), by="test")


def test_start_options_are_used_as_given_and_not_saved(tmp_path: Path) -> None:
    store, *_ = _store_with_mfa(tmp_path)
    override = ra.config_from_start_options(
        proxy_port=_free_port(), proxy_socket=None, private_host=None, private_port=None, tls_cert=None, tls_key=None
    )
    assert override is not None
    plan = ra.prepare(store, local_port=8765, override=override)
    try:
        assert plan.outcome == "started" and plan.source == "start_options"
        assert ra.load_state(store).desired.mode == "local"
    finally:
        assert plan.remote is not None
        plan.remote.sock.close()
    with pytest.raises(ra.RemoteAccessError):
        ra.config_from_start_options(proxy_port=8766, proxy_socket="/tmp/x.sock", private_host=None, private_port=None, tls_cert=None, tls_key=None)


def test_the_event_log_keeps_no_credentials(tmp_path: Path) -> None:
    from raiker.api.proxy_guard import RemoteListener

    _store_with_mfa(tmp_path)
    app = create_app(tmp_path, proxy_listener=RemoteListener(kind="proxy", port=8766))
    device = TestClient(app, base_url="https://testserver:8766", headers={"X-Forwarded-Proto": "https"})
    device.post("/api/auth/login", json={"username": USER, "password": "wrong-password-xyz"})
    ticket = device.post("/api/auth/login", json={"username": USER, "password": PASSWORD}).json()["ticket"]
    device.post("/api/auth/mfa/verify", json={"ticket": ticket, "code": "123456"})
    with SQLiteStore(tmp_path).connect() as connection:
        rows = [dict(row) for row in connection.execute("SELECT kind, detail_json FROM remote_access_events")]
    kinds = [row["kind"] for row in rows]
    assert "remote_sign_in_failed" in kinds and "remote_mfa_failed" in kinds
    text = json.dumps(rows)
    for secret in ("wrong-password-xyz", PASSWORD, ticket, "123456"):
        assert secret not in text
    # Only scalars are ever kept, whatever a caller passes.
    ra.record_event(SQLiteStore(tmp_path), "probe", nested={"a": 1}, n=1)
    assert ra.recent_events(SQLiteStore(tmp_path), limit=1)[0]["detail"] == {"n": 1}


# --- the API ---------------------------------------------------------------------


def test_apply_needs_fresh_mfa_a_confirmation_and_passing_checks(tmp_path: Path) -> None:
    store, client, headers, totp = _store_with_mfa(tmp_path)
    config = {"mode": "proxy", "proxy_kind": "port", "proxy_port": _free_port()}
    by_password = client.post("/api/auth/elevate", json={"password": PASSWORD}, headers=headers).json()["token"]
    assert client.post("/api/remote-access/apply", json={"config": config, "confirm": True},
                       headers={"Authorization": f"Bearer {by_password}"}).status_code == 403
    fresh = {"Authorization": "Bearer " + client.post(
        "/api/auth/elevate", json={"password": PASSWORD, "mfa_code": totp.now()}, headers=headers
    ).json()["token"]}
    assert client.post("/api/remote-access/apply", json={"config": config}, headers=fresh).status_code == 400
    bad = {"mode": "proxy", "proxy_kind": "port", "proxy_port": 8765}
    assert client.post("/api/remote-access/apply", json={"config": bad, "confirm": True}, headers=fresh).status_code == 422
    applied = client.post("/api/remote-access/apply", json={"config": config, "confirm": True}, headers=fresh)
    assert applied.status_code == 200, applied.text
    status = applied.json()
    # Saved for the next start, and not shown as open before it is.
    assert status["desired"]["proxy_port"] == config["proxy_port"]
    assert status["active"]["address"] is None
    assert status["state"] == "pending_restart" and status["restart_required"] is True


def test_check_names_missing_mfa_first(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    token = client.post("/api/auth/register", json={"username": USER, "password": PASSWORD}).json()["token"]
    checks = client.post(
        "/api/remote-access/check",
        json={"mode": "proxy", "proxy_kind": "port", "proxy_port": _free_port()},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert checks["ok"] is False and checks["checks"][0]["code"] == "mfa_required"


def test_status_reports_the_running_listener_not_the_wanted_one(tmp_path: Path) -> None:
    from raiker.api.proxy_guard import RemoteListener

    _store, _client, _headers, totp = _store_with_mfa(tmp_path)
    store = SQLiteStore(tmp_path)
    running = ra.RemoteAccessConfig(mode="proxy", proxy_port=8766)
    ra.save_desired(store, running, by="test")
    app = create_app(tmp_path, proxy_listener=running.listener())
    app.state.remote_access.startup = {"outcome": "started", "config": running.to_dict()}
    local = TestClient(app)
    ticket = local.post("/api/auth/login", json={"username": USER, "password": PASSWORD}).json()["ticket"]
    token = local.post("/api/auth/mfa/verify", json={"ticket": ticket, "code": totp.now()}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    status = local.get("/api/remote-access", headers=headers).json()
    assert status["state"] == "enabled" and status["active"]["address"] == "127.0.0.1:8766"
    assert status["https"] == "not_verified" and status["restart_required"] is False
    # An HTTPS request through the proxy verifies it.
    TestClient(app, base_url="https://testserver:8766", headers={"X-Forwarded-Proto": "https"}).get("/api/health")
    assert local.get("/api/remote-access", headers=headers).json()["https"] == "verified"
    # Asking for something else is pending until a restart, and says so.
    ra.save_desired(store, ra.RemoteAccessConfig(mode="proxy", proxy_port=8799), by="test")
    pending = local.get("/api/remote-access", headers=headers).json()
    assert pending["state"] == "pending_restart" and pending["active"]["address"] == "127.0.0.1:8766"
    assert RemoteListener(kind="proxy", port=8766).describe() == pending["active"]["address"]


def test_the_host_menu_reports_access_from_the_running_host(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    token = client.post("/api/auth/register", json={"username": USER, "password": PASSWORD}).json()["token"]
    access = client.get("/api/host", headers={"Authorization": f"Bearer {token}"}).json()["access"]
    assert access == {"state": "disabled", "mode": "local", "address": None}


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_the_proxy_socket_is_created_owner_and_group_only(short_dir: Path) -> None:
    import stat

    path = short_dir / "proxy.sock"
    opened = ra.open_listener(ra.RemoteAccessConfig(mode="proxy", proxy_kind="socket", proxy_socket=str(path)))
    try:
        assert stat.S_IMODE(path.stat().st_mode) & 0o007 == 0
        opened.sock.listen(1)
        with pytest.raises(ra.RemoteAccessError) as live:
            ra.open_listener(ra.RemoteAccessConfig(mode="proxy", proxy_kind="socket", proxy_socket=str(path)))
        assert live.value.code == "socket_in_use"
    finally:
        opened.sock.close()
    replaced = ra.open_listener(ra.RemoteAccessConfig(mode="proxy", proxy_kind="socket", proxy_socket=str(path)))
    replaced.sock.close()


def test_reapplying_the_listener_this_host_holds_is_not_in_use(tmp_path: Path) -> None:
    """Turned off, the listener is still bound until a restart; it is Raiker's own."""
    _store, _client, headers, totp = _store_with_mfa(tmp_path)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as held:
        held.bind(("127.0.0.1", 0))
        held.listen(1)
        port = held.getsockname()[1]
        config = ra.RemoteAccessConfig(mode="proxy", proxy_port=port)
        app = create_app(tmp_path, proxy_listener=config.listener())
        app.state.remote_access.disable_now()
        client = TestClient(app)
        answer = client.post(
            "/api/remote-access/check", json={"mode": "proxy", "proxy_kind": "port", "proxy_port": port}, headers=headers
        ).json()
        assert answer["ok"] is True, answer


def test_a_setting_that_failed_to_start_is_not_working_until_changed(tmp_path: Path) -> None:
    _store, _client, headers, _totp = _store_with_mfa(tmp_path)
    store = SQLiteStore(tmp_path)
    broken = ra.RemoteAccessConfig(mode="proxy", proxy_port=8790)
    ra.save_desired(store, broken, by="test")
    app = create_app(tmp_path)
    app.state.remote_access.startup = {"outcome": "failed", "attempted": broken.to_dict(), "message": "Remote access did not start: x"}
    client = TestClient(app)
    status = client.get("/api/remote-access", headers=headers).json()
    assert status["state"] == "error" and status["restart_required"] is False
    assert status["problems"][0]["message"] == "Remote access did not start: x"
    ra.save_desired(store, ra.RemoteAccessConfig(mode="proxy", proxy_port=8791), by="test")
    changed = client.get("/api/remote-access", headers=headers).json()
    assert changed["state"] == "pending_restart" and changed["restart_required"] is True

