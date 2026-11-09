# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
import pytest

from scripts.package_voice_sources import download_source


@pytest.mark.parametrize("fault", ["digest", "truncated", "oversized", "network"])
def test_bad_voice_sources_never_become_published_files(tmp_path: Path, fault: str) -> None:
    body = b"source archive"
    record = {"name": "source.tar.gz", "url": "https://example.test/source", "size": len(body),
              "sha256": hashlib.sha256(body).hexdigest()}

    def response(request: httpx.Request) -> httpx.Response:
        if fault == "network":
            raise httpx.ConnectError("offline", request=request)
        content = {"digest": b"wrong! archive", "truncated": body[:-1], "oversized": body + b"!"}[fault]
        return httpx.Response(200, content=content)

    with httpx.Client(transport=httpx.MockTransport(response)) as client, pytest.raises((ValueError, httpx.HTTPError)):
        download_source(record, tmp_path, client)
    assert list(tmp_path.iterdir()) == []


def test_matching_voice_source_is_published_after_verification(tmp_path: Path) -> None:
    body = b"source archive"
    record = {"name": "source.tar.gz", "url": "https://example.test/source", "size": len(body),
              "sha256": hashlib.sha256(body).hexdigest()}
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body))) as client:
        path = download_source(record, tmp_path, client)
    assert path.read_bytes() == body
    assert not list(tmp_path.glob("*.partial"))
