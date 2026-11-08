"""A transient 5xx from GitHub's release CDN is retried; a 404 is not."""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
import pytest

from raiker.models.llama_cpp import installer
from raiker.models.llama_cpp.installer import InstallError, download_asset
from raiker.models.llama_cpp.releases import ReleaseAsset

BODY = b"llama archive bytes"
URL = "https://github.com/ggml-org/llama.cpp/releases/download/b1/llama.zip"
ASSET = ReleaseAsset("llama.zip", URL, len(BODY), "sha256:" + hashlib.sha256(BODY).hexdigest())


def _client(statuses: list[int]) -> tuple[httpx.Client, list[int]]:
    seen: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        status = statuses[min(len(seen), len(statuses) - 1)]
        seen.append(status)
        return httpx.Response(status, content=BODY if status == 200 else b"", request=request)

    return httpx.Client(transport=httpx.MockTransport(handler)), seen


@pytest.fixture(autouse=True)
def no_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer.time, "sleep", lambda _seconds: None)


def test_a_504_then_success_downloads_and_verifies(tmp_path: Path) -> None:
    client, seen = _client([504, 503, 200])
    path = download_asset(ASSET, tmp_path / "llama.zip", client=client)
    assert path.read_bytes() == BODY
    assert seen == [504, 503, 200]


def test_a_404_is_not_retried(tmp_path: Path) -> None:
    client, seen = _client([404])
    with pytest.raises(InstallError, match="llama_cpp_download_failed"):
        download_asset(ASSET, tmp_path / "llama.zip", client=client)
    assert seen == [404]


def test_a_persistent_504_fails_after_the_allowed_attempts(tmp_path: Path) -> None:
    client, seen = _client([504])
    with pytest.raises(InstallError, match="llama_cpp_download_failed"):
        download_asset(ASSET, tmp_path / "llama.zip", client=client)
    assert len(seen) == installer.DOWNLOAD_ATTEMPTS
