"""Installing the official llama.cpp build into Raiker's own data directory.

The steps, each of which can refuse:

1. **Download** each selected asset from GitHub over HTTPS, following redirects
   only to GitHub's release hosts, refusing a body larger than the release says.
2. **Verify** the bytes against the SHA-256 digest GitHub publishes for the
   asset. An asset with no published digest is not installed: "probably the
   right bytes" is not a standard for an executable Raiker will run.
3. **Unpack** into a staging directory, refusing absolute paths, ``..``, device
   files and links that leave the directory.
4. **Self-check** by running ``llama-server --version`` and
   ``--list-devices``. A GPU build whose backend sees no device is reported as
   such, so the caller can fall back to the next backend rather than install a
   build that would silently run on the CPU — or not at all.
5. **Switch** atomically: the staged directory is renamed into place and
   ``current.json`` is replaced in one ``os.replace``. Until then the previous
   installation keeps serving.

Nothing is written outside ``<workspace>/runtimes/llama.cpp``, nothing needs
administrator rights, and uninstalling is deleting that directory.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import threading
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

import httpx

from raiker.contracts.views import View
from raiker.models.llama_cpp.releases import (
    ALLOWED_DOWNLOAD_HOSTS,
    AssetSelection,
    ReleaseAsset,
    ReleaseError,
)

EXECUTABLE = "llama-server.exe" if sys.platform == "win32" else "llama-server"
#: No llama.cpp archive is near this; a body past it is not the release.
MAX_ASSET_BYTES = 2 * 1024**3
_CHUNK = 1024 * 1024
_MANIFEST = "manifest.json"
_CURRENT = "current.json"

ProgressFn = Callable[[int, int | None, str], None]
CancelFn = Callable[[], None]

_install_lock = threading.Lock()


class InstallError(RuntimeError):
    """An installation that did not happen; ``str()`` is a bounded reason code."""

    bounded_reason = True


@dataclass(frozen=True)
class DeviceReport(View):
    """One device ``llama-server --list-devices`` says this build can use."""

    id: str
    name: str
    memory_total_bytes: int | None
    memory_free_bytes: int | None


@dataclass(frozen=True)
class Installation(View):
    tag: str
    backend: str
    os: str
    arch: str
    cuda_version: str | None
    directory: str
    executable: str
    version_text: str
    devices: tuple[DeviceReport, ...]
    installed_at: str
    assets: tuple[str, ...]


def runtime_root(workspace_root: Path) -> Path:
    return Path(workspace_root) / "runtimes" / "llama.cpp"


# ── download and verify ────────────────────────────────────────────────


def _check_host(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https" or (parts.hostname or "").lower() not in ALLOWED_DOWNLOAD_HOSTS:
        raise InstallError("llama_cpp_download_host_refused")


def download_asset(
    asset: ReleaseAsset,
    destination: Path,
    *,
    client: httpx.Client,
    progress: Callable[[int], None] | None = None,
    cancelled: CancelFn | None = None,
) -> Path:
    """Stream ``asset`` to ``destination`` and prove it matches its digest."""
    if asset.digest is None:
        raise InstallError("llama_cpp_release_unverified")
    if asset.size <= 0 or asset.size > MAX_ASSET_BYTES:
        raise InstallError("llama_cpp_asset_size_invalid")
    _check_host(asset.url)
    last: InstallError | None = None
    for attempt in range(DOWNLOAD_ATTEMPTS):
        if attempt:
            # GitHub's release CDN answers a large archive with 502/503/504 now
            # and then (2026-11-08: a 504 for the CUDA build failed every live
            # install). A few waits fix that; a 404 or a bad digest never retries.
            time.sleep(min(2 ** attempt, 30))
        try:
            return _download_once(asset, destination, client=client, progress=progress, cancelled=cancelled)
        except _TransientDownload as transient:
            last = InstallError("llama_cpp_download_failed")
            last.__cause__ = transient
    assert last is not None
    raise last


#: How many times a transient server or network failure is tried before failing.
DOWNLOAD_ATTEMPTS = 4


class _TransientDownload(Exception):
    """A 5xx or a dropped connection: worth another try."""


def _download_once(
    asset: ReleaseAsset,
    destination: Path,
    *,
    client: httpx.Client,
    progress: Callable[[int], None] | None,
    cancelled: CancelFn | None,
) -> Path:
    expected = (asset.digest or "").split(":", 1)[1]
    hasher = hashlib.sha256()
    received = 0
    try:
        with contextlib.ExitStack() as stack:
            url = asset.url
            for _ in range(6):
                _check_host(url)
                response = stack.enter_context(client.stream(
                    "GET", url, headers={"User-Agent": "Raiker"}, follow_redirects=False,
                ))
                _check_host(str(response.url))
                if not response.is_redirect:
                    break
                location = response.headers.get("location")
                if not location:
                    raise InstallError("llama_cpp_download_failed")
                url = str(response.url.join(location))
                response.close()
            else:
                raise InstallError("llama_cpp_download_failed")
            if response.status_code >= 500:
                raise _TransientDownload(f"http_{response.status_code}")
            if response.status_code != 200:
                raise InstallError("llama_cpp_download_failed")
            with destination.open("wb") as handle:
                for chunk in response.iter_bytes(_CHUNK):
                    received += len(chunk)
                    if received > asset.size:
                        raise InstallError("llama_cpp_download_oversize")
                    hasher.update(chunk)
                    handle.write(chunk)
                    if progress is not None:
                        progress(len(chunk))
                    if cancelled is not None:
                        cancelled()
    except (httpx.TransportError, httpx.RemoteProtocolError) as exc:
        destination.unlink(missing_ok=True)
        raise _TransientDownload(type(exc).__name__) from exc
    except httpx.HTTPError as exc:
        raise InstallError("llama_cpp_download_failed") from exc
    if received != asset.size:
        raise InstallError("llama_cpp_download_truncated")
    if hasher.hexdigest() != expected:
        destination.unlink(missing_ok=True)
        raise InstallError("llama_cpp_digest_mismatch")
    return destination


# ── unpack safely ──────────────────────────────────────────────────────


def _safe_member(name: str) -> PurePosixPath:
    normalised = name.replace("\\", "/")
    path = PurePosixPath(normalised)
    if (
        not normalised
        or path.is_absolute()
        or re.match(r"^[A-Za-z]:", normalised)
        or any(part == ".." for part in path.parts)
    ):
        raise InstallError("llama_cpp_archive_unsafe")
    return path


def _within(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def extract_archive(archive: Path, destination: Path) -> None:
    """Unpack a ``.zip`` or ``.tar.gz`` into ``destination``, refusing escapes."""
    destination.mkdir(parents=True, exist_ok=True)
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as bundle:
            for info in bundle.infolist():
                member = _safe_member(info.filename)
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise InstallError("llama_cpp_archive_unsafe")
                target = destination.joinpath(*member.parts)
                if not _within(destination, target):
                    raise InstallError("llama_cpp_archive_unsafe")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(info) as source, target.open("wb") as sink:
                    shutil.copyfileobj(source, sink, _CHUNK)
                if os.name != "nt" and mode & 0o111:
                    target.chmod(0o755)
        return
    if not archive.name.endswith((".tar.gz", ".tgz")):
        raise InstallError("llama_cpp_archive_format_unknown")
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        for entry in members:
            path = _safe_member(entry.name)
            target = destination.joinpath(*path.parts)
            if entry.isdev() or entry.isfifo() or not _within(destination, target):
                raise InstallError("llama_cpp_archive_unsafe")
            if entry.issym() or entry.islnk():
                link = PurePosixPath(entry.linkname.replace("\\", "/"))
                if link.is_absolute():
                    raise InstallError("llama_cpp_archive_unsafe")
                base = target.parent if entry.issym() else destination
                if not _within(destination, base.joinpath(*link.parts)):
                    raise InstallError("llama_cpp_archive_unsafe")
        if hasattr(tarfile, "data_filter"):
            bundle.extractall(destination, members=members, filter="data")
        else:  # pragma: no cover - Python < 3.11.4; every member was checked above
            bundle.extractall(destination, members=members)  # noqa: S202


def _single_root(directory: Path) -> Path:
    """An archive's own top-level folder, when it has exactly one."""
    entries = [entry for entry in directory.iterdir() if entry.name != "__MACOSX"]
    return entries[0] if len(entries) == 1 and entries[0].is_dir() else directory


