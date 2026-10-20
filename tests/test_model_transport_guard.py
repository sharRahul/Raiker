"""BUG-349 — the dial-time address guard on both model transports.

The transport hardening plan (now FIXED-1021 to FIXED-1030 in
``docs/plans/FIXED_ITEMS.md``) named twelve scenarios, NET-01 to NET-12. Each test below names the one it proves. Resolution is
stubbed where the scenario is about an answer no real resolver would give on
demand (a hosted name that becomes ``10.0.0.5``); everything that can be real
is real — sockets, a loopback HTTP server, a TLS handshake, a CONNECT proxy.
"""

from __future__ import annotations

import asyncio
import datetime
import http.server
import ipaddress
import socket
import ssl
import threading
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpcore
import httpx
import pytest

from raiker.models.exceptions import (
    ProviderDialRefusedError,
    ProviderPolicyError,
    provider_error_code,
    provider_failure_message,
)
from raiker.models.factory import ModelProviderFactory, ProviderRuntimePolicy
from raiker.models.registry import ModelProfileRegistry, profile_with_model
from raiker.models.transport import ModelTransport, ProviderClientPool
from raiker.models.transport_guard import (
    GuardedNetworkBackend,
    proxy_for,
    proxy_route,
    refuse_metadata_destination,
    resolve_for_dial,
)
from raiker.runtime.executors import sandbox
from raiker.runtime.executors.sandbox import SandboxError, post_json

OPEN = ProviderRuntimePolicy(
    allow_policy_gated_provider=True,
    allow_hosted_provider=True,
    allow_private_network_provider=True,
)
_PROXY_VARIABLES = (
    "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy",
    "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy",
)


@pytest.fixture(autouse=True)
def _no_proxy_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test states its own proxy environment; none inherits the host's."""
    for name in _PROXY_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def _answers(*addresses: str) -> Any:
    """A ``getaddrinfo`` stand-in that answers *addresses* and counts its calls."""
    calls: list[str] = []

    def resolver(host: str, port: int, *args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
        calls.append(host)
        out = []
        for address in addresses:
            family = socket.AF_INET6 if ":" in address else socket.AF_INET
            out.append((family, socket.SOCK_STREAM, 6, "", (address, port)))
        return out

    resolver.calls = calls  # type: ignore[attr-defined]
    return resolver


def _sequence(*rounds: tuple[str, ...]) -> Any:
    """A resolver whose *n*-th lookup answers ``rounds[n]`` — a rebinding name."""
    calls: list[str] = []

    def resolver(host: str, port: int, *args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
        answer = rounds[min(len(calls), len(rounds) - 1)]
        calls.append(host)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, port)) for a in answer]

    resolver.calls = calls  # type: ignore[attr-defined]
    return resolver


def _detail(exc: pytest.ExceptionInfo[BaseException]) -> str:
    return str(exc.value)


# ── D1: every answer classified against the declared class ────────────────────


def test_net01_hosted_name_resolving_to_a_private_address_is_refused() -> None:
    with pytest.raises(ProviderDialRefusedError) as exc:
        resolve_for_dial("models.example.com", 443, "remote_hosted", resolver=_answers("10.0.0.5"))
    assert _detail(exc) == "model_dial_refused:non_public_address"


@pytest.mark.parametrize("answer", ["127.0.0.1", "::1", "::ffff:127.0.0.1", "100.64.1.2"])
def test_net02_hosted_name_resolving_to_loopback_or_shared_space_is_refused(answer: str) -> None:
    with pytest.raises(ProviderDialRefusedError, match="non_public_address"):
        resolve_for_dial("models.example.com", 443, "remote_hosted", resolver=_answers(answer))


def test_net04_metadata_literal_is_refused_for_every_class() -> None:
    for kind in ("remote_hosted", "private_network", "local_machine"):
        for literal in ("169.254.169.254", "fd00:ec2::254", "100.100.100.200"):
            with pytest.raises(ProviderDialRefusedError, match="metadata_address"):
                resolve_for_dial(literal, 80, kind, allow_link_local=True)
    # …and by a saved URL, before anything is resolved: on the provider card.
    with pytest.raises(ProviderDialRefusedError, match="metadata_address"):
        refuse_metadata_destination("http://169.254.169.254/latest")
    with pytest.raises(ProviderDialRefusedError, match="metadata_address"):
        refuse_metadata_destination("http://[::ffff:169.254.169.254]/")


