"""Windows: the owner chooses the account or WSL2 for sandboxed commands.

Only commands follow the choice; hooks, MCP servers and plugins run Windows
interpreters and stay on the account. Choosing WSL2 before it is set up fails
closed: the probe measures WSL2 and commands refuse.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from raiker.execution.commands.backends import native as native_backend
from raiker.execution.commands.runner import MemoryCommandSink
from raiker.execution.commands.sandbox_backend import (
    load_windows_backend,
    save_windows_backend,
)
from raiker.execution.workspaces import TaskWorkspaceRegistry
from tests.test_command_backends import _installed_runner, request

WSL_REPORT = {
    "platform": "windows",
    "boundary": "wsl_bubblewrap",
    "available": False,
    "observations": {
        name: "enforced"
        for name in (
            "relay", "workspace_write", "escape_write", "masked_read", "egress",
            "descendant_reaped", "seccomp", "windows_interop", "loopback",
        )
    },
}
ACCOUNT_REPORT = {**WSL_REPORT, "boundary": "restricted_account"}


def test_the_choice_defaults_to_the_account_and_refuses_anything_else(tmp_path: Path) -> None:
    assert load_windows_backend(tmp_path) == "account"
    assert save_windows_backend(tmp_path, "wsl") == "wsl"
    assert load_windows_backend(tmp_path) == "wsl"
    with pytest.raises(ValueError, match="command_sandbox_backend_invalid"):
        save_windows_backend(tmp_path, "host")
    assert load_windows_backend(tmp_path) == "wsl"


def _driver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seen: list[list[str]], report: dict[str, Any]
) -> native_backend.NativeSandboxDriver:
    monkeypatch.setattr(native_backend, "_on_windows", lambda: True)
    workspace = tmp_path / "ws"
    workspace.mkdir(exist_ok=True)
    helper = _bundled(tmp_path)
    linux_digest = hashlib.sha256((helper.parent / "wsl-x86_64" / "raiker-command-runner").read_bytes()).hexdigest()

    def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
        seen.append(argv)
        if "--wsl-status" in argv:
            body: dict[str, Any] = {"configured": True, "base": str(tmp_path / "wsl-copies"), "runner_sha256": linux_digest}
        elif "--account-status" in argv:
            body = {"configured": True, "base": str(tmp_path / "account-copies")}
        elif "--probe" in argv:
            body = WSL_REPORT if "--boundary" in argv else report
        else:
            body = {}
        return subprocess.CompletedProcess(argv, 0, json.dumps(body), "")

    native_backend._ACCOUNT_BASE_CACHE.clear()
    return native_backend.NativeSandboxDriver(
        workspace, helper_root=helper, run_probe=run
    )


def test_with_wsl_chosen_commands_measure_wsl_and_programs_stay_on_the_account(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[list[str]] = []
    driver = _driver(tmp_path, monkeypatch, seen, ACCOUNT_REPORT)
    save_windows_backend(driver.workspace_root, "wsl")

    commands = driver.probe()
    assert commands.boundary == "wsl_bubblewrap" and commands.available
    assert next(a for a in seen if "--probe" in a)[-2:] == ["--boundary", "wsl"]

    seen.clear()
    programs = driver.probe(for_programs=True)
    assert programs.boundary == "restricted_account"
    assert "--boundary" not in next(a for a in seen if "--probe" in a)

    assert driver.copy_base() == tmp_path / "wsl-copies"
    assert driver.account_base() == tmp_path / "account-copies"
    native_backend._ACCOUNT_BASE_CACHE.clear()


def test_wsl_requires_seccomp_and_no_windows_interop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    driver = _driver(tmp_path, monkeypatch, [], ACCOUNT_REPORT)
    save_windows_backend(driver.workspace_root, "wsl")
    WSL_REPORT["observations"]["windows_interop"] = "unenforced"  # type: ignore[index]
    try:
        proof = driver.probe()
    finally:
        WSL_REPORT["observations"]["windows_interop"] = "enforced"  # type: ignore[index]
    assert not proof.available
    assert proof.reason_code == "native_sandbox_not_enforced"
    native_backend._ACCOUNT_BASE_CACHE.clear()


@pytest.mark.parametrize("installed_digest", [None, "0" * 64])
def test_wsl_runtime_refuses_an_installed_runner_without_the_packaged_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, installed_digest: str | None
) -> None:
    seen: list[list[str]] = []
    driver = _driver(tmp_path, monkeypatch, seen, ACCOUNT_REPORT)
    save_windows_backend(driver.workspace_root, "wsl")
    original = driver._run_probe

    def changed_runner(argv: list[str]) -> subprocess.CompletedProcess[str]:
        if "--wsl-status" in argv:
            seen.append(argv)
            return subprocess.CompletedProcess(argv, 0, json.dumps({"configured": True, "runner_sha256": installed_digest}), "")
        return original(argv)

    driver._run_probe = changed_runner
    proof = driver.probe()
    assert not proof.available
    assert proof.reason_code == "native_sandbox_wsl_runner_mismatch"
    assert not any("--probe" in argv for argv in seen)


def test_wsl_runtime_refuses_a_missing_bundled_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[list[str]] = []
    driver = _driver(tmp_path, monkeypatch, seen, ACCOUNT_REPORT)
    save_windows_backend(driver.workspace_root, "wsl")
    (driver.helper_root.parent / "wsl-x86_64" / "digest.json").unlink()
    proof = driver.probe()
    assert not proof.available
    assert proof.reason_code == "native_sandbox_wsl_runner_missing"
    assert not any("--probe" in argv for argv in seen)


@pytest.mark.parametrize("change", ["installed", "packaged"])
def test_cached_wsl_proof_does_not_license_a_changed_runner_at_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    from raiker.execution.commands.backends.base import CommandBackendError

    driver = _driver(tmp_path, monkeypatch, [], ACCOUNT_REPORT)
    save_windows_backend(driver.workspace_root, "wsl")
    proof = driver.probe()
    assert proof.available
    if change == "packaged":
        (driver.helper_root.parent / "wsl-x86_64" / "digest.json").unlink()
        expected = "native_sandbox_wsl_runner_missing"
    else:
        monkeypatch.setattr(driver, "wsl_status", lambda: {"configured": True, "runner_sha256": "0" * 64})
        expected = "native_sandbox_wsl_runner_mismatch"
    launched: list[object] = []
    backend = native_backend.NativeSandboxBackend(
        driver=driver, proof=proof, workspaces=TaskWorkspaceRegistry(tmp_path / "copies"),
        runner=lambda *args, **kwargs: launched.append(args),
    )
    with pytest.raises(CommandBackendError, match=expected):
        backend.start(request(driver.workspace_root, argv_template=("cat", "seed.txt")), MemoryCommandSink())
    assert not launched
    assert not (tmp_path / "copies").exists()


def test_with_the_account_chosen_nothing_asks_wsl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[list[str]] = []
    driver = _driver(tmp_path, monkeypatch, seen, ACCOUNT_REPORT)
    assert driver.probe().boundary == "restricted_account"
    assert driver.copy_base() == tmp_path / "account-copies"
    assert not any("--wsl-status" in argv or "--boundary" in argv for argv in seen)
    native_backend._ACCOUNT_BASE_CACHE.clear()


def test_a_wsl_run_passes_linux_argv_through_without_mounts_or_downloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from raiker.execution.commands.egress_runtime import save_settings

    seen: list[list[str]] = []
    driver = _driver(tmp_path, monkeypatch, seen, ACCOUNT_REPORT)
    save_windows_backend(driver.workspace_root, "wsl")
    save_settings(driver.workspace_root, True, ["pypi.org"])
    launched: list[dict[str, Any]] = []

    def fake_runner(req: Any, argv: list[str], cwd: Path, env: dict[str, str], sink: Any, **_k: Any) -> Any:
        launched.append({"argv": argv, "policy": json.loads(Path(argv[2]).read_text(encoding="utf-8"))})
        return object()

    backend = native_backend.NativeSandboxBackend(
        driver=driver,
        proof=driver.probe(),
        workspaces=TaskWorkspaceRegistry(tmp_path / "copies"),
        runner=fake_runner,
    )
    (driver.workspace_root / "src").mkdir()
    backend.start(
        request(driver.workspace_root, argv_template=("python3", "-m", "pytest"), cwd="src"),
        MemoryCommandSink(),
    )
    [run] = launched
    assert run["argv"][run["argv"].index("--") + 1 :] == ["python3", "-m", "pytest"]
    assert run["policy"]["toolchain_paths"] == []
    assert run["policy"]["network"] == "none"
    assert run["policy"]["wsl_runner_sha256"] == hashlib.sha256(b"\x7fELF linux runner").hexdigest()
    native_backend._ACCOUNT_BASE_CACHE.clear()


def test_the_bundled_linux_runner_is_found_only_with_a_matching_digest(tmp_path: Path) -> None:
    import hashlib

    helper = _installed_runner(tmp_path)
    driver = native_backend.NativeSandboxDriver(tmp_path, helper_root=helper)
    assert driver.wsl_runner() is None
    wsl = helper.parent / "wsl-x86_64"
    wsl.mkdir()
    binary = wsl / "raiker-command-runner"
    binary.write_bytes(b"\x7fELF linux runner")
    (wsl / "digest.json").write_text(
        json.dumps({"sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}), encoding="utf-8"
    )
    assert driver.wsl_runner() == binary
    binary.write_bytes(b"\x7fELF replaced")
    assert driver.wsl_runner() is None


def _bundled(tmp_path: Path) -> Path:
    import hashlib

    helper = _installed_runner(tmp_path)
    wsl = helper.parent / "wsl-x86_64"
    wsl.mkdir()
    binary = wsl / "raiker-command-runner"
    binary.write_bytes(b"\x7fELF linux runner")
    (wsl / "digest.json").write_text(
        json.dumps({"sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}), encoding="utf-8"
    )
    return helper


def test_setup_runs_the_bundled_linux_runner_with_the_owners_tarball(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(native_backend, "_on_windows", lambda: True)
    helper = _bundled(tmp_path)
    sent: list[list[str]] = []

    def run_setup(argv: list[str]) -> subprocess.CompletedProcess[str]:
        sent.append(argv)
        return subprocess.CompletedProcess(argv, 0, "{}", "")

    driver = native_backend.NativeSandboxDriver(tmp_path, helper_root=helper, run_setup=run_setup)
    rootfs = tmp_path / "ubuntu-base-24.04-base-amd64.tar.gz"
    rootfs.write_bytes(b"tar")

    assert driver.setup_wsl(rootfs) == (True, "")
    [argv] = sent
    assert argv[1:3] == ["--setup-wsl", "--linux-runner"]
    assert argv[3] == str(helper.parent / "wsl-x86_64" / "raiker-command-runner")
    assert argv[4:] == ["--rootfs", str(rootfs)]

    assert driver.setup_wsl(tmp_path / "missing.tar") == (False, "native_sandbox_wsl_rootfs_invalid")
    notes = tmp_path / "notes.txt"
    notes.write_text("x")
    assert driver.setup_wsl(notes) == (False, "native_sandbox_wsl_rootfs_invalid")
    assert driver.reset_wsl() == (True, "")
    assert sent[-1][1:] == ["--reset-wsl"]


def test_setup_reports_the_runners_own_refusal_and_needs_the_bundled_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(native_backend, "_on_windows", lambda: True)
    rootfs = tmp_path / "base.tar"
    rootfs.write_bytes(b"tar")
    refused = '{"raiker_runner_error":"native_sandbox_wsl_bubblewrap_missing"}\n'
    driver = native_backend.NativeSandboxDriver(
        tmp_path,
        helper_root=_bundled(tmp_path),
        run_setup=lambda argv: subprocess.CompletedProcess(argv, 91, "", refused),
    )
    assert driver.setup_wsl(rootfs) == (False, "native_sandbox_wsl_bubblewrap_missing")

    bare = native_backend.NativeSandboxDriver(tmp_path / "other", helper_root=_installed_runner(tmp_path / "other"))
    assert bare.setup_wsl(rootfs) == (False, "native_sandbox_wsl_runner_missing")


def test_setup_is_refused_off_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(native_backend, "_on_windows", lambda: False)
    driver = native_backend.NativeSandboxDriver(tmp_path, helper_root=_bundled(tmp_path))
    assert driver.setup_wsl(tmp_path / "base.tar") == (False, "native_sandbox_wsl_unavailable")
    assert driver.reset_wsl() == (False, "native_sandbox_wsl_unavailable")


def test_the_account_requires_its_loopback_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A host set up before the WFP loopback filter refuses until setup runs again."""
    driver = _driver(tmp_path, monkeypatch, [], ACCOUNT_REPORT)
    observations = ACCOUNT_REPORT["observations"]
    observations["loopback"] = "unenforced"  # type: ignore[index]
    try:
        proof = driver.probe()
    finally:
        observations["loopback"] = "enforced"  # type: ignore[index]
    assert not proof.available
    assert proof.reason_code == "native_sandbox_not_enforced"
    assert driver.probe().available
    native_backend._ACCOUNT_BASE_CACHE.clear()