def find_executable(directory: Path) -> Path | None:
    candidates = sorted(directory.rglob(EXECUTABLE), key=lambda path: len(path.parts))
    return next((path for path in candidates if path.is_file()), None)


# ── self-check ─────────────────────────────────────────────────────────

_DEVICE_LINE = re.compile(
    r"^\s*(?P<id>[A-Za-z]+\d+)\s*:\s*(?P<name>.+?)\s*\((?P<total>\d+)\s*MiB,\s*(?P<free>\d+)\s*MiB free\)"
)


def parse_devices(text: str) -> tuple[DeviceReport, ...]:
    devices: list[DeviceReport] = []
    for line in text.splitlines():
        match = _DEVICE_LINE.match(line)
        if match:
            devices.append(
                DeviceReport(
                    id=match.group("id"),
                    name=match.group("name"),
                    memory_total_bytes=int(match.group("total")) * 1024**2,
                    memory_free_bytes=int(match.group("free")) * 1024**2,
                )
            )
    return tuple(devices)


def runtime_environment(executable: Path) -> dict[str, str]:
    """The environment a managed ``llama-server`` runs with.

    Its shared libraries sit beside it. The release builds find them through
    ``$ORIGIN`` / ``@loader_path`` and Windows searches the executable's folder
    first, but naming the folder too costs nothing and survives a build that
    forgot the rpath.
    """
    env = dict(os.environ)
    folder = str(executable.parent)
    variable = {"linux": "LD_LIBRARY_PATH", "darwin": "DYLD_LIBRARY_PATH"}.get(sys.platform)
    if variable:
        env[variable] = os.pathsep.join(item for item in (folder, env.get(variable, "")) if item)
    elif sys.platform == "win32":
        env["PATH"] = os.pathsep.join((folder, env.get("PATH", "")))
    return env