def test_net05_metadata_names_are_refused_and_so_is_a_name_resolving_to_one() -> None:
    for name in ("metadata.google.internal", "metadata.azure.com"):
        with pytest.raises(ProviderDialRefusedError, match="metadata_address"):
            refuse_metadata_destination(f"http://{name}/computeMetadata/v1")
        with pytest.raises(ProviderDialRefusedError, match="metadata_address"):
            resolve_for_dial(name, 80, "private_network", resolver=_answers("10.0.0.9"))
    with pytest.raises(ProviderDialRefusedError, match="metadata_address"):
        resolve_for_dial(
            "gpu.lan", 80, "private_network", allow_link_local=True,
            resolver=_answers("169.254.169.254"),
        )


@pytest.mark.parametrize("answer", ["192.168.1.20", "10.1.2.3", "fd12:3456::7", "100.101.102.103"])
def test_net06_private_name_resolving_to_a_private_address_is_allowed(answer: str) -> None:
    assert resolve_for_dial("gpu-box", 8000, "private_network", resolver=_answers(answer)) == [
        str(ipaddress.ip_address(answer))
    ]


def test_net07_private_name_resolving_to_a_public_address_is_refused() -> None:
    with pytest.raises(ProviderDialRefusedError) as exc:
        resolve_for_dial("gpu.lan", 8000, "private_network", resolver=_answers("93.184.216.34"))
    assert _detail(exc) == "model_dial_refused:public_address_for_private"
    with pytest.raises(ProviderDialRefusedError, match="loopback_for_private"):
        resolve_for_dial("gpu.lan", 8000, "private_network", resolver=_answers("127.0.1.1"))


def test_link_local_needs_the_owners_per_connection_opt_in() -> None:
    with pytest.raises(ProviderDialRefusedError, match="link_local_address"):
        resolve_for_dial("169.254.10.10", 8000, "private_network")
    assert resolve_for_dial("169.254.10.10", 8000, "private_network", allow_link_local=True) == [
        "169.254.10.10"
    ]
    # The opt-in is never one for a hosted connection.
    with pytest.raises(ProviderDialRefusedError, match="non_public_address"):
        resolve_for_dial("x.example.com", 443, "remote_hosted", allow_link_local=True,
                         resolver=_answers("169.254.10.10"))


def test_net12_mixed_public_and_ula_answers_refuse_the_whole_dial() -> None:
    with pytest.raises(ProviderDialRefusedError, match="non_public_address"):
        resolve_for_dial(
            "models.example.com", 443, "remote_hosted",
            resolver=_answers("2606:4700::6810:84e5", "fd00::5"),
        )
    # All public is allowed, in the resolver's order, without duplicates.
    assert resolve_for_dial(
        "models.example.com", 443, "remote_hosted",
        resolver=_answers("2606:4700::6810:84e5", "93.184.216.34", "93.184.216.34"),
    ) == ["2606:4700::6810:84e5", "93.184.216.34"]


def test_an_unresolvable_name_is_a_connection_failure_not_a_policy_answer() -> None:
    def fails(*_args: Any, **_kwargs: Any) -> list[tuple[Any, ...]]:
        raise socket.gaierror("no such name")

    with pytest.raises(httpcore.ConnectError):
        resolve_for_dial("nowhere.example.com", 443, "remote_hosted", resolver=fails)


def test_a_local_profile_only_dials_loopback() -> None:
    assert resolve_for_dial("localhost", 11434, "local_machine", resolver=_answers("::1", "127.0.0.1")) == [
        "::1", "127.0.0.1",
    ]
    with pytest.raises(ProviderDialRefusedError, match="non_loopback_for_local"):
        resolve_for_dial("x.localhost", 11434, "local_machine", resolver=_answers("192.168.0.4"))


# ── D2: the backend dials the address that passed, once per connection ───────


class _RecordingBackend(httpcore.AsyncNetworkBackend):
    """Records what was dialled and refuses to dial anything for real."""

    def __init__(self, fail: set[str] | None = None) -> None:
        self.dialled: list[str] = []
        self.fail = fail or set()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> httpcore.AsyncNetworkStream:
        self.dialled.append(host)
        raise httpcore.ConnectError(f"recorded:{host}")

    async def sleep(self, seconds: float) -> None:
        return None


def test_net03_a_rebinding_answer_cannot_move_the_dialled_address() -> None:
    resolver = _sequence(("93.184.216.34",), ("127.0.0.1",))
    inner = _RecordingBackend()
    backend = GuardedNetworkBackend("remote_hosted", resolver=resolver, inner=inner)

    async def body() -> None:
        with pytest.raises(httpcore.ConnectError):
            await backend.connect_tcp("models.example.com", 443)
        # The address that passed is the one dialled; the name never is.
        assert inner.dialled == ["93.184.216.34"]
        assert resolver.calls == ["models.example.com"]
        # A *new* connection resolves again, and the rebound answer refuses it.
        with pytest.raises(ProviderDialRefusedError, match="non_public_address"):
            await backend.connect_tcp("models.example.com", 443)
        assert inner.dialled == ["93.184.216.34"]

    asyncio.run(body())


