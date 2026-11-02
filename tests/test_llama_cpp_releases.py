"""Choosing the official llama.cpp asset for each platform and backend."""

from __future__ import annotations

import httpx
import pytest

from raiker.models.llama_cpp.releases import (
    Release,
    ReleaseAsset,
    ReleaseError,
    fetch_release,
    parse_release,
    select_assets,
)

TAG = "b7000"
DIGEST = "sha256:" + "a" * 64
NAMES = [
    f"llama-{TAG}-bin-macos-arm64.tar.gz",
    f"llama-{TAG}-bin-macos-x64.tar.gz",
    f"llama-{TAG}-bin-ubuntu-x64.tar.gz",
    f"llama-{TAG}-bin-ubuntu-arm64.tar.gz",
    f"llama-{TAG}-bin-ubuntu-vulkan-x64.tar.gz",
    f"llama-{TAG}-bin-ubuntu-vulkan-arm64.tar.gz",
    f"llama-{TAG}-bin-ubuntu-cuda-12.8-x64.tar.gz",
    f"cudart-llama-{TAG}-bin-ubuntu-cuda-12.8-x64.tar.gz",
    f"llama-{TAG}-bin-ubuntu-cuda-13.4-x64.tar.gz",
    f"cudart-llama-{TAG}-bin-ubuntu-cuda-13.4-x64.tar.gz",
    f"llama-{TAG}-bin-win-cpu-x64.zip",
    f"llama-{TAG}-bin-win-cpu-arm64.zip",
    f"llama-{TAG}-bin-win-vulkan-x64.zip",
    f"llama-{TAG}-bin-win-cuda-12.4-x64.zip",
    "cudart-llama-bin-win-cuda-12.4-x64.zip",
    f"llama-{TAG}-bin-win-cuda-13.4-x64.zip",
    "cudart-llama-bin-win-cuda-13.4-x64.zip",
    f"llama-{TAG}-bin-win-sycl-x64.zip",
    f"llama-{TAG}-bin-ubuntu-rocm-10.0-x64.tar.gz",
    f"llama-{TAG}-xcframework.zip",
]


def _release(names: list[str] = NAMES) -> Release:
    return Release(
        TAG,
        None,
        tuple(
            ReleaseAsset(name, f"https://github.com/ggml-org/llama.cpp/releases/download/{TAG}/{name}", 100, DIGEST)
            for name in names
        ),
    )


@pytest.mark.parametrize(
    ("os_name", "arch", "backend", "expected"),
    [
        ("macos", "arm64", "metal", f"llama-{TAG}-bin-macos-arm64.tar.gz"),
        ("macos", "arm64", "cpu", f"llama-{TAG}-bin-macos-arm64.tar.gz"),
        ("macos", "x64", "cpu", f"llama-{TAG}-bin-macos-x64.tar.gz"),
        ("linux", "x64", "cpu", f"llama-{TAG}-bin-ubuntu-x64.tar.gz"),
        ("linux", "arm64", "cpu", f"llama-{TAG}-bin-ubuntu-arm64.tar.gz"),
        ("linux", "x64", "vulkan", f"llama-{TAG}-bin-ubuntu-vulkan-x64.tar.gz"),
        ("linux", "arm64", "vulkan", f"llama-{TAG}-bin-ubuntu-vulkan-arm64.tar.gz"),
        ("windows", "x64", "cpu", f"llama-{TAG}-bin-win-cpu-x64.zip"),
        ("windows", "arm64", "cpu", f"llama-{TAG}-bin-win-cpu-arm64.zip"),
        ("windows", "x64", "vulkan", f"llama-{TAG}-bin-win-vulkan-x64.zip"),
    ],
)
def test_each_platform_gets_its_own_build(os_name: str, arch: str, backend: str, expected: str) -> None:
    selection = select_assets(_release(), os_name=os_name, arch=arch, backend=backend)
    assert selection.primary.name == expected
    assert selection.companions == ()


@pytest.mark.parametrize(
    ("os_name", "driver", "build", "runtime"),
    [
        ("linux", "13.4", f"llama-{TAG}-bin-ubuntu-cuda-13.4-x64.tar.gz", f"cudart-llama-{TAG}-bin-ubuntu-cuda-13.4-x64.tar.gz"),
        ("linux", "12.9", f"llama-{TAG}-bin-ubuntu-cuda-12.8-x64.tar.gz", f"cudart-llama-{TAG}-bin-ubuntu-cuda-12.8-x64.tar.gz"),
        # Minor-version compatibility: a 12.2 driver runs the 12.8 build.
        ("linux", "12.2", f"llama-{TAG}-bin-ubuntu-cuda-12.8-x64.tar.gz", f"cudart-llama-{TAG}-bin-ubuntu-cuda-12.8-x64.tar.gz"),
        ("windows", "12.6", f"llama-{TAG}-bin-win-cuda-12.4-x64.zip", "cudart-llama-bin-win-cuda-12.4-x64.zip"),
        ("windows", "13.5", f"llama-{TAG}-bin-win-cuda-13.4-x64.zip", "cudart-llama-bin-win-cuda-13.4-x64.zip"),
    ],
)
def test_cuda_picks_newest_build_the_driver_runs_and_its_runtime(
    os_name: str, driver: str, build: str, runtime: str
) -> None:
    selection = select_assets(
        _release(), os_name=os_name, arch="x64", backend="cuda", cuda_driver_version=driver
    )
    assert selection.primary.name == build
    assert [asset.name for asset in selection.companions] == [runtime]
    assert selection.download_bytes == 200


