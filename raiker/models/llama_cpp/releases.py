"""Which official llama.cpp release asset this machine should run.

ggml-org publishes one archive per platform and backend on every ``b<NNNN>``
release (``.github/workflows/release.yml`` and ``release-publish.yml`` in
ggml-org/llama.cpp)::

    llama-<tag>-bin-macos-arm64.tar.gz            Metal, Apple silicon
    llama-<tag>-bin-macos-x64.tar.gz              CPU, Intel Mac
    llama-<tag>-bin-ubuntu-<arch>.tar.gz          CPU
    llama-<tag>-bin-ubuntu-vulkan-<arch>.tar.gz   Vulkan
    llama-<tag>-bin-ubuntu-cuda-<v>-<arch>.tar.gz CUDA   + cudart-llama-<tag>-bin-ubuntu-cuda-<v>-<arch>.tar.gz
    llama-<tag>-bin-win-cpu-<arch>.zip            CPU
    llama-<tag>-bin-win-vulkan-<arch>.zip         Vulkan
    llama-<tag>-bin-win-cuda-<v>-<arch>.zip       CUDA   + cudart-llama-bin-win-cuda-<v>-<arch>.zip

Older releases used ``.zip`` everywhere, so both extensions are accepted. The
CUDA version in the name moves between releases, so it is matched, not pinned:
the newest build the driver supports wins.

Selection (:func:`select_assets`) is a pure function over asset names, so every
platform's choice is tested on any host. Fetching the release
(:func:`fetch_release`) is the only network call, and it is made only when the
owner asks to install or to check for an update.
"""

from __future__ import annotations

import contextlib
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from raiker.contracts.views import View

REPOSITORY = "ggml-org/llama.cpp"
API_ROOT = f"https://api.github.com/repos/{REPOSITORY}/releases"
RELEASES_PAGE = f"https://github.com/{REPOSITORY}/releases"
LICENSE_URL = f"https://github.com/{REPOSITORY}/blob/master/LICENSE"

#: Hosts a release asset may be served from. GitHub redirects downloads from
#: ``github.com`` to its release-asset CDN; anything else is refused.
ALLOWED_DOWNLOAD_HOSTS = frozenset(
    {"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"}
)

_TAG = re.compile(r"^b\d{3,6}$")
_ARCHIVE = r"(?P<ext>tar\.gz|zip)"


class ReleaseError(ValueError):
    """A release that cannot be installed; ``str()`` is a bounded reason code."""

    bounded_reason = True


@dataclass(frozen=True)
class ReleaseAsset(View):
    name: str
    url: str
    size: int
    #: ``sha256:<hex>`` as GitHub publishes it, or ``None`` on an asset uploaded
    #: before GitHub computed digests. Such an asset is never installed.
    digest: str | None


@dataclass(frozen=True)
class Release(View):
    tag: str
    published_at: str | None
    assets: tuple[ReleaseAsset, ...]


@dataclass(frozen=True)
class AssetSelection(View):
    tag: str
    backend: str
    os: str
    arch: str
    #: The llama.cpp build itself.
    primary: ReleaseAsset
    #: The CUDA runtime libraries a CUDA build needs beside it; empty otherwise.
    companions: tuple[ReleaseAsset, ...]
    cuda_version: str | None = None

    @property
    def download_bytes(self) -> int:
        return self.primary.size + sum(asset.size for asset in self.companions)


def _pattern(os_name: str, backend: str, arch: str, tag: str) -> re.Pattern[str]:
    t = re.escape(tag)
    if os_name == "macos":
        return re.compile(rf"^llama-{t}-bin-macos-{arch}\.{_ARCHIVE}$")
    platform = "ubuntu" if os_name == "linux" else "win"
    if backend == "cuda":
        return re.compile(rf"^llama-{t}-bin-{platform}-cuda-(?P<cuda>\d+\.\d+)-{arch}\.{_ARCHIVE}$")
    if backend == "vulkan":
        return re.compile(rf"^llama-{t}-bin-{platform}-vulkan-{arch}\.{_ARCHIVE}$")
    if os_name == "linux":
        return re.compile(rf"^llama-{t}-bin-ubuntu-{arch}\.{_ARCHIVE}$")
    return re.compile(rf"^llama-{t}-bin-win-cpu-{arch}\.{_ARCHIVE}$")


