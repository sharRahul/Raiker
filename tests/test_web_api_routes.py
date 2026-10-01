"""Every path the web client calls is a route the backend serves (OPT-02).

The client's endpoint catalogue (``web/src/lib/api.ts`` and ``web/src/lib/api/``)
is hand-written, so a backend route renamed or removed left a wrapper that
compiled, shipped, and answered 404 the first time an owner reached it. The
backend's OpenAPI document is the list of what it serves; this holds the
catalogue to it. Methods are not compared — a wrapper's verb is usually in an
options object, and a path that exists under the wrong verb answers 405, which
the route's own tests catch.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from raiker.api.app import create_app

WEB_LIB = Path(__file__).resolve().parents[1] / "web" / "src" / "lib"
CLIENT_FILES = [WEB_LIB / "api.ts", *sorted((WEB_LIB / "api").glob("*.ts"))]

_LITERAL = re.compile(r"""(["'`])((?:(?!\1).)*)\1""", re.S)
# A `//` comment, not the `//` inside a URL literal: it follows whitespace.
_LINE_COMMENT = re.compile(r"(^|\s)//[^\n]*", re.M)


def _literal_text(quote: str, body: str) -> str:
    # A template's `${…}` is one path segment's worth of something.
    return re.sub(r"\$\{[^}]*\}", "{}", body) if quote == "`" else body


def client_paths(source: str) -> set[str]:
    """Every ``/api/…`` path the source builds, with ``{}`` for each variable part.

    Follows ``+`` concatenation, because a long path is split across lines:
    ``"/api/x/" + id`` is ``/api/x/{}``. The query string is not part of the path.
    """
    # Comments first: an apostrophe in prose would pair with a real quote.
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    source = _LINE_COMMENT.sub(r"\1", source)
    found: set[str] = set()
    for match in _LITERAL.finditer(source):
        quote, body = match.group(1), match.group(2)
        if not body.startswith("/api/"):
            continue
        path = _literal_text(quote, body)
        position = match.end()
        while True:
            rest = source[position:]
            plus = re.match(r"\s*\+\s*", rest)
            if not plus:
                break
            position += plus.end()
            following = _LITERAL.match(source, position)
            if following is None:
                path += "{}"
                break
            path += _literal_text(following.group(1), following.group(2))
            position = following.end()
        found.add(path.split("?", 1)[0])
    return found


def _segments(path: str) -> list[str]:
    return path.strip("/").split("/")


def _matches(client: str, backend: str) -> bool:
    ours, theirs = _segments(client), _segments(backend)
    if len(ours) != len(theirs):
        return False
    return all(
        "{}" in mine or (theirs_part.startswith("{") and theirs_part.endswith("}"))
        or mine == theirs_part
        for mine, theirs_part in zip(ours, theirs, strict=True)
    )


@pytest.fixture(scope="module")
def backend_paths(tmp_path_factory: pytest.TempPathFactory) -> list[str]:
    app = create_app(tmp_path_factory.mktemp("routes"))
    return list(app.openapi()["paths"])


def test_every_client_path_is_a_backend_route(backend_paths: list[str]) -> None:
    called = set().union(*(client_paths(f.read_text(encoding="utf-8")) for f in CLIENT_FILES))
    assert len(called) > 200, "the parser found almost nothing; it is broken, not the client"
    missing = sorted(
        path for path in called if not any(_matches(path, route) for route in backend_paths)
    )
    assert not missing, "the web client calls paths the backend does not serve:\n" + "\n".join(
        missing
    )


def test_concatenation_and_templates_are_followed() -> None:
    source = (
        "request(`/api/a/${id}/` +\n `${b}/c`);\n"
        'postJson("/api/x/" + encodeURIComponent(name), {});\n'
        'request("/api/q?x=1");\n'
    )
    assert client_paths(source) == {"/api/a/{}/{}/c", "/api/x/{}", "/api/q"}


def test_a_variable_segment_matches_a_literal_route_segment() -> None:
    assert _matches("/api/capability-modes/{}/{}", "/api/capability-modes/{capability}/ask")
    assert not _matches("/api/capability-modes/{}", "/api/capability-modes/{capability}/ask")
    assert not _matches("/api/models", "/api/model-setup")