def test_cuda_driver_older_than_every_build_is_refused() -> None:
    with pytest.raises(ReleaseError, match="llama_cpp_cuda_driver_too_old"):
        select_assets(_release(), os_name="linux", arch="x64", backend="cuda", cuda_driver_version="11.8")


def test_metal_off_apple_and_cuda_on_a_mac_are_unsupported() -> None:
    with pytest.raises(ReleaseError, match="llama_cpp_backend_unsupported"):
        select_assets(_release(), os_name="linux", arch="x64", backend="metal")
    with pytest.raises(ReleaseError, match="llama_cpp_backend_unsupported"):
        select_assets(_release(), os_name="macos", arch="arm64", backend="cuda")
    with pytest.raises(ReleaseError, match="llama_cpp_backend_unsupported"):
        select_assets(_release(), os_name="macos", arch="x64", backend="metal")


def test_missing_asset_is_named() -> None:
    with pytest.raises(ReleaseError, match="llama_cpp_asset_missing"):
        select_assets(_release([]), os_name="linux", arch="x64", backend="cpu")


def test_legacy_zip_releases_still_resolve_but_tar_wins() -> None:
    legacy = f"llama-{TAG}-bin-ubuntu-x64.zip"
    selection = select_assets(_release([legacy]), os_name="linux", arch="x64", backend="cpu")
    assert selection.primary.name == legacy
    both = select_assets(
        _release([legacy, f"llama-{TAG}-bin-ubuntu-x64.tar.gz"]), os_name="linux", arch="x64", backend="cpu"
    )
    assert both.primary.name.endswith(".tar.gz")


def test_parse_release_keeps_only_github_assets_and_valid_digests() -> None:
    release = parse_release(
        {
            "tag_name": TAG,
            "published_at": "2026-10-30T00:00:00Z",
            "assets": [
                {"name": "a.zip", "browser_download_url": "https://github.com/x/a.zip", "size": 1, "digest": DIGEST},
                {"name": "b.zip", "browser_download_url": "https://evil.example/b.zip", "size": 1, "digest": DIGEST},
                {"name": "c.zip", "browser_download_url": "https://github.com/x/c.zip", "size": 1, "digest": "md5:x"},
                {"name": 5},
            ],
        }
    )
    assert [asset.name for asset in release.assets] == ["a.zip", "c.zip"]
    assert release.assets[0].digest == DIGEST and release.assets[1].digest is None


@pytest.mark.parametrize("payload", [None, [], {"tag_name": "latest"}, {"tag_name": "b1; rm -rf"}])
def test_unreadable_release_is_refused(payload: object) -> None:
    with pytest.raises(ReleaseError, match="llama_cpp_release_unreadable"):
        parse_release(payload)


def test_fetch_release_uses_the_api_and_maps_failures() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.path.endswith("/tags/b1234"):
            return httpx.Response(404)
        if request.url.path.endswith("/releases"):
            # GitHub's stable "latest" can be source-only. Automatic
            # installation must pass it over and choose the newest official
            # build release, even when GitHub marks that release prerelease.
            return httpx.Response(200, json=[
                {"tag_name": "v0.8.0", "assets": []},
                {"tag_name": TAG, "assets": [{
                    "name": NAMES[0],
                    "browser_download_url": f"https://github.com/x/{NAMES[0]}",
                    "size": 1,
                    "digest": DIGEST,
                }]},
            ])
        return httpx.Response(200, json={"tag_name": TAG, "assets": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert fetch_release(client=client).tag == TAG
    assert seen[0] == "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=100"
    with pytest.raises(ReleaseError, match="llama_cpp_release_not_found"):
        fetch_release("b1234", client=client)
    with pytest.raises(ReleaseError, match="llama_cpp_release_tag_invalid"):
        fetch_release("../../x", client=client)

    def broken(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    with pytest.raises(ReleaseError, match="llama_cpp_release_unreachable"):
        fetch_release(client=httpx.Client(transport=httpx.MockTransport(broken)))


def test_automatic_release_selection_refuses_when_no_build_release_exists() -> None:
    client = httpx.Client(transport=httpx.MockTransport(
        lambda _request: httpx.Response(200, json=[{"tag_name": "v0.8.0", "assets": []}])
    ))
    with pytest.raises(ReleaseError, match="llama_cpp_release_not_found"):
        fetch_release(client=client)
