"""Downloading, verifying, unpacking and activating a llama.cpp build."""

from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import sys
import tarfile
import zipfile
from pathlib import Path

import httpx
import pytest

from raiker.models.llama_cpp import installer
from raiker.models.llama_cpp.installer import DeviceReport, InstallError
from raiker.models.llama_cpp.releases import AssetSelection, ReleaseAsset

EXE = installer.EXECUTABLE
FAKE_SERVER = Path(__file__).parent / "fixtures" / "llama_cpp" / "fake_llama_server.py"


def _tar(entries: dict[str, bytes], *, links: dict[str, str] | None = None) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as bundle:
        for name, data in entries.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o755
            bundle.addfile(info, io.BytesIO(data))
        for name, target in (links or {}).items():
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            bundle.addfile(info)
    return buffer.getvalue()


def _zip(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for name, data in entries.items():
            bundle.writestr(name, data)
    return buffer.getvalue()


def _asset(name: str, data: bytes, *, digest: str | None = "auto") -> ReleaseAsset:
    value = f"sha256:{hashlib.sha256(data).hexdigest()}" if digest == "auto" else digest
    return ReleaseAsset(name, f"https://github.com/ggml-org/llama.cpp/releases/download/b7000/{name}", len(data), value)


def _client(blobs: dict[str, bytes], *, redirect_to: str | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        name = request.url.path.rsplit("/", 1)[-1]
        if request.url.host == "github.com" and redirect_to is not None:
            return httpx.Response(302, headers={"Location": f"{redirect_to}/{name}"})
        return httpx.Response(200, content=blobs[name])

    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def _selection(primary: ReleaseAsset, *companions: ReleaseAsset, backend: str = "cpu") -> AssetSelection:
    return AssetSelection("b7000", backend, "linux", "x64", primary, tuple(companions))


def _ok(_executable: Path, _backend: str) -> tuple[str, tuple[DeviceReport, ...]]:
    return "version: 7000 (test)", ()


def test_install_verifies_unpacks_and_activates(tmp_path: Path) -> None:
    data = _tar({f"llama-b7000/{EXE}": b"#!/bin/sh\n", "llama-b7000/libllama.so": b"lib"})
    asset = _asset("llama-b7000-bin-ubuntu-x64.tar.gz", data)
    progress: list[tuple[int, int | None, str]] = []
    result = installer.install(
        tmp_path, _selection(asset), client=_client({asset.name: data}),
        progress=lambda done, total, phase: progress.append((done, total, phase)), verify=_ok,
    )
    assert Path(result.executable).is_file()
    assert result.tag == "b7000" and result.backend == "cpu"
    assert progress[-1][2] == "verifying_llama_cpp"
    assert any(phase == "downloading_llama_cpp" and done == len(data) for done, _, phase in progress)
    current = installer.current(tmp_path)
    assert current is not None and current.executable == result.executable
    resolved = installer.resolve_executable(tmp_path)
    assert resolved.source == "managed" and resolved.backend == "cpu"
    manifest = json.loads((Path(result.directory) / "manifest.json").read_text())
    assert manifest["digests"][asset.name] == asset.digest
    # No staging or download debris is left behind.
    assert sorted(p.name for p in installer.runtime_root(tmp_path).iterdir()) == ["b7000-cpu", "current.json"]
    if os.name != "nt":
        assert os.stat(result.executable).st_mode & stat.S_IXUSR


def test_cuda_runtime_libraries_land_beside_the_server(tmp_path: Path) -> None:
    build = _zip({EXE: b"exe", "ggml-cuda.dll": b"dll"})
    runtime = _zip({"cudart64_12.dll": b"rt", "cublas64_12.dll": b"blas"})
    primary = _asset("llama-b7000-bin-win-cuda-12.4-x64.zip", build)
    companion = _asset("cudart-llama-bin-win-cuda-12.4-x64.zip", runtime)
    result = installer.install(
        tmp_path, _selection(primary, companion, backend="cuda"),
        client=_client({primary.name: build, companion.name: runtime}), verify=_ok,
    )
    folder = Path(result.executable).parent
    assert (folder / "cudart64_12.dll").read_bytes() == b"rt"
    assert (folder / "cublas64_12.dll").is_file()
    assert result.assets == (primary.name, companion.name)


def test_redirect_to_github_cdn_is_followed(tmp_path: Path) -> None:
    data = _tar({f"x/{EXE}": b"exe"})
    asset = _asset("llama-b7000-bin-ubuntu-x64.tar.gz", data)
    client = _client({asset.name: data}, redirect_to="https://release-assets.githubusercontent.com/a")
    assert installer.install(tmp_path, _selection(asset), client=client, verify=_ok).tag == "b7000"


def test_redirect_off_github_is_refused(tmp_path: Path) -> None:
    data = _tar({f"x/{EXE}": b"exe"})
    asset = _asset("llama-b7000-bin-ubuntu-x64.tar.gz", data)
    client = _client({asset.name: data}, redirect_to="https://evil.example")
    with pytest.raises(InstallError, match="llama_cpp_download_host_refused"):
        installer.install(tmp_path, _selection(asset), client=client, verify=_ok)
    assert installer.current(tmp_path) is None


def test_digest_mismatch_installs_nothing(tmp_path: Path) -> None:
    data = _tar({f"x/{EXE}": b"exe"})
    asset = _asset("llama-b7000-bin-ubuntu-x64.tar.gz", data, digest="sha256:" + "0" * 64)
    with pytest.raises(InstallError, match="llama_cpp_digest_mismatch"):
        installer.install(tmp_path, _selection(asset), client=_client({asset.name: data}), verify=_ok)
    assert installer.current(tmp_path) is None
    assert [p.name for p in installer.runtime_root(tmp_path).iterdir()] == []


def test_asset_without_published_digest_is_never_installed(tmp_path: Path) -> None:
    data = _tar({f"x/{EXE}": b"exe"})
    asset = _asset("llama-b7000-bin-ubuntu-x64.tar.gz", data, digest=None)
    with pytest.raises(InstallError, match="llama_cpp_release_unverified"):
        installer.install(tmp_path, _selection(asset), client=_client({asset.name: data}), verify=_ok)


def test_body_larger_than_published_size_is_refused(tmp_path: Path) -> None:
    data = _tar({f"x/{EXE}": b"exe"})
    asset = ReleaseAsset("big.tar.gz", "https://github.com/x/big.tar.gz", 10, "sha256:" + "0" * 64)
    with pytest.raises(InstallError, match="llama_cpp_download_oversize"):
        installer.install(tmp_path, _selection(asset), client=_client({"big.tar.gz": data}), verify=_ok)


@pytest.mark.parametrize(
    "entries",
    [{"../evil": b"x"}, {"/etc/evil": b"x"}, {"C:/evil": b"x"}, {"a/../../evil": b"x"}],
)
def test_zip_escape_is_refused(tmp_path: Path, entries: dict[str, bytes]) -> None:
    archive = tmp_path / "bad.zip"
    archive.write_bytes(_zip(entries))
    with pytest.raises(InstallError, match="llama_cpp_archive_unsafe"):
        installer.extract_archive(archive, tmp_path / "out")
    assert not (tmp_path / "evil").exists()


def test_tar_symlink_out_of_the_build_is_refused(tmp_path: Path) -> None:
    archive = tmp_path / "bad.tar.gz"
    archive.write_bytes(_tar({"x/ok": b"1"}, links={"x/link": "../../../etc/passwd"}))
    with pytest.raises(InstallError, match="llama_cpp_archive_unsafe"):
        installer.extract_archive(archive, tmp_path / "out")


def test_tar_symlink_inside_the_build_is_kept(tmp_path: Path) -> None:
    if sys.platform == "win32":
        pytest.skip("symlink creation needs privileges on Windows")
    archive = tmp_path / "ok.tar.gz"
    archive.write_bytes(_tar({"x/libllama.so.0": b"lib"}, links={"x/libllama.so": "libllama.so.0"}))
    installer.extract_archive(archive, tmp_path / "out")
    assert (tmp_path / "out" / "x" / "libllama.so").read_bytes() == b"lib"


def test_failed_self_check_keeps_the_previous_build(tmp_path: Path) -> None:
    first = _tar({f"a/{EXE}": b"v1"})
    asset = _asset("llama-b7000-bin-ubuntu-x64.tar.gz", first)
    installed = installer.install(tmp_path, _selection(asset), client=_client({asset.name: first}), verify=_ok)

    def broken(_executable: Path, _backend: str) -> tuple[str, tuple[DeviceReport, ...]]:
        raise InstallError("llama_cpp_backend_no_device")

    second = _tar({f"b/{EXE}": b"v2"})
    vulkan = _asset("llama-b7000-bin-ubuntu-vulkan-x64.tar.gz", second)
    with pytest.raises(InstallError, match="llama_cpp_backend_no_device"):
        installer.install(
            tmp_path, _selection(vulkan, backend="vulkan"), client=_client({vulkan.name: second}), verify=broken
        )
    current = installer.current(tmp_path)
    assert current is not None and current.executable == installed.executable


def test_switching_backend_replaces_and_prunes_the_old_build(tmp_path: Path) -> None:
    cpu = _tar({f"a/{EXE}": b"cpu"})
    vulkan = _tar({f"b/{EXE}": b"vk"})
    a = _asset("llama-b7000-bin-ubuntu-x64.tar.gz", cpu)
    b = _asset("llama-b7000-bin-ubuntu-vulkan-x64.tar.gz", vulkan)
    installer.install(tmp_path, _selection(a), client=_client({a.name: cpu}), verify=_ok)
    result = installer.install(tmp_path, _selection(b, backend="vulkan"), client=_client({b.name: vulkan}), verify=_ok)
    assert Path(result.executable).read_bytes() == b"vk"
    names = sorted(p.name for p in installer.runtime_root(tmp_path).iterdir())
    assert names == ["b7000-vulkan", "current.json"]


def test_concurrent_install_is_refused(tmp_path: Path) -> None:
    assert installer._install_lock.acquire(blocking=False)
    try:
        data = _tar({f"x/{EXE}": b"exe"})
        asset = _asset("a.tar.gz", data)
        with pytest.raises(InstallError, match="llama_cpp_install_in_progress"):
            installer.install(tmp_path, _selection(asset), client=_client({asset.name: data}), verify=_ok)
    finally:
        installer._install_lock.release()


def test_cancel_during_download_cleans_up(tmp_path: Path) -> None:
    data = _tar({f"x/{EXE}": b"exe"})
    asset = _asset("a.tar.gz", data)

    class Stop(Exception):
        pass

    def cancel() -> None:
        raise Stop

    with pytest.raises(Stop):
        installer.install(tmp_path, _selection(asset), client=_client({asset.name: data}), cancelled=cancel, verify=_ok)
    assert installer.current(tmp_path) is None
    assert list(installer.runtime_root(tmp_path).iterdir()) == []


def test_tampered_current_pointer_is_ignored(tmp_path: Path) -> None:
    root = installer.runtime_root(tmp_path)
    root.mkdir(parents=True)
    (root / "current.json").write_text(json.dumps({"directory": "../../etc"}))
    assert installer.current(tmp_path) is None


def test_uninstall_removes_everything(tmp_path: Path) -> None:
    data = _tar({f"x/{EXE}": b"exe"})
    asset = _asset("a.tar.gz", data)
    installer.install(tmp_path, _selection(asset), client=_client({asset.name: data}), verify=_ok)
    installer.uninstall(tmp_path)
    assert installer.current(tmp_path) is None
    assert not installer.runtime_root(tmp_path).exists()


def test_parse_devices_reads_llama_server_listing() -> None:
    devices = installer.parse_devices(
        "Available devices:\n"
        "  CUDA0: NVIDIA GeForce RTX 4090 (24563 MiB, 23000 MiB free)\n"
        "  Vulkan0: AMD Radeon RX 7900 XTX (RADV NAVI31) (24560 MiB, 24000 MiB free)\n"
        "  Metal: Apple M3 Max\n"
    )
    assert [device.id for device in devices] == ["CUDA0", "Vulkan0"]
    assert devices[0].memory_free_bytes == 23000 * 1024**2
    assert devices[1].name == "AMD Radeon RX 7900 XTX (RADV NAVI31)"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shebang stand-in")
def test_self_check_runs_the_real_binary_interface(tmp_path: Path) -> None:
    executable = tmp_path / "llama-server"
    executable.write_text(f"#!{sys.executable}\nimport runpy, sys\nsys.argv[0] = {str(FAKE_SERVER)!r}\n"
                          f"runpy.run_path({str(FAKE_SERVER)!r}, run_name='__main__')\n")
    executable.chmod(0o755)
    version, devices = installer.self_check(executable, "cuda")
    assert "9999" in version
    assert devices[0].id == "CUDA0"
    version, devices = installer.self_check(executable, "cpu")
    assert devices == ()


def test_self_check_refuses_a_binary_that_cannot_run(tmp_path: Path) -> None:
    executable = tmp_path / EXE
    executable.write_bytes(b"\x00not a program")
    if os.name != "nt":
        executable.chmod(0o755)
    with pytest.raises(InstallError, match="llama_cpp_install_unrunnable"):
        installer.self_check(executable, "cpu")
