"""The multipart POST is the same boundary as the JSON one, differently encoded.

`post_multipart` exists because OpenAI's `/v1/images/edits` takes the image as a
file part rather than as base64 in a JSON body — without it, BUG-277's "edit
this generation" could never reach that provider.

A new way to send bytes off the machine is exactly the kind of change that
quietly widens an egress surface, so what is held here is that it does not. Every
check `post_json` makes is made here, in the same order, with the same reason
code — the scheme, the absent allowlist, and the host — and the two extra checks
are about the encoding rather than the destination.
"""

from __future__ import annotations

import pytest

from raiker.runtime.executors.sandbox import SandboxError, post_json, post_multipart

FIELDS = {"model": "gpt-image-1", "prompt": "a cat"}
FILES = {"image": ("source.png", "image/png", b"\x89PNG\r\n\x1a\n")}


def _refuse(*args: object, **kwargs: object) -> dict:
    raise AssertionError("a refused request must not reach the network")


# ── The same refusals, in the same order, as post_json ───────────────────────


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://host/x", "not-a-url", "https://"])
def test_only_http_and_https_are_addressable(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("urllib.request.urlopen", _refuse)

    with pytest.raises(SandboxError) as caught:
        post_multipart(url, FIELDS, FILES, egress_allowlist=frozenset({"*"}))

    assert str(caught.value).startswith("invalid_url:")


def test_an_absent_allowlist_denies_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail closed: an empty allowlist is not "no restriction"."""
    monkeypatch.setattr("urllib.request.urlopen", _refuse)

    allowlists: list[frozenset[str] | None] = [None, frozenset()]
    for allowlist in allowlists:
        with pytest.raises(SandboxError) as caught:
            post_multipart(
                "https://api.openai.com/v1/images/edits",
                FIELDS,
                FILES,
                egress_allowlist=allowlist,
            )
        assert str(caught.value) == "egress_denied:no_allowlist"


def test_a_host_outside_the_allowlist_is_refused_by_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("urllib.request.urlopen", _refuse)

    with pytest.raises(SandboxError) as caught:
        post_multipart(
            "https://evil.example/v1/images/edits",
            FIELDS,
            FILES,
            egress_allowlist=frozenset({"api.openai.com"}),
        )

    assert str(caught.value) == "egress_denied:evil.example"


def test_it_refuses_exactly_where_post_json_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    """The point of the whole file, stated against the function it mirrors.

    If these two ever disagree, one of them has a way out the other does not.
    """
    monkeypatch.setattr("urllib.request.urlopen", _refuse)
    cases = [
        ("file:///etc/passwd", frozenset({"*"})),
        ("https://api.openai.com/x", None),
        ("https://evil.example/x", frozenset({"api.openai.com"})),
    ]

    for url, allowlist in cases:
        with pytest.raises(SandboxError) as json_error:
            post_json(url, {"a": 1}, egress_allowlist=allowlist)
        with pytest.raises(SandboxError) as multipart_error:
            post_multipart(url, FIELDS, FILES, egress_allowlist=allowlist)
        assert str(json_error.value) == str(multipart_error.value)


# ── The two checks that are about the encoding ───────────────────────────────


def _captured_send(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Let the real function build a body, and hand back what it would have sent."""
    captured: dict[str, object] = {}

    class _Response:
        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, size: int) -> bytes:
            return b"{}"

    def capture(request: object, timeout: float = 0) -> _Response:
        captured["content_type"] = request.get_header("Content-type")  # type: ignore[attr-defined]
        captured["body"] = request.data  # type: ignore[attr-defined]
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", capture)
    return captured


def test_the_body_is_a_well_formed_multipart_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _captured_send(monkeypatch)

    post_multipart(
        "https://api.openai.com/v1/images/edits",
        FIELDS,
        FILES,
        egress_allowlist=frozenset({"api.openai.com"}),
    )

    content_type = str(captured["content_type"])
    assert content_type.startswith("multipart/form-data; boundary=----raiker")
    boundary = content_type.split("boundary=", 1)[1]
    body = captured["body"]
    assert isinstance(body, bytes)
    assert b'name="model"' in body and b"gpt-image-1" in body
    # The file part keeps its filename and type, and the bytes are verbatim.
    assert b'filename="source.png"' in body and b"Content-Type: image/png" in body
    assert FILES["image"][2] in body
    assert body.endswith(f"--{boundary}--\r\n".encode())