def _cudart_names(os_name: str, tag: str, cuda: str, arch: str) -> tuple[str, ...]:
    if os_name == "linux":
        stem = f"cudart-llama-{tag}-bin-ubuntu-cuda-{cuda}-{arch}"
    else:
        stem = f"cudart-llama-bin-win-cuda-{cuda}-{arch}"
    return (f"{stem}.tar.gz", f"{stem}.zip")


def _version(text: str) -> tuple[int, int]:
    major, minor = text.split(".")[:2]
    return int(major), int(minor)


def _pick_cuda(available: Sequence[str], driver: str | None) -> str | None:
    """The newest CUDA build the driver can run.

    A driver runs any toolkit up to the version it reports. Within one major
    version CUDA's minor-version compatibility lets a newer build run too, so
    that is the fallback when nothing older is published.
    """
    if not available:
        return None
    ordered = sorted(set(available), key=_version, reverse=True)
    if driver is None:
        return None
    limit = _version(driver)
    within = [version for version in ordered if _version(version) <= limit]
    if within:
        return within[0]
    same_major = [version for version in ordered if _version(version)[0] == limit[0]]
    return same_major[0] if same_major else None


def select_assets(
    release: Release,
    *,
    os_name: str,
    arch: str,
    backend: str,
    cuda_driver_version: str | None = None,
) -> AssetSelection:
    """The archive(s) to install for ``backend`` on this platform.

    Raises :class:`ReleaseError` with ``llama_cpp_backend_unsupported`` when the
    platform has no such build (Metal off Apple silicon, CUDA on a Mac), and
    ``llama_cpp_asset_missing`` when this release did not publish it.
    """
    if os_name not in {"windows", "macos", "linux"} or arch not in {"x64", "arm64"}:
        raise ReleaseError("llama_cpp_platform_unsupported")
    if os_name == "macos":
        # One build per Mac architecture. The Apple-silicon build carries Metal
        # *and* the CPU backend, so "cpu" there is the same download run with no
        # offload — what a Mac without a usable Metal device (a VM) needs.
        allowed = {"metal", "cpu"} if arch == "arm64" else {"cpu"}
        if backend not in allowed:
            raise ReleaseError("llama_cpp_backend_unsupported")
    elif backend == "metal":
        raise ReleaseError("llama_cpp_backend_unsupported")
    if backend not in {"cuda", "vulkan", "metal", "cpu"}:
        raise ReleaseError("llama_cpp_backend_unsupported")
    pattern = _pattern(os_name, backend, arch, release.tag)
    matches = [(asset, pattern.match(asset.name)) for asset in release.assets]
    found = [(asset, match) for asset, match in matches if match is not None]
    if not found:
        raise ReleaseError("llama_cpp_asset_missing")
    cuda_version: str | None = None
    companions: tuple[ReleaseAsset, ...] = ()
    if backend == "cuda":
        versions = [match.group("cuda") for _asset, match in found]
        cuda_version = _pick_cuda(versions, cuda_driver_version)
        if cuda_version is None:
            raise ReleaseError("llama_cpp_cuda_driver_too_old")
        found = [(asset, match) for asset, match in found if match.group("cuda") == cuda_version]
        names = _cudart_names(os_name, release.tag, cuda_version, arch)
        runtime = next((asset for asset in release.assets if asset.name in names), None)
        if runtime is None:
            raise ReleaseError("llama_cpp_asset_missing")
        companions = (runtime,)
    # Prefer the current tar.gz over a legacy zip when a release has both.
    found.sort(key=lambda pair: pair[1].group("ext") != "tar.gz")
    return AssetSelection(
        tag=release.tag, backend=backend, os=os_name, arch=arch,
        primary=found[0][0], companions=companions, cuda_version=cuda_version,
    )


