from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from raiker.models.huggingface import HubGatedError, HuggingFaceAccessError, HuggingFaceService

REVISION = "a" * 40


class FakeHub:
    def __init__(self, *, gated: bool = False) -> None:
        self.gated = gated
        self.download_calls: list[dict[str, object]] = []

    def search(self, query: str, *, limit: int, token: str | None):
        assert limit <= 50
        return [SimpleNamespace(id="owner/repo", downloads=12, likes=3, gated=self.gated)]

    def model_info(self, repo_id: str, *, revision: str | None, token: str | None):
        assert repo_id == "owner/repo"
        if self.gated:
            raise HubGatedError(f"access denied for token {token}")
        return SimpleNamespace(
            id=repo_id,
            sha=REVISION,
            gated=self.gated,
            card_data={"license": "apache-2.0"},
            siblings=[
                SimpleNamespace(rfilename="README.md", size=100),
                SimpleNamespace(rfilename="model-Q8_0.gguf", size=800),
                SimpleNamespace(rfilename="model-Q4_K_M-00001-of-00002.gguf", size=200),
                SimpleNamespace(rfilename="model-Q4_K_M-00002-of-00002.gguf", size=300),
                SimpleNamespace(rfilename="broken-Q5_K_M-00001-of-00002.gguf", size=250),
            ],
        )

    def snapshot_download(self, **kwargs: object):
        self.download_calls.append(kwargs)
        if kwargs.get("dry_run"):
            return [
                SimpleNamespace(
                    filename="model-Q4_K_M-00001-of-00002.gguf", file_size=200, is_cached=True
                ),
                SimpleNamespace(
                    filename="model-Q4_K_M-00002-of-00002.gguf", file_size=300, is_cached=False
                ),
            ]
        return str(kwargs["local_dir"])


def test_complete_gguf_is_preferred_and_revision_is_pinned(tmp_path: Path) -> None:
    service = HuggingFaceService(FakeHub(), cache_dir=tmp_path / "hf")

    variants = service.variants("owner/repo", revision="main")

    assert variants[0].format == "gguf"
    assert variants[0].complete is True
    assert variants[0].revision == REVISION
    assert variants[0].quantization == "Q4_K_M"
    assert variants[0].files == (
        "model-Q4_K_M-00001-of-00002.gguf",
        "model-Q4_K_M-00002-of-00002.gguf",
    )
    assert variants[-1].complete is False


def test_dry_run_reports_cache_reuse_and_uses_exact_files(tmp_path: Path) -> None:
    hub = FakeHub()
    service = HuggingFaceService(hub, cache_dir=tmp_path / "hf")
    variant = service.variants("owner/repo", revision=REVISION)[0]

    preview = service.dry_run("owner/repo", variant, token="hf_private")

    assert preview.total_bytes == 500
    assert preview.cached_bytes == 200
    assert preview.download_bytes == 300
    assert hub.download_calls[0]["revision"] == REVISION
    assert hub.download_calls[0]["allow_patterns"] == list(variant.files)
    assert hub.download_calls[0]["dry_run"] is True


def test_gated_repository_returns_stable_link_without_secret(tmp_path: Path) -> None:
    service = HuggingFaceService(FakeHub(gated=True), cache_dir=tmp_path / "hf")

    with pytest.raises(HuggingFaceAccessError) as raised:
        service.variants("owner/repo", token="hf_private")

    assert raised.value.code == "gated_access_required"
    assert raised.value.repository_url == "https://huggingface.co/owner/repo"
    assert "hf_private" not in repr(raised.value)


def test_download_refuses_unpinned_or_incomplete_selection(tmp_path: Path) -> None:
    service = HuggingFaceService(FakeHub(), cache_dir=tmp_path / "hf")
    variants = service.variants("owner/repo")

    with pytest.raises(ValueError, match="incomplete_hugging_face_variant"):
        service.dry_run("owner/repo", variants[-1])