def test_a_part_carrying_the_boundary_is_refused_rather_than_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A part containing the boundary would terminate the body early.

    Unpredictable boundaries make this practically unreachable — which is why
    the boundary is pinned here rather than guessed. A guard that cannot be
    reached from outside is still a guard, and an untested one is a comment.
    """
    monkeypatch.setattr("urllib.request.urlopen", _refuse)
    monkeypatch.setattr("secrets.token_hex", lambda n=16: "deadbeef")
    boundary = "----raikerdeadbeef"

    with pytest.raises(SandboxError) as field_error:
        post_multipart(
            "https://api.openai.com/v1/images/edits",
            {**FIELDS, "prompt": f"x{boundary}x"},
            FILES,
            egress_allowlist=frozenset({"api.openai.com"}),
        )
    assert str(field_error.value) == "multipart_boundary_in_field"

    with pytest.raises(SandboxError) as file_error:
        post_multipart(
            "https://api.openai.com/v1/images/edits",
            FIELDS,
            {"image": ("x.png", "image/png", boundary.encode() + b"rest")},
            egress_allowlist=frozenset({"api.openai.com"}),
        )
    assert str(file_error.value) == "multipart_boundary_in_file"


def test_the_boundary_is_unpredictable_between_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A counter would let one request's body be shaped against the next one's."""
    seen: list[str] = []

    class _Response:
        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, size: int) -> bytes:
            return b"{}"

    def capture(request: object, timeout: float = 0) -> _Response:
        seen.append(str(request.get_header("Content-type")))  # type: ignore[attr-defined]
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", capture)
    for _ in range(3):
        post_multipart(
            "https://api.openai.com/v1/images/edits",
            FIELDS,
            FILES,
            egress_allowlist=frozenset({"api.openai.com"}),
        )

    assert len(set(seen)) == 3


def test_a_non_json_reply_is_a_named_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Response:
        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, size: int) -> bytes:
            return b"<html>not json</html>"

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Response())

    with pytest.raises(SandboxError) as caught:
        post_multipart(
            "https://api.openai.com/v1/images/edits",
            FIELDS,
            FILES,
            egress_allowlist=frozenset({"api.openai.com"}),
        )

    assert str(caught.value) == "response_not_json"


# ── The wire format, against a real server ───────────────────────────────────


def test_a_real_http_server_parses_the_body_and_gets_the_bytes_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one thing a mocked `urlopen` cannot prove.

    Every test above asserts what `post_multipart` *builds*. This one hands the
    body to a real HTTP server over a real socket and has Python's own multipart
    parser read it back, because a body that this file agrees with itself about
    is not the same as a body a provider can parse. A missing CRLF, a
    mis-encoded header or a boundary off by one byte passes every assertion
    above and fails at OpenAI.
    """
    import email
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    received: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's name
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            # Parse it the way a server does: the headers plus the body, read
            # back as a MIME multipart document.
            parsed = email.message_from_bytes(
                f"Content-Type: {self.headers['Content-Type']}\r\n\r\n".encode() + raw
            )
            parts = {}
            for part in parsed.walk():
                if not isinstance(part, email.message.Message):
                    continue
                disposition = str(part.get("Content-Disposition", ""))
                if 'name="' not in disposition:
                    continue
                name = disposition.split('name="', 1)[1].split('"', 1)[0]
                parts[name] = part.get_payload(decode=True)
            received["parts"] = parts
            received["is_multipart"] = parsed.is_multipart()
            body = b'{"ok": true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            return None

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    host = f"127.0.0.1:{server.server_port}"

    try:
        answer = post_multipart(
            f"http://{host}/v1/images/edits",
            {"model": "gpt-image-1", "prompt": "make it blue", "n": "2"},
            {"image": ("source.png", "image/png", FILES["image"][2])},
            egress_allowlist=frozenset({host}),
        )
    finally:
        thread.join(timeout=5)
        server.server_close()

    assert answer == {"ok": True}
    assert received["is_multipart"] is True
    parts = received["parts"]
    assert isinstance(parts, dict)
    assert parts["model"] == b"gpt-image-1"
    assert parts["prompt"] == b"make it blue"
    assert parts["n"] == b"2"
    # The image survives byte for byte. This is what an edit is.
    assert parts["image"] == FILES["image"][2]