def test_answers_are_tried_in_order_and_only_among_those_that_passed() -> None:
    inner = _RecordingBackend()
    backend = GuardedNetworkBackend(
        "remote_hosted",
        resolver=_answers("2606:4700::6810:84e5", "93.184.216.34"),
        inner=inner,
    )

    async def body() -> None:
        with pytest.raises(httpcore.ConnectError):
            await backend.connect_tcp("models.example.com", 443)

    asyncio.run(body())
    assert inner.dialled == ["2606:4700::6810:84e5", "93.184.216.34"]


@pytest.fixture
def loopback_server() -> Iterator[dict[str, Any]]:
    """A real HTTP server on 127.0.0.1 that records each request's Host header."""
    seen: dict[str, Any] = {"hosts": [], "connections": set()}

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:  # noqa: N802 - http.server API
            seen["hosts"].append(self.headers.get("Host"))
            seen["connections"].add(self.client_address)
            body = b'{"data": []}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: Any) -> None:
            return None

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    seen["port"] = server.server_address[1]
    try:
        yield seen
    finally:
        server.shutdown()
        server.server_close()


def test_the_pinned_dial_keeps_the_name_on_the_request(loopback_server: dict[str, Any]) -> None:
    """A real socket: the address dialled is the resolved one, Host stays the name."""
    port = loopback_server["port"]
    resolver = _answers("127.0.0.1")
    transport = ModelTransport(
        f"http://models.localhost:{port}", declared_kind="local_machine", resolver=resolver
    )

    async def body() -> None:
        async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
            first = await client.get(f"http://models.localhost:{port}/v1/models")
            second = await client.get(f"http://models.localhost:{port}/v1/models")
        assert first.status_code == second.status_code == 200

    asyncio.run(body())
    assert loopback_server["hosts"] == [f"models.localhost:{port}"] * 2
    # Acceptance criterion 6 — a kept-alive connection pays for no second lookup.
    assert resolver.calls == ["models.localhost"]
    assert len(loopback_server["connections"]) == 1


def test_net08_loopback_never_uses_a_proxy_even_when_one_is_set(
    monkeypatch: pytest.MonkeyPatch, loopback_server: dict[str, Any]
) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    port = loopback_server["port"]
    pool = ProviderClientPool()

    async def body() -> None:
        client = pool.client(endpoint=f"http://127.0.0.1:{port}/v1", timeout=5.0)
        assert client._transport.proxy is None  # type: ignore[attr-defined]
        response = await client.get(f"http://127.0.0.1:{port}/v1/models")
        assert response.status_code == 200
        await pool.aclose()

    asyncio.run(body())


def test_a_private_network_origin_bypasses_the_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example:3128")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:3128")
    assert proxy_for("http://192.168.1.20:8000/v1", "private_network") is None
    assert proxy_for("http://gpu-box:8000/v1", "private_network") is None
    assert proxy_for("https://api.example.com/v1", "remote_hosted") == "http://proxy.example:3128"
    monkeypatch.setenv("NO_PROXY", "api.example.com")
    assert proxy_for("https://api.example.com/v1", "remote_hosted") is None


def test_the_models_page_names_the_proxy_without_its_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://user:secret@proxy.example:3128")
    assert proxy_route("https://api.example.com/v1", "remote_hosted") == "proxy.example:3128"
    assert proxy_route("http://127.0.0.1:11434/v1", "local_machine") == ""


@pytest.fixture
def connect_proxy() -> Iterator[dict[str, Any]]:
    """A proxy that records the CONNECT line it was asked for, then hangs up."""
    seen: dict[str, Any] = {"lines": []}
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(4)
    listener.settimeout(5)

    def serve() -> None:
        try:
            conn, _ = listener.accept()
        except OSError:
            return
        with conn:
            data = conn.recv(4096)
            seen["lines"].append(data.split(b"\r\n", 1)[0].decode("latin-1"))
            conn.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    seen["port"] = listener.getsockname()[1]
    try:
        yield seen
    finally:
        listener.close()
        thread.join(timeout=5)