def _run_tool(executable: Path, *args: str, timeout: float = 30.0) -> tuple[int, str]:
    try:
        completed = subprocess.run(  # noqa: S603 - our own verified executable, fixed argv
            [str(executable), *args],
            capture_output=True, text=True, timeout=timeout, check=False,
            stdin=subprocess.DEVNULL, env=runtime_environment(executable),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise InstallError("llama_cpp_install_unrunnable") from exc
    return completed.returncode, f"{completed.stdout}\n{completed.stderr}"


def self_check(executable: Path, backend: str) -> tuple[str, tuple[DeviceReport, ...]]:
    """The build's version line and its devices; refuses a build that cannot run."""
    code, output = _run_tool(executable, "--version")
    if code != 0 or "version" not in output.lower():
        raise InstallError("llama_cpp_install_unrunnable")
    version = next((line.strip() for line in output.splitlines() if "version" in line.lower()), "")
    devices: tuple[DeviceReport, ...] = ()
    if backend != "cpu":
        _code, listing = _run_tool(executable, "--list-devices")
        devices = parse_devices(listing)
        if not devices:
            raise InstallError("llama_cpp_backend_no_device")
    return version[:200], devices


# ── the install ────────────────────────────────────────────────────────


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def install(
    workspace_root: Path,
    selection: AssetSelection,
    *,
    client: httpx.Client | None = None,
    progress: ProgressFn | None = None,
    cancelled: CancelFn | None = None,
    verify: Callable[[Path, str], tuple[str, tuple[DeviceReport, ...]]] = self_check,
) -> Installation:
    """Download, verify, unpack, self-check and activate ``selection``."""
    if not _install_lock.acquire(blocking=False):
        raise InstallError("llama_cpp_install_in_progress")
    root = runtime_root(workspace_root)
    root.mkdir(parents=True, exist_ok=True)
    staging = root / f".staging-{os.getpid()}-{int(time.time() * 1000)}"
    owned = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(60.0, connect=20.0), follow_redirects=True)
    try:
        staging.mkdir()
        downloads = staging / "downloads"
        downloads.mkdir()
        total = selection.download_bytes
        done = 0

        def advance(count: int) -> None:
            nonlocal done
            done += count
            if progress is not None:
                progress(done, total, "downloading_llama_cpp")

        archives: list[Path] = []
        for asset in (selection.primary, *selection.companions):
            archives.append(
                download_asset(
                    asset, downloads / asset.name, client=client, progress=advance, cancelled=cancelled
                )
            )
        if progress is not None:
            progress(done, total, "unpacking_llama_cpp")
        unpacked = staging / "build"
        extract_archive(archives[0], unpacked)
        executable = find_executable(unpacked)
        if executable is None:
            raise InstallError("llama_cpp_server_not_in_archive")
        for companion in archives[1:]:
            scratch = staging / f"companion-{companion.name}"
            extract_archive(companion, scratch)
            source = _single_root(scratch)
            for entry in source.iterdir():
                target = executable.parent / entry.name
                if not target.exists():
                    shutil.move(str(entry), str(target))
        if os.name != "nt":
            executable.chmod(0o755)
        if cancelled is not None:
            cancelled()
        if progress is not None:
            progress(done, total, "verifying_llama_cpp")
        version, devices = verify(executable, selection.backend)
        name = f"{selection.tag}-{selection.backend}"
        final = root / name
        if final.exists():
            shutil.rmtree(final, ignore_errors=True)
        shutil.move(str(unpacked), str(final))
        relative = executable.relative_to(unpacked)
        installation = Installation(
            tag=selection.tag,
            backend=selection.backend,
            os=selection.os,
            arch=selection.arch,
            cuda_version=selection.cuda_version,
            directory=str(final),
            executable=str(final / relative),
            version_text=version,
            devices=devices,
            installed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            assets=tuple(asset.name for asset in (selection.primary, *selection.companions)),
        )
        manifest = installation.to_dict() | {
            "executable": str(relative),
            "directory": name,
            "digests": {
                asset.name: asset.digest for asset in (selection.primary, *selection.companions)
            },
        }
        _write_json_atomic(final / _MANIFEST, manifest)
        previous = _current_name(root)
        _write_json_atomic(root / _CURRENT, {"directory": name})
        if previous and previous != name:
            # A server still running from the old build keeps its files open on
            # Windows; what cannot be removed now is removed by the next install.
            shutil.rmtree(root / previous, ignore_errors=True)
        prune(workspace_root)
        return installation
    except ReleaseError as exc:
        raise InstallError(str(exc)) from exc
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        if owned:
            client.close()
        _install_lock.release()


