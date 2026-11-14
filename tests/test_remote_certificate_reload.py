"""BUG-359 limit 3 — a renewed certificate is served without a restart."""

from __future__ import annotations

import os
import socket
import ssl
import threading
import time
from pathlib import Path

from cryptography import x509

from raiker.api.server_runner import CertificateReloader
from tests.test_remote_access import _self_signed


def _served_serial(context: ssl.SSLContext) -> int:
    """Handshake once against ``context`` and return the certificate it served."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def accept() -> None:
        conn, _ = server.accept()
        try:
            with context.wrap_socket(conn, server_side=True) as tls:
                tls.recv(1)
        except (ssl.SSLError, OSError):
            pass

    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    client = ssl.create_default_context()
    client.check_hostname = False
    client.verify_mode = ssl.CERT_NONE
    with socket.create_connection(("127.0.0.1", port)) as raw, client.wrap_socket(raw) as tls:
        der = tls.getpeercert(binary_form=True)
    thread.join(5)
    server.close()
    assert der is not None
    return x509.load_der_x509_certificate(der).serial_number


def _serial(path: Path) -> int:
    return x509.load_pem_x509_certificate(path.read_bytes()).serial_number


def test_a_renewed_pair_is_served_on_the_next_handshake(tmp_path: Path) -> None:
    cert, key = _self_signed(tmp_path, host="127.0.0.1")
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(str(cert), str(key))
    reloader = CertificateReloader(context, str(cert), str(key))
    first = _serial(cert)
    assert _served_serial(context) == first
    assert reloader.check() is False  # nothing changed

    renewed = tmp_path / "renewed"
    renewed.mkdir()
    new_cert, new_key = _self_signed(renewed, host="127.0.0.1")
    os.replace(new_cert, cert)
    os.replace(new_key, key)
    later = time.time() + 5
    os.utime(cert, (later, later))
    assert reloader.check() is True
    assert reloader.reloads == 1
    assert _served_serial(context) == _serial(cert) != first


def test_a_pair_that_does_not_load_keeps_the_old_certificate(tmp_path: Path) -> None:
    cert, key = _self_signed(tmp_path, host="127.0.0.1")
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(str(cert), str(key))
    reloader = CertificateReloader(context, str(cert), str(key))
    first = _serial(cert)
    original = cert.read_bytes()
    cert.write_text("-----BEGIN CERTIFICATE-----\nhalf written\n")
    later = time.time() + 5
    os.utime(cert, (later, later))
    assert reloader.check() is False
    assert reloader.last_error is not None
    cert.write_bytes(original)
    assert _served_serial(context) == first


def test_a_check_keeps_its_path_through_the_response_redactor(tmp_path: Path) -> None:
    """BUG-359 limit 5 — the path is a locator field, not a word in the sentence."""
    from raiker.api.redaction import redact_response_body
    from raiker.app.remote_access import RemoteAccessConfig, validate

    folder = tmp_path / "tmpQ9xZ3kLmN8pR2sT5vW7yA1bC4dE6fG0hJ"
    folder.mkdir()
    missing = folder / "raiker.crt"
    config = RemoteAccessConfig(
        mode="private", private_host="10.1.2.3", private_port=8443,
        tls_cert=str(missing), tls_key=str(folder / "raiker.key"),
    )
    checks = [check.to_dict() for check in validate(config, local_port=8765, bind_test=False) if check.code == "tls_unreadable"]
    assert checks, "expected the missing certificate to be reported"
    body = redact_response_body({"checks": checks})
    assert body["checks"][0]["path"] == str(missing)
    assert "[REDACTED" not in body["checks"][0]["message"]