def test_net09_hosted_https_goes_through_the_owners_proxy(
    monkeypatch: pytest.MonkeyPatch, connect_proxy: dict[str, Any]
) -> None:
    monkeypatch.setenv("HTTPS_PROXY", f"http://127.0.0.1:{connect_proxy['port']}")
    pool = ProviderClientPool()

    async def body() -> None:
        client = pool.client(endpoint="https://api.example.com/v1", timeout=5.0)
        with pytest.raises(httpx.ProxyError):
            await client.get(
                "https://api.example.com/v1/models", headers={"Authorization": "Bearer sk"}
            )
        await pool.aclose()

    asyncio.run(body())
    # The proxy was asked for a tunnel to the connection's own origin; the key
    # travels inside the TLS tunnel it would have opened, never in this line.
    assert connect_proxy["lines"] == ["CONNECT api.example.com:443 HTTP/1.1"]


def test_net10_a_keyed_plain_http_request_through_a_proxy_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    hosted = ModelTransport("http://api.example.com", declared_kind="remote_hosted")
    assert hosted.proxy == "http://127.0.0.1:9"

    async def body() -> None:
        async with httpx.AsyncClient(transport=hosted, trust_env=False) as client:
            with pytest.raises(ProviderDialRefusedError, match="credential_over_http_proxy"):
                await client.get("http://api.example.com/v1/models", headers={"Authorization": "Bearer sk"})

    asyncio.run(body())
    # A keyed http:// *private* endpoint is never handed to the proxy at all.
    assert ModelTransport("http://192.168.1.20:8000", declared_kind="private_network").proxy is None


# ── D5: TLS and credential origin ─────────────────────────────────────────────