def _current_name(root: Path) -> str | None:
    with contextlib.suppress(OSError, ValueError):
        data = json.loads((root / _CURRENT).read_text(encoding="utf-8"))
        name = data.get("directory") if isinstance(data, dict) else None
        if isinstance(name, str) and re.fullmatch(r"b\d+-(cuda|vulkan|metal|cpu)", name):
            return name
    return None


def current(workspace_root: Path) -> Installation | None:
    """The active managed installation, or ``None`` when there is none usable."""
    root = runtime_root(workspace_root)
    name = _current_name(root)
    if name is None:
        return None
    directory = root / name
    try:
        data = json.loads((directory / _MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    relative = _safe_member(str(data.get("executable", "")))
    executable = directory.joinpath(*relative.parts)
    if not executable.is_file() or not _within(directory, executable):
        return None
    devices = tuple(
        DeviceReport(
            id=str(item.get("id", "")),
            name=str(item.get("name", "")),
            memory_total_bytes=item.get("memory_total_bytes"),
            memory_free_bytes=item.get("memory_free_bytes"),
        )
        for item in data.get("devices", [])
        if isinstance(item, dict)
    )
    return Installation(
        tag=str(data.get("tag", "")),
        backend=str(data.get("backend", "cpu")),
        os=str(data.get("os", "")),
        arch=str(data.get("arch", "")),
        cuda_version=data.get("cuda_version"),
        directory=str(directory),
        executable=str(executable),
        version_text=str(data.get("version_text", "")),
        devices=devices,
        installed_at=str(data.get("installed_at", "")),
        assets=tuple(str(item) for item in data.get("assets", [])),
    )


def prune(workspace_root: Path) -> None:
    """Remove every build and stale staging directory except the active one."""
    root = runtime_root(workspace_root)
    keep = _current_name(root)
    if not root.is_dir():
        return
    for entry in root.iterdir():
        if entry.is_dir() and entry.name != keep:
            shutil.rmtree(entry, ignore_errors=True)


def uninstall(workspace_root: Path) -> None:
    root = runtime_root(workspace_root)
    with _install_lock:
        (root / _CURRENT).unlink(missing_ok=True)
        if root.is_dir():
            shutil.rmtree(root, ignore_errors=True)


@dataclass(frozen=True)
class ResolvedExecutable(View):
    path: str | None
    #: ``managed`` (installed by Raiker), ``path`` (the owner's own), or ``none``.
    source: str
    backend: str | None


def resolve_executable(workspace_root: Path) -> ResolvedExecutable:
    """Raiker's own installation first, then a ``llama-server`` on ``PATH``."""
    installed = current(workspace_root)
    if installed is not None:
        return ResolvedExecutable(installed.executable, "managed", installed.backend)
    found = shutil.which("llama-server")
    if found:
        return ResolvedExecutable(found, "path", None)
    return ResolvedExecutable(None, "none", None)