def parse_release(payload: Any) -> Release:
    """A GitHub release API answer, validated down to what selection needs."""
    if not isinstance(payload, dict):
        raise ReleaseError("llama_cpp_release_unreadable")
    tag = payload.get("tag_name")
    if not isinstance(tag, str) or not _TAG.match(tag):
        raise ReleaseError("llama_cpp_release_unreadable")
    assets: list[ReleaseAsset] = []
    for entry in payload.get("assets") or []:
        if not isinstance(entry, dict):
            continue
        name, url, size = entry.get("name"), entry.get("browser_download_url"), entry.get("size")
        if not isinstance(name, str) or not isinstance(url, str) or not isinstance(size, int):
            continue
        if not url.startswith("https://github.com/"):
            continue
        digest = entry.get("digest")
        valid = isinstance(digest, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
        assets.append(ReleaseAsset(name, url, size, digest if valid else None))
    published = payload.get("published_at")
    return Release(tag, published if isinstance(published, str) else None, tuple(assets))


#: 2026-11-08 — llama.cpp publishes a release and then uploads its ~40
#: archives over several minutes. Every live install job that ran in the
#: minute after b12195 appeared failed on an asset that was not there yet.
#: Automatic installation takes the newest release that has been public this
#: long; a newer one is offered on the next update check.
RELEASE_SETTLE = timedelta(minutes=30)


def settled_release(candidates: Sequence[Release], *, now: datetime | None = None) -> Release:
    """The newest release old enough to have finished uploading, else the newest."""
    moment = now or datetime.now(UTC)
    for release in candidates:
        if release.published_at is None:
            continue
        try:
            published = datetime.fromisoformat(release.published_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if moment - published >= RELEASE_SETTLE:
            return release
    return candidates[0]


def fetch_release(
    tag: str | None = None, *, client: httpx.Client | None = None, now: datetime | None = None
) -> Release:
    """A usable official build release, or the one named ``tag``.

    ``/releases/latest`` follows GitHub's stable-release flag, not llama.cpp's
    binary publishing channel. It can therefore point at a stable source
    release with no runtime archives while the current ``bNNNN`` prereleases
    contain the supported binaries. Automatic installation uses the releases
    collection instead and takes the first valid build release with assets.
    An explicitly requested tag remains exact.
    """
    if tag is not None and not _TAG.match(tag):
        raise ReleaseError("llama_cpp_release_tag_invalid")
    url = f"{API_ROOT}?per_page=100" if tag is None else f"{API_ROOT}/tags/{tag}"
    owned = client is None
    client = client or httpx.Client(timeout=20.0, follow_redirects=True)
    try:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "Raiker"}
        # Opt-in only, and Raiker's own variable: a general GITHUB_TOKEN in the
        # owner's environment is never sent anywhere on their behalf. CI sets
        # this to avoid the per-IP rate limit shared by hosted runners.
        token = os.environ.get("RAIKER_GITHUB_API_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise ReleaseError("llama_cpp_release_unreachable") from exc
    finally:
        if owned:
            client.close()
    if response.status_code == 404:
        raise ReleaseError("llama_cpp_release_not_found")
    if response.status_code != 200:
        raise ReleaseError("llama_cpp_release_unreachable")
    try:
        payload = response.json()
        if tag is not None:
            return parse_release(payload)
        if not isinstance(payload, list):
            raise ReleaseError("llama_cpp_release_unreadable")
        candidates: list[Release] = []
        for entry in payload:
            with contextlib.suppress(ReleaseError):
                release = parse_release(entry)
                if release.assets:
                    candidates.append(release)
        if not candidates:
            raise ReleaseError("llama_cpp_release_not_found")
        return settled_release(candidates, now=now)
    except ValueError as exc:
        if isinstance(exc, ReleaseError):
            raise
        raise ReleaseError("llama_cpp_release_unreadable") from exc