def _issue_certificate(directory: Path, name: str) -> tuple[Path, Path, Path]:
    """A CA, and a leaf certificate it signed for *name* only."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    now = datetime.datetime.now(datetime.UTC)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Raiker test CA")])
    ca = (
        x509.CertificateBuilder()
        .subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    leaf_key = ec.generate_private_key(ec.SECP256R1())
    leaf = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
        .issuer_name(ca_name).public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(name)]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    ca_path, cert_path, key_path = directory / "ca.pem", directory / "leaf.pem", directory / "leaf.key"
    ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    cert_path.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        leaf_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return ca_path, cert_path, key_path


def test_net11_a_certificate_for_another_name_is_refused_before_headers_are_sent(
    tmp_path: Path,
) -> None:
    ca_path, cert_path, key_path = _issue_certificate(tmp_path, "other.localhost")
    server_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    server_context.load_cert_chain(cert_path, key_path)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(2)
    listener.settimeout(5)
    port = listener.getsockname()[1]
    received: list[bytes] = []

    def serve() -> None:
        try:
            raw, _ = listener.accept()
        except OSError:
            return
        try:
            with server_context.wrap_socket(raw, server_side=True) as tls:
                received.append(tls.recv(4096))
        except (ssl.SSLError, OSError):
            return

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    client_context = ssl.create_default_context(cafile=str(ca_path))
    transport = ModelTransport(
        f"https://models.localhost:{port}",
        declared_kind="local_machine",
        resolver=_answers("127.0.0.1"),
        ssl_context=client_context,
    )

    async def body() -> None:
        async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
            with pytest.raises(httpx.ConnectError):
                await client.get(
                    f"https://models.localhost:{port}/v1/models",
                    headers={"Authorization": "Bearer sk-secret"},
                )

    try:
        asyncio.run(body())
    finally:
        thread.join(timeout=5)
        listener.close()
    # The handshake failed on the name, so not one request byte — and no key —
    # reached the server.
    assert not any(received)


def test_a_credential_is_only_attached_to_the_clients_own_origin() -> None:
    transport = ModelTransport("https://api.example.com", declared_kind="remote_hosted")

    async def body() -> None:
        async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
            with pytest.raises(ProviderPolicyError, match="model_credential_origin_mismatch"):
                await client.get("https://evil.example.net/v1", headers={"x-api-key": "sk"})

    asyncio.run(body())


def test_the_pool_replacement_is_pinned_to_the_locked_httpx() -> None:
    """D2 risk — httpx exposes no backend hook; an upgrade that renames `_pool` fails here."""
    transport = ModelTransport("https://api.example.com", declared_kind="remote_hosted")
    pool = transport._inner._pool  # noqa: SLF001
    assert isinstance(pool, httpcore.AsyncConnectionPool)
    assert isinstance(pool._network_backend, GuardedNetworkBackend)  # noqa: SLF001
    assert pool._network_backend.declared_kind == "remote_hosted"  # noqa: SLF001


def test_the_pool_keys_clients_by_dial_rule() -> None:
    pool = ProviderClientPool()

    async def body() -> None:
        plain = pool.client(endpoint="http://169.254.10.10:8000", timeout=5.0)
        opted = pool.client(endpoint="http://169.254.10.10:8000", timeout=5.0, allow_link_local=True)
        assert plain is not opted
        hosted = pool.client(endpoint="https://openrouter.ai/api/v1", timeout=5.0, endpoint_kind="remote_hosted")
        assert hosted._transport.declared_kind == "remote_hosted"  # type: ignore[attr-defined]
        await pool.aclose()

    asyncio.run(body())


# ── The refusal reaches the owner as a policy answer ──────────────────────────


def test_a_saved_metadata_endpoint_is_refused_on_the_card() -> None:
    profile = profile_with_model(
        ModelProfileRegistry.load().resolve_profile_id("generic-openai-compatible"), "m"
    )
    factory = ModelProviderFactory(
        policy=OPEN, connection={"endpoint": "http://169.254.169.254/v1"}
    )
    with pytest.raises(ProviderDialRefusedError, match="model_dial_refused:metadata_address"):
        factory.resolve(profile)


def test_a_dial_refusal_keeps_its_own_code_and_sentence() -> None:
    exc = ProviderDialRefusedError("model_dial_refused:non_public_address")
    assert isinstance(exc, ProviderPolicyError)
    assert provider_error_code(exc) == "model_dial_refused:non_public_address"
    message = provider_failure_message("model_dial_refused:non_public_address")
    assert "private" in message and "not a network fault" in message
    assert "model_unavailable: model_dial_refused:non_public_address" in message


def test_router_turn_refusal_happens_before_any_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    """A hosted connection whose name resolves privately: refused, nothing dialled."""
    dialled: list[str] = []
    real = httpcore.AnyIOBackend.connect_tcp

    async def spy(self: Any, host: str, port: int, **kwargs: Any) -> Any:
        dialled.append(host)
        return await real(self, host, port, **kwargs)

    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", spy)
    monkeypatch.setattr(
        "raiker.models.transport_guard.socket.getaddrinfo", _answers("10.0.0.5")
    )
    pool = ProviderClientPool()

    async def body() -> None:
        client = pool.client(endpoint="https://models.example.com", timeout=5.0)
        with pytest.raises(ProviderDialRefusedError, match="non_public_address"):
            await client.get("https://models.example.com/v1/models", headers={"Authorization": "Bearer sk"})
        await pool.aclose()

    asyncio.run(body())
    assert dialled == []


# ── D2, urllib half: the image helpers ───────────────────────────────────────


def test_image_helper_refuses_a_hosted_name_that_resolves_privately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("raiker.models.transport_guard.socket.getaddrinfo", _answers("127.0.0.1"))
    with pytest.raises(SandboxError, match="model_dial_refused:non_public_address"):
        post_json(
            "https://api.openai.com/v1/images/generations",
            {"prompt": "x"},
            egress_allowlist=frozenset({"api.openai.com"}),
            headers={"Authorization": "Bearer sk"},
            dial_kind="remote_hosted",
        )


def test_image_helper_dials_the_address_that_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("raiker.models.transport_guard.socket.getaddrinfo", _answers("93.184.216.34"))
    pinned: list[tuple[str, str, bool]] = []

    class _Opener:
        def add_handler(self, _handler: Any) -> None:
            return None

        def open(self, _request: Any, timeout: float) -> Any:
            raise OSError("stop before the network")

    def fake_pinned(host: str, address: str, *, direct: bool = False) -> Any:
        pinned.append((host, address, direct))
        return _Opener()

    monkeypatch.setattr("raiker.runtime.web_policy.pinned_https_opener", fake_pinned)
    with pytest.raises(SandboxError, match="fetch_failed"):
        post_json(
            "https://api.openai.com/v1/images/generations",
            {"prompt": "x"},
            egress_allowlist=frozenset({"api.openai.com"}),
            dial_kind="remote_hosted",
        )
    assert pinned == [("api.openai.com", "93.184.216.34", True)]


def test_image_helper_through_a_proxy_is_not_pinned(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    called: list[str] = []

    def fake_open(request: urllib.request.Request, timeout: float) -> Any:
        called.append(request.full_url)
        raise OSError("stop")

    monkeypatch.setattr(sandbox, "_open_without_redirects", fake_open)
    with pytest.raises(SandboxError, match="fetch_failed"):
        post_json(
            "https://api.openai.com/v1/images/generations",
            {"prompt": "x"},
            egress_allowlist=frozenset({"api.openai.com"}),
            dial_kind="remote_hosted",
        )
    assert called == ["https://api.openai.com/v1/images/generations"]
