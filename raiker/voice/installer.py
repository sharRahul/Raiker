"""Download, verify and lay out voice components. Nothing unverified is kept.

Every file comes from the catalogue (:mod:`raiker.voice.catalogue`) and is
streamed to a temporary file, checked against its SHA-256 and size, and only
then moved into place. Archives (engine builds) are unpacked with the same
escape-refusing extractor the llama.cpp engine uses. A component is recorded
as installed by writing ``installed.json`` beside it last, so a half-finished
install is never mistaken for a finished one.

Layout, under the workspace::

    runtimes/voice/<item id>/            one folder per catalogue item
    runtimes/voice/<item id>/installed.json
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from raiker.models.llama_cpp.installer import extract_archive
from raiker.voice.catalogue import (
    ALLOWED_DOWNLOAD_HOSTS,
    CatalogueError,
    CatalogueItem,
    require_installable,
)

_CHUNK = 1024 * 1024
ARCHIVE_COMPONENTS = frozenset({"whisper_engine", "piper_engine"})


class VoiceInstallError(RuntimeError):
    bounded_reason = True


def voice_root(workspace_root: Path) -> Path:
    return Path(workspace_root) / "runtimes" / "voice"


def item_dir(workspace_root: Path, item_id: str) -> Path:
    return voice_root(workspace_root) / item_id


def _marker(workspace_root: Path, item_id: str) -> Path:
    return item_dir(workspace_root, item_id) / "installed.json"


def is_installed(workspace_root: Path, item: CatalogueItem) -> bool:
    marker = _marker(workspace_root, item.item_id)
    try:
        recorded = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(recorded, dict) and recorded.get("sha256") == item.sha256


def installed_path(workspace_root: Path, item: CatalogueItem) -> Path | None:
    """The file (model) or executable (engine) an installed item provides."""
    if not is_installed(workspace_root, item):
        return None
    folder = item_dir(workspace_root, item.item_id)
    if item.component in ARCHIVE_COMPONENTS:
        name = item.executable or ""
        found = sorted(folder.rglob(name), key=lambda path: len(path.parts)) if name else []
        return next((path for path in found if path.is_file()), None)
    name = Path(urlsplit(item.url or "").path).name
    candidate = folder / name
    return candidate if candidate.is_file() else None


def _check_host(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https" or (parts.hostname or "").lower() not in ALLOWED_DOWNLOAD_HOSTS:
        raise VoiceInstallError("voice_download_host_refused")


def download(
    item: CatalogueItem,
    destination: Path,
    *,
    client: httpx.Client,
    progress: Callable[[int], None] | None = None,
    cancelled: Callable[[], None] | None = None,
) -> Path:
    """Stream ``item`` to ``destination`` and prove it matches the catalogue."""
    try:
        require_installable(item)
    except CatalogueError as exc:
        raise VoiceInstallError(str(exc)) from exc
    assert item.url and item.sha256 and item.size_bytes  # checked by require_installable
    _check_host(item.url)
    hasher = hashlib.sha256()
    received = 0
    partial = destination.with_name(destination.name + ".part")
    try:
        with client.stream("GET", item.url, headers={"User-Agent": "Raiker"}, follow_redirects=True) as response:
            for hop in [*response.history, response]:
                _check_host(str(hop.url))
            if response.status_code != 200:
                raise VoiceInstallError("voice_download_failed")
            with partial.open("wb") as handle:
                for chunk in response.iter_bytes(_CHUNK):
                    received += len(chunk)
                    if received > item.size_bytes:
                        raise VoiceInstallError("voice_download_oversize")
                    hasher.update(chunk)
                    handle.write(chunk)
                    if progress is not None:
                        progress(len(chunk))
                    if cancelled is not None:
                        cancelled()
    except httpx.HTTPError as exc:
        partial.unlink(missing_ok=True)
        raise VoiceInstallError("voice_download_failed") from exc
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    if received != item.size_bytes:
        partial.unlink(missing_ok=True)
        raise VoiceInstallError("voice_download_truncated")
    if hasher.hexdigest() != item.sha256:
        partial.unlink(missing_ok=True)
        raise VoiceInstallError("voice_digest_mismatch")
    os.replace(partial, destination)
    return destination


def install_item(
    workspace_root: Path,
    item: CatalogueItem,
    *,
    client: httpx.Client,
    progress: Callable[[int], None] | None = None,
    cancelled: Callable[[], None] | None = None,
) -> Path:
    """Install one item, or return at once if it already is."""
    try:
        require_installable(item)
    except CatalogueError as exc:
        raise VoiceInstallError(str(exc)) from exc
    if is_installed(workspace_root, item):
        found = installed_path(workspace_root, item)
        if found is not None:
            return found
    folder = item_dir(workspace_root, item.item_id)
    staging = folder.with_name(folder.name + ".staging")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        name = Path(urlsplit(item.url or "").path).name or item.item_id
        fetched = download(item, staging / name, client=client, progress=progress, cancelled=cancelled)
        if item.component in ARCHIVE_COMPONENTS:
            unpacked = staging / "unpacked"
            try:
                extract_archive(fetched, unpacked)
            except Exception as exc:  # noqa: BLE001 - the extractor's own codes name llama.cpp
                raise VoiceInstallError("voice_archive_unsafe") from exc
            fetched.unlink(missing_ok=True)
        (staging / "installed.json").write_text(
            json.dumps({"item_id": item.item_id, "sha256": item.sha256, "size_bytes": item.size_bytes}),
            encoding="utf-8",
        )
        shutil.rmtree(folder, ignore_errors=True)
        os.replace(staging, folder)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    found = installed_path(workspace_root, item)
    if found is None:
        raise VoiceInstallError("voice_install_incomplete")
    if item.component in ARCHIVE_COMPONENTS and os.name != "nt":
        found.chmod(0o755)
    return found


def remove_all(workspace_root: Path) -> int:
    """Remove every voice component. Returns the bytes freed."""
    root = voice_root(workspace_root)
    freed = 0
    if root.is_dir():
        for path in root.rglob("*"):
            if path.is_file():
                try:
                    freed += path.stat().st_size
                except OSError:
                    continue
        shutil.rmtree(root, ignore_errors=True)
    return freed


def installed_bytes(workspace_root: Path) -> int:
    root = voice_root(workspace_root)
    total = 0
    if root.is_dir():
        for path in root.rglob("*"):
            if path.is_file():
                try:
                    total += path.stat().st_size
                except OSError:
                    continue
    return total
